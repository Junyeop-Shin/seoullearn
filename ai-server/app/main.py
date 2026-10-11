"""AI 서버 API. 매뉴얼 Q&A(/qa), 의도 분류 라우터(/chat), 양식 초안(/drafts/…), 규칙 도구(/tools/…)가 있다."""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from datetime import date
from typing import Annotated, Any

from . import allowance, forms, guard, inquiry, qa, router, unanswered
from .config import settings
from .llm import LLMUnavailableError, get_chat_model
from .pipelines import build_retriever

# 요청 본문(질문 원문)은 로그에 남기지 않는다. 길이와 결과 유형만 남김.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ai-server")



def _warm() -> None:
    try:
        _retriever()
    except Exception as e:   # 실패해도 서버는 뜨고 첫 질문에서 다시 만든다
        log.warning("warmup failed=%s", type(e).__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 검색기(임베딩 모델과 색인)를 뒤에서 미리 만들어 첫 질문이 느리지 않게 한다. 서버는 바로 요청을 받는다
    threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(title="서울런 멘토 업무 지원 AI 서버", version="0.1.0", lifespan=lifespan)
PIPELINE = os.getenv("QA_PIPELINE", "md_hybrid_glossary")
CORPUS = os.getenv("QA_CORPUS", "v2")


_building = threading.Lock()


@lru_cache(maxsize=1)
def _build_retriever():
    r, _ = build_retriever(PIPELINE, CORPUS)
    return r


def _retriever():
    with _building:   # 첫 질문이 겹치거나 시작할 때의 미리 만들기와 겹쳐도 한 번만 만든다
        return _build_retriever()


@lru_cache(maxsize=1)
def _llm():
    return get_chat_model("answer")


class QARequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)


class QAResponse(BaseModel):
    answer: str
    answerable: str
    route: str | None
    route_info: str | None
    citations: list[str]
    sources: list[dict[str, str]] = []      # 근거로 쓴 자료의 이름표와 본문 (화면에서 펼쳐 본다)
    changed_notices: list[str] = []         # 근거로 쓴 활동가이드 내용을 바꾼 공지의 제목
    pii_masked: list[str]
    safety: bool
    # 답을 다 못 했을 때(partial·no) 문의처에 보낼 글 초안과 연락 방법. 아동 안전 경로에서는 만들지 않는다.
    inquiry_draft: str | None = None
    inquiry_contact: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=1000)


class ChatResponse(BaseModel):
    intent: str  # qa | report | plan | safety | calc(활동비 계산)
    method: str  # guard(안전 가드) | rule(규칙) | llm(LLM 분류)
    answer: str
    pii_masked: list[str]
    # intent가 qa·safety일 때
    answerable: str | None = None
    route: str | None = None
    route_info: str | None = None
    citations: list[str] = []
    sources: list[dict[str, str]] = []
    changed_notices: list[str] = []
    safety: bool = False
    inquiry_draft: str | None = None
    inquiry_contact: str | None = None
    # intent가 report·plan일 때: 이동할 화면과 거기서 입력할 항목
    screen: str | None = None
    form_id: str | None = None
    required_inputs: list[str] = []


@lru_cache(maxsize=1)
def _graph():
    return router.build_graph(_llm, _retriever)


class DraftRequest(BaseModel):
    # 필드 key별 입력값. 양식마다 다르므로 모양을 고정하지 않는다 (GET /api/forms/{formId}의 fields 참고)
    inputs: dict[str, Any] = Field(default_factory=dict)
    # 필드가 아닌 참고 입력 (사전 연락 답변, 주차별 계획, 인계 요약 등)
    extra: dict[str, Any] = Field(default_factory=dict)


def _draft_llm():
    return _llm()  # 모델 객체를 하나만 둔다: 분당 호출 제한(LLM_RPM)이 객체마다 따로 세어진다


def _log_draft(form_id: str, res) -> None:
    # 본문은 남기지 않는다. 양식 이름과 개수만 남긴다
    log.info("draft form=%s fields=%d missing=%d warnings=%d pii=%s error=%s", form_id, len(res.draft),
             len(res.missing_questions), len(res.warnings), res.pii_masked, bool(res.error))


@app.get("/health")
def health():
    return {"status": "ok", "pipeline": PIPELINE, "corpus": CORPUS, "llm": f"{settings.llm_provider}:{settings.llm_model}"}


@app.post("/qa", response_model=QAResponse)
def ask(req: QARequest):
    try:
        # 아동 안전 신호가 있으면 검색기와 LLM을 만들지도 않는다 (DB나 키에 문제가 있어도 안내는 나가야 한다)
        safe = guard.check(req.question).safety
        res = qa.answer(req.question, None if safe else _retriever(), None if safe else _llm(), settings.top_k)
        draft = inquiry.build(res)
    except LLMUnavailableError:
        log.warning("qa len=%d llm_unavailable", len(req.question))
        raise HTTPException(status_code=503, detail="지금은 답변을 만들 수 없습니다. 잠시 후 다시 시도해 주세요.")
    log.info("qa len=%d answerable=%s route=%s pii=%s safety=%s error=%s draft=%s",
             len(req.question), res.answerable, res.route, res.pii_masked, res.safety, bool(res.error), draft is not None)
    if not res.error:   # 답변을 만들다 실패한 질문은 '자료에 없는 질문'이 아니다
        unanswered.record(req.question, res.answerable, res.route, res.safety)
    return QAResponse(answer=res.answer, answerable=res.answerable, route=res.route, route_info=qa.route_contact(res.route),
                      citations=res.cite_labels, sources=res.sources, changed_notices=res.changed_notices,
                      pii_masked=res.pii_masked, safety=res.safety,
                      inquiry_draft=draft.text if draft else None, inquiry_contact=draft.contact if draft else None)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        state = _graph().invoke({"message": req.message})
    except LLMUnavailableError:
        log.warning("chat len=%d llm_unavailable", len(req.message))
        raise HTTPException(status_code=503, detail="지금은 답변을 만들 수 없습니다. 잠시 후 다시 시도해 주세요.")
    result = dict(state["result"])
    if state["intent"] == "qa":
        unanswered.record(req.message, result.get("answerable"), result.get("route"), bool(result.get("safety")))
    log.info("chat len=%d intent=%s method=%s pii=%s classify_error=%s error=%s",
             len(req.message), state["intent"], state["method"], state.get("pii_masked", []),
             bool(state.get("classify_error")), bool(result.pop("error", False)))
    return ChatResponse(intent=state["intent"], method=state["method"], pii_masked=state.get("pii_masked", []), **result)


class PreContactRequest(BaseModel):
    mode: str = Field("온라인", pattern="^(온라인|오프라인)$")
    subject: str = Field("", max_length=30)   # 신청 과목 (문자에 '수학 멘토'처럼 넣는다)


class OutlineRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)


class DateRange(BaseModel):
    start: date
    end: date


class WeeklyPlanRequest(BaseModel):
    lectures: list[dict[str, Any]] = Field(..., max_length=300)  # 목차 파서 결과 [{no, title, ...}]
    done: int = Field(0, ge=0)
    sessions: int = Field(16, ge=1, le=40)
    pace: str = Field("보통", pattern="^(느림|보통|빠름)$")
    per_week: int | None = Field(None, ge=1, le=10)    # 일주일에 몇 강씩
    target: int | None = Field(None, ge=1, le=300)     # 이번 회기에 들을 강 수(목표)
    start_date: date | None = None
    exams: list[DateRange] = []
    breaks: list[DateRange] = []


# 아래 세 경로는 양식 엔진을 거치지 않는 전용 기능이다. /drafts/{form_id}보다 먼저 등록해야 한다.
@app.post("/drafts/pre_contact")
def pre_contact(req: PreContactRequest):
    res = forms.precontact.build(req.mode, req.subject)
    log.info("draft form=pre_contact mode=%s len=%d", res["mode"], len(res["sms"]["text"]))
    return res


@app.post("/drafts/course_outline")
def course_outline(req: OutlineRequest):
    try:
        res = forms.outline.parse(req.text, _draft_llm())
    except LLMUnavailableError:
        res = forms.outline.parse(req.text, None)  # 규칙으로 읽은 것만이라도 돌려준다
        res["warnings"].append("지금은 AI를 쓸 수 없어 자동으로 읽힌 강의만 정리했습니다. 빠진 강의가 없는지 확인해 주세요.")
    log.info("draft form=course_outline len=%d lectures=%d unparsed=%d error=%s", len(req.text), len(res["lectures"]),
             len(res["unparsed"]), bool(res["error"]))
    return res


class OutlineImageRequest(BaseModel):
    image: str = Field(..., min_length=30, max_length=forms.outline.MAX_IMAGE_CHARS)   # data:image/...;base64,...


@app.post("/drafts/course_outline_image")
def course_outline_image(req: OutlineImageRequest):
    try:
        res = forms.outline.read_image(req.image, _draft_llm())
    except LLMUnavailableError:
        res = {"text": "", "lines": 0, "error": "지금은 AI를 쓸 수 없습니다. 잠시 후 다시 시도하거나 목록을 복사해 붙여 넣어 주세요."}
    except Exception as e:   # 이미지를 받지 못하는 모델 등: 제공사마다 예외가 달라 종류만 남긴다
        log.warning("draft form=course_outline_image failed=%s", type(e).__name__)
        res = {"text": "", "lines": 0, "error": "이미지를 읽지 못했습니다. 지금 모델이 이미지를 받지 못할 수 있습니다. 강의 목록을 복사해 붙여 넣어 주세요."}
    # 이미지도 읽은 글도 남기지 않는다. 크기와 줄 수만 남긴다
    log.info("draft form=course_outline_image size=%d lines=%d error=%s", len(req.image), res["lines"], bool(res["error"]))
    return res


@app.post("/drafts/weekly_plan")
def weekly_plan(req: WeeklyPlanRequest):
    if any(not isinstance(x.get("title"), str) for x in req.lectures):
        raise HTTPException(status_code=422, detail="제목이 없는 강의가 있습니다. [목차 불러오기]를 다시 눌러 주세요.")
    if req.done > len(req.lectures):
        raise HTTPException(status_code=422, detail="이미 들은 강의 수가 불러온 강의 수보다 많습니다. 숫자를 고쳐 주세요.")
    alloc = forms.weekly_plan.allocate(req.lectures, req.done, req.sessions, req.pace, req.start_date,
                                       [(r.start, r.end) for r in req.exams], [(r.start, r.end) for r in req.breaks],
                                       per_week=req.per_week, target=req.target)
    try:
        res = forms.weekly_plan.write_lines(alloc, _draft_llm())
    except LLMUnavailableError:
        res = forms.weekly_plan.write_lines(alloc, None)
        res["warnings"].append("지금은 AI를 쓸 수 없어 기본 문장으로 채웠습니다.")
    log.info("draft form=weekly_plan lectures=%d sessions=%d covered=%d left=%d error=%s", len(req.lectures), req.sessions,
             res["covered"], res["left"], bool(res.get("error")))
    return res


class AllowanceRequest(BaseModel):
    mode: str = Field(..., pattern="^(온라인|오프라인)$")
    normal: int = Field(0, ge=0, le=60)        # 정상 진행해 승인된 회차 수
    no_show: int = Field(0, ge=0, le=60)       # 멘티 무단결석 (증빙 승인 시 기본수당만)
    late_cancel: int = Field(0, ge=0, le=60)   # 임박취소 (온라인, 준비수당만)
    stage: int = Field(1, ge=1, le=6)          # 장기활동 가산금 구간 (온라인)
    senior: bool = False                       # 고학년지도 가산금
    vulnerable: bool = False                   # 취약계층지원 가산금
    hours: int = Field(1, ge=1, le=2)          # 회차당 시간 (시간확대면 2)
    monthly_valid: list[Annotated[int, Field(ge=0, le=99)]] = Field(default_factory=list, max_length=36)   # 달마다의 유효 진행 횟수 (구간 변화를 보고 싶을 때)


@app.post("/tools/allowance")
def allowance_calc(req: AllowanceRequest):
    """활동비 계산기. 규칙 함수만 쓴다 (LLM 없음). 입력에는 개인정보가 없다."""
    res = allowance.estimate(req.mode, req.normal, req.no_show, req.late_cancel, req.stage, req.senior, req.vulnerable, req.hours)
    if req.monthly_valid and req.mode == "온라인":
        res["months"] = allowance.stages_by_month(req.monthly_valid, req.stage)
    log.info("tool=allowance mode=%s total=%d", req.mode, res["total"])
    return res


class AllowanceGroup(BaseModel):
    mode: str = Field(..., pattern="^(온라인|오프라인)$")
    hours: int = Field(1, ge=1, le=2)
    normal: int = Field(0, ge=0, le=31)
    no_show: int = Field(0, ge=0, le=31)
    late_cancel: int = Field(0, ge=0, le=31)
    senior: bool = False


class AllowanceMonthRequest(BaseModel):
    groups: list[AllowanceGroup] = Field(..., min_length=1, max_length=20)   # 멘티 한 명이 한 줄. 이름은 받지 않는다
    stage: int = Field(1, ge=1, le=6)
    vulnerable: bool = False


@app.post("/tools/allowance_month")
def allowance_month(req: AllowanceMonthRequest):
    """여러 멘티의 한 달 활동비 추정. 규칙 함수만 쓴다 (LLM 없음). 입력은 회차 수와 조건뿐이고 개인정보가 없다."""
    res = allowance.estimate_month([g.model_dump() for g in req.groups], req.stage, req.vulnerable)
    log.info("tool=allowance_month groups=%d total=%d", len(req.groups), res["total"])
    return res


class HandoverRequest(BaseModel):
    reports: list[dict[str, Any]] = Field(..., max_length=40)   # 활동보고서 초안들 (필드 key별 값)


@app.post("/drafts/handover_summary")
def handover_summary(req: HandoverRequest):
    try:
        res = forms.handover.build(req.reports, _draft_llm())
    except LLMUnavailableError:
        log.warning("draft form=handover_summary llm_unavailable")
        raise HTTPException(status_code=503, detail="지금은 초안을 만들 수 없습니다. 잠시 후 다시 시도해 주세요.")
    log.info("draft form=handover_summary reports=%d items=%d warnings=%d pii=%s errors=%d", len(req.reports),
             sum(bool(v) for v in res["summary"].values()), len(res["warnings"]), res["pii_masked"], len(res["errors"]))
    return res


@app.post("/drafts/{form_id}")
def draft(form_id: str, req: DraftRequest):
    """양식 엔진으로 초안을 만든다. forms/<form_id>.json에 fields가 있는 양식이면 코드 수정 없이 쓸 수 있다."""
    try:
        form = forms.engine.load_form(form_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="해당 양식을 찾을 수 없습니다.")
    if "fields" not in form:
        raise HTTPException(status_code=404, detail="이 양식은 초안 생성을 지원하지 않습니다.")
    try:
        res = forms.draft(form_id, req.inputs, _draft_llm(), req.extra)
    except LLMUnavailableError:
        log.warning("draft form=%s llm_unavailable", form_id)
        raise HTTPException(status_code=503, detail="지금은 초안을 만들 수 없습니다. 잠시 후 다시 시도해 주세요.")
    except (TypeError, KeyError, AttributeError, ValueError) as e:   # 양식과 모양이 다른 입력: 종류만 남긴다
        log.warning("draft form=%s bad_input=%s", form_id, type(e).__name__)
        raise HTTPException(status_code=422, detail="입력 형식을 확인해 주세요.")
    _log_draft(form_id, res)
    return res.to_dict()

"""AI 서버 API. 매뉴얼 Q&A(/qa)와 의도 분류 라우터(/chat)가 있다. 보고서 초안은 다음 단계에서 추가."""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from datetime import date, datetime
from typing import Any

from . import forms, guard, inquiry, qa, router, unanswered
from .config import settings
from .llm import LLMUnavailableError, get_chat_model
from .pipelines import build_retriever

# 요청 본문(질문 원문)은 로그에 남기지 않는다. 길이와 결과 유형만 남김.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ai-server")

app = FastAPI(title="서울런 멘토 업무 지원 AI 서버", version="0.1.0")
PIPELINE = os.getenv("QA_PIPELINE", "md_hybrid_glossary")
CORPUS = os.getenv("QA_CORPUS", "v2")


@lru_cache(maxsize=1)
def _retriever():
    r, _ = build_retriever(PIPELINE, CORPUS)
    return r


@lru_cache(maxsize=1)
def _llm():
    return get_chat_model("answer")


class QARequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    # 소속 자치구 이음단 카카오톡 오픈채팅 주소. 멘토 브라우저에 저장해 두고 요청마다 보낸다 (서버 저장 안 함).
    ieumdan_chat_url: str | None = Field(None, max_length=200, pattern=qa.KAKAO_OPENCHAT_PATTERN)


class QAResponse(BaseModel):
    answer: str
    answerable: str
    route: str | None
    route_info: str | None
    route_link: str | None
    citations: list[str]
    pii_masked: list[str]
    safety: bool
    # 답을 다 못 했을 때(partial·no) 문의처에 보낼 글 초안과 연락 방법. 아동 안전 경로에서는 만들지 않는다.
    inquiry_draft: str | None = None
    inquiry_contact: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=1000)
    ieumdan_chat_url: str | None = Field(None, max_length=200, pattern=qa.KAKAO_OPENCHAT_PATTERN)


class ChatResponse(BaseModel):
    intent: str  # qa | report | plan | safety
    method: str  # guard(안전 가드) | rule(규칙) | llm(LLM 분류)
    answer: str
    pii_masked: list[str]
    # intent가 qa·safety일 때
    answerable: str | None = None
    route: str | None = None
    route_info: str | None = None
    route_link: str | None = None
    citations: list[str] = []
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


@lru_cache(maxsize=1)
def _draft_llm():
    return get_chat_model("answer")


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
        res = qa.answer(req.question, _retriever(), _llm(), settings.top_k)
        draft = inquiry.build(res, _llm(), req.ieumdan_chat_url)
    except LLMUnavailableError:
        log.warning("qa len=%d llm_unavailable", len(req.question))
        raise HTTPException(status_code=503, detail="지금은 답변을 만들 수 없습니다. 잠시 후 다시 시도해 주세요.")
    log.info("qa len=%d answerable=%s route=%s pii=%s safety=%s error=%s draft=%s draft_error=%s",
             len(req.question), res.answerable, res.route, res.pii_masked, res.safety, bool(res.error),
             draft is not None, bool(draft and draft.error))
    unanswered.record(req.question, res.answerable, res.route, res.safety)
    info, link = qa.route_contact(res.route, req.ieumdan_chat_url)
    return QAResponse(answer=res.answer, answerable=res.answerable, route=res.route,
                      route_info=info, route_link=link,
                      citations=res.cite_labels, pii_masked=res.pii_masked, safety=res.safety,
                      inquiry_draft=draft.text if draft else None, inquiry_contact=draft.contact if draft else None)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        state = _graph().invoke({"message": req.message, "ieumdan_chat_url": req.ieumdan_chat_url})
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
    call_time: str | None = Field(None, max_length=20)
    answers: dict[str, Any] | None = None


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
    start_date: date | None = None
    exams: list[DateRange] = []
    breaks: list[DateRange] = []
    context: dict[str, Any] = Field(default_factory=dict)  # 과목, 멘티가 말한 목표 등 (선택)


# 아래 세 경로는 양식 엔진을 거치지 않는 전용 기능이다. /drafts/{form_id}보다 먼저 등록해야 한다.
@app.post("/drafts/pre_contact")
def pre_contact(req: PreContactRequest):
    res = forms.precontact.build(req.mode, req.call_time, req.answers)
    log.info("draft form=pre_contact mode=%s questions=%d sms_parts=%d", res["mode"], len(res["questions"]), len(res["sms"]["parts"]))
    return res


@app.post("/drafts/course_outline")
def course_outline(req: OutlineRequest):
    try:
        res = forms.outline.parse(req.text, _draft_llm())
    except LLMUnavailableError:
        res = forms.outline.parse(req.text, None)  # 규칙으로 읽은 것만이라도 돌려준다
        res["warnings"].append("지금은 AI를 쓸 수 없어 규칙으로 읽은 강의만 정리했습니다.")
    log.info("draft form=course_outline len=%d lectures=%d unparsed=%d error=%s", len(req.text), len(res["lectures"]),
             len(res["unparsed"]), bool(res["error"]))
    return res


@app.post("/drafts/weekly_plan")
def weekly_plan(req: WeeklyPlanRequest):
    if req.done > len(req.lectures):
        raise HTTPException(status_code=422, detail="이미 들은 강 수가 전체 강 수보다 많습니다.")
    alloc = forms.weekly_plan.allocate(req.lectures, req.done, req.sessions, req.pace, req.start_date,
                                       [(r.start, r.end) for r in req.exams], [(r.start, r.end) for r in req.breaks])
    masked = {k: (guard.check(v).text if isinstance(v, str) else v) for k, v in req.context.items()}
    try:
        res = forms.weekly_plan.write_lines(alloc, _draft_llm(), masked)
    except LLMUnavailableError:
        res = forms.weekly_plan.write_lines(alloc, None)
        res["warnings"].append("지금은 AI를 쓸 수 없어 기본 문장으로 채웠습니다.")
    log.info("draft form=weekly_plan lectures=%d sessions=%d covered=%d left=%d error=%s", len(req.lectures), req.sessions,
             res["covered"], res["left"], bool(res.get("error")))
    return res


class SplitRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)


class HandoverRequest(BaseModel):
    reports: list[dict[str, Any]] = Field(..., max_length=40)   # 활동보고서 초안들 (필드 key별 값)


class IeumdanRequest(BaseModel):
    kind: str = Field(..., pattern="^(장소 요청|일정 변경|장소 변경)$")
    region: str = Field("", max_length=100)
    schedule: str = Field("", max_length=100)
    current: datetime | None = None
    desired: datetime | None = None
    reason: str = Field("", max_length=200)


@app.post("/drafts/split_reports")
def split_reports(req: SplitRequest):
    res = forms.report_split.split(req.text)
    log.info("draft form=split_reports len=%d sessions=%d warnings=%d", len(req.text), len(res["sessions"]), len(res["warnings"]))
    return res


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


@app.post("/drafts/ieumdan_request")
def ieumdan_request(req: IeumdanRequest):
    res = forms.ieumdan.build(req.kind, req.region, req.schedule, req.current, req.desired, req.reason)
    log.info("draft form=ieumdan_request kind=%s len=%d warnings=%d pii=%s", req.kind, res["length"], len(res["warnings"]), res["pii_masked"])
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
    _log_draft(form_id, res)
    return res.to_dict()

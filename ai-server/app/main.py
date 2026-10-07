"""AI 서버 API. 지금은 매뉴얼 Q&A만 있다. 보고서 초안은 다음 단계에서 추가."""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import qa
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


@app.get("/health")
def health():
    return {"status": "ok", "pipeline": PIPELINE, "corpus": CORPUS, "llm": f"{settings.llm_provider}:{settings.llm_model}"}


@app.post("/qa", response_model=QAResponse)
def ask(req: QARequest):
    try:
        res = qa.answer(req.question, _retriever(), _llm(), settings.top_k)
    except LLMUnavailableError:
        log.warning("qa len=%d llm_unavailable", len(req.question))
        raise HTTPException(status_code=503, detail="지금은 답변을 만들 수 없습니다. 잠시 후 다시 시도해 주세요.")
    log.info("qa len=%d answerable=%s route=%s pii=%s safety=%s error=%s",
             len(req.question), res.answerable, res.route, res.pii_masked, res.safety, bool(res.error))
    info, link = qa.route_contact(res.route, req.ieumdan_chat_url)
    return QAResponse(answer=res.answer, answerable=res.answerable, route=res.route,
                      route_info=info, route_link=link,
                      citations=res.cite_labels, pii_masked=res.pii_masked, safety=res.safety)

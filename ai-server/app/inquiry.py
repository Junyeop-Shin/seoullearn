"""문의 초안: 답을 다 못 했을 때 문의처에 보낼 글을 만들어 준다.

LLM은 문장만 만든다. 연락처는 코드가 붙이고, 초안은 내보내기 전에 가드로 한 번 더 가린다.
아동 안전 경로에서는 초안을 만들지 않는다 (즉시 전화 안내만).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from . import guard
from .llm import ChatLLM, LLMUnavailableError
from .qa import ROUTE_INFO, QAResult

SYSTEM = """너는 서울런 멘토가 문의처에 보낼 문의 글의 초안을 쓴다. 아래 규칙을 반드시 지킨다.

1. 한국어 존댓말, 3~4문장. 첫 문장은 '안녕하세요, 서울런 멘토입니다.'로 시작한다.
2. [질문]의 요지를 한 문장으로 정리하고, [확인한 근거]를 이미 확인했다는 점을 밝힌 뒤, 확인을 부탁한다.
3. [질문]과 [확인한 근거]에 없는 사실(날짜, 횟수, 금액, 사정)을 만들지 않는다.
4. 멘티·멘토의 이름, 학교, 연락처는 쓰지 않는다. 필요하면 '담당 멘티'라고 쓴다.
5. 문의처 이름, 전화번호, 주소는 쓰지 않는다 (따로 붙인다).

반드시 아래 JSON 한 개만 출력한다. 코드블록 표시는 쓰지 않는다.
{"draft": "..."}"""


@dataclass
class InquiryDraft:
    text: str
    contact: str | None  # 문의처 연락 방법 (이음단이면 오픈채팅 주소)
    error: str | None = None  # LLM 출력 형식 오류. 이때 text는 정해진 틀로 만든 초안이다


def _fallback(question: str, pages: str) -> str:
    return (f"안녕하세요, 서울런 멘토입니다. 다음 내용을 문의드립니다: {question} "
            f"{pages}을(를) 확인했지만 해당 내용을 찾지 못했습니다. 확인 부탁드립니다.")


def needs_draft(res: QAResult) -> bool:
    return not res.safety and res.answerable in ("partial", "no") and bool(res.route) and res.route != "운영사무국(즉시)"


def build(res: QAResult, llm: ChatLLM, ieumdan_chat_url: str | None = None) -> InquiryDraft | None:
    if not needs_draft(res):
        return None
    question = guard.check(res.question).text
    pages = ", ".join(dict.fromkeys(res.cite_labels)) or "활동가이드"
    contact = ieumdan_chat_url if res.route == "이음단" and ieumdan_chat_url else ROUTE_INFO.get(res.route)
    error = None
    try:
        raw = llm.complete(SYSTEM, f"[문의처]\n{res.route}\n\n[질문]\n{question}\n\n[확인한 근거]\n{pages}")
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise ValueError("JSON 없음")
        text = str(json.loads(m.group(0))["draft"]).strip()
        if not text:
            raise ValueError("빈 초안")
    except LLMUnavailableError:
        raise
    except Exception as e:  # 형식 오류는 기록하고 정해진 틀로 대신한다
        error = f"{type(e).__name__}: {e}"
        text = _fallback(question, pages)
    return InquiryDraft(text=guard.check(text).text, contact=contact, error=error)

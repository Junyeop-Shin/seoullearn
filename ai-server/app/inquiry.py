"""문의 초안: 답을 다 못 했을 때 문의처에 보낼 글을 정해진 틀로 만든다.

LLM을 부르지 않는다. 질문에 없는 사정을 지어 붙이지 않고, 답을 못 한 질문마다 호출이 하나 더 붙지 않게 하려는 것이다.
가드로 가린 질문만 쓰고 가린 자리표시는 뺀다. 연락처는 코드가 붙인다. 아동 안전 경로에서는 초안을 만들지 않는다 (즉시 전화 안내만).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import guard
from .qa import ROUTE_INFO, QAResult


@dataclass
class InquiryDraft:
    text: str
    contact: str | None  # 문의처 연락 방법


def needs_draft(res: QAResult) -> bool:
    # 답변을 만들다 실패한 것(형식 오류)은 자료에 없는 것이 아니다: '찾아보았지만 찾지 못했다'는 초안을 만들지 않는다
    return not res.safety and not res.error and res.answerable in ("partial", "no") and bool(res.route) and res.route != "운영사무국(즉시)"


def build(res: QAResult) -> InquiryDraft | None:
    if not needs_draft(res):
        return None
    question = guard.drop_marks(guard.check(res.question).text)
    pages = ", ".join(dict.fromkeys(res.cite_labels))
    checked = (f"{pages}에서 일부 내용은 확인했지만 정확한 기준을 찾지 못했습니다." if pages
               else "활동가이드와 공지에서 찾아보았지만 해당 내용을 찾지 못했습니다.")
    text = f"안녕하세요, 서울런 멘토입니다. 아래 내용을 문의드립니다.\n\n{question}\n\n{checked} 확인 부탁드립니다."
    return InquiryDraft(text=text, contact=ROUTE_INFO.get(res.route))

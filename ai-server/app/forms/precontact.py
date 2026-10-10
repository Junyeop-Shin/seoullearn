"""사전 연락 질문지와 문자·전화 초안 (forms/pre_contact.json).

모두 규칙으로 만든다 (LLM을 부르지 않는다). 멘티·멘토 이름 자리는 [멘티명], [멘토명]으로 둔다.
"""
from __future__ import annotations

import re

from .. import guard, prompts
from .engine import load_form

SMS_UNIT = 90  # 문자 한 통 길이 확인용 단위


def split_message(text: str, size: int = SMS_UNIT) -> list[str]:
    """size자 이하 조각으로 나눈다. 되도록 줄·문장 끝에서 자른다."""
    parts: list[str] = []
    for line in [x.strip() for x in text.split("\n") if x.strip()]:
        chunks = re.split(r"(?<=[.?!])\s+", line)
        cur = ""
        for c in chunks:
            while len(c) > size:  # 한 문장이 size보다 길면 그냥 자른다
                if cur:
                    parts.append(cur)
                    cur = ""
                parts.append(c[:size])
                c = c[size:]
            if len(cur) + len(c) + (1 if cur else 0) <= size:
                cur = f"{cur} {c}".strip()
            else:
                parts.append(cur)
                cur = c
        if cur:
            parts.append(cur)
    return parts


def build(mode: str = "온라인", call_time: str | None = None, answers: dict | None = None, subject: str = "") -> dict:
    """mode: 온라인 | 오프라인. call_time: 전화할 시각(예: '19시'). answers: 이미 받은 답변(질문 key별). subject: 신청 과목."""
    form = load_form("pre_contact")
    offline = mode == "오프라인"
    questions = []
    for q in form["questions"]:
        if q.get("when") == "offline" and not offline:
            continue
        ask = q["ask"]
        m = re.match(r"\(온라인\)\s*(.+?)\s*/\s*\(오프라인\)\s*(.+)", ask)
        if m:
            ask = m.group(2) if offline else m.group(1)
        ask = re.sub(r"^\(오프라인\)\s*", "", ask)
        questions.append({"key": q["key"], "ask": ask, "pii": bool(q.get("pii")), "note": q.get("note") or q.get("rules")})

    when = f"오늘 {call_time} 이후에" if call_time else "곧"
    extra = ("오프라인 멘토링 장소는 희망 지역을 확인한 뒤 자치구 이음단의 장소 예약이 끝나야 확정됩니다."
             if offline else "온라인 멘토링은 서로온 앱으로 진행하니 미리 설치해 주시면 좋겠습니다.")
    # 문구는 templates/pre_contact.md에 있다. 줄글 한 덩어리로 쓰고, 회기 길이(4개월·16회)는 그룹마다 달라 적지 않는다.
    # 문자는 서울런 플랫폼에서 나가 멘토 번호가 찍히지 않으므로 회신받을 번호 자리([멘토 연락처])를 문자 안에 둔다.
    # [멘토명]·[멘티명]·[멘토 연락처]는 서버가 채우지 않는다 (이름과 연락처는 멘토 브라우저에만 있다)
    subject = guard.check(subject.strip()).text
    sms = " ".join(prompts.render("pre_contact", subject_phrase=f"{subject} " if subject else "", when=when, mode_note=extra).split())
    call = ("안녕하세요? [멘티명]님 되시나요? 저는 이번 서울런 멘토로 활동하게 된 [멘토명]이며, [멘티명] 학생의 멘토로 선정되어 "
            "연락드리게 되었습니다. 앞으로 진행될 멘토링 관련해서 몇 가지 사항을 여쭤봐도 괜찮을까요?")
    notes = [form["no_response_rule"], "멘토링 시간은 09:00~22:00 안에서 정합니다."]
    if offline:
        notes.insert(0, "오프라인은 이음단 장소 예약 후 일정이 확정됩니다. 장소가 확정되기 전에는 종합계획서①을 입력하지 않습니다.")
    out = {"mode": "오프라인" if offline else "온라인", "questions": questions,
           "sms": {"text": sms, "length": len(sms), "parts": split_message(sms)}, "call_script": call, "notes": notes}
    if answers is not None:
        out["unanswered"] = [q["key"] for q in questions if not q["pii"] and not str(answers.get(q["key"], "")).strip()]
    return out

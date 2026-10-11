"""사전 연락 문자 문구 (templates/pre_contact.md, forms/pre_contact.json).

규칙으로 만든다 (LLM을 부르지 않는다). 멘티·멘토 이름 자리는 [멘티명], [멘토명]으로 둔다.
"""
from __future__ import annotations

import re

from .. import guard, prompts
from .engine import load_form


def build(mode: str = "온라인", subject: str = "") -> dict:
    """mode: 온라인 | 오프라인. subject: 신청 과목. {mode, sms: {text}, notes}"""
    offline = mode == "오프라인"
    extra = ("오프라인 멘토링 장소는 희망 지역을 확인한 뒤 자치구 이음단의 장소 예약이 끝나야 확정됩니다."
             if offline else "온라인 멘토링은 서로온 앱으로 진행하니 미리 설치해 주시면 좋겠습니다.")
    # 문구는 templates/pre_contact.md에 있다. 템플릿의 줄 바꿈을 그대로 쓰고(읽기 편하게 문단을 나눈다), 회기 길이(4개월·16회)는 그룹마다 달라 적지 않는다.
    # 문자는 서울런 플랫폼에서 나가 멘토 번호가 찍히지 않으므로 회신받을 번호 자리([멘토 연락처])를 문자 안에 둔다.
    # [멘토명]·[멘티명]·[멘토 연락처]는 서버가 채우지 않는다 (이름과 연락처는 멘토 브라우저에만 있다)
    subject = guard.check(subject.strip()).text
    # render는 자리가 모두 빈 줄을 뺀다: 과목이 없어도 첫 줄(인사)이 빠지지 않게 표시를 넣었다가 지운다
    raw = prompts.render("pre_contact", subject_phrase=f"{subject} " if subject else "\x00", when="곧", mode_note=extra).replace("\x00", "")
    sms = re.sub(r"\n{3,}", "\n\n", "\n".join(" ".join(line.split()) for line in raw.strip().split("\n")))   # 안내가 없는 방식은 빈 줄이 겹친다
    notes = [load_form("pre_contact")["no_response_rule"], "멘토링 시간은 09:00~22:00 안에서 정합니다."]
    if offline:
        notes.insert(0, "오프라인은 이음단 장소 예약 후 일정이 확정됩니다. 장소가 확정되기 전에는 종합계획서①을 입력하지 않습니다.")
    return {"mode": "오프라인" if offline else "온라인", "sms": {"text": sms}, "notes": notes}

"""이음단에 보낼 장소·일정 요청 메시지 (오프라인 멘토링). 규칙으로만 만든다 (LLM 없음).

날짜 계산은 여기서 한다: 일정·장소 변경은 예약된 일정 최소 3일 전, 담당자 근무시간 안에 요청해야 한다 (활동가이드 p.23).
멘티 이름은 넣지 않는다.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from .. import guard, prompts

WEEKDAYS = "월화수목금토일"
KINDS = ("장소 요청", "일정 변경", "장소 변경")
MIN_DAYS = 3


def _d(d: date) -> str:
    return f"{d.month}월 {d.day}일({WEEKDAYS[d.weekday()]})"


def build(kind: str, region: str = "", schedule: str = "", current: datetime | None = None, desired: datetime | None = None,
          reason: str = "", now: datetime | None = None) -> dict:
    """kind: 장소 요청(새 그룹) | 일정 변경 | 장소 변경.
    region: 희망 지역. schedule: 희망 요일·시간(장소 요청). current: 지금 예약된 일시. desired: 바꾸고 싶은 일시."""
    if kind not in KINDS:
        raise ValueError(f"요청 종류는 {', '.join(KINDS)} 중 하나여야 합니다.")
    now = now or datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)  # 컨테이너 시계는 UTC다
    warnings: list[str] = []
    pii: set[str] = set()

    def clean(text: str) -> str:
        g = guard.check(text.strip())
        pii.update(g.pii)
        return g.text

    region, schedule, reason = clean(region), clean(schedule), clean(reason)
    lines = ["안녕하세요, 서울런 멘토입니다."]
    if kind == "장소 요청":
        if not region:
            warnings.append("희망 지역을 적어 주세요.")
        if not schedule:
            warnings.append("희망 요일과 시간을 적어 주세요.")
        # 문구는 templates/venue_request.md에 있다
        lines = prompts.render("venue_request", region=region or "(작성 필요)", schedule=schedule or "(작성 필요)").split("\n")
    else:
        if current is None:
            warnings.append("지금 예약된 멘토링 일시를 넣어 주세요.")
        else:
            days = (current.date() - now.date()).days
            if days < 0:
                warnings.append("예약된 일시가 이미 지났습니다. 날짜를 확인해 주세요.")
            elif days < MIN_DAYS:
                warnings.append(f"예약된 일정({_d(current.date())})까지 {days}일 남았습니다. 변경은 최소 {MIN_DAYS}일 전에 요청해야 해서 "
                                "반영되지 않을 수 있습니다. 이음단과 먼저 통화로 상의해 주세요.")
        if kind == "일정 변경":
            if desired is None:
                warnings.append("바꾸고 싶은 일시를 넣어 주세요.")
            elif not (9 * 60 <= desired.hour * 60 + desired.minute <= 21 * 60):
                warnings.append("멘토링은 09:00~22:00 안에서 진행해야 합니다. 바꾸려는 시각을 확인해 주세요.")
            lines.append("오프라인 멘토링 일정 변경을 요청드립니다.")
            lines.append(f"기존: {_d(current.date()) + f' {current:%H:%M}' if current else '(작성 필요)'}")
            lines.append(f"변경 희망: {_d(desired.date()) + f' {desired:%H:%M}' if desired else '(작성 필요)'}")
        else:
            if not region:
                warnings.append("옮기고 싶은 지역을 적어 주세요.")
            lines.append("오프라인 멘토링 장소 변경을 요청드립니다.")
            lines.append(f"적용 희망 회차: {_d(current.date()) + f' {current:%H:%M}' if current else '(작성 필요)'}부터")
            lines.append(f"희망 지역: {region or '(작성 필요)'}")
        if reason:
            lines.append(f"사유: {reason}")
        lines.append("가능 여부 확인 부탁드립니다. 플랫폼에서도 변경 요청을 올리겠습니다.")
        if now.weekday() >= 5:
            warnings.append("오늘은 주말입니다. 담당자 근무시간 안에 닿아야 하므로 평일에 확인될 수 있습니다.")
    reminders = ["장소와 일정은 이음단의 승인이 있어야 확정됩니다. 승인 없이 진행한 활동은 인정되지 않습니다."]
    if kind != "장소 요청":
        reminders.append(f"변경은 예약된 일정 최소 {MIN_DAYS}일 전, 담당자 근무시간 안에 요청합니다. 장소 사정으로 반영되지 않을 수 있습니다.")
    message = "\n".join(lines)
    return {"kind": kind, "message": message, "length": len(message), "warnings": warnings, "reminders": reminders, "pii_masked": sorted(pii)}

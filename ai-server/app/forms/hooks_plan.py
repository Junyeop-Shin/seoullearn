"""종합계획서①(플랫폼 입력)과 종합계획서②(서식 파일) 특수 처리."""
from __future__ import annotations

from datetime import timedelta

from . import checks
from .engine import Context, DraftResult, Hooks, load_form, register

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
LATER = "1회차에 자세한 상담 예정"
DEFAULT_RULES = ["멘토링 시간 준수하기", "일정 변경은 미리 논의하기", "인강은 계획대로 수강하고 과제 해 오기"]
LENGTH_WARN = 300  # 플랫폼 칸별 글자 수 제한은 미확인. 확인 전까지 이 길이를 넘으면 경고만 한다


def structure_blocks(minutes: int) -> list[tuple[int, str]]:
    """멘토링 구성 (분, 내용). 숫자 배분은 규칙으로 정한다."""
    unit = minutes // 6
    return [(unit, "온라인 강의 수강 확인 및 질의응답"), (unit * 3, "개념 학습과 문제 풀이"),
            (unit, "오답 정리"), (minutes - unit * 5, "상담 및 다음 회차 안내")]


def allowed_handover(handover) -> dict:
    """인계 요약은 허용 목록의 항목만 받는다 (출석 패턴, 과제 수행, 학습 태도, 수강 강의·진도)."""
    if not isinstance(handover, dict):
        return {}
    allow = {a["key"]: a["label"] for a in load_form("handover_summary")["allow"]}
    return {allow[k]: v for k, v in handover.items() if k in allow and v}


def _curriculum(ctx: Context, fmt: str) -> list[str] | None:
    sessions = ctx.extra.get("weekly_plan")
    if not sessions:
        return None
    out = []
    for s in sessions:
        if fmt == "file":
            out.append(f"(온라인강의) {s['no']}회차: {s['online']} / (멘토링내용) {s['mentoring']} / (학습상담) {s['counsel']}")
        else:
            out.append(f"{s['no']}회차 (온라인 강의) {s['online']} / (멘토링 내용) {s['mentoring']} / (상담) {s['counsel']}")
    return out


class _PlanBase(Hooks):
    def _common_prepare(self, ctx: Context) -> None:
        dropped = ctx.extra.get("handover")
        ctx.extra["handover"] = allowed_handover(dropped)
        if isinstance(dropped, dict) and len(ctx.extra["handover"]) < len([v for v in dropped.values() if v]):
            ctx.warn("인계 요약에서 허용되지 않은 항목(학업 수준, 정서·상담 내용 등)은 쓰지 않았습니다.")
        if not ctx.extra["handover"]:
            ctx.extra.pop("handover")
        ctx.extra["_weekly_plan_given"] = bool(ctx.extra.get("weekly_plan"))


@register("plan_initial")
class PlanInitialHooks(_PlanBase):

    def prepare(self, ctx: Context) -> None:
        self._common_prepare(ctx)
        i = ctx.inputs
        dt = checks.parse_datetime(str(i.get("start_datetime", "")))
        minutes = int(i["duration"]) if str(i.get("duration", "")).isdigit() else None
        if dt and minutes:
            start = dt.hour * 60 + dt.minute
            if start < 9 * 60 or start + minutes > 22 * 60:
                ctx.warn("멘토링은 09:00~22:00 안에서 진행해야 합니다. 시작 시각과 멘토링 시간을 확인해 주세요.")
        if dt and i.get("weekday") in WEEKDAYS and WEEKDAYS[dt.weekday()] != i["weekday"]:
            ctx.warn(f"시작일({dt.date().isoformat()})은 {WEEKDAYS[dt.weekday()]}요일인데 학습 요일은 {i['weekday']}요일로 입력됐습니다.")
        if minutes == 120:
            ctx.remind("120분 멘토링은 시간확대 승인을 받은 그룹만 가능합니다.")
        ctx.extra["_minutes"] = minutes or 60
        # LLM이 볼 참고 입력에서 내부용 값은 뺀다
        ctx.extra["_plan_sessions"] = ctx.extra.pop("weekly_plan", None)

    def fixed(self, f: dict, ctx: Context):
        if f["key"] == "structure":
            return " / ".join(f"{m}분 {what}" for m, what in structure_blocks(ctx.extra["_minutes"]))
        if f["key"] == "rules":
            return ", ".join(DEFAULT_RULES)
        if f["key"] == "curriculum":
            ctx.extra["weekly_plan"] = ctx.extra.get("_plan_sessions")
            lines = _curriculum(ctx, "platform")
            ctx.extra.pop("weekly_plan", None)
            return lines if lines else ["1회차 (온라인 강의) 수강 진도 확인 / (멘토링 내용) 학습 수준 확인과 계획 협의 / (상담) 학습 목표 상담"]
        return None

    def finish(self, ctx: Context, result: DraftResult) -> None:
        d = result.draft
        if not ctx.extra.get("_plan_sessions"):
            ctx.warn("주차별 계획이 없어 회차별 커리큘럼을 1회차만 채웠습니다. 강의 목차로 주차별 계획을 먼저 만들어 주세요.")
        if isinstance(d.get("diagnosis"), str) and LATER not in d["diagnosis"]:
            d["diagnosis"] = (d["diagnosis"].rstrip(". ") + ". " if d["diagnosis"].strip() else "") + LATER
        ctx.warn("활동규칙은 기본 예시입니다. 멘티와 협의한 규칙으로 고쳐 주세요.")
        removed_all: set[str] = set()
        for key, value in list(d.items()):
            items = value if isinstance(value, list) else [value]
            cleaned = []
            for item in items:
                text, removed = checks.plain_text(str(item)) if not str(item).startswith("[") else (str(item), [])
                removed_all.update(removed)
                cleaned.append(text)
                limit = next((f.get("max_length") for f in ctx.form["fields"] if f["key"] == key), None) or LENGTH_WARN
                if len(text) > limit:
                    ctx.warn(f"'{key}' 칸이 {len(text)}자입니다. 내용이 많으면 등록 오류가 날 수 있으니 {limit}자 안팎으로 줄여 주세요.")
            d[key] = cleaned if isinstance(value, list) else cleaned[0]
        if removed_all:
            ctx.warn(f"플랫폼 등록 오류를 막으려고 특수문자({' '.join(sorted(removed_all))})를 바꾸거나 뺐습니다.")
        ctx.remind("종합계획서①은 등록 후 수정할 수 없습니다. 1회차 일정만 변경할 수 있고, 여러 회차를 바꿔야 하면 이음단에 문의해 주세요.")
        if ctx.extra.get("mode") == "오프라인":
            ctx.remind("오프라인은 이음단의 장소 예약이 끝난 뒤에 종합계획서①을 입력합니다.")
        ctx.remind("종합계획서①은 매칭 후 7일 이내에 플랫폼에 직접 입력합니다.")
        for k in [k for k in ctx.extra if k.startswith("_")]:
            ctx.extra.pop(k)


@register("plan_file")
class PlanFileHooks(_PlanBase):

    def prepare(self, ctx: Context) -> None:
        self._common_prepare(ctx)
        ctx.extra["_plan_sessions"] = ctx.extra.pop("weekly_plan", None)
        ctx.extra["_start"] = ctx.extra.pop("start_datetime", None)
        ctx.extra["_minutes"] = int(ctx.extra.pop("duration", 60) or 60)

    def derive(self, f: dict, ctx: Context):
        if f["key"] == "period":
            dt = checks.parse_datetime(str(ctx.extra.get("_start") or "")) or None
            d = dt.date() if dt else checks.parse_date(str(ctx.extra.get("_start") or ""))
            if not d:
                return None
            return f"{checks.fmt(d)}~{checks.fmt(d + timedelta(days=7 * 15))}"  # 1회차 ~ 16회차 예정일
        return None

    def fixed(self, f: dict, ctx: Context):
        if f["key"] == "curriculum":
            ctx.extra["weekly_plan"] = ctx.extra.get("_plan_sessions")
            lines = _curriculum(ctx, "file")
            ctx.extra.pop("weekly_plan", None)
            return lines if lines else []
        if f["key"] == "structure":
            dt = checks.parse_datetime(str(ctx.extra.get("_start") or ""))
            blocks = structure_blocks(ctx.extra["_minutes"])
            if not dt:
                return [f"{m}분 {what}" for m, what in blocks]
            out, t = [], dt.hour * 60 + dt.minute
            for m, what in blocks:
                out.append(f"{t // 60:02d}:{t % 60:02d}~{(t + m) // 60:02d}:{(t + m) % 60:02d} {what}")
                t += m
            return out
        return None

    def finish(self, ctx: Context, result: DraftResult) -> None:
        d = result.draft
        if not d.get("curriculum"):
            ctx.warn("주차별 계획이 없어 커리큘럼을 비웠습니다. 회차별 온라인 강의 수강 계획은 반드시 들어가야 합니다.")
            result.missing_questions.append({"key": "curriculum", "label": "커리큘럼", "question": "강의 목차로 주차별 계획을 먼저 만들어 주세요."})
        lines = []
        for f in ctx.form["fields"]:
            v = d.get(f["key"])
            lines.append(f"■ {f['label']}")
            lines += [f"  - {x}" for x in v] if isinstance(v, list) else [f"  {v if v else '(작성 필요)'}"]
        result.text = "\n".join(lines)
        ctx.remind("종합계획서②는 공지사항의 서식 파일에 옮겨 적어 1회차 활동보고서의 첨부파일로 올립니다. 첨부하지 않으면 1회차 활동비가 지급되지 않습니다.")
        for k in [k for k in ctx.extra if k.startswith("_")]:
            ctx.extra.pop(k)

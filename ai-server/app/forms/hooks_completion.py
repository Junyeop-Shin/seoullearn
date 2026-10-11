"""완료보고서 특수 처리: 활동보고서 16건 → 수행 리스트(규칙), 멘토링 내용·성취도(LLM 초안).

감성케어 상담 칸은 활동보고서에서 가져오지 않는다. 멘토가 직접 쓴 내용만 다듬는다.
"""
from __future__ import annotations

import re
from collections import Counter

from . import checks, sensitive
from .engine import Context, DraftResult, Hooks, register

WEEKDAYS = "월화수목금토일"
# LLM에 넘기는 회차별 사실. 학습이해도 척도와 개인정보 칸은 넘기지 않는다
_FACT_KEYS = {"attendance": "출결", "lecture_progress": "인강 수강", "homework": "과제", "progress_note": "학습 진도", "progress_scale": "학습진도(성실성)",
              "scope": "학습 범위", "session_content": "멘토링 내용", "etc": "기타", "requests": "건의사항"}
ABSENT = ("무단결석", "인정결석", "임박취소")


def session_line(r: dict) -> str | None:
    """'N회차 : YY. MM. DD. 요일 HH시MM분~HH시MM분(60분간)'. 날짜를 못 읽으면 None."""
    d = checks.parse_date(str(r.get("session_date", "")))
    if not d:
        return None
    head = f"{r['session_no']}회차 : {d.year % 100:02d}. {d.month:02d}. {d.day:02d}. {WEEKDAYS[d.weekday()]}"
    status = r.get("status") or ""
    if status in ABSENT:
        return f"{head} ({status})"
    t = checks.parse_time_range(str(r.get("actual_time", "")))
    if not t or t[1] <= t[0]:
        return f"{head} (진행시간 확인 필요)"
    s, e = t
    return f"{head} {s // 60:02d}시{s % 60:02d}분~{e // 60:02d}시{e % 60:02d}분({e - s}분간)"


def stats(reports: list[dict]) -> dict:
    """출결·성실성 통계. 숫자는 여기서 세고 LLM은 문장만 쓴다."""
    status = Counter((r.get("status") or "출석") for r in reports)
    scale = Counter(r["progress_scale"] for r in reports if r.get("progress_scale"))
    # '미수행', '수행 못 함', '수행 안 함'도 하지 않은 것으로 센다 (멘토가 고쳐 쓴 줄, 플랫폼에서 붙여 넣은 보고서)
    done = Counter("수행하지 않음" if re.search(r"미수행|수행\s*(?:하지\s*)?(?:않|못|안)", str(r.get("homework"))) else "수행함"
                   for r in reports if "수행" in str(r.get("homework") or ""))
    # 완강 여부를 가늠할 마지막 수강 기록. 그대로 LLM에 가는 값이라 정서·가정·건강 문장을 뺀다
    last = next((v for v in (sensitive.drop_lines(str(r.get("lecture_progress") or ""))[0].strip() for r in reversed(reports)) if v), "")
    return {"전체 회차 수": len(reports), "출결": dict(status), "과제": dict(done), "마지막 인강 기록": last, "학습진도(성실성) 평가 분포": dict(scale)}


@register("completion_report")
class CompletionReportHooks(Hooks):

    def prepare(self, ctx: Context) -> None:
        ctx.extra["_total"] = total = 8 if str(ctx.extra.pop("duration", "")) == "120" else 16   # 시간확대(120분)는 한 회기가 8회차다
        reports = sorted((r for r in ctx.extra.pop("reports", []) or [] if isinstance(r, dict) and str(r.get("session_no", "")).strip()),
                         key=lambda r: int(re.sub(r"\D", "", str(r["session_no"])) or 0))
        for r in reports:
            r["session_no"] = int(re.sub(r"\D", "", str(r["session_no"])) or 0)
        ctx.extra["_reports"] = reports
        filtered = False
        facts = []
        for r in reports:
            row = {"회차": r["session_no"], "상태": r.get("status") or "출석"}
            whole = str(r.get("progress_note") or "").strip()   # 학습 진도 칸 전체. 있으면 거기서 뽑은 세 줄은 다시 넘기지 않는다
            for key, label in _FACT_KEYS.items():
                v = str(r.get(key) or "").strip()
                if not v:
                    continue
                v, kinds = sensitive.drop_lines(v)   # 정서·가정·건강 내용은 완료보고서 초안의 재료로 쓰지 않는다 (바꿔 쓰지 않고 뺀다)
                filtered = filtered or bool(kinds)
                if v and not (whole and key in ("attendance", "lecture_progress", "homework")):
                    row[label] = v
            facts.append(row)
        if filtered:
            ctx.warn("활동보고서의 정서·가정·건강 관련 내용은 초안에 쓰지 않았습니다. 감성케어 상담 칸은 직접 작성해 주세요.")
        if reports:
            ctx.extra["회차별 기록"] = facts
            ctx.extra["통계"] = stats(reports)
        # 친화·성장활동 기록(멘토가 적어 둔 것)도 참고 자료다. 정서·가정·건강 내용은 같은 규칙으로 뺀다
        acts = []
        for a in ctx.extra.pop("activities", None) or []:
            row = {k: sensitive.drop_lines(str(v))[0] for k, v in a.items() if str(v).strip()} if isinstance(a, dict) else {}
            if any(row.values()):
                acts.append({k: v for k, v in row.items() if v})
        if acts:
            ctx.extra["친화·성장활동"] = acts
        goals = ctx.extra.pop("plan_goal", None)
        ctx.extra["_goals"] = [str(g).strip() for g in goals if str(g).strip()] if isinstance(goals, list) else []
        if ctx.extra["_goals"]:
            ctx.extra["학습목표"] = ctx.extra["_goals"]
        if not reports:
            ctx.warn("활동보고서가 없습니다. 회차별 활동보고서를 먼저 저장하거나 플랫폼의 보고서를 붙여 넣어 주세요.")
        elif len(reports) < total:
            ctx.warn(f"활동보고서가 {len(reports)}건입니다. 완료보고서는 {total}회차를 마친 뒤 작성합니다.")

    def derive(self, f: dict, ctx: Context):
        reports = ctx.extra["_reports"]
        if f["key"] == "subject":
            subjects = Counter(str(r.get("subject") or "").strip() for r in reports if r.get("subject"))
            return subjects.most_common(1)[0][0] if subjects else None
        if f["key"] == "session_list":
            lines = [session_line(r) for r in reports]
            if any(x is None for x in lines):
                ctx.warn("멘토링 일자를 읽지 못한 회차가 있어 수행 리스트에서 뺐습니다.")
            return [x for x in lines if x]
        if f["key"] == "learning_goal":
            return ctx.extra["_goals"] or None
        return None

    def fixed(self, f: dict, ctx: Context):
        if f["key"] in ("content", "achievement", "requests") and not ctx.extra["_reports"]:
            return []   # 기록이 없으면 LLM에 쓰게 하지 않는다
        return None

    def finish(self, ctx: Context, result: DraftResult) -> None:
        for q in result.missing_questions:
            if q["key"] == "learning_goal":
                q["question"] = "종합계획서에 적은 학습목표를 알려 주세요. (종합계획서②를 저장해 두면 자동으로 불러옵니다.)"
        if not str(result.draft.get("emotional_care") or "").strip():
            ctx.remind("감성케어 상담 칸은 비워 두었습니다. 적을 내용이 있으면 직접 작성해 주세요 (권장 기재 항목).")
        ctx.remind(f"완료보고서는 {ctx.extra['_total']}회차 활동보고서가 승인된 직후 작성합니다. 작성하지 않으면 마지막 회차 활동비가 지급되지 않고 연장 회기도 시작되지 않습니다.")
        for k in [k for k in ctx.extra if k.startswith("_")]:
            ctx.extra.pop(k)

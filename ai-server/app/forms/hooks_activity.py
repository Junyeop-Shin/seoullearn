"""활동보고서 특수 처리: 메모 → 학습 내용, 결석 회차, 정서·건강 내용 거르기, 제출 안내."""
from __future__ import annotations

import re

from . import checks, sensitive
from .engine import Context, DraftResult, Hooks, register

ABSENT = ("무단결석", "인정결석", "임박취소")   # 멘토링을 진행하지 못한 회차
_TEXT_KEYS = ("scope", "goal", "attendance", "lecture_progress", "homework", "session_content", "etc", "requests")
# 결석 회차에는 채우지 않는 칸
_LEARNING_KEYS = ("scope", "goal", "lecture_progress", "homework", "progress_scale", "understanding_scale", "session_content")


@register("activity_report")
class ActivityReportHooks(Hooks):

    def prepare(self, ctx: Context) -> None:
        i = ctx.inputs
        ctx.extra["status"] = status = (i.pop("status", None) or ctx.extra.get("status") or "출석").strip()
        keep_lines = bool(ctx.extra.pop("keep_lines", False))   # 화면의 칸을 줄마다 실어 보낸 글: 줄 구성과 글자를 그대로 지킨다
        ctx.extra["_long"] = long = str(ctx.extra.pop("duration", "")) == "120"   # 시간확대: 출석 인정 기준이 120분이고 한 회기가 8회차다 (활동가이드 p.36)
        notes = i.pop("notes", None)
        if notes and not i.get("session_content"):
            i["session_content"] = notes  # 자유 메모가 '멘토링 학습 내용'의 재료다
        ctx.extra["health"] = False
        for key in _TEXT_KEYS:
            if isinstance(i.get(key), str) and i[key].strip():
                # 항목별로 줄을 나눠 적은 글(화면의 잘한 점·부족한 점·개선 방향 칸)은 줄 구성을 지키며 거른다
                i[key], kinds = sensitive.drop_lines(i[key]) if keep_lines or "\n" in i[key] else sensitive.filter_text(i[key])
                if "정서" in kinds:
                    ctx.warn("정서·가정 관련 내용은 활동보고서에 넣지 않았습니다. 필요하면 완료보고서의 감성케어 칸에 직접 작성해 주세요.")
                if "건강" in kinds:
                    ctx.extra["health"] = True
                    ctx.warn("질병명 같은 건강 정보가 든 문장은 활동보고서에서 뺐습니다. 결석 사유라면 '질병으로 인한 결석'이라고만 적어 주세요."
                             if keep_lines or "\n" in i[key] else "질병명 같은 건강 정보는 '질병으로 인한 결석' 수준으로만 적었습니다.")
        if status in ABSENT:
            for key in _LEARNING_KEYS:
                if key != "session_content":
                    i.pop(key, None)  # 진행하지 않은 회차의 학습 내용은 만들지 않는다
        # 실제 접속 시간 검사
        f = next(x for x in ctx.form["fields"] if x["key"] == "actual_time")
        if i.get("actual_time"):
            rules = {**(f.get("rules") or {}), **({"min_minutes": 120} if long else {})}
            for msg in checks.check_time_range(i["actual_time"], rules, need_min=status not in ABSENT):
                ctx.warn(msg)

    def required(self, f: dict, ctx: Context) -> bool:
        if ctx.extra.get("status") in ABSENT and f["key"] in _LEARNING_KEYS:
            return False
        if ctx.extra.get("status") in ("인정결석", "임박취소") and f["key"] == "actual_time":
            return False  # 시작 전에 확인된 결석·취소라 접속 기록이 없을 수 있다
        return bool(f.get("required"))

    def fixed(self, f: dict, ctx: Context):
        status = ctx.extra.get("status")
        if status not in ABSENT:
            return None
        if f["key"] == "session_content":
            if status == "무단결석":
                return "멘티 무단결석으로 멘토링을 진행하지 못함."
            if status == "임박취소":
                return "멘티의 임박취소로 멘토링을 진행하지 못함."
            reason = "질병으로 인한 결석" if ctx.extra.get("health") else "불가항력 사유로 인한 결석"
            return f"멘티의 {reason}(인정결석)으로 멘토링을 진행하지 못함."
        if f["key"] in _LEARNING_KEYS:
            return ""
        return None

    def finish(self, ctx: Context, result: DraftResult) -> None:
        i, status = ctx.inputs, ctx.extra.get("status")
        if status not in ABSENT:
            ctx.remind("진행시간은 예정 시간이 아니라 플랫폼 접속 기록과 일치하는 실제 시작~종료 시간으로 적어 주세요.")
        d = checks.parse_date(str(i.get("session_date", "")))
        if d:
            ctx.remind(f"활동보고서는 멘토링 날짜로부터 7일 이내({checks.fmt(checks.add_days(d, 7))}까지) 제출해야 합니다.")
        if status == "지각":
            ctx.remind("지각 회차는 증빙 사진이 3장 필요합니다: 시작, 멘티 입장 후 중간, 종료.")
        elif status == "무단결석":
            ctx.remind("무단결석 증빙: ① 사전 출석 확인 연락내역(멘티 답장) ② 예정 시각 멘토 접속·도착 증빙 ③ 30분 대기 증빙 ④ 결석 관련 연락내역.")
            ctx.remind("무단결석 회차는 증빙이 확인되면 기본수당만 지급됩니다 (준비활동·장기활동 가산금 제외).")
            ctx.remind("무단결석은 회기 내 2회 승인되면 해당 그룹이 즉시 종료됩니다.")
        elif status == "임박취소":
            ctx.remind("임박취소 증빙: ① 사전 일정약속 연락내역(멘티 답장) ② 멘티의 임박취소 연락내역. 연락 증빙은 날짜가 보여야 합니다.")
            ctx.remind("임박취소 회차는 사유와 증빙을 보고서와 첨부파일로 내고 승인받으면 준비수당만 지급됩니다 (온라인 멘토링에만 해당).")
        elif status == "인정결석":
            ctx.remind("인정결석은 질병·사고 등 불가항력 사유를 객관적 증빙으로 확인받아야 합니다.")
            ctx.remind("인정결석 회차는 회기 종료일까지 멘티와 일정을 조율해 진행합니다.")
        try:
            no = int(str(i.get("session_no", "")).strip())
        except ValueError:
            no = None
        if no == 1:
            ctx.remind("1회차 활동보고서에는 종합계획서② 파일을 함께 첨부해야 합니다. 첨부하지 않으면 해당 회차 활동비가 지급되지 않습니다.")
        if no is not None and no >= (7 if ctx.extra.get("_long") else 14):
            ctx.remind("회기의 마지막 두 회차 무렵에는 멘티와 다음 회기 연장 여부를 상의해 주세요.")
        text = " ".join(str(i.get(k, "")) for k in _TEXT_KEYS)
        if re.search(r"(어머님|아버님|어머니|아버지|보호자|학부모).{0,20}(상담|통화|요청|원하)", text):
            ctx.remind("보호자의 상담 요청은 활동가이드 p.25 보호자 상담 가이드라인을 확인하고, 혼자 응대하기 어려우면 운영사무국에 공유해 주세요.")
        if re.search(r"장소.{0,10}(변경|바꾸|옮기)", text):
            ctx.remind("장소 변경은 이음단 승인이 필요합니다. 예약 일정 최소 3일 전, 이음단 근무 시간 안에 요청해 주세요.")

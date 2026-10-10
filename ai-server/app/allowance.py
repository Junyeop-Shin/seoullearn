"""활동비 계산기. 활동가이드 4-1·4-2(p.41~47)의 기준을 규칙 함수로 옮긴 것이다. RAG와 LLM을 쓰지 않는다.

금액은 추정값이다. 실제 지급액은 승인 결과와 운영사무국 정산에 따른다.
"""
from __future__ import annotations

import math
import re

ONLINE_BASE = 12_790        # 온라인 기본수당(시간당). 국가근로장학금 기준
OFFLINE_BASE = 30_000       # 오프라인 기본수당(시간당)
PREP_RATE = 0.30            # 준비활동 가산금 (온라인만)
EXTRA_RATE = 0.20           # 고학년지도 또는 취약계층지원 가산금 (택1, 중복 불가)
LONG_TERM_RATES = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]   # 장기활동 가산금: 1~6구간 (온라인만)
MAX_STAGE = len(LONG_TERM_RATES)
MONTHLY_MIN = 4             # 구간 적용 횟수로 인정되는 월 유효 진행 횟수
MONTHS_PER_STAGE = 2        # 기준을 채운 달이 2번 모이면 다음 달부터 1구간 상승
SOURCES = ["활동가이드 p.41-42 활동비 구성 체계", "활동가이드 p.44 장기활동 가산금", "활동가이드 p.47 활동수당 지급 기준"]
DISCLAIMER = "활동가이드 기준으로 계산한 추정 금액입니다. 실제 지급액은 활동보고서 승인 결과와 운영사무국 정산에 따릅니다."


def up10(amount: float) -> int:
    """원 단위 올림 (활동가이드 p.47: 12,790원의 10% = 1,280원)."""
    return int(math.ceil(round(amount, 6) / 10) * 10)


def hourly(mode: str, stage: int = 1, senior: bool = False, vulnerable: bool = False) -> dict:
    """시간당 활동비와 내역. mode: 온라인 | 오프라인. stage: 장기활동 가산금 구간(1~6, 온라인만).
    senior: 고학년지도 가산금. vulnerable: 취약계층지원 가산금 (둘은 중복되지 않는다)."""
    if mode not in ("온라인", "오프라인"):
        raise ValueError("멘토링 유형은 온라인 또는 오프라인이어야 합니다.")
    if not 1 <= stage <= MAX_STAGE:
        raise ValueError(f"가산금 구간은 1~{MAX_STAGE}이어야 합니다.")
    base = ONLINE_BASE if mode == "온라인" else OFFLINE_BASE
    items = [{"name": "기본수당", "amount": base}]
    notes: list[str] = []
    if mode == "온라인":
        items.append({"name": "준비활동 가산금 (30%)", "amount": up10(base * PREP_RATE)})
        if stage > 1:
            rate = LONG_TERM_RATES[stage - 1]
            items.append({"name": f"장기활동 가산금 ({stage}구간, {int(rate * 100)}%)", "amount": up10(base * rate)})
    elif stage > 1:
        notes.append("준비활동·장기활동 가산금은 온라인 멘토링에만 있습니다.")
    if senior or vulnerable:
        name = "고학년지도 가산금 (20%)" if senior else "취약계층지원 가산금 (20%, 회기 종료 후 정산)"
        items.append({"name": name, "amount": up10(base * EXTRA_RATE)})
        if senior and vulnerable:
            notes.append("고학년지도 가산금과 취약계층지원 가산금은 중복 지급되지 않아 하나만 넣었습니다.")
        if vulnerable and not senior:
            notes.append("취약계층지원 가산금은 회기가 끝난 뒤 수기를 제출해 승인받으면 한꺼번에 지급됩니다.")
    return {"mode": mode, "stage": stage if mode == "온라인" else None, "items": items, "total": sum(i["amount"] for i in items), "notes": notes}


def stages_by_month(valid_counts: list[int], start_stage: int = 1) -> list[dict]:
    """달마다의 유효 진행 횟수 → 달마다의 가산금 구간 (온라인).
    유효 진행 횟수가 4회 이상인 달만 적용 횟수(4)로 인정하고, 그런 달이 2번 모이면 다음 달부터 1구간 오른다. 구간은 내려가지 않는다."""
    out, stage, qualified = [], start_stage, 0
    for n, count in enumerate(valid_counts, 1):
        if count < 0:
            raise ValueError("진행 횟수는 0 이상이어야 합니다.")
        applied = MONTHLY_MIN if count >= MONTHLY_MIN else 0
        rate = hourly("온라인", stage)
        out.append({"month": n, "valid": count, "applied": applied, "stage": stage,
                    "hourly": ONLINE_BASE + up10(ONLINE_BASE * LONG_TERM_RATES[stage - 1]), "hourly_with_prep": rate["total"]})
        if applied:
            qualified += 1
            if qualified % MONTHS_PER_STAGE == 0 and stage < MAX_STAGE:
                stage += 1
    return out


def _stage_note(valid: int) -> str:
    return (f"이 달 온라인 멘토링의 유효 진행 횟수는 {valid}회입니다. {MONTHLY_MIN}회 이상인 달이 {MONTHS_PER_STAGE}번 모이면 다음 달부터 가산금 구간이 1단계 오릅니다."
            if valid >= MONTHLY_MIN else
            f"온라인 멘토링의 유효 진행 횟수가 {valid}회라 {MONTHLY_MIN}회 기준에 못 미칩니다. 이 달은 구간 상승 기준에 들어가지 않습니다.")


def estimate(mode: str, normal: int = 0, no_show: int = 0, late_cancel: int = 0, stage: int = 1, senior: bool = False,
             vulnerable: bool = False, hours: int = 1, stage_note: bool = True) -> dict:
    """한 달(또는 한 기간)의 활동비 추정.
    normal: 정상 진행해 승인된 회차 수. no_show: 멘티 무단결석(증빙 승인 시 기본수당만).
    late_cancel: 임박취소(온라인만, 준비수당만). hours: 회차당 시간(시간확대면 2). 진행하지 못한 회차는 시간확대여도 1시간분으로 본다.
    stage_note: 유효 진행 횟수 안내를 붙일지 (여러 멘티를 합쳐 계산할 때는 합계로 한 번만 붙인다)."""
    if min(normal, no_show, late_cancel) < 0 or hours not in (1, 2):
        raise ValueError("회차 수는 0 이상, 회차당 시간은 1 또는 2여야 합니다.")
    rate = hourly(mode, stage, senior, vulnerable)
    base = rate["items"][0]["amount"]
    prep = up10(base * PREP_RATE) if mode == "온라인" else 0
    extra = up10(base * EXTRA_RATE) if vulnerable and not senior else 0   # 취약계층 가산금은 사후 정산이라 따로 보여 준다
    per_hour_now = rate["total"] - extra
    lines = [{"name": f"정상 진행 {normal}회 × {hours}시간 × {per_hour_now:,}원", "amount": normal * hours * per_hour_now}]
    notes = list(rate["notes"])
    if no_show:
        lines.append({"name": f"멘티 무단결석 {no_show}회 × 1시간 × 기본수당 {base:,}원", "amount": no_show * base})
        notes.append("무단결석 회차는 증빙이 승인돼야 기본수당이 지급됩니다 (준비활동·장기활동 가산금 제외).")
    if late_cancel:
        if mode == "온라인":
            lines.append({"name": f"임박취소 {late_cancel}회 × 1시간 × 준비활동 가산금 {prep:,}원", "amount": late_cancel * prep})
            notes.append("임박취소 회차는 사유와 증빙이 승인돼야 준비수당만 지급됩니다.")
        else:
            notes.append("임박취소 규정은 온라인 멘토링에만 있어 오프라인 계산에는 넣지 않았습니다.")
    if hours == 2 and len(lines) > 1:
        # 활동가이드에 시간확대 회차의 무단결석·임박취소 금액은 없다. p.36 출석 기준의 '멘토 단독 접속은 120분 그룹도 60분만 인정'을 따라 적게 잡는다
        notes.append("시간확대(120분) 그룹의 무단결석·임박취소 회차는 1시간분으로 계산했습니다 (활동가이드 p.36: 멘토 단독 접속은 120분 그룹도 60분만 인정). 정확한 금액은 운영사무국에 확인해 주세요.")
    total = sum(x["amount"] for x in lines)
    out = {"mode": mode, "hourly": rate, "lines": lines, "total": total, "later": None, "notes": notes,
           "valid_count": normal, "counts_for_stage": normal >= MONTHLY_MIN if mode == "온라인" else None,
           "sources": SOURCES, "disclaimer": DISCLAIMER}
    if extra:
        out["later"] = {"name": f"취약계층지원 가산금 {normal}회 × {hours}시간 × {extra:,}원 (회기 종료 후 정산)", "amount": normal * hours * extra}
    if mode == "온라인" and stage_note:
        notes.append(_stage_note(normal))
    return out


def estimate_month(groups: list[dict], stage: int = 1, vulnerable: bool = False) -> dict:
    """여러 멘티의 한 달 활동비 추정. groups: 멘티 한 명이 한 줄 [{mode, hours, normal, no_show, late_cancel, senior}] (이름은 받지 않는다).
    장기활동 가산금 구간(stage)과 취약계층지원 가산금(vulnerable)은 멘토에게 붙는 조건이라 모든 줄에 같이 적용한다.
    유효 진행 횟수는 멘티 구분 없이 온라인 멘토링의 정상 진행 회차를 모두 더해 센다 (활동가이드 p.45 Q&A)."""
    rows = [estimate(g["mode"], int(g.get("normal") or 0), int(g.get("no_show") or 0), int(g.get("late_cancel") or 0), stage,
                     bool(g.get("senior")), vulnerable, int(g.get("hours") or 1), stage_note=False) for g in groups]
    online = [r for r in rows if r["mode"] == "온라인"]
    valid = sum(r["valid_count"] for r in online)
    notes = list(dict.fromkeys(n for r in rows for n in r["notes"]))
    if online:
        notes.append(_stage_note(valid))
    return {"groups": rows, "total": sum(r["total"] for r in rows), "later_total": sum(r["later"]["amount"] for r in rows if r["later"]),
            "valid_count": valid if online else None, "counts_for_stage": valid >= MONTHLY_MIN if online else None,
            "notes": notes, "sources": SOURCES, "disclaimer": DISCLAIMER}


# ------------------------------------------------------------------ 질문에서 조건 읽기 (라우터용)
_AMOUNT = re.compile(r"얼마")
_ABOUT_PAY = re.compile(r"시간당|한\s*시간|시급|활동비|수당|가산금|받")
# 결석·취소 회차, 친화·성장활동, 봉사형처럼 조건이 붙은 금액은 일반 시간당 금액으로 답하면 틀린다: 매뉴얼 검색으로 보낸다
_NOT_CALC = re.compile(r"언제|며칠|기한|어디|세금|공제|장학금|입금|결석|취소|지각|조퇴|이탈|친화|성장\s*활동|봉사")


def is_rate_question(text: str) -> bool:
    """'시간당 얼마'처럼 금액을 묻는 질문인지. 지급일·세금, 결석·취소 회차의 금액 같은 질문은 매뉴얼 검색으로 보낸다."""
    return bool(_AMOUNT.search(text) and _ABOUT_PAY.search(text) and not _NOT_CALC.search(text))


def answer_rate_question(text: str) -> dict:
    """질문에 적힌 조건으로 시간당 금액을 계산해 답한다. 유형이 안 적혀 있으면 온라인·오프라인을 모두 보여 준다."""
    modes = [m for m in ("온라인", "오프라인") if m in text] or ["온라인", "오프라인"]
    senior = bool(re.search(r"고등|고학년|고[1-3]", text))
    vulnerable = "취약계층" in text
    top = bool(re.search(r"최대|최고|많이", text))
    m = re.search(r"(\d{1,2})\s*구간", text)
    stage = int(m.group(1)) if m and 1 <= int(m.group(1)) <= MAX_STAGE else None
    m = re.search(r"(\d{1,3})\s*회차", text)
    if stage is None and m:
        stage = min(MAX_STAGE, (max(int(m.group(1)), 1) - 1) // 8 + 1)   # 1~8회차 1구간, 9~16회차 2구간 …
    parts, results = [], []
    for mode in modes:
        r = hourly(mode, stage or 1, senior or top, vulnerable and not (senior or top))
        results.append(r)
        detail = " + ".join(f"{i['name']} {i['amount']:,}원" for i in r["items"])
        cond = f" ({r['stage']}구간 기준)" if mode == "온라인" else ""
        parts.append(f"{mode} 멘토링{cond}은 시간당 {r['total']:,}원입니다: {detail}.")
        if not (senior or top or vulnerable):
            extra = up10((ONLINE_BASE if mode == "온라인" else OFFLINE_BASE) * EXTRA_RATE)
            parts.append(f"고학년지도 또는 취약계층지원 가산금 대상이면 {extra:,}원이 더 붙습니다 (둘 중 하나만).")
        if mode == "온라인" and stage is None:
            parts.append("온라인은 9회차부터 장기활동 가산금이 구간별로 10~50% 더 붙습니다.")
    if top:
        parts.append("최대 금액은 고학년지도 또는 취약계층지원 가산금 중 하나를 받는 경우로 계산했습니다.")
    for note in dict.fromkeys(n for r in results for n in r["notes"]):
        parts.append(note)
    parts.append(DISCLAIMER)
    return {"answer": " ".join(parts), "citations": SOURCES, "results": results}

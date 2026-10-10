"""초안 검증 규칙. 계산과 검증은 여기서 하고 LLM은 문장만 만든다."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

_NUM = re.compile(r"\d+(?:[.,:]\d+)*")
_TIME_RANGE = re.compile(r"(\d{1,2}):(\d{2})\s*[~\-–]\s*(\d{1,2}):(\d{2})")
# 플랫폼 입력에서 오류를 낼 수 있는 문자. 한글, 영문, 숫자, 흔한 문장부호만 남긴다 (허용 범위는 미확인이라 보수적으로)
_NOT_PLAIN = re.compile(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ\s.,()/~:\-]")
_CIRCLED = {c: str(i) for i, c in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳", 1)}
_ROMAN = {"Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5"}


def numbers(text: str) -> set[str]:
    """글에 나온 숫자 토큰 ('03'은 '3'으로도 센다). '17:03' 같은 묶음은 쪼개지 않는다:
    쪼개면 시각의 '3'이 '3등급' 같은 지어낸 숫자를 통과시킨다."""
    out: set[str] = set()
    for tok in _NUM.findall(text or ""):
        out.add(tok)
        out.add(tok.lstrip("0") or "0")
    return out


def unsupported_numbers(output: str, sources: str) -> list[str]:
    """출력에 있는데 입력 어디에도 없는 숫자. 날짜·점수·진도를 지어냈는지 보는 규칙 검사."""
    allowed = numbers(sources)
    bad = []
    for tok in _NUM.findall(output or ""):
        parts = [p.lstrip("0") or "0" for p in re.split(r"[.,:]", tok)]
        if tok not in allowed and not all(p in allowed for p in parts):
            bad.append(tok)
    return sorted(set(bad))


def drop_unsupported(value, sources: str):
    """지어낸 숫자가 든 문장(목록이면 항목)을 뺀다. (남긴 값, 빠진 숫자 목록)."""
    removed: list[str] = []
    if isinstance(value, list):
        kept = []
        for item in value:
            bad = unsupported_numbers(str(item), sources)
            removed += bad
            if not bad:
                kept.append(item)
        return kept, sorted(set(removed))
    lines = []
    for line in str(value).split("\n"):   # 줄 구성은 그대로 두고 줄 안에서 문장 단위로 본다
        kept_s = []
        for s in re.split(r"(?<=[.!?])[ \t]+", line):
            bad = unsupported_numbers(s, sources)
            removed += bad
            if not bad:
                kept_s.append(s)
        if kept_s or not line.strip():
            lines.append(" ".join(kept_s))
    return "\n".join(lines).strip(), sorted(set(removed))


def parse_time_range(text: str) -> tuple[int, int] | None:
    """'17:03~18:05' → (시작 분, 종료 분). 못 읽으면 None."""
    m = _TIME_RANGE.search(text or "")
    if not m:
        return None
    h1, m1, h2, m2 = map(int, m.groups())
    if not (0 <= h1 <= 23 and 0 <= h2 <= 24 and m1 < 60 and m2 < 60):
        return None
    return h1 * 60 + m1, h2 * 60 + m2


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def check_time_range(text: str, rules: dict, need_min: bool = True) -> list[str]:
    r = parse_time_range(text)
    if r is None:
        return ["진행시간을 '17:10~18:09'처럼 시작~종료로 적어 주세요."]
    start, end = r
    out = []
    if end <= start:
        out.append("진행시간의 종료 시각이 시작 시각보다 빠릅니다.")
    if "earliest_start" in rules and start < _minutes(rules["earliest_start"]):
        out.append(f"멘토링은 {rules['earliest_start']} 이후에 시작해야 합니다.")
    if "latest_end" in rules and end > _minutes(rules["latest_end"]):
        out.append(f"멘토링은 {rules['latest_end']} 이전에 끝나야 합니다.")
    if need_min and "min_minutes" in rules and 0 < end - start < rules["min_minutes"]:
        out.append(f"실제 진행시간이 {end - start}분으로 {rules['min_minutes']}분에 못 미칩니다. 출석 인정 기준을 확인해 주세요.")
    return out


def parse_date(text: str) -> date | None:
    m = re.search(r"(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})", text or "")
    if not m:
        return None
    try:
        return date(*map(int, m.groups()))
    except ValueError:
        return None


def parse_datetime(text: str) -> datetime | None:
    d = parse_date(text)
    m = re.search(r"(\d{1,2}):(\d{2})", text or "")
    if not d or not m:
        return None
    try:
        return datetime(d.year, d.month, d.day, int(m.group(1)), int(m.group(2)))
    except ValueError:   # 25:00 같은 없는 시각
        return None


def add_days(d: date, days: int) -> date:
    return d + timedelta(days=days)


def fmt(d: date) -> str:
    return f"{d.year}.{d.month:02d}.{d.day:02d}."


def plain_text(text: str) -> tuple[str, list[str]]:
    """플랫폼 입력용: 동그라미 숫자·로마 숫자는 일반 숫자로, 그 밖의 특수문자는 뺀다. (정리한 글, 바꾸거나 뺀 문자)."""
    removed: list[str] = []
    out = []
    text = re.sub(r"(?m)^[ \t]*[·•ㆍ][ \t]*", "", text)       # 줄 머리의 글머리 기호는 뗀다 (', 시간 지키기'가 되지 않게)
    text = re.sub(r"(\d)[·ㆍ](\d)", r"\1.\2", text)          # 6·25 → 6.25 (화면의 platformSafe와 같은 규칙)
    for ch in text:
        if ch in _CIRCLED:
            out.append(f"({_CIRCLED[ch]})")
            removed.append(ch)
        elif ch in _ROMAN:
            out.append(_ROMAN[ch])
            removed.append(ch)
        elif ch in "·•ㆍ":
            out.append(", ")
            removed.append(ch)
        elif _NOT_PLAIN.match(ch):
            out.append(" ")
            removed.append(ch)
        else:
            out.append(ch)
    cleaned = re.sub(r"[ \t]+", " ", "".join(out)).replace(" ,", ",").strip()
    return cleaned, sorted(set(removed))

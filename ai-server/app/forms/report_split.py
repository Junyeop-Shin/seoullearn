"""서울런 플랫폼에서 복사한 활동보고서 여러 개를 회차별로 나눈다 (규칙 기반, LLM 없음).

붙여 넣은 글에서 활동보고서 서식의 항목 이름(멘토링 일자, 진행 회차 …)을 찾아 그 뒤의 글을 값으로 읽는다.
개인정보 칸(멘티 성명 등)의 값은 읽고 바로 버린다.
"""
from __future__ import annotations

import re

from .engine import load_form

_SESSION_NO = re.compile(r"(\d{1,2})")


def _labels() -> list[tuple[str, str, bool]]:
    """(항목 이름, key, 개인정보 여부). 긴 이름부터 찾는다 ('학습진도 - 출결'이 '학습진도'보다 먼저)."""
    out = []
    for f in load_form("activity_report")["fields"]:
        out.append((f["label"], f["key"], bool(f.get("pii"))))
        short = re.sub(r"\s*\(.*?\)", "", f["label"]).strip()   # '진행시간 (실제 접속시간)' → '진행시간'
        if short != f["label"]:
            out.append((short, f["key"], bool(f.get("pii"))))
    return sorted(out, key=lambda x: -len(x[0]))


def _find_labels(text: str) -> list[tuple[int, int, str, bool]]:
    """글에서 항목 이름이 나오는 자리. (시작, 끝, key, 개인정보)."""
    found: list[tuple[int, int, str, bool]] = []
    taken: list[tuple[int, int]] = []
    for label, key, pii in _labels():
        pat = re.compile(r"(?m)^[ \t\-•·\[]*" + r"\s*".join(map(re.escape, label.split())) + r"[\]\s]*[:：]?[ \t]*")
        for m in pat.finditer(text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append((m.start(), m.end(), key, pii))
    return sorted(found)


def split(text: str) -> dict:
    """{sessions: [{session_no, ...필드 key별 값}], warnings}. 회차 번호 순으로 정렬한다."""
    marks = _find_labels(text or "")
    warnings: list[str] = []
    if not marks:
        return {"sessions": [], "warnings": ["활동보고서 항목을 찾지 못했습니다. 플랫폼의 보고서 내용을 항목 이름과 함께 복사해 붙여 넣어 주세요."]}
    # 보고서 하나의 시작: 같은 key가 다시 나오면 새 보고서로 본다
    blocks: list[dict] = []
    cur: dict = {}
    for n, (start, end, key, pii) in enumerate(marks):
        value = text[end : marks[n + 1][0] if n + 1 < len(marks) else len(text)].strip()
        if key in cur or (key == "session_date" and cur):
            blocks.append(cur)
            cur = {}
        cur[key] = "" if pii else value
    if cur:
        blocks.append(cur)
    sessions = []
    for b in blocks:
        m = _SESSION_NO.search(str(b.get("session_no", "")))
        if not m:
            warnings.append("진행 회차를 읽지 못한 보고서가 있어 뺐습니다.")
            continue
        b["session_no"] = int(m.group(1))
        sessions.append({k: v for k, v in b.items() if v != "" or k == "session_no"})
    sessions.sort(key=lambda s: s["session_no"])
    nos = [s["session_no"] for s in sessions]
    dup = sorted({n for n in nos if nos.count(n) > 1})
    if dup:
        warnings.append(f"같은 회차가 두 번 들어 있습니다: {', '.join(map(str, dup))}회차. 나중 것을 썼습니다.")
        sessions = list({s["session_no"]: s for s in sessions}.values())
    if sessions:
        missing = [n for n in range(1, max(s["session_no"] for s in sessions) + 1) if n not in {s["session_no"] for s in sessions}]
        if missing:
            warnings.append(f"빠진 회차가 있습니다: {', '.join(map(str, missing))}회차.")
    return {"sessions": sessions, "warnings": warnings}

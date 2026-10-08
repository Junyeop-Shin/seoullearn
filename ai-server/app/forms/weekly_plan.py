"""주차별(회차별) 계획 추천.

몇 회차에 몇 강을 넣을지는 규칙 함수(allocate)가 정한다. LLM은 회차마다 '멘토링 내용'과 '상담' 문장만 쓴다.
'온라인 강의' 줄은 배분 결과로 코드가 만든다 (LLM이 강 번호를 쓰지 않는다).
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, timedelta

from ..llm import ChatLLM, LLMUnavailableError
from . import checks

PACE = {"느림": 0.8, "보통": 1.0, "빠름": 1.25}
MAX_PER_SESSION = 3
COUNSEL = ["학습 계획 점검", "인강 수강 습관 점검", "과제·오답 정리 방법 상담", "학습 고민 상담"]


def _in(d: date, ranges: list[tuple[date, date]]) -> bool:
    return any(a <= d <= b for a, b in ranges)


def allocate(lectures: list[dict], done: int = 0, sessions: int = 16, pace: str = "보통", start_date: date | None = None,
             exams: list[tuple[date, date]] | None = None, breaks: list[tuple[date, date]] | None = None,
             exam_sessions: list[int] | None = None) -> dict:
    """회차별 강의 배분.

    lectures: [{no, title, ...}] 강좌 전체 목록. done: 이미 들은 강 수(앞에서부터).
    exams: 시험 기간(날짜). 시험 기간에 걸린 회차는 새 강의를 넣지 않고, 그 직전 회차는 복습으로 둔다.
    exam_sessions: 날짜 대신 회차 번호로 시험 주를 줄 때. breaks: 방학 기간. 방학 회차는 강의를 조금 더 넣는다.
    """
    if pace not in PACE:
        raise ValueError(f"학습 속도는 {', '.join(PACE)} 중 하나여야 합니다.")
    exams, breaks = exams or [], breaks or []
    remaining = list(lectures[done:])
    plan = []
    for n in range(1, sessions + 1):
        d = start_date + timedelta(days=7 * (n - 1)) if start_date else None
        plan.append({"no": n, "date": d.isoformat() if d else None, "kind": "진도", "lectures": [], "vacation": bool(d and _in(d, breaks))})
    # 시험 기간과 그 직전 복습 회차
    exam_nos = set(exam_sessions or [])
    for s in plan:
        if s["date"] and _in(date.fromisoformat(s["date"]), exams):
            exam_nos.add(s["no"])
    for s in plan:
        d = date.fromisoformat(s["date"]) if s["date"] else None
        before_exam = (s["no"] + 1 in exam_nos) or bool(d and any(d < a <= d + timedelta(days=7) for a, _ in exams))
        if s["no"] in exam_nos:
            s["kind"] = "시험기간"
        elif before_exam:
            s["kind"] = "복습"
    if sessions >= 4 and plan[-1]["kind"] == "진도":
        plan[-1]["kind"] = "정리"  # 마지막 회차는 총정리와 연장 상담
    teach = [s for s in plan if s["kind"] == "진도"]
    total, t = len(remaining), len(teach)
    warnings: list[str] = []
    given = 0
    for j, s in enumerate(teach):
        target = min(total, round((j + 1) * total / t * PACE[pace])) if t else 0
        want = target - given
        if s["vacation"] and given + want < total:
            want += 1  # 방학에는 한 강 더
        want = max(0, min(want, MAX_PER_SESSION, total - given))
        s["lectures"] = remaining[given : given + want]
        given += want
    for s in teach:
        if not s["lectures"]:
            s["kind"] = "복습" if given else "진도확인"
    left = total - given
    if left > 0:
        warnings.append(f"이 속도로는 {sessions}회차 안에 {left}강이 남습니다. 속도를 올리거나 다음 회기 계획에 넣어 주세요.")
    if total == 0:
        warnings.append("남은 강의가 없습니다. 복습과 문제 풀이 위주로 계획했습니다.")
    if t and total and math.ceil(total / t) > MAX_PER_SESSION:
        warnings.append(f"회차당 {MAX_PER_SESSION}강을 넘지 않게 배분했습니다.")
    return {"sessions": plan, "covered": given, "left": left, "warnings": warnings}


def online_line(s: dict) -> str:
    """'온라인 강의' 줄. 배분 결과만으로 만든다."""
    if s["lectures"]:
        return ", ".join(f"{x['no']}강 {x['title']}" if x.get("no") is not None and not re.match(r"^\s*\d+강", str(x["title"]))
                         else str(x["title"])
                         for x in s["lectures"])
    return {"복습": "앞 회차 강의 복습", "시험기간": "시험 범위 강의 복습", "정리": "수강 강의 총정리"}.get(s["kind"], "수강 진도 확인")


def _fallback(s: dict, k: int) -> dict:
    titles = ", ".join(str(x["title"]) for x in s["lectures"])
    mentoring = {"진도": f"{titles} 개념 정리와 문제 풀이" if titles else "수강 범위 질의응답",
                 "복습": "앞 회차 내용 복습과 오답 풀이", "시험기간": "시험 대비 질의응답과 오답 풀이",
                 "정리": "회기 학습 내용 총정리", "진도확인": "수강 진도 확인과 질의응답"}[s["kind"]]
    counsel = "다음 회기 연장 여부와 학습 계획 상담" if s["kind"] == "정리" else (
        "시험 준비 점검" if s["kind"] in ("복습", "시험기간") else COUNSEL[k % len(COUNSEL)])
    return {"mentoring": mentoring, "counsel": counsel}


SYSTEM = """서울런 멘토링의 회차별 계획에서 회차마다 두 가지를 짧게 쓴다.
- mentoring: 그 회차 멘토링에서 할 일 (강의 제목에 맞는 개념 정리, 문제 풀이, 복습 등). 20자 안팎
- counsel: 학습·진학 상담 주제 한 가지. 15자 안팎

규칙:
1. [회차 목록]에 있는 강의 제목과 회차 종류만 근거로 쓴다. 강 번호, 날짜, 점수, 교재 쪽수 같은 숫자를 쓰지 않는다.
2. [참고]에 없는 진로, 목표 점수, 학교 이야기를 만들지 않는다.
3. 종류가 '복습'·'시험기간'이면 새 진도를 쓰지 않는다. '정리'이면 총정리와 다음 회기 연장 상담을 쓴다.

JSON 객체 하나만 출력한다. 키는 회차 번호 문자열이다.
{"1": {"mentoring": "...", "counsel": "..."}, "2": {...}}"""


def write_lines(alloc: dict, llm: ChatLLM | None, context: dict | None = None) -> dict:
    """회차별 세 줄을 붙인다. LLM이 없거나 형식이 틀리면 규칙 문장으로 대신한다."""
    sessions, error, data = alloc["sessions"], None, {}
    if llm is not None:
        listing = [{"회차": s["no"], "종류": s["kind"], "강의": [str(x["title"]) for x in s["lectures"]]} for s in sessions]
        user = f"[참고]\n{json.dumps(context or {}, ensure_ascii=False)}\n\n[회차 목록]\n{json.dumps(listing, ensure_ascii=False)}"
        try:
            raw = llm.complete(SYSTEM, user)
            m = re.search(r"\{.*\}", raw, re.S)
            if not m:
                raise ValueError("JSON 없음")
            data = json.loads(m.group(0))
        except LLMUnavailableError:
            raise
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
    replaced = 0
    for k, s in enumerate(sessions):
        fb = _fallback(s, k)
        got = data.get(str(s["no"])) if isinstance(data, dict) else None
        lines = {}
        for key in ("mentoring", "counsel"):
            text = str((got or {}).get(key) or "").strip()
            # 강의 제목에 있는 숫자 말고 다른 숫자가 나오면 지어낸 것으로 보고 규칙 문장을 쓴다
            if not text or checks.unsupported_numbers(text, json.dumps([x["title"] for x in s["lectures"]], ensure_ascii=False)):
                replaced += bool(text)
                text = fb[key]
            lines[key] = text
        s["online"] = online_line(s)
        s["mentoring"], s["counsel"] = lines["mentoring"], lines["counsel"]
        s["line"] = f"(온라인 강의) {s['online']} / (멘토링 내용) {s['mentoring']} / (상담) {s['counsel']}"
    if replaced:
        alloc["warnings"].append(f"AI가 쓴 문장 {replaced}개에 근거 없는 숫자가 있어 기본 문장으로 바꿨습니다.")
    alloc["error"] = error
    return alloc

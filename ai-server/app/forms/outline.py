"""강의 목차 파서: 멘토가 학습사이트 강좌 페이지에서 복사해 붙여 넣은 글 → 강 단위 목록.

규칙으로 먼저 나누고, 규칙으로 못 나눈 줄만 LLM에 묻는다. 학습사이트에 접속하거나 긁어 오지 않는다.
출력: [{no, title, unit, minutes}]  (no는 목차에 번호가 없으면 null)
"""
from __future__ import annotations

import json
import re

from ..llm import ChatLLM, LLMUnavailableError

_NOISE = re.compile(r"^(수강하기|맛보기|미리보기|강의\s*목차|목차|교재|다운로드|재생|완강|수강\s*중|NEW|HOT|\d+%|총\s*\d+강.*)$", re.I)
_UNIT = re.compile(r"^\s*(?:[\[\(<【■▶◆●]\s*)?((?:제?\s*\d+\s*(?:단원|장|부|편)|(?:PART|Part|CHAPTER|Chapter|UNIT|Unit)\s*\d+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*[.\)]|[IVX]{1,4}\s*\.)\s*.*?)\s*[\]\)>】]?\s*$")
_LECTURE = [
    re.compile(r"^\s*[\[\(]?\s*(?:제\s*)?(\d{1,3})\s*(?:강|차시|회차|회)\s*[\]\)]?\s*[.:\-]?\s*(.+)$"),
    re.compile(r"^\s*(?:Theme|THEME|Lecture|LECTURE|Lesson|LESSON|Day|DAY)\s*(\d{1,3})\s*[.:\-]?\s*(.+)$"),
    re.compile(r"^\s*(\d{1,3})\s*[.\)]\s+(.+)$"),
    re.compile(r"^\s*(\d{1,3})\s+(\D.+)$"),
]
_MIN = [
    (re.compile(r"\(?\s*(\d{1,2}):(\d{2}):(\d{2})\s*\)?\s*$"), lambda m: int(m[1]) * 60 + int(m[2]) + (1 if int(m[3]) >= 30 else 0)),
    (re.compile(r"\(?\s*(\d{1,3}):(\d{2})\s*\)?\s*$"), lambda m: int(m[1]) + (1 if int(m[2]) >= 30 else 0)),
    (re.compile(r"\(?\s*(\d{1,3})\s*분\s*\)?\s*$"), lambda m: int(m[1])),
]

ASK = """학습사이트 강좌 목차에서 복사한 줄들이다. 각 줄이 강의 한 개인지 판단해 정리한다.
- 강의이면 {"line": 줄 번호, "title": "강의 제목", "minutes": 분 또는 null}
- 강의가 아니면(단원 이름, 메뉴, 광고 등) {"line": 줄 번호, "title": null}
줄에 없는 내용을 만들지 않는다. JSON 배열 하나만 출력한다."""


def _minutes(title: str) -> tuple[str, int | None]:
    for pat, conv in _MIN:
        m = pat.search(title)
        if m:
            return title[: m.start()].rstrip(" -|·,"), conv(m)
    return title, None


def parse(text: str, llm: ChatLLM | None = None) -> dict:
    lectures: list[dict] = []
    pending: list[tuple[int, str, str | None]] = []  # (위치, 줄, 단원)
    unit: str | None = None
    for raw in (text or "").splitlines():
        line = re.sub(r"\s+", " ", raw.replace("\t", " ")).strip()
        if not line or _NOISE.match(line):
            continue
        um = _UNIT.match(line)
        if um and not re.match(r"^\s*\d{1,3}\s*(?:강|차시)", line):
            unit = um.group(1).strip()
            continue
        for pat in _LECTURE:
            m = pat.match(line)
            if m:
                title, minutes = _minutes(m.group(2).strip())
                lectures.append({"no": int(m.group(1)), "title": title, "unit": unit, "minutes": minutes})
                break
        else:
            pending.append((len(lectures), line, unit))

    warnings: list[str] = []
    unparsed = [p[1] for p in pending]
    error = None
    if pending and llm is not None:
        numbered = "\n".join(f"{n}: {p[1]}" for n, p in enumerate(pending, 1))
        try:
            raw = llm.complete(ASK, numbered)
            m = re.search(r"\[.*\]", raw, re.S)
            if not m:
                raise ValueError("JSON 없음")
            unparsed = []
            answered = {int(x["line"]): x for x in json.loads(m.group(0))}
            for n, (pos, line, u) in enumerate(pending, 1):
                x = answered.get(n) or {}
                title = x.get("title")
                if title and str(title).replace(" ", "") in line.replace(" ", ""):  # 줄에 없는 제목은 받지 않는다
                    lectures.append({"no": None, "title": str(title).strip(), "unit": u,
                                     "minutes": x.get("minutes") if isinstance(x.get("minutes"), int) else None, "_pos": pos - 0.5 + n / 1000})
                elif title:
                    unparsed.append(line)
        except LLMUnavailableError:
            raise
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            unparsed = [p[1] for p in pending]
    # 원래 순서대로 놓는다. 번호가 없던 강(오리엔테이션 등)은 no를 비워 둔다 (사이트의 강 번호와 어긋나지 않게)
    out = [lec for _, lec in sorted(enumerate(lectures), key=lambda t: t[1].pop("_pos", t[0]))]
    nos = [x["no"] for x in out if x["no"] is not None]
    if len(set(nos)) != len(nos):
        warnings.append("강 번호가 겹칩니다. 여러 강좌의 목차가 섞였는지 확인해 주세요.")
    if unparsed:
        warnings.append(f"강의로 읽지 못한 줄이 {len(unparsed)}개 있습니다. 필요하면 직접 추가해 주세요.")
    if not out:
        warnings.append("강의 목록을 찾지 못했습니다. 강좌 페이지의 목차 부분을 복사해 붙여 넣어 주세요.")
    return {"lectures": out, "unparsed": unparsed, "warnings": warnings, "error": error}

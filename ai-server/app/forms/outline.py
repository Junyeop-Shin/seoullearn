"""강의 목차 파서: 멘토가 학습사이트 강좌 페이지에서 복사해 붙여 넣은 글 → 강 단위 목록.

규칙으로 먼저 나누고, 규칙으로 못 나눈 줄만 LLM에 묻는다. 학습사이트에 접속하거나 긁어 오지 않는다.
출력: [{no, title, unit, minutes}]  (no는 목차에 번호가 없으면 null)
재생 시간만 적힌 줄이 되풀이되는 목차는 묶음 단위로 읽는다: 시간 줄 앞의 첫 줄이 강의 제목이고, 번호가 없으면 순서대로 번호를 붙인다(auto_no).
"""
from __future__ import annotations

import json
import re

from .. import guard, prompts
from ..llm import ChatLLM, LLMUnavailableError

_NOISE = re.compile(r"^(수강하기|맛보기|미리보기|강의\s*목차|목차|교재|다운로드|재생|완강|수강\s*중|NEW|HOT|\d+%|총\s*\d+강.*)$", re.I)
_UNIT = re.compile(r"^\s*(?:[\[\(<【■▶◆●]\s*)?((?:제?\s*\d+\s*(?:단원|장|부|편)(?![가-힣])|(?:PART|Part|CHAPTER|Chapter|UNIT|Unit)\s*\d+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*[.\)]|[IVX]{1,4}\s*\.)\s*.*?)\s*[\]\)>】]?\s*$")
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

ASK = prompts.load("course_outline")
# 재생 시간만 있는 줄: '- 48:53', '1:01:13'
_DURATION_LINE = re.compile(r"^-?\s*(?:\d{1,2}:)?\d{1,3}:\d{2}$")
_TAIL_MARK = re.compile(r"\s*[▶▷►]\s*\S*$")   # 'Hard Core.15ㅣ100 ▶완강'의 꼬리표


def _parse_blocks(lines: list[str]) -> list[dict]:
    """제목 줄(과 덧붙은 줄들) 뒤에 재생 시간 줄이 오는 목차. 강의 제목이 제각각이어도 시간 줄로 강의를 가른다."""
    out: list[dict] = []
    block: list[str] = []
    for line in lines:
        if not _DURATION_LINE.match(line):
            block.append(line)
            continue
        titles = [x for x in block if not _NOISE.match(x)]
        block = []
        if not titles:
            continue
        title = _TAIL_MARK.sub("", titles[0]).strip() or titles[0]
        minutes = _minutes(line.lstrip("- "))[1]
        for pat in _LECTURE[:2]:   # '12강 제목'처럼 번호가 분명한 제목은 그 번호를 쓴다
            m = pat.match(title)
            if m:
                out.append({"no": int(m.group(1)), "title": m.group(2).strip(), "unit": None, "minutes": minutes})
                break
        else:
            out.append({"no": len(out) + 1, "title": title, "unit": None, "minutes": minutes, "auto_no": True})
    return out


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
    cleaned = [re.sub(r"\s+", " ", raw.replace("\t", " ")).strip() for raw in (text or "").splitlines()]
    cleaned = [x for x in cleaned if x]
    if sum(bool(_DURATION_LINE.match(x)) for x in cleaned) >= 3:
        blocks = _parse_blocks(cleaned)
        return {"lectures": blocks, "unparsed": [], "error": None,
                "warnings": [] if blocks else ["강의 목록을 찾지 못했습니다. 강좌 페이지의 목차 부분을 복사해 붙여 넣어 주세요."]}
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
            pending.append((len(lectures), guard.check(line).text, unit))  # LLM에 보낼 수 있는 줄: 가려 둔다

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


MAX_IMAGE_CHARS = 950_000   # data URL 글자 수. 화면이 줄여서 보내고, 앞단(nginx)의 요청 한도 1MB 안쪽이다
_IMAGE = re.compile(r"^data:image/(?:jpeg|png|webp);base64,[A-Za-z0-9+/=]+$")


def read_image(data_url: str, llm) -> dict:
    """강의 목록을 찍은 이미지 한 장 → 보이는 강의 줄들의 글. 멘토가 확인하고 고친 뒤 parse()에 넣는다.
    이미지는 가드로 가릴 수 없으므로, 돌아온 글은 가드를 한 번 거친다. 이미지도 글도 저장하지 않는다.
    돌려주는 값: {text, lines(줄 수), error}"""
    if not _IMAGE.match(data_url) or len(data_url) > MAX_IMAGE_CHARS:
        return {"text": "", "lines": 0, "error": "이미지를 읽지 못했습니다. JPG, PNG 이미지를 다시 올려 주세요."}
    reader = getattr(llm, "read_image", None)
    if reader is None:
        return {"text": "", "lines": 0, "error": "지금 설정된 AI 모델은 이미지를 읽지 못합니다. 강의 목록을 복사해 붙여 넣어 주세요."}
    raw = reader(prompts.load("course_outline_image"), "이 이미지의 강의 목록을 옮겨 적어 주세요.", data_url)
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        lines = json.loads(m.group(0))["lines"] if m else None
    except (ValueError, KeyError, TypeError):
        lines = None
    if not isinstance(lines, list):
        return {"text": "", "lines": 0, "error": "이미지에서 강의 목록을 읽지 못했습니다. 다시 시도하거나 목록을 복사해 붙여 넣어 주세요."}   # 형식 오류는 조용히 넘기지 않는다
    kept = [guard.drop_marks(guard.check(str(x)).text).strip() for x in lines if str(x).strip()]
    kept = [x for x in kept if x]
    return {"text": "\n".join(kept), "lines": len(kept), "error": "" if kept else "이미지에서 강의 목록을 찾지 못했습니다. 강의 목록이 보이게 찍은 이미지를 올려 주세요."}

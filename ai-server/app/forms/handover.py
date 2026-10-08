"""멘토 교체 인계 요약 (forms/handover_summary.json).

허용 목록 방식이다. 허용 항목마다 그 항목의 출처 칸(allow[].from)만 모아 LLM에 따로 묻는다.
학습이해도, 멘토링 학습 내용, 기타·건의사항 같은 출처가 아닌 칸은 LLM에 아예 보내지 않는다.
그래도 섞여 들어온 학업 수준·정서 표현은 2차 검사에서 문장째 뺀다.
"""
from __future__ import annotations

import json
import os
import re

from .. import guard
from ..llm import ChatLLM, LLMUnavailableError
from . import checks, sensitive
from .engine import load_form

SYSTEM = """이전 멘토의 활동보고서 기록에서 다음 멘토에게 넘길 '{label}' 한 가지만 요약한다.

규칙:
1. [기록]에 있는 내용만 쓴다. 기록에 없는 사실, 횟수, 날짜를 만들지 않는다.
2. {guidance}
3. 학업 수준(성적, 등급, 점수, 이해도, 잘한다·못한다, 어려워한다는 평가)은 쓰지 않는다.
4. 정서·가정·교우 관계, 멘토의 개인 사정, 이름·학교·연락처는 쓰지 않는다.
5. 보고서 문체로 한두 문장.

JSON 한 개만 출력한다: {{"summary": "..."}}"""

# 2차 검사: 요약에 남아 있으면 안 되는 표현 (학업 수준, 정서·개인 사정)
_ACADEMIC = re.compile(r"성적|등급|점수|\d+\s*점|중간고사|기말고사|모의고사|시험\s*(?:결과|점수|성적)|이해도|이해력|이해가\s*(?:빠|느|부족|낮|높)|"
                       r"잘함|잘\s*하는\s*편|못\s*하는\s*편|어려워|어려움|약하|약함|취약|우수|뛰어나|상위권|하위권|중위권|학업\s*수준|학습\s*수준")
_PERSONAL = re.compile(r"군입대|입대|유학|퇴사|개인\s*사정|서운|아쉬워")
# '학습진도(성실성)' 척도의 값은 태도 항목에서 써도 된다 (학업 수준이 아니라 성실성 평가다)
_SCALE_WORDS = ("매우 잘함", "잘함", "보통", "노력필요", "매우 노력필요")


def include_weak_units() -> bool:
    """취약 단원 포함 여부는 미정 사항이다. 기본은 넣지 않는다."""
    return os.getenv("HANDOVER_INCLUDE_WEAK_UNITS", "false").lower() == "true"


def _allow_items() -> list[dict]:
    items = list(load_form("handover_summary")["allow"])
    if include_weak_units():
        items.append({"key": "weak_units", "label": "취약 단원", "from": ["activity_report.session_content"],
                      "guidance": "멘티가 어려워한 단원 이름만 나열. 평가나 점수는 쓰지 않음"})
    return items


def last_lecture(reports: list[dict]) -> dict:
    """마지막으로 수강이 확인된 강 번호와 다음 시작 강. 숫자는 규칙으로 구한다 (LLM이 '다음은 9강'을 계산하지 않게)."""
    last = 0
    for r in reports:
        text = str(r.get("lecture_progress") or "")
        if "미수강" in text and "수강" not in text.replace("미수강", ""):
            continue
        for part in re.split(r"[,/]|그리고", text):
            if "미수강" in part:
                continue
            last = max([last] + [int(n) for n in re.findall(r"(\d{1,3})\s*강", part)] +
                       [int(n) for n in re.findall(r"(\d{1,3})\s*,\s*\d{1,3}\s*강", text)])
    return {"마지막으로 수강한 강": f"{last}강", "다음 시작": f"{last + 1}강"} if last else {}


def _records(item: dict, reports: list[dict]) -> list[dict]:
    """이 항목의 출처 칸만 뽑는다."""
    keys = [src.split(".", 1)[1] for src in item["from"] if src.startswith("activity_report.")]
    out = []
    for r in sorted(reports, key=lambda x: int(re.sub(r"\D", "", str(x.get("session_no", 0))) or 0)):
        row = {"회차": r.get("session_no")}
        for k in keys:
            v = str(r.get(k) or "").strip()
            if v:
                row[k] = sensitive.filter_text(guard.check(v).text)[0]
        if len(row) > 1:
            out.append(row)
    return out


def second_check(text: str, key: str) -> tuple[str, list[str]]:
    """(남긴 글, 뺀 문장). 학업 수준·정서·개인 사정 표현이 든 문장을 뺀다."""
    kept, dropped = [], []
    for s in [x.strip() for x in re.split(r"(?<=[.!?])\s+", text or "") if x.strip()]:
        probe = s
        if key == "attitude":
            for w in _SCALE_WORDS:   # 성실성 척도 값은 검사에서 제외
                probe = probe.replace(w, "")
        if key != "weak_units" and _ACADEMIC.search(probe) or _PERSONAL.search(probe) or sensitive.filter_text(s)[1]:
            dropped.append(s)
        else:
            kept.append(s)
    return " ".join(kept), dropped


def build(reports: list[dict], llm: ChatLLM) -> dict:
    """{summary: {key: 글}, labels: {key: 이름}, warnings, pii_masked, errors}. 서버에 저장하지 않는다."""
    reports = [r for r in (reports or []) if isinstance(r, dict)]
    summary: dict[str, str] = {}
    labels: dict[str, str] = {}
    warnings: list[str] = []
    errors: list[str] = []
    pii: set[str] = set()
    for r in reports:
        for v in r.values():
            if isinstance(v, str):
                pii.update(guard.check(v).pii)
    if not reports:
        warnings.append("활동보고서가 없습니다. 보관함에서 불러오거나 플랫폼의 보고서를 붙여 넣어 주세요.")
    for item in _allow_items():
        key = item["key"]
        labels[key] = item["label"]
        records = _records(item, reports)
        if not records:
            summary[key] = ""
            continue
        if key == "course_progress" and last_lecture(reports):
            records = records + [{"규칙으로 계산한 진도": last_lecture(reports)}]
        source = json.dumps(records, ensure_ascii=False)
        try:
            raw = llm.complete(SYSTEM.format(label=item["label"], guidance=item["guidance"]), f"[기록]\n{source}")
            m = re.search(r"\{.*\}", raw, re.S)
            if not m:
                raise ValueError("JSON 없음")
            text = str(json.loads(m.group(0))["summary"]).strip()
        except LLMUnavailableError:
            raise
        except Exception as e:   # 형식 오류는 기록하고 그 항목을 비워 둔다 (지어내지 않는다)
            errors.append(f"{key}: {type(e).__name__}: {e}")
            summary[key] = ""
            warnings.append(f"'{item['label']}' 요약을 만들지 못했습니다. 직접 작성해 주세요.")
            continue
        text = guard.check(text).text
        text, removed = checks.drop_unsupported(text, source + json.dumps(item, ensure_ascii=False))
        if removed:
            warnings.append(f"'{item['label']}'에 기록에 없는 숫자({', '.join(removed)})가 있어 해당 문장을 뺐습니다.")
        text, dropped = second_check(text, key)
        if dropped:
            warnings.append(f"'{item['label']}'에서 학업 수준이나 정서·개인 사정에 해당하는 문장 {len(dropped)}개를 뺐습니다.")
        summary[key] = text
    return {"summary": summary, "labels": labels, "warnings": warnings, "pii_masked": sorted(pii), "errors": errors,
            "reminders": ["인계 요약은 이전 멘토가 내용을 확인한 뒤 운영사무국·이음단을 통해 전달합니다.",
                          "학업 수준(성적·이해도)과 정서·상담 내용은 인계하지 않습니다."]}

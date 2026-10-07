"""매뉴얼 Q&A: 검색 → 답변 생성 → 근거·문의처 정리."""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field

from . import guard
from .corpus import Chunk
from .llm import ChatLLM, LLMUnavailableError

ROUTES = ["운영사무국", "이음단", "학습지원센터", "운영사무국(즉시)"]
ROUTE_INFO = {
    "운영사무국": "멘토링 운영사무국 (02-3274-9212, 카카오 채널 '서울런멘토링')",
    "이음단": "소속 자치구 이음단 (카카오톡 오픈채팅)",
    "학습지원센터": "서울런 학습지원센터 (1533-0909)",
    "운영사무국(즉시)": "멘토링 운영사무국 (02-3274-9212)에 즉시 보고",
}

SYSTEM = """너는 서울런 멘토의 업무 질문에 답하는 도우미다. 아래 규칙을 반드시 지킨다.

1. [자료]에 있는 내용으로만 답한다. 자료에 없는 사실, 숫자, 날짜를 만들지 않는다.
2. 자료로 완전히 답할 수 있으면 answerable="yes", 일부만 답할 수 있으면 "partial", 답할 수 없으면 "no".
   partial이나 no이면 route에 문의처를 고른다.
3. 문의처 기준 (활동가이드 p.62를 바탕으로 정리):
   - 운영사무국: 매칭 전 단계(멘토 선발·교육, 매칭 조건 변경, 재매칭, 활동중단)와 사업 전체 운영
     (활동비·가산금, 공지·규정, 장학금, 시간확대 승인, 화상시스템 장애 등)
   - 이음단: 매칭 이후 실제 멘토링 운영. 온라인·오프라인 모두 해당한다. 장소, 일정 변경,
     활동보고서 승인·보완, 출결 확인 등. 운영사무국과 멘토 사이를 이어주는 창구다.
   - 학습지원센터: 멘티의 서울런 홈페이지 사용
   - 운영사무국(즉시): 보호자 갈등이 심하거나 아동 보호·안전 우려가 있을 때
   자료에 연락할 곳이 적혀 있으면 자료를 따른다. 자료에 '담당자'라고만 나오면 매칭 전 일은 운영사무국,
   매칭 이후 멘토링 운영은 이음단으로 본다.
   답을 완전히 했더라도 그 절차상 연락해야 하는 곳이 있으면 route에 적는다. 연락할 곳이 없으면 null.
4. 온라인과 오프라인 규칙이 다르면 질문이 어느 쪽인지 보고, 모르면 둘 다 구분해 답한다.
5. 공지와 활동가이드가 다르면 게시일이 최근이고 효력 중인 공지를 따른다.
   '활동가이드 내용을 바꾼 공지' 표시가 있는 자료로 답할 때는 무엇이 어떻게 바뀌었는지(이전 기준과 지금 기준)를
   한 문장으로 반드시 밝힌다.
6. 답변은 한국어 존댓말, 3~5문장 이내로 핵심부터 쓴다. 질문에 답하는 데 필요 없는 자료 내용은 덧붙이지 않는다.
7. citations에는 답변에 실제로 쓴 자료 번호만 넣는다.

반드시 아래 JSON 한 개만 출력한다. 코드블록 표시는 쓰지 않는다.
{"answerable": "yes|partial|no", "answer": "...", "citations": [1, 2], "route": null}"""


@dataclass
class QAResult:
    question: str
    answer: str
    answerable: str
    route: str | None
    citations: list[str] = field(default_factory=list)  # chunk id
    cite_labels: list[str] = field(default_factory=list)
    retrieved: list[str] = field(default_factory=list)  # chunk id, 순위대로
    pii_masked: list[str] = field(default_factory=list)
    safety: bool = False
    latency_ms: int = 0
    raw: str = ""
    error: str | None = None

    def to_dict(self):
        return asdict(self)


# 이음단 오픈채팅 주소 형식. 다른 주소는 받지 않는다.
KAKAO_OPENCHAT_PATTERN = r"^https://open\.kakao\.com/[A-Za-z0-9/_\-]+$"


def route_contact(route: str | None, ieumdan_chat_url: str | None = None) -> tuple[str | None, str | None]:
    """문의처 안내 문구와 링크. 이음단 오픈채팅 주소는 자치구마다 달라서 멘토가 보낸 값을 그대로 쓴다.
    서버는 이 주소를 저장하지 않는다."""
    if not route:
        return None, None
    link = ieumdan_chat_url if route == "이음단" else None
    return ROUTE_INFO.get(route), link


def build_context(chunks: list[Chunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        meta = f"{c.cite} | 유형: {c.mtype}"
        if c.doc_type != "manual":
            meta += f" | 게시일: {c.published} | 상태: {c.status}"
            if c.supersedes:
                meta += " | 활동가이드 내용을 바꾼 공지"
        parts.append(f"[자료 {i}] ({meta})\n{c.text}")
    return "\n\n".join(parts)


def parse_output(raw: str) -> dict:
    """모델이 코드블록이나 앞뒤 설명을 붙여도 JSON만 뽑는다."""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("JSON 없음")
    data = json.loads(m.group(0))
    if data.get("answerable") not in ("yes", "partial", "no"):
        raise ValueError(f"answerable 값 오류: {data.get('answerable')}")
    if data.get("route") not in ROUTES:  # 키가 없거나 목록 밖의 값이면 문의처 없음으로 본다
        data["route"] = None
    data["citations"] = [int(x) for x in data.get("citations", []) if str(x).isdigit()]
    return data


def answer(question: str, retriever, llm: ChatLLM, k: int = 5) -> QAResult:
    t0 = time.monotonic()
    g = guard.check(question)
    if g.safety:
        return QAResult(question=question, answer=guard.SAFETY_ANSWER, answerable="yes", route="운영사무국(즉시)",
                        pii_masked=g.pii, safety=True, latency_ms=int((time.monotonic() - t0) * 1000))
    hits = [c for c, _ in retriever.search(g.text, k)]
    user = f"[자료]\n{build_context(hits)}\n\n[질문]\n{g.text}"
    res = QAResult(question=question, answer="", answerable="no", route="운영사무국",
                   retrieved=[c.id for c in hits], pii_masked=g.pii)
    try:
        res.raw = llm.complete(SYSTEM, user)
        data = parse_output(res.raw)
        res.answer, res.answerable, res.route = data["answer"], data["answerable"], data["route"]
        used = [hits[i - 1] for i in data["citations"] if 1 <= i <= len(hits)]
        res.citations = [c.id for c in used]
        res.cite_labels = [c.cite for c in used]
    except LLMUnavailableError:  # 요청 한도·서버 과부하는 답변 실패가 아니다. 호출한 쪽에서 멈춘다
        raise
    except Exception as e:  # 형식 오류도 평가에 기록되도록 실패로 남긴다
        res.error = f"{type(e).__name__}: {e}"
        res.answer = "답변을 만들지 못했습니다. 운영사무국에 문의해 주세요."
    res.latency_ms = int((time.monotonic() - t0) * 1000)
    return res

"""의도 분류 라우터 (LangGraph).

흐름: 가드 → (아동 안전이면 즉시 안내) → 의도 분류 → qa / report / plan
- 분류는 먼저 규칙(키워드)으로 하고, 규칙으로 못 가를 때만 LLM을 부른다.
- report·plan은 멘티 화면에서 쓰므로 화면 안내와 필요한 입력 목록만 돌려준다.
- '시간당 얼마'처럼 금액을 묻는 질문은 활동비 계산기(규칙 함수)로 답한다. 검색도 LLM도 쓰지 않는다.
- LLM에는 가드로 가린 문장만 보낸다.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from . import allowance, guard, inquiry, qa
from .config import settings
from .llm import ChatLLM, LLMUnavailableError, first_json

INTENTS = ("qa", "report", "plan")

# 무엇에 관한 말인가
# 완료보고서와 친화·성장활동 결과보고서는 화면이 따로 있어 활동보고서 안내로 보내지 않는다 (매뉴얼 질문으로 답한다)
_REPORT = re.compile(r"활동\s*보고서|주간\s*보고서|회차\s*보고서|(?<!완료)(?<!완료\s)(?<!결과)(?<!결과\s)보고서")
_PLAN = re.compile(r"종합\s*계획서|계획서|주차별\s*계획|회차별\s*계획|커리큘럼|학습\s*계획")
# 써 달라는 말인가 (작성 요청)
_WRITE = re.compile(r"써\s*줘|써\s*주|작성해|작성\s*좀|작성을\s*도와|초안|만들어|짜\s*줘|짜\s*주|세워\s*줘|세워\s*주|추천해|정리해\s*줘|정리해\s*주|다듬어|채워\s*줘|채워\s*주")
# 규정·절차를 묻는 말인가
_ASK = re.compile(r"언제|어디|어떻게|얼마|몇\s|뭐예요|뭔가요|무엇|되나요|돼요|될까요|인가요|있나요|있어요\?|하나요|해야\s*(?:해|돼|하)|기한|마감|\?$")

ASK_SYSTEM = """서울런 멘토가 보낸 말의 의도를 하나로 분류한다.

- qa: 활동가이드·공지의 규정, 절차, 기한, 문의처를 묻는다. 보고서나 계획서에 '관한 질문'도 여기다.
- report: 활동보고서 초안을 써 달라, 다듬어 달라는 작성 요청이다.
- plan: 종합계획서나 주차별(회차별) 학습 계획을 짜 달라는 작성 요청이다.

JSON 한 개만 출력한다. 코드블록 표시는 쓰지 않는다.
{"intent": "qa|report|plan"}"""


def classify_by_rule(text: str) -> str | None:
    """규칙으로 확실히 가를 수 있으면 의도를, 애매하면 None을 돌려준다."""
    report, plan = bool(_REPORT.search(text)), bool(_PLAN.search(text))
    write, ask = bool(_WRITE.search(text)), bool(_ASK.search(text))
    if not report and not plan:
        return "qa"  # 보고서·계획서 이야기가 아니면 매뉴얼 질문
    if write and ask:
        return None  # "보고서 써줘도 되나요?"처럼 작성 요청인지 질문인지 섞임
    if not write:
        return "qa" if ask else None  # 주제만 있고 무엇을 원하는지 없음
    if report and plan:
        return None  # 두 양식이 함께 나옴
    return "plan" if plan else "report"


def classify_by_llm(text: str, llm: ChatLLM) -> tuple[str, str | None]:
    """(의도, 오류). 출력 형식이 틀리면 오류를 기록하고 qa로 보낸다."""
    try:
        intent = first_json(llm.complete(ASK_SYSTEM, text)).get("intent")
        if intent not in INTENTS:
            raise ValueError(f"intent 값 오류: {intent}")
        return intent, None
    except LLMUnavailableError:
        raise
    except Exception as e:
        return "qa", f"{type(e).__name__}: {e}"


# ------------------------------------------------------------- 화면 안내
SCREENS = {
    "report": {"form_id": "activity_report", "screen": "활동보고서 작성",
               "message": "활동보고서는 '내 멘티'에서 멘티를 고르면 쓸 수 있습니다. 아래 항목을 준비해 주세요."},
    "plan": {"form_id": "plan_initial", "screen": "종합계획서 작성",
             "message": "종합계획서는 '내 멘티'에서 멘티를 고르면 쓸 수 있습니다. 아래 항목을 준비해 주세요."},
}


@lru_cache(maxsize=8)
def required_inputs(form_id: str) -> tuple[str, ...]:
    """양식 스키마에서 멘토가 직접 넣어야 하는 필수 항목의 이름. 개인정보 칸은 입력받지 않으므로 뺀다."""
    path = settings.root / "forms" / f"{form_id}.json"
    fields = json.loads(path.read_text(encoding="utf-8"))["fields"]
    return tuple(f["label"] for f in fields
                 if f.get("required") and f.get("source") in ("user", "user_text") and not f.get("pii"))


# ----------------------------------------------------------------- 그래프
class ChatState(TypedDict, total=False):
    message: str            # 원문. 로그·저장에 쓰지 않는다
    masked: str             # 가드를 거친 문장 (LLM에는 이것만 보낸다)
    pii_masked: list[str]
    intent: str             # qa | report | plan | safety
    method: str             # guard | rule | llm
    classify_error: str | None
    result: dict


def build_graph(llm_factory: Callable[[], ChatLLM], retriever_factory: Callable[[], object]):
    """LLM과 검색기는 필요할 때만 만든다 (규칙으로 끝나는 요청은 둘 다 쓰지 않을 수 있다)."""

    def guard_node(state: ChatState) -> ChatState:
        g = guard.check(state["message"])
        out: ChatState = {"masked": g.text, "pii_masked": g.pii}
        if g.safety:
            out.update(intent="safety", method="guard")
        return out

    def classify_node(state: ChatState) -> ChatState:
        if allowance.is_rate_question(state["masked"]):
            return {"intent": "calc", "method": "rule", "classify_error": None}   # 금액 질문은 계산기로 (LLM 없음)
        intent = classify_by_rule(state["masked"])
        if intent:
            return {"intent": intent, "method": "rule", "classify_error": None}
        intent, err = classify_by_llm(state["masked"], llm_factory())
        return {"intent": intent, "method": "llm", "classify_error": err}

    def safety_node(state: ChatState) -> ChatState:
        return {"result": {"answer": guard.SAFETY_ANSWER, "answerable": "yes", "route": "운영사무국(즉시)",
                           "route_info": qa.route_contact("운영사무국(즉시)"), "citations": [], "safety": True}}

    def qa_node(state: ChatState) -> ChatState:
        res = qa.answer(state["message"], retriever_factory(), llm_factory(), settings.top_k)
        draft = inquiry.build(res)
        # 형식 오류면 답변 상태를 비운다: 화면이 '자료에서 찾지 못했습니다'라고 하지 않고, 답 못 한 질문으로도 남기지 않는다
        return {"result": {"answer": res.answer, "answerable": None if res.error else res.answerable, "route": res.route, "route_info": qa.route_contact(res.route),
                           "citations": res.cite_labels, "sources": res.sources, "changed_notices": res.changed_notices, "safety": res.safety,
                           "inquiry_draft": draft.text if draft else None,
                           "inquiry_contact": draft.contact if draft else None, "error": bool(res.error)}}

    def calc_node(state: ChatState) -> ChatState:
        r = allowance.answer_rate_question(state["masked"])
        return {"result": {"answer": r["answer"], "answerable": "yes", "route": None, "route_info": None,
                           "citations": r["citations"], "safety": False, "screen": "활동비 계산"}}

    def screen_node(state: ChatState) -> ChatState:
        s = SCREENS[state["intent"]]
        return {"result": {"answer": s["message"], "screen": s["screen"], "form_id": s["form_id"],
                           "required_inputs": list(required_inputs(s["form_id"]))}}

    g = StateGraph(ChatState)
    g.add_node("guard", guard_node)
    g.add_node("classify", classify_node)
    g.add_node("safety", safety_node)
    g.add_node("qa", qa_node)
    g.add_node("screen", screen_node)
    g.add_node("calc", calc_node)
    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", lambda s: "safety" if s.get("intent") == "safety" else "classify",
                            {"safety": "safety", "classify": "classify"})
    g.add_conditional_edges("classify", lambda s: s["intent"] if s["intent"] in ("qa", "calc") else "screen",
                            {"qa": "qa", "calc": "calc", "screen": "screen"})
    for node in ("safety", "qa", "screen", "calc"):
        g.add_edge(node, END)
    return g.compile()

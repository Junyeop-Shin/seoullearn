"""의도 분류 정확도를 잰다.

  python -m evaluation.intent_eval              규칙만 (LLM 호출 없음). 규칙으로 못 가른 문항은 '미분류'로 센다
  python -m evaluation.intent_eval --llm        규칙으로 못 가른 문항만 LLM에 묻는다
결과: eval/runs/intent_eval[_llm].json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app import guard
from app.config import settings
from app.llm import ChatLLM, get_chat_model
from app.router import classify_by_llm, classify_by_rule


def classify(message: str, llm: ChatLLM | None) -> dict:
    """라우터 그래프와 같은 순서: 가드 → 규칙 → (애매하면) LLM."""
    g = guard.check(message)
    if g.safety:
        return {"pred": "safety", "method": "guard", "error": None}
    intent = classify_by_rule(g.text)
    if intent:
        return {"pred": intent, "method": "rule", "error": None}
    if llm is None:
        return {"pred": None, "method": "unresolved", "error": None}
    intent, err = classify_by_llm(g.text, llm)
    return {"pred": intent, "method": "llm", "error": err}


def evaluate(items: list[dict], llm: ChatLLM | None = None) -> dict:
    recs = [{**it, **classify(it["message"], llm)} for it in items]
    n = len(recs)
    by_method = Counter(r["method"] for r in recs)
    decided = [r for r in recs if r["method"] in ("guard", "rule")]
    per_intent = {}
    for intent in sorted({r["intent"] for r in recs}):
        rs = [r for r in recs if r["intent"] == intent]
        per_intent[intent] = {"n": len(rs), "correct": sum(r["pred"] == r["intent"] for r in rs)}
    return {
        "n": n,
        "accuracy": round(100 * sum(r["pred"] == r["intent"] for r in recs) / n, 1),
        "by_method": dict(by_method),
        "llm_calls": by_method.get("llm", 0),
        # 규칙·가드가 스스로 정한 문항만의 정확도. 규칙이 자신 있게 틀리는지 본다
        "rule_decided_n": len(decided),
        "rule_decided_accuracy": round(100 * sum(r["pred"] == r["intent"] for r in decided) / max(len(decided), 1), 1),
        "llm_format_errors": sum(bool(r["error"]) for r in recs),
        "per_intent": per_intent,
        "wrong": [{"id": r["id"], "intent": r["intent"], "pred": r["pred"], "method": r["method"]} for r in recs
                  if r["pred"] != r["intent"]],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--llm", action="store_true", help="규칙으로 못 가른 문항을 LLM에 묻는다")
    p.add_argument("--set", type=Path, default=settings.root / "eval" / "intent_set.json")
    a = p.parse_args()
    items = json.loads(a.set.read_text(encoding="utf-8"))["items"]
    llm = get_chat_model("answer") if a.llm else None
    s = evaluate(items, llm)
    s["llm"] = llm.name if llm else None
    out = settings.root / "eval" / "runs" / f"intent_eval{'_llm' if a.llm else ''}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False, indent=2))
    print(f"저장: {out}")


if __name__ == "__main__":
    main()

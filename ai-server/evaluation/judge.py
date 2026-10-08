"""LLM 채점. 예측 답변을 평가셋 정답과 비교해 0~2점을 매긴다.

채점 모델(JUDGE_MODEL)은 개선 전후를 비교하는 동안 바꾸지 않는다.
일부는 사람이 직접 채점해 이 점수가 믿을 만한지 확인한다 (eval/human_check.csv).

  python -m evaluation.judge eval/runs/<결과>.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.llm import get_eval_model

from .metrics import summarize

SYSTEM = """너는 서울런 멘토 Q&A 답변을 채점한다. [정답]을 기준으로 [예측]을 평가한다.

score:
- 2: 정답의 핵심 사실(숫자, 기한, 절차, 문의처)이 모두 맞고 틀린 내용이 없다.
- 1: 핵심 일부만 맞거나 중요한 조건이 빠졌다. 틀린 내용은 없다.
- 0: 핵심이 틀렸거나, 정답과 모순되거나, 답할 수 없는 질문에 단정적으로 답했다.
unsupported: 정답에도 없고 일반 상식도 아닌 구체적 사실(숫자, 날짜, 규정)을 새로 지어냈으면 true.
표현 방식이나 길이는 점수에 반영하지 않는다.

JSON 한 개만 출력: {"score": 0, "unsupported": false, "reason": "한 문장"}"""


def judge_record(llm, r: dict) -> dict:
    user = (f"[질문]\n{r['question']}\n\n[정답] (답변 가능: {r['gold']['answerable']}, 문의처: {r['gold']['route']})\n"
            f"{r['gold']['answer']}\n\n[예측] (답변 가능: {r['pred']['answerable']}, 문의처: {r['pred']['route']})\n{r['pred']['answer']}")
    raw = llm.complete(SYSTEM, user)
    try:
        import re

        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        return {"score": int(data["score"]), "unsupported": bool(data.get("unsupported")), "reason": data.get("reason", "")}
    except Exception as e:
        return {"score": None, "error": f"{type(e).__name__}: {e}", "raw": raw}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run_file", type=Path)
    a = p.parse_args()
    llm = get_eval_model("judge")
    lines = [json.loads(x) for x in a.run_file.read_text(encoding="utf-8").splitlines() if x.strip()]
    for n, r in enumerate(lines, 1):
        if r.get("pred") and not r.get("judge"):
            r["judge"] = judge_record(llm, r)
            r["judge"]["model"] = llm.name
        print(f"\r{n}/{len(lines)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    out = a.run_file.with_name(a.run_file.stem + "_judged.jsonl")
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in lines), encoding="utf-8")
    summary_path = a.run_file.with_suffix(".summary.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    summary.update(summarize(lines, summary.get("k", 5)))
    summary["judge_model"] = llm.name
    out.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary.get("judge"), ensure_ascii=False))
    print(f"저장: {out}")


if __name__ == "__main__":
    main()

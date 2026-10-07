"""여러 평가 결과를 한 표로 비교한다.

  python -m evaluation.report eval/runs/*.summary.json
결과: eval/reports/compare.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import settings

COLS = [
    ("검색 hit@1", ("retrieval", "hit@1")), ("검색 hit@3", ("retrieval", "hit@3")), ("검색 hit@k", ("retrieval", "hit@k")),
    ("MRR", ("retrieval", "mrr")), ("답변가능 판단", ("answer", "answerable_acc")), ("지어내기↓", ("answer", "fabrication_rate")),
    ("과잉거절↓", ("answer", "over_refusal_rate")), ("문의처", ("answer", "route_acc")),
    ("인용 정확도", ("answer", "citation_precision")), ("안전 연결", ("answer", "safety_route_ok")),
    ("채점 평균(0~2)", ("judge", "correctness_avg_0to2")), ("완전 정답", ("judge", "fully_correct")),
]


def get(s: dict, path: tuple[str, str]):
    sec, key = path
    d = s.get(sec) or {}
    if key == "hit@k":
        key = f"hit@{s.get('k', 5)}"
    v = d.get(key)
    return "-" if v is None else v


def main():
    p = argparse.ArgumentParser()
    p.add_argument("summaries", nargs="+", type=Path)
    a = p.parse_args()
    rows = [json.loads(x.read_text(encoding="utf-8")) for x in a.summaries]
    rows.sort(key=lambda s: s.get("created", ""))
    head = "| 설정 | 임베딩 | 코퍼스 | LLM | " + " | ".join(c for c, _ in COLS) + " |"
    lines = ["# RAG 평가 비교", "", "백분율(%)은 높을수록 좋고, ↓ 표시는 낮을수록 좋다.", "", head,
             "|" + " --- |" * (len(COLS) + 4)]
    for s in rows:
        emb = (s.get("embedding") or "-").split(":")[-1].split("/")[-1]
        lines.append(f"| {s['config']} | {emb} | {s['corpus']} | {s.get('llm') or '검색만'} | "
                     + " | ".join(str(get(s, path)) for _, path in COLS) + " |")
    lines += ["", "## 설정 설명", ""] + sorted({f"- **{s['config']}**: {s.get('description', '')}" for s in rows})
    out = settings.root / "eval" / "reports" / "compare.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n저장: {out}")


if __name__ == "__main__":
    main()

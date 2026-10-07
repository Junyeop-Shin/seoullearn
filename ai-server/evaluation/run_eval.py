"""평가 실행.

예)
  검색만 측정 (LLM 호출 없음, 무료 한도 안 씀)
    python -m evaluation.run_eval --config md_hybrid --corpus v1 --retrieval-only
  답변까지 측정
    python -m evaluation.run_eval --config md_hybrid --corpus v1
  전체 흐름 점검 (가짜 LLM)
    python -m evaluation.run_eval --config md_bm25 --fake-llm --limit 5

결과: eval/runs/<시각>_<config>_<corpus>.jsonl 과 .summary.json
"""
from __future__ import annotations

import argparse
import re
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app import qa
from app.config import settings
from app.llm import get_chat_model, get_embedder
from app.pipelines import CONFIGS, build_retriever
from app.retrieval import get_reranker

from .metrics import evidence_match, gold_ranks, summarize


class FakeLLM:
    """네트워크 없이 흐름만 확인하는 가짜 모델. 1번 자료를 근거로 '답할 수 있음'이라고 답한다."""

    name = "fake"

    def complete(self, system: str, user: str) -> str:
        return json.dumps({"answerable": "yes", "answer": "(가짜 답변)", "citations": [1], "route": None}, ensure_ascii=False)


def _embedder_name(r) -> str | None:
    if hasattr(r, "embedder"):
        return r.embedder.name
    for child in [getattr(r, "inner", None), *getattr(r, "retrievers", [])]:
        if child is not None and (name := _embedder_name(child)):
            return name
    return None


def load_items(path: Path, corpus: str, ids: set[str] | None, limit: int | None):
    data = json.loads(path.read_text(encoding="utf-8"))["items"]
    if ids:
        data = [it for it in data if it["id"] in ids]
    if limit:
        data = data[:limit]
    for it in data:
        gold = it["v1"] if corpus == "v1" or it["v2"] is None else it["v2"]
        yield it, gold


def run(config: str, corpus: str, retrieval_only: bool = False, fake_llm: bool = False, limit: int | None = None,
        ids: set[str] | None = None, embedder=None, out_dir: Path | None = None, k: int | None = None,
        note: str = "", reranker=None) -> tuple[Path, dict]:
    k = k or settings.top_k
    retriever, chunks = build_retriever(config, corpus, embedder=embedder, reranker=reranker)
    by_id = {c.id: c for c in chunks}
    llm = None if retrieval_only else (FakeLLM() if fake_llm else get_chat_model("answer"))
    out_dir = out_dir or settings.root / "eval" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    emb = _embedder_name(retriever)
    emb_tag = f"_{re.sub(r'[^A-Za-z0-9.-]+', '-', emb.split('/')[-1])}" if emb else ""
    out = out_dir / f"{stamp}_{config}{emb_tag}_{corpus}{'_retrieval' if retrieval_only else ''}.jsonl"

    records = []
    items = list(load_items(settings.root / "eval" / "eval_set.json", corpus, ids, limit))
    for n, (it, gold) in enumerate(items, 1):
        rec = {"id": it["id"], "question": it["question"], "category": it["category"], "origin": it["origin"],
               "type": it["type"], "gold": gold}
        if retrieval_only:
            hits = [c for c, _ in retriever.search(qa.guard.check(it["question"]).text, k)]
            rec["retrieved"] = [c.id for c in hits]
        else:
            res = qa.answer(it["question"], retriever, llm, k)
            hits = [by_id[i] for i in res.retrieved]
            rec["retrieved"] = res.retrieved
            rec["pred"] = res.to_dict()
            rec["cite_ok"] = [any(evidence_match(by_id[c], ev) for ev in gold["evidence"]) for c in res.citations]
        rec["ranks"] = gold_ranks(hits, gold["evidence"])
        records.append(rec)
        print(f"\r{n}/{len(items)} {it['id']}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = {
        "config": config, "description": CONFIGS[config].description, "corpus": corpus, "k": k,
        "retrieval_only": retrieval_only, "llm": None if llm is None else llm.name,
        "embedding": _embedder_name(retriever),
        "reranker": getattr(getattr(retriever, "reranker", None), "name", None),
        "chunks": len(chunks), "created": stamp, "note": note, **summarize(records, k),
    }
    out.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return out, summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="md_hybrid", choices=list(CONFIGS))
    p.add_argument("--corpus", default="v1", choices=["v1", "v2"])
    p.add_argument("--retrieval-only", action="store_true")
    p.add_argument("--fake-llm", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--ids", help="쉼표로 구분한 문항 ID (예: Q023,Q024)")
    p.add_argument("--k", type=int)
    p.add_argument("--embedding-model", help="이번 실행만 임베딩 모델 바꾸기 (예: BAAI/bge-m3)")
    p.add_argument("--embedding-provider", choices=["local", "gemini", "hash"])
    p.add_argument("--reranker-model", help="이번 실행만 리랭커 모델 바꾸기 (rerank 설정에서만 쓰인다)")
    p.add_argument("--note", default="", help="비교표에 적을 메모 (예: 가드 수정 후)")
    a = p.parse_args()
    t0 = time.time()
    embedder = None
    if a.embedding_model or a.embedding_provider:
        embedder = get_embedder(a.embedding_provider, a.embedding_model)
    out, s = run(a.config, a.corpus, a.retrieval_only, a.fake_llm, a.limit, set(a.ids.split(",")) if a.ids else None,
                 embedder=embedder, k=a.k, note=a.note,
                 reranker=get_reranker(a.reranker_model) if a.reranker_model else None)
    print(json.dumps({k: v for k, v in s.items() if k != "by_category"}, ensure_ascii=False, indent=2))
    print(f"저장: {out}  ({time.time() - t0:.0f}초)")


if __name__ == "__main__":
    main()

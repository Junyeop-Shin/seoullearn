"""임베딩 모델 하나의 검색 품질과 비용(색인 시간, 검색 시간, 메모리)을 잰다. LLM 호출 없음.

  python -m evaluation.embedding_bench --embedding-model BAAI/bge-m3
결과: eval/runs/embedding_bench_<모델>.json

메모리는 프로세스 최대값이라 모델마다 따로 실행해야 한다 (한 번에 한 모델).
"""
from __future__ import annotations

import argparse
import json
import re
import resource
import sys
import time
from pathlib import Path

from app import qa
from app.config import settings
from app.llm import Embedder, get_embedder
from app.pipelines import build_retriever

from .run_eval import load_items, run

CONFIGS = ["md_vector", "md_hybrid"]


def peak_memory_mb() -> dict:
    """컨테이너(cgroup) 최대 메모리와 프로세스 최대 RSS. cgroup 값은 컨테이너 밖에서는 없을 수 있다."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = rss / 1024 / 1024 if sys.platform == "darwin" else rss / 1024  # macOS는 바이트, 리눅스는 KB
    out = {"process_peak_rss_mb": round(rss_mb), "container_peak_mb": None}
    peak = Path("/sys/fs/cgroup/memory.peak")
    if peak.exists():
        out["container_peak_mb"] = round(int(peak.read_text().strip()) / 1024 / 1024)
    return out


def bench(embedder: Embedder, corpus: str = "v1", out_dir: Path | None = None, limit: int | None = None,
          load_seconds: float | None = None) -> dict:
    result: dict = {"embedding": embedder.name, "corpus": corpus, "model_load_seconds": load_seconds, "configs": {}}
    questions = [qa.guard.check(it["question"]).text
                 for it, _ in load_items(settings.root / "eval" / "eval_set.json", corpus, None, limit)]
    for config in CONFIGS:
        retriever, chunks = build_retriever(config, corpus, embedder=embedder, vector_backend="file")
        if "index_seconds" not in result:
            # 색인 캐시(.cache/index_*.npy)를 거치지 않고 청크 전체를 직접 임베딩해 잰다
            t0 = time.perf_counter()
            embedder.embed([c.text for c in chunks])
            result["index_seconds"] = round(time.perf_counter() - t0, 2)
            result["chunks"] = len(chunks)
        t0 = time.perf_counter()
        for q in questions:
            retriever.search(q, settings.top_k)
        search_ms = 1000 * (time.perf_counter() - t0) / max(len(questions), 1)
        _, summary = run(config, corpus, retrieval_only=True, embedder=embedder, out_dir=out_dir, limit=limit)
        result["configs"][config] = {"search_ms_per_query": round(search_ms, 1), "questions": len(questions),
                                     **summary["retrieval"]}
    result.update(peak_memory_mb())
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--embedding-model", required=True)
    p.add_argument("--embedding-provider", default="local", choices=["local", "gemini", "hash"])
    p.add_argument("--corpus", default="v1", choices=["v1", "v2"])
    a = p.parse_args()
    t0 = time.perf_counter()
    embedder = get_embedder(a.embedding_provider, a.embedding_model)
    load = round(time.perf_counter() - t0, 2)  # 처음 실행이면 내려받는 시간이 섞인다
    result = bench(embedder, a.corpus, load_seconds=load)
    out_dir = settings.root / "eval" / "runs"
    out = out_dir / f"embedding_bench_{re.sub(r'[^A-Za-z0-9.-]+', '-', a.embedding_model.split('/')[-1])}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"저장: {out}")


if __name__ == "__main__":
    main()

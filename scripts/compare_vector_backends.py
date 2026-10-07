"""pgvector와 file 방식의 벡터 검색 결과가 같은지 평가셋 질문으로 비교한다. LLM 호출 없음.

  docker compose run --rm ai-server python /project/scripts/compare_vector_backends.py [--corpus v1|v2]
순위가 하나라도 다르면 종료 코드 1.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai-server"))

from app import guard  # noqa: E402
from app.config import settings  # noqa: E402
from app.corpus import load_markdown  # noqa: E402
from app.llm import get_embedder  # noqa: E402
from app.retrieval import VectorRetriever  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", default="v2", choices=["v1", "v2"])
    p.add_argument("--k", type=int, default=settings.top_k)
    a = p.parse_args()
    chunks, embedder = load_markdown(a.corpus), get_embedder()
    file = VectorRetriever(chunks, embedder, backend="file")
    pg = VectorRetriever(chunks, embedder, backend="pgvector")
    items = json.loads((settings.root / "eval" / "eval_set.json").read_text(encoding="utf-8"))["items"]
    diff, max_gap = [], 0.0
    for it in items:
        q = guard.check(it["question"]).text
        f, g = file.search(q, a.k), pg.search(q, a.k)
        max_gap = max([max_gap] + [abs(x[1] - y[1]) for x, y in zip(f, g)])
        if [c.id for c, _ in f] != [c.id for c, _ in g]:
            diff.append(it["id"])
    print(f"코퍼스 {a.corpus}, 청크 {len(chunks)}개, 질문 {len(items)}개, 상위 {a.k}개 비교")
    print(f"순위가 다른 문항: {len(diff)}개 {diff}")
    print(f"같은 순위의 점수 차이 최대: {max_gap:.6f}")
    return 1 if diff else 0


if __name__ == "__main__":
    sys.exit(main())

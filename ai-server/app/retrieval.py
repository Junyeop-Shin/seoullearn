"""검색기: 벡터, BM25, 하이브리드(RRF), 용어집 질의 확장."""
from __future__ import annotations

import csv
import hashlib
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

from .config import settings
from .corpus import Chunk
from .llm import Embedder

_WORD = re.compile(r"[가-힣]+|[a-zA-Z]+|\d+(?:[.,]\d+)*")


def tokenize(text: str) -> list[str]:
    """형태소 분석기 없이 쓰는 한국어 토큰화: 어절 + 한글 2글자 조각."""
    out = []
    for w in _WORD.findall(text.lower()):
        out.append(w)
        if re.fullmatch(r"[가-힣]+", w) and len(w) > 2:
            out.extend(w[i : i + 2] for i in range(len(w) - 1))
    return out


class BM25Retriever:
    name = "bm25"

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.docs = [tokenize(c.text) for c in chunks]
        self.tf = [Counter(d) for d in self.docs]
        self.avgdl = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        q = tokenize(query)
        scores = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            scores.append(s)
        order = np.argsort(scores)[::-1][:k]
        return [(self.chunks[i], float(scores[i])) for i in order]


class VectorRetriever:
    name = "vector"

    def __init__(self, chunks: list[Chunk], embedder: Embedder):
        self.chunks, self.embedder = chunks, embedder
        self.matrix = self._load_or_build()

    def _load_or_build(self) -> np.ndarray:
        h = hashlib.sha256(("\x1e".join(c.text for c in self.chunks) + self.embedder.name).encode()).hexdigest()[:16]
        path: Path = settings.cache_dir / f"index_{h}.npy"
        if path.exists():
            return np.load(path)
        m = self.embedder.embed([c.text for c in self.chunks])
        np.save(path, m)
        return m

    def search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        q = self.embedder.embed_query(query)
        scores = self.matrix @ q
        order = np.argsort(scores)[::-1][:k]
        return [(self.chunks[i], float(scores[i])) for i in order]


class HybridRetriever:
    """Reciprocal Rank Fusion. 점수 척도가 다른 두 검색기를 순위로 합친다."""

    name = "hybrid"

    def __init__(self, retrievers: list, pool: int = 20, rrf_k: int = 60):
        self.retrievers, self.pool, self.rrf_k = retrievers, pool, rrf_k

    def search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        scores: dict[str, float] = {}
        by_id: dict[str, Chunk] = {}
        for r in self.retrievers:
            for rank, (c, _) in enumerate(r.search(query, self.pool)):
                scores[c.id] = scores.get(c.id, 0.0) + 1.0 / (self.rrf_k + rank + 1)
                by_id[c.id] = c
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
        return [(by_id[i], s) for i, s in top]


class GlossaryExpander:
    """멘토가 쓰는 표현을 공식 용어로 보강한다. 예: 주간보고서 → 활동보고서."""

    def __init__(self, path: Path | None = None):
        path = path or settings.data_dir / "glossary.csv"
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.pairs = sorted(((r["user_term"], r["official_term"]) for r in rows), key=lambda x: -len(x[0]))

    def expand(self, query: str) -> str:
        extra = [off for user, off in self.pairs if user in query and off not in query]
        return query + (" " + " ".join(dict.fromkeys(extra)) if extra else "")


class ExpandingRetriever:
    def __init__(self, inner, expander: GlossaryExpander):
        self.inner, self.expander = inner, expander
        self.name = f"{inner.name}+glossary"

    def search(self, query: str, k: int):
        return self.inner.search(self.expander.expand(query), k)

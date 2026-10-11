"""RAG 실험 공통 도구. 저장소 코드는 고치지 않고 감싸서 쓴다. LLM 호출 없음."""
import sys

sys.path.insert(0, ".")
import dataclasses
import math
import re
from collections import Counter

import numpy as np

from app import guard
from app.config import settings
from app.corpus import front_matter, load_markdown
from app.llm import get_embedder
from app.retrieval import BM25Retriever, GlossaryExpander, VectorRetriever, tokenize
from evaluation.metrics import gold_ranks, summarize
from evaluation.run_eval import load_items

K = 5
_EMB = None
EXP = GlossaryExpander()


def emb():
    global _EMB
    if _EMB is None:
        _EMB = get_embedder()
    return _EMB


def items(corpus):
    return list(load_items(settings.root / "eval" / "eval_set.json", corpus, None, None))


def prep(q):
    """서비스와 같은 순서: 가드 → 용어집 보강."""
    return EXP.expand(guard.check(q).text)


def doc_meta():
    """doc_id → 머리말 (aliases, related, supersedes ...)."""
    out = {}
    for folder in ("manual", "notice"):
        for f in sorted((settings.data_dir / folder).glob("*.md")):
            fm, _ = front_matter(f.read_text(encoding="utf-8"))
            out[fm["doc_id"]] = fm
    return out


class Ranker:
    """검색기를 감싸 질의마다 전체 순위(청크 id)와 점수를 기억한다."""

    def __init__(self, retriever, n):
        self.r, self.n, self.cache = retriever, n, {}

    def full(self, q):
        if q not in self.cache:
            self.cache[q] = [(c.id, s) for c, s in self.r.search(q, self.n)]
        return self.cache[q]

    def rank(self, q):
        return [i for i, _ in self.full(q)]


def fuse(lists, weights=None, pool=20, rrf_k=60):
    """HybridRetriever.search 와 같은 계산(같은 동점 처리). 전체 순위를 돌려준다."""
    weights = weights or [1.0] * len(lists)
    scores = {}
    for lst, w in zip(lists, weights):
        for rank, cid in enumerate(lst[:pool]):
            scores[cid] = scores.get(cid, 0.0) + w / (rrf_k + rank + 1)
    return [i for i, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


class Bench:
    def __init__(self, corpus, vec_chunks=None, bm_chunks=None, bm_cls=BM25Retriever, **bm_kw):
        self.corpus = corpus
        self.chunks = load_markdown(corpus)
        self.by_id = {c.id: c for c in self.chunks}
        n = len(self.chunks)
        self.vec = Ranker(VectorRetriever(vec_chunks or self.chunks, emb(), backend="file"), n)
        self.bm = Ranker(bm_cls(bm_chunks or self.chunks, **bm_kw), n)
        self.items = items(corpus)

    def base(self, q, **kw):
        return fuse([self.vec.rank(q), self.bm.rank(q)], **kw)

    def run(self, fn=None, k=K):
        """fn(질의, bench) → 청크 id 순위. 기록은 run_eval 과 같은 모양."""
        fn = fn or (lambda q, b: b.base(q))
        recs = []
        for it, gold in self.items:
            ids = fn(prep(it["question"]), self)[:k]
            hits = [self.by_id[i] for i in ids]
            recs.append({"id": it["id"], "gold": gold, "retrieved": ids, "ranks": gold_ranks(hits, gold["evidence"])})
        return recs


def odd(r):
    return int(r["id"][1:]) % 2 == 1


def line(recs, k=K):
    def one(rs):
        s = summarize(rs, k)["retrieval"]
        return f"n={s['n']} h1={s['hit@1']} h3={s['hit@3']} h{k}={s[f'hit@{k}']} r{k}={s[f'recall@{k}']} mrr={s['mrr']}"
    return (f"전체 {one(recs)} | 홀 {one([r for r in recs if odd(r)])} | 짝 {one([r for r in recs if not odd(r)])}")


def best(r):
    xs = [x for x in r["ranks"] if x]
    return min(xs) if xs else None


def diff(a, b, k=K):
    """a(전) → b(후): hit@k, hit@1 이 달라진 문항."""
    out = {"h5+": [], "h5-": [], "h1+": [], "h1-": []}
    for x, y in zip(a, b):
        if not x["gold"]["evidence"]:
            continue
        bx, by = best(x), best(y)
        hx, hy = bool(bx and bx <= k), bool(by and by <= k)
        if hy and not hx: out["h5+"].append(x["id"])
        if hx and not hy: out["h5-"].append(x["id"])
        if by == 1 and bx != 1: out["h1+"].append(x["id"])
        if bx == 1 and by != 1: out["h1-"].append(x["id"])
    return " ".join(f"{k_}:{','.join(v) or '-'}" for k_, v in out.items())


def report(name, base, recs, k=K):
    print(f"## {name}\n   {line(recs, k)}\n   변화 {diff(base, recs, k)}", flush=True)


class BM25X:
    """BM25Retriever 와 같은 식. 토큰화 함수와 k1, b 를 바꿔 볼 수 있다."""

    name = "bm25x"

    def __init__(self, chunks, tok=tokenize, k1=1.5, b=0.75, text=lambda c: c.text):
        self.chunks, self.tok = chunks, tok
        self.docs = [tok(text(c)) for c in chunks]
        self.tf = [Counter(d) for d in self.docs]
        self.avgdl = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.k1, self.b = k1, b

    def search(self, query, k):
        q = self.tok(query)
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


def with_text(chunks, fn):
    return [dataclasses.replace(c, text=fn(c)) for c in chunks]

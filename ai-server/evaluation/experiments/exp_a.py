"""기준선, aliases, BM25 변형, RRF 격자. LLM 호출 없음."""
import sys

from common import *  # noqa
import itertools
import time

from app.pipelines import build_retriever
from evaluation.run_eval import run as _  # noqa: F401  (import 확인용)

META = doc_meta()
ONLY = sys.argv[1:] or ["base", "alias", "bm25", "rrf"]

for corpus in ("v1", "v2"):
    print(f"\n==================== {corpus}", flush=True)
    B = Bench(corpus)
    base = B.run()
    print(f"청크 {len(B.chunks)}개, 평균 {sum(len(c.text) for c in B.chunks) / len(B.chunks):.0f}자")
    print("기준선(재구현)   ", line(base))

    if "base" in ONLY:
        # 저장소의 실제 검색기로 잰 값과 같은지 확인
        real, _chunks = build_retriever("md_hybrid_glossary", corpus, embedder=emb(), vector_backend="file")
        t0 = time.time()
        recs = []
        for it, gold in B.items:
            hits = [c for c, _ in real.search(guard.check(it["question"]).text, K)]
            recs.append({"id": it["id"], "gold": gold, "retrieved": [c.id for c in hits], "ranks": gold_ranks(hits, gold["evidence"])})
        dt = (time.time() - t0) / len(B.items) * 1000
        print("기준선(저장소)   ", line(recs), f"| 질문당 {dt:.0f}ms")
        print("   상위5 동일:", all(a["retrieved"] == b["retrieved"] for a, b in zip(base, recs)))
        print("   hit@5 실패:", [(r["id"], r["ranks"]) for r in base if r["gold"]["evidence"] and not (best(r) and best(r) <= K)])
        v = summarize([r for r in B.run(lambda q, b: b.vec.rank(q))], K)["retrieval"]
        m = summarize([r for r in B.run(lambda q, b: b.bm.rank(q))], K)["retrieval"]
        print("   벡터만", v, "\n   BM25만", m)

    if "alias" in ONLY:
        al = lambda c: " ".join(META[c.doc_id].get("aliases") or [])
        tail = with_text(B.chunks, lambda c: c.text + "\n" + al(c))
        head = with_text(B.chunks, lambda c: c.text.replace("]\n", f"] ({', '.join(META[c.doc_id].get('aliases') or [])})\n", 1))
        b1 = Bench(corpus, bm_chunks=tail)
        report("1a aliases → BM25에만", base, b1.run())
        b2 = Bench(corpus, vec_chunks=tail, bm_chunks=tail)
        report("1b aliases → BM25 + 임베딩 (청크 끝에)", base, b2.run())
        b3 = Bench(corpus, vec_chunks=head, bm_chunks=head)
        report("1c aliases → BM25 + 임베딩 (제목 줄에)", base, b3.run())
        b4 = Bench(corpus, vec_chunks=tail)
        report("1d aliases → 임베딩에만", base, b4.run())

    if "bm25" in ONLY:
        W = re.compile(r"[가-힣]+|[a-zA-Z]+|\d+(?:[.,]\d+)*")
        JOSA = re.compile(r"(으로부터|에서는|에게서|이라고|이에요|이예요|으로는|까지는|부터는|에서|에게|한테|으로|까지|부터|이랑|이나|이라|처럼|보다|예요|은|는|이|가|을|를|에|의|로|와|과|도|만|랑|나)$")

        def tok_ng(ns, words=True, josa=False):
            def f(text):
                out = []
                for w in W.findall(text.lower()):
                    han = re.fullmatch(r"[가-힣]+", w)
                    if josa and han and len(w) > 2:
                        w2 = JOSA.sub("", w)
                        w = w2 if len(w2) >= 2 else w
                    if words:
                        out.append(w)
                    if han:
                        for n in ns:
                            if len(w) > n:
                                out.extend(w[i:i + n] for i in range(len(w) - n + 1))
                            elif not words and len(w) == n:
                                out.append(w)
                return out
            return f

        def bm(name, **kw):
            b = Bench(corpus, bm_cls=BM25X, **kw)
            recs = b.run()
            report(name, base, recs)
            s = summarize(b.run(lambda q, bb: bb.bm.rank(q)), K)["retrieval"]
            print(f"      (BM25 단독 h1={s['hit@1']} h5={s['hit@5']} mrr={s['mrr']})")

        bm("5-0 확인: BM25X 기본값 (기준선과 같아야 함)")
        bm("5a 조사 떼기 + 어절 + 2글자", tok=tok_ng([2], josa=True))
        bm("5b 어절 + 2글자 + 3글자", tok=tok_ng([2, 3]))
        bm("5c 2글자 조각만 (어절 없음)", tok=tok_ng([2], words=False))
        bm("5d 어절 + 3글자", tok=tok_ng([3]))
        hdr = lambda n: (lambda c: (c.text.split("\n", 1)[0] + "\n") * n + c.text)
        bm("5e 제목·소제목 2번 더 (가중 3배)", text=hdr(2))
        bm("5f 제목·소제목 1번 더 (가중 2배)", text=hdr(1))
        bm("5g k1=1.2 b=0.5", k1=1.2, b=0.5)
        bm("5h k1=0.9 b=0.4", k1=0.9, b=0.4)
        bm("5i k1=2.0 b=0.9", k1=2.0, b=0.9)

    if "rrf" in ONLY:
        grid = []
        for wb, pool, rk in itertools.product([0.3, 0.5, 0.7, 1.0, 1.5, 2.0], [10, 20, 40, 200], [10, 30, 60, 100]):
            recs = B.run(lambda q, b: fuse([b.vec.rank(q), b.bm.rank(q)], [1.0, wb], pool, rk))
            so = summarize([r for r in recs if odd(r)], K)["retrieval"]
            se = summarize([r for r in recs if not odd(r)], K)["retrieval"]
            grid.append(((wb, pool, rk), so, se, recs))
        key = lambda s: (s["hit@5"], s["mrr"])
        print("## 4 RRF 격자 (BM25 가중치, pool, k) 96가지. 홀수 기준 상위 5:")
        for p, so, se, recs in sorted(grid, key=lambda g: key(g[1]), reverse=True)[:5]:
            print(f"   {p}  홀 h1={so['hit@1']} h5={so['hit@5']} mrr={so['mrr']} | 짝 h1={se['hit@1']} h5={se['hit@5']} mrr={se['mrr']}")
        p, so, se, recs = max(grid, key=lambda g: key(g[1]))
        report(f"4 홀수로 고른 값 {p}", base, recs)
        cur = next(g for g in grid if g[0] == (1.0, 20, 60))
        print(f"   지금 값 (1.0,20,60) 홀 h5={cur[1]['hit@5']} mrr={cur[1]['mrr']} | 짝 h5={cur[2]['hit@5']} mrr={cur[2]['mrr']}")
        eh = sorted({(g[2]["hit@5"], g[2]["mrr"]) for g in grid})
        print(f"   짝수에서 격자 전체 범위: h5 {eh[0][0]}~{eh[-1][0]}, mrr {min(g[2]['mrr'] for g in grid)}~{max(g[2]['mrr'] for g in grid)}")
        print(f"   홀수에서 격자 전체 범위: h5 {min(g[1]['hit@5'] for g in grid)}~{max(g[1]['hit@5'] for g in grid)}, mrr {min(g[1]['mrr'] for g in grid)}~{max(g[1]['mrr'] for g in grid)}")

"""공지 우선(순서 바꾸기) 자세히 보기, 후보들의 '서비스에서 검색을 타는 문항' 기준 재확인. LLM 호출 없음."""

from common import *  # noqa
from app import allowance

META = doc_meta()
SUP = {d: m["supersedes"] for d, m in META.items() if m.get("supersedes") and m.get("status", "active") == "active"}
B = Bench("v2")
base = B.run()
SQ = ["Q028", "Q051", "Q052", "Q053", "Q054", "Q055", "Q056", "Q057"]
lab = lambda i: f"{i.replace('manual-2026-', 'M').replace('notice-2026-', '')}({B.by_id[i].heading[:10]})"


def notice_first(n_pull=0, grow=False):
    """상위 5개 안에 대체된 활동가이드 청크가 있으면, 그 공지의 청크를 그 앞으로 옮긴다.
    n_pull > 0 이면 5개 밖(합친 순위 40위까지)에 있는 그 공지의 청크도 n_pull개까지 끌어온다."""
    def fn(q, b):
        full = b.base(q)
        top = full[:K]
        for nd, olds in SUP.items():
            if not any(b.by_id[i].doc_id in olds for i in top):
                continue
            extra = [i for i in full[K:] if b.by_id[i].doc_id == nd][:n_pull]
            notice = [i for i in top if b.by_id[i].doc_id == nd] + extra
            if not notice:
                continue
            rest = [i for i in top if i not in notice]
            at = next(n for n, i in enumerate(rest) if b.by_id[i].doc_id in olds)
            top = rest[:at] + notice + rest[at:]
            if not grow:
                top = top[:K]
        return top
    return fn


def first_pos(ids, pred):
    return next((n for n, i in enumerate(ids, 1) if pred(i)), None)


print("공지가 바꾼 8문항: 기준선 상위 5개와 정답")
for (it, gold), r in zip(B.items, base):
    if it["id"] in SQ:
        print(f" {it['id']} {it['question']}\n    정답: {gold['answer'][:110]}\n    상위5: {[lab(i) for i in r['retrieved']]}")
        full = B.base(prep(it["question"]))
        nd = next(ev.partition(':')[0] for ev in gold["evidence"] if ev.partition(':')[0] in SUP)
        print(f"    그 공지 청크의 합친 순위: {[(n, lab(i)) for n, i in enumerate(full, 1) if B.by_id[i].doc_id == nd][:6]}")

for name, fn, k in [("2g 순서만: 5개 안의 공지 청크를 대체된 가이드 청크 앞으로", notice_first(0), 5),
                    ("2h 공지 청크 1개 더 끌어와 앞에 (5개 유지, 뒤가 밀려남)", notice_first(1), 5),
                    ("2i 공지 청크 2개 더 끌어와 앞에 (5개 유지)", notice_first(2), 5),
                    ("2j 공지 청크 2개 더 끌어와 앞에 (늘림, 최대 7개)", notice_first(2, True), 7)]:
    recs = B.run(fn, k=k)
    print(f"## {name}\n   {line(recs, 5)}")
    changed = [a["id"] for a, b_ in zip(base, recs) if a["retrieved"] != b_["retrieved"]]
    print(f"   바뀐 질문 {len(changed)}개: 8문항 안 {[c for c in changed if c in SQ]}, 밖 {[c for c in changed if c not in SQ]}")
    print(f"   변화 {diff(base, recs)}")
    is_n = lambda i: B.by_id[i].doc_id in SUP
    is_old = lambda i: any(B.by_id[i].doc_id in olds for olds in SUP.values())
    for a, b_ in zip(base, recs):
        if a["id"] in SQ:
            print(f"     {a['id']} 첫 공지 청크 {first_pos(a['retrieved'], is_n)}→{first_pos(b_['retrieved'], is_n)}위, 공지 청크 수 "
                  f"{sum(map(is_n, a['retrieved']))}→{sum(map(is_n, b_['retrieved']))}, 가이드(대체됨) 청크 수 {sum(map(is_old, a['retrieved']))}→{sum(map(is_old, b_['retrieved']))}"
                  f" | {[lab(i) for i in b_['retrieved']]}")
    lost = [(a["id"], best(a), best(b_)) for a, b_ in zip(base, recs) if a["id"] not in SQ and a["retrieved"] != b_["retrieved"]]
    print("   8문항 밖 (id, 근거 순위 전, 후):", lost)

# ---------------------------------------------------------------- 후보 재확인: 서비스에서 검색을 타는 문항만
print("\n==== 후보 재확인: 안전 가드·금액 계산기로 빠지는 문항(Q001,Q002,Q041,Q045,Q050)을 뺀 값")
for corpus in ("v1", "v2"):
    b0 = Bench(corpus)
    skip = {it["id"] for it, _ in b0.items if guard.check(it["question"]).safety or allowance.is_rate_question(guard.check(it["question"]).text)}
    f = lambda recs: [r for r in recs if r["id"] not in skip]
    r0 = b0.run()
    print(f"-- {corpus} 기준선      {line(f(r0))}")
    al = lambda c: " ".join(META[c.doc_id].get("aliases") or [])
    tail = with_text(b0.chunks, lambda c: c.text + "\n" + al(c))
    b1 = Bench(corpus, vec_chunks=tail, bm_chunks=tail)
    r1 = b1.run()
    print(f"   1b aliases 양쪽  {line(f(r1))}\n      변화 {diff(f(r0), f(r1))}")
    r8 = b0.run(k=8)
    print(f"   상위 8개         {line(f(r8), 8)}")
    r2 = b0.run(lambda q, b: fuse([b.vec.rank(q), b.bm.rank(q)], [1.0, 0.7], 40, 10))
    print(f"   RRF (0.7,40,10)  {line(f(r2))}\n      변화 {diff(f(r0), f(r2))}")
    # 벡터만 (BM25가 지금 자료에서 도움이 되는지)
    rv = b0.run(lambda q, b: b.vec.rank(q))
    print(f"   벡터만           {line(f(rv))}\n      변화 {diff(f(r0), f(rv))}")
    # 용어집 없이
    import common
    recs = []
    for it, gold in b0.items:
        ids = b0.base(guard.check(it["question"]).text)[:K]
        recs.append({"id": it["id"], "gold": gold, "retrieved": ids, "ranks": gold_ranks([b0.by_id[i] for i in ids], gold["evidence"])})
    print(f"   용어집 없이      {line(f(recs))}\n      변화(용어집 없음→있음) {diff(f(recs), f(r0))}")

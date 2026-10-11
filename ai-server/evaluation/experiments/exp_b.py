"""공지 우선, 유형 메타데이터, 답 없음 경계, 이웃 청크, 자체 아이디어. LLM 호출 없음."""
import sys

from common import *  # noqa
from app import allowance

META = doc_meta()
ONLY = sys.argv[1:] or ["n12", "rrf", "notice", "mtype", "thr", "parent", "ideas"]


def ctx_stats(b, recs):
    """상위 묶음의 평균 청크 수, 평균 글자 수."""
    n = [len(r["retrieved"]) for r in recs]
    ch = [sum(len(b.by_id[i].text) for i in r["retrieved"]) for r in recs]
    return f"청크 {sum(n) / len(n):.1f}개, {sum(ch) / len(ch):.0f}자 (최대 {max(ch)})"


def in_ctx(recs):
    """자료 묶음 안에 근거가 하나라도 있는 비율 / 근거를 모두 찾은 비율 / 근거 재현율. 순위와 무관."""
    ev = [r for r in recs if r["gold"]["evidence"]]
    anyhit = sum(any(x for x in r["ranks"]) for r in ev)
    allhit = sum(all(x for x in r["ranks"]) for r in ev)
    rec = sum(sum(1 for x in r["ranks"] if x) / len(r["ranks"]) for r in ev) / len(ev)
    return f"근거 하나 이상 {100 * anyhit / len(ev):.1f}% ({anyhit}/{len(ev)}), 모두 {100 * allhit / len(ev):.1f}%, 재현율 {100 * rec:.1f}%"


for corpus in ("v1", "v2"):
    print(f"\n==================== {corpus}", flush=True)
    B = Bench(corpus)
    base = B.run()
    print("기준선 ", line(base), "|", ctx_stats(B, base))
    served = [r for r, (it, _) in zip(base, B.items)
              if not guard.check(it["question"]).safety and not allowance.is_rate_question(guard.check(it["question"]).text)]
    print(f"서비스에서 실제로 검색을 타는 문항만 (안전 가드·금액 계산기로 빠지는 {len(base) - len(served)}문항 제외): {line(served)}")
    print("   빠지는 문항:", [r["id"] for r in base if r not in served])

    if "n12" in ONLY and corpus == "v2":
        from app.retrieval import BM25Retriever as BM, VectorRetriever as VR
        old = [c for c in B.chunks if c.doc_id != "notice-2026-n12"]
        b = Bench("v2")
        b.vec, b.bm = Ranker(VR(old, emb(), backend="file"), len(old)), Ranker(BM(old), len(old))
        r = b.run()
        report(f"N12 공지를 뺀 예전 자료({len(old)}청크) → 지금: 아래 '변화'는 N12가 들어오며 달라진 문항", r, base)
        print("   N12 없는 자료:", line(r))

    if "rrf" in ONLY:
        for p in [(0.7, 40, 10), (0.7, 20, 10), (1.0, 40, 10), (1.0, 20, 10), (0.7, 40, 60), (1.0, 40, 60), (0.5, 40, 10)]:
            report(f"4 RRF (BM25 가중치, pool, k)={p}", base, B.run(lambda q, b: fuse([b.vec.rank(q), b.bm.rank(q)], [1.0, p[0]], p[1], p[2])))

    if "notice" in ONLY and corpus == "v2":
        sup = {d: m.get("supersedes") or [] for d, m in META.items() if m.get("supersedes") and m.get("status", "active") == "active"}
        rel = {d: m.get("related") or [] for d, m in META.items() if m.get("doc_type") == "notice" and m.get("status", "active") == "active"}
        print("대체 관계:", sup)
        sq = [r["id"] for r in base if any(ev.partition(":")[0] in sup for ev in r["gold"]["evidence"])]
        print("공지가 바꾼 문항:", sq)

        def boost(mode, links, deep=20):
            def fn(q, b):
                full = b.base(q)                      # pool 20씩 합친 순위 (최대 40개)
                top = full[:K]
                docs = {b.by_id[i].doc_id for i in top}
                add = []
                for nd, olds in links.items():
                    if nd in docs or not (set(olds) & docs):
                        continue
                    cand = next((i for i in full[:deep] if b.by_id[i].doc_id == nd), None)
                    if cand is None and deep > 40:    # 합친 순위에 없으면 벡터 순위에서 고른다
                        cand = next(i for i in b.vec.rank(q) if b.by_id[i].doc_id == nd)
                    if cand:
                        add.append((nd, olds, cand))
                if not add:
                    return top
                if mode == "append":                  # 여섯 번째(이후)로 붙임
                    return top + [c for _, _, c in add]
                if mode == "replace":                 # 뒤에서부터 바꿈
                    keep = top[:K - len(add)]
                    return keep + [c for _, _, c in add]
                if mode == "before":                  # 대체된 활동가이드 청크 바로 앞에 끼움 (K개 유지)
                    out = list(top)
                    for _, olds, c in add:
                        at = next(n for n, i in enumerate(out) if b.by_id[i].doc_id in olds)
                        out.insert(at, c)
                    return out[:K]
                if mode == "before+":                 # 끼우고 하나 늘림
                    out = list(top)
                    for _, olds, c in add:
                        at = next(n for n, i in enumerate(out) if b.by_id[i].doc_id in olds)
                        out.insert(at, c)
                    return out
            return fn

        def show(name, fn, k=K):
            recs = B.run(fn, k=k)
            report(name, base, recs, k) if k == K else print(f"## {name}\n   {in_ctx(recs)} | {ctx_stats(B, recs)}")
            fired = sum(a["retrieved"] != b_["retrieved"] for a, b_ in zip(base, recs))
            print(f"   바뀐 질문 {fired}개. 공지가 바꾼 8문항의 근거 순위 전→후:",
                  " ".join(f"{a['id']}:{best(a)}→{best(b_)}" for a, b_ in zip(base, recs) if a["id"] in sq))
            print("   8문항 밖에서 바뀐 질문:", [a["id"] for a, b_ in zip(base, recs) if a["retrieved"] != b_["retrieved"] and a["id"] not in sq])
            return recs

        print("   기준선 8문항 순위:", " ".join(f"{a['id']}:{best(a)}" for a in base if a["id"] in sq))
        print("   기준선 6개까지:", in_ctx(B.run(k=6)), "|", ctx_stats(B, B.run(k=6)))
        show("2a supersedes 공지를 6번째로 붙임 (합친 순위 20위 안에 있을 때)", boost("append", sup), k=8)
        show("2b supersedes 공지로 5번째를 바꿈", boost("replace", sup))
        show("2c supersedes 공지를 대체된 활동가이드 청크 바로 앞에 끼움 (5개 유지)", boost("before", sup))
        show("2c' 같은 방식, 20위 밖이면 벡터 순위에서 고름", boost("before", sup, deep=999))
        show("2d supersedes 공지를 앞에 끼우고 6개로", boost("before+", sup), k=8)
        show("2e related 공지까지 넓혀 5번째를 바꿈", boost("replace", rel))
        show("2f related 공지까지 넓혀 6번째로 붙임", boost("append", rel), k=10)

    if "mtype" in ONLY:
        ON = re.compile(r"온라인|화상|서로온|비대면")
        OFF = re.compile(r"오프라인|스터디카페|(?<!비)대면")

        def qtype(q):
            a, o = bool(ON.search(q)), bool(OFF.search(q))
            return "온라인" if a and not o else "오프라인" if o and not a else None

        def demote(q, b):
            full = b.base(q)
            t = qtype(q)
            if not t:
                return full
            opp = "오프라인" if t == "온라인" else "온라인"
            return [i for i in full if b.by_id[i].mtype != opp] + [i for i in full if b.by_id[i].mtype == opp]

        def prefer(q, b):   # 같은 유형 청크를 한 칸 올림 (약한 방식)
            full = b.base(q)
            t = qtype(q)
            if not t:
                return full
            sc = {i: -n + (1.5 if b.by_id[i].mtype == t else 0) - (1.5 if b.by_id[i].mtype not in (t, "공통") else 0) for n, i in enumerate(full)}
            return sorted(full, key=lambda i: -sc[i])

        from collections import Counter as C
        print("청크 유형:", dict(C(c.mtype for c in B.chunks)))
        fired = [(it["id"], it["type"], qtype(prep(it["question"]))) for it, _ in B.items if qtype(prep(it["question"]))]
        print(f"유형 낱말이 잡힌 질문 {len(fired)}개 (id, 평가셋 유형, 감지):", fired)
        wrong = [(r["id"], [B.by_id[i].mtype for i in r["retrieved"]]) for r, (it, _) in zip(base, B.items)
                 if qtype(prep(it["question"])) and any(B.by_id[i].mtype not in ("공통", qtype(prep(it["question"]))) for i in r["retrieved"])]
        print(f"   그중 기준선 상위 5개에 반대 유형 청크가 있는 질문 {len(wrong)}개:", wrong)
        report("3a 반대 유형 청크를 맨 뒤로", base, B.run(demote))
        report("3b 같은 유형 +1.5칸, 반대 유형 -1.5칸", base, B.run(prefer))

    if "thr" in ONLY:
        rows = []
        for it, gold in B.items:
            q = prep(it["question"])
            v, m = B.vec.full(q), B.bm.full(q)
            rows.append((it["id"], gold["answerable"], bool(gold["evidence"]), v[0][1], sum(s for _, s in v[:5]) / 5, v[0][1] - v[4][1], m[0][1],
                         len(set(i for i, _ in v[:5]) & set(i for i, _ in m[:5]))))

        def auc(pos, neg):   # pos가 neg보다 클 확률
            return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))

        names = ["벡터 1위 유사도", "벡터 상위5 평균", "벡터 1위-5위 차", "BM25 1위 점수", "벡터·BM25 상위5 겹침"]
        for label, neg_fn in [("정답이 '답 없음(no)'인 문항", lambda r: r[1] == "no"), ("근거가 아예 없는 문항", lambda r: not r[2])]:
            neg, pos = [r for r in rows if neg_fn(r)], [r for r in rows if not neg_fn(r)]
            print(f"## 6 {label} {len(neg)}개 vs 나머지 {len(pos)}개")
            for n, name in enumerate(names, 3):
                a, b_ = sorted(r[n] for r in neg), sorted(r[n] for r in pos)
                q = lambda xs, p: xs[min(int(p * len(xs)), len(xs) - 1)]
                thr = max(a)   # 답 없는 문항을 모두 잡는 경계
                fp = sum(x <= thr for x in b_)
                print(f"   {name}: 없음 {a[0]:.3f}~{a[-1]:.3f} (중앙 {q(a, .5):.3f}) | 있음 {b_[0]:.3f}~{b_[-1]:.3f} (10% {q(b_, .1):.3f}, 중앙 {q(b_, .5):.3f})"
                      f" | AUC {auc([r[n] for r in pos], [r[n] for r in neg]):.2f} | 없음을 모두 잡는 경계에서 잘못 걸리는 '있음' {fp}/{len(b_)}")
            print("   없음 문항 값:", [(r[0], round(r[3], 3), round(r[6], 1)) for r in neg])

    if "parent" in ONLY:
        order = [c.id for c in B.chunks]
        pos = {i: n for n, i in enumerate(order)}

        def neigh(i, span=1):
            out = []
            for d in range(-span, span + 1):
                j = pos[i] + d
                if 0 <= j < len(order) and B.by_id[order[j]].doc_id == B.by_id[i].doc_id:
                    out.append(order[j])
            return out

        def expand(top_n, span=1):
            def fn(q, b):
                out = []
                for i in b.base(q)[:top_n]:
                    for j in ([i] + neigh(i, span)):
                        if j not in out:
                            out.append(j)
                return out
            return fn

        def whole_doc(top_n):
            def fn(q, b):
                top = b.base(q)[:K]
                docs = list(dict.fromkeys(b.by_id[i].doc_id for i in top[:top_n]))
                return top + [c.id for c in b.chunks if c.doc_id in docs and c.id not in top]
            return fn

        print("## 7 이웃 청크 / 부모 문서 확장 (순위가 아니라 LLM에 주는 묶음 기준)")
        for name, fn, k in [("상위 5 (지금)", None, 5), ("상위 8", None, 8), ("상위 10", None, 10), ("상위 12", None, 12),
                            ("상위 5 + 앞뒤 이웃", expand(5), 99), ("상위 3 + 앞뒤 이웃", expand(3), 99),
                            ("상위 5 + 1위 문서 전체", whole_doc(1), 99), ("상위 5 + 상위 2개 문서 전체", whole_doc(2), 99)]:
            recs = B.run(fn, k=k)
            print(f"   {name:24s} {in_ctx(recs)} | {ctx_stats(B, recs)}")
            if name.startswith("상위 5 +") or name == "상위 8":
                b5 = {r["id"] for r in base if r["gold"]["evidence"] and not any(r["ranks"])}
                n5 = {r["id"] for r in recs if r["gold"]["evidence"] and not any(r["ranks"])}
                print(f"      새로 근거가 들어온 문항: {sorted(b5 - n5)}")

    if "ideas" in ONLY:
        # 8a 한 문서에서 최대 2개만 (다양성)
        def cap(n):
            def fn(q, b):
                out, cnt = [], {}
                for i in b.base(q):
                    d = b.by_id[i].doc_id
                    if cnt.get(d, 0) < n:
                        out.append(i)
                        cnt[d] = cnt.get(d, 0) + 1
                return out
            return fn

        report("8a 한 문서에서 최대 2개", base, B.run(cap(2)))
        report("8a' 한 문서에서 최대 3개", base, B.run(cap(3)))

        # 8b 작게 찾고 크게 주기: 섹션을 줄(표의 행, 글머리 줄) 단위로 임베딩하고, 섹션 점수 = 가장 잘 맞는 줄의 점수
        kids, owner = [], []
        for c in B.chunks:
            head, _, body = c.text.partition("\n")
            lines_ = [l.strip() for l in body.splitlines() if len(l.strip()) >= 8 and not re.fullmatch(r"[|\-: ]+", l.strip())]
            for l in lines_:
                kids.append(f"{head}\n{l}")
                owner.append(c.id)
        print(f"## 8b 줄 단위 색인: 줄 {len(kids)}개 (섹션 {len(B.chunks)}개)")
        import hashlib, time
        import numpy as np
        key = hashlib.sha256(("\x1e".join(kids) + emb().name).encode()).hexdigest()[:16]
        path = settings.cache_dir / f"index_{key}.npy"
        t0 = time.time()
        if path.exists():
            M = np.load(path)
        else:
            M = emb().embed(kids)
            np.save(path, M)
        print(f"   줄 임베딩 {time.time() - t0:.0f}초")
        qcache = {}

        def line_rank(q):
            if q not in qcache:
                s = M @ emb().embed_query(q)
                bestc = {}
                for o, x in zip(owner, s):
                    if x > bestc.get(o, -9):
                        bestc[o] = float(x)
                qcache[q] = [i for i, _ in sorted(bestc.items(), key=lambda x: -x[1])]
            return qcache[q]

        s = summarize(B.run(lambda q, b: line_rank(q)), K)["retrieval"]
        print("   줄 단위 벡터 단독:", s)
        report("8b-1 줄 단위 벡터 + BM25 (섹션 벡터를 대신함)", base, B.run(lambda q, b: fuse([line_rank(q), b.bm.rank(q)])))
        report("8b-2 섹션 벡터 + 줄 단위 벡터 + BM25 (셋을 합침)", base, B.run(lambda q, b: fuse([b.vec.rank(q), line_rank(q), b.bm.rank(q)])))
        report("8b-3 섹션 벡터 + 줄 단위 벡터 (BM25 없음)", base, B.run(lambda q, b: fuse([b.vec.rank(q), line_rank(q)])))

        # 8c 문의처를 묻는 말이 있으면 '문의처별 담당 범위' 청크를 5번째에 넣기
        ASK = re.compile(r"어디(에|로|다|서)?\s*(물어|문의|연락|말해|얘기)|누구(한테|에게)")
        target = next(c.id for c in B.chunks if c.doc_id == "manual-2026-7" and "담당 범위" in c.heading)

        def contact(q, b):
            top = b.base(q)[:K]
            if ASK.search(q) and target not in top:
                top = top[:K - 1] + [target]
            return top

        hit = [it["id"] for it, _ in B.items if ASK.search(prep(it["question"]))]
        print("   문의처를 묻는 말이 잡힌 질문:", hit)
        report("8c 문의처 질문이면 '문의처별 담당 범위'를 5번째에", base, B.run(contact))

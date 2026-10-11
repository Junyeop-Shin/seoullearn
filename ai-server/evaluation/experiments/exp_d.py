"""Q053(시간확대 조건)을 청크 단위로 보기 + 용어집 한 줄('조건' → '대상')의 효과. LLM 호출 없음."""
import sys

from common import *  # noqa
import common

B = Bench("v2")
base = B.run()
q = prep("시간확대 하려면 조건이 뭐예요?")
print("보강된 질의:", q)
for t in ("notice-2026-n06#2", "manual-2026-5-1#2", "notice-2026-n06#5", "notice-2026-n06#7"):
    print(f"  {t} ({B.by_id[t].heading}): 벡터 {B.vec.rank(q).index(t) + 1}위, BM25 {B.bm.rank(q).index(t) + 1}위, 합친 순위 "
          f"{(B.base(q).index(t) + 1) if t in B.base(q) else '40위 밖'}")

# 용어집에 한 줄을 더했을 때 (저장소 파일은 그대로, 메모리에서만)
for extra in [("조건", "대상"), ("조건", "신청 대상 요건")]:
    old = common.EXP.pairs
    common.EXP.pairs = sorted(old + [extra], key=lambda x: -len(x[0]))
    B2 = Bench("v2")
    recs = B2.run()
    fired = [it["id"] for it, _ in B2.items if extra[0] in it["question"]]
    print(f"## 용어집 + {extra}: 걸리는 질문 {fired}")
    print("  ", line(recs), "\n   변화", diff(base, recs))
    q2 = prep("시간확대 하려면 조건이 뭐예요?")
    full = B2.base(q2)
    print("   Q053 상위5:", [f"{i}({B.by_id[i].heading[:8]})" for i in full[:5]])
    for b1, r in zip(base, recs):
        if b1["id"] in fired:
            print(f"     {b1['id']} 근거 순위 {best(b1)}→{best(r)}")
    common.EXP.pairs = old

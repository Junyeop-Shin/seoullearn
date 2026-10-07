"""평가 지표. 검색(정답 근거를 찾았나) → 판단(답할지 말지) → 연결(문의처) → 인용 → 채점 순."""
from __future__ import annotations

from collections import defaultdict

import re

from app.corpus import Chunk, parse_page_range

# 공지가 매뉴얼 내용을 바꿨을 때 답변이 그 사실을 밝혔는지 보는 표현. 낱말 검사라서 대략적인 지표다.
CHANGE_WORDS = re.compile(r"바뀌|바뀐|변경되|변경됐|개정|종료되|종료됐|종료된|이전에는|기존|더 이상|달라")


def notes_change(answer: str) -> bool:
    return bool(CHANGE_WORDS.search(answer or ""))


def evidence_match(chunk: Chunk, evidence: str) -> bool:
    """근거 'doc_id:페이지'와 청크가 같은 문서·겹치는 페이지인지."""
    doc_id, _, page = evidence.partition(":")
    if chunk.doc_id != doc_id:
        return False
    g, c = parse_page_range(page), parse_page_range(chunk.page)
    if g is None or c is None:
        return True
    return not (c[1] < g[0] or g[1] < c[0])


def gold_ranks(retrieved: list[Chunk], evidence: list[str]) -> list[int | None]:
    """근거마다 처음 찾은 순위(1부터). 못 찾으면 None."""
    out = []
    for ev in evidence:
        rank = next((i for i, c in enumerate(retrieved, 1) if evidence_match(c, ev)), None)
        out.append(rank)
    return out


def _pct(n, d):
    return round(100.0 * n / d, 1) if d else None


def summarize(records: list[dict], k: int) -> dict:
    s: dict = {"n": len(records)}

    # 검색: 근거가 있는 문항만
    with_ev = [r for r in records if r["gold"]["evidence"]]
    hit = lambda r, kk: any(x is not None and x <= kk for x in r["ranks"])  # noqa: E731
    s["retrieval"] = {
        "n": len(with_ev),
        "hit@1": _pct(sum(hit(r, 1) for r in with_ev), len(with_ev)),
        "hit@3": _pct(sum(hit(r, 3) for r in with_ev), len(with_ev)),
        f"hit@{k}": _pct(sum(hit(r, k) for r in with_ev), len(with_ev)),
        f"recall@{k}": _pct(sum(sum(1 for x in r["ranks"] if x and x <= k) / len(r["ranks"]) for r in with_ev), len(with_ev)),
        "mrr": round(sum(1.0 / min([x for x in r["ranks"] if x] or [float("inf")]) for r in with_ev) / max(len(with_ev), 1), 3),
    }

    answered = [r for r in records if r.get("pred")]
    if not answered:
        return s
    g_ans = lambda r: r["gold"]["answerable"]  # noqa: E731
    p_ans = lambda r: r["pred"]["answerable"]  # noqa: E731
    gold_no = [r for r in answered if g_ans(r) == "no"]
    gold_yes = [r for r in answered if g_ans(r) == "yes"]
    s["answer"] = {
        "answerable_acc": _pct(sum(g_ans(r) == p_ans(r) for r in answered), len(answered)),
        # 답이 없는데 답했다고 한 비율 (지어내기 위험). 낮을수록 좋다
        "fabrication_rate": _pct(sum(p_ans(r) == "yes" for r in gold_no), len(gold_no)),
        # 답이 있는데 못 한다고 한 비율. 낮을수록 좋다
        "over_refusal_rate": _pct(sum(p_ans(r) == "no" for r in gold_yes), len(gold_yes)),
        "route_acc": _pct(sum(r["gold"]["route"] == r["pred"]["route"] for r in answered), len(answered)),
        "format_error_rate": _pct(sum(bool(r["pred"].get("error")) for r in answered), len(answered)),
    }
    cited = [r for r in answered if r["pred"]["citations"] and r["gold"]["evidence"]]
    if cited:
        good = sum(sum(1 for ok in r["cite_ok"] if ok) for r in cited)
        total = sum(len(r["cite_ok"]) for r in cited)
        s["answer"]["citation_precision"] = _pct(good, total)
    # 매뉴얼을 대체한 공지(supersedes)가 정답 근거인 문항에서, 답변이 '바뀐 점'을 밝힌 비율 (v2 코퍼스에서만 나온다)
    superseded = [r for r in answered if r.get("supersede")]
    if superseded:
        s["answer"]["change_noted_n"] = len(superseded)
        s["answer"]["change_noted_rate"] = _pct(sum(notes_change(r["pred"]["answer"]) for r in superseded), len(superseded))
    safety = [r for r in answered if r["gold"]["route"] == "운영사무국(즉시)"]
    if safety:
        s["answer"]["safety_route_ok"] = _pct(sum(r["pred"]["route"] == "운영사무국(즉시)" for r in safety), len(safety))

    judged = [r for r in answered if r.get("judge") and r["judge"].get("score") is not None]
    if judged:
        s["judge"] = {
            "n": len(judged),
            "correctness_avg_0to2": round(sum(r["judge"]["score"] for r in judged) / len(judged), 2),
            "fully_correct": _pct(sum(r["judge"]["score"] == 2 for r in judged), len(judged)),
            "unsupported_claims": _pct(sum(bool(r["judge"].get("unsupported")) for r in judged), len(judged)),
        }

    by_cat = defaultdict(list)
    for r in answered:
        by_cat[r["category"]].append(r)
    s["by_category"] = {
        c: {"n": len(rs), "answerable_acc": _pct(sum(g_ans(r) == p_ans(r) for r in rs), len(rs)),
            "retrieval_hit@k": _pct(sum(hit(r, k) for r in rs if r["gold"]["evidence"]), sum(1 for r in rs if r["gold"]["evidence"]))}
        for c, rs in sorted(by_cat.items())
    }
    return s

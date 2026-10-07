"""실행 결과(jsonl)의 hit@k를 홀수·짝수 번호 문항으로 나눠 보여준다 (용어집·프롬프트 과적합 확인용).

  python scripts/parity_hits.py eval/runs/<전>.jsonl eval/runs/<후>.jsonl [--k 5]
"""
import argparse
import json
from pathlib import Path


def rates(path: Path, k: int) -> dict:
    out = {}
    recs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    for name, want in (("홀수", 1), ("짝수", 0)):
        rs = [r for r in recs if r["gold"]["evidence"] and int(r["id"][1:]) % 2 == want]
        hit = [r["id"] for r in rs if any(x and x <= k for x in r["ranks"])]
        out[name] = (len(hit), len(rs), set(hit))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("before", type=Path)
    p.add_argument("after", type=Path)
    p.add_argument("--k", type=int, default=5)
    a = p.parse_args()
    b, f = rates(a.before, a.k), rates(a.after, a.k)
    for name in ("홀수", "짝수"):
        (bh, bn, bs), (fh, fn, fs) = b[name], f[name]
        print(f"{name} 문항 hit@{a.k}: {100 * bh / bn:.1f}% ({bh}/{bn}) → {100 * fh / fn:.1f}% ({fh}/{fn})"
              f"  새로 맞음 {sorted(fs - bs)}  새로 틀림 {sorted(bs - fs)}")


if __name__ == "__main__":
    main()

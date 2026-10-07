"""RAG 원본 문서 형식 검사.

검사 항목
- front matter 필수 필드 (doc_type별)
- 모든 ## 제목 바로 아래 page/type 주석
- type 값, 매뉴얼 청크 페이지가 문서 pages 범위 안에 있는지
- related / supersedes가 존재하는 doc_id를 가리키는지
- doc_id 중복
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

REQUIRED = {
    "manual": ["doc_id", "title", "section", "pages", "doc_type", "source", "version", "published", "mentoring_type", "aliases"],
    "notice": ["doc_id", "title", "doc_type", "source", "published", "valid_from", "valid_until", "status", "mentoring_type", "related", "supersedes", "aliases"],
}
TYPES = {"공통", "온라인", "오프라인"}
MARK = re.compile(r"^<!-- page: (?P<page>[^|]+?) \| type: (?P<type>\S+) -->$")


def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        v = v.strip().strip('"')
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        fm[k.strip()] = v
    return fm, text[m.end():]


def page_range(s):
    a, _, b = s.partition("-")
    return int(a), int(b or a)


def main():
    errors, docs, chunks = [], {}, 0
    files = sorted((DATA / "manual").glob("*.md")) + sorted((DATA / "notice").glob("*.md"))
    for f in files:
        text = f.read_text(encoding="utf-8")
        fm, body = front_matter(text)
        if fm is None:
            errors.append(f"{f.name}: front matter 없음")
            continue
        kind = fm.get("doc_type")
        for k in REQUIRED.get(kind, []):
            if k not in fm:
                errors.append(f"{f.name}: 필드 누락 {k}")
        if fm.get("mentoring_type") not in TYPES:
            errors.append(f"{f.name}: mentoring_type 값 오류 {fm.get('mentoring_type')}")
        if fm["doc_id"] in docs:
            errors.append(f"{f.name}: doc_id 중복 {fm['doc_id']}")
        docs[fm["doc_id"]] = fm
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if not line.startswith("## "):
                continue
            chunks += 1
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            m = MARK.match(nxt)
            if not m:
                errors.append(f"{f.name}: '{line}' 아래 page/type 주석 없음")
                continue
            if m["type"] not in TYPES:
                errors.append(f"{f.name}: '{line}' type 값 오류 {m['type']}")
            if kind == "manual":
                lo, hi = page_range(fm["pages"])
                plo, phi = page_range(m["page"].strip())
                if plo < lo or phi > hi:
                    errors.append(f"{f.name}: '{line}' 페이지 {m['page']}가 범위 {fm['pages']} 밖")
    for did, fm in docs.items():
        for key in ("related", "supersedes"):
            for ref in fm.get(key) or []:
                if ref not in docs:
                    errors.append(f"{did}: {key}가 없는 문서를 가리킴 {ref}")
    with open(DATA / "glossary.csv", encoding="utf-8") as g:
        rows = list(csv.DictReader(g))
    if not rows or set(rows[0]) != {"user_term", "official_term", "note"}:
        errors.append("glossary.csv: 헤더 오류")

    n_manual = sum(1 for d in docs.values() if d["doc_type"] == "manual")
    n_notice = len(docs) - n_manual
    print(f"문서 {len(docs)}개 (매뉴얼 {n_manual}, 공지 {n_notice}), 청크 {chunks}개, 용어 {len(rows)}개")
    for e in errors:
        print("ERROR", e)
    print("OK" if not errors else f"{len(errors)}개 오류")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

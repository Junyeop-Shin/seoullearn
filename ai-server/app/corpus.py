"""RAG 원본 문서를 청크로 만든다.

두 가지 방식을 지원한다 (개선 전후 비교용).
- markdown: 정리한 섹션 문서(data/manual, data/notice). '## 제목' 하나 = 청크 하나, 메타데이터 포함
- pdf: 활동가이드 원본 PDF를 페이지 텍스트 그대로 고정 길이로 자름 (기본형)
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import settings

MARK = re.compile(r"^<!-- page: (?P<page>[^|]+?) \| type: (?P<type>\S+) -->$")


@dataclass
class Chunk:
    id: str
    doc_id: str
    title: str
    heading: str
    text: str
    page: str = "-"
    mtype: str = "공통"  # 공통 / 온라인 / 오프라인
    doc_type: str = "manual"
    status: str = "active"
    published: str = "unknown"
    supersedes: list[str] = field(default_factory=list)

    @property
    def cite(self) -> str:
        """사용자에게 보여줄 근거 표기."""
        if self.doc_type == "manual":
            return f"활동가이드 p.{self.page} {self.heading}"
        return f"공지 「{self.title}」 {self.heading}"


def front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        v = v.strip().strip('"')
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        fm[k.strip()] = v
    return fm, text[m.end():]


def parse_page_range(p: str) -> tuple[int, int] | None:
    p = p.strip()
    if not p or p == "-":
        return None
    a, _, b = p.partition("-")
    return int(a), int(b or a)


def load_markdown(corpus: str = "v1", include_expired: bool = False, data_dir: Path | None = None) -> list[Chunk]:
    """corpus v1 = 매뉴얼만, v2 = 매뉴얼 + 공지."""
    data_dir = data_dir or settings.data_dir
    folders = ["manual"] + (["notice"] if corpus == "v2" else [])
    chunks: list[Chunk] = []
    for folder in folders:
        for f in sorted((data_dir / folder).glob("*.md")):
            fm, body = front_matter(f.read_text(encoding="utf-8"))
            status = fm.get("status", "active")
            if status == "expired" and not include_expired:
                continue
            sections = re.split(r"(?m)^## ", body)
            for n, sec in enumerate(sections[1:], 1):
                lines = sec.splitlines()
                heading = lines[0].strip()
                page, mtype = "-", fm.get("mentoring_type", "공통")
                rest = lines[1:]
                if rest and (m := MARK.match(rest[0].strip())):
                    page, mtype = m["page"].strip(), m["type"]
                    rest = rest[1:]
                content = "\n".join(rest).strip()
                # 청크 앞에 문서 제목 > 소제목 경로를 붙여 검색에 걸리게 한다
                text = f"[{fm.get('title', '')} > {heading}]\n{content}"
                chunks.append(Chunk(
                    id=f"{fm['doc_id']}#{n}", doc_id=fm["doc_id"], title=fm.get("title", ""), heading=heading,
                    text=text, page=page, mtype=mtype, doc_type=fm.get("doc_type", "manual"), status=status,
                    published=fm.get("published", "unknown"), supersedes=fm.get("supersedes") or [],
                ))
    return chunks


# ------------------------------------------------------------------ PDF 기본형
def _manual_page_map(data_dir: Path) -> list[tuple[int, int, str]]:
    out = []
    for f in (data_dir / "manual").glob("*.md"):
        fm, _ = front_matter(f.read_text(encoding="utf-8"))
        r = parse_page_range(fm.get("pages", ""))
        if r:
            out.append((r[0], r[1], fm["doc_id"]))
    return out


def _pdf_pages(pdf: Path) -> list[str]:
    try:
        import fitz  # pymupdf

        with fitz.open(pdf) as doc:
            return [page.get_text() for page in doc]
    except ImportError:
        if not shutil.which("pdftotext"):
            raise RuntimeError("pymupdf 또는 pdftotext가 필요합니다")
        out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
        return out.split("\f")


def load_pdf(pdf: Path | None = None, size: int = 500, overlap: int = 100, data_dir: Path | None = None) -> list[Chunk]:
    """원본 PDF를 페이지별로 고정 길이 청크로 자른다. 인쇄 페이지 = PDF 페이지 - 1."""
    data_dir = data_dir or settings.data_dir
    if pdf is None:
        found = sorted((data_dir / "raw").glob("*.pdf"))
        if not found:
            raise FileNotFoundError("data/raw/ 에 활동가이드 PDF를 넣어 주세요")
        pdf = found[0]
    page_map = _manual_page_map(data_dir)
    chunks = []
    for idx, raw in enumerate(_pdf_pages(pdf), 1):
        printed = idx - 1
        text = re.sub(r"[ \t]+", " ", raw).strip()
        if len(text) < 20:
            continue
        doc_id = next((d for a, b, d in page_map if a <= printed <= b), "manual-2026-other")
        for k, start in enumerate(range(0, max(len(text) - overlap, 1), size - overlap)):
            piece = text[start : start + size]
            chunks.append(Chunk(id=f"pdf-p{printed}-{k}", doc_id=doc_id, title="활동가이드 원문", heading=f"p.{printed}",
                                text=piece, page=str(printed)))
    return chunks


def load_chunks(source: str, corpus: str = "v1") -> list[Chunk]:
    if source == "pdf":
        if corpus != "v1":
            raise ValueError("PDF 기본형은 매뉴얼만(v1) 지원")
        return load_pdf()
    return load_markdown(corpus)

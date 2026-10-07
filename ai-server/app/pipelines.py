"""평가·서비스에서 쓰는 RAG 설정 모음. 개선 단계를 하나씩 추가해 전후를 비교한다."""
from __future__ import annotations

from dataclasses import dataclass

from .corpus import load_chunks
from .llm import Embedder, get_embedder
from .retrieval import BM25Retriever, ExpandingRetriever, GlossaryExpander, HybridRetriever, VectorRetriever


@dataclass(frozen=True)
class PipelineConfig:
    name: str
    source: str  # pdf | markdown
    retriever: str  # vector | bm25 | hybrid
    glossary: bool = False
    description: str = ""


CONFIGS = {
    c.name: c
    for c in [
        PipelineConfig("pdf_vector", "pdf", "vector", description="기본형: 원본 PDF 고정 길이 청크 + 벡터 검색"),
        PipelineConfig("pdf_bm25", "pdf", "bm25", description="원본 PDF 고정 길이 청크 + BM25 (참고용)"),
        PipelineConfig("md_vector", "markdown", "vector", description="정리한 섹션 문서 + 벡터 검색"),
        PipelineConfig("md_bm25", "markdown", "bm25", description="정리한 섹션 문서 + BM25 (참고용)"),
        PipelineConfig("md_hybrid", "markdown", "hybrid", description="섹션 문서 + 벡터·BM25 하이브리드"),
        PipelineConfig("md_hybrid_glossary", "markdown", "hybrid", glossary=True, description="하이브리드 + 용어집 질의 확장"),
    ]
}


def build_retriever(config: str | PipelineConfig, corpus: str = "v1", embedder: Embedder | None = None):
    cfg = CONFIGS[config] if isinstance(config, str) else config
    chunks = load_chunks(cfg.source, corpus)
    if cfg.retriever == "bm25":
        r = BM25Retriever(chunks)
    else:
        vec = VectorRetriever(chunks, embedder or get_embedder())
        r = vec if cfg.retriever == "vector" else HybridRetriever([vec, BM25Retriever(chunks)])
    if cfg.glossary:
        r = ExpandingRetriever(r, GlossaryExpander())
    return r, chunks

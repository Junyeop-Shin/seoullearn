"""pgvector 벡터 저장소. 매뉴얼·공지 청크와 그 메타데이터만 저장한다.

멘티 관련 데이터, 질문 원문, 답변은 여기에 저장하지 않는다 (그런 테이블도 만들지 않는다).
"""
from __future__ import annotations

import numpy as np

from .corpus import Chunk

TABLE = "rag_chunks"
SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS {TABLE} (
    index_key       text NOT NULL,   -- 청크 내용 + 임베딩 모델의 해시. 문서나 모델이 바뀌면 새 색인이 된다
    chunk_id        text NOT NULL,
    doc_id          text NOT NULL,
    page            text NOT NULL,
    mtype           text NOT NULL,
    status          text NOT NULL,
    published       text NOT NULL,
    embedding_model text NOT NULL,
    content         text NOT NULL,   -- 매뉴얼·공지 청크 본문
    embedding       vector NOT NULL,
    PRIMARY KEY (index_key, chunk_id)
);
"""


def vector_literal(v: np.ndarray) -> str:
    return "[" + ",".join(f"{float(x):.8f}" for x in v) + "]"


class PgVectorStore:
    def __init__(self, url: str, connect=None):
        if connect is None:
            import psycopg  # 지연 import: file 방식과 오프라인 테스트에는 불필요

            connect = psycopg.connect
        self.conn = connect(url, autocommit=True)
        self.conn.execute(SCHEMA)

    def has_index(self, index_key: str) -> bool:
        row = self.conn.execute(f"SELECT 1 FROM {TABLE} WHERE index_key = %s LIMIT 1", (index_key,)).fetchone()
        return row is not None

    def add(self, index_key: str, chunks: list[Chunk], matrix: np.ndarray, embedding_model: str) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(
                f"INSERT INTO {TABLE} (index_key, chunk_id, doc_id, page, mtype, status, published, embedding_model,"
                " content, embedding) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)"
                " ON CONFLICT (index_key, chunk_id) DO NOTHING",
                [(index_key, c.id, c.doc_id, c.page, c.mtype, c.status, c.published, embedding_model, c.text,
                  vector_literal(v)) for c, v in zip(chunks, matrix)],
            )

    def search(self, index_key: str, query: np.ndarray, k: int) -> list[tuple[str, float]]:
        """코사인 유사도가 높은 순서로 (chunk_id, 점수). 벡터는 정규화돼 있어 file 방식의 내적과 같은 값이다."""
        q = vector_literal(query)
        rows = self.conn.execute(
            f"SELECT chunk_id, 1 - (embedding <=> %s::vector) FROM {TABLE} WHERE index_key = %s"
            " ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s", (q, index_key, q, k)).fetchall()
        return [(r[0], float(r[1])) for r in rows]

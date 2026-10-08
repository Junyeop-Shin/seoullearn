# RAG 평가 비교

백분율(%)은 높을수록 좋고, ↓ 표시는 낮을수록 좋다.

| 설정 | 메모 | 임베딩 | 코퍼스 | LLM | 검색 hit@1 | 검색 hit@3 | 검색 hit@k | MRR | 답변가능 판단 | 지어내기↓ | 과잉거절↓ | 문의처 | 인용 정확도 | 바뀐 점 언급 | 안전 연결 | 채점 평균(0~2) | 완전 정답 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pdf_bm25 | - | - | v1 | 검색만 | 38.2 | 60.3 | 70.6 | 0.501 | - | - | - | - | - | - | - | - | - |
| pdf_vector | - | multilingual-e5-small-ko-v2 | v1 | 검색만 | 44.1 | 70.6 | 80.9 | 0.59 | - | - | - | - | - | - | - | - | - |
| md_bm25 | - | - | v1 | 검색만 | 52.9 | 72.1 | 75.0 | 0.618 | - | - | - | - | - | - | - | - | - |
| md_vector | - | multilingual-e5-small-ko-v2 | v1 | 검색만 | 54.4 | 79.4 | 83.8 | 0.669 | - | - | - | - | - | - | - | - | - |
| md_hybrid | - | multilingual-e5-small-ko-v2 | v1 | 검색만 | 52.9 | 77.9 | 86.8 | 0.665 | - | - | - | - | - | - | - | - | - |
| md_hybrid_glossary | - | multilingual-e5-small-ko-v2 | v1 | 검색만 | 54.4 | 77.9 | 86.8 | 0.673 | - | - | - | - | - | - | - | - | - |
| md_hybrid_glossary | - | multilingual-e5-small-ko-v2 | v1 | openai:gpt-4.1-mini-2025-04-14 | 54.4 | 77.9 | 85.3 | 0.67 | 73.6 | 12.5 | 3.8 | 73.6 | 63.9 | - | 100.0 | 1.14 | 40.3 |
| md_hybrid_glossary | 가드 수정 후 | multilingual-e5-small-ko-v2 | v1 | 검색만 | 55.9 | 80.9 | 88.2 | 0.689 | - | - | - | - | - | - | - | - | - |
| md_hybrid_glossary | 가드 수정 후 | multilingual-e5-small-ko-v2 | v1 | openai:gpt-4.1-mini-2025-04-14 | 55.9 | 80.9 | 86.8 | 0.687 | 79.2 | 12.5 | 3.8 | 76.4 | 64.2 | - | 100.0 | 1.12 | 40.3 |
| md_hybrid_glossary | route 키 누락 허용 | multilingual-e5-small-ko-v2 | v1 | openai:gpt-4.1-mini-2025-04-14 | 55.9 | 80.9 | 86.8 | 0.687 | 81.9 | 12.5 | 0.0 | 79.2 | 64.6 | - | 100.0 | 1.15 | 41.7 |
| md_hybrid_glossary_rerank | 리랭커 mmarco-mMiniLMv2-L12-H384-v1 | multilingual-e5-small-ko-v2 | v1 | 검색만 | 55.9 | 82.4 | 83.8 | 0.675 | - | - | - | - | - | - | - | - | - |
| md_hybrid_glossary | 용어집 보강 후 | multilingual-e5-small-ko-v2 | v1 | 검색만 | 58.8 | 83.8 | 91.2 | 0.722 | - | - | - | - | - | - | - | - | - |
| md_hybrid_glossary | 용어집 보강 후 | multilingual-e5-small-ko-v2 | v1 | openai:gpt-4.1-mini-2025-04-14 | 58.8 | 83.8 | 89.7 | 0.719 | 83.3 | 12.5 | 0.0 | 80.6 | 65.8 | - | 100.0 | 1.19 | 43.1 |
| md_hybrid_glossary_rerank | 리랭커 bge-reranker-v2-m3 (용어집 보강 후) | multilingual-e5-small-ko-v2 | v1 | 검색만 | 77.9 | 86.8 | 92.6 | 0.837 | - | - | - | - | - | - | - | - | - |
| md_hybrid_glossary | 답변 규칙 보강 전 (v2) | multilingual-e5-small-ko-v2 | v2 | openai:gpt-4.1-mini-2025-04-14 | 59.2 | 83.1 | 87.3 | 0.705 | 84.7 | 25.0 | 3.3 | 79.2 | 65.4 | 12.5 | 100.0 | 1.18 | 41.7 |
| md_hybrid_glossary | 답 못 하면 문의처 기본값 (최종) | multilingual-e5-small-ko-v2 | v1 | openai:gpt-4.1-mini-2025-04-14 | 58.8 | 83.8 | 89.7 | 0.719 | 80.6 | 12.5 | 0.0 | 86.1 | 66.7 | - | 100.0 | 1.26 | 48.6 |
| md_hybrid_glossary | 답 못 하면 문의처 기본값 (최종, v2) | multilingual-e5-small-ko-v2 | v2 | openai:gpt-4.1-mini-2025-04-14 | 59.2 | 83.1 | 87.3 | 0.705 | 81.9 | 25.0 | 3.3 | 80.6 | 65.3 | 37.5 | 100.0 | 1.18 | 43.1 |
| md_hybrid_glossary_rerank | 리랭커 bge-reranker-v2-m3 + 최종 규칙 | multilingual-e5-small-ko-v2 | v1 | openai:gpt-4.1-mini-2025-04-14 | 77.9 | 86.8 | 92.6 | 0.837 | 76.4 | 25.0 | 0.0 | 77.8 | 69.7 | - | 100.0 | 1.17 | 41.7 |

## 설정 설명

- **md_bm25**: 정리한 섹션 문서 + BM25 (참고용)
- **md_hybrid**: 섹션 문서 + 벡터·BM25 하이브리드
- **md_hybrid_glossary**: 하이브리드 + 용어집 질의 확장
- **md_hybrid_glossary_rerank**: 하이브리드 + 용어집 + 상위 20개 리랭커
- **md_vector**: 정리한 섹션 문서 + 벡터 검색
- **pdf_bm25**: 원본 PDF 고정 길이 청크 + BM25 (참고용)
- **pdf_vector**: 기본형: 원본 PDF 고정 길이 청크 + 벡터 검색

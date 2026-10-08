# RAG 평가 비교

백분율(%)은 높을수록 좋고, ↓ 표시는 낮을수록 좋다.

| 설정 | 메모 | 임베딩 | 코퍼스 | LLM | 검색 hit@1 | 검색 hit@3 | 검색 hit@k | MRR | 답변가능 판단 | 지어내기↓ | 과잉거절↓ | 문의처 | 인용 정확도 | 바뀐 점 언급 | 안전 연결 | 채점 평균(0~2) | 완전 정답 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pdf_bm25 | 최종 | - | v1 | 검색만 | 38.2 | 61.8 | 70.6 | 0.505 | - | - | - | - | - | - | - | - | - |
| pdf_vector | 최종 | multilingual-e5-small-ko-v2 | v1 | 검색만 | 44.1 | 72.1 | 82.4 | 0.595 | - | - | - | - | - | - | - | - | - |
| md_bm25 | 최종 | - | v1 | 검색만 | 52.9 | 72.1 | 75.0 | 0.618 | - | - | - | - | - | - | - | - | - |
| md_vector | 최종 | multilingual-e5-small-ko-v2 | v1 | 검색만 | 57.4 | 79.4 | 83.8 | 0.683 | - | - | - | - | - | - | - | - | - |
| md_hybrid | 최종 | multilingual-e5-small-ko-v2 | v1 | 검색만 | 54.4 | 80.9 | 88.2 | 0.682 | - | - | - | - | - | - | - | - | - |
| md_hybrid_glossary | 최종 | multilingual-e5-small-ko-v2 | v1 | 검색만 | 58.8 | 83.8 | 91.2 | 0.722 | - | - | - | - | - | - | - | - | - |
| md_hybrid_glossary | 최종 | multilingual-e5-small-ko-v2 | v2 | 검색만 | 59.2 | 83.1 | 87.3 | 0.709 | - | - | - | - | - | - | - | - | - |
| md_hybrid_glossary | 최종 (순서 seed 0) | multilingual-e5-small-ko-v2 | v1 | openai:gpt-4.1-mini-2025-04-14 | 58.8 | 83.8 | 89.7 | 0.719 | 80.6 | 12.5 | 0.0 | 86.1 | 69.0 | - | 100.0 | 1.38 | 55.6 |
| md_hybrid_glossary | 최종 (순서 seed 1) | multilingual-e5-small-ko-v2 | v1 | openai:gpt-4.1-mini-2025-04-14 | 30.9 | 64.7 | 89.7 | 0.513 | 80.6 | 12.5 | 3.8 | 80.6 | 64.7 | - | 100.0 | 1.24 | 47.2 |
| md_hybrid_glossary | 최종 (순서 seed 2) | multilingual-e5-small-ko-v2 | v1 | openai:gpt-4.1-mini-2025-04-14 | 27.9 | 66.2 | 89.7 | 0.495 | 81.9 | 12.5 | 1.9 | 77.8 | 64.1 | - | 100.0 | 1.29 | 50.0 |
| md_hybrid_glossary | 최종 (순서 seed 0) | multilingual-e5-small-ko-v2 | v2 | openai:gpt-4.1-mini-2025-04-14 | 59.2 | 83.1 | 87.3 | 0.709 | 83.3 | 25.0 | 3.3 | 86.1 | 60.4 | 25.0 | 100.0 | 1.22 | 44.4 |
| md_hybrid_glossary | 최종 (순서 seed 1) | multilingual-e5-small-ko-v2 | v2 | openai:gpt-4.1-mini-2025-04-14 | 39.4 | 69.0 | 87.3 | 0.571 | 81.9 | 25.0 | 3.3 | 80.6 | 62.5 | 25.0 | 100.0 | 1.24 | 44.4 |
| md_hybrid_glossary | 최종 (순서 seed 2) | multilingual-e5-small-ko-v2 | v2 | openai:gpt-4.1-mini-2025-04-14 | 33.8 | 73.2 | 87.3 | 0.545 | 80.6 | 25.0 | 3.3 | 76.4 | 62.7 | 37.5 | 100.0 | 1.19 | 45.8 |

## 설정 설명

- **md_bm25**: 정리한 섹션 문서 + BM25 (참고용)
- **md_hybrid**: 섹션 문서 + 벡터·BM25 하이브리드
- **md_hybrid_glossary**: 하이브리드 + 용어집 질의 확장
- **md_vector**: 정리한 섹션 문서 + 벡터 검색
- **pdf_bm25**: 원본 PDF 고정 길이 청크 + BM25 (참고용)
- **pdf_vector**: 기본형: 원본 PDF 고정 길이 청크 + 벡터 검색

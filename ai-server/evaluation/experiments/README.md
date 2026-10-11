# 검색 실험 (2026-10-11)

매뉴얼 질문의 검색에 심화 기법을 넣으면 나아지는지 재 본 스크립트다. 서비스 코드가 아니다. 저장소의 검색기를 감싸서 쓰고, LLM을 부르지 않는다(로컬 임베딩과 BM25만).
결과와 판단은 `eval/reports/retrieval_experiments.md`에 있다.

```bash
# 한 번에 하나씩. 각 1~3분
docker compose run --rm ai-server python evaluation/experiments/exp_a.py            # 기준선, aliases, BM25 변형, RRF 격자 (base alias bm25 rrf 중 골라 돌릴 수 있다)
docker compose run --rm ai-server python evaluation/experiments/exp_b.py            # 공지 붙이기, 유형, 답 없음 경계, 이웃·문서 확장, 그 밖 (n12 rrf notice mtype thr parent ideas)
docker compose run --rm ai-server python evaluation/experiments/exp_c.py            # 공지 순서 바꾸기, 서비스에서 검색을 타는 문항 기준
docker compose run --rm ai-server python evaluation/experiments/exp_d.py            # Q053의 청크별 순위, 용어집 한 줄
```

청크 글을 바꾸는 실험은 `.cache/`에 색인 파일(`index_*.npy`)을 새로 만든다. 지워도 된다.

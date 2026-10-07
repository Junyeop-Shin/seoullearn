# 임베딩 모델 비교 (1-A-3)

2026-10-07, 로컬 Docker(CPU 10코어, 메모리 7.75GiB, GPU 없음)에서 측정. LLM 호출 없음.

- 코퍼스: v1 (매뉴얼만, 청크 85개). 평가셋 72문항 중 근거가 있는 68문항 집계. 1문항이 약 1.5%p다.
- 설정: `md_vector`, `md_hybrid`, 상위 5개 검색
- 측정 도구: `python -m evaluation.embedding_bench --embedding-model <모델>` (모델마다 컨테이너를 따로 띄움)
- 실행 결과 원본: `eval/runs/embedding_bench_*.json` (2차), `eval/runs/first_download/` (1차)

## 추천: 경량 모델 `dragonkue/multilingual-e5-small-ko-v2` 유지

기준은 "경량 모델과 최고 모델의 hit@5 차이가 5%p 미만이면 경량 모델"이다.

| 비교 | 경량 모델 hit@5 | 최고 모델 hit@5 | 차이 |
| --- | --- | --- | --- |
| md_vector끼리 | 83.8 | 88.2 (bge-m3) | 4.4%p (3문항) |
| md_hybrid끼리 | 86.8 | 86.8 (경량 모델이 최고) | 0 |
| 각 모델의 가장 좋은 설정끼리 | 86.8 (md_hybrid) | 88.2 (bge-m3, md_vector) | 1.4%p (1문항) |

어느 쪽으로 비교해도 5%p 미만이므로 경량 모델을 추천한다. 비용 차이도 크다. bge-m3는 색인이 약 20배 느리고 메모리를 2~3배 쓴다.

다만 이 기준이 보지 않는 차이가 하나 있다. **bge-m3의 md_vector는 hit@1이 67.6%로 경량 모델(54.4%)보다 13.2%p(9문항) 높다.** 정답 근거를 1위에 올리는 능력은 bge-m3가 분명히 낫다. 1-B의 리랭커가 hit@1을 올리는 역할이므로 지금은 경량 모델로 가고, 리랭커를 붙인 뒤에도 hit@1이 낮게 남으면 bge-m3를 다시 검토하는 순서를 권한다.

## 검색 품질

| 모델 | 설정 | hit@1 | hit@3 | hit@5 | recall@5 | MRR |
| --- | --- | --- | --- | --- | --- | --- |
| dragonkue/multilingual-e5-small-ko-v2 (기본) | md_vector | 54.4 | 79.4 | 83.8 | 69.9 | 0.669 |
| dragonkue/multilingual-e5-small-ko-v2 (기본) | md_hybrid | 52.9 | 77.9 | 86.8 | 73.5 | 0.665 |
| BAAI/bge-m3 | md_vector | 67.6 | 80.9 | 88.2 | 76.0 | 0.748 |
| BAAI/bge-m3 | md_hybrid | 58.8 | 76.5 | 80.9 | 70.3 | 0.680 |
| intfloat/multilingual-e5-large-instruct | md_vector | 55.9 | 79.4 | 83.8 | 71.3 | 0.680 |
| intfloat/multilingual-e5-large-instruct | md_hybrid | 55.9 | 77.9 | 80.9 | 69.9 | 0.663 |

품질 수치는 두 번 측정해 모두 같았다.

- **대형 모델은 하이브리드에서 오히려 내려간다.** bge-m3는 md_vector 88.2 → md_hybrid 80.9, e5-large-instruct는 83.8 → 80.9다. 벡터 검색이 맞힌 문항을 BM25가 끌어내린다. 경량 모델만 하이브리드에서 오른다(83.8 → 86.8).
- **e5-large-instruct는 경량 모델과 사실상 같다.** md_vector hit@5가 83.8로 같고 hit@1은 1문항 차이다. 크기가 큰 만큼의 이득이 없다.
- bge-m3를 쓴다면 하이브리드가 아니라 벡터 단독이 낫다. 이 경우 지금의 `md_hybrid_glossary` 기본 설정과 맞지 않는다.

## 비용

| 모델 | 색인 시간 (85청크) | 질문 1개 평균 검색 시간 | 프로세스 최대 메모리 | 컨테이너 최대 메모리 | 모델 불러오기 |
| --- | --- | --- | --- | --- | --- |
| dragonkue/multilingual-e5-small-ko-v2 (기본) | 3~9초 | 12~53ms | 약 1.1GB | 0.9~1.2GB | 7~10초 |
| BAAI/bge-m3 | 61~78초 | 128~551ms | 2.6~3.3GB | 1.8~5.0GB | 9초 (첫 실행은 내려받기 포함 245초) |
| intfloat/multilingual-e5-large-instruct | 100~174초 | 185~1,767ms | 약 1.7GB | 1.1~2.3GB | 10초 (첫 실행은 내려받기 포함 163초) |

범위는 두 번 측정한 최소~최대다. **시간과 메모리는 실행마다 크게 흔들렸으므로 자릿수 비교로만 본다.**

- 검색 시간은 md_vector와 md_hybrid 두 설정, 두 번 측정을 모두 합친 범위다. 각 실행에서 먼저 잰 설정이 첫 질문 준비 시간 때문에 더 느리게 나왔다.
- 컨테이너 최대 메모리는 cgroup 값이라 파일 캐시가 포함된다. 첫 실행에서는 모델을 내려받아 쓰는 양이 더해져 크게 나왔다(bge-m3 5.0GB).
- 같은 PC에서 다른 컨테이너 2개(약 1.2GB)가 함께 돌고 있었다.
- 색인은 한 번 만들면 `.cache/index_*.npy`에 남아 다시 만들지 않는다. 매 질문마다 드는 비용은 검색 시간과 메모리다.

## 확정할 때 할 일

- 경량 모델로 확정하면 `.env.example`의 `EMBEDDING_MODEL`은 지금 값 그대로다. 기획서 미정 사항(BUILD_GUIDE 9장)에 확정 내용만 적으면 된다.
- 모델을 바꾸면 평가 규칙대로 1-A-2의 벡터 결과(`pdf_vector`, `md_vector`, `md_hybrid`, `md_hybrid_glossary`)를 모두 다시 잰다.

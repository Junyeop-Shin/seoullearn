# 서울런 멘토 업무 지원 AI 에이전트

서울런 멘토의 반복 업무(매뉴얼 문의, 활동보고서·종합계획서 작성, 멘토 교체 인계)를 돕는 AI 서비스. 지금은 1단계 MVP 중 **매뉴얼 Q&A RAG(리랭커, 문의 초안, pgvector 색인 포함)와 평가 실행기**까지 구현되어 있다.

> 이 저장소는 비공개로 유지한다. 활동가이드 정리본에 원문 내용이 들어 있다.

## 구조

```
ai-server/            Python AI 서버 (FastAPI)
  app/
    config.py         .env 설정 (LLM·임베딩 교체는 여기서)
    llm.py            LLM·임베딩 제공자, 요청 한도 대기·재시도, 응답 캐시
    corpus.py         문서 → 청크 (정리한 마크다운 / 원본 PDF)
    retrieval.py      벡터, BM25, 하이브리드(RRF), 용어집 질의 확장
    guard.py          아동 안전 신호 감지, 개인정보 가리기
    qa.py             검색 → 답변 생성 → 근거·문의처
    pipelines.py      비교할 RAG 설정 목록
    main.py           API (/health, /qa)
  evaluation/
    run_eval.py       평가 실행
    judge.py          LLM 채점 (0~2점)
    metrics.py        지표 계산
    report.py         설정별 비교표
  tests/              오프라인 테스트 (API 키 불필요)
data/                 RAG 원본 문서 (data/README.md)
eval/                 평가셋, 평가 결과, 리포트
forms/                보고서 양식 스키마
synthetic/            가상 멘티 데이터
scripts/              데이터 검증 스크립트
docs/                 개발 지침(BUILD_GUIDE.md)
CLAUDE.md             Claude Code 작업 규칙
```

## 처음 설정

1. `.env.example`을 `.env`로 복사하고 `GOOGLE_API_KEY`를 넣는다.
2. 활동가이드 원본 PDF를 `data/raw/`에 넣는다 (PDF 기본형 비교용, Git에는 올라가지 않음).
3. 이미지를 만들고 테스트를 돌린다.

```bash
docker compose build
docker compose run --rm ai-server python -m unittest discover -s tests -v
```

처음 벡터 검색을 실행할 때 임베딩 모델을 내려받는다(기본 모델 약 0.5GB, 비교용 bge-m3 약 2.3GB). 한 번 받으면 `hf-cache` 볼륨에 남는다.

Docker 없이 할 때:

```bash
cd ai-server
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## 평가 실행 순서

API 무료 한도를 아끼기 위해 **검색만 측정(LLM 호출 없음) → 답변 측정 → 채점** 순서로 간다. 같은 질문·같은 모델 호출은 `.cache/llm_cache.jsonl`에 남아 다시 돌려도 한도를 쓰지 않는다.

```bash
# 1) 검색만 측정: API 호출 0회
docker compose run --rm ai-server python -m evaluation.run_eval --config pdf_vector --corpus v1 --retrieval-only
docker compose run --rm ai-server python -m evaluation.run_eval --config md_vector --corpus v1 --retrieval-only
docker compose run --rm ai-server python -m evaluation.run_eval --config md_hybrid --corpus v1 --retrieval-only

# 1-1) 임베딩 모델 비교: 같은 설정을 bge-m3로 한 번 더 (기본 모델이 거의 같으면 가벼운 쪽을 쓴다)
docker compose run --rm ai-server python -m evaluation.run_eval --config md_vector --corpus v1 --retrieval-only --embedding-model BAAI/bge-m3
docker compose run --rm ai-server python -m evaluation.run_eval --config md_hybrid --corpus v1 --retrieval-only --embedding-model BAAI/bge-m3
docker compose run --rm ai-server python -m evaluation.run_eval --config md_hybrid --corpus v1 --retrieval-only --embedding-model intfloat/multilingual-e5-large-instruct

# 2) 답변까지 측정: 문항당 1회 호출 (70회)
docker compose run --rm ai-server python -m evaluation.run_eval --config md_hybrid --corpus v1

# 3) 채점: 문항당 1회 호출 (70회)
docker compose run --rm ai-server python -m evaluation.judge eval/runs/<2번 결과>.jsonl

# 4) 비교표
docker compose run --rm ai-server python -m evaluation.report eval/runs/*.summary.json
```

먼저 `--limit 5`로 짧게 돌려 응답 형식과 한도를 확인한 뒤 전체를 돌린다. 429 오류가 잦으면 `.env`의 `LLM_RPM`을 낮춘다.

### 비교할 설정 (pipelines.py)

| 설정 | 내용 |
| --- | --- |
| pdf_vector | 기본형: 원본 PDF 고정 길이 청크 + 벡터 검색 |
| pdf_bm25 | 원본 PDF + BM25 (참고) |
| md_vector | 정리한 섹션 문서 + 벡터 검색 |
| md_bm25 | 정리한 섹션 문서 + BM25 (참고) |
| md_hybrid | 섹션 문서 + 벡터·BM25 하이브리드 |
| md_hybrid_glossary | 하이브리드 + 용어집 질의 확장 (API 서버 기본값) |
| md_hybrid_glossary_rerank | 위 설정 + 상위 20개를 cross-encoder 리랭커로 다시 정렬 (`RERANKER_MODEL`) |

리랭커는 첫 번째 결과 적중률을 크게 올리지만 CPU에서는 질문 하나에 10초 안팎이 걸린다. 수치는 `eval/reports/improvement_1b.md` 참고.

코퍼스 `v1`은 매뉴얼만, `v2`는 매뉴얼 + 효력 중인 공지다.

### 지표

| 구분 | 지표 | 의미 |
| --- | --- | --- |
| 검색 | hit@k, recall@k, MRR | 정답 근거가 상위 k개 안에 들어왔는가 |
| 판단 | answerable_acc | 답할 수 있음/일부/없음을 맞혔는가 |
| 판단 | fabrication_rate ↓ | 답이 없는 질문에 답했다고 한 비율 (지어내기 위험) |
| 판단 | over_refusal_rate ↓ | 답이 있는데 못 한다고 한 비율 |
| 연결 | route_acc, safety_route_ok | 문의처를 맞혔는가, 아동 안전 질문을 즉시 연결했는가 |
| 인용 | citation_precision | 답변에 단 근거가 실제 정답 근거인가 |
| 공지 | change_noted_rate | 매뉴얼을 바꾼 공지가 근거일 때 답변이 바뀐 점을 밝혔는가 (v2, 낱말 검사) |
| 채점 | correctness_avg, fully_correct | LLM 채점 점수 (0~2) |

## API 실행

```bash
docker compose up
curl -X POST localhost:8000/qa -H "Content-Type: application/json" -d '{"question": "지각 처리 어떻게 해요?"}'
```

질문 원문은 서버 로그에 남기지 않는다. 이름·전화번호·학교명 등은 LLM에 보내기 전에 가린다.

문의처가 이음단이면 멘토가 보낸 소속 이음단 오픈채팅 주소(`ieumdan_chat_url`, `https://open.kakao.com/...`만 허용)를 `route_link`로 돌려준다. 이 주소는 멘토 브라우저에 저장하고 서버에는 저장하지 않는다.

```bash
curl -X POST localhost:8000/qa -H "Content-Type: application/json" \
  -d '{"question": "보고서 승인이 안 나요", "ieumdan_chat_url": "https://open.kakao.com/o/예시주소"}'
```

답을 다 못 했을 때(`answerable`이 `partial`·`no`)는 문의처에 보낼 글 초안 `inquiry_draft`와 연락 방법 `inquiry_contact`를 함께 돌려준다. 아동 안전 경로에서는 초안을 만들지 않는다.

벡터 색인은 `db` 서비스(PostgreSQL + pgvector)의 `rag_chunks` 테이블에 둔다. 매뉴얼·공지 청크만 들어가고 멘티 관련 데이터는 저장하지 않는다. 평가와 테스트는 DB 없이 `.npy` 파일 방식으로 돈다(`VECTOR_BACKEND=file`). 두 방식의 결과가 같은지는 아래로 확인한다.

```bash
docker compose run --rm ai-server python /project/scripts/compare_vector_backends.py
```

문의처 구분 기준(매칭 전은 운영사무국, 매칭 후 멘토링 운영은 온·오프라인 모두 이음단)은 `data/README.md` 참고.

## 지금까지 측정

- `eval/reports/baseline_retrieval.md`, `embedding_choice.md`, `baseline_answer.md`: 1-A 기준 측정
- `eval/reports/improvement_1b.md`: 1-B 개선을 하나씩 적용하며 다시 잰 결과
- `eval/reports/compare.md`: 전체 비교표

개선 하나를 적용한 뒤에는 `scripts/measure.sh`로 같은 평가셋을 다시 잰다.

## 개발 규칙

- 개발 단계에서는 **실제 멘티 정보를 절대 넣지 않는다.** 가상 데이터(`synthetic/`)만 쓴다.
- 채점 모델(`JUDGE_MODEL`)은 개선 전후를 비교하는 동안 바꾸지 않는다.
- 임베딩 모델을 바꾸면 모든 벡터 결과를 다시 측정한다.
- 용어집·프롬프트를 고칠 때는 평가셋 홀수 번호로 고치고 짝수 번호로 확인한다 (과적합 방지).

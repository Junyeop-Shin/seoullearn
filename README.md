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
    forms/            양식 엔진, 활동보고서·종합계획서 훅, 사전 연락, 목차 파서, 주차별 계획
    router.py         의도 분류 라우터 (LangGraph: 가드 → 규칙 → LLM → qa/report/plan)
    inquiry.py        문의 초안
    vector_store.py   pgvector 벡터 저장소
    main.py           API (/health, /qa, /chat)
  evaluation/
    run_eval.py       평가 실행
    judge.py          LLM 채점 (0~2점)
    metrics.py        지표 계산
    report.py         설정별 비교표
  tests/              오프라인 테스트 (API 키 불필요)
frontend/             Vue 3 화면: 매뉴얼 질문, 사전 연락, 종합계획서, 활동보고서, 보관함 (frontend/README.md)
backend/              Spring Boot 업무 백엔드: 로그인·역할, 양식 스키마 API, AI 서버 중계 (backend/README.md)
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

호출 비용을 아끼기 위해 **검색만 측정(LLM 호출 없음) → 답변 측정 → 채점** 순서로 간다. 평가 실행에서는 같은 질문·같은 모델의 응답이 `.cache/llm_cache.jsonl`에 남아 다시 돌려도 호출하지 않는다(`LLM_CACHE=off`로 끌 수 있다).

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

## 화면 실행

```bash
docker compose up -d frontend ai-server     # backend, db도 함께 뜬다
# http://localhost:3000 에서 멘토 계정을 만들고 시작한다
```

데모 순서와 녹화 대본은 `docs/demo_scenario.md`, 작성 시간 기록표는 `docs/time_measurement.md`, 포트폴리오용 RAG 결과는 `docs/rag_results.md`에 있다.

## API 실행

화면이 쓰는 입구는 backend(`localhost:8080/api`)다. 로그인한 사용자의 `/api/qa`, `/api/chat` 요청을 ai-server로 넘긴다. 로그인 방법과 curl 예시는 `backend/README.md` 참고. 아래는 ai-server를 직접 부르는 방법이다.

```bash
docker compose up
curl -X POST localhost:8000/qa -H "Content-Type: application/json" -d '{"question": "지각 처리 어떻게 해요?"}'
```

질문 원문은 서버 로그에 남기지 않는다. 이름·전화번호·학교명 등은 LLM에 보내기 전에 가린다. API 서버는 LLM 응답을 디스크에 저장하지 않는다(평가 실행만 `.cache/llm_cache.jsonl`을 쓴다).

입력 본문이 로그, DB, 캐시 어디에도 남지 않는지는 아래로 확인한다. 가상 회차 기록으로 `/api/qa`, `/api/chat`을 10번 호출한 뒤 세 곳을 뒤진다. 기능을 추가할 때마다 다시 돌린다.

```bash
docker compose up -d backend
python scripts/check_no_leak.py
```

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

### 보고서 초안 (/drafts)

양식 엔진(`app/forms/`)이 `forms/<form_id>.json` 스키마와 멘토 입력으로 초안을 만든다. 서버에는 아무것도 저장하지 않는다.

| 경로 | 내용 | LLM |
| --- | --- | --- |
| `POST /drafts/activity_report` | 활동보고서 초안. 결석 회차 처리, 제출·증빙 안내 | 멘토가 쓴 사실을 문장으로 다듬기만 |
| `POST /drafts/pre_contact` | 사전 연락 질문지와 문자 초안(90자 단위) | 쓰지 않음 |
| `POST /drafts/course_outline` | 붙여 넣은 강의 목차 → 강 목록 | 규칙으로 못 읽은 줄만 |
| `POST /drafts/weekly_plan` | 16회차 계획. 배분은 규칙 함수 | 회차별 멘토링 내용·상담 문장만 |
| `POST /drafts/plan_initial` | 종합계획서① 초안 (플랫폼 입력용 문자 정리, 수정 불가 경고) | 학습목표·학생진단만 |
| `POST /drafts/plan_file` | 종합계획서② 초안 (서식 항목 순서 텍스트) | 학습목표, 멘토 입력 다듬기 |
| `POST /drafts/split_reports` | 플랫폼에서 복사한 활동보고서 여러 개를 회차별로 분리 | 쓰지 않음 |
| `POST /drafts/completion_report` | 완료보고서 초안. 수행 리스트·통계는 규칙, 감성케어 칸은 멘토 입력만 | 멘토링 내용·성취도 |
| `POST /drafts/handover_summary` | 멘토 교체 인계 요약. 허용 항목 네 가지만, 항목마다 출처 칸만 모아 따로 질의 | 항목별 요약 |
| `POST /drafts/ieumdan_request` | 이음단 장소·일정 요청 메시지. 3일 전 규칙을 날짜 계산으로 확인 | 쓰지 않음 |

- 필드의 `source`에 따라 처리가 갈린다: `user`는 입력 그대로, `placeholder`는 `[멘티명]` 같은 자리표시, `derived`는 규칙 계산, `user_text`는 다듬기, `llm_draft`는 초안.
- 개인정보 칸에 입력이 오면 버리고 경고한다. 5점 척도, 시간, 회차, 날짜 계산은 LLM에 맡기지 않는다.
- LLM이 쓴 문장에 입력에 없는 숫자가 있으면 그 문장을 빼고 경고한다.
- 응답: `draft`(필드별 값), `missing_questions`(되물을 항목), `warnings`, `reminders`(제출·증빙 안내), `pii_masked`.
- 새 양식은 `forms/`에 JSON 파일을 추가하면 `/drafts/<form_id>`로 바로 쓸 수 있고, 화면의 '기타 서식'에도 바로 나온다. 양식별 특수 처리는 `hooks_*.py`의 훅으로 분리한다. 시간확대 신청 전 확인, 친화·성장활동 계획서·결과보고서는 JSON 파일만으로 추가했다.

```bash
docker compose run --rm ai-server python -m evaluation.report_eval [--judge]   # 초안 평가 (eval/report_eval/cases.json)
```

### 활동비 계산기

활동가이드 4-1·4-2(p.41~47)의 기준을 규칙 함수로 옮겼다 (`app/allowance.py`). RAG와 LLM을 쓰지 않는다.

- `POST /tools/allowance`: 유형, 회차 수(정상·무단결석·임박취소), 가산금 구간, 고학년지도·취약계층지원 가산금으로 추정 금액과 내역을 돌려준다. 달마다의 유효 진행 횟수를 넣으면 구간이 언제 오르는지 보여 준다.
- `/chat`에서 "시간당 얼마" 같은 금액 질문이 오면 검색 대신 이 함수로 답한다 (`intent`가 `calc`).
- 금액은 추정값이다. 실제 지급액은 승인 결과와 운영사무국 정산에 따른다.

### 협약 장소 지도

오프라인 멘토링 장소를 자치구별로 찾아보는 화면이다 (`/places`). 장소는 직접 예약하지 않고 이음단에 요청한다.

- 장소 목록은 backend가 파일에서 읽어 내준다 (`GET /api/places`, `PLACES_FILE`). **지금 들어 있는 12곳은 모두 지어낸 예시다** (`synthetic/places.json`). 실제 목록을 받으면 이 파일만 바꾼다.
- 지도는 카카오맵이다. `.env`의 `KAKAO_MAP_JS_KEY`에 JavaScript 키를 넣고, 카카오 개발자 사이트의 플랫폼 > Web에 화면 주소(`http://localhost:3000`)를 등록해야 뜬다.
- 키가 없거나 주소가 등록되지 않았으면 지도 없이 목록과 '카카오맵에서 보기' 링크만 보여 준다.
- 카카오에는 장소 이름과 좌표만 전달된다. 멘티·멘토 정보는 보내지 않는다.

### 답 못 한 질문 모음

매뉴얼로 답하지 못한 질문(`answerable`이 `no`·`partial`)을 모아 운영 측의 매뉴얼 보완 자료로 쓰는 기능이다 (`app/unanswered.py`).
**기본은 꺼져 있다.** 꺼져 있으면 서버는 질문을 어디에도 저장하지 않는다. 운영 기관과 협의한 뒤 `.env`에 `UNANSWERED_LOG=on`을 넣어 켠다.

켜면 이렇게 동작한다.

- 저장하는 것: 가드로 가린 질문 문장, 분류, 문의처, 날짜(일 단위). 누가 물었는지(아이디, 접속 주소, 시각)는 저장하지 않는다.
- 저장하지 않는 질문: 아동 안전 신호가 있는 것, 정서·가정·건강·성적 이야기가 든 것, 150자를 넘는 것(상황 설명일 가능성이 높다).
- 관리자(ADMIN)만 `GET /api/admin/unanswered`, `/api/admin/unanswered/export.csv`로 보고, 항목을 지울 수 있다.
- 모인 질문에 운영 측이 답을 달아 문서로 만들면(`data/notice/`의 공지나 FAQ 형식), 그 문서가 다시 RAG 자료가 되어 같은 질문에 답할 수 있게 된다.

### 의도 분류 라우터 (/chat)

`POST /chat`은 말의 의도를 나눠 처리한다(LangGraph, `app/router.py`). 안전 가드가 먼저 보고, 규칙(키워드)으로 분류한 뒤 애매할 때만 LLM을 부른다.

| intent | 처리 |
| --- | --- |
| qa | `/qa`와 같은 답변, 근거, 문의처, 문의 초안 |
| report | '활동보고서 작성' 화면 안내와 거기서 입력할 항목 목록 |
| plan | '종합계획서 작성' 화면 안내와 입력할 항목 목록 |
| safety | 운영사무국(즉시) 안내. 분류도 LLM 호출도 하지 않는다 |

```bash
curl -X POST localhost:8000/chat -H "Content-Type: application/json" -d '{"message": "3회차 활동보고서 초안 써 줘"}'
docker compose run --rm ai-server python -m evaluation.intent_eval [--llm]   # 분류 정확도 (eval/intent_set.json)
```

문의처 구분 기준(매칭 전은 운영사무국, 매칭 후 멘토링 운영은 온·오프라인 모두 이음단)은 `data/README.md` 참고.

## 지금까지 측정

- `eval/reports/baseline_retrieval.md`, `embedding_choice.md`, `baseline_answer.md`: 1-A 기준 측정
- `eval/reports/improvement_1b.md`: 1-B 개선을 하나씩 적용하며 다시 잰 결과
- `eval/reports/compare.md`: 전체 비교표
- `eval/reports/intent_eval.md`: 의도 분류 측정
- `eval/reports/report_eval.md`, `report_eval_notes.md`: 보고서 초안 평가와 해석

개선 하나를 적용한 뒤에는 `scripts/measure.sh`로 같은 평가셋을 다시 잰다.

## 개발 규칙

- 개발 단계에서는 **실제 멘티 정보를 절대 넣지 않는다.** 가상 데이터(`synthetic/`)만 쓴다.
- 채점 모델(`JUDGE_MODEL`)은 개선 전후를 비교하는 동안 바꾸지 않는다.
- 임베딩 모델을 바꾸면 모든 벡터 결과를 다시 측정한다.
- 용어집·프롬프트를 고칠 때는 평가셋 홀수 번호로 고치고 짝수 번호로 확인한다 (과적합 방지).

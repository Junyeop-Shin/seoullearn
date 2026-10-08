# frontend

Vue 3 화면. 모든 요청은 같은 출처의 `/api`(backend)로만 보낸다.

- Vue 3, vue-router, Vite. 상태 관리 라이브러리는 쓰지 않는다.
- 배포: nginx가 정적 파일을 내주고 `/api`를 backend로 넘긴다 (`nginx.conf`).

## 화면

| 경로 | 화면 | 내용 |
| --- | --- | --- |
| `/login` | 로그인·가입 | 멘토 계정 |
| `/` | 매뉴얼 질문 | 답변, 근거 카드, 문의처 카드(이음단이면 오픈채팅 버튼), 문의 초안, 가린 개인정보 표시 |
| `/pre-contact` | 사전 연락 | 질문지, 90자 단위 문자 초안, 받은 답변 저장 |
| `/plan` | 종합계획서 | 강의 목차 → 주차별 계획 → 종합계획서① → 종합계획서② |
| `/report` | 활동보고서 | 초안 생성, 필드별 수정·복사 |
| `/completion` | 완료보고서 | 활동보고서 16건(보관함 또는 붙여넣기) → 수행 리스트, 멘토링 내용·성취도 초안 |
| `/handover` | 인계 요약 | 출석 패턴, 과제 수행, 학습 태도, 수강 강의·진도 네 가지만 |
| `/ieumdan` | 이음단 요청 | 장소 요청, 일정·장소 변경 메시지 |
| `/admin/unanswered` | 답 못 한 질문 (관리자) | 목록, CSV 내보내기, 삭제 |
| `/vault` | 보관함 | 멘티 별칭별 초안 목록, 파일 내보내기·가져오기, 전체 삭제 |
| `/settings` | 설정 | 소속 이음단 오픈채팅 주소 |

## 구조

```
src/api/client.js          backend 호출 (세션 쿠키, CSRF 토큰, 오류 문구)
src/lib/formFields.js      양식 스키마 → 입력 칸 목록
src/components/SchemaForm.vue    스키마로 입력 칸을 자동으로 그린다
src/components/DraftResult.vue   초안 결과: 되물을 질문, 경고, 필드별 수정·'플랫폼에 복사', 제출 안내
src/components/AnswerCard.vue    답변 카드
src/stores/vault.js        브라우저 보관함 (IndexedDB)
src/stores/settings.js     설정 (localStorage)
src/stores/auth.js         로그인 상태
src/views/                 화면
```

입력 화면은 `GET /api/forms/{formId}`의 스키마로 그린다. 멘토가 직접 넣는 칸(`source`가 `user`, `user_text`)만 입력으로 나오고, 개인정보 칸과 AI·규칙이 채우는 칸은 결과에만 나온다. 양식 JSON에 필드를 추가하면 화면 코드를 고치지 않아도 입력 칸이 생긴다.

## 브라우저에만 두는 것

- 초안과 사전 연락 답변: IndexedDB 보관함. 서버로 보내지 않는다. 형식은 `docs/vault_format.md`.
- 이음단 오픈채팅 주소: localStorage. 질문할 때 `ieumdan_chat_url`로 함께 보내고 서버는 저장하지 않는다.

## 실행

```bash
docker compose up -d frontend ai-server    # http://localhost:3000
```

개발 서버(backend는 8080에 떠 있어야 한다):

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173, /api는 backend로 넘긴다
```

## 테스트

```bash
cd frontend && npm test
```

브라우저 없이 돈다(jsdom, 가짜 IndexedDB). 화면을 실제 브라우저로 끝까지 눌러 보는 점검은 `scripts/e2e_demo.mjs`.

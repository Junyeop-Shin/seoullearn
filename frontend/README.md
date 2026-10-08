# frontend

Vue 3 화면. 모든 요청은 같은 출처의 `/api`(backend)로만 보낸다.

- Vue 3, vue-router, Vite. 상태 관리 라이브러리는 쓰지 않는다.
- 배포: nginx가 정적 파일을 내주고 `/api`를 backend로 넘긴다 (`nginx.conf`).

## 화면

문서는 모두 멘티 아래에서 쓴다. 멘티는 별칭으로만 구분하고 이름·학년·학교·연락처 칸은 없다.

| 경로 | 화면 | 내용 |
| --- | --- | --- |
| `/login` | 로그인·가입 | 멘토 계정 |
| `/` | 매뉴얼 질문 | 답변, 근거 카드, 문의처 카드(이음단이면 오픈채팅 버튼), 문의 초안, 가린 개인정보 표시 |
| `/mentees` | 내 멘티 | 멘티 목록과 다음 할 일, 멘티 추가 |
| `/mentees/:alias` | 멘티 작업 공간 | 기본 정보, 회기 시작 문서, 16회차 목록, 회기 마무리 문서, 자료 내보내기·회기 정리·삭제 |
| `/mentees/:alias/plan` | 종합계획서 | 강의 목차(붙여 넣기 또는 '내 강좌') → 주차별 계획 → 종합계획서① → 종합계획서② |
| `/mentees/:alias/report/:no` | 활동보고서 | 회차별 작성. 저장한 초안은 다시 열어 고친다 |
| `/mentees/:alias/completion` | 완료보고서 | 저장한 활동보고서(또는 붙여 넣기) → 수행 리스트, 멘토링 내용·성취도 초안 |
| `/mentees/:alias/handover` | 인계 요약 | 출석 패턴, 과제 수행, 학습 태도, 수강 강의·진도 네 가지만 |
| `/pre-contact` | 사전 연락 문자 | 매칭 직후 보낼 문자 초안 |
| `/ieumdan` | 이음단 요청 | 장소 요청, 일정·장소 변경 메시지 |
| `/places` | 협약 장소 | 자치구별 장소 목록과 카카오맵 (지금은 가상 장소) |
| `/allowance` | 활동비 계산 | 시간당 금액, 한 달 추정 합계, 달마다의 가산금 구간 |
| `/forms`, `/forms/:formId` | 기타 서식 | 전용 화면이 없는 양식. `forms/`에 JSON을 추가하면 바로 나온다 |
| `/vault` | 백업·복원 | 전체 자료 내보내기·가져오기·삭제 |
| `/settings` | 설정 | 소속 이음단 오픈채팅 주소 |
| `/admin/unanswered` | 답 못 한 질문 (관리자) | 목록, CSV 내보내기, 삭제 |

기본 정보에 적어 둔 과목·강좌·일정·목표는 다른 화면이 불러와 채운다. 활동보고서는 회차 번호와 예상 날짜까지 채우고, 종합계획서는 일정과 '과목 및 시간' 칸, 저장해 둔 강좌 목차를 채운다.

## 구조

```
src/api/client.js          backend 호출 (세션 쿠키, CSRF 토큰, 오류 문구)
src/lib/formFields.js      양식 스키마 → 입력 칸 목록
src/components/SchemaForm.vue    스키마로 입력 칸을 자동으로 그린다
src/components/DraftResult.vue   초안 결과: 되물을 질문, 경고, 필드별 수정·'플랫폼에 복사', 제출 안내
src/components/AnswerCard.vue    답변 카드
src/lib/mentee.js          멘티 기본 정보, 회차 목록, 다음 할 일 계산
src/stores/vault.js        브라우저 보관함 (IndexedDB), 멘티 단위 내보내기·회기 정리
src/stores/settings.js     설정 (localStorage)
src/stores/auth.js         로그인 상태
src/views/                 화면
```

입력 화면은 `GET /api/forms/{formId}`의 스키마로 그린다. 멘토가 직접 넣는 칸(`source`가 `user`, `user_text`)만 입력으로 나오고, 개인정보 칸과 AI·규칙이 채우는 칸은 결과에만 나온다. 양식 JSON에 필드를 추가하면 화면 코드를 고치지 않아도 입력 칸이 생긴다.

## 브라우저에만 두는 것

- 초안, 멘티 정보, 내 강좌: IndexedDB 보관함. 서버로 보내지 않는다. 형식은 `docs/vault_format.md`.
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

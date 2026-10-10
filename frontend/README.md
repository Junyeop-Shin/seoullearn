# frontend

Vue 3 화면. 모든 요청은 같은 출처의 `/api`(backend)로만 보낸다.

- Vue 3, vue-router, Vite. 상태 관리 라이브러리는 쓰지 않는다.
- 배포: nginx가 정적 파일을 내주고 `/api`를 backend로 넘긴다 (`nginx.conf`).

## 화면

멘티 한 명이 메뉴 하나다. 왼쪽 메뉴에서 멘티를 고르면 그 멘티의 지금 단계 화면이 열린다. 설계는 `docs/workflow.md`.

| 경로 | 화면 | 내용 |
| --- | --- | --- |
| `/login` | 로그인·가입 | 멘토 계정. 가입하면 멘토 설정이 먼저 열린다 |
| `/mentees` | 내 멘티 | 멘티 목록과 단계, 예시 멘티 불러오기, AI 다듬기 확인용 멘티 불러오기 |
| `/mentees/new` | 멘티 등록 | 이름, 학년, 과목, 자치구, 방식, 회당 학습시간. 진행 중인 멘티는 회기·단계·회차부터 시작 |
| `/mentees/:alias` | 멘티 화면 | 단계 진행바, 지금 단계의 화면, 이전·다음 단계, 멘티 설정 버튼 |
| `/mentees/:alias/manage` | 멘티 설정 | 멘티 정보 수정, 지난 보고서, 인계 요약 만들기, 보관, 자료 내보내기·삭제 |
| `/mentees/:alias/report/:no` | 활동보고서 | 지난 회차 보고서를 다시 열어 고친다 |
| `/mentees/:alias/completion` | 완료보고서 | 저장한 활동보고서(또는 붙여 넣기) → 수행 리스트, 멘토링 내용·성취도 초안 |
| `/mentees/:alias/handover` | 인계 요약 | 출석 패턴, 과제 수행, 학습 태도, 수강 강의·진도 네 가지만 |
| `/schedule` | 오프라인 일정·장소 | 멘티를 고르면 다음달(또는 이번 달) 일정과 자치구 협약 장소(지도)가 나오고, 이음단에 보낼 문구를 만든다 (AI 미사용, 서버로 보내지 않음) |
| `/` | 매뉴얼 질문 | 답변, 근거 카드, 문의처 카드(이음단이면 이음단 연락처로 가는 버튼), 문의 초안, 가린 개인정보 표시 |
| `/ieumdan` | 이음단 연락처 | 자치구별 이음단 카카오톡 채널 바로가기. 내 멘티의 자치구를 위에 보여 준다 |
| `/places` | 협약 장소 | 자치구별 장소 목록과 카카오맵 (지금은 임시로 넣은 스터디카페. 실제 협약 장소 아님) |
| `/allowance` | 활동비 계산 | 시간당 금액, 한 달 추정 합계, 달마다의 가산금 구간 |
| `/forms`, `/forms/:formId` | 기타 서식 | 전용 화면이 없는 양식. `forms/`에 JSON을 추가하면 바로 나온다 |
| `/settings` | 멘토 설정 | 이름, 연락처, 멘토링 유형, 대학교·전공 |
| `/vault` | 백업·복원 | 전체 자료 내보내기·가져오기·삭제 |
| `/admin/unanswered` | 답 못 한 질문 (관리자) | 목록, CSV 내보내기, 삭제 |

단계는 사전 연락 → 종합계획서 → 활동보고서 → 완료보고서다. 단계별 화면은 `src/views/stages/`에 있다: 사전 연락(`PreContactStage`), 종합계획서(`PlanningStage`: 종합계획서①·② 탭). 활동보고서와 완료보고서 단계는 `ReportView`, `CompletionView`를 멘티 화면 안에 넣어 쓴다.

## 구조

```
src/api/client.js                backend 호출 (세션 쿠키, CSRF 토큰, 오류 문구)
src/lib/stage.js                 단계 규칙: 순서, 다음·이전, 회차 수, 보고서 저장 뒤 전이, 다음 회기
src/lib/mentee.js                멘티 정보, 메뉴 이름, 정규 일정, 개인정보 칸에 채울 값
src/lib/schedule.js              날짜 계산(주차별, 다음달), 문구 템플릿 채우기, 자리표시를 이름으로 바꾸기
src/lib/reports.js               보관함 → 보고서 입력, 이번 주차 계획, 지난 회차 과제, 커리큘럼 줄
src/lib/plan.js                  종합계획서의 항목 형식((1)~(4), (과목역량) 등), 플랫폼용 글자 정리
src/lib/curriculum.js            교육과정 단원 찾기와 주차에 나누는 규칙 (AI·서버 미사용)
src/components/PlaceMap.vue      협약 장소 지도와 목록 (카카오맵)
src/lib/formFields.js            양식 스키마 → 입력 칸 목록
src/components/StageBar.vue      단계 진행바
src/components/CopyBlock.vue     붙여 넣을 글 한 덩어리와 복사 버튼
src/components/CurriculumEditor.vue   주차별 커리큘럼 표와 추천
src/components/DraftResult.vue   초안 결과: 되물을 질문, 경고, 필드별 수정·복사·다시 생성, 이름 칸 채우기
src/components/SchemaForm.vue    스키마로 입력 칸을 자동으로 그린다 (기타 서식, 완료보고서)
src/components/AnswerCard.vue    답변 카드
src/templates/monthly_schedule.md     이음단에 보내는 일정·장소 문구 (이름이 들어가 브라우저에서 만든다)
public/data/curriculum.json           학년·학기·과목별 교육과정 단원 (교과과정으로 채우기의 자료. 출처는 파일의 sources)
src/stores/vault.js              브라우저 보관함 (IndexedDB), 멘티 단위 내보내기
src/stores/settings.js           멘토 설정 (localStorage)
src/stores/auth.js               로그인 상태
src/views/                       화면
```

입력 화면은 `GET /api/forms/{formId}`의 스키마로 그린다. 멘토가 직접 넣는 칸(`source`가 `user`, `user_text`)만 입력으로 나오고, 개인정보 칸과 AI·규칙이 채우는 칸은 결과에만 나온다. 양식 JSON에 필드를 추가하면 화면 코드를 고치지 않아도 입력 칸이 생긴다.

## 브라우저에만 두는 것

- 초안, 멘티 정보(이름·학년 포함), 내 강좌: IndexedDB 보관함. 형식은 `docs/vault_format.md`.
- 멘토 이름·연락처·멘토링 유형·대학교·전공: localStorage.
- 이름, 학년, 연락처, 소속은 서버로 보내지 않는다. 서버가 만든 초안의 `[멘티명]` 같은 자리표시를 화면이 채운다 (`fillValues`, `fillNames`).
- 자치구별 이음단 카카오톡 채널 주소는 공개된 주소라 화면 자료(`public/data/eumdan_channels.json`)로 싣는다. 서버로 보내지 않는다. 주소를 받지 못한 자치구(지금은 동대문구)는 목록에 없다.

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

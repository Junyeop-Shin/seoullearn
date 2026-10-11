# frontend

Vue 3 화면. 모든 요청은 같은 출처의 `/api`(backend)로만 보낸다.

- Vue 3, vue-router, Vite. 상태 관리 라이브러리는 쓰지 않는다.
- 배포: nginx가 정적 파일을 내주고 `/api`를 backend로 넘긴다 (`nginx.conf`).

## 화면

멘티 한 명이 메뉴 하나다. 왼쪽 메뉴에서 멘티를 고르면 그 멘티의 지금 단계 화면이 열린다. 설계는 `docs/workflow.md`.

| 경로 | 화면 | 내용 |
| --- | --- | --- |
| `/login` | 로그인·가입 | 멘토 계정. 가입은 가입 전 동의(항목마다 따로) → 아이디·비밀번호 순서다. 가입하면 멘토 설정이 먼저 열린다 |
| `/privacy` | 개인정보 처리방침 | 로그인 전에도 볼 수 있다. 내용은 `src/lib/privacy.js` 하나에 있고 가입 전 동의 화면과 함께 쓴다 |
| `/mentees` | 내 멘티 | 멘티 목록과 단계, 예시 멘티 불러오기, 단계별 연습용 멘티 불러오기 |
| `/mentees/new` | 멘티 등록 | 이름, 학년, 과목, 자치구, 방식, 회당 학습시간. 진행 중인 멘티는 회기·단계·회차부터 시작 |
| `/mentees/:alias` | 멘티 화면 | 단계 진행바, 지금 단계의 화면, 이전·다음 단계, 멘티 설정 버튼 |
| `/mentees/:alias/manage` | 멘티 설정 | 멘티 정보 수정, 지난 보고서, 인계 요약 만들기, 종료한 멘티로 표시, 자료 내려받기·삭제 |
| `/mentees/:alias/report/:no` | 활동보고서 | 지난 회차 보고서를 다시 열어 고친다 |
| `/mentees/:alias/completion` | 완료보고서 | 화면을 열면 저장한 종합계획서와 활동보고서(또는 붙여 넣기)로 플랫폼의 네 칸 초안을 쓴다 |
| `/mentees/:alias/handover` | 인계 요약 | 출석 패턴, 과제 수행, 학습 태도, 수강 강의·진도 네 가지만 |
| `/schedule` | 오프라인 일정·장소 | 멘티를 고르면 다음달(또는 이번 달) 일정과 자치구 협약 장소(지도)가 나오고, 이음단에 보낼 문구를 만든다 (AI 미사용, 서버로 보내지 않음) |
| `/` | 매뉴얼 질문 | 답변, 근거 카드, 문의처 카드(이음단이면 이음단 연락처로 가는 버튼), 문의 초안, 가린 개인정보 표시 |
| `/ieumdan` | 이음단 연락처 | 자치구별 이음단 카카오톡 채널 바로가기. 내 멘티의 자치구를 위에 보여 준다 |
| `/places` | 협약 장소 | 자치구별 장소 목록과 카카오맵 (지금은 임시로 넣은 스터디카페. 실제 협약 장소 아님) |
| `/allowance` | 활동비 계산 | 시간당 금액, 한 달 추정 합계, 달마다의 가산금 구간 |
| `/bonding` | 친화·성장활동 | 구글폼 바로가기, 신청·결과보고서에 적은 내용 적어 두기, 증빙사진 이름 바꿔 압축 (AI 미사용) |
| `/extension` | 시간확대 요건 확인 | 멘티가 시간확대를 신청할 수 있는지 네 가지 요건 확인, 이음단 채널 바로가기 |
| `/settings` | 멘토 설정 | 이름, 연락처, 멘토링 유형, 대학교·전공. 회원 탈퇴 |
| `/vault` | 백업·복원 | 전체 자료 내보내기·가져오기·삭제 |
| `/admin/unanswered` | 답 못 한 질문 (관리자) | 목록, CSV 내보내기, 삭제 |

단계는 사전 연락 → 종합계획서 → 활동보고서 → 완료보고서다. 단계별 화면은 `src/views/stages/`에 있다: 사전 연락(`PreContactStage`), 종합계획서(`PlanningStage`: 종합계획서①·② 탭). 활동보고서와 완료보고서 단계는 `ReportView`, `CompletionView`를 멘티 화면 안에 넣어 쓴다. 종합계획서②·활동보고서·완료보고서를 저장하면 체크리스트 팝업(`components/ChecklistDialog.vue`, 판단 규칙은 `lib/checklist.js`)이 한 번 뜬다.

## 구조

```
src/api/client.js                backend 호출 (세션 쿠키, CSRF 토큰, 오류 문구)
src/lib/stage.js                 단계 규칙: 순서, 다음·이전, 회차 수, 보고서 저장 뒤 전이, 다음 회기
src/lib/mentee.js                멘티 정보, 메뉴 이름, 정규 일정, 개인정보 칸에 채울 값
src/lib/schedule.js              날짜 계산(주차별, 다음달), 문구 템플릿 채우기, 자리표시를 이름으로 바꾸기
src/lib/report.js                활동보고서 화면의 칸과 규칙 (플랫폼 입력 칸과 같은 구성)
src/lib/reports.js               보관함 → 보고서 입력, 이번 주차 계획, 지난 회차 과제, 커리큘럼 줄, 회기 요약
src/lib/reportSplit.js           플랫폼에서 복사해 붙여 넣은 활동보고서를 회차별로 나누기 (이름 칸이 있어 브라우저에서 한다)
src/lib/plan.js                  종합계획서의 항목 형식((1)~(4), (과목역량) 등), 플랫폼용 글자 정리
src/lib/planFile.js              종합계획서②를 서식 파일(hwpx, docx)에 채워 넣기
src/lib/curriculum.js            교육과정 단원 찾기와 주차에 나누는 규칙 (AI·서버 미사용)
src/lib/checklist.js             보고서 체크리스트의 판단 규칙 (○ △ ✕)과 팝업 상태
src/lib/privacy.js               가입 전 동의와 개인정보 처리방침의 내용 (서버가 받는 정보나 AI 제공사가 바뀌면 시행일과 함께 고친다)
src/lib/allowance.js             활동비 계산에 넣을 한 달치 입력을 저장한 활동보고서에서 만들기
src/lib/photos.js, image.js      인증사진 이름 바꿔 압축, 서버로 보낼 이미지 줄이기
src/lib/channels.js, places.js   이음단 카카오톡 채널, 협약 장소와 카카오맵
src/lib/copy.js, toast.js, reveal.js, formFields.js   복사, 알림, 오류 상자로 스크롤, 초안 값을 글로
src/components/StageBar.vue      단계 진행바
src/components/ChecklistDialog.vue    저장 뒤 뜨는 체크리스트 팝업 (앱 틀이 하나 띄운다)
src/components/ConsentStep.vue   가입 전 동의 (항목마다 따로, 미리 체크하지 않는다)
src/components/CopyBlock.vue     붙여 넣을 글 한 덩어리와 복사 버튼
src/components/CurriculumEditor.vue   주차별 커리큘럼 표
src/components/ReportSource.vue  완료보고서·인계 요약의 재료가 되는 활동보고서 (보관함, 또는 붙여 넣기)
src/components/AnswerCard.vue    답변 카드 (답변 상태, 근거 원문 펼치기, 공지 변경 알림, 문의처, 문의 초안)
src/components/PlaceMap.vue      협약 장소 지도와 목록 (카카오맵)
src/components/MenteePick.vue, MenteeHeader.vue, ExtensionCheck.vue, NavIcon.vue   멘티 고르기, 멘티 머리말, 시간확대 요건, 메뉴 아이콘
src/templates/monthly_schedule.md     이음단에 보내는 일정·장소 문구 (이름이 들어가 브라우저에서 만든다)
public/data/curriculum.json           학년·학기·과목별 교육과정 단원 (교과과정으로 채우기의 자료. 출처는 파일의 sources)
src/stores/vault.js              브라우저 보관함 (IndexedDB), 멘티 단위 내보내기, 다른 탭에 변경 알림
src/stores/settings.js           멘토 설정 (localStorage)
src/stores/auth.js               로그인 상태, 회원 탈퇴
src/stores/chat.js               매뉴얼 질문의 대화 (탭이 열려 있는 동안만, 저장하지 않는다)
src/views/                       화면. 단계 화면은 src/views/stages/
```

화면의 칸은 플랫폼 입력 칸과 서식 파일에 맞춰 화면마다 직접 짰다. 양식 스키마(`GET /api/forms/{formId}`)는 붙여 넣은 활동보고서를 항목 이름으로 나눌 때만 읽는다(`ReportSource`).

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

# 브라우저 보관함 데이터 형식

멘토가 만든 초안은 멘토 브라우저의 IndexedDB에만 저장한다. 서버로 보내지 않는다. 2단계의 완료보고서와 인계 요약은 이 보관함의 활동보고서를 읽어 만든다.

- DB 이름: `seoullearn-mentor-vault` (버전 1)
- 저장소: `items` (키: `id`, 색인: `alias`)
- 코드: `frontend/src/stores/vault.js`

## 항목 (item)

| 필드 | 형식 | 설명 |
| --- | --- | --- |
| `id` | 문자열 | 항목 식별자. 자동 생성 |
| `alias` | 문자열 | 멘티를 구분하는 키. 등록할 때 적은 이름(예: `김OO`)이며 실명 대신 별칭·이니셜을 권한다. 화면 주소에도 쓰인다 |
| `formId` | 문자열 | 양식 이름. `forms/<formId>.json`과 같다. 사전 연락 답변은 `pre_contact` |
| `title` | 문자열 | 목록에 보이는 이름 (예: `활동보고서 3회차`) |
| `sessionNo` | 숫자 또는 null | 회차. 활동보고서에만 있다 |
| `savedAt` | ISO 8601 문자열 | 저장 시각 |
| `inputs` | 객체 | 초안을 만들 때 넣은 입력 (필드 key별) |
| `extra` | 객체 | 필드가 아닌 참고 입력과 화면 상태. 양식별 내용은 아래 표 |
| `draft` | 객체 | 멘토가 고친 최종 초안 (필드 key별 값. 목록 필드는 문자열 배열) |

`draft`의 key는 양식 스키마의 필드 key와 같다. 예를 들어 활동보고서의 `attendance`, `homework`, `lecture_progress`, `progress_scale`은 인계 요약의 허용 항목 재료가 된다 (`forms/handover_summary.json`의 `allow[].from`).

## 양식별로 읽는 법

| `formId` | 2단계에서 쓰는 곳 | 주로 읽는 것 |
| --- | --- | --- |
| `activity_report` | 다음 회차 보고서, 완료보고서(회차별 수행 리스트), 인계 요약 | `sessionNo`, `draft` 전체, `extra.assignedHomework`(`{lecture, task}`: 이번에 낸 과제), `extra.quick`(빠른 입력 원본) |
| `plan_initial` | 종합계획서②, 활동보고서(이번 주차 계획), 완료보고서(학습목표) | `draft`, `extra.memo`(멘토가 적은 메모), `extra.rows`(커리큘럼 표 `[{week, date, time, edited, content, online, mentoring}]`. `online`은 몇 강인지, `mentoring`은 학습 내용, `course`는 그 주차의 강좌 번호. `edited`는 멘토가 그 회차의 일시를 직접 고쳤다는 표시) |
| `plan_file` | 활동보고서(이번 주차 계획), 완료보고서(학습목표 대비 성취도) | `draft.learning_goal`, `extra.rows`, `extra.courses`(수강 강좌 목록 `[{platform, lecture, instructor, done, lectures}]`. 예전 자료는 `extra.course` 하나), `extra.common`(과목, 진행 일정), `extra.alloc`(배분 방식), `extra.value`(칸마다 적은 글), `extra.base`(가져올 때의 종합계획서① 글: 고치지 않은 칸을 가려낸다), `extra.defaults`(규칙으로 만든 멘토링 구성). 예전 자료의 `extra.changed`는 읽지 않는다 |
| `handover_summary` | 다음 멘토의 종합계획서① 인계 요약 칸 | `draft` (`attendance_pattern`, `homework_pattern`, `attitude`, `course_progress`) |
| `completion_report` | 지난 회기 요약의 재료, 보관용 | `draft` 전체 |
| `term_summary` | 다음 회기 종합계획서①의 참고와 AI 재료 | `draft`: `term`, `rounds`, `course`, `goal`, `last_scope`, `next_homework`, `content`, `achievement`, `next_course`(다음 회기에 들을 강좌, 선택). 다음 회기를 시작할 때 만든다. 감성케어 칸은 넣지 않는다 |
| `mentee_profile` | 왼쪽 메뉴, 단계 진행, 모든 화면의 자동 입력 | `draft`: `name`, `grade`, `subject`, `subjectEtc`, `district`, `mode`, `duration`, `course`, `start_datetime`, `regularSchedule`(`[{weekday, startTime}]`), `venue`, `goal`, `level`, `term`, `currentRound`, `stage`, `archived`, `lastHomework`. 연락처·학교 칸은 없다. `stage`가 없는 예전 자료는 저장된 문서로 단계를 짐작한다 (`lib/stage.js`의 `withState`) |
| `course_outline` | (2026-10-11부터 만들지 않음. 예전 자료만 남아 있다) 종합계획서의 강의 목차 (내 강좌) | `title`(강좌 이름), `draft.lectures` (`[{no, title, unit, minutes}]`). `alias`는 항상 `내 강좌` |

읽는 코드는 `frontend/src/lib/reports.js`에 있다 (`reportsFromVault`, `goalsFromVault`, `handoverFromVault`, `curriculumRow`, `previousHomework`).

`draft`의 개인정보 칸에는 서버가 준 자리표시(`[멘티명]`)가 그대로 저장된다. 화면이 보여 줄 때 멘티 정보와 멘토 설정의 값으로 채운다. 멘토 설정(이름, 연락처, 멘토링 유형, 대학교·전공, 이음단 주소)은 보관함이 아니라 localStorage(`seoullearn.settings.v1`)에 있어 내보내기 파일에 들어가지 않는다.

같은 멘티의 활동보고서는 `alias`가 같고 `formId`가 `activity_report`인 항목을 `sessionNo` 순으로 읽는다. 같은 회차가 여러 번 저장돼 있으면 `savedAt`이 가장 늦은 것을 쓴다.

## 내보내기 파일

보관함 화면의 '파일로 내보내기'가 만드는 JSON이다. '파일에서 가져오기'는 같은 `id`를 덮어쓴다.

```json
{
  "format": "seoullearn-mentor-vault",
  "version": 1,
  "exportedAt": "2026-10-08T02:30:00.000Z",
  "items": [
    {
      "id": "mgq1x2-8f3k2a9b",
      "alias": "수학 고2 A",
      "formId": "activity_report",
      "title": "활동보고서 6회차",
      "sessionNo": 6,
      "savedAt": "2026-10-08T02:29:10.000Z",
      "inputs": { "session_no": "6", "status": "출석" },
      "extra": {},
      "draft": { "mentee_name": "[멘티명]", "attendance": "정시에 출석함." }
    }
  ]
}
```

- 가져올 때 `format`이 다르거나 `version`이 더 높으면 받지 않는다.
- 파일에는 초안 내용이 그대로 들어 있다. 멘토가 직접 안전하게 보관해야 한다.

## 회기 정리

멘티 화면의 완료보고서 단계에서 '다음 회기 시작'을 누르면 지난 회기 요약(`term_summary`)을 만든 뒤 그 멘티의 항목 중 `mentee_profile`, `completion_report`, `handover_summary`, `term_summary`만 남기고 나머지(종합계획서, 회차별 활동보고서)를 지우고, 멘티 정보의 회기를 1 올려 종합계획서① 단계로 되돌린다. '이 멘티 자료 내보내기'는 그 멘티의 항목만 같은 파일 형식으로 내보내며, 백업·복원 화면의 '파일에서 가져오기'로 되살린다.

## 형식을 바꿀 때

필드를 더하는 것은 `version`을 올리지 않아도 된다. 필드의 뜻을 바꾸거나 없애면 `version`을 올리고, `vault.js`의 `onupgradeneeded`와 `importAll`에 옛 버전 변환을 넣는다.

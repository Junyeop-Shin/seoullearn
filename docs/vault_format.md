# 브라우저 보관함 데이터 형식

멘토가 만든 초안은 멘토 브라우저의 IndexedDB에만 저장한다. 서버로 보내지 않는다. 2단계의 완료보고서와 인계 요약은 이 보관함의 활동보고서를 읽어 만든다.

- DB 이름: `seoullearn-mentor-vault` (버전 1)
- 저장소: `items` (키: `id`, 색인: `alias`)
- 코드: `frontend/src/stores/vault.js`

## 항목 (item)

| 필드 | 형식 | 설명 |
| --- | --- | --- |
| `id` | 문자열 | 항목 식별자. 자동 생성 |
| `alias` | 문자열 | 멘티 별칭 (예: `수학 고2 A`). 실명을 쓰지 않는다 |
| `formId` | 문자열 | 양식 이름. `forms/<formId>.json`과 같다. 사전 연락 답변은 `pre_contact` |
| `title` | 문자열 | 목록에 보이는 이름 (예: `활동보고서 3회차`) |
| `sessionNo` | 숫자 또는 null | 회차. 활동보고서에만 있다 |
| `savedAt` | ISO 8601 문자열 | 저장 시각 |
| `inputs` | 객체 | 초안을 만들 때 넣은 입력 (필드 key별) |
| `extra` | 객체 | 필드가 아닌 참고 입력. 종합계획서에는 `weekly_plan`(회차 목록)이 들어간다 |
| `draft` | 객체 | 멘토가 고친 최종 초안 (필드 key별 값. 목록 필드는 문자열 배열) |

`draft`의 key는 양식 스키마의 필드 key와 같다. 예를 들어 활동보고서의 `attendance`, `homework`, `lecture_progress`, `progress_scale`은 인계 요약의 허용 항목 재료가 된다 (`forms/handover_summary.json`의 `allow[].from`).

## 양식별로 읽는 법

| `formId` | 2단계에서 쓰는 곳 | 주로 읽는 것 |
| --- | --- | --- |
| `activity_report` | 완료보고서(회차별 수행 리스트), 인계 요약 | `sessionNo`, `draft` 전체 |
| `pre_contact` | 종합계획서① | `draft` (질문 key별 답변), `inputs.mode` |
| `plan_initial` | 종합계획서②, 완료보고서(학습목표) | `draft.learning_goal`, `extra.weekly_plan` |
| `plan_file` | 완료보고서(학습목표 대비 성취도) | `draft.learning_goal` |
| `handover_summary` | 다음 멘토의 종합계획서① 인계 요약 칸 | `draft` (`attendance_pattern`, `homework_pattern`, `attitude`, `course_progress`) |
| `completion_report` | 보관용 | `draft` 전체 |

읽는 코드는 `frontend/src/lib/reports.js`에 있다 (`reportsFromVault`, `goalsFromVault`, `handoverFromVault`).

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

## 형식을 바꿀 때

필드를 더하는 것은 `version`을 올리지 않아도 된다. 필드의 뜻을 바꾸거나 없애면 `version`을 올리고, `vault.js`의 `onupgradeneeded`와 `importAll`에 옛 버전 변환을 넣는다.

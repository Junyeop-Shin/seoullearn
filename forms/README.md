# 양식 스키마

보고서 초안 기능이 쓰는 양식 정의다. 양식 하나 = JSON 파일 하나이며, 새 서식(시간확대 신청서, 친화·성장활동 계획서 등)은 같은 형식의 파일을 추가하면 된다.

| 파일 | 양식 | 단계 |
| --- | --- | --- |
| activity_report.json | 활동보고서 | MVP |
| pre_contact.json | 사전 연락 질문지 | MVP |
| plan_initial.json | 종합계획서① (사전 종합계획서) | MVP |
| plan_file.json | 종합계획서② (종합계획서 파일) | MVP |
| completion_report.json | 완료보고서 | 2차 |
| handover_summary.json | 인계 요약 (허용 항목 목록) | 2차 |
| time_extension_check.json | 시간확대 신청 전 확인 (멘티가 직접 신청하므로 멘토용 확인표) | 3단계 |
| bonding_plan.json | 친화·성장활동 계획서 (신청서) | 3단계 |
| bonding_report.json | 친화·성장활동 결과보고서 | 3단계 |

## 필드 속성

| 속성 | 뜻 |
| --- | --- |
| key / label | 코드용 이름 / 서식에 찍히는 항목명 |
| type | text, integer, date, datetime, date_range, time_range, enum, scale5, list |
| required | 필수 기재 여부 (활동가이드 '필수기재항목' 기준) |
| source | 값을 누가 만드는가 (아래 표) |
| pii | 개인정보 여부. true면 AI에 입력받지 않음 |
| handover | 인계 요약에 넘겨도 되는지 (allow / deny) |
| checklist | 활동가이드 p.32 보고서 작성 체크리스트 번호 |
| rules | 검증 규칙 (시간 범위, 회차 범위, 지어내기 금지 등) |

### source 값

| 값 | 의미 | LLM의 역할 |
| --- | --- | --- |
| user | 멘토가 직접 고르거나 입력 (척도, 시간, 회차, 연장 의사) | 손대지 않음 |
| user_text | 멘토가 짧게 입력한 사실 | 문장으로 다듬기만. 내용 추가 금지 |
| llm_draft | 입력과 근거를 바탕으로 AI가 초안 제안 (학습목표, 커리큘럼 등) | 초안 작성. 멘토 확인 필수 |
| derived | 다른 입력·보고서에서 계산 (수행리스트, 기간) | 코드로 계산 |
| placeholder | 개인정보 칸 | `[멘티명]` 같은 자리표시만 출력 |

## 확인이 필요한 부분

- 활동보고서: 공지 첨부 서식과 활동가이드 부록의 차이 3가지 (activity_report.json의 open_questions)
- 종합계획서①: 플랫폼 칸별 글자 수 제한, 등록 오류를 내는 특수문자 범위
- 인계 요약: 취약 단원 정보 포함 여부

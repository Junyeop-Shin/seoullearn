# backend

Spring Boot 업무 백엔드. 화면(Vue)은 이 서비스의 `/api`로만 요청한다.

- Java 21, Spring Boot 4.1, Gradle
- DB: PostgreSQL (`db` 서비스). backend가 쓰는 테이블은 `app_user`(회원)와 `unanswered_question`(답 못 한 질문 모음) 둘이다

## 하는 일

| 기능 | 경로 | 설명 |
| --- | --- | --- |
| 로그인·역할 | `/api/auth/*`, `/api/admin/*` | 멘토(MENTOR), 관리자(ADMIN). 아이디·비밀번호 해시·역할과 가입 전 동의 기록만 저장한다. 회원 탈퇴는 계정을 바로 지운다 |
| 양식 스키마 | `GET /api/forms`, `GET /api/forms/{formId}` | 저장소의 `forms/*.json`을 그대로 제공한다. 파일을 추가하면 목록에 바로 나온다 |
| AI 서버 중계 | `POST /api/qa`, `POST /api/chat`, `/api/drafts/**`, `/api/tools/**` | 로그인한 사용자의 요청을 ai-server로 넘기고 응답을 그대로 돌려준다 |
| 협약 장소 | `GET /api/places`, `GET /api/config` | 장소 목록 파일을 그대로 내주고, 카카오맵 JavaScript 키(공개 키)를 화면에 알려 준다 |
| 답 못 한 질문 모음 | `GET /api/admin/unanswered`, `GET /api/admin/unanswered/export.csv`, `DELETE /api/admin/unanswered/{id}` | 관리자만. ai-server가 모은 가린 질문 문장을 보고, CSV로 내보내고, 지운다 |

## 저장하지 않는 것

- 실명, 학교, 연락처. `app_user`에는 `id, username, password_hash, role`과 가입 전 동의 기록(`consent_version`: 동의한 문서의 시행일, `consented_at`: 동의한 일시)만 있다.
- 질문, 답변, 보고서 내용. 중계하는 본문은 해석하지도 저장하지도 않는다.
- 예외는 답 못 한 질문 모음이다. ai-server가 가린 질문 문장·분류·문의처·날짜만 `unanswered_question`에 넣는다. 질문한 사람을 알 수 있는 열은 없다.
- 로그에는 `/api` 요청마다 메서드, 경로, 상태 코드, 처리 시간만 남는다(`api-access`). 본문, 쿼리 문자열, 사용자 아이디는 남기지 않는다.

## 로그인 방식

세션 쿠키 로그인이다. 상태를 바꾸는 요청(POST 등)에는 CSRF 토큰이 필요하다.

1. `GET /api/auth/csrf`를 호출하면 `XSRF-TOKEN` 쿠키가 온다.
2. 이후 POST 요청마다 그 값을 `X-XSRF-TOKEN` 헤더에 넣는다. (axios는 자동으로 한다.)

| 경로 | 설명 |
| --- | --- |
| `POST /api/auth/signup` | 멘토 가입. `{"username", "password", "consentVersion", "consents"}`. 아이디는 영문 소문자·숫자·밑줄 4~20자, 비밀번호는 8~72자. 가입 전 동의(필수 항목 `age14, collect, overseas, mentee` 전부)가 없으면 400 |
| `POST /api/auth/reset-request`, `POST /api/auth/reset` | 비밀번호 찾기. 아이디와 가입할 때 적은 전자우편이 맞으면 30분 동안 한 번 쓸 수 있는 재설정 주소를 메일로 보낸다(맞는지는 알려 주지 않는다). SMTP는 `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`, 주소의 앞부분은 `APP_BASE_URL`. 메일 서버 없이 확인하려면 `RESET_LOG_LINK=true`로 띄워 로그의 `password_reset_link`를 연다(개발용) |
| `DELETE /api/auth/me` | 회원 탈퇴(동의 철회). 계정을 바로 지우고 로그아웃한다. 다른 기기에 남은 세션은 그 기기의 다음 요청에서 끊긴다(`AccountSessionFilter`: 로그인할 때 세션에 적어 둔 계정 번호가 DB에 없으면 세션을 끝낸다). 관리자 계정은 안 된다 |
| `POST /api/auth/login` | 로그인 |
| `GET /api/auth/me` | 로그인한 사용자와 역할 |
| `POST /api/auth/logout` | 로그아웃 |

로그인을 10분 안에 10번 틀리면(같은 아이디 + 같은 접속 주소) 10분 동안 잠기고 429를 돌려준다. 잠긴 동안에는 비밀번호가 맞아도 로그인되지 않는다. 한 접속 주소에서 아이디를 바꿔 가며 20번 틀려도 그 주소가 10분 잠긴다. 실패 기록은 서버 메모리에만 있고 DB와 로그에는 남지 않는다.

관리자 계정은 가입으로 만들 수 없다. `.env`에 `ADMIN_USERNAME`, `ADMIN_PASSWORD`를 넣으면 시작할 때 만들어진다.

오류 응답은 ai-server와 같은 `{"detail": "..."}` 모양이다.

## 실행

```bash
docker compose up -d backend        # db, ai-server도 함께 뜬다. http://localhost:8080
```

curl로 확인하는 예:

```bash
J=cookies.txt
curl -s -c $J -b $J localhost:8080/api/auth/csrf -o /dev/null
T=$(grep XSRF-TOKEN $J | awk '{print $7}')
curl -s -c $J -b $J -X POST localhost:8080/api/auth/signup -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $T" \
  -d '{"username":"mentor_test1","password":"test-pass-1234","consentVersion":"2026-10-11","consents":["age14","collect","overseas","mentee"]}'
curl -s -c $J -b $J -X POST localhost:8080/api/auth/login -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $T" \
  -d '{"username":"mentor_test1","password":"test-pass-1234"}'
T=$(grep XSRF-TOKEN $J | awk '{print $7}')
curl -s -c $J -b $J -X POST localhost:8080/api/qa -H 'Content-Type: application/json' -H "X-XSRF-TOKEN: $T" \
  -d '{"question":"지각 처리 어떻게 해요?"}'
```

## 테스트

DB는 메모리 H2, AI 서버는 테스트 안에서 띄우는 가짜 서버를 쓴다. 외부 서비스와 API 키가 필요 없다.

```bash
cd backend && ./gradlew test
```

## 설정 (환경 변수)

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `DATABASE_URL`, `DATABASE_USERNAME`, `DATABASE_PASSWORD` | 로컬 PostgreSQL | DB 접속 |
| `AI_SERVER_URL` | `http://localhost:8000` | ai-server 주소 |
| `FORMS_DIR` | `../forms` | 양식 스키마 폴더 |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | 없음 | 있으면 관리자 계정 생성 |
| `SESSION_COOKIE_SECURE` | `false` | HTTPS로 배포할 때 `true` |

## 배포 전에 할 일

- `SESSION_COOKIE_SECURE=true`, DB 비밀번호 교체
- 로그인 실패 제한은 접속 주소(`remoteAddr`)를 기준으로 센다. 프록시나 로드밸런서 뒤에 두면 모든 사용자가 같은 주소로 보이므로, 배포 구성에 맞춰 전달 헤더 설정(`server.forward-headers-strategy`)을 해야 한다.
- 가입 횟수 제한은 없다.
- 세션은 서버 메모리에 있다. 서버를 다시 띄우면 로그인이 풀리고, 서버를 여러 대로 늘리려면 세션 저장소가 필요하다.

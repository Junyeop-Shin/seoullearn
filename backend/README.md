# backend

Spring Boot 업무 백엔드. 화면(Vue)은 이 서비스의 `/api`로만 요청한다.

- Java 21, Spring Boot 4.1, Gradle
- DB: PostgreSQL (`db` 서비스). 테이블은 `app_user` 하나뿐이다

## 하는 일

| 기능 | 경로 | 설명 |
| --- | --- | --- |
| 로그인·역할 | `/api/auth/*`, `/api/admin/*` | 멘토(MENTOR), 관리자(ADMIN). 아이디·비밀번호 해시·역할만 저장한다 |
| 양식 스키마 | `GET /api/forms`, `GET /api/forms/{formId}` | 저장소의 `forms/*.json`을 그대로 제공한다. 파일을 추가하면 목록에 바로 나온다 |
| AI 서버 중계 | `POST /api/qa`, `POST /api/chat`, `/api/drafts/**` | 로그인한 사용자의 요청을 ai-server로 넘기고 응답을 그대로 돌려준다 |

## 저장하지 않는 것

- 실명, 학교, 연락처, 가입 일시. `app_user`에는 `id, username, password_hash, role` 열만 있다.
- 질문, 답변, 보고서 내용. 중계하는 본문은 해석하지도 저장하지도 않는다.
- 로그에는 `/api` 요청마다 메서드, 경로, 상태 코드, 처리 시간만 남는다(`api-access`). 본문, 쿼리 문자열, 사용자 아이디는 남기지 않는다.

## 로그인 방식

세션 쿠키 로그인이다. 상태를 바꾸는 요청(POST 등)에는 CSRF 토큰이 필요하다.

1. `GET /api/auth/csrf`를 호출하면 `XSRF-TOKEN` 쿠키가 온다.
2. 이후 POST 요청마다 그 값을 `X-XSRF-TOKEN` 헤더에 넣는다. (axios는 자동으로 한다.)

| 경로 | 설명 |
| --- | --- |
| `POST /api/auth/signup` | 멘토 가입. `{"username", "password"}`. 아이디는 영문 소문자·숫자·밑줄 4~20자, 비밀번호는 8~72자 |
| `POST /api/auth/login` | 로그인 |
| `GET /api/auth/me` | 로그인한 사용자와 역할 |
| `POST /api/auth/logout` | 로그아웃 |
| `GET /api/admin/users` | 계정 목록 (ADMIN만) |

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
  -d '{"username":"mentor_test1","password":"test-pass-1234"}'
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
- 로그인 시도 횟수 제한이 없다. 공개 배포 전에 추가해야 한다.
- 세션은 서버 메모리에 있다. 서버를 다시 띄우면 로그인이 풀리고, 서버를 여러 대로 늘리려면 세션 저장소가 필요하다.

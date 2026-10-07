# backend

Spring Boot 업무 백엔드 자리. 지금은 폴더 구조만 있고 코드는 1-C-2 단계에서 만든다.
Java·Spring Boot 버전과 빌드 도구, 패키지 이름은 1-C-2를 시작할 때 정한다.

## 맡을 일 (docs/BUILD_GUIDE.md 1-C-2)

- 로그인과 역할: 멘토(MENTOR), 관리자(ADMIN). 아이디·비밀번호 해시·역할만 저장한다. 실명·학교는 저장하지 않는다.
- 양식 스키마 API: `forms/*.json`을 읽어 `GET /api/forms`, `GET /api/forms/{formId}`로 제공한다.
- AI 서버 중계: `/api/qa`, `/api/chat`, `/api/drafts/**` 요청을 ai-server로 넘긴다.
  요청·응답 본문은 로그에 남기지 않고 상태 코드와 처리 시간만 남긴다.

## 폴더

```
src/main/java/        애플리케이션 코드
src/main/resources/   설정 파일
src/test/java/        테스트
```

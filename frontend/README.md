# frontend

Vue 3 화면 자리. 지금은 폴더 구조만 있고 코드는 1-E 단계에서 만든다.

## 맡을 일 (docs/BUILD_GUIDE.md 1-E)

- 로그인, Q&A 채팅 화면. 모든 요청은 backend(`/api`)로만 보낸다.
- 양식 스키마로 입력 화면을 그리는 양식 컴포넌트 (활동보고서, 사전 연락, 종합계획서①·②).
- 브라우저 보관함(IndexedDB)과 파일 내보내기·가져오기. 초안과 이음단 오픈채팅 주소는 브라우저에만 저장한다.

## 폴더

```
public/           정적 파일
src/api/          backend 호출
src/assets/       이미지·스타일
src/components/   공용 컴포넌트 (양식, 근거·문의처 카드)
src/router/       화면 경로
src/stores/       상태, 브라우저 보관함
src/views/        화면
```

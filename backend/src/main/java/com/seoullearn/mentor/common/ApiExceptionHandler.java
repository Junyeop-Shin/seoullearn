package com.seoullearn.mentor.common;

import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.TypeMismatchException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.ErrorResponse;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** 오류 응답은 AI 서버(FastAPI)와 같은 {"detail": "..."} 모양으로 맞춘다. */
@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Map<String, String>> api(ApiException e) {
        return ResponseEntity.status(e.getStatus()).body(Map.of("detail", e.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, String>> invalid(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getDefaultMessage())
                .findFirst().orElse("입력값을 확인해 주세요.");
        return ResponseEntity.badRequest().body(Map.of("detail", message));
    }

    /** 읽을 수 없는 본문, 형식이 다른 경로 변수(숫자 자리에 글자)는 요청 오류다. */
    @ExceptionHandler({HttpMessageNotReadableException.class, TypeMismatchException.class})
    public ResponseEntity<Map<String, String>> unreadable(Exception e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("detail", "요청 형식을 확인해 주세요."));
    }

    /**
     * 그 밖의 오류. 여기서 잡지 않으면 /error로 넘어가 '로그인이 필요합니다'(401)나 권한 오류(403)로 바뀌어 나간다.
     * 스프링이 정한 요청 오류(405, 415 등)는 그 상태 코드로, 나머지는 500으로 돌려준다. 로그에는 예외 종류만 남긴다.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, String>> other(Exception e) {
        if (e instanceof ErrorResponse known && known.getStatusCode().is4xxClientError()) {
            return ResponseEntity.status(known.getStatusCode()).body(Map.of("detail", "요청 형식을 확인해 주세요."));
        }
        log.warn("unhandled {}", e.getClass().getSimpleName());
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of("detail", "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."));
    }
}

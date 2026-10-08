package com.seoullearn.mentor.common;

import org.springframework.http.HttpStatus;

/** 사용자에게 그대로 보여줄 한국어 안내 문구와 상태 코드를 담는 예외. */
public class ApiException extends RuntimeException {

    private final HttpStatus status;

    public ApiException(HttpStatus status, String message) {
        super(message);
        this.status = status;
    }

    public HttpStatus getStatus() {
        return status;
    }
}

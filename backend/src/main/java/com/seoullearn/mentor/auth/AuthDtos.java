package com.seoullearn.mentor.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public final class AuthDtos {

    private AuthDtos() {
    }

    public record SignupRequest(
            @NotBlank(message = "아이디를 입력해 주세요.")
            @Pattern(regexp = "^[a-z0-9_]{4,20}$", message = "아이디는 영문 소문자, 숫자, 밑줄로 4~20자여야 합니다. 실명이나 학교명은 쓰지 마세요.")
            String username,
            @NotBlank(message = "비밀번호를 입력해 주세요.")
            @Size(min = 8, max = 72, message = "비밀번호는 8~72자여야 합니다.")
            String password) {
    }

    public record LoginRequest(
            @NotBlank(message = "아이디를 입력해 주세요.") String username,
            @NotBlank(message = "비밀번호를 입력해 주세요.") String password) {
    }

    public record UserResponse(String username, Role role) {
    }
}

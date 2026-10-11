package com.seoullearn.mentor.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.util.Set;

public final class AuthDtos {

    private AuthDtos() {
    }

    public record SignupRequest(
            @NotBlank(message = "아이디를 적어 주세요.")
            @Pattern(regexp = "^[a-z0-9_]{4,20}$", message = "아이디는 영문 소문자, 숫자, 밑줄로 4~20자여야 합니다. 실명이나 학교명은 쓰지 마세요.")
            String username,
            @NotBlank(message = "비밀번호를 적어 주세요.")
            @Size(min = 8, max = 72, message = "비밀번호는 8~72자여야 합니다.")
            String password,
            @NotBlank(message = "이메일 주소를 적어 주세요.")
            @Email(message = "이메일 주소를 확인해 주세요.")
            @Size(max = 100, message = "이메일 주소를 확인해 주세요.")
            String email,
            // 가입 전 동의: 화면이 보여 준 문서의 시행일과 동의한 항목 (frontend/src/lib/privacy.js)
            @NotNull(message = "가입 전 동의가 필요합니다.")
            @Pattern(regexp = "^\\d{4}-\\d{2}-\\d{2}$", message = "가입 전 동의가 필요합니다.")
            String consentVersion,
            @NotNull(message = "가입 전 동의가 필요합니다.")
            Set<String> consents) {
    }

    public record LoginRequest(
            // 길이를 묶는다: 가입 규칙(아이디 20자, 비밀번호 72자)을 넘는 값은 어차피 맞을 수 없고, 로그인 실패 기록의 키가 길어지지 않게 한다
            @NotBlank(message = "아이디를 적어 주세요.")
            @Size(max = 20, message = "아이디나 비밀번호가 맞지 않습니다. 다시 확인해 주세요.") String username,
            @NotBlank(message = "비밀번호를 적어 주세요.")
            @Size(max = 72, message = "아이디나 비밀번호가 맞지 않습니다. 다시 확인해 주세요.") String password) {
    }

    public record ResetRequest(
            @NotBlank(message = "아이디를 적어 주세요.")
            @Size(max = 20, message = "아이디는 20자까지입니다. 가입할 때 적은 아이디를 확인해 주세요.") String username,
            @NotBlank(message = "이메일 주소를 적어 주세요.")
            @Size(max = 100, message = "이메일 주소를 확인해 주세요.") String email) {
    }

    public record NewPassword(
            @NotBlank @Size(max = 100) String token,
            @NotBlank(message = "비밀번호를 적어 주세요.")
            @Size(min = 8, max = 72, message = "비밀번호는 8~72자여야 합니다.")
            String password) {
    }

    public record UserResponse(String username, Role role) {
    }
}

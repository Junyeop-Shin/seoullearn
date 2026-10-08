package com.seoullearn.mentor.auth;

import com.seoullearn.mentor.auth.AuthDtos.LoginRequest;
import com.seoullearn.mentor.auth.AuthDtos.SignupRequest;
import com.seoullearn.mentor.auth.AuthDtos.UserResponse;
import com.seoullearn.mentor.common.ApiException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AppUserRepository users;
    private final PasswordEncoder passwordEncoder;
    private final AuthenticationManager authenticationManager;
    private final SecurityContextRepository securityContextRepository;

    public AuthController(AppUserRepository users, PasswordEncoder passwordEncoder,
            AuthenticationManager authenticationManager, SecurityContextRepository securityContextRepository) {
        this.users = users;
        this.passwordEncoder = passwordEncoder;
        this.authenticationManager = authenticationManager;
        this.securityContextRepository = securityContextRepository;
    }

    /** 화면이 처음 열릴 때 호출해 CSRF 토큰 쿠키(XSRF-TOKEN)를 받는다. */
    @GetMapping("/csrf")
    public Map<String, String> csrf(CsrfToken token) {
        return Map.of("headerName", token.getHeaderName(), "token", token.getToken());
    }

    /** 멘토 가입. 관리자 계정은 가입으로 만들 수 없다 (환경 변수로만 만든다). */
    @PostMapping("/signup")
    @ResponseStatus(HttpStatus.CREATED)
    public UserResponse signup(@Valid @RequestBody SignupRequest req) {
        if (users.existsByUsername(req.username())) {
            throw new ApiException(HttpStatus.CONFLICT, "이미 사용 중인 아이디입니다.");
        }
        AppUser user = users.save(new AppUser(req.username(), passwordEncoder.encode(req.password()), Role.MENTOR));
        return new UserResponse(user.getUsername(), user.getRole());
    }

    @PostMapping("/login")
    public UserResponse login(@Valid @RequestBody LoginRequest req, HttpServletRequest request,
            HttpServletResponse response) {
        Authentication auth;
        try {
            auth = authenticationManager.authenticate(
                    UsernamePasswordAuthenticationToken.unauthenticated(req.username(), req.password()));
        } catch (AuthenticationException e) {
            // 아이디가 없는지 비밀번호가 틀렸는지 구분해 알려주지 않는다
            throw new ApiException(HttpStatus.UNAUTHORIZED, "아이디 또는 비밀번호가 올바르지 않습니다.");
        }
        if (request.getSession(false) != null) {
            request.changeSessionId(); // 세션 고정 공격 방지
        }
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(auth);
        SecurityContextHolder.setContext(context);
        securityContextRepository.saveContext(context, request, response);
        return toResponse(auth);
    }

    @GetMapping("/me")
    public UserResponse me(Authentication auth) {
        return toResponse(auth);
    }

    private static UserResponse toResponse(Authentication auth) {
        boolean admin = auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
        return new UserResponse(auth.getName(), admin ? Role.ADMIN : Role.MENTOR);
    }
}

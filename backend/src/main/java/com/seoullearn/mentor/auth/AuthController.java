package com.seoullearn.mentor.auth;

import com.seoullearn.mentor.auth.AuthDtos.LoginRequest;
import com.seoullearn.mentor.auth.AuthDtos.NewPassword;
import com.seoullearn.mentor.auth.AuthDtos.ResetRequest;
import com.seoullearn.mentor.auth.AuthDtos.SignupRequest;
import com.seoullearn.mentor.auth.AuthDtos.UserResponse;
import com.seoullearn.mentor.common.ApiException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.util.Map;
import java.util.Set;
import org.springframework.dao.DataIntegrityViolationException;
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
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    /** 가입 전에 모두 받아야 하는 것: 만 14세 이상 확인, 국외 이전 동의, 이용 수칙(멘티 정보 미입력) 확인. 화면의 frontend/src/lib/privacy.js(CONSENTS)와 같다.
     * 계정 정보의 수집·이용은 계약 이행에 필요한 처리라 동의를 받지 않는다 (화면이 알리기만 한다). */
    static final Set<String> REQUIRED_CONSENTS = Set.of("age14", "overseas", "mentee");

    private final AppUserRepository users;
    private final PasswordEncoder passwordEncoder;
    private final AuthenticationManager authenticationManager;
    private final SecurityContextRepository securityContextRepository;
    private final LoginAttemptLimiter limiter;
    private final Clock clock;
    private final PasswordReset passwordReset;

    public AuthController(AppUserRepository users, PasswordEncoder passwordEncoder,
            AuthenticationManager authenticationManager, SecurityContextRepository securityContextRepository,
            LoginAttemptLimiter limiter, Clock clock, PasswordReset passwordReset) {
        this.passwordReset = passwordReset;
        this.limiter = limiter;
        this.clock = clock;
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

    /**
     * 멘토 가입. 관리자 계정은 가입으로 만들 수 없다 (환경 변수로만 만든다).
     * 가입 전 동의(필수 항목 전부)가 없으면 받지 않고, 동의한 문서의 시행일과 일시를 함께 기록한다.
     */
    @PostMapping("/signup")
    @ResponseStatus(HttpStatus.CREATED)
    public UserResponse signup(@Valid @RequestBody SignupRequest req) {
        if (!req.consents().containsAll(REQUIRED_CONSENTS)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "국외 이전 동의와 확인 항목을 모두 체크해야 가입할 수 있습니다.");
        }
        // 비밀번호 암호화(bcrypt)는 72바이트까지만 받는다. 글자 수 검사는 한글(한 글자 3바이트)을 거르지 못한다
        if (req.password().getBytes(StandardCharsets.UTF_8).length > 72) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "비밀번호가 너무 깁니다. 한글은 24자, 영문·숫자는 72자까지 쓸 수 있습니다.");
        }
        if (users.existsByUsername(req.username())) {
            throw new ApiException(HttpStatus.CONFLICT, "이미 쓰고 있는 아이디입니다. 다른 아이디를 적어 주세요.");
        }
        try {
            AppUser user = users.saveAndFlush(new AppUser(req.username(), passwordEncoder.encode(req.password()), Role.MENTOR)
                    .email(req.email().trim().toLowerCase()).agreed(req.consentVersion(), clock.instant()));
            return new UserResponse(user.getUsername(), user.getRole());
        } catch (DataIntegrityViolationException e) {   // 같은 아이디로 동시에 가입한 경우
            throw new ApiException(HttpStatus.CONFLICT, "이미 쓰고 있는 아이디입니다. 다른 아이디를 적어 주세요.");
        }
    }

    /**
     * 회원 탈퇴(동의 철회). 계정(아이디, 비밀번호 해시, 동의 기록)을 바로 지우고 로그아웃한다.
     * 다른 기기에 남은 세션은 그 기기의 다음 요청에서 끊긴다 (AccountSessionFilter).
     * 멘티 자료는 서버에 없다 (멘토의 브라우저에만 있다).
     */
    @DeleteMapping("/me")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Transactional
    public void withdraw(Authentication auth, HttpServletRequest request) {
        if (toResponse(auth).role() == Role.ADMIN) {
            throw new ApiException(HttpStatus.FORBIDDEN, "관리자 계정은 여기서 탈퇴할 수 없습니다.");
        }
        users.deleteByUsername(auth.getName());
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        SecurityContextHolder.clearContext();
    }

    /** 비밀번호 재설정 메일을 청한다. 아이디와 전자우편이 맞는지 알려 주지 않으려고 언제나 같은 응답을 준다. */
    @PostMapping("/reset-request")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void resetRequest(@Valid @RequestBody ResetRequest req) {
        passwordReset.request(req.username(), req.email());
    }

    /** 메일로 받은 주소의 값(token)으로 새 비밀번호를 정한다. */
    @PostMapping("/reset")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Transactional
    public void reset(@Valid @RequestBody NewPassword req) {
        if (req.password().getBytes(StandardCharsets.UTF_8).length > 72) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "비밀번호가 너무 깁니다. 한글은 24자, 영문·숫자는 72자까지 쓸 수 있습니다.");
        }
        Long id = passwordReset.redeem(req.token());
        AppUser user = id == null ? null : users.findById(id).orElse(null);
        if (user == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "재설정 주소가 만료됐거나 이미 썼습니다. 비밀번호 찾기를 다시 해 주세요.");
        }
        user.changePassword(passwordEncoder.encode(req.password()));
    }

    @PostMapping("/login")
    public UserResponse login(@Valid @RequestBody LoginRequest req, HttpServletRequest request,
            HttpServletResponse response) {
        String address = request.getRemoteAddr();
        Duration locked = limiter.lockedFor(req.username(), address);
        if (!locked.isZero()) {
            // 잠긴 동안에는 비밀번호가 맞아도 확인하지 않는다
            long minutes = Math.max(1, (locked.toSeconds() + 59) / 60);
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS,
                    "로그인 시도가 너무 많습니다. " + minutes + "분 후에 다시 시도해 주세요.");
        }
        Authentication auth;
        try {
            auth = authenticationManager.authenticate(
                    UsernamePasswordAuthenticationToken.unauthenticated(req.username(), req.password()));
        } catch (AuthenticationException e) {
            // 없는 아이디도 똑같이 센다. 아이디가 없는지 비밀번호가 틀렸는지 구분해 알려주지 않는다
            limiter.recordFailure(req.username(), address);
            throw new ApiException(HttpStatus.UNAUTHORIZED, "아이디나 비밀번호가 맞지 않습니다. 다시 확인해 주세요.");
        }
        limiter.recordSuccess(req.username(), address);
        if (request.getSession(false) != null) {
            request.changeSessionId(); // 세션 고정 공격 방지
        }
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(auth);
        SecurityContextHolder.setContext(context);
        securityContextRepository.saveContext(context, request, response);
        // 계정 번호와 비밀번호 해시를 세션에 적어 둔다: 탈퇴하거나 비밀번호를 재설정하면 다른 기기에 남은 세션도 다음 요청에서 끊긴다 (AccountSessionFilter)
        users.findByUsername(auth.getName()).ifPresent(u -> {
            request.getSession().setAttribute(AccountSessionFilter.ACCOUNT_ID, u.getId());
            request.getSession().setAttribute(AccountSessionFilter.PW, u.getPasswordHash());
        });
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

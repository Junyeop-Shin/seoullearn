package com.seoullearn.mentor.auth;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import java.io.IOException;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 탈퇴했거나 지워진 계정의 남은 세션을 끊는다 (다른 기기에 로그인해 둔 세션).
 * 로그인할 때 세션에 적어 둔 계정 번호가 DB에 없으면 세션을 끝낸다. 뒤의 보안 필터가 로그인하지 않은 요청으로 보고 401을 돌려준다.
 * 아이디가 아니라 계정 번호로 확인한다: 같은 아이디로 다시 가입한 계정을 옛 세션이 건드리지 못한다.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
public class AccountSessionFilter extends OncePerRequestFilter {

    static final String ACCOUNT_ID = "accountId";

    static final String PW = "pw";

    private final AppUserRepository users;

    public AccountSessionFilter(AppUserRepository users) {
        this.users = users;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/api/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        HttpSession session = request.getSession(false);
        // 계정이 없어졌거나(탈퇴) 비밀번호가 바뀌었으면(재설정) 그 전에 만든 세션은 끊는다
        if (session != null && session.getAttribute(ACCOUNT_ID) instanceof Long id
                && !users.findById(id).map(u -> u.getPasswordHash().equals(session.getAttribute(PW))).orElse(false)) {
            session.invalidate();
        }
        chain.doFilter(request, response);
    }
}

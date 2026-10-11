package com.seoullearn.mentor.auth;

import java.security.SecureRandom;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Component;

/**
 * 비밀번호 재설정. 아이디와 가입할 때 적은 전자우편이 맞으면 한 번만 쓸 수 있는 주소를 메일로 보낸다 (30분 동안 유효).
 * 재설정 값은 메모리에만 둔다 (로그인 실패 기록과 같다: 서버를 다시 띄우면 사라지고, 그때는 다시 청하면 된다).
 * 로그에는 아이디와 주소를 남기지 않는다.
 */
@Component
public class PasswordReset {

    private static final Logger log = LoggerFactory.getLogger(PasswordReset.class);
    private static final Duration VALID = Duration.ofMinutes(30);

    private record Pending(Long userId, Instant expires) {
    }

    private final Map<String, Pending> pending = new ConcurrentHashMap<>();
    private final SecureRandom random = new SecureRandom();
    private final AppUserRepository users;
    private final ObjectProvider<JavaMailSender> mail;
    private final Clock clock;
    private final String mailHost;
    private final String from;
    private final String baseUrl;
    private final boolean logLink;

    public PasswordReset(AppUserRepository users, ObjectProvider<JavaMailSender> mail, Clock clock,
            @Value("${spring.mail.host:}") String mailHost, @Value("${app.mail-from:}") String from,
            @Value("${app.base-url}") String baseUrl, @Value("${app.reset-log-link:false}") boolean logLink) {
        this.users = users;
        this.mail = mail;
        this.clock = clock;
        this.mailHost = mailHost;
        this.from = from;
        this.baseUrl = baseUrl;
        this.logLink = logLink;
    }

    /** 아이디와 전자우편이 맞으면 재설정 주소를 보낸다. 맞지 않아도 아무것도 알려 주지 않는다. */
    public void request(String username, String email) {
        Instant now = clock.instant();
        pending.values().removeIf(p -> p.expires().isBefore(now));
        AppUser user = users.findByUsername(username.trim()).orElse(null);
        if (user == null || user.getEmail() == null || !user.getEmail().equalsIgnoreCase(email.trim())) {
            return;
        }
        byte[] bytes = new byte[32];
        random.nextBytes(bytes);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        pending.values().removeIf(p -> p.userId().equals(user.getId()));   // 새로 청하면 앞의 주소는 못 쓴다
        pending.put(token, new Pending(user.getId(), now.plus(VALID)));
        String link = baseUrl + "/login?reset=" + token;
        if (logLink) {
            log.info("password_reset_link {}", link);
        }
        JavaMailSender sender = mailHost.isBlank() ? null : mail.getIfAvailable();
        if (sender == null) {
            log.warn("password_reset mail_not_configured");
            return;
        }
        SimpleMailMessage m = new SimpleMailMessage();
        if (!from.isBlank()) {
            m.setFrom(from);
        }
        m.setTo(user.getEmail());
        m.setSubject("[서울런 멘토 도우미] 비밀번호 재설정 안내");
        m.setText("아래 주소를 열어 새 비밀번호를 정해 주세요. 30분 동안 한 번만 쓸 수 있습니다.\n\n" + link
                + "\n\n비밀번호 찾기를 누른 적이 없다면 이 메일은 무시하셔도 됩니다.");
        try {
            sender.send(m);
        } catch (Exception e) {
            log.warn("password_reset mail_failed type={}", e.getClass().getSimpleName());
        }
    }

    /** 재설정 값이 유효하면 그 계정 번호를 돌려주고 값을 없앤다. 아니면 null. */
    public Long redeem(String token) {
        Pending p = pending.remove(token);
        return p == null || p.expires().isBefore(clock.instant()) ? null : p.userId();
    }
}

package com.seoullearn.mentor.auth;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/** ADMIN_USERNAME, ADMIN_PASSWORD 환경 변수가 있으면 시작할 때 관리자 계정을 만든다. 이미 있으면 건드리지 않는다. */
@Component
public class AdminSeeder implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(AdminSeeder.class);

    private final AppUserRepository users;
    private final PasswordEncoder passwordEncoder;
    private final String username;
    private final String password;

    public AdminSeeder(AppUserRepository users, PasswordEncoder passwordEncoder,
            @Value("${app.admin.username:}") String username, @Value("${app.admin.password:}") String password) {
        this.users = users;
        this.passwordEncoder = passwordEncoder;
        this.username = username;
        this.password = password;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (username.isBlank() || password.isBlank()) {
            return;
        }
        if (password.length() < 8) {
            log.warn("관리자 계정을 만들지 않았습니다: ADMIN_PASSWORD는 8자 이상이어야 합니다.");
            return;
        }
        if (!users.existsByUsername(username)) {
            users.save(new AppUser(username, passwordEncoder.encode(password), Role.ADMIN));
            log.info("관리자 계정을 만들었습니다.");
        } else if (users.findByUsername(username).orElseThrow().getRole() != Role.ADMIN) {
            log.warn("관리자 계정을 만들지 않았습니다: 같은 아이디의 멘토 계정이 이미 있습니다.");
        }
    }
}

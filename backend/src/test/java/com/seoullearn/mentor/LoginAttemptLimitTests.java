package com.seoullearn.mentor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.seoullearn.mentor.auth.LoginAttemptLimiter;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

/** 로그인 실패 횟수 제한. 시간은 테스트가 직접 움직이는 시계로 흘려보낸다. */
@SpringBootTest
class LoginAttemptLimitTests {

    static class MovableClock extends Clock {
        Instant now = Instant.parse("2026-10-08T00:00:00Z");

        @Override
        public Instant instant() {
            return now;
        }

        @Override
        public ZoneId getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }
    }

    @TestConfiguration
    static class Config {
        @Bean
        @Primary
        MovableClock testClock() {
            return new MovableClock();
        }
    }

    @Autowired
    WebApplicationContext context;
    @Autowired
    MovableClock clock;

    MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.webAppContextSetup(context).apply(springSecurity()).build();
        clock.now = clock.now.plus(Duration.ofHours(1)); // 앞 테스트의 실패 기록이 모두 만료되도록
    }

    private ResultActions login(String username, String password, String address) throws Exception {
        return mvc.perform(post("/api/auth/login").with(csrf()).with(r -> {
            r.setRemoteAddr(address);
            return r;
        }).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"" + username + "\", \"password\": \"" + password + "\"}"));
    }

    private void signup(String username) throws Exception {
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"" + username + "\", \"password\": \"mentor-pass-1\", \"email\": \"m@example.com\", \"consentVersion\": \"2026-10-11\","
                        + " \"consents\": [\"age14\", \"overseas\", \"mentee\"]}"))
                .andExpect(status().isCreated());
    }

    @Test
    void locksAfterTenFailuresEvenWithRightPasswordThenUnlocks() throws Exception {
        signup("limit_a1");
        for (int i = 0; i < 10; i++) {
            login("limit_a1", "wrong-pass-" + i, "10.0.0.1").andExpect(status().isUnauthorized());
        }
        login("limit_a1", "mentor-pass-1", "10.0.0.1").andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.detail").value("로그인 시도가 너무 많습니다. 10분 후에 다시 시도해 주세요."));
        // 다른 곳에서 접속한 같은 사용자는 잠기지 않는다 (남이 일부러 잠그는 것을 막는다)
        login("limit_a1", "mentor-pass-1", "10.0.0.2").andExpect(status().isOk());
        clock.now = clock.now.plus(Duration.ofMinutes(10)).plusSeconds(1);
        login("limit_a1", "mentor-pass-1", "10.0.0.1").andExpect(status().isOk());
    }

    @Test
    void successResetsCountAndOldFailuresExpire() throws Exception {
        signup("limit_b1");
        for (int i = 0; i < 9; i++) {
            login("limit_b1", "wrong-pass-" + i, "10.0.1.1").andExpect(status().isUnauthorized());
        }
        login("limit_b1", "mentor-pass-1", "10.0.1.1").andExpect(status().isOk());
        for (int i = 0; i < 9; i++) {
            login("limit_b1", "wrong-pass-" + i, "10.0.1.1").andExpect(status().isUnauthorized());
        }
        clock.now = clock.now.plus(Duration.ofMinutes(11)); // 10분이 지나면 앞의 실패는 세지 않는다
        login("limit_b1", "wrong-pass-x", "10.0.1.1").andExpect(status().isUnauthorized());
        login("limit_b1", "mentor-pass-1", "10.0.1.1").andExpect(status().isOk());
    }

    @Test
    void unknownUsernamesAreCountedTheSameWay() throws Exception {
        for (int i = 0; i < 10; i++) {
            login("nobody_zz", "wrong-pass-" + i, "10.0.2.1").andExpect(status().isUnauthorized());
        }
        login("nobody_zz", "wrong-pass-9", "10.0.2.1").andExpect(status().isTooManyRequests());
    }

    @Test
    void manyFailuresFromOneAddressLockThatAddress() throws Exception {
        signup("limit_c1");
        for (int i = 0; i < 20; i++) {
            login("guess_" + (i % 10) + "x", "wrong-pass-1", "10.0.3.1").andExpect(status().isUnauthorized());
        }
        login("limit_c1", "mentor-pass-1", "10.0.3.1").andExpect(status().isTooManyRequests());
        login("limit_c1", "mentor-pass-1", "10.0.3.2").andExpect(status().isOk());
    }

    @Test
    void limiterKeepsNothingAfterLockExpires() {
        MovableClock c = new MovableClock();
        LoginAttemptLimiter limiter = new LoginAttemptLimiter(c);
        for (int i = 0; i < 10; i++) {
            limiter.recordFailure("someone", "10.9.9.9");
        }
        assertThat(limiter.lockedFor("someone", "10.9.9.9")).isEqualTo(Duration.ofMinutes(10));
        assertThat(limiter.lockedFor("SOMEONE", "10.9.9.9")).isEqualTo(Duration.ofMinutes(10)); // 대소문자로 우회 불가
        c.now = c.now.plus(Duration.ofMinutes(10));
        assertThat(limiter.lockedFor("someone", "10.9.9.9")).isZero();
    }
}

package com.seoullearn.mentor.auth;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;

/**
 * 로그인 실패 횟수 제한. 비밀번호를 계속 넣어 보는 시도를 막는다.
 * - 같은 아이디 + 같은 접속 주소: 10분 안에 5번 틀리면 10분 동안 잠근다.
 * - 같은 접속 주소 전체: 10분 안에 20번 틀리면 10분 동안 잠근다 (아이디를 바꿔 가며 시도하는 경우).
 * 기록은 서버 메모리에만 두고 DB와 로그에는 남기지 않는다. 서버를 다시 띄우면 지워진다.
 */
@Component
public class LoginAttemptLimiter {

    static final int MAX_PER_ACCOUNT = 5;
    static final int MAX_PER_ADDRESS = 20;
    static final Duration WINDOW = Duration.ofMinutes(10);
    static final Duration LOCK = Duration.ofMinutes(10);
    private static final int MAX_ENTRIES = 10_000;

    private record Entry(int failures, Instant windowStart, Instant lockedUntil) {
    }

    private final Map<String, Entry> entries = new ConcurrentHashMap<>();
    private final Clock clock;

    public LoginAttemptLimiter(Clock clock) {
        this.clock = clock;
    }

    /** 잠겨 있으면 풀릴 때까지 남은 시간, 아니면 0. */
    public Duration lockedFor(String username, String address) {
        Instant now = clock.instant();
        Duration a = remaining(entries.get(accountKey(username, address)), now);
        Duration b = remaining(entries.get(addressKey(address)), now);
        return a.compareTo(b) >= 0 ? a : b;
    }

    public void recordFailure(String username, String address) {
        Instant now = clock.instant();
        if (entries.size() >= MAX_ENTRIES) {
            entries.entrySet().removeIf(e -> expired(e.getValue(), now));
        }
        bump(accountKey(username, address), MAX_PER_ACCOUNT, now);
        bump(addressKey(address), MAX_PER_ADDRESS, now);
    }

    public void recordSuccess(String username, String address) {
        entries.remove(accountKey(username, address));
    }

    private void bump(String key, int max, Instant now) {
        entries.compute(key, (k, e) -> {
            if (e == null || expired(e, now)) {
                e = new Entry(0, now, null);
            }
            int failures = e.failures() + 1;
            return new Entry(failures, e.windowStart(), failures >= max ? now.plus(LOCK) : null);
        });
    }

    private static boolean expired(Entry e, Instant now) {
        if (e.lockedUntil() != null) {
            return !now.isBefore(e.lockedUntil());
        }
        return now.isAfter(e.windowStart().plus(WINDOW));
    }

    private static Duration remaining(Entry e, Instant now) {
        if (e == null || e.lockedUntil() == null || !now.isBefore(e.lockedUntil())) {
            return Duration.ZERO;
        }
        return Duration.between(now, e.lockedUntil());
    }

    private static String accountKey(String username, String address) {
        return "u:" + String.valueOf(username).toLowerCase() + "|" + address;
    }

    private static String addressKey(String address) {
        return "a:" + address;
    }
}

package com.seoullearn.mentor.proxy;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** AI 서버 주소와 응답 대기 시간. */
@ConfigurationProperties("app.ai-server")
public record AiServerProperties(String url, Duration connectTimeout, Duration readTimeout) {
}

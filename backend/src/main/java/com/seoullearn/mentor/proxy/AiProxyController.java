package com.seoullearn.mentor.proxy;

import jakarta.servlet.http.HttpServletRequest;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * AI 서버 중계. 로그인한 사용자의 요청을 ai-server로 넘기고 응답을 그대로 돌려준다.
 * 본문은 읽어서 해석하지도, 로그나 DB에 남기지도 않는다. 기록은 ApiAccessLogFilter의 상태 코드와 처리 시간뿐이다.
 */
@RestController
public class AiProxyController {

    private static final String PREFIX = "/api";

    private final AiServerProperties props;
    private final HttpClient client;

    public AiProxyController(AiServerProperties props) {
        this.props = props;
        // HTTP/1.1로 고정한다. 기본값(HTTP/2 업그레이드 시도)으로 보내면 uvicorn이 요청 본문을 받지 못한다
        this.client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(props.connectTimeout()).build();
    }

    @PostMapping({"/api/qa", "/api/chat"})
    public ResponseEntity<byte[]> post(HttpServletRequest request, @RequestBody(required = false) byte[] body)
            throws InterruptedException {
        return forward(request, body);
    }

    /** 보고서 초안 API. ai-server에 /drafts/** 가 생기면 그대로 쓰인다. */
    @RequestMapping("/api/drafts/**")
    public ResponseEntity<byte[]> drafts(HttpServletRequest request, @RequestBody(required = false) byte[] body)
            throws InterruptedException {
        return forward(request, body);
    }

    private ResponseEntity<byte[]> forward(HttpServletRequest request, byte[] body) throws InterruptedException {
        String path = request.getRequestURI().substring(PREFIX.length());
        if (path.contains("..")) {
            return error(HttpStatus.BAD_REQUEST, "요청 경로를 확인해 주세요.");
        }
        String query = request.getQueryString();
        URI target = URI.create(props.url() + path + (query == null ? "" : "?" + query));
        HttpRequest.Builder out = HttpRequest.newBuilder(target).timeout(props.readTimeout())
                .method(request.getMethod(), body == null || body.length == 0
                        ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofByteArray(body));
        // 쿠키와 인증 헤더는 넘기지 않는다. 내용 형식만 전달한다
        String contentType = request.getContentType();
        if (contentType != null) {
            out.header(HttpHeaders.CONTENT_TYPE, contentType);
        }
        out.header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE);
        try {
            HttpResponse<byte[]> res = client.send(out.build(), HttpResponse.BodyHandlers.ofByteArray());
            String type = res.headers().firstValue(HttpHeaders.CONTENT_TYPE).orElse(MediaType.APPLICATION_JSON_VALUE);
            return ResponseEntity.status(res.statusCode()).header(HttpHeaders.CONTENT_TYPE, type).body(res.body());
        } catch (HttpTimeoutException e) {
            return error(HttpStatus.GATEWAY_TIMEOUT, "답변을 만드는 데 시간이 너무 오래 걸렸습니다. 잠시 후 다시 시도해 주세요.");
        } catch (IOException e) {
            return error(HttpStatus.BAD_GATEWAY, "AI 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.");
        }
    }

    private static ResponseEntity<byte[]> error(HttpStatus status, String detail) {
        byte[] json = ("{\"detail\": \"" + detail + "\"}").getBytes(StandardCharsets.UTF_8);
        return ResponseEntity.status(status).contentType(MediaType.APPLICATION_JSON).body(json);
    }
}

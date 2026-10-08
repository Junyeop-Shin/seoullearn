package com.seoullearn.mentor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.seoullearn.mentor.auth.AppUser;
import com.seoullearn.mentor.auth.AppUserRepository;
import com.seoullearn.mentor.common.ApiAccessLogFilter;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

/** DB는 메모리 H2, AI 서버는 테스트 안에서 띄운 가짜 서버를 쓴다. 외부 서비스와 API 키가 필요 없다. */
@SpringBootTest
@ExtendWith(OutputCaptureExtension.class)
class BackendApiTests {

    // 가상 문장. 로그·DB에 남으면 안 되는 본문 조각 확인용
    private static final String QUESTION = "가람중 멘티가 지각했는데 어떻게 처리하나요 010-0000-1234";
    private static final String AI_ANSWER = "30분 이내는 지각으로 처리합니다";

    private static final List<String> aiRequests = new CopyOnWriteArrayList<>();
    private static final List<String> aiCookies = new CopyOnWriteArrayList<>();
    private static HttpServer fakeAi;

    @Autowired
    WebApplicationContext context;
    @Autowired
    AppUserRepository users;
    @Autowired
    JdbcTemplate jdbc;
    @Autowired
    ApiAccessLogFilter accessLogFilter;

    MockMvc mvc;

    @DynamicPropertySource
    static void aiServer(DynamicPropertyRegistry registry) throws IOException {
        fakeAi = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        fakeAi.createContext("/", exchange -> {
            String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            aiRequests.add(exchange.getRequestMethod() + " " + exchange.getRequestURI() + " " + body);
            aiCookies.add(String.valueOf(exchange.getRequestHeaders().getFirst("Cookie")));
            String path = exchange.getRequestURI().getPath();
            int code = path.equals("/qa") || path.equals("/chat") || path.startsWith("/drafts/") ? 200 : 404;
            if (body.contains("한도")) {
                code = 503;
            }
            byte[] out = (code == 200 ? "{\"answer\": \"" + AI_ANSWER + "\", \"intent\": \"qa\"}"
                    : "{\"detail\": \"가짜 서버 오류\"}").getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(code, out.length);
            exchange.getResponseBody().write(out);
            exchange.close();
        });
        fakeAi.start();
        registry.add("app.ai-server.url", () -> "http://127.0.0.1:" + fakeAi.getAddress().getPort());
    }

    @AfterAll
    static void stop() {
        fakeAi.stop(0);
    }

    @BeforeEach
    void setUp() {
        // 실제 서버에서는 서블릿 필터로 자동 등록된다. MockMvc에는 직접 넣는다
        mvc = MockMvcBuilders.webAppContextSetup(context).addFilters(accessLogFilter).apply(springSecurity()).build();
        aiRequests.clear();
        aiCookies.clear();
    }

    private MockHttpSession login(String username, String password) throws Exception {
        MockHttpSession session = new MockHttpSession();
        mvc.perform(post("/api/auth/login").with(csrf()).session(session).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"" + username + "\", \"password\": \"" + password + "\"}"))
                .andExpect(status().isOk());
        return session;
    }

    private MockHttpSession mentor(String username) throws Exception {
        if (!users.existsByUsername(username)) {
            mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                    .content("{\"username\": \"" + username + "\", \"password\": \"mentor-pass-1\"}"))
                    .andExpect(status().isCreated());
        }
        return login(username, "mentor-pass-1");
    }

    // ------------------------------------------------------------ 로그인과 역할
    @Test
    void signupStoresOnlyUsernameHashAndRole() throws Exception {
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_a1\", \"password\": \"mentor-pass-1\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.role").value("MENTOR"))
                .andExpect(jsonPath("$.password").doesNotExist());
        AppUser saved = users.findByUsername("mentor_a1").orElseThrow();
        assertThat(saved.getPasswordHash()).startsWith("{bcrypt}").doesNotContain("mentor-pass-1");
        List<String> columns = jdbc.queryForList(
                "SELECT LOWER(column_name) FROM information_schema.columns WHERE LOWER(table_name) = 'app_user'", String.class);
        assertThat(columns).containsExactlyInAnyOrder("id", "username", "password_hash", "role");
    }

    @Test
    void signupRejectsBadInputAndDuplicates() throws Exception {
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"홍길동\", \"password\": \"mentor-pass-1\"}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.detail").exists());
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_b1\", \"password\": \"short\"}"))
                .andExpect(status().isBadRequest());
        mentor("mentor_dup");
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_dup\", \"password\": \"mentor-pass-1\"}"))
                .andExpect(status().isConflict());
    }

    @Test
    void loginSessionAndLogout() throws Exception {
        MockHttpSession session = mentor("mentor_c1");
        mvc.perform(get("/api/auth/me").session(session)).andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value("mentor_c1")).andExpect(jsonPath("$.role").value("MENTOR"));
        mvc.perform(post("/api/auth/logout").with(csrf()).session(session)).andExpect(status().isNoContent());
        mvc.perform(get("/api/auth/me").session(session)).andExpect(status().isUnauthorized());
    }

    @Test
    void wrongPasswordAndUnknownUserGetSameAnswer() throws Exception {
        mentor("mentor_d1");
        for (String body : List.of("{\"username\": \"mentor_d1\", \"password\": \"wrong-pass-1\"}",
                "{\"username\": \"nobody_x1\", \"password\": \"wrong-pass-1\"}")) {
            mvc.perform(post("/api/auth/login").with(csrf()).contentType(MediaType.APPLICATION_JSON).content(body))
                    .andExpect(status().isUnauthorized())
                    .andExpect(jsonPath("$.detail").value("아이디 또는 비밀번호가 올바르지 않습니다."));
        }
    }

    @Test
    void apiRequiresLoginAndCsrf() throws Exception {
        mvc.perform(get("/api/forms")).andExpect(status().isUnauthorized()).andExpect(jsonPath("$.detail").value("로그인이 필요합니다."));
        mvc.perform(post("/api/qa").with(csrf()).contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isUnauthorized());
        MockHttpSession session = mentor("mentor_e1");
        mvc.perform(post("/api/qa").session(session).contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isForbidden()); // CSRF 토큰 없음
        assertThat(aiRequests).isEmpty();
    }

    @Test
    void adminEndpointsNeedAdminRole() throws Exception {
        MockHttpSession mentor = mentor("mentor_f1");
        mvc.perform(get("/api/admin/users").session(mentor)).andExpect(status().isForbidden());
        MockHttpSession admin = login("admin_test", "admin-password-1"); // 환경 설정으로 만든 관리자
        mvc.perform(get("/api/auth/me").session(admin)).andExpect(jsonPath("$.role").value("ADMIN"));
        mvc.perform(get("/api/admin/users").session(admin)).andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.username == 'admin_test')].role").value("ADMIN"));
    }

    // ------------------------------------------------------------ 양식 스키마
    @Test
    void formsListAndDetail() throws Exception {
        MockHttpSession session = mentor("mentor_g1");
        mvc.perform(get("/api/forms").session(session)).andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.form_id == 'activity_report')].title").value("활동보고서"))
                .andExpect(jsonPath("$.length()").value(6));
        mvc.perform(get("/api/forms/activity_report").session(session)).andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.form_id").value("activity_report"))
                .andExpect(jsonPath("$.fields").isArray());
        mvc.perform(get("/api/forms/no_such_form").session(session)).andExpect(status().isNotFound());
        mvc.perform(get("/api/forms/..%2F..%2FCLAUDE").session(session)).andExpect(status().is4xxClientError());
    }

    // ------------------------------------------------------------ AI 서버 중계
    @Test
    void proxyForwardsBodyAndReturnsResponseAsIs() throws Exception {
        MockHttpSession session = mentor("mentor_h1");
        String body = "{\"question\": \"" + QUESTION + "\"}";
        mvc.perform(post("/api/qa").with(csrf()).session(session).contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isOk()).andExpect(jsonPath("$.answer").value(AI_ANSWER));
        mvc.perform(post("/api/chat").with(csrf()).session(session).contentType(MediaType.APPLICATION_JSON)
                .content("{\"message\": \"" + QUESTION + "\"}")).andExpect(status().isOk());
        mvc.perform(post("/api/drafts/activity_report").with(csrf()).session(session)
                .contentType(MediaType.APPLICATION_JSON).content("{\"session_no\": 3}")).andExpect(status().isOk());
        assertThat(aiRequests).containsExactly(
                "POST /qa " + body,
                "POST /chat {\"message\": \"" + QUESTION + "\"}",
                "POST /drafts/activity_report {\"session_no\": 3}");
        assertThat(aiCookies).containsOnly("null"); // 세션 쿠키는 AI 서버로 넘기지 않는다
    }

    @Test
    void proxyPassesThroughAiServerErrorStatus() throws Exception {
        MockHttpSession session = mentor("mentor_i1");
        mvc.perform(post("/api/qa").with(csrf()).session(session).contentType(MediaType.APPLICATION_JSON)
                .content("{\"question\": \"한도 초과 상황\"}"))
                .andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.detail").value("가짜 서버 오류"));
    }

    @Test
    void logsHaveStatusAndTimeButNoBodies(CapturedOutput output) throws Exception {
        MockHttpSession session = mentor("mentor_j1");
        mvc.perform(post("/api/qa").with(csrf()).session(session).contentType(MediaType.APPLICATION_JSON)
                .content("{\"question\": \"" + QUESTION + "\"}")).andExpect(status().isOk());
        String logs = output.getAll();
        assertThat(logs).containsPattern("POST /api/qa status=200 ms=\\d+");
        assertThat(logs).doesNotContain("가람중", "010-0000-1234", "지각했는데", AI_ANSWER, "mentor-pass-1", "mentor_j1");
        // DB에도 질문이 남지 않는다: 테이블은 app_user 하나뿐이다
        List<String> tables = jdbc.queryForList(
                "SELECT LOWER(table_name) FROM information_schema.tables WHERE table_schema = 'PUBLIC'", String.class);
        assertThat(tables).containsExactly("app_user");
    }
}

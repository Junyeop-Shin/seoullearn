package com.seoullearn.mentor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.seoullearn.mentor.auth.AccountSessionFilter;
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
    @Autowired
    AccountSessionFilter accountSessionFilter;

    MockMvc mvc;

    @DynamicPropertySource
    static void aiServer(DynamicPropertyRegistry registry) throws IOException {
        fakeAi = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        fakeAi.createContext("/", exchange -> {
            String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            aiRequests.add(exchange.getRequestMethod() + " " + exchange.getRequestURI() + " " + body);
            aiCookies.add(String.valueOf(exchange.getRequestHeaders().getFirst("Cookie")));
            String path = exchange.getRequestURI().getPath();
            int code = path.equals("/qa") || path.equals("/chat") || path.startsWith("/drafts/") || path.startsWith("/tools/") ? 200 : 404;
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
        registry.add("app.reset-log-link", () -> "true");   // 메일 서버 없이 재설정 주소를 로그에서 읽는다
        registry.add("app.ai-server.url", () -> "http://127.0.0.1:" + fakeAi.getAddress().getPort());
    }

    @AfterAll
    static void stop() {
        fakeAi.stop(0);
    }

    @BeforeEach
    void setUp() {
        // 실제 서버에서는 서블릿 필터로 자동 등록된다. MockMvc에는 직접 넣는다
        mvc = MockMvcBuilders.webAppContextSetup(context).addFilters(accessLogFilter, accountSessionFilter).apply(springSecurity()).build();
        aiRequests.clear();
        aiCookies.clear();
    }

    /** 가입 전 동의: 필수 항목 전부와 동의한 문서의 시행일 */
    private static final String CONSENT = ", \"email\": \"mentor@example.com\", \"consentVersion\": \"2026-10-11\", \"consents\": [\"age14\", \"overseas\", \"mentee\"]";

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
                    .content("{\"username\": \"" + username + "\", \"password\": \"mentor-pass-1\"" + CONSENT + "}"))
                    .andExpect(status().isCreated());
        }
        return login(username, "mentor-pass-1");
    }

    // ------------------------------------------------------------ 로그인과 역할
    @Test
    void signupStoresOnlyUsernameHashRoleAndConsent() throws Exception {
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_a1\", \"password\": \"mentor-pass-1\"" + CONSENT + "}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.role").value("MENTOR"))
                .andExpect(jsonPath("$.password").doesNotExist());
        AppUser saved = users.findByUsername("mentor_a1").orElseThrow();
        assertThat(saved.getPasswordHash()).startsWith("{bcrypt}").doesNotContain("mentor-pass-1");
        List<String> columns = jdbc.queryForList(
                "SELECT LOWER(column_name) FROM information_schema.columns WHERE LOWER(table_name) = 'app_user'", String.class);
        assertThat(columns).containsExactlyInAnyOrder("id", "username", "password_hash", "role", "consent_version", "consented_at", "email");
        assertThat(saved.getConsentVersion()).isEqualTo("2026-10-11");
        assertThat(saved.getConsentedAt()).isNotNull();
    }

    @Test
    void signupNeedsEveryRequiredConsent() throws Exception {
        // 동의 없이, 일부만 동의하고는 가입할 수 없다
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_n1\", \"password\": \"mentor-pass-1\", \"email\": \"a@example.com\"}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.detail").value("가입 전 동의가 필요합니다."));
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_n1\", \"password\": \"mentor-pass-1\", \"email\": \"a@example.com\", \"consentVersion\": \"2026-10-11\", \"consents\": [\"age14\", \"mentee\"]}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.detail").value("국외 이전 동의와 확인 항목을 모두 체크해야 가입할 수 있습니다."));
        assertThat(users.existsByUsername("mentor_n1")).isFalse();
    }

    @Test
    void passwordResetByMailedLink(CapturedOutput output) throws Exception {
        MockHttpSession old = mentor("mentor_r1");
        // 전자우편이 다르면 주소를 만들지 않고, 응답은 같다 (맞는지 알려 주지 않는다)
        mvc.perform(post("/api/auth/reset-request").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_r1\", \"email\": \"other@example.com\"}")).andExpect(status().isNoContent());
        assertThat(output.getOut()).doesNotContain("password_reset_link");
        mvc.perform(post("/api/auth/reset-request").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_r1\", \"email\": \"Mentor@Example.com\"}")).andExpect(status().isNoContent());
        String out = output.getOut();
        String token = out.substring(out.lastIndexOf("/login?reset=") + 13).split("\\s")[0];
        mvc.perform(post("/api/auth/reset").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"token\": \"" + token + "\", \"password\": \"new-pass-9999\"}")).andExpect(status().isNoContent());
        login("mentor_r1", "new-pass-9999");
        // 재설정 전에 로그인해 둔 세션은 끊긴다
        mvc.perform(get("/api/auth/me").session(old)).andExpect(status().isUnauthorized());
        // 한 번 쓴 주소는 다시 못 쓴다
        mvc.perform(post("/api/auth/reset").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"token\": \"" + token + "\", \"password\": \"again-pass-1\"}")).andExpect(status().isBadRequest());
        assertThat(out).doesNotContain("mentor_r1 ").doesNotContain("mentor@example.com");
    }

    @Test
    void withdrawDeletesAccountAndEndsSession() throws Exception {
        MockHttpSession session = mentor("mentor_w1");
        mvc.perform(delete("/api/auth/me").session(session)).andExpect(status().isForbidden());   // CSRF 토큰 없이는 안 된다
        mvc.perform(delete("/api/auth/me").with(csrf()).session(session)).andExpect(status().isNoContent());
        assertThat(users.existsByUsername("mentor_w1")).isFalse();
        mvc.perform(get("/api/auth/me").session(session)).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/auth/login").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_w1\", \"password\": \"mentor-pass-1\"}"))
                .andExpect(status().isUnauthorized());
        // 다른 기기에 로그인해 둔 세션도 탈퇴 뒤의 첫 요청에서 끊긴다. 같은 아이디로 다시 가입한 계정을 옛 세션이 쓰지 못한다
        MockHttpSession pc = mentor("mentor_w2");
        MockHttpSession phone = login("mentor_w2", "mentor-pass-1");
        mvc.perform(delete("/api/auth/me").with(csrf()).session(phone)).andExpect(status().isNoContent());
        mentor("mentor_w2");
        mvc.perform(get("/api/auth/me").session(pc)).andExpect(status().isUnauthorized());
        assertThat(users.existsByUsername("mentor_w2")).isTrue();
        // 관리자 계정은 환경 변수로 관리한다
        MockHttpSession admin = login("admin_test", "admin-password-1");
        mvc.perform(delete("/api/auth/me").with(csrf()).session(admin)).andExpect(status().isForbidden());
        assertThat(users.existsByUsername("admin_test")).isTrue();
    }

    @Test
    void signupRejectsBadInputAndDuplicates() throws Exception {
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"홍길동\", \"password\": \"mentor-pass-1\"" + CONSENT + "}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.detail").exists());
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_b1\", \"password\": \"short\"" + CONSENT + "}"))
                .andExpect(status().isBadRequest());
        // 한글 비밀번호는 글자 수가 72자 안쪽이어도 암호화 한도(72바이트)를 넘을 수 있다: 서버 오류가 아니라 입력 오류로 알린다
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_b2\", \"password\": \"" + "가".repeat(30) + "\"" + CONSENT + "}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.detail").value("비밀번호가 너무 깁니다. 한글은 24자, 영문·숫자는 72자까지 쓸 수 있습니다."));
        // 처리되지 않은 요청 오류도 로그인·권한 오류로 바뀌지 않고 제 상태 코드와 {detail}로 나간다
        mvc.perform(put("/api/auth/login").with(csrf()).contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isMethodNotAllowed()).andExpect(jsonPath("$.detail").exists());
        mvc.perform(post("/api/auth/login").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"" + "a".repeat(200) + "\", \"password\": \"x\"}"))
                .andExpect(status().isBadRequest());
        mentor("mentor_dup");
        mvc.perform(post("/api/auth/signup").with(csrf()).contentType(MediaType.APPLICATION_JSON)
                .content("{\"username\": \"mentor_dup\", \"password\": \"mentor-pass-1\"" + CONSENT + "}"))
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
                    .andExpect(jsonPath("$.detail").value("아이디나 비밀번호가 맞지 않습니다. 다시 확인해 주세요."));
        }
    }

    @Test
    void apiRequiresLoginAndCsrf() throws Exception {
        mvc.perform(get("/api/forms/activity_report")).andExpect(status().isUnauthorized()).andExpect(jsonPath("$.detail").value("로그인이 필요합니다. 다시 로그인해 주세요."));
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
        mvc.perform(get("/api/admin/unanswered").session(mentor)).andExpect(status().isForbidden());
        MockHttpSession admin = login("admin_test", "admin-password-1"); // 환경 설정으로 만든 관리자
        mvc.perform(get("/api/auth/me").session(admin)).andExpect(jsonPath("$.role").value("ADMIN"));
        mvc.perform(get("/api/admin/unanswered").session(admin)).andExpect(status().isOk());
    }

    // ------------------------------------------------------------ 양식 스키마
    @Test
    void formsListAndDetail() throws Exception {
        MockHttpSession session = mentor("mentor_g1");
        mvc.perform(get("/api/forms/activity_report").session(session)).andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.form_id").value("activity_report"))
                .andExpect(jsonPath("$.fields").isArray());
        mvc.perform(get("/api/forms/no_such_form").session(session)).andExpect(status().isNotFound());
        mvc.perform(get("/api/forms/..%2F..%2FCLAUDE").session(session)).andExpect(status().is4xxClientError());
    }

    // ------------------------------------------------------------ 협약 장소
    @Test
    void placesAndPublicConfigNeedLogin() throws Exception {
        mvc.perform(get("/api/places")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/config")).andExpect(status().isUnauthorized());
        MockHttpSession session = mentor("mentor_p1");
        mvc.perform(get("/api/places").session(session)).andExpect(status().isOk())
                .andExpect(jsonPath("$.sample").value(true))
                .andExpect(jsonPath("$.places[0].name").value(org.hamcrest.Matchers.startsWith("(가상)")))
                .andExpect(jsonPath("$.places[0].lat").isNumber());
        mvc.perform(get("/api/config").session(session)).andExpect(status().isOk())
                .andExpect(jsonPath("$.kakaoMapJsKey").value("test-js-key"))
                .andExpect(jsonPath("$.length()").value(1));   // 공개 키 하나뿐이다. 다른 설정은 내보내지 않는다
    }

    // ------------------------------------------------------------ 서식 파일
    @Test
    void planTemplateNeedsLoginAndFallsBackWhenMissing() throws Exception {
        mvc.perform(get("/api/templates/plan").param("format", "docx")).andExpect(status().isUnauthorized());
        MockHttpSession session = mentor("mentor_t1");
        mvc.perform(get("/api/templates/plan").param("format", "docx").session(session)).andExpect(status().isOk())
                .andExpect(content().bytes("fake-docx".getBytes()));
        // 그 형식의 서식이 서버에 없으면 404: 화면이 내보내지 못한다고 알린다
        mvc.perform(get("/api/templates/plan").param("format", "hwpx").session(session)).andExpect(status().isNotFound());
        mvc.perform(get("/api/templates/plan").param("format", "../x").session(session)).andExpect(status().isBadRequest());
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
        mvc.perform(post("/api/tools/allowance").with(csrf()).session(session)
                .contentType(MediaType.APPLICATION_JSON).content("{\"mode\": \"온라인\"}")).andExpect(status().isOk());
        assertThat(aiRequests).containsExactly(
                "POST /qa " + body,
                "POST /chat {\"message\": \"" + QUESTION + "\"}",
                "POST /drafts/activity_report {\"session_no\": 3}",
                "POST /tools/allowance {\"mode\": \"온라인\"}");
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
        // backend는 중계한 질문을 DB에 쓰지 않는다. 테이블은 회원과 '답 못 한 질문 모음'(ai-server가 가린 문장만 넣음) 둘뿐이다
        List<String> tables = jdbc.queryForList(
                "SELECT LOWER(table_name) FROM information_schema.tables WHERE table_schema = 'PUBLIC'", String.class);
        assertThat(tables).containsExactlyInAnyOrder("app_user", "unanswered_question");
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM unanswered_question WHERE question LIKE '%지각했는데%'", Integer.class)).isZero();
    }
}

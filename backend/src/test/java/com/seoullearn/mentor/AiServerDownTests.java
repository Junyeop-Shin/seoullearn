package com.seoullearn.mentor;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

/** AI 서버가 꺼져 있을 때 (테스트 설정의 주소는 아무도 듣지 않는 포트다). */
@SpringBootTest
class AiServerDownTests {

    @Autowired
    WebApplicationContext context;

    @Test
    void returns502WithKoreanMessage() throws Exception {
        MockMvcBuilders.webAppContextSetup(context).apply(springSecurity()).build()
                .perform(post("/api/qa").with(csrf()).with(user("mentor_x1").roles("MENTOR"))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"question\": \"지각 처리\"}"))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.detail").value("지금은 AI 기능을 쓸 수 없습니다. 잠시 후 다시 시도해 주세요."));
    }
}

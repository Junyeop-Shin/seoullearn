package com.seoullearn.mentor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.charset.StandardCharsets;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

/** 답 못 한 질문 모음: 관리자만 보고, 질문한 사람 정보는 없다. */
@SpringBootTest
class UnansweredTests {

    @Autowired
    WebApplicationContext context;
    @Autowired
    JdbcTemplate jdbc;

    MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.webAppContextSetup(context).apply(springSecurity()).build();
        jdbc.update("DELETE FROM unanswered_question");
        // ai-server가 넣는 것과 같은 모양
        jdbc.update("INSERT INTO unanswered_question (question, answerable, route, created_on) VALUES (?, ?, ?, DATE '2026-10-08')",
                "[학교명] 멘티 활동인증서를 영문으로 받을 수 있나요?", "no", "운영사무국");
        jdbc.update("INSERT INTO unanswered_question (question, answerable, route, created_on) VALUES (?, ?, ?, DATE '2026-10-09')",
                "=HYPERLINK(\"http://x\") \"주 1회\" 기준이 월~일인가요?", "partial", null);
    }

    @Test
    void onlyAdminCanSee() throws Exception {
        mvc.perform(get("/api/admin/unanswered")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/admin/unanswered").with(user("mentor_a").roles("MENTOR"))).andExpect(status().isForbidden());
        mvc.perform(get("/api/admin/unanswered/export.csv").with(user("mentor_a").roles("MENTOR"))).andExpect(status().isForbidden());
        mvc.perform(get("/api/admin/unanswered").with(user("admin_a").roles("ADMIN"))).andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].createdOn").value("2026-10-09"))   // 최근 것부터
                .andExpect(jsonPath("$[1].route").value("운영사무국"))
                .andExpect(jsonPath("$[1].question").value("[학교명] 멘티 활동인증서를 영문으로 받을 수 있나요?"));
    }

    @Test
    void tableHasNoColumnsThatIdentifyTheAsker() {
        List<String> columns = jdbc.queryForList(
                "SELECT LOWER(column_name) FROM information_schema.columns WHERE LOWER(table_name) = 'unanswered_question'", String.class);
        assertThat(columns).containsExactlyInAnyOrder("id", "question", "answerable", "route", "created_on");
    }

    @Test
    void csvExportIsExcelSafe() throws Exception {
        byte[] body = mvc.perform(get("/api/admin/unanswered/export.csv").with(user("admin_a").roles("ADMIN")))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsByteArray();
        String csv = new String(body, StandardCharsets.UTF_8);
        assertThat(csv).startsWith("﻿날짜,분류,문의처,질문\r\n");
        assertThat(csv).contains("\"2026-10-08\",\"답 없음\",\"운영사무국\",\"[학교명] 멘티 활동인증서를 영문으로 받을 수 있나요?\"");
        // 수식으로 시작하는 칸은 막고, 따옴표는 두 번 쓴다
        assertThat(csv).contains("\"2026-10-09\",\"일부만 답함\",\"\",\"'=HYPERLINK(\"\"http://x\"\") \"\"주 1회\"\" 기준이 월~일인가요?\"");
    }

    @Test
    void adminCanDelete() throws Exception {
        Long id = jdbc.queryForObject("SELECT MIN(id) FROM unanswered_question", Long.class);
        mvc.perform(delete("/api/admin/unanswered/" + id).with(csrf()).with(user("mentor_a").roles("MENTOR"))).andExpect(status().isForbidden());
        mvc.perform(delete("/api/admin/unanswered/" + id).with(csrf()).with(user("admin_a").roles("ADMIN"))).andExpect(status().isNoContent());
        mvc.perform(delete("/api/admin/unanswered/" + id).with(csrf()).with(user("admin_a").roles("ADMIN"))).andExpect(status().isNotFound());
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM unanswered_question", Integer.class)).isEqualTo(1);
    }
}

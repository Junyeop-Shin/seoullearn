package com.seoullearn.mentor;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/** 서울런 멘토 업무 지원 백엔드: 로그인·역할, 양식 스키마 제공, AI 서버 중계. */
@SpringBootApplication
@ConfigurationPropertiesScan
public class MentorBackendApplication {

    public static void main(String[] args) {
        SpringApplication.run(MentorBackendApplication.class, args);
    }
}

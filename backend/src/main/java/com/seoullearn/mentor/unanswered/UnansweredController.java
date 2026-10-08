package com.seoullearn.mentor.unanswered;

import com.seoullearn.mentor.common.ApiException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/** 답 못 한 질문 모음. 관리자(ADMIN)만 볼 수 있다 (/api/admin/** 은 SecurityConfig에서 ADMIN으로 제한). */
@RestController
@RequestMapping("/api/admin/unanswered")
public class UnansweredController {

    public record Row(Long id, String createdOn, String answerable, String route, String question) {
    }

    private final UnansweredQuestionRepository repository;

    public UnansweredController(UnansweredQuestionRepository repository) {
        this.repository = repository;
    }

    @GetMapping
    public List<Row> list() {
        return repository.findTop1000ByOrderByCreatedOnDescIdDesc().stream()
                .map(q -> new Row(q.getId(), q.getCreatedOn().toString(), q.getAnswerable(), q.getRoute(), q.getQuestion()))
                .toList();
    }

    /** 엑셀에서 바로 열 수 있는 CSV (UTF-8 BOM). */
    @GetMapping(value = "/export.csv", produces = "text/csv")
    public ResponseEntity<byte[]> csv() {
        StringBuilder sb = new StringBuilder("﻿날짜,분류,문의처,질문\r\n");
        for (Row r : list()) {
            sb.append(cell(r.createdOn())).append(',').append(cell(label(r.answerable()))).append(',')
                    .append(cell(r.route() == null ? "" : r.route())).append(',').append(cell(r.question())).append("\r\n");
        }
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"unanswered_questions.csv\"")
                .contentType(new MediaType("text", "csv", StandardCharsets.UTF_8))
                .body(sb.toString().getBytes(StandardCharsets.UTF_8));
    }

    /** 남기면 안 되는 내용이 들어온 항목을 관리자가 지운다. */
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id) {
        if (!repository.existsById(id)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "해당 항목을 찾을 수 없습니다.");
        }
        repository.deleteById(id);
    }

    private static String label(String answerable) {
        return "partial".equals(answerable) ? "일부만 답함" : "답 없음";
    }

    /** CSV 칸: 따옴표로 감싸고, 엑셀이 수식으로 읽을 수 있는 첫 글자(= + - @)는 작은따옴표로 막는다. */
    static String cell(String value) {
        String v = value == null ? "" : value;
        if (!v.isEmpty() && "=+-@\t\r".indexOf(v.charAt(0)) >= 0) {
            v = "'" + v;
        }
        return "\"" + v.replace("\"", "\"\"") + "\"";
    }
}

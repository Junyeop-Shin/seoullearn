package com.seoullearn.mentor.unanswered;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDate;

/** 매뉴얼로 답하지 못한 질문. 가린 문장과 분류, 문의처, 날짜만 있다. 질문한 사람 정보는 없다. */
@Entity
@Table(name = "unanswered_question")
public class UnansweredQuestion {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 300)
    private String question;

    @Column(nullable = false, length = 10)
    private String answerable;

    @Column(length = 20)
    private String route;

    @Column(name = "created_on", nullable = false)
    private LocalDate createdOn;

    protected UnansweredQuestion() {
    }

    public Long getId() {
        return id;
    }

    public String getQuestion() {
        return question;
    }

    public String getAnswerable() {
        return answerable;
    }

    public String getRoute() {
        return route;
    }

    public LocalDate getCreatedOn() {
        return createdOn;
    }
}

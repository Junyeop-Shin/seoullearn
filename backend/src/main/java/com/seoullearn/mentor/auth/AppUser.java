package com.seoullearn.mentor.auth;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

/**
 * 회원. 아이디, 비밀번호 해시, 역할, 전자우편(비밀번호 재설정용), 가입 전 동의 기록(동의한 문서의 시행일과 동의한 일시)만 저장한다.
 * 실명, 학교, 전화번호 같은 다른 정보는 저장하지 않는다.
 */
@Entity
@Table(name = "app_user")
public class AppUser {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 20)
    private String username;

    @Column(name = "password_hash", nullable = false, length = 100)
    private String passwordHash;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private Role role;

    // 가입 전 동의 기록. 환경 변수로 만드는 관리자 계정에는 없다
    @Column(name = "consent_version", length = 10)
    private String consentVersion;

    @Column(name = "consented_at")
    private Instant consentedAt;

    // 비밀번호 재설정 메일을 받을 주소. 이 칸이 생기기 전의 계정과 관리자 계정에는 없다
    @Column(length = 100)
    private String email;

    protected AppUser() {
    }

    public AppUser email(String email) {
        this.email = email;
        return this;
    }

    public String getEmail() {
        return email;
    }

    public void changePassword(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public AppUser(String username, String passwordHash, Role role) {
        this.username = username;
        this.passwordHash = passwordHash;
        this.role = role;
    }

    /** 가입 전 동의를 기록한다: 화면이 보여 준 문서의 시행일과 동의한 일시. */
    public AppUser agreed(String version, Instant at) {
        this.consentVersion = version;
        this.consentedAt = at;
        return this;
    }

    public String getConsentVersion() {
        return consentVersion;
    }

    public Instant getConsentedAt() {
        return consentedAt;
    }

    public Long getId() {
        return id;
    }

    public String getUsername() {
        return username;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public Role getRole() {
        return role;
    }
}

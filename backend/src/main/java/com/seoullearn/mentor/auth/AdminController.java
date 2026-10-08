package com.seoullearn.mentor.auth;

import com.seoullearn.mentor.auth.AuthDtos.UserResponse;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 관리자(ADMIN) 전용. 지금은 계정 목록만 있다. */
@RestController
@RequestMapping("/api/admin")
public class AdminController {

    private final AppUserRepository users;

    public AdminController(AppUserRepository users) {
        this.users = users;
    }

    @GetMapping("/users")
    public List<UserResponse> users() {
        return users.findAll().stream().map(u -> new UserResponse(u.getUsername(), u.getRole())).toList();
    }
}

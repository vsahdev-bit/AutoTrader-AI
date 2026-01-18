package com.autotrader.auth.controller;

import com.autotrader.auth.dto.LoginResponse;
import com.autotrader.auth.dto.SessionInfoResponse;
import com.autotrader.auth.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.security.Principal;
import java.util.UUID;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/login")
    public ResponseEntity<LoginResponse> login(
            @RequestParam String email,
            @RequestParam String authProvider) {
        LoginResponse response = authService.loginOrRegister(email, authProvider);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/session")
    public ResponseEntity<SessionInfoResponse> getSession(Principal principal) {
        // Extract userId from JWT token in security context
        UUID userId = UUID.fromString(principal.getName());
        SessionInfoResponse response = authService.getSessionInfo(userId);
        return ResponseEntity.ok(response);
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout() {
        return ResponseEntity.ok().build();
    }
}

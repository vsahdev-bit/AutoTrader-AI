package com.autotrader.auth.service;

import com.autotrader.auth.dto.LoginResponse;
import com.autotrader.auth.dto.SessionInfoResponse;
import com.autotrader.auth.entity.User;
import com.autotrader.auth.repository.UserRepository;
import com.autotrader.auth.security.JwtUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class AuthService {

    private final UserRepository userRepository;
    private final JwtUtil jwtUtil;

    @Transactional
    public LoginResponse loginOrRegister(String email, String authProvider) {
        log.info("Login/Register attempt for email: {}, provider: {}", email, authProvider);
        
        User user = userRepository.findByEmail(email)
                .orElseGet(() -> {
                    User newUser = User.builder()
                            .id(UUID.randomUUID())
                            .email(email)
                            .authProvider(authProvider)
                            .build();
                    return userRepository.save(newUser);
                });

        String token = jwtUtil.generateToken(user.getId());
        log.info("User authenticated: {}", user.getId());

        return LoginResponse.builder()
                .userId(user.getId())
                .sessionExpiresAt(LocalDateTime.now().plusMinutes(15))
                .build();
    }

    public SessionInfoResponse getSessionInfo(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));

        return SessionInfoResponse.builder()
                .userId(user.getId())
                .authenticated(true)
                .brokerageConnected(false) // TODO: Check brokerage_connections table
                .brokerageTokenExpiresAt(null)
                .build();
    }
}

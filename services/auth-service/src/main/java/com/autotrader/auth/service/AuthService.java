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

/**
 * AuthService - Core business logic for user authentication and session management.
 * 
 * This service implements the authentication workflow for the AutoTrader AI platform,
 * handling both new user registration and returning user authentication in a single
 * unified flow (progressive registration pattern).
 * 
 * Key Responsibilities:
 * - User lookup and automatic registration
 * - JWT token generation for authenticated sessions
 * - Session information retrieval and validation
 * - Integration with brokerage connection status
 * 
 * Design Patterns:
 * - Progressive Registration: Users are created on first login attempt
 * - Stateless Sessions: All session data encoded in JWT tokens
 * - Repository Pattern: Database access abstracted through UserRepository
 * 
 * Transaction Management:
 * - loginOrRegister: Transactional to ensure atomic user creation
 * - getSessionInfo: Read-only, no transaction needed
 * 
 * Security Considerations:
 * - Passwords are never stored (OAuth-only in current implementation)
 * - JWT tokens are short-lived (15 minutes) to limit exposure
 * - User IDs are UUIDs to prevent enumeration attacks
 * 
 * @see JwtUtil for JWT token operations
 * @see UserRepository for database operations
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class AuthService {

    /** Repository for user persistence operations */
    private final UserRepository userRepository;
    
    /** Utility for JWT token generation and validation */
    private final JwtUtil jwtUtil;

    /**
     * Authenticate an existing user or register a new one.
     * 
     * This method implements the "login or register" pattern where:
     * 1. If user with email exists -> return existing user
     * 2. If user doesn't exist -> create new user and return
     * 
     * This simplifies the frontend flow by eliminating separate
     * registration and login endpoints.
     * 
     * Transaction Behavior:
     * - Marked @Transactional to ensure atomic user creation
     * - If user creation fails, entire operation rolls back
     * - Prevents duplicate users from race conditions
     * 
     * @param email User's email address (validated by OAuth provider or input validation)
     * @param authProvider Authentication method used: "GOOGLE", "LOCAL", etc.
     *                     Stored for analytics and future auth method management
     * @return LoginResponse containing the user ID and session expiration timestamp
     * 
     * Example Usage:
     * <pre>
     * LoginResponse response = authService.loginOrRegister("user@example.com", "GOOGLE");
     * // response.getUserId() -> UUID of authenticated user
     * // response.getSessionExpiresAt() -> When the session token expires
     * </pre>
     */
    @Transactional
    public LoginResponse loginOrRegister(String email, String authProvider) {
        log.info("Login/Register attempt for email: {}, provider: {}", email, authProvider);
        
        // Attempt to find existing user, or create new one if not found
        // The orElseGet lambda is only executed if findByEmail returns empty
        User user = userRepository.findByEmail(email)
                .orElseGet(() -> {
                    // Create new user with auto-generated UUID
                    User newUser = User.builder()
                            .id(UUID.randomUUID())
                            .email(email)
                            .authProvider(authProvider)
                            .build();
                    log.info("Creating new user account for email: {}", email);
                    return userRepository.save(newUser);
                });

        // Generate JWT token for the authenticated user
        // Token contains user ID as subject claim
        String token = jwtUtil.generateToken(user.getId());
        log.info("User authenticated successfully: {}", user.getId());

        // Build response with session metadata
        // Session expires in 15 minutes (matches JWT expiration)
        return LoginResponse.builder()
                .userId(user.getId())
                .sessionExpiresAt(LocalDateTime.now().plusMinutes(15))
                .build();
    }

    /**
     * Retrieve session information for an authenticated user.
     * 
     * This method is called after JWT validation to provide the frontend
     * with current session status and user capabilities.
     * 
     * Information Returned:
     * - User ID (for display and API calls)
     * - Authentication status (always true if this method is reached)
     * - Brokerage connection status (whether user can execute trades)
     * - Brokerage token expiration (for proactive reconnection prompts)
     * 
     * @param userId UUID of the authenticated user (from JWT subject claim)
     * @return SessionInfoResponse with current session and connection status
     * @throws RuntimeException if user not found (indicates data inconsistency)
     * 
     * Future Enhancements:
     * - Query brokerage_connections table for actual connection status
     * - Include user's risk limits and trading preferences
     * - Add account balance from connected brokerage
     */
    public SessionInfoResponse getSessionInfo(UUID userId) {
        // Fetch user from database to ensure they still exist
        // This also allows us to return fresh user data
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));

        // Build session response with connection status
        // TODO: Query user_brokerage_connections table for actual status
        return SessionInfoResponse.builder()
                .userId(user.getId())
                .authenticated(true)
                .brokerageConnected(false) // TODO: Check brokerage_connections table
                .brokerageTokenExpiresAt(null) // TODO: Get from brokerage connection
                .build();
    }
}

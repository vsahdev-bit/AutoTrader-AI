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

/**
 * AuthController - REST API endpoints for authentication operations.
 * 
 * This controller handles all authentication-related HTTP requests for the
 * AutoTrader AI platform. It supports multiple authentication providers
 * (Google OAuth, email/password) and manages user sessions via JWT tokens.
 * 
 * Endpoints:
 * - POST /auth/login     - Authenticate user and create session
 * - GET  /auth/session   - Get current session info (requires auth)
 * - POST /auth/logout    - Invalidate current session
 * 
 * Security Model:
 * - Stateless authentication using JWT tokens
 * - Tokens are short-lived (15 minutes) for security
 * - Refresh tokens (7 days) enable seamless re-authentication
 * - All endpoints except /login require valid JWT in Authorization header
 * 
 * Error Handling:
 * - 400 Bad Request: Invalid input parameters
 * - 401 Unauthorized: Invalid/expired token or credentials
 * - 500 Internal Server Error: Database or system failures
 * 
 * @see AuthService for business logic
 * @see LoginResponse for login response structure
 * @see SessionInfoResponse for session info structure
 */
@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {

    /** Service layer for authentication business logic */
    private final AuthService authService;

    /**
     * Authenticate a user and create a new session.
     * 
     * This endpoint handles both new user registration and returning user login.
     * If the email doesn't exist, a new user account is created automatically
     * (progressive registration pattern common in modern apps).
     * 
     * Flow:
     * 1. Frontend authenticates with Google OAuth and receives credential
     * 2. Frontend decodes credential to get email and calls this endpoint
     * 3. Backend creates/retrieves user and generates JWT token
     * 4. Frontend stores token for subsequent API calls
     * 
     * @param email User's email address (validated by Google or entered directly)
     * @param authProvider Authentication provider: "GOOGLE" or "LOCAL"
     * @return LoginResponse containing userId and session expiration time
     * 
     * Note: In production, this would also return the JWT token in the response
     * or set it as an HTTP-only cookie for additional security.
     */
    @PostMapping("/login")
    public ResponseEntity<LoginResponse> login(
            @RequestParam String email,
            @RequestParam String authProvider) {
        LoginResponse response = authService.loginOrRegister(email, authProvider);
        return ResponseEntity.ok(response);
    }

    /**
     * Get information about the current authenticated session.
     * 
     * This endpoint is called by the frontend to:
     * - Verify the user is still authenticated
     * - Check if brokerage is connected (for trade execution)
     * - Get session expiration time (for proactive refresh)
     * 
     * The Principal object is automatically populated by Spring Security
     * from the validated JWT token in the Authorization header.
     * 
     * @param principal Security context containing authenticated user info
     *                  (injected by Spring Security from JWT token)
     * @return SessionInfoResponse with authentication status and brokerage connection info
     * @throws RuntimeException if user not found (should not happen with valid JWT)
     */
    @GetMapping("/session")
    public ResponseEntity<SessionInfoResponse> getSession(Principal principal) {
        // Extract userId from JWT token subject claim in security context
        // The JWT subject contains the user's UUID as a string
        UUID userId = UUID.fromString(principal.getName());
        SessionInfoResponse response = authService.getSessionInfo(userId);
        return ResponseEntity.ok(response);
    }

    /**
     * Logout the current user and invalidate their session.
     * 
     * Current Implementation: Simple acknowledgment (stateless JWT)
     * Since JWTs are stateless, "logout" on the server side is a no-op.
     * The frontend handles logout by:
     * 1. Clearing the stored JWT token
     * 2. Clearing any cached user data
     * 3. Redirecting to login page
     * 
     * Future Enhancement: Implement token blacklisting in Redis for
     * immediate token invalidation (required for security-critical apps).
     * 
     * @return Empty 200 OK response indicating successful logout
     */
    @PostMapping("/logout")
    public ResponseEntity<Void> logout() {
        // TODO: Implement token blacklisting in Redis for immediate invalidation
        // Current implementation relies on token expiration (15 min max exposure)
        return ResponseEntity.ok().build();
    }
}

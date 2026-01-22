package com.autotrader.auth.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * LoginResponse - Data Transfer Object for successful authentication responses.
 * 
 * This DTO is returned after successful user authentication, providing the
 * frontend with session information needed for subsequent API calls.
 * 
 * Response Structure:
 * - userId: Unique identifier for the authenticated user
 * - sessionExpiresAt: When the current session/token expires
 * 
 * Example Response:
 * <pre>
 * {
 *   "userId": "123e4567-e89b-12d3-a456-426614174000",
 *   "sessionExpiresAt": "2024-01-15T10:30:00"
 * }
 * </pre>
 * 
 * Frontend Usage:
 * 1. Store userId for user-specific API calls
 * 2. Monitor sessionExpiresAt for proactive token refresh
 * 3. Display session countdown to user (optional UX enhancement)
 * 
 * Note: The actual JWT token may be returned separately via:
 * - HTTP-only cookie (more secure, prevents XSS)
 * - Authorization header (current implementation)
 * 
 * @see AuthController#login for endpoint
 * @see AuthService#loginOrRegister for response generation
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LoginResponse {
    
    /**
     * Unique identifier for the authenticated user.
     * 
     * This UUID is used by the frontend to:
     * - Make user-specific API calls (e.g., GET /api/users/{userId}/trades)
     * - Display personalized content
     * - Track analytics events
     * 
     * Security: This is a public identifier, not a secret.
     * Authentication relies on the JWT token, not the userId.
     */
    private UUID userId;
    
    /**
     * Timestamp when the current session expires.
     * 
     * This matches the JWT token expiration time (15 minutes by default).
     * 
     * Frontend should:
     * - Monitor this timestamp for proactive refresh
     * - Warn user before expiration (e.g., "Session expires in 2 min")
     * - Trigger re-authentication when expired
     * 
     * Format: ISO 8601 datetime (e.g., "2024-01-15T10:30:00")
     */
    private LocalDateTime sessionExpiresAt;
}

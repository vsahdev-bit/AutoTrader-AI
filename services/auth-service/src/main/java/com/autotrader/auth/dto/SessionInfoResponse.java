package com.autotrader.auth.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * SessionInfoResponse - Data Transfer Object for session status queries.
 * 
 * This DTO provides comprehensive information about the user's current
 * session state, including authentication status and brokerage connectivity.
 * It's used by the frontend to determine what features are available.
 * 
 * Response Structure:
 * - userId: The authenticated user's identifier
 * - authenticated: Whether the session is valid
 * - brokerageConnected: Whether user has connected a brokerage account
 * - brokerageTokenExpiresAt: When brokerage OAuth token expires
 * 
 * Example Response:
 * <pre>
 * {
 *   "userId": "123e4567-e89b-12d3-a456-426614174000",
 *   "authenticated": true,
 *   "brokerageConnected": true,
 *   "brokerageTokenExpiresAt": "2024-01-20T15:00:00"
 * }
 * </pre>
 * 
 * Frontend Decision Logic:
 * - !authenticated -> Redirect to login
 * - !brokerageConnected -> Show "Connect Brokerage" prompt
 * - brokerageTokenExpiresAt near -> Warn about re-authentication
 * 
 * Called by: GET /api/v1/auth/session
 * Frequency: On app load, after navigation, periodically in background
 * 
 * @see AuthController#getSession for endpoint
 * @see AuthService#getSessionInfo for response generation
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SessionInfoResponse {
    
    /**
     * Unique identifier for the authenticated user.
     * 
     * Matches the userId returned in LoginResponse.
     * Used for consistency checks and user-specific operations.
     */
    private UUID userId;
    
    /**
     * Whether the current session is authenticated.
     * 
     * In practice, this is always true when this endpoint is called
     * successfully (401 is returned for invalid tokens).
     * 
     * Included for:
     * - Explicit API contract
     * - Future scenarios where partial sessions might exist
     */
    private boolean authenticated;
    
    /**
     * Whether the user has an active brokerage connection.
     * 
     * This determines if the user can:
     * - Execute trades (requires connection)
     * - View portfolio data (requires connection)
     * - See real account balances (requires connection)
     * 
     * If false, frontend should prompt user to connect their brokerage
     * account (e.g., Robinhood) via OAuth flow.
     */
    private boolean brokerageConnected;
    
    /**
     * When the brokerage OAuth token expires.
     * 
     * Brokerage tokens (e.g., Robinhood) have their own expiration
     * separate from our session tokens. When this expires:
     * - Trade execution will fail
     * - User needs to re-authenticate with brokerage
     * 
     * Null if no brokerage is connected.
     * 
     * Frontend should proactively prompt re-authentication
     * when this timestamp approaches.
     */
    private LocalDateTime brokerageTokenExpiresAt;
}

package com.autotrader.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * LoginRequest - Data Transfer Object for email/password login requests.
 * 
 * This DTO captures the payload for traditional email/password authentication.
 * Currently, the platform primarily uses Google OAuth, but this DTO supports
 * future email/password authentication flow.
 * 
 * Validation:
 * - email: Must be non-blank and valid email format
 * - password: Must be non-blank (additional strength validation in service layer)
 * 
 * Usage:
 * <pre>
 * POST /api/v1/auth/login
 * Content-Type: application/json
 * 
 * {
 *   "email": "user@example.com",
 *   "password": "securePassword123"
 * }
 * </pre>
 * 
 * Security Note:
 * Password should be transmitted over HTTPS only.
 * Never log or persist the password field.
 * 
 * @see AuthController for endpoint handling
 * @see AuthService for authentication logic
 */
@Data
public class LoginRequest {
    
    /**
     * User's email address for authentication.
     * 
     * Validation:
     * - @NotBlank: Cannot be null, empty, or whitespace-only
     * - @Email: Must match standard email format (RFC 5322)
     */
    @NotBlank
    @Email
    private String email;
    
    /**
     * User's password for authentication.
     * 
     * Validation:
     * - @NotBlank: Cannot be null, empty, or whitespace-only
     * 
     * Note: Additional password strength validation (length, complexity)
     * should be performed in the service layer.
     */
    @NotBlank
    private String password;
}

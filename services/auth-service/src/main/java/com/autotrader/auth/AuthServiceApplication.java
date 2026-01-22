package com.autotrader.auth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.ComponentScan;

/**
 * AuthServiceApplication - Main entry point for the Authentication Microservice.
 * 
 * This service is part of the AutoTrader AI platform's User Interaction & Execution Plane,
 * responsible for:
 * - User authentication via Google OAuth 2.0 and email/password
 * - JWT token generation and validation
 * - Session management with short-lived tokens (15 minutes)
 * - User registration and account management
 * - Integration with brokerage OAuth flows (Robinhood)
 * 
 * Architecture Context:
 * - Runs on port 8081 (configured in application.yml)
 * - Connects to PostgreSQL for user persistence
 * - Uses HashiCorp Vault for secure token storage (brokerage OAuth tokens)
 * - Stateless design - all session state stored in JWT tokens
 * 
 * Security Features:
 * - JWT tokens with HMAC-SHA256 signing
 * - OAuth 2.0 integration for Google SSO
 * - Backend-only brokerage token handling (tokens never exposed to frontend)
 * 
 * API Base Path: /api/v1/auth
 * 
 * @see AuthController for REST endpoint definitions
 * @see AuthService for business logic implementation
 * @see JwtUtil for JWT token operations
 */
@SpringBootApplication
@ComponentScan(basePackages = "com.autotrader.auth")
public class AuthServiceApplication {

    /**
     * Application entry point.
     * Bootstraps the Spring Boot application context with auto-configuration
     * for web, JPA, security, and OAuth2 client capabilities.
     * 
     * @param args Command-line arguments (supports standard Spring Boot args)
     */
    public static void main(String[] args) {
        SpringApplication.run(AuthServiceApplication.class, args);
    }
}

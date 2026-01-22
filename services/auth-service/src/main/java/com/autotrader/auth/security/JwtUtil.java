package com.autotrader.auth.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.security.Key;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;

/**
 * JwtUtil - Utility class for JSON Web Token (JWT) operations.
 * 
 * This class handles all JWT-related operations for the AutoTrader AI platform:
 * - Token generation with configurable expiration
 * - Token validation and signature verification
 * - Claims extraction (user ID, expiration, custom claims)
 * 
 * JWT Structure (RFC 7519):
 * - Header: Algorithm (HS256) and token type (JWT)
 * - Payload: Subject (user ID), issued at, expiration, custom claims
 * - Signature: HMAC-SHA256 using secret key
 * 
 * Security Configuration (from application.yml):
 * - jwt.secret: HMAC signing key (min 256 bits for HS256)
 * - jwt.expiration: Token lifetime in milliseconds (default: 15 minutes)
 * 
 * Security Best Practices Implemented:
 * - Short-lived tokens (15 min) to limit exposure window
 * - HMAC-SHA256 signing (symmetric, fast, secure)
 * - Secret key derived using Keys.hmacShaKeyFor for proper key sizing
 * - No sensitive data stored in token payload
 * 
 * Token Lifecycle:
 * 1. User authenticates successfully
 * 2. generateToken() creates signed JWT with user ID as subject
 * 3. Frontend includes token in Authorization header for API calls
 * 4. validateToken() verifies signature and expiration on each request
 * 5. Token expires after 15 minutes, user must re-authenticate
 * 
 * @see AuthService for token generation context
 * @see <a href="https://jwt.io">JWT.io</a> for JWT debugging
 */
@Component
public class JwtUtil {

    /**
     * Secret key for HMAC-SHA256 signing.
     * Must be at least 256 bits (32 characters) for HS256 algorithm.
     * Loaded from jwt.secret property in application.yml.
     * 
     * SECURITY WARNING: In production, this must be:
     * - Stored securely (environment variable or Vault)
     * - Unique per environment
     * - Rotated periodically
     */
    @Value("${jwt.secret}")
    private String secret;

    /**
     * Token expiration time in milliseconds.
     * Default: 900000ms (15 minutes) - configured in application.yml
     * 
     * Trade-off: Shorter = more secure but more re-authentication
     * 15 minutes is a good balance for financial applications.
     */
    @Value("${jwt.expiration}")
    private Long expiration;

    /**
     * Generate the cryptographic signing key from the secret string.
     * 
     * Uses JJWT's Keys.hmacShaKeyFor() which:
     * - Converts string to byte array using UTF-8
     * - Creates a SecretKey suitable for HMAC operations
     * - Validates key length is appropriate for the algorithm
     * 
     * @return Key object for HMAC-SHA256 signing/verification
     */
    private Key getSigningKey() {
        return Keys.hmacShaKeyFor(secret.getBytes());
    }

    /**
     * Extract the user ID from a JWT token.
     * 
     * The user ID is stored in the "sub" (subject) claim per JWT spec.
     * This is the primary identifier used to look up user data.
     * 
     * @param token The JWT token string (without "Bearer " prefix)
     * @return User ID as string (UUID format)
     * @throws io.jsonwebtoken.JwtException if token is invalid or tampered
     */
    public String extractUserId(String token) {
        return extractClaim(token, Claims::getSubject);
    }

    /**
     * Extract the expiration date from a JWT token.
     * 
     * The expiration is stored in the "exp" claim as Unix timestamp.
     * Used to check if token is still valid before processing requests.
     * 
     * @param token The JWT token string
     * @return Date when the token expires
     */
    public Date extractExpiration(String token) {
        return extractClaim(token, Claims::getExpiration);
    }

    /**
     * Generic method to extract any claim from a JWT token.
     * 
     * Uses functional interface to allow extraction of any claim type.
     * This pattern avoids code duplication for different claim types.
     * 
     * @param token The JWT token string
     * @param claimsResolver Function that extracts the desired claim from Claims object
     * @param <T> The return type of the claim
     * @return The extracted claim value
     * 
     * Example:
     * <pre>
     * // Extract custom claim
     * String role = extractClaim(token, claims -> claims.get("role", String.class));
     * </pre>
     */
    public <T> T extractClaim(String token, Function<Claims, T> claimsResolver) {
        final Claims claims = extractAllClaims(token);
        return claimsResolver.apply(claims);
    }

    /**
     * Parse and validate a JWT token, extracting all claims.
     * 
     * This method performs:
     * 1. Base64 decoding of header, payload, and signature
     * 2. Signature verification using the signing key
     * 3. Claims extraction from the payload
     * 
     * If signature verification fails, JwtException is thrown.
     * 
     * @param token The JWT token string to parse
     * @return Claims object containing all token claims
     * @throws io.jsonwebtoken.ExpiredJwtException if token is expired
     * @throws io.jsonwebtoken.SignatureException if signature is invalid
     * @throws io.jsonwebtoken.MalformedJwtException if token format is invalid
     */
    private Claims extractAllClaims(String token) {
        return Jwts.parserBuilder()
                .setSigningKey(getSigningKey())
                .build()
                .parseClaimsJws(token)
                .getBody();
    }

    /**
     * Check if a JWT token has expired.
     * 
     * Compares the token's expiration claim against the current time.
     * Used as part of token validation before processing requests.
     * 
     * @param token The JWT token string
     * @return true if token is expired, false if still valid
     */
    private Boolean isTokenExpired(String token) {
        return extractExpiration(token).before(new Date());
    }

    /**
     * Generate a new JWT token for an authenticated user.
     * 
     * Creates a signed JWT with:
     * - Subject (sub): User's UUID
     * - Issued At (iat): Current timestamp
     * - Expiration (exp): Current time + configured expiration
     * 
     * The token is signed with HMAC-SHA256 for integrity verification.
     * 
     * @param userId UUID of the authenticated user
     * @return Signed JWT token string (header.payload.signature)
     * 
     * Token Format Example:
     * eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLXV1aWQiLCJpYXQiOjE2...}.signature
     */
    public String generateToken(UUID userId) {
        // Empty claims map - can be extended with roles, permissions, etc.
        Map<String, Object> claims = new HashMap<>();
        return createToken(claims, userId.toString());
    }

    /**
     * Create a JWT token with the specified claims and subject.
     * 
     * This is the core token creation method that assembles and signs the JWT.
     * 
     * Token Structure:
     * - Claims: Custom key-value pairs (currently empty, extensible)
     * - Subject: User identifier (UUID as string)
     * - IssuedAt: Token creation timestamp (for debugging/auditing)
     * - Expiration: When token becomes invalid
     * - Signature: HMAC-SHA256 signature for tamper detection
     * 
     * @param claims Map of custom claims to include in the token
     * @param subject The subject claim value (typically user ID)
     * @return Compact serialized JWT string
     */
    private String createToken(Map<String, Object> claims, String subject) {
        return Jwts.builder()
                .setClaims(claims)           // Set custom claims first
                .setSubject(subject)         // User ID as subject claim
                .setIssuedAt(new Date(System.currentTimeMillis()))  // Token creation time
                .setExpiration(new Date(System.currentTimeMillis() + expiration))  // Expiry time
                .signWith(getSigningKey(), SignatureAlgorithm.HS256)  // Sign with HMAC-SHA256
                .compact();  // Serialize to string format
    }

    /**
     * Validate a JWT token against a specific user ID.
     * 
     * Validation checks:
     * 1. Token signature is valid (not tampered)
     * 2. Token has not expired
     * 3. Token's subject matches the expected user ID
     * 
     * This method should be called on every authenticated API request
     * to ensure the token is valid and belongs to the requesting user.
     * 
     * @param token The JWT token string to validate
     * @param userId The expected user ID (from request context)
     * @return true if token is valid and belongs to the user, false otherwise
     */
    public Boolean validateToken(String token, UUID userId) {
        final String extractedUserId = extractUserId(token);
        // Token is valid if: subject matches user ID AND token hasn't expired
        return (extractedUserId.equals(userId.toString()) && !isTokenExpired(token));
    }
}

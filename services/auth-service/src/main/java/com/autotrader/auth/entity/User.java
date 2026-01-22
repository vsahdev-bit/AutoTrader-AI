package com.autotrader.auth.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * User - JPA Entity representing a user account in the AutoTrader AI platform.
 * 
 * This entity maps to the 'users' table in PostgreSQL and serves as the central
 * identity record for all user-related data. All other tables (trades, configs,
 * recommendations) reference this entity via foreign key relationships.
 * 
 * Table Schema (from V1__initial_schema.sql):
 * - id: UUID primary key (auto-generated)
 * - email: Unique email address (used as login identifier)
 * - auth_provider: How user authenticates ('GOOGLE', 'LOCAL')
 * - created_at: Account creation timestamp (immutable)
 * - updated_at: Last modification timestamp (auto-updated)
 * 
 * Design Decisions:
 * - UUID for ID: Prevents sequential ID enumeration attacks
 * - Email as unique identifier: Natural key for user lookup
 * - No password field: OAuth-only authentication in MVP
 * - Lombok annotations: Reduce boilerplate (getters, setters, builder)
 * 
 * Lifecycle:
 * - Created when user first logs in (via AuthService.loginOrRegister)
 * - Updated when profile changes (via future ProfileService)
 * - Cascade delete to all related records (via foreign key constraints)
 * 
 * Related Tables:
 * - user_profiles: Extended profile information (display name, phone)
 * - user_onboarding: Onboarding progress tracking
 * - user_trading_preferences: Risk limits and trading preferences
 * - user_brokerage_connections: Connected brokerage accounts
 * - trade_authorizations: Trade history
 * 
 * @see UserRepository for database operations
 * @see AuthService for user creation logic
 */
@Entity
@Table(name = "users")
@Data  // Lombok: generates getters, setters, equals, hashCode, toString
@NoArgsConstructor  // Lombok: required by JPA for entity instantiation
@AllArgsConstructor  // Lombok: enables builder pattern
@Builder  // Lombok: enables fluent builder API for object construction
public class User {

    /**
     * Unique identifier for the user.
     * 
     * Using UUID instead of auto-increment for:
     * - Security: No sequential ID enumeration
     * - Distributed systems: No central ID generator needed
     * - Merge-friendly: Easy database replication
     */
    @Id
    @Column(name = "id", columnDefinition = "UUID")
    private UUID id;

    /**
     * User's email address - serves as the primary login identifier.
     * 
     * Constraints:
     * - UNIQUE: No two users can have the same email
     * - NOT NULL: Email is required for all users
     * 
     * Used for:
     * - User lookup during login
     * - Communication (password reset, notifications)
     * - Display in UI
     */
    @Column(name = "email", unique = true, nullable = false)
    private String email;

    /**
     * Authentication provider that created this account.
     * 
     * Current Values:
     * - "GOOGLE": User authenticated via Google OAuth 2.0
     * - "LOCAL": User registered with email/password (future)
     * 
     * Used for:
     * - Analytics (which auth methods are popular)
     * - Conditional logic (e.g., password reset only for LOCAL)
     * - Future: Account linking between providers
     */
    @Column(name = "auth_provider", nullable = false)
    private String authProvider;

    /**
     * Timestamp when the user account was created.
     * 
     * @CreationTimestamp: Hibernate automatically sets on INSERT
     * updatable = false: Prevents modification after creation
     * 
     * Used for:
     * - User analytics and cohort analysis
     * - Account age verification
     * - Audit logging
     */
    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /**
     * Timestamp when the user record was last modified.
     * 
     * @UpdateTimestamp: Hibernate automatically updates on every save
     * 
     * Used for:
     * - Tracking account activity
     * - Debugging and support
     * - Optimistic locking (could be used with @Version)
     */
    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    /**
     * JPA lifecycle callback executed before INSERT.
     * 
     * Ensures UUID is generated if not already set.
     * This handles cases where entity is created via:
     * - Default constructor (new User())
     * - Builder without explicit ID
     * 
     * Note: Builder.id() can override this with a specific UUID.
     */
    @PrePersist
    public void prePersist() {
        if (id == null) {
            id = UUID.randomUUID();
        }
    }
}

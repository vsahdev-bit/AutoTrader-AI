package com.autotrader.auth.repository;

import com.autotrader.auth.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/**
 * UserRepository - Data Access Layer for User entities.
 * 
 * This repository interface provides CRUD operations and custom queries
 * for the User entity. Spring Data JPA automatically generates the
 * implementation at runtime based on method naming conventions.
 * 
 * Inherited Methods (from JpaRepository):
 * - save(User entity): Create or update user
 * - findById(UUID id): Find user by primary key
 * - findAll(): Retrieve all users
 * - delete(User entity): Remove user
 * - count(): Total number of users
 * 
 * Custom Methods (defined below):
 * - findByEmail: Lookup user by email address
 * - existsByEmail: Check if email is already registered
 * 
 * Query Generation:
 * Spring Data JPA parses method names and generates SQL queries:
 * - findByEmail -> SELECT * FROM users WHERE email = ?
 * - existsByEmail -> SELECT COUNT(*) > 0 FROM users WHERE email = ?
 * 
 * Transaction Behavior:
 * - Read methods: Run in read-only transaction
 * - Write methods: Run in read-write transaction
 * - All operations are atomic
 * 
 * @see User for entity definition
 * @see AuthService for business logic using this repository
 */
@Repository
public interface UserRepository extends JpaRepository<User, UUID> {
    
    /**
     * Find a user by their email address.
     * 
     * This is the primary lookup method for authentication, as email
     * serves as the unique identifier for user accounts.
     * 
     * Query: SELECT * FROM users WHERE email = :email
     * 
     * @param email The email address to search for (case-sensitive)
     * @return Optional containing the User if found, empty Optional if not
     * 
     * Usage:
     * <pre>
     * Optional<User> user = userRepository.findByEmail("user@example.com");
     * user.ifPresent(u -> System.out.println("Found: " + u.getId()));
     * </pre>
     */
    Optional<User> findByEmail(String email);
    
    /**
     * Check if a user with the given email already exists.
     * 
     * More efficient than findByEmail when you only need existence check,
     * as it doesn't need to load the full entity.
     * 
     * Query: SELECT COUNT(*) > 0 FROM users WHERE email = :email
     * 
     * @param email The email address to check
     * @return true if a user with this email exists, false otherwise
     * 
     * Usage:
     * <pre>
     * if (userRepository.existsByEmail("new@example.com")) {
     *     throw new EmailAlreadyExistsException();
     * }
     * </pre>
     */
    boolean existsByEmail(String email);
}

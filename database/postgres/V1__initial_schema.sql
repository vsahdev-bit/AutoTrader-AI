-- ============================================================================
-- V1__initial_schema.sql
-- AutoTrader AI - Initial Database Schema
-- ============================================================================
-- 
-- This is the foundational Flyway migration that creates the core database 
-- schema for the AutoTrader AI platform. Flyway uses the version number (V1)
-- to track which migrations have been applied.
--
-- OVERVIEW:
-- The schema supports a two-plane architecture:
--   1. Continuous Intelligence Plane: Stores ML-generated recommendations
--   2. User Execution Plane: Handles authentication, trades, and audit logging
--
-- KEY DESIGN DECISIONS:
--   - UUIDs for all primary keys (scalability, no sequential guessing)
--   - Soft deletes via CASCADE for referential integrity cleanup
--   - JSONB for flexible, schema-less data (signals, order details)
--   - Explicit CHECK constraints for data validation at DB level
--   - Timestamps for audit trails and debugging
-- ============================================================================

-- ----------------------------------------------------------------------------
-- EXTENSION: uuid-ossp
-- ----------------------------------------------------------------------------
-- PostgreSQL extension that provides functions for generating universally 
-- unique identifiers (UUIDs). We use uuid_generate_v4() which creates random
-- UUIDs, making them unpredictable and suitable for security-sensitive IDs.
-- The "IF NOT EXISTS" clause makes this migration idempotent (safe to re-run).
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TABLE: users
-- ============================================================================
-- Core user account table. This is the central entity that all other tables
-- reference. Users can authenticate via multiple providers (Google SSO, email).
--
-- COLUMNS:
--   id            - UUID primary key, auto-generated for each new user
--   email         - User's email address, must be unique across the system
--   auth_provider - How the user authenticates: 'google', 'email', etc.
--                   This helps track SSO vs password-based authentication
--   created_at    - When the account was first created (immutable)
--   updated_at    - Last modification time (should be updated via trigger)
--
-- CONSTRAINTS:
--   - email UNIQUE: Prevents duplicate accounts with same email
--   - All fields NOT NULL: No partial user records allowed
-- ============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    auth_provider VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- TABLE: brokerage_connections
-- ============================================================================
-- Stores the connection status between users and their brokerage accounts
-- (e.g., Robinhood). Note: Actual OAuth tokens are stored in HashiCorp Vault,
-- NOT in this table, for security reasons. This table only tracks metadata.
--
-- DESIGN CHOICE: One-to-one relationship with users (user_id is PK)
-- In MVP, each user has one brokerage. Future versions may support multiple.
--
-- COLUMNS:
--   user_id          - FK to users table, also serves as PK (1:1 relationship)
--   brokerage        - Name of the brokerage: 'robinhood', 'tdameritrade', etc.
--   token_expires_at - When the OAuth token expires (for refresh scheduling)
--   connected_at     - When the user first connected this brokerage
--   updated_at       - Last time connection was refreshed/modified
--
-- SECURITY NOTE:
--   OAuth access tokens and refresh tokens are stored encrypted in Vault,
--   referenced by user_id. This table only stores non-sensitive metadata.
-- ============================================================================
CREATE TABLE brokerage_connections (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    brokerage VARCHAR(50) NOT NULL,
    token_expires_at TIMESTAMP NOT NULL,
    connected_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- TABLE: user_configurations
-- ============================================================================
-- Stores user trading preferences and risk limits. These settings control
-- how the AI generates recommendations and what constraints apply to trades.
--
-- COLUMNS:
--   user_id           - FK to users, also PK (each user has one config)
--   symbols           - Array of stock symbols user wants to track/trade
--                       Example: {'AAPL', 'GOOGL', 'MSFT', 'TSLA'}
--   max_position_pct  - Maximum % of portfolio for a single position (1-100)
--                       Prevents over-concentration in one stock
--   max_trades_per_day - Daily trade limit to prevent overtrading
--   signal_weights    - JSONB object customizing how signals affect recommendations
--                       Example: {"technical": 0.4, "sentiment": 0.3, "fundamental": 0.3}
--   version           - Optimistic locking version for concurrent updates
--                       Incremented on each update to detect conflicts
--   updated_at        - Timestamp of last configuration change
--
-- CHECK CONSTRAINTS:
--   - max_position_pct BETWEEN 1 AND 100: Valid percentage range
--   - max_trades_per_day > 0: Must allow at least one trade
-- ============================================================================
CREATE TABLE user_configurations (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    symbols TEXT[] NOT NULL,
    max_position_pct INTEGER NOT NULL CHECK (max_position_pct BETWEEN 1 AND 100),
    max_trades_per_day INTEGER NOT NULL CHECK (max_trades_per_day > 0),
    signal_weights JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- TABLE: recommendations
-- ============================================================================
-- Stores AI-generated trading recommendations. These are pre-computed by the
-- Continuous Intelligence Plane (ML services) and served to users on-demand.
-- Recommendations are immutable once created - they represent a point-in-time
-- AI decision that can be audited later.
--
-- COLUMNS:
--   id               - Unique identifier for each recommendation
--   user_id          - The user this recommendation is personalized for
--   symbol           - Stock ticker symbol (e.g., 'AAPL', 'GOOGL')
--   action           - AI's recommendation: 'BUY', 'SELL', or 'HOLD'
--   confidence       - Model's confidence score (0.000 to 1.000)
--                      Higher values indicate stronger signals
--   suggested_order  - JSONB with suggested order parameters:
--                      {"quantity": 10, "order_type": "LIMIT", "limit_price": 150.00}
--   model_version    - Version of ML model that generated this recommendation
--                      Critical for debugging and model comparison
--   features_version - Version of feature engineering pipeline used
--                      Ensures reproducibility of recommendations
--   generated_at     - When the ML model created this recommendation
--   created_at       - When this record was inserted into the database
--
-- BUSINESS LOGIC:
--   - Recommendations are generated continuously by ML pipeline
--   - Users see most recent recommendations for their watchlist
--   - Old recommendations are kept for compliance/audit purposes
-- ============================================================================
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL CHECK (action IN ('BUY','SELL','HOLD')),
    confidence NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    suggested_order JSONB NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    features_version VARCHAR(50) NOT NULL,
    generated_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- INDEX: Optimizes the most common query pattern - fetching a user's recent
-- recommendations. DESC ordering on generated_at puts newest first.
-- Compound index (user_id, generated_at) supports efficient filtering + sorting.
CREATE INDEX idx_recommendations_user_time ON recommendations(user_id, generated_at DESC);

-- ============================================================================
-- TABLE: recommendation_explanations
-- ============================================================================
-- Stores human-readable explanations for each AI recommendation.
-- This is a key feature for Explainable AI (XAI) - users need to understand
-- WHY the AI is suggesting a particular action.
--
-- DESIGN: One-to-one with recommendations (recommendation_id is PK)
-- Explanations are generated by the LLM-based Explainability Service.
--
-- COLUMNS:
--   recommendation_id - FK to recommendations table, also serves as PK
--   summary           - Human-readable text explaining the recommendation
--                       Example: "AAPL shows strong momentum with positive 
--                       earnings sentiment. RSI indicates oversold conditions."
--   signals           - JSONB breakdown of contributing signals and their weights
--                       Example: {"rsi": 0.25, "macd": 0.30, "sentiment": 0.45}
--   created_at        - When explanation was generated (may be async)
--
-- NOTE: Explanations may be generated slightly after recommendations due to
-- the LLM processing time. The UI handles this gracefully.
-- ============================================================================
CREATE TABLE recommendation_explanations (
    recommendation_id UUID PRIMARY KEY REFERENCES recommendations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    signals JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- TABLE: trades
-- ============================================================================
-- Records all trade orders placed through the platform. This is the core
-- table for the User Execution Plane and is critical for:
--   1. Tracking order status and execution
--   2. Compliance and audit requirements
--   3. Portfolio management and reporting
--
-- COLUMNS:
--   id                 - Unique trade identifier
--   user_id            - User who initiated the trade
--   symbol             - Stock ticker being traded
--   side               - Trade direction: 'BUY' or 'SELL'
--   order_type         - Order execution type: 'MARKET' or 'LIMIT'
--                        MARKET: Execute at current price
--                        LIMIT: Execute only at specified price or better
--   quantity           - Number of shares to trade (must be positive)
--   limit_price        - Price limit for LIMIT orders (NULL for MARKET orders)
--   status             - Current order status lifecycle:
--                        'PENDING' -> 'SUBMITTED' -> 'FILLED'/'REJECTED'/'CANCELLED'
--   brokerage_order_id - Order ID returned by the brokerage (e.g., Robinhood)
--                        Used for status polling and reconciliation
--   idempotency_key    - UUID that prevents duplicate order submission
--                        Same key = same order, prevents accidental double-trades
--   created_at         - When order was created in our system
--   updated_at         - Last status update time
--
-- SECURITY: Trade execution requires user confirmation and valid session.
-- All trades are logged in audit_logs for compliance.
-- ============================================================================
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY','SELL')),
    order_type VARCHAR(10) NOT NULL CHECK (order_type IN ('MARKET','LIMIT')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    limit_price NUMERIC(10,2),
    status VARCHAR(20) NOT NULL,
    brokerage_order_id VARCHAR(100),
    idempotency_key UUID NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- INDEX: Unique constraint on (user_id, idempotency_key) ensures that
-- the same user cannot submit duplicate orders with the same idempotency key.
-- This is crucial for preventing double-charges in distributed systems where
-- network issues might cause retry attempts.
CREATE UNIQUE INDEX idx_trades_idempotency ON trades(user_id, idempotency_key);

-- ============================================================================
-- TABLE: trade_events
-- ============================================================================
-- Event sourcing table for trade lifecycle tracking. Each state change in a
-- trade's lifecycle is recorded as an immutable event. This provides:
--   1. Complete audit trail of what happened and when
--   2. Ability to replay events for debugging
--   3. Async processing of trade status updates
--
-- COLUMNS:
--   id         - Unique event identifier
--   trade_id   - FK to the trade this event belongs to
--   event_type - Type of lifecycle event:
--                'ORDER_CREATED', 'ORDER_SUBMITTED', 'ORDER_FILLED',
--                'ORDER_PARTIALLY_FILLED', 'ORDER_CANCELLED', 'ORDER_REJECTED'
--   payload    - JSONB with event-specific details:
--                For FILLED: {"filled_quantity": 10, "fill_price": 150.25}
--                For REJECTED: {"reason": "Insufficient funds"}
--   created_at - When this event occurred
--
-- DESIGN: Events are append-only (no updates or deletes in normal operation).
-- The current trade status is derived from the most recent event.
-- ============================================================================
CREATE TABLE trade_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID REFERENCES trades(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- TABLE: audit_logs
-- ============================================================================
-- Immutable audit log for compliance and security monitoring. Financial
-- regulations (SEC, FINRA) require detailed records of all user actions
-- related to trading and account management.
--
-- COLUMNS:
--   id          - Unique log entry identifier
--   user_id     - User who performed the action (NULL for system actions)
--   action      - What action was performed:
--                 'LOGIN', 'LOGOUT', 'TRADE_EXECUTED', 'CONFIG_UPDATED',
--                 'BROKERAGE_CONNECTED', 'BROKERAGE_DISCONNECTED', etc.
--   entity_type - Type of entity affected: 'trade', 'user', 'config', etc.
--   entity_id   - UUID of the affected entity (for linking to source record)
--   metadata    - JSONB with additional context:
--                 {"ip_address": "192.168.1.1", "user_agent": "Chrome/...", 
--                  "old_value": {...}, "new_value": {...}}
--   created_at  - Timestamp of the action (immutable)
--
-- COMPLIANCE NOTE:
--   - This table should NEVER be modified or deleted in production
--   - Retention period: 7+ years per financial regulations
--   - Consider partitioning by date for large-scale deployments
-- ============================================================================
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- INDEX: Enables efficient lookup of all actions by a specific user.
-- Critical for security investigations and user activity reports.
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);

-- INDEX: Enables efficient time-range queries (e.g., "all actions in last 24h").
-- DESC ordering optimizes for recent-first queries which are most common.
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    auth_provider VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Brokerage connections
CREATE TABLE brokerage_connections (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    brokerage VARCHAR(50) NOT NULL,
    token_expires_at TIMESTAMP NOT NULL,
    connected_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- User configurations
CREATE TABLE user_configurations (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    symbols TEXT[] NOT NULL,
    max_position_pct INTEGER NOT NULL CHECK (max_position_pct BETWEEN 1 AND 100),
    max_trades_per_day INTEGER NOT NULL CHECK (max_trades_per_day > 0),
    signal_weights JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Recommendations
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

CREATE INDEX idx_recommendations_user_time ON recommendations(user_id, generated_at DESC);

-- Recommendation explanations
CREATE TABLE recommendation_explanations (
    recommendation_id UUID PRIMARY KEY REFERENCES recommendations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    signals JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Trades
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

CREATE UNIQUE INDEX idx_trades_idempotency ON trades(user_id, idempotency_key);

-- Trade events
CREATE TABLE trade_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID REFERENCES trades(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Audit logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at DESC);

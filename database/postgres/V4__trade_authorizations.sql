-- Trade authorization status enum
DO $$ BEGIN
    CREATE TYPE trade_auth_status AS ENUM ('pending', 'confirmed', 'executed', 'expired', 'cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Trade authorizations table (tracks trade requests and their auth tokens)
CREATE TABLE IF NOT EXISTS trade_authorizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brokerage_connection_id UUID NOT NULL REFERENCES user_brokerage_connections(id),
    
    -- Trade details
    symbol VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'SELL')),
    quantity DECIMAL(18, 8) NOT NULL,
    order_type VARCHAR(20) NOT NULL DEFAULT 'market' CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit')),
    limit_price DECIMAL(18, 4),
    
    -- Authorization
    auth_token_hash VARCHAR(64) NOT NULL,  -- SHA256 hash of the auth token (actual token in Vault)
    pin_hash VARCHAR(64),  -- Optional: hashed PIN for additional verification
    status trade_auth_status NOT NULL DEFAULT 'pending',
    
    -- Timing
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,  -- When the auth token expires
    confirmed_at TIMESTAMP,  -- When user confirmed with PIN
    executed_at TIMESTAMP,  -- When trade was executed
    
    -- Execution result
    executed_price DECIMAL(18, 4),
    executed_quantity DECIMAL(18, 8),
    broker_order_id VARCHAR(255),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_trade_auth_user ON trade_authorizations(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_auth_status ON trade_authorizations(status);
CREATE INDEX IF NOT EXISTS idx_trade_auth_expires ON trade_authorizations(expires_at) WHERE status = 'pending';

-- Trade audit log (immutable record of all trade-related actions)
CREATE TABLE IF NOT EXISTS trade_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_authorization_id UUID REFERENCES trade_authorizations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    action VARCHAR(50) NOT NULL,  -- e.g., 'auth_created', 'auth_confirmed', 'trade_executed', 'auth_expired'
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_audit_user ON trade_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_audit_trade ON trade_audit_log(trade_authorization_id);

-- User trade PINs (optional additional security layer)
CREATE TABLE IF NOT EXISTS user_trade_pins (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    pin_hash VARCHAR(64) NOT NULL,  -- SHA256 hash of PIN
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_user_trade_pins_updated_at ON user_trade_pins;
CREATE TRIGGER update_user_trade_pins_updated_at
    BEFORE UPDATE ON user_trade_pins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to automatically expire old authorizations
CREATE OR REPLACE FUNCTION expire_old_trade_authorizations()
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE trade_authorizations
    SET status = 'expired'
    WHERE status = 'pending'
    AND expires_at < NOW();
    
    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql;

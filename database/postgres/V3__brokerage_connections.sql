-- Brokerage connections table (stores Plaid connection info)
CREATE TABLE IF NOT EXISTS user_brokerage_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plaid_item_id VARCHAR(255) NOT NULL,
    plaid_access_token TEXT NOT NULL,  -- Encrypted in production
    institution_id VARCHAR(50),
    institution_name VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disconnected', 'error')),
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, plaid_item_id)
);

CREATE INDEX IF NOT EXISTS idx_brokerage_connections_user ON user_brokerage_connections(user_id);

-- Brokerage accounts (individual accounts within a connection)
CREATE TABLE IF NOT EXISTS user_brokerage_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES user_brokerage_connections(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plaid_account_id VARCHAR(255) NOT NULL,
    account_name VARCHAR(255),
    account_type VARCHAR(50),  -- e.g., 'investment', 'brokerage'
    account_subtype VARCHAR(50),  -- e.g., 'ira', '401k', 'brokerage'
    mask VARCHAR(10),  -- Last 4 digits
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(connection_id, plaid_account_id)
);

CREATE INDEX IF NOT EXISTS idx_brokerage_accounts_user ON user_brokerage_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_brokerage_accounts_connection ON user_brokerage_accounts(connection_id);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_user_brokerage_connections_updated_at ON user_brokerage_connections;
CREATE TRIGGER update_user_brokerage_connections_updated_at
    BEFORE UPDATE ON user_brokerage_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_brokerage_accounts_updated_at ON user_brokerage_accounts;
CREATE TRIGGER update_user_brokerage_accounts_updated_at
    BEFORE UPDATE ON user_brokerage_accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

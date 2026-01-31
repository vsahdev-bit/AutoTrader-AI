-- =============================================================================
-- V19: Options Watchlist (per-user)
-- =============================================================================
-- Stores user-selected symbols for options workflows.
-- This is separate from the main equity watchlist.
-- =============================================================================

CREATE TABLE IF NOT EXISTS options_watchlist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol VARCHAR(10) NOT NULL,
    company_name VARCHAR(255),
    exchange VARCHAR(20),
    added_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_options_watchlist_user ON options_watchlist(user_id);

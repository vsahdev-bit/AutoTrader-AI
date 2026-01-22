-- =============================================================================
-- V6: Connector Status Schema
-- =============================================================================
-- 
-- This migration creates tables for storing data connector health status.
-- The connector health check service runs every 3 hours and stores results here.
--
-- Tables:
--   - connector_status: Stores the latest status for each connector
--   - connector_status_history: Stores historical status checks for trending
--
-- =============================================================================

-- =============================================================================
-- Table: connector_status
-- =============================================================================
-- Stores the current status for each data connector.
-- Updated by the health check service every 3 hours.
-- =============================================================================

CREATE TABLE IF NOT EXISTS connector_status (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Connector identification
    connector_name VARCHAR(50) NOT NULL UNIQUE,
    connector_type VARCHAR(30) NOT NULL, -- 'paid', 'free', 'social', 'disabled'
    display_name VARCHAR(100) NOT NULL,
    
    -- Status information
    status VARCHAR(20) NOT NULL DEFAULT 'unknown' 
        CHECK (status IN ('connected', 'disconnected', 'error', 'disabled', 'unknown')),
    status_message TEXT,
    
    -- Last successful check details
    last_check_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    last_error_at TIMESTAMP WITH TIME ZONE,
    last_error_message TEXT,
    
    -- Metrics from last check
    articles_fetched INTEGER DEFAULT 0,
    response_time_ms INTEGER,
    
    -- Configuration
    requires_api_key BOOLEAN NOT NULL DEFAULT true,
    has_api_key BOOLEAN NOT NULL DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Table: connector_status_history
-- =============================================================================
-- Stores historical status checks for trending and analysis.
-- Keeps last 7 days of history.
-- =============================================================================

CREATE TABLE IF NOT EXISTS connector_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    connector_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    status_message TEXT,
    articles_fetched INTEGER DEFAULT 0,
    response_time_ms INTEGER,
    error_message TEXT,
    
    checked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Fast lookup by connector name
CREATE INDEX idx_connector_status_name ON connector_status(connector_name);

-- History queries
CREATE INDEX idx_connector_history_name_time 
ON connector_status_history(connector_name, checked_at DESC);

-- Cleanup old history
CREATE INDEX idx_connector_history_checked_at 
ON connector_status_history(checked_at);

-- =============================================================================
-- Seed Initial Connector Data
-- =============================================================================

INSERT INTO connector_status (connector_name, connector_type, display_name, requires_api_key, status) VALUES
    -- Paid connectors (require API keys from Vault)
    ('polygon', 'paid', 'Polygon.io', true, 'unknown'),
    ('alpha_vantage', 'paid', 'Alpha Vantage', true, 'unknown'),
    ('finnhub', 'paid', 'Finnhub', true, 'unknown'),
    ('newsapi', 'paid', 'NewsAPI', true, 'unknown'),
    ('benzinga', 'paid', 'Benzinga', true, 'unknown'),
    ('fmp', 'paid', 'Financial Modeling Prep', true, 'unknown'),
    ('nasdaq_data_link', 'paid', 'Nasdaq Data Link', true, 'unknown'),
    ('iex_cloud', 'disabled', 'IEX Cloud', true, 'disabled'),
    
    -- Free connectors (no API key required)
    ('yahoo_finance', 'free', 'Yahoo Finance', false, 'unknown'),
    ('rss_feeds', 'free', 'RSS Feeds', false, 'unknown'),
    ('sec_edgar', 'free', 'SEC EDGAR', false, 'unknown'),
    ('tipranks', 'free', 'TipRanks', false, 'unknown'),
    
    -- Social connectors (optional API key)
    ('stocktwits', 'social', 'StockTwits', false, 'unknown')
ON CONFLICT (connector_name) DO NOTHING;

-- =============================================================================
-- Table: llm_connector_status
-- =============================================================================
-- Stores the current status for each LLM provider.
-- Updated by the health check service every 3 hours.
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_connector_status (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- LLM provider identification
    provider_name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    
    -- Provider tier (paid or free)
    tier VARCHAR(20) NOT NULL DEFAULT 'paid' 
        CHECK (tier IN ('paid', 'free')),
    
    -- Fallback order (1 = primary, 2 = first fallback, etc.)
    fallback_order INTEGER NOT NULL DEFAULT 1,
    
    -- Status information
    status VARCHAR(20) NOT NULL DEFAULT 'unknown' 
        CHECK (status IN ('connected', 'disconnected', 'error', 'disabled', 'unknown')),
    status_message TEXT,
    
    -- Last check details
    last_check_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    last_error_at TIMESTAMP WITH TIME ZONE,
    last_error_message TEXT,
    
    -- Metrics from last check
    response_time_ms INTEGER,
    
    -- Configuration
    requires_api_key BOOLEAN NOT NULL DEFAULT true,
    has_api_key BOOLEAN NOT NULL DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_llm_connector_status_name ON llm_connector_status(provider_name);
CREATE INDEX IF NOT EXISTS idx_llm_connector_status_order ON llm_connector_status(fallback_order);

-- Seed Initial LLM Connector Data
INSERT INTO llm_connector_status (provider_name, display_name, model_name, tier, fallback_order, requires_api_key, status) VALUES
    ('openai', 'OpenAI', 'gpt-4o-mini', 'paid', 1, true, 'unknown'),
    ('anthropic', 'Anthropic', 'claude-3-haiku', 'paid', 2, true, 'unknown'),
    ('groq', 'Groq', 'llama-3.1-8b-instant', 'free', 3, true, 'unknown')
ON CONFLICT (provider_name) DO NOTHING;

-- Trigger for updated_at
CREATE TRIGGER trigger_update_llm_connector_status_timestamp
    BEFORE UPDATE ON llm_connector_status
    FOR EACH ROW
    EXECUTE FUNCTION update_connector_status_timestamp();

COMMENT ON TABLE llm_connector_status IS 
'Stores current status for each LLM provider. Updated by health check service.';

-- =============================================================================
-- Function: Update timestamp on row update
-- =============================================================================

CREATE OR REPLACE FUNCTION update_connector_status_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_connector_status_timestamp
    BEFORE UPDATE ON connector_status
    FOR EACH ROW
    EXECUTE FUNCTION update_connector_status_timestamp();

-- =============================================================================
-- Function: Cleanup old history (keep last 7 days)
-- =============================================================================

CREATE OR REPLACE FUNCTION cleanup_old_connector_history()
RETURNS void AS $$
BEGIN
    DELETE FROM connector_status_history
    WHERE checked_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE connector_status IS 
'Stores current status for each data connector. Updated by health check service.';

COMMENT ON TABLE connector_status_history IS 
'Historical status checks for trending. Kept for 7 days.';

COMMENT ON COLUMN connector_status.connector_type IS 
'Type: paid (requires API key), free (no key), social (optional key), disabled';

COMMENT ON COLUMN connector_status.status IS 
'Current status: connected, disconnected, error, disabled, unknown';

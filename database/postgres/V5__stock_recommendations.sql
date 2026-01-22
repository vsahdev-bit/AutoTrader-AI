-- =============================================================================
-- V5: Stock Recommendations Schema
-- =============================================================================
-- 
-- This migration creates tables for storing AI-generated stock recommendations.
-- The system stores the last 10 recommendations per symbol for historical view.
--
-- Tables:
--   - stock_recommendations: Stores individual recommendations with scores
--
-- =============================================================================

-- =============================================================================
-- Table: stock_recommendations
-- =============================================================================
-- Stores AI-generated trading recommendations for each stock symbol.
-- Keeps last 10 recommendations per symbol for historical analysis.
-- =============================================================================

CREATE TABLE IF NOT EXISTS stock_recommendations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Stock identification
    symbol VARCHAR(10) NOT NULL,
    
    -- Recommendation details
    action VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'SELL', 'HOLD')),
    score DECIMAL(5, 4) NOT NULL,  -- Raw score from -1 to 1
    normalized_score DECIMAL(5, 4) NOT NULL,  -- Normalized to 0-1 scale
    confidence DECIMAL(4, 3) NOT NULL,  -- 0 to 1
    
    -- Price at recommendation time
    price_at_recommendation DECIMAL(12, 4),
    
    -- Component scores (for transparency)
    news_sentiment_score DECIMAL(5, 4),
    news_momentum_score DECIMAL(5, 4),
    technical_trend_score DECIMAL(5, 4),
    technical_momentum_score DECIMAL(5, 4),
    
    -- Key indicators snapshot
    rsi DECIMAL(5, 4),
    macd_histogram DECIMAL(10, 8),
    price_vs_sma20 DECIMAL(6, 4),
    news_sentiment_1d DECIMAL(5, 4),
    article_count_24h INTEGER DEFAULT 0,
    
    -- Explanation (JSON for flexibility)
    explanation JSONB,
    
    -- Metadata
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    data_sources_used TEXT[],  -- e.g., ['yahoo_finance', 'reddit', 'finnhub']
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Primary lookup: symbol + time (most recent first)
CREATE INDEX idx_recommendations_symbol_time 
ON stock_recommendations(symbol, generated_at DESC);

-- For cleanup job: find old recommendations
CREATE INDEX idx_recommendations_generated_at 
ON stock_recommendations(generated_at);

-- For filtering by action
CREATE INDEX idx_recommendations_symbol_action 
ON stock_recommendations(symbol, action);

-- =============================================================================
-- Function: Cleanup old recommendations (keep last 10 per symbol)
-- =============================================================================

CREATE OR REPLACE FUNCTION cleanup_old_recommendations()
RETURNS void AS $$
BEGIN
    -- Delete recommendations beyond the 10 most recent per symbol
    DELETE FROM stock_recommendations
    WHERE id IN (
        SELECT id FROM (
            SELECT 
                id,
                ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY generated_at DESC) as rn
            FROM stock_recommendations
        ) ranked
        WHERE rn > 10
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE stock_recommendations IS 
'Stores AI-generated trading recommendations. Keeps last 10 per symbol.';

COMMENT ON COLUMN stock_recommendations.score IS 
'Raw recommendation score from -1 (strong sell) to 1 (strong buy)';

COMMENT ON COLUMN stock_recommendations.normalized_score IS 
'Score normalized to 0-1 scale for display. 0.8+ = BUY, <0.5 = SELL';

COMMENT ON COLUMN stock_recommendations.explanation IS 
'JSON object containing human-readable explanation and detailed breakdown';

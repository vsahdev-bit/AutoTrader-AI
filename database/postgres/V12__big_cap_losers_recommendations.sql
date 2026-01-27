-- =============================================================================
-- V12: Big Cap Losers Recommendations Schema
-- =============================================================================
-- 
-- This migration creates a table for storing AI-generated recommendations
-- specifically for big cap losers detected by the crawler service.
-- 
-- These recommendations are independent of user watchlists and are generated
-- automatically when stocks with >$1B market cap fall significantly.
--
-- =============================================================================

-- =============================================================================
-- Table: big_cap_losers_recommendations
-- =============================================================================
CREATE TABLE IF NOT EXISTS big_cap_losers_recommendations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Link to the big_cap_losers record
    big_cap_loser_id INTEGER REFERENCES big_cap_losers(id) ON DELETE CASCADE,
    
    -- Stock identification (denormalized for easier queries)
    symbol VARCHAR(10) NOT NULL,
    
    -- Recommendation details
    action VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'SELL', 'HOLD')),
    score DECIMAL(10, 6) NOT NULL,
    normalized_score DECIMAL(10, 6) NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    
    -- Market regime at time of recommendation
    market_regime VARCHAR(50),
    regime_confidence DECIMAL(5, 4),
    
    -- Component scores
    news_score DECIMAL(10, 6),
    technical_score DECIMAL(10, 6),
    regime_score DECIMAL(10, 6),
    
    -- Price at recommendation
    price_at_recommendation DECIMAL(12, 4),
    
    -- Explanation (JSON object)
    explanation JSONB,
    
    -- Data sources used
    data_sources_used TEXT[],
    
    -- Timestamps
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Primary lookup: symbol + time
CREATE INDEX idx_bcl_rec_symbol_time 
ON big_cap_losers_recommendations(symbol, generated_at DESC);

-- Link to big_cap_losers
CREATE INDEX idx_bcl_rec_loser_id 
ON big_cap_losers_recommendations(big_cap_loser_id);

-- For filtering by action
CREATE INDEX idx_bcl_rec_action 
ON big_cap_losers_recommendations(action);

-- For filtering by trading date (via join with big_cap_losers)
CREATE INDEX idx_bcl_rec_generated 
ON big_cap_losers_recommendations(generated_at DESC);

-- =============================================================================
-- View: Latest recommendations for big cap losers
-- =============================================================================
CREATE OR REPLACE VIEW v_big_cap_losers_with_recommendations AS
SELECT 
    bcl.id as loser_id,
    bcl.symbol,
    bcl.company_name,
    bcl.current_price,
    bcl.price_change,
    bcl.percent_change,
    bcl.market_cap,
    bcl.market_cap_formatted,
    bcl.volume,
    bcl.trading_date,
    bcl.crawled_at,
    rec.id as recommendation_id,
    rec.action,
    rec.score,
    rec.normalized_score,
    rec.confidence,
    rec.market_regime,
    rec.regime_confidence,
    rec.news_score,
    rec.technical_score,
    rec.explanation,
    rec.generated_at as recommendation_generated_at
FROM big_cap_losers bcl
LEFT JOIN LATERAL (
    SELECT *
    FROM big_cap_losers_recommendations r
    WHERE r.symbol = bcl.symbol
    ORDER BY r.generated_at DESC
    LIMIT 1
) rec ON true
WHERE bcl.market_cap >= 1000000000;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE big_cap_losers_recommendations IS 
'Stores AI-generated trading recommendations for big cap losers (>$1B market cap stocks with significant drops)';

COMMENT ON COLUMN big_cap_losers_recommendations.action IS 
'Trading action: BUY, SELL, or HOLD based on normalized_score';

COMMENT ON COLUMN big_cap_losers_recommendations.confidence IS 
'Confidence level 0-1 based on data quality and model certainty';

COMMENT ON COLUMN big_cap_losers_recommendations.market_regime IS 
'Current market regime: volatility, trending, ranging, etc.';

-- ============================================================================
-- V11__big_cap_losers_schema.sql
-- Schema for tracking big cap stocks (>$50B) that have fallen significantly
-- ============================================================================
--
-- This schema supports the Big Cap Losers feature which:
-- 1. Crawls Yahoo Finance losers page every 2 hours
-- 2. Filters for stocks with market cap > $50B
-- 3. Tracks stocks that have fallen > 15%
--
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: big_cap_losers
-- Stores snapshots of big cap stocks that are significant losers
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS big_cap_losers (
    id SERIAL PRIMARY KEY,
    
    -- Stock identification
    symbol VARCHAR(10) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    
    -- Price information
    current_price DECIMAL(12, 4) NOT NULL,
    price_change DECIMAL(12, 4) NOT NULL,
    percent_change DECIMAL(8, 4) NOT NULL,
    
    -- Market data
    market_cap BIGINT NOT NULL,              -- Market cap in dollars
    market_cap_formatted VARCHAR(20),        -- e.g., "$150.5B"
    volume BIGINT,
    avg_volume BIGINT,
    
    -- Additional info
    day_high DECIMAL(12, 4),
    day_low DECIMAL(12, 4),
    fifty_two_week_high DECIMAL(12, 4),
    fifty_two_week_low DECIMAL(12, 4),
    pe_ratio DECIMAL(10, 2),
    
    -- Tracking
    crawled_at TIMESTAMP NOT NULL DEFAULT NOW(),
    trading_date DATE NOT NULL,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Unique constraint to prevent duplicates per crawl
    CONSTRAINT unique_loser_per_crawl UNIQUE (symbol, crawled_at)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_big_cap_losers_symbol ON big_cap_losers(symbol);
CREATE INDEX IF NOT EXISTS idx_big_cap_losers_date ON big_cap_losers(trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_big_cap_losers_crawled ON big_cap_losers(crawled_at DESC);
CREATE INDEX IF NOT EXISTS idx_big_cap_losers_percent ON big_cap_losers(percent_change);
CREATE INDEX IF NOT EXISTS idx_big_cap_losers_market_cap ON big_cap_losers(market_cap DESC);

-- ----------------------------------------------------------------------------
-- Table: big_cap_losers_daily_summary
-- Daily aggregated summary of big cap losers
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS big_cap_losers_daily_summary (
    id SERIAL PRIMARY KEY,
    
    -- Date
    summary_date DATE NOT NULL UNIQUE,
    
    -- Statistics
    total_stocks_tracked INTEGER DEFAULT 0,
    stocks_over_15_percent_drop INTEGER DEFAULT 0,
    worst_performer_symbol VARCHAR(10),
    worst_performer_drop DECIMAL(8, 4),
    
    -- Top losers (JSON array)
    top_losers JSONB,                        -- Array of {symbol, company_name, percent_change, market_cap}
    
    -- Sector breakdown
    sector_breakdown JSONB,                  -- Object with sector counts
    
    -- Timestamps
    generated_at TIMESTAMP DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_big_cap_summary_date ON big_cap_losers_daily_summary(summary_date DESC);

-- ----------------------------------------------------------------------------
-- Table: big_cap_losers_crawl_logs
-- Tracks crawl operations for monitoring
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS big_cap_losers_crawl_logs (
    id SERIAL PRIMARY KEY,
    
    -- Crawl information
    crawl_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Results
    total_losers_found INTEGER DEFAULT 0,
    big_cap_losers_found INTEGER DEFAULT 0,
    over_15_percent_found INTEGER DEFAULT 0,
    
    -- Status
    status VARCHAR(20) NOT NULL,             -- 'success', 'partial', 'failed'
    error_message TEXT,
    
    -- Timing
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_big_cap_crawl_timestamp ON big_cap_losers_crawl_logs(crawl_timestamp DESC);

-- ----------------------------------------------------------------------------
-- Views for easy querying
-- ----------------------------------------------------------------------------

-- View: Current big cap losers over 15% drop
CREATE OR REPLACE VIEW v_big_cap_losers_over_15 AS
SELECT 
    symbol,
    company_name,
    current_price,
    price_change,
    percent_change,
    market_cap,
    market_cap_formatted,
    volume,
    crawled_at,
    trading_date
FROM big_cap_losers
WHERE percent_change <= -15.0
  AND market_cap >= 50000000000  -- $50B
ORDER BY percent_change ASC;

-- View: Latest crawl results
CREATE OR REPLACE VIEW v_big_cap_losers_latest AS
SELECT bcl.*
FROM big_cap_losers bcl
INNER JOIN (
    SELECT symbol, MAX(crawled_at) as max_crawled
    FROM big_cap_losers
    GROUP BY symbol
) latest ON bcl.symbol = latest.symbol AND bcl.crawled_at = latest.max_crawled
WHERE bcl.market_cap >= 50000000000
ORDER BY bcl.percent_change ASC;

-- View: Today's big cap losers
CREATE OR REPLACE VIEW v_big_cap_losers_today AS
SELECT *
FROM big_cap_losers
WHERE trading_date = CURRENT_DATE
  AND market_cap >= 50000000000
ORDER BY percent_change ASC;

-- ----------------------------------------------------------------------------
-- Comments
-- ----------------------------------------------------------------------------
COMMENT ON TABLE big_cap_losers IS 'Tracks big cap stocks (>$50B) that are significant daily losers';
COMMENT ON TABLE big_cap_losers_daily_summary IS 'Daily aggregated summary of big cap losers';
COMMENT ON TABLE big_cap_losers_crawl_logs IS 'Crawl operation logs for the big cap losers service';

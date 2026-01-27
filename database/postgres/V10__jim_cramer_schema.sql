-- ============================================================================
-- V10__jim_cramer_schema.sql
-- Schema for Jim Cramer news articles and AI-generated summaries
-- ============================================================================
-- 
-- This schema supports the Jim Cramer Advice feature which:
-- 1. Crawls news sources daily for Jim Cramer content
-- 2. Uses LLM to extract stock mentions and sentiment
-- 3. Generates daily summaries of Cramer's recommendations
--
-- Data Flow:
--   Web Crawl → jim_cramer_articles (raw) → LLM Analysis → jim_cramer_summaries
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: jim_cramer_articles
-- Stores raw articles mentioning Jim Cramer from various sources
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jim_cramer_articles (
    id SERIAL PRIMARY KEY,
    
    -- Article identification
    article_url TEXT NOT NULL UNIQUE,
    article_hash VARCHAR(64) NOT NULL,  -- SHA256 hash to detect duplicates
    
    -- Source information
    source_name VARCHAR(100) NOT NULL,  -- e.g., 'CNBC', 'Google News', 'TheStreet'
    source_type VARCHAR(50) NOT NULL,   -- 'rss', 'web_crawl', 'api', 'twitter'
    
    -- Article content
    title TEXT NOT NULL,
    description TEXT,
    full_content TEXT,                   -- Full article text if available
    author VARCHAR(255),
    
    -- Media
    thumbnail_url TEXT,
    video_url TEXT,
    
    -- Timestamps
    published_at TIMESTAMP NOT NULL,
    crawled_at TIMESTAMP DEFAULT NOW(),
    
    -- Processing status
    is_processed BOOLEAN DEFAULT FALSE,  -- Whether LLM has analyzed this
    processed_at TIMESTAMP,
    
    -- Metadata (JSON for flexibility)
    metadata JSONB DEFAULT '{}',
    
    -- Indexes
    CONSTRAINT unique_article_hash UNIQUE (article_hash)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_cramer_articles_published ON jim_cramer_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_cramer_articles_source ON jim_cramer_articles(source_name);
CREATE INDEX IF NOT EXISTS idx_cramer_articles_processed ON jim_cramer_articles(is_processed);
CREATE INDEX IF NOT EXISTS idx_cramer_articles_crawled ON jim_cramer_articles(crawled_at DESC);

-- ----------------------------------------------------------------------------
-- Table: jim_cramer_stock_mentions
-- Stores individual stock mentions extracted from articles by LLM
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jim_cramer_stock_mentions (
    id SERIAL PRIMARY KEY,
    
    -- Link to article
    article_id INTEGER NOT NULL REFERENCES jim_cramer_articles(id) ON DELETE CASCADE,
    
    -- Stock information
    symbol VARCHAR(10) NOT NULL,         -- Stock ticker (e.g., 'AAPL')
    company_name VARCHAR(255),           -- Full company name
    
    -- Cramer's sentiment on this stock
    sentiment VARCHAR(20) NOT NULL,      -- 'bullish', 'bearish', 'neutral', 'mixed'
    sentiment_score FLOAT,               -- -1.0 to 1.0
    confidence FLOAT,                    -- LLM confidence 0.0 to 1.0
    
    -- What Cramer said
    recommendation VARCHAR(50),          -- 'buy', 'sell', 'hold', 'avoid', 'watch'
    price_target DECIMAL(10, 2),         -- If mentioned
    reasoning TEXT,                      -- Summary of why
    
    -- Direct quote if available
    quote TEXT,
    
    -- Timestamps
    mentioned_at TIMESTAMP,              -- When in the show/article
    extracted_at TIMESTAMP DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_cramer_mentions_symbol ON jim_cramer_stock_mentions(symbol);
CREATE INDEX IF NOT EXISTS idx_cramer_mentions_article ON jim_cramer_stock_mentions(article_id);
CREATE INDEX IF NOT EXISTS idx_cramer_mentions_sentiment ON jim_cramer_stock_mentions(sentiment);
CREATE INDEX IF NOT EXISTS idx_cramer_mentions_date ON jim_cramer_stock_mentions(extracted_at DESC);

-- ----------------------------------------------------------------------------
-- Table: jim_cramer_daily_summaries
-- AI-generated daily summaries of Cramer's views
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jim_cramer_daily_summaries (
    id SERIAL PRIMARY KEY,
    
    -- Date for this summary
    summary_date DATE NOT NULL UNIQUE,
    
    -- Overall market sentiment from Cramer
    market_sentiment VARCHAR(20),        -- 'bullish', 'bearish', 'neutral', 'mixed'
    market_sentiment_score FLOAT,        -- -1.0 to 1.0
    
    -- LLM-generated summary
    summary_title VARCHAR(500),          -- Headline summary
    summary_text TEXT NOT NULL,          -- Full summary (500-1000 words)
    key_points JSONB,                    -- Array of bullet points
    
    -- Top picks for the day
    top_bullish_picks JSONB,             -- Array of {symbol, reasoning}
    top_bearish_picks JSONB,             -- Array of {symbol, reasoning}
    stocks_to_watch JSONB,               -- Array of {symbol, reasoning}
    
    -- Sectors discussed
    sectors_bullish JSONB,               -- Array of sector names
    sectors_bearish JSONB,
    
    -- Statistics
    total_articles_analyzed INTEGER DEFAULT 0,
    total_stocks_mentioned INTEGER DEFAULT 0,
    
    -- LLM metadata
    llm_provider VARCHAR(50),            -- 'groq', 'anthropic', 'openai'
    llm_model VARCHAR(100),
    
    -- Timestamps
    generated_at TIMESTAMP DEFAULT NOW(),
    
    -- Raw LLM response for debugging
    raw_llm_response JSONB
);

-- Index for date lookups
CREATE INDEX IF NOT EXISTS idx_cramer_summaries_date ON jim_cramer_daily_summaries(summary_date DESC);

-- ----------------------------------------------------------------------------
-- Table: jim_cramer_crawl_logs
-- Tracks crawl operations for monitoring and debugging
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jim_cramer_crawl_logs (
    id SERIAL PRIMARY KEY,
    
    -- Crawl information
    crawl_date DATE NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    
    -- Results
    articles_found INTEGER DEFAULT 0,
    articles_new INTEGER DEFAULT 0,
    articles_duplicate INTEGER DEFAULT 0,
    
    -- Status
    status VARCHAR(20) NOT NULL,         -- 'success', 'partial', 'failed'
    error_message TEXT,
    
    -- Timing
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_cramer_crawl_date ON jim_cramer_crawl_logs(crawl_date DESC);

-- ----------------------------------------------------------------------------
-- Views for easy querying
-- ----------------------------------------------------------------------------

-- View: Today's stock mentions with article info
CREATE OR REPLACE VIEW v_cramer_today_mentions AS
SELECT 
    m.symbol,
    m.company_name,
    m.sentiment,
    m.sentiment_score,
    m.recommendation,
    m.reasoning,
    m.quote,
    a.title AS article_title,
    a.article_url,
    a.source_name,
    a.published_at
FROM jim_cramer_stock_mentions m
JOIN jim_cramer_articles a ON m.article_id = a.id
WHERE a.published_at >= CURRENT_DATE
ORDER BY a.published_at DESC;

-- View: Latest summary with top picks
CREATE OR REPLACE VIEW v_cramer_latest_summary AS
SELECT 
    s.*,
    (SELECT COUNT(*) FROM jim_cramer_articles WHERE published_at >= s.summary_date) as article_count
FROM jim_cramer_daily_summaries s
ORDER BY s.summary_date DESC
LIMIT 1;

-- View: Stock sentiment trends (last 7 days)
CREATE OR REPLACE VIEW v_cramer_stock_trends AS
SELECT 
    m.symbol,
    COUNT(*) as mention_count,
    AVG(m.sentiment_score) as avg_sentiment,
    MODE() WITHIN GROUP (ORDER BY m.sentiment) as dominant_sentiment,
    array_agg(DISTINCT m.recommendation) as recommendations,
    MIN(a.published_at) as first_mention,
    MAX(a.published_at) as last_mention
FROM jim_cramer_stock_mentions m
JOIN jim_cramer_articles a ON m.article_id = a.id
WHERE a.published_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY m.symbol
ORDER BY mention_count DESC;

-- ----------------------------------------------------------------------------
-- Comments
-- ----------------------------------------------------------------------------
COMMENT ON TABLE jim_cramer_articles IS 'Raw articles mentioning Jim Cramer from various news sources';
COMMENT ON TABLE jim_cramer_stock_mentions IS 'Individual stock mentions extracted from articles by LLM';
COMMENT ON TABLE jim_cramer_daily_summaries IS 'AI-generated daily summaries of Cramers market views';
COMMENT ON TABLE jim_cramer_crawl_logs IS 'Crawl operation logs for monitoring';

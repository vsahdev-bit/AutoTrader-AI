-- Research Stocks Schema
-- Stores scraped stock data from Yahoo Finance for research/filtering

CREATE TABLE IF NOT EXISTS research_stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    price DECIMAL(15, 4),
    change DECIMAL(15, 4),
    change_percent DECIMAL(10, 4),
    volume BIGINT,
    avg_volume_3m BIGINT,
    market_cap BIGINT,
    pe_ratio DECIMAL(15, 4),
    source VARCHAR(50) NOT NULL,  -- 'most-active', 'gainers', 'losers'
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint on symbol to avoid duplicates per scrape session
    CONSTRAINT unique_symbol_per_scrape UNIQUE (symbol, scraped_at)
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_research_stocks_symbol ON research_stocks(symbol);
CREATE INDEX IF NOT EXISTS idx_research_stocks_scraped_at ON research_stocks(scraped_at);
CREATE INDEX IF NOT EXISTS idx_research_stocks_market_cap ON research_stocks(market_cap);
CREATE INDEX IF NOT EXISTS idx_research_stocks_change_percent ON research_stocks(change_percent);

-- Table to track scrape metadata
CREATE TABLE IF NOT EXISTS research_stocks_scrape_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'in_progress',  -- 'in_progress', 'completed', 'failed'
    stocks_count INTEGER DEFAULT 0,
    error_message TEXT,
    sources_scraped TEXT[]  -- Array of sources that were scraped
);

-- Table to store search criteria definitions
CREATE TABLE IF NOT EXISTS research_stock_criteria (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    sql_hint TEXT,  -- Hint for LLM to generate SQL
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Insert default criteria
INSERT INTO research_stock_criteria (name, description, sql_hint) VALUES
    ('large_cap', 'Show me stocks with market cap of greater than $2B', 'market_cap > 2000000000'),
    ('big_drop', 'Show me stocks with daily price drop of more than 15%', 'change_percent < -15'),
    ('volume_deviation', 'Show me stocks where today''s volume is high/low from average vol (3M) by 50%', 'ABS(volume - avg_volume_3m) > (avg_volume_3m * 0.5)')
ON CONFLICT (name) DO NOTHING;

COMMENT ON TABLE research_stocks IS 'Stores scraped stock data from Yahoo Finance for research filtering';
COMMENT ON TABLE research_stocks_scrape_runs IS 'Tracks metadata for each scrape run';
COMMENT ON TABLE research_stock_criteria IS 'Defines available search criteria for stock filtering';

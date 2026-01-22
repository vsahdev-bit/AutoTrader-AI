-- =============================================================================
-- ClickHouse Schema for News and Sentiment Data
-- =============================================================================
--
-- This schema defines the time-series tables for storing news articles
-- and sentiment analysis results in ClickHouse. Optimized for:
-- - Fast time-range queries
-- - Efficient aggregation by symbol
-- - Real-time analytics for the recommendation engine
--
-- Tables:
-- - news_articles: Raw news articles with sentiment scores
-- - news_sentiment_aggregates: Pre-computed sentiment aggregates by symbol/time
-- - symbol_news_features: ML features derived from news for recommendations
--
-- =============================================================================

-- =============================================================================
-- Table: news_articles
-- =============================================================================
-- Stores individual news articles with sentiment analysis results.
-- Partitioned by month for efficient time-based queries and data retention.
--
-- Typical Queries:
-- - Get recent articles for a symbol
-- - Calculate average sentiment over time windows
-- - Find high-impact news (high confidence sentiment)
-- =============================================================================
CREATE TABLE IF NOT EXISTS news_articles
(
    -- Article identification
    article_id String COMMENT 'Unique article ID (MD5 hash of URL + published_at)',
    
    -- Content
    title String COMMENT 'Article headline',
    summary String COMMENT 'Article summary or first paragraph',
    url String COMMENT 'Link to original article',
    
    -- Source information
    source LowCardinality(String) COMMENT 'Source connector (alpha_vantage, finnhub, newsapi, rss_*)',
    source_name String COMMENT 'Human-readable source name (Reuters, Bloomberg, etc.)',
    
    -- Timestamps
    published_at DateTime COMMENT 'When article was published',
    fetched_at DateTime COMMENT 'When we retrieved the article',
    inserted_at DateTime DEFAULT now() COMMENT 'When inserted into ClickHouse',
    
    -- Stock associations
    symbols Array(String) COMMENT 'Stock symbols mentioned in article',
    categories Array(LowCardinality(String)) COMMENT 'Article categories (earnings, m&a, etc.)',
    
    -- Sentiment analysis results
    sentiment_score Float32 COMMENT 'Sentiment score from -1.0 (bearish) to +1.0 (bullish)',
    sentiment_label LowCardinality(String) COMMENT 'Categorical label (very_bearish to very_bullish)',
    sentiment_confidence Float32 COMMENT 'Model confidence in sentiment prediction (0-1)',
    sentiment_analyzer LowCardinality(String) COMMENT 'Which analyzer produced this (finbert, llm, hybrid)',
    sentiment_reasoning Nullable(String) COMMENT 'LLM explanation for sentiment (when available)',
    
    -- Optional metadata
    author Nullable(String) COMMENT 'Article author',
    image_url Nullable(String) COMMENT 'Article thumbnail/header image'
)
ENGINE = MergeTree()
-- Partition by month for efficient data management and retention
PARTITION BY toYYYYMM(published_at)
-- Order by time and article_id for efficient time-range and lookup queries
ORDER BY (published_at, article_id)
-- TTL for automatic data retention (keep 1 year of data)
TTL published_at + INTERVAL 1 YEAR
SETTINGS index_granularity = 8192;

-- Index for symbol-based queries (most common access pattern)
ALTER TABLE news_articles ADD INDEX idx_symbols symbols TYPE bloom_filter() GRANULARITY 4;

-- Index for source filtering
ALTER TABLE news_articles ADD INDEX idx_source source TYPE set(100) GRANULARITY 4;


-- =============================================================================
-- Table: news_sentiment_aggregates
-- =============================================================================
-- Pre-computed sentiment aggregates by symbol and time window.
-- Updated periodically by aggregation jobs for fast dashboard queries.
--
-- Time Windows:
-- - 1h: Hourly sentiment (for intraday analysis)
-- - 1d: Daily sentiment (most common)
-- - 1w: Weekly sentiment (for trend analysis)
-- =============================================================================
CREATE TABLE IF NOT EXISTS news_sentiment_aggregates
(
    -- Dimensions
    symbol String COMMENT 'Stock symbol',
    time_window LowCardinality(String) COMMENT 'Aggregation window (1h, 1d, 1w)',
    window_start DateTime COMMENT 'Start of time window',
    window_end DateTime COMMENT 'End of time window',
    
    -- Sentiment metrics
    article_count UInt32 COMMENT 'Number of articles in window',
    avg_sentiment Float32 COMMENT 'Average sentiment score',
    min_sentiment Float32 COMMENT 'Most bearish sentiment in window',
    max_sentiment Float32 COMMENT 'Most bullish sentiment in window',
    sentiment_std Float32 COMMENT 'Standard deviation of sentiment',
    
    -- Weighted sentiment (by confidence)
    weighted_avg_sentiment Float32 COMMENT 'Confidence-weighted average sentiment',
    total_confidence Float32 COMMENT 'Sum of confidence scores',
    
    -- Category breakdown
    earnings_sentiment Nullable(Float32) COMMENT 'Avg sentiment for earnings news',
    earnings_count UInt32 DEFAULT 0 COMMENT 'Count of earnings articles',
    
    -- Source breakdown (for quality weighting)
    premium_source_sentiment Nullable(Float32) COMMENT 'Avg sentiment from premium sources',
    premium_source_count UInt32 DEFAULT 0 COMMENT 'Count from premium sources',
    
    -- Metadata
    computed_at DateTime DEFAULT now() COMMENT 'When this aggregate was computed'
)
ENGINE = ReplacingMergeTree(computed_at)
PARTITION BY toYYYYMM(window_start)
ORDER BY (symbol, time_window, window_start)
SETTINGS index_granularity = 8192;


-- =============================================================================
-- Table: symbol_news_features
-- =============================================================================
-- ML features derived from news data for the recommendation engine.
-- These features are computed daily and used as inputs to the ML model.
--
-- Features capture:
-- - Recent sentiment trends
-- - News volume (attention indicator)
-- - Sentiment volatility
-- - Category-specific signals
-- =============================================================================
CREATE TABLE IF NOT EXISTS symbol_news_features
(
    -- Identification
    symbol String COMMENT 'Stock symbol',
    feature_date Date COMMENT 'Date these features are computed for',
    
    -- Short-term sentiment (1-3 days)
    sentiment_1d Float32 COMMENT 'Average sentiment last 24 hours',
    sentiment_3d Float32 COMMENT 'Average sentiment last 3 days',
    sentiment_momentum Float32 COMMENT 'Sentiment change (1d vs 3d)',
    
    -- Medium-term sentiment (1-2 weeks)  
    sentiment_7d Float32 COMMENT 'Average sentiment last 7 days',
    sentiment_14d Float32 COMMENT 'Average sentiment last 14 days',
    sentiment_trend Float32 COMMENT 'Sentiment trend (7d vs 14d)',
    
    -- News volume features
    article_count_1d UInt32 COMMENT 'Articles in last 24 hours',
    article_count_7d UInt32 COMMENT 'Articles in last 7 days',
    volume_ratio Float32 COMMENT 'Recent volume vs average (attention spike)',
    
    -- Sentiment quality/confidence
    avg_confidence_1d Float32 COMMENT 'Average model confidence (quality indicator)',
    high_confidence_ratio Float32 COMMENT 'Ratio of high-confidence articles',
    
    -- Volatility features
    sentiment_volatility_7d Float32 COMMENT 'Std dev of daily sentiment (uncertainty)',
    sentiment_range_7d Float32 COMMENT 'Max-min sentiment range',
    
    -- Category-specific features
    earnings_sentiment Nullable(Float32) COMMENT 'Recent earnings news sentiment',
    analyst_sentiment Nullable(Float32) COMMENT 'Recent analyst coverage sentiment',
    product_sentiment Nullable(Float32) COMMENT 'Recent product news sentiment',
    
    -- Metadata
    computed_at DateTime DEFAULT now() COMMENT 'When features were computed'
)
ENGINE = ReplacingMergeTree(computed_at)
PARTITION BY toYYYYMM(feature_date)
ORDER BY (feature_date, symbol)
SETTINGS index_granularity = 8192;


-- =============================================================================
-- Materialized View: Real-time Symbol Sentiment
-- =============================================================================
-- Automatically aggregates sentiment by symbol as articles are inserted.
-- Provides near-real-time sentiment updates for the dashboard.
-- =============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_symbol_sentiment_realtime
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMMDD(published_date)
ORDER BY (published_date, symbol)
AS SELECT
    toDate(published_at) AS published_date,
    arrayJoin(symbols) AS symbol,
    count() AS article_count,
    sum(sentiment_score) AS sentiment_sum,
    sum(sentiment_score * sentiment_confidence) AS weighted_sentiment_sum,
    sum(sentiment_confidence) AS confidence_sum
FROM news_articles
GROUP BY published_date, symbol;


-- =============================================================================
-- Sample Queries
-- =============================================================================

-- Get recent sentiment for a symbol
-- SELECT 
--     toDate(published_at) as date,
--     avg(sentiment_score) as avg_sentiment,
--     count() as article_count
-- FROM news_articles
-- WHERE has(symbols, 'AAPL')
--   AND published_at >= now() - INTERVAL 7 DAY
-- GROUP BY date
-- ORDER BY date;

-- Get top movers by sentiment change
-- SELECT
--     symbol,
--     sentiment_1d,
--     sentiment_7d,
--     sentiment_momentum,
--     article_count_1d
-- FROM symbol_news_features
-- WHERE feature_date = today()
-- ORDER BY abs(sentiment_momentum) DESC
-- LIMIT 10;

-- Get high-impact news (high confidence, strong sentiment)
-- SELECT
--     title,
--     symbols,
--     sentiment_score,
--     sentiment_confidence,
--     source_name,
--     published_at
-- FROM news_articles
-- WHERE published_at >= now() - INTERVAL 24 HOUR
--   AND sentiment_confidence > 0.8
--   AND abs(sentiment_score) > 0.5
-- ORDER BY published_at DESC
-- LIMIT 20;

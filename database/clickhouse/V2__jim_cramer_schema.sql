-- ============================================================================
-- V2__jim_cramer_schema.sql
-- ClickHouse schema for Jim Cramer raw article storage
-- ============================================================================
-- 
-- ClickHouse is used for high-volume raw article storage with efficient
-- time-series queries. This complements PostgreSQL which stores the
-- processed summaries and stock mentions.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Table: jim_cramer_raw_articles
-- High-volume storage for all crawled articles
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jim_cramer_raw_articles (
    -- Article identification
    article_id UUID DEFAULT generateUUIDv4(),
    article_url String,
    article_hash String,
    
    -- Source
    source_name LowCardinality(String),
    source_type LowCardinality(String),
    
    -- Content
    title String,
    description String,
    full_content String,
    author String,
    
    -- Media URLs
    thumbnail_url String,
    video_url String,
    
    -- Timestamps
    published_at DateTime,
    crawled_at DateTime DEFAULT now(),
    
    -- Processing
    is_processed UInt8 DEFAULT 0,
    
    -- Metadata as JSON string
    metadata String DEFAULT '{}'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(published_at)
ORDER BY (source_name, published_at, article_hash)
TTL published_at + INTERVAL 90 DAY  -- Keep raw articles for 90 days
SETTINGS index_granularity = 8192;

-- ----------------------------------------------------------------------------
-- Table: jim_cramer_article_content
-- Full text content for search (separate for efficiency)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jim_cramer_article_content (
    article_hash String,
    full_text String,
    word_count UInt32,
    crawled_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(crawled_at)
ORDER BY (article_hash)
TTL crawled_at + INTERVAL 90 DAY;

-- ----------------------------------------------------------------------------
-- Materialized View: Daily article counts by source
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_cramer_daily_counts
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, source_name)
AS SELECT
    toDate(crawled_at) AS date,
    source_name,
    count() AS article_count
FROM jim_cramer_raw_articles
GROUP BY date, source_name;

-- =============================================================================
-- V21: Recommendation Run Articles (Top News per run)
-- =============================================================================
-- Stores the exact set of article_ids used for each symbol during a
-- recommendation generation run.
-- =============================================================================

CREATE TABLE IF NOT EXISTS recommendation_run_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    article_ids TEXT NOT NULL, -- JSON array of ClickHouse article_id strings
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(run_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_recommendation_run_articles_run
    ON recommendation_run_articles (run_id);

CREATE INDEX IF NOT EXISTS idx_recommendation_run_articles_symbol
    ON recommendation_run_articles (symbol);

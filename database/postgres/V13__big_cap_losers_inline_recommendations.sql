-- =============================================================================
-- V13: Inline AI recommendation fields on big_cap_losers
-- =============================================================================
--
-- Spec alignment:
-- - Big Cap Losers snapshot is stored in big_cap_losers (latest only)
-- - Recommendation engine outputs are stored on the same rows
--
-- This migration adds columns to big_cap_losers to store the recommendation
-- fields directly and avoids needing to join big_cap_losers_recommendations.
-- =============================================================================

ALTER TABLE big_cap_losers
  ADD COLUMN IF NOT EXISTS action VARCHAR(10) CHECK (action IN ('BUY','SELL','HOLD')),
  ADD COLUMN IF NOT EXISTS score DECIMAL(10, 6),
  ADD COLUMN IF NOT EXISTS normalized_score DECIMAL(10, 6),
  ADD COLUMN IF NOT EXISTS confidence DECIMAL(5, 4) CHECK (confidence >= 0 AND confidence <= 1),
  ADD COLUMN IF NOT EXISTS market_regime VARCHAR(50),
  ADD COLUMN IF NOT EXISTS regime_confidence DECIMAL(5, 4),
  ADD COLUMN IF NOT EXISTS news_score DECIMAL(10, 6),
  ADD COLUMN IF NOT EXISTS technical_score DECIMAL(10, 6),
  ADD COLUMN IF NOT EXISTS details_url TEXT,
  ADD COLUMN IF NOT EXISTS top_news JSONB,
  ADD COLUMN IF NOT EXISTS explanation JSONB,
  ADD COLUMN IF NOT EXISTS recommendation_generated_at TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS recommendation_error TEXT;

CREATE INDEX IF NOT EXISTS idx_big_cap_losers_action ON big_cap_losers(action);
CREATE INDEX IF NOT EXISTS idx_big_cap_losers_rec_generated_at ON big_cap_losers(recommendation_generated_at DESC);

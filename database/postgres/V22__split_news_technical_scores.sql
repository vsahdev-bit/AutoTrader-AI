-- =============================================================================
-- V22: Split News vs Technical Scores/Confidence/Actions
-- =============================================================================
-- Adds new per-track fields to stock_recommendations.
-- We keep legacy combined columns for now (action/score/normalized_score/confidence)
-- but the application will stop writing them.

ALTER TABLE stock_recommendations
  ADD COLUMN IF NOT EXISTS news_action VARCHAR(10) CHECK (news_action IN ('BUY','SELL','HOLD')),
  ADD COLUMN IF NOT EXISTS news_normalized_score DECIMAL(5,4),
  ADD COLUMN IF NOT EXISTS news_confidence DECIMAL(4,3),
  ADD COLUMN IF NOT EXISTS technical_action VARCHAR(10) CHECK (technical_action IN ('BUY','SELL','HOLD')),
  ADD COLUMN IF NOT EXISTS technical_normalized_score DECIMAL(5,4),
  ADD COLUMN IF NOT EXISTS technical_confidence DECIMAL(4,3);

-- Helpful indexes for filtering
CREATE INDEX IF NOT EXISTS idx_recommendations_symbol_news_action
  ON stock_recommendations(symbol, news_action);

CREATE INDEX IF NOT EXISTS idx_recommendations_symbol_technical_action
  ON stock_recommendations(symbol, technical_action);

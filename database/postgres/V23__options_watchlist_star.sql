-- =============================================================================
-- V23: Add star flag to options_watchlist
-- =============================================================================

ALTER TABLE options_watchlist
ADD COLUMN IF NOT EXISTS is_starred BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_options_watchlist_user_star
  ON options_watchlist (user_id, is_starred);

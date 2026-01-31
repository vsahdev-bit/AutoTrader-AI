-- =============================================================================
-- V20: Watchlist Star / Pin support
-- =============================================================================

ALTER TABLE user_watchlist
  ADD COLUMN IF NOT EXISTS is_starred BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_user_watchlist_starred
  ON user_watchlist (user_id, is_starred);

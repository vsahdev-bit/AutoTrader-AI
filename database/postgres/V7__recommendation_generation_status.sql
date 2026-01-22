-- =============================================================================
-- V7: Recommendation Generation Status Schema
-- =============================================================================
-- 
-- This migration creates a table to track the status of recommendation
-- generation runs, allowing the UI to show "Calculating" state.
--
-- =============================================================================

CREATE TABLE IF NOT EXISTS recommendation_generation_status (
    id INTEGER PRIMARY KEY DEFAULT 1,  -- Singleton row
    status VARCHAR(20) NOT NULL DEFAULT 'idle' 
        CHECK (status IN ('idle', 'running', 'completed', 'failed')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    symbols TEXT,  -- JSON array of symbols being processed
    error_message TEXT,
    
    -- Ensure only one row exists
    CONSTRAINT single_row CHECK (id = 1)
);

-- Insert default row
INSERT INTO recommendation_generation_status (id, status) 
VALUES (1, 'idle')
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE recommendation_generation_status IS 
'Tracks the status of recommendation generation runs (singleton table)';

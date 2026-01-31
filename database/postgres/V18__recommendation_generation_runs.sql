-- =============================================================================
-- V18: Recommendation Generation Runs (per-run status tracking)
-- =============================================================================
--
-- Adds a per-run status table so the UI can safely poll a specific on-demand
-- generation run (jobId/runId) without collisions between concurrent runs.
--
-- This is intentionally additive and keeps the existing singleton
-- recommendation_generation_status table for backward compatibility.
-- =============================================================================

CREATE TABLE IF NOT EXISTS recommendation_generation_runs (
    run_id UUID PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('idle', 'running', 'completed', 'failed')),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    symbols TEXT, -- JSON array of symbols being processed
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_recommendation_generation_runs_started_at
    ON recommendation_generation_runs (started_at DESC);

COMMENT ON TABLE recommendation_generation_runs IS
'Tracks status of individual recommendation generation runs (run_id/job_id)';

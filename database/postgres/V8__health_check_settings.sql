-- V8: Health Check Settings
-- Stores toggle state for data connector and LLM connector health checks

CREATE TABLE IF NOT EXISTS health_check_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(50) UNIQUE NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default settings (both enabled by default)
INSERT INTO health_check_settings (setting_key, enabled) VALUES
    ('data_connectors_health_check', TRUE),
    ('llm_connectors_health_check', TRUE)
ON CONFLICT (setting_key) DO NOTHING;

-- Add comment
COMMENT ON TABLE health_check_settings IS 
'Stores health check toggle states. When enabled=FALSE, the health check service skips that category.';

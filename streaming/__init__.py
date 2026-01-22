"""
Streaming Package
=================

This package contains the data streaming and processing components for
the AutoTrader AI Continuous Intelligence Plane.

Subpackages:
- connectors: News data source connectors (Alpha Vantage, Finnhub, etc.)
- processors: Data processing pipelines and schedulers
- kafka_configs: Kafka topic and consumer configurations

Main Components:
- NewsPipeline: Orchestrates news fetching, sentiment analysis, storage
- PipelineScheduler: Manages scheduled execution of pipelines
- Config: Central configuration management

Quick Start:
-----------
```python
from streaming.config import Config
from streaming.processors import NewsPipeline

# Load config from environment
config = Config.from_env()

# Create and run pipeline
pipeline = NewsPipeline(config.to_pipeline_config())
await pipeline.initialize()
results = await pipeline.run()
```

CLI Usage:
----------
```bash
# Run pipeline continuously
python -m streaming.run_pipeline

# Run once (for testing)
python -m streaming.run_pipeline --once

# Show configuration
python -m streaming.run_pipeline --show-config
```
"""

from .config import Config

__all__ = ["Config"]
__version__ = "1.0.0"

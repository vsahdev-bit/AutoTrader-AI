"""
Stream Processors Package
=========================

This package contains data processing pipelines for the AutoTrader AI
Continuous Intelligence Plane. Processors fetch, analyze, and store
news and market data for the recommendation engine.

Main Components:
- NewsPipeline: Orchestrates news fetching, sentiment analysis, and storage
- Scheduler: Manages periodic execution of pipeline jobs
"""

from .news_pipeline import NewsPipeline, NewsProcessorConfig
from .scheduler import PipelineScheduler

__all__ = [
    "NewsPipeline",
    "NewsProcessorConfig", 
    "PipelineScheduler",
]

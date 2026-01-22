#!/usr/bin/env python3
"""
News Pipeline Runner
====================

Main entry point for running the news processing pipeline.
This script initializes and runs the complete news ingestion,
sentiment analysis, and storage pipeline.

Usage:
------
# Run with default settings (uses environment variables)
python -m streaming.run_pipeline

# Run once (single fetch, useful for testing)
python -m streaming.run_pipeline --once

# Run with specific symbols
SYMBOLS=AAPL,GOOGL,MSFT python -m streaming.run_pipeline

# Run with LLM analysis enabled
ENABLE_LLM_ANALYSIS=true OPENAI_API_KEY=sk-... python -m streaming.run_pipeline

Environment Variables:
---------------------
See streaming/config.py for full list of configuration options.

Required for production:
- At least one news API key (ALPHA_VANTAGE_API_KEY, FINNHUB_API_KEY, or NEWSAPI_API_KEY)

Optional but recommended:
- OPENAI_API_KEY: For LLM sentiment analysis
- CLICKHOUSE_HOST: For feature storage
- REDIS_URL: For caching
"""

import asyncio
import argparse
import logging
import signal
import sys
from typing import Optional

from streaming.config import Config
from streaming.processors import NewsPipeline, PipelineScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


async def run_once(config: Config) -> dict:
    """
    Run the pipeline once and return results.
    
    Useful for testing and debugging.
    """
    pipeline_config = config.to_pipeline_config()
    pipeline = NewsPipeline(pipeline_config)
    
    try:
        await pipeline.initialize()
        results = await pipeline.run()
        
        logger.info(f"Pipeline run complete: {len(results)} articles processed")
        return {
            "articles_processed": len(results),
            "metrics": pipeline.get_metrics(),
        }
        
    finally:
        await pipeline.close()


async def run_continuous(config: Config):
    """
    Run the pipeline continuously with scheduled intervals.
    
    Runs until interrupted (Ctrl+C or SIGTERM).
    """
    pipeline_config = config.to_pipeline_config()
    pipeline = NewsPipeline(pipeline_config)
    scheduler = PipelineScheduler()
    
    # Setup signal handlers
    shutdown_event = asyncio.Event()
    
    def handle_shutdown(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        shutdown_event.set()
    
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: handle_shutdown(s))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass
    
    try:
        await pipeline.initialize()
        
        # Register pipeline job
        scheduler.register_job(
            name="news_pipeline",
            callback=pipeline.run,
            interval_seconds=config.fetch_interval_minutes * 60,
            run_immediately=True,
        )
        
        # Start scheduler
        await scheduler.start()
        
        logger.info("Pipeline running. Press Ctrl+C to stop.")
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
    finally:
        await scheduler.stop()
        await pipeline.close()
        
        # Print final metrics
        metrics = pipeline.get_metrics()
        logger.info("Final metrics:")
        for key, value in metrics.items():
            logger.info(f"  {key}: {value}")


async def run_feature_computation(config: Config):
    """
    Run feature computation job (computes ML features from raw articles).
    
    This is typically run less frequently (e.g., hourly) to update
    the symbol_news_features table in ClickHouse.
    """
    # TODO: Implement feature computation job
    logger.warning("Feature computation not yet implemented")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AutoTrader AI News Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run pipeline once and exit (default: run continuously)",
    )
    
    parser.add_argument(
        "--compute-features",
        action="store_true",
        help="Run feature computation job instead of news pipeline",
    )
    
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print configuration and exit",
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration
    config = Config.from_env()
    
    if args.show_config:
        config.print_summary()
        return
    
    # Print startup message
    logger.info("=" * 60)
    logger.info("AutoTrader AI - News Processing Pipeline")
    logger.info("=" * 60)
    config.print_summary()
    
    # Validate configuration
    if not config.has_news_api_keys:
        logger.warning("No news API keys configured!")
        logger.warning("Only RSS feeds will be used for news collection.")
        logger.warning("Set ALPHA_VANTAGE_API_KEY, FINNHUB_API_KEY, or NEWSAPI_API_KEY for more sources.")
    
    # Run the appropriate mode
    try:
        if args.compute_features:
            asyncio.run(run_feature_computation(config))
        elif args.once:
            result = asyncio.run(run_once(config))
            print(f"\nResults: {result}")
        else:
            asyncio.run(run_continuous(config))
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        sys.exit(1)
    
    logger.info("Pipeline shutdown complete")


if __name__ == "__main__":
    main()

"""
Jim Cramer Advice Service
==========================

Main service that orchestrates:
1. Crawling news sources for Jim Cramer content
2. Analyzing articles with LLM
3. Storing results in PostgreSQL and ClickHouse
4. Generating daily summaries

Runs daily at 9 AM PST via Docker cron.

Usage:
    # Run once
    python service.py --once
    
    # Run with scheduler (for Docker)
    python service.py --schedule
"""

import asyncio
import argparse
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional
import asyncpg
import json

# Add parent path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jim_cramer_service.crawler import JimCramerCrawler, CramerArticle
from jim_cramer_service.analyzer import JimCramerAnalyzer, ArticleAnalysis, DailySummary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


class JimCramerService:
    """
    Main service for Jim Cramer news crawling and analysis.
    """
    
    def __init__(
        self,
        postgres_url: Optional[str] = None,
        clickhouse_url: Optional[str] = None,
    ):
        """
        Initialize the service.
        
        Args:
            postgres_url: PostgreSQL connection string
            clickhouse_url: ClickHouse connection string (optional)
        """
        self.postgres_url = postgres_url or os.getenv("DATABASE_URL")
        self.clickhouse_url = clickhouse_url or os.getenv("CLICKHOUSE_URL")
        
        self.crawler = JimCramerCrawler(
            max_articles_per_source=20,
            lookback_hours=24,
        )
        self.analyzer = JimCramerAnalyzer()
        
        self.pg_pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize connections."""
        logger.info("Initializing Jim Cramer service...")
        
        # Initialize crawler
        await self.crawler.initialize()
        
        # Initialize PostgreSQL
        if self.postgres_url:
            try:
                self.pg_pool = await asyncpg.create_pool(
                    self.postgres_url,
                    min_size=2,
                    max_size=10,
                )
                logger.info("✓ Connected to PostgreSQL")
            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL: {e}")
        else:
            logger.warning("No PostgreSQL URL configured")
        
        logger.info("Jim Cramer service initialized")
    
    async def close(self):
        """Close connections."""
        await self.crawler.close()
        if self.pg_pool:
            await self.pg_pool.close()
    
    async def run(self) -> dict:
        """
        Run the full crawl, analyze, and summarize pipeline.
        
        Returns:
            dict with statistics about the run
        """
        start_time = datetime.now(timezone.utc)
        stats = {
            "started_at": start_time.isoformat(),
            "articles_crawled": 0,
            "articles_new": 0,
            "articles_analyzed": 0,
            "stocks_mentioned": 0,
            "summary_generated": False,
            "errors": [],
        }
        
        try:
            # Step 1: Crawl all sources
            logger.info("=" * 60)
            logger.info("STEP 1: Crawling news sources")
            logger.info("=" * 60)
            
            articles = await self.crawler.crawl_all_sources()
            stats["articles_crawled"] = len(articles)
            logger.info(f"Crawled {len(articles)} articles")
            
            if not articles:
                logger.warning("No articles found!")
                return stats
            
            # Step 2: Store articles and check for duplicates
            logger.info("=" * 60)
            logger.info("STEP 2: Storing articles")
            logger.info("=" * 60)
            
            new_articles = []
            for article in articles:
                is_new = await self._store_article(article)
                if is_new:
                    new_articles.append(article)
            
            stats["articles_new"] = len(new_articles)
            logger.info(f"New articles: {len(new_articles)}")
            
            # Step 3: Analyze new articles with LLM
            logger.info("=" * 60)
            logger.info("STEP 3: Analyzing articles with LLM")
            logger.info("=" * 60)
            
            all_mentions = []
            analyzed_articles = []
            
            for i, article in enumerate(new_articles, 1):
                logger.info(f"Analyzing article {i}/{len(new_articles)}: {article.title[:50]}...")
                
                try:
                    # Fetch full content if not already available
                    if not article.full_content:
                        article = await self.crawler.fetch_full_article(article)
                    
                    # Analyze with LLM
                    content = article.full_content or article.description or article.title
                    analysis = await self.analyzer.analyze_article(
                        title=article.title,
                        content=content,
                        url=article.url,
                    )
                    
                    # Store analysis results
                    article_id = await self._get_article_id(article.content_hash)
                    if article_id and analysis.stock_mentions:
                        await self._store_stock_mentions(article_id, analysis.stock_mentions)
                        all_mentions.extend([m.to_dict() for m in analysis.stock_mentions])
                    
                    # Mark article as processed
                    await self._mark_article_processed(article_id, analysis.summary)
                    
                    analyzed_articles.append({
                        "title": article.title,
                        "url": article.url,
                        "summary": analysis.summary,
                        "overall_sentiment": analysis.overall_sentiment,
                    })
                    
                    stats["articles_analyzed"] += 1
                    stats["stocks_mentioned"] += len(analysis.stock_mentions)
                    
                    # Rate limiting
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    logger.error(f"Error analyzing article: {e}")
                    stats["errors"].append(f"Article analysis error: {str(e)}")
            
            logger.info(f"Analyzed {stats['articles_analyzed']} articles, found {stats['stocks_mentioned']} stock mentions")
            
            # Step 4: Generate daily summary
            logger.info("=" * 60)
            logger.info("STEP 4: Generating daily summary")
            logger.info("=" * 60)
            
            if analyzed_articles:
                try:
                    summary = await self.analyzer.generate_daily_summary(
                        articles=analyzed_articles,
                        stock_mentions=all_mentions,
                    )
                    
                    await self._store_daily_summary(summary)
                    stats["summary_generated"] = True
                    
                    logger.info(f"Daily summary generated: {summary.summary_title}")
                    logger.info(f"Market sentiment: {summary.market_sentiment}")
                    logger.info(f"Top bullish picks: {[p['symbol'] for p in summary.top_bullish_picks]}")
                    logger.info(f"Top bearish picks: {[p['symbol'] for p in summary.top_bearish_picks]}")
                    
                except Exception as e:
                    logger.error(f"Error generating daily summary: {e}")
                    stats["errors"].append(f"Summary generation error: {str(e)}")
            
            # Step 5: Log crawl results
            await self._log_crawl(stats)
            
        except Exception as e:
            logger.error(f"Service error: {e}")
            stats["errors"].append(str(e))
        
        # Calculate duration
        end_time = datetime.now(timezone.utc)
        stats["completed_at"] = end_time.isoformat()
        stats["duration_seconds"] = (end_time - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("CRAWL COMPLETE")
        logger.info(f"Duration: {stats['duration_seconds']:.1f}s")
        logger.info(f"Articles: {stats['articles_crawled']} crawled, {stats['articles_new']} new, {stats['articles_analyzed']} analyzed")
        logger.info(f"Stocks mentioned: {stats['stocks_mentioned']}")
        logger.info(f"Summary generated: {stats['summary_generated']}")
        if stats["errors"]:
            logger.warning(f"Errors: {len(stats['errors'])}")
        logger.info("=" * 60)
        
        return stats
    
    async def _store_article(self, article: CramerArticle) -> bool:
        """
        Store article in PostgreSQL.
        
        Returns:
            True if article is new, False if duplicate
        """
        if not self.pg_pool:
            return True
        
        try:
            async with self.pg_pool.acquire() as conn:
                # Check if exists
                exists = await conn.fetchval(
                    "SELECT 1 FROM jim_cramer_articles WHERE article_hash = $1",
                    article.content_hash
                )
                
                if exists:
                    return False
                
                # Convert to naive UTC datetime for PostgreSQL TIMESTAMP without timezone
                published_at = article.published_at
                if published_at.tzinfo is not None:
                    published_at = published_at.astimezone(timezone.utc).replace(tzinfo=None)
                # If already naive, assume it's UTC
                
                # Insert new article
                await conn.execute("""
                    INSERT INTO jim_cramer_articles (
                        article_url, article_hash, source_name, source_type,
                        title, description, full_content, author,
                        thumbnail_url, video_url, published_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                    article.url,
                    article.content_hash,
                    article.source_name,
                    article.source_type,
                    article.title,
                    article.description,
                    article.full_content,
                    article.author,
                    article.thumbnail_url,
                    article.video_url,
                    published_at,
                    json.dumps(article.metadata),
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error storing article: {e}")
            return True  # Assume new on error
    
    async def _get_article_id(self, content_hash: str) -> Optional[int]:
        """Get article ID by hash."""
        if not self.pg_pool:
            return None
        
        try:
            async with self.pg_pool.acquire() as conn:
                return await conn.fetchval(
                    "SELECT id FROM jim_cramer_articles WHERE article_hash = $1",
                    content_hash
                )
        except Exception as e:
            logger.error(f"Error getting article ID: {e}")
            return None
    
    async def _store_stock_mentions(self, article_id: int, mentions: list):
        """Store stock mentions for an article."""
        if not self.pg_pool or not mentions:
            return
        
        try:
            async with self.pg_pool.acquire() as conn:
                for mention in mentions:
                    await conn.execute("""
                        INSERT INTO jim_cramer_stock_mentions (
                            article_id, symbol, company_name, sentiment,
                            sentiment_score, confidence, recommendation,
                            reasoning, quote, price_target
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                        article_id,
                        mention.symbol,
                        mention.company_name,
                        mention.sentiment,
                        mention.sentiment_score,
                        mention.confidence,
                        mention.recommendation,
                        mention.reasoning,
                        mention.quote,
                        mention.price_target,
                    )
        except Exception as e:
            logger.error(f"Error storing stock mentions: {e}")
    
    async def _mark_article_processed(self, article_id: Optional[int], summary: str):
        """Mark article as processed."""
        if not self.pg_pool or not article_id:
            return
        
        try:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE jim_cramer_articles 
                    SET is_processed = TRUE, processed_at = NOW()
                    WHERE id = $1
                """, article_id)
        except Exception as e:
            logger.error(f"Error marking article processed: {e}")
    
    async def _store_daily_summary(self, summary: DailySummary):
        """Store or update daily summary."""
        if not self.pg_pool:
            return
        
        try:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO jim_cramer_daily_summaries (
                        summary_date, market_sentiment, market_sentiment_score,
                        summary_title, summary_text, key_points,
                        top_bullish_picks, top_bearish_picks, stocks_to_watch,
                        sectors_bullish, sectors_bearish,
                        total_articles_analyzed, total_stocks_mentioned,
                        llm_provider, llm_model
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (summary_date) DO UPDATE SET
                        market_sentiment = EXCLUDED.market_sentiment,
                        market_sentiment_score = EXCLUDED.market_sentiment_score,
                        summary_title = EXCLUDED.summary_title,
                        summary_text = EXCLUDED.summary_text,
                        key_points = EXCLUDED.key_points,
                        top_bullish_picks = EXCLUDED.top_bullish_picks,
                        top_bearish_picks = EXCLUDED.top_bearish_picks,
                        stocks_to_watch = EXCLUDED.stocks_to_watch,
                        sectors_bullish = EXCLUDED.sectors_bullish,
                        sectors_bearish = EXCLUDED.sectors_bearish,
                        total_articles_analyzed = EXCLUDED.total_articles_analyzed,
                        total_stocks_mentioned = EXCLUDED.total_stocks_mentioned,
                        llm_provider = EXCLUDED.llm_provider,
                        llm_model = EXCLUDED.llm_model,
                        generated_at = NOW()
                """,
                    summary.summary_date.date(),
                    summary.market_sentiment,
                    summary.market_sentiment_score,
                    summary.summary_title,
                    summary.summary_text,
                    json.dumps(summary.key_points),
                    json.dumps(summary.top_bullish_picks),
                    json.dumps(summary.top_bearish_picks),
                    json.dumps(summary.stocks_to_watch),
                    json.dumps(summary.sectors_bullish),
                    json.dumps(summary.sectors_bearish),
                    summary.total_articles,
                    summary.total_stocks,
                    summary.llm_provider,
                    summary.llm_model,
                )
        except Exception as e:
            logger.error(f"Error storing daily summary: {e}")
    
    async def _log_crawl(self, stats: dict):
        """Log crawl statistics."""
        if not self.pg_pool:
            return
        
        try:
            async with self.pg_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO jim_cramer_crawl_logs (
                        crawl_date, source_name, articles_found, articles_new,
                        status, started_at, completed_at, duration_seconds, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                    datetime.utcnow().date(),
                    "all_sources",
                    stats.get("articles_crawled", 0),
                    stats.get("articles_new", 0),
                    "failed" if stats.get("errors") else "success",
                    datetime.fromisoformat(stats["started_at"]).replace(tzinfo=None),
                    datetime.fromisoformat(stats.get("completed_at", stats["started_at"])).replace(tzinfo=None),
                    int(stats.get("duration_seconds", 0)),
                    json.dumps(stats),
                )
        except Exception as e:
            logger.error(f"Error logging crawl: {e}")


async def run_scheduled():
    """Run the service on a daily schedule (9 AM PST / 17:00 UTC)."""
    service = JimCramerService()
    await service.initialize()
    
    # Target time: 9 AM PST = 17:00 UTC
    TARGET_HOUR_UTC = 17
    TARGET_MINUTE_UTC = 0
    
    logger.info("=" * 60)
    logger.info("JIM CRAMER SERVICE - SCHEDULED MODE")
    logger.info("=" * 60)
    logger.info(f"Scheduled to run daily at 9:00 AM PST (17:00 UTC)")
    logger.info("Running initial crawl...")
    
    # Run once at startup
    await service.run()
    
    while True:
        now = datetime.utcnow()
        
        # Calculate next run time (17:00 UTC = 9 AM PST)
        next_run = now.replace(hour=TARGET_HOUR_UTC, minute=TARGET_MINUTE_UTC, second=0, microsecond=0)
        
        # If we've passed today's run time, schedule for tomorrow
        # Use > instead of >= to ensure we run if we're exactly at the scheduled time
        if now > next_run:
            next_run = next_run + timedelta(days=1)
        
        # Calculate seconds until next run
        seconds_until_run = (next_run - now).total_seconds()
        
        # If seconds_until_run is 0 or negative (edge case), run immediately
        if seconds_until_run <= 0:
            seconds_until_run = 0
        
        logger.info(f"Next scheduled run: {next_run.strftime('%Y-%m-%d %H:%M:%S')} UTC ({seconds_until_run/3600:.1f} hours)")
        
        # Sleep until next run time
        if seconds_until_run > 0:
            await asyncio.sleep(seconds_until_run)
        
        # Run the service
        logger.info("Starting scheduled Jim Cramer crawl...")
        try:
            await service.run()
        except Exception as e:
            logger.error(f"Error during scheduled run: {e}")
        
        # Sleep for 61 seconds to ensure we move past the scheduled minute
        # This prevents running twice at the same minute
        await asyncio.sleep(61)


async def run_once():
    """Run the service once and exit."""
    service = JimCramerService()
    await service.initialize()
    
    try:
        stats = await service.run()
        return stats
    finally:
        await service.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Jim Cramer Advice Service")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run with scheduler (9 AM PST daily)",
    )
    args = parser.parse_args()
    
    if args.schedule:
        asyncio.run(run_scheduled())
    else:
        asyncio.run(run_once())


if __name__ == "__main__":
    main()

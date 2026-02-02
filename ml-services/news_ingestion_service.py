#!/usr/bin/env python3
"""
News Ingestion Service
======================

A scheduled service that continuously fetches news from multiple data sources,
analyzes sentiment using LLM, and stores results in ClickHouse.

Features:
- Fetches news from Polygon, Finnhub, NewsAPI, Benzinga, FMP
- Analyzes sentiment using LLM (Anthropic/Groq with fallback)
- Stores articles in ClickHouse for time-series analysis
- Runs on configurable schedule (default: every 30 minutes)
- Tracks processed articles to avoid duplicates

Usage:
    # Run once
    python news_ingestion_service.py --once
    
    # Run continuously (default: every 30 minutes)
    python news_ingestion_service.py
    
    # Custom interval
    python news_ingestion_service.py --interval 15

Environment Variables:
    CLICKHOUSE_HOST: ClickHouse server host (default: localhost)
    CLICKHOUSE_PORT: ClickHouse HTTP port (default: 8123)
    CLICKHOUSE_USER: ClickHouse username (default: default)
    CLICKHOUSE_PASSWORD: ClickHouse password
    VAULT_ADDR: Vault server address (default: http://localhost:8200)
    VAULT_TOKEN: Vault authentication token
"""

import asyncio
import logging
import os
import sys
import uuid
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Iterable
from dataclasses import dataclass

import re

# Add paths for imports
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streaming'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")


def normalize_symbols(raw: Iterable[str]) -> List[str]:
    """Normalize and validate ticker symbols.

    - Splits on whitespace/newlines/commas
    - Uppercases and trims
    - Keeps only [A-Z0-9.-] tickers (length 1-10)

    This prevents garbage like "BE\nTRW" or "\nNTLA" from propagating.
    """
    out: List[str] = []
    seen: Set[str] = set()

    for item in raw or []:
        if item is None:
            continue
        # Split any embedded whitespace/newlines/commas
        parts = re.split(r"[\s,]+", str(item))
        for p in parts:
            sym = p.strip().upper()
            if not sym:
                continue
            if not _TICKER_RE.match(sym):
                continue
            if sym in seen:
                continue
            seen.add(sym)
            out.append(sym)

    return out


@dataclass
class ProcessedArticle:
    """Article with sentiment analysis results."""
    article_id: str
    title: str
    source: str
    url: str
    published_at: datetime
    fetched_at: datetime
    content: str
    summary: str
    symbols: List[str]
    categories: List[str]
    sentiment_score: float
    sentiment_label: str
    confidence: float
    relevance_score: float
    language: str
    author: str
    image_url: str


async def load_symbols_from_postgres(max_symbols: int = 200) -> List[str]:
    """Load symbols from Postgres user watchlists.

    Uses DATABASE_URL (expected to be provided in docker-compose).
    Returns a normalized, de-duped list.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL not set; cannot load watchlist symbols")
        return []

    try:
        import asyncpg
    except Exception as e:
        logger.warning(f"asyncpg not available; cannot load watchlist symbols: {e}")
        return []

    conn = None
    try:
        conn = await asyncpg.connect(dsn=db_url)
        # Pull from both watchlists; UNION de-dupes at SQL-level.
        rows = await conn.fetch(
            """
            SELECT symbol FROM user_watchlist
            UNION
            SELECT symbol FROM options_watchlist
            """
        )
        symbols = normalize_symbols([r["symbol"] for r in rows])
        if max_symbols and len(symbols) > max_symbols:
            symbols = symbols[:max_symbols]
        return symbols
    except Exception as e:
        logger.warning(f"Failed to load symbols from Postgres: {e}")
        return []
    finally:
        try:
            if conn is not None:
                await conn.close()
        except Exception:
            pass


class NewsIngestionService:
    """Service that fetches news, analyzes sentiment, and stores in ClickHouse."""

    def __init__(
        self,
        symbols: List[str] = None,
        clickhouse_host: str = "localhost",
        clickhouse_port: int = 8123,
        clickhouse_user: str = "default",
        clickhouse_password: str = "",
        enable_sentiment: bool = True,
        symbols_source: Optional[str] = None,
        max_symbols: Optional[int] = None,
    ):
        """
        Initialize the news ingestion service.
        
        Args:
            symbols: List of stock symbols to track
            clickhouse_host: ClickHouse server host
            clickhouse_port: ClickHouse HTTP port
            clickhouse_user: ClickHouse username
            clickhouse_password: ClickHouse password
            enable_sentiment: Whether to run sentiment analysis
        """
        self.symbols = normalize_symbols(symbols) if symbols else None
        self.symbols_source = (symbols_source or os.getenv("NEWS_SYMBOLS_SOURCE", "default")).strip().lower()
        self.max_symbols = max_symbols or int(os.getenv("NEWS_MAX_SYMBOLS", "200"))
        self.clickhouse_host = clickhouse_host
        self.clickhouse_port = clickhouse_port
        self.clickhouse_user = clickhouse_user
        self.clickhouse_password = clickhouse_password
        self.enable_sentiment = enable_sentiment
        
        self.connectors = []
        self.sentiment_analyzer = None
        self.ch_client = None
        self._processed_urls: Set[str] = set()
        
        # Metrics
        self.metrics = {
            "total_runs": 0,
            "total_articles_fetched": 0,
            "total_articles_stored": 0,
            "last_run_time": None,
        }
    
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing News Ingestion Service...")
        
        # Initialize connectors
        await self._init_connectors()
        
        # Initialize sentiment analyzer
        if self.enable_sentiment:
            await self._init_sentiment_analyzer()
        
        # Initialize ClickHouse
        await self._init_clickhouse()
        
        logger.info(f"Service initialized with {len(self.connectors)} connectors")
    
    async def _init_connectors(self):
        """Initialize news source connectors."""
        from connectors import (
            PolygonConnector,
            FinnhubConnector,
            NewsAPIConnector,
            BenzingaConnector,
            FinancialModelingPrepConnector,
        )
        
        connector_classes = [
            ('Polygon', PolygonConnector),
            ('Finnhub', FinnhubConnector),
            ('NewsAPI', NewsAPIConnector),
            ('Benzinga', BenzingaConnector),
            ('FMP', FinancialModelingPrepConnector),
        ]
        
        for name, ConnectorClass in connector_classes:
            try:
                connector = ConnectorClass()
                await connector._ensure_api_key()
                if connector.api_key:
                    self.connectors.append((name, connector))
                    logger.info(f"✓ {name} connector initialized")
                else:
                    logger.info(f"✗ {name} connector skipped - no API key")
            except Exception as e:
                logger.warning(f"✗ {name} connector failed: {e}")
    
    async def _init_sentiment_analyzer(self):
        """Initialize LLM sentiment analyzer."""
        try:
            # Try multiple import paths
            try:
                from sentiment_analysis.src.analyzer import LLMAnalyzerWithFallback
            except ImportError:
                # Add the ml-services path and try again
                sentiment_path = os.path.join(os.path.dirname(__file__), 'sentiment-analysis', 'src')
                sys.path.insert(0, sentiment_path)
                from analyzer import LLMAnalyzerWithFallback
            
            self.sentiment_analyzer = LLMAnalyzerWithFallback()
            await self.sentiment_analyzer._load_keys_from_vault()
            
            if self.sentiment_analyzer.is_available:
                providers = self.sentiment_analyzer.available_providers
                logger.info(f"✓ Sentiment analyzer initialized with providers: {providers}")
            else:
                logger.warning("✗ No LLM providers available for sentiment analysis")
                self.sentiment_analyzer = None
                
        except Exception as e:
            logger.warning(f"✗ Sentiment analyzer failed to initialize: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            self.sentiment_analyzer = None
    
    async def _init_clickhouse(self):
        """Initialize ClickHouse connection."""
        try:
            import clickhouse_connect
            
            self.ch_client = clickhouse_connect.get_client(
                host=self.clickhouse_host,
                port=self.clickhouse_port,
                username=self.clickhouse_user,
                password=self.clickhouse_password,
            )
            
            # Verify connection
            result = self.ch_client.query("SELECT 1")
            logger.info("✓ ClickHouse connection established")
            
        except Exception as e:
            logger.error(f"✗ ClickHouse connection failed: {e}")
            raise
    
    async def run_once(self) -> Dict[str, Any]:
        """
        Run one ingestion cycle.
        
        Returns:
            Dict with metrics from this run
        """
        start_time = datetime.utcnow()
        self.metrics["total_runs"] += 1
        run_num = self.metrics["total_runs"]
        
        logger.info(f"{'='*60}")
        logger.info(f"Starting ingestion run #{run_num}")
        logger.info(f"{'='*60}")
        
        # Fetch news from all connectors
        all_articles = []
        for name, connector in self.connectors:
            try:
                logger.info(f"Fetching from {name}...")
                articles = await connector.fetch_news(
                    symbols=self.symbols,
                    limit=20
                )
                if articles:
                    for article in articles:
                        all_articles.append({
                            'source': name,
                            'article': article
                        })
                    logger.info(f"  ✓ {name}: {len(articles)} articles")
                else:
                    logger.info(f"  - {name}: No articles")
            except Exception as e:
                logger.warning(f"  ✗ {name}: Error - {str(e)[:50]}")
        
        self.metrics["total_articles_fetched"] += len(all_articles)
        logger.info(f"Total fetched: {len(all_articles)} articles")
        
        # Filter duplicates
        new_articles = []
        for item in all_articles:
            url = item['article'].url
            if url and url not in self._processed_urls:
                new_articles.append(item)
                self._processed_urls.add(url)
        
        duplicates = len(all_articles) - len(new_articles)
        logger.info(f"New articles: {len(new_articles)} ({duplicates} duplicates skipped)")
        
        if not new_articles:
            logger.info("No new articles to process")
            self.metrics["last_run_time"] = datetime.utcnow()
            return {"articles_processed": 0}
        
        # Analyze sentiment
        processed_articles = []
        for item in new_articles:
            article = item['article']
            source = item['source']
            
            # Default sentiment values
            sentiment_score = 0.0
            sentiment_label = "neutral"
            confidence = 0.5
            
            # Run sentiment analysis if available
            if self.sentiment_analyzer:
                try:
                    text = f"{article.title}. {article.summary if hasattr(article, 'summary') and article.summary else ''}"
                    result = await self.sentiment_analyzer.analyze(text[:1000])
                    sentiment_score = result.score
                    sentiment_label = result.label.value if hasattr(result.label, 'value') else str(result.label)
                    confidence = result.confidence
                except Exception as e:
                    logger.debug(f"Sentiment analysis failed for article: {e}")
            
            # Extract symbols
            symbols = article.symbols if article.symbols else []
            
            # Extract categories
            categories = []
            if hasattr(article, 'categories') and article.categories:
                categories = [c.value if hasattr(c, 'value') else str(c) for c in article.categories]
            
            processed = ProcessedArticle(
                article_id=str(uuid.uuid4()),
                title=article.title[:500] if article.title else 'Unknown',
                source=source,
                url=article.url[:1000] if article.url else '',
                published_at=article.published_at or datetime.utcnow(),
                fetched_at=datetime.utcnow(),
                content=article.content[:5000] if article.content else '',
                summary=article.summary[:1000] if hasattr(article, 'summary') and article.summary else '',
                symbols=symbols,
                categories=categories,
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                confidence=confidence,
                relevance_score=1.0,
                language='en',
                author=article.author if hasattr(article, 'author') and article.author else '',
                image_url=article.image_url if hasattr(article, 'image_url') and article.image_url else '',
            )
            processed_articles.append(processed)
        
        # Store in ClickHouse
        await self._store_to_clickhouse(processed_articles)
        
        self.metrics["total_articles_stored"] += len(processed_articles)
        self.metrics["last_run_time"] = datetime.utcnow()
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"{'='*60}")
        logger.info(f"Run #{run_num} completed in {duration:.1f}s")
        logger.info(f"  Articles processed: {len(processed_articles)}")
        logger.info(f"  Total stored (all time): {self.metrics['total_articles_stored']}")
        logger.info(f"{'='*60}")
        
        return {
            "articles_processed": len(processed_articles),
            "duration_seconds": duration,
        }
    
    async def _store_to_clickhouse(self, articles: List[ProcessedArticle]):
        """Store processed articles in ClickHouse."""
        if not articles:
            return
        
        rows = []
        for a in articles:
            rows.append([
                a.article_id,
                a.title,
                a.source,
                a.url,
                a.published_at,
                a.fetched_at,
                a.content,
                a.summary,
                a.symbols,
                a.categories,
                a.sentiment_score,
                a.sentiment_label,
                a.confidence,
                a.relevance_score,
                a.language,
                a.author,
                a.image_url,
            ])
        
        # IMPORTANT: ClickHouse schema is the contract.
        # We store metadata + summary + derived sentiment features (no full article body).
        column_names = [
            'article_id',
            'title',
            'summary',
            'url',
            'source',
            'source_name',
            'published_at',
            'fetched_at',
            'symbols',
            'categories',
            'sentiment_score',
            'sentiment_label',
            'sentiment_confidence',
            'sentiment_analyzer',
            'sentiment_reasoning',
            'author',
            'image_url',
        ]

        # Remap rows to match the column_names above
        remapped_rows = []
        for a in articles:
            remapped_rows.append([
                a.article_id,
                a.title,
                a.summary,
                a.url,
                a.source,
                a.source,  # source_name (best-effort)
                a.published_at,
                a.fetched_at,
                a.symbols,
                a.categories,
                a.sentiment_score,
                a.sentiment_label,
                a.confidence,
                'unknown',  # sentiment_analyzer (best-effort)
                None,       # sentiment_reasoning
                a.author if a.author else None,
                a.image_url if a.image_url else None,
            ])

        try:
            self.ch_client.insert('news_articles', remapped_rows, column_names=column_names)
            logger.info(f"✓ Stored {len(articles)} articles in ClickHouse")
        except Exception as e:
            logger.error(f"✗ Failed to store in ClickHouse: {e}")
    
    async def run_forever(self, interval_minutes: int = 30):
        """
        Run the service continuously.
        
        Args:
            interval_minutes: Minutes between runs
        """
        logger.info(f"Starting continuous ingestion (interval: {interval_minutes} min)")
        
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Ingestion run failed: {e}")
            
            logger.info(f"Sleeping for {interval_minutes} minutes...")
            await asyncio.sleep(interval_minutes * 60)
    
    async def close(self):
        """Clean up resources."""
        for name, connector in self.connectors:
            try:
                await connector.close()
            except:
                pass
        
        if self.ch_client:
            self.ch_client.close()
        
        logger.info("Service closed")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="News Ingestion Service")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=30, help="Interval in minutes (default: 30)")
    parser.add_argument("--symbols", type=str, help="Comma-separated list of symbols")
    parser.add_argument("--no-sentiment", action="store_true", help="Disable sentiment analysis")
    args = parser.parse_args()
    
    # Parse symbols
    symbols: Optional[List[str]] = None
    if args.symbols:
        symbols = normalize_symbols(args.symbols.split(","))
    
    # Get ClickHouse config from environment
    ch_host = os.getenv("CLICKHOUSE_HOST", "localhost")
    ch_port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    ch_user = os.getenv("CLICKHOUSE_USER", "default")
    ch_password = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_dev_pass")
    
    # Create service
    service = NewsIngestionService(
        symbols=symbols,
        clickhouse_host=ch_host,
        clickhouse_port=ch_port,
        clickhouse_user=ch_user,
        clickhouse_password=ch_password,
        enable_sentiment=not args.no_sentiment,
        symbols_source=os.getenv("NEWS_SYMBOLS_SOURCE", "default"),
        max_symbols=int(os.getenv("NEWS_MAX_SYMBOLS", "200")),
    )
    
    try:
        # If no explicit --symbols were provided, optionally load from Postgres watchlists.
        if not service.symbols:
            if service.symbols_source in ("watchlist", "postgres", "db"):
                loaded = await load_symbols_from_postgres(max_symbols=service.max_symbols)
                if loaded:
                    service.symbols = loaded
                    logger.info(f"Loaded {len(service.symbols)} symbols from Postgres watchlists")
                else:
                    logger.warning("No symbols loaded from Postgres watchlists; falling back to default mega-cap list")
                    service.symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA"]
            else:
                service.symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA"]

        await service.initialize()

        if args.once:
            await service.run_once()
        else:
            await service.run_forever(interval_minutes=args.interval)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())

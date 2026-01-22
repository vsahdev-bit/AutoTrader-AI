"""
News Processing Pipeline
========================

This module implements the main news processing pipeline for the AutoTrader AI
Continuous Intelligence Plane. It orchestrates:

1. News Fetching: Collect articles from multiple sources
2. Deduplication: Prevent duplicate article processing
3. Sentiment Analysis: Hybrid FinBERT + LLM analysis
4. Storage: Persist to ClickHouse for time-series analysis
5. Caching: Store recent articles in Redis for fast access

Pipeline Architecture:
```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   News      │──►│   Dedup     │──►│  Sentiment  │──►│  Storage    │
│  Connectors │   │   Filter    │   │  Analysis   │   │ (ClickHouse)│
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
                                                              │
                                                              ▼
                                                       ┌─────────────┐
                                                       │   Redis     │
                                                       │   Cache     │
                                                       └─────────────┘
```

Batch Processing Model:
- Pipeline runs every 5 minutes (configurable)
- Each run fetches new articles since last run
- Articles are processed in batches for efficiency
- Results are immediately available for recommendations
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set
import json
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class NewsProcessorConfig:
    """
    Configuration for the news processing pipeline.
    
    Supports 12+ data sources across news APIs, social media,
    regulatory filings, and research analytics.
    """
    # Symbols to track
    symbols: List[str] = field(default_factory=lambda: [
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA"
    ])
    
    # Pipeline settings
    fetch_interval_minutes: int = 5
    lookback_hours: int = 24
    max_articles_per_source: int = 50
    
    # Sentiment analysis
    enable_sentiment: bool = True
    enable_llm: bool = False
    llm_api_key: Optional[str] = None
    llm_provider: str = "openai"
    
    # Storage
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    redis_url: str = "redis://localhost:6379"
    
    # ==========================================================================
    # News API Keys
    # ==========================================================================
    alpha_vantage_key: Optional[str] = None
    finnhub_key: Optional[str] = None
    newsapi_key: Optional[str] = None
    benzinga_key: Optional[str] = None
    fmp_key: Optional[str] = None  # Financial Modeling Prep
    
    # ==========================================================================
    # Social Media API Keys
    # ==========================================================================
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    twitter_bearer_token: Optional[str] = None
    stocktwits_token: Optional[str] = None  # Optional, works without
    
    # ==========================================================================
    # Feature Toggles
    # ==========================================================================
    enable_social_media: bool = True
    enable_sec_filings: bool = True
    enable_analyst_data: bool = True  # TipRanks
    
    # ==========================================================================
    # Source-specific Settings
    # ==========================================================================
    rss_feeds: List[str] = field(default_factory=list)
    reddit_subreddits: List[str] = field(default_factory=lambda: [
        "wallstreetbets", "stocks", "investing", "stockmarket", "options"
    ])


@dataclass 
class ProcessedArticle:
    """
    Article with sentiment analysis results.
    
    This represents the final output of the pipeline, ready for storage
    and use by the recommendation engine.
    """
    article_id: str
    title: str
    summary: str
    url: str
    source: str
    source_name: str
    published_at: datetime
    fetched_at: datetime
    symbols: List[str]
    categories: List[str]
    
    # Sentiment results
    sentiment_score: float
    sentiment_label: str
    sentiment_confidence: float
    sentiment_analyzer: str
    sentiment_reasoning: Optional[str] = None
    sentiment_aspects: Optional[Dict[str, float]] = None
    
    # Metadata
    author: Optional[str] = None
    image_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "article_id": self.article_id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "source_name": self.source_name,
            "published_at": self.published_at.isoformat(),
            "fetched_at": self.fetched_at.isoformat(),
            "symbols": self.symbols,
            "categories": self.categories,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "sentiment_confidence": self.sentiment_confidence,
            "sentiment_analyzer": self.sentiment_analyzer,
            "sentiment_reasoning": self.sentiment_reasoning,
            "sentiment_aspects": self.sentiment_aspects,
            "author": self.author,
            "image_url": self.image_url,
        }


class NewsPipeline:
    """
    Main news processing pipeline.
    
    Orchestrates the complete flow from fetching news to storing
    analyzed results. Designed for batch processing with configurable
    intervals.
    
    Example Usage:
        config = NewsProcessorConfig(
            symbols=["AAPL", "GOOGL", "MSFT"],
            alpha_vantage_key="your_key",
            finnhub_key="your_key",
            enable_sentiment=True,
        )
        
        pipeline = NewsPipeline(config)
        await pipeline.initialize()
        
        # Run once
        results = await pipeline.run()
        
        # Or run continuously
        await pipeline.run_forever()
    """
    
    def __init__(self, config: NewsProcessorConfig):
        """
        Initialize the news pipeline.
        
        Args:
            config: Pipeline configuration
        """
        self.config = config
        self.connectors = []
        self.sentiment_analyzer = None
        self.storage = None
        self.cache = None
        
        # Track processed article IDs for deduplication
        self._processed_ids: Set[str] = set()
        self._last_run: Optional[datetime] = None
        
        # Metrics
        self.metrics = {
            "total_runs": 0,
            "total_articles_fetched": 0,
            "total_articles_processed": 0,
            "total_duplicates_skipped": 0,
            "last_run_duration_seconds": 0,
        }
    
    async def initialize(self):
        """
        Initialize all pipeline components.
        
        Sets up news connectors, sentiment analyzer, and storage backends.
        """
        logger.info("Initializing news pipeline...")
        
        # Initialize news connectors
        await self._init_connectors()
        
        # Initialize sentiment analyzer
        if self.config.enable_sentiment:
            await self._init_sentiment_analyzer()
        
        # Initialize storage
        await self._init_storage()
        
        logger.info(f"Pipeline initialized with {len(self.connectors)} connectors")
    
    async def _init_connectors(self):
        """Initialize all news and social media source connectors."""
        # Import all connectors
        from streaming.connectors import (
            # News APIs
            AlphaVantageConnector,
            FinnhubConnector,
            NewsAPIConnector,
            RSSFeedConnector,
            YahooFinanceConnector,
            BenzingaConnector,
            FinancialModelingPrepConnector,
            # Regulatory
            SECEdgarConnector,
            # Social Media
            RedditConnector,
            TwitterConnector,
            StockTwitsConnector,
            # Research
            TipRanksConnector,
        )
        
        self.connectors = []
        
        # =====================================================================
        # News API Connectors
        # =====================================================================
        
        # Alpha Vantage (if API key provided)
        if self.config.alpha_vantage_key:
            self.connectors.append(
                AlphaVantageConnector(api_key=self.config.alpha_vantage_key)
            )
            logger.info("Added Alpha Vantage connector")
        
        # Finnhub (if API key provided)
        if self.config.finnhub_key:
            self.connectors.append(
                FinnhubConnector(api_key=self.config.finnhub_key)
            )
            logger.info("Added Finnhub connector")
        
        # NewsAPI (if API key provided)
        if self.config.newsapi_key:
            self.connectors.append(
                NewsAPIConnector(api_key=self.config.newsapi_key)
            )
            logger.info("Added NewsAPI connector")
        
        # Benzinga (if API key provided)
        if self.config.benzinga_key:
            self.connectors.append(
                BenzingaConnector(api_key=self.config.benzinga_key)
            )
            logger.info("Added Benzinga connector")
        
        # Financial Modeling Prep (if API key provided)
        if self.config.fmp_key:
            self.connectors.append(
                FinancialModelingPrepConnector(api_key=self.config.fmp_key)
            )
            logger.info("Added Financial Modeling Prep connector")
        
        # Yahoo Finance (no API key required)
        self.connectors.append(YahooFinanceConnector())
        logger.info("Added Yahoo Finance connector")
        
        # RSS Feeds (no API key required)
        rss_connector = RSSFeedConnector(
            enabled_feeds=self.config.rss_feeds if self.config.rss_feeds else None
        )
        self.connectors.append(rss_connector)
        logger.info("Added RSS feed connector")
        
        # =====================================================================
        # Regulatory Filings
        # =====================================================================
        
        if self.config.enable_sec_filings:
            self.connectors.append(SECEdgarConnector())
            logger.info("Added SEC EDGAR connector")
        
        # =====================================================================
        # Social Media Connectors
        # =====================================================================
        
        if self.config.enable_social_media:
            # Reddit (if credentials provided)
            if self.config.reddit_client_id and self.config.reddit_client_secret:
                self.connectors.append(
                    RedditConnector(
                        client_id=self.config.reddit_client_id,
                        client_secret=self.config.reddit_client_secret,
                        subreddits=self.config.reddit_subreddits,
                    )
                )
                logger.info("Added Reddit connector")
            
            # X/Twitter (if bearer token provided)
            if self.config.twitter_bearer_token:
                self.connectors.append(
                    TwitterConnector(bearer_token=self.config.twitter_bearer_token)
                )
                logger.info("Added X (Twitter) connector")
            
            # StockTwits (works without auth, better with)
            self.connectors.append(
                StockTwitsConnector(access_token=self.config.stocktwits_token)
            )
            logger.info("Added StockTwits connector")
        
        # =====================================================================
        # Research & Analytics
        # =====================================================================
        
        if self.config.enable_analyst_data:
            self.connectors.append(TipRanksConnector())
            logger.info("Added TipRanks connector")
    
    async def _init_sentiment_analyzer(self):
        """Initialize sentiment analysis components."""
        # Import here to handle optional dependencies
        try:
            from ml_services.sentiment_analysis.src.analyzer import HybridSentimentAnalyzer
            
            self.sentiment_analyzer = HybridSentimentAnalyzer(
                llm_api_key=self.config.llm_api_key if self.config.enable_llm else None,
                llm_provider=self.config.llm_provider,
            )
            await self.sentiment_analyzer.initialize()
            logger.info("Sentiment analyzer initialized")
            
        except ImportError as e:
            logger.warning(f"Sentiment analysis not available: {e}")
            logger.warning("Install transformers and torch for FinBERT support")
            self.sentiment_analyzer = None
    
    async def _init_storage(self):
        """Initialize storage backends (ClickHouse and Redis)."""
        # Initialize ClickHouse storage
        try:
            self.storage = ClickHouseStorage(
                host=self.config.clickhouse_host,
                port=self.config.clickhouse_port,
            )
            await self.storage.initialize()
            logger.info("ClickHouse storage initialized")
        except Exception as e:
            logger.warning(f"ClickHouse not available: {e}")
            self.storage = None
        
        # Initialize Redis cache
        try:
            self.cache = RedisCache(url=self.config.redis_url)
            await self.cache.initialize()
            
            # Load previously processed IDs from cache
            cached_ids = await self.cache.get_processed_ids()
            self._processed_ids.update(cached_ids)
            logger.info(f"Redis cache initialized, loaded {len(cached_ids)} processed IDs")
            
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            self.cache = None
    
    async def run(self) -> List[ProcessedArticle]:
        """
        Execute one pipeline run.
        
        Fetches news from all sources, deduplicates, analyzes sentiment,
        and stores results.
        
        Returns:
            List of processed articles from this run
        """
        start_time = datetime.utcnow()
        self.metrics["total_runs"] += 1
        
        logger.info(f"Starting pipeline run #{self.metrics['total_runs']}")
        
        # Determine time range for fetching
        since = self._last_run or (start_time - timedelta(hours=self.config.lookback_hours))
        
        # Step 1: Fetch news from all sources
        all_articles = await self._fetch_all_news(since)
        self.metrics["total_articles_fetched"] += len(all_articles)
        logger.info(f"Fetched {len(all_articles)} total articles")
        
        # Step 2: Deduplicate
        new_articles = self._deduplicate(all_articles)
        duplicates_skipped = len(all_articles) - len(new_articles)
        self.metrics["total_duplicates_skipped"] += duplicates_skipped
        logger.info(f"After deduplication: {len(new_articles)} new articles ({duplicates_skipped} duplicates)")
        
        if not new_articles:
            logger.info("No new articles to process")
            self._last_run = start_time
            return []
        
        # Step 3: Analyze sentiment
        if self.sentiment_analyzer:
            processed = await self._analyze_sentiment(new_articles)
        else:
            # No sentiment analysis, use neutral scores
            processed = self._create_neutral_results(new_articles)
        
        self.metrics["total_articles_processed"] += len(processed)
        
        # Step 4: Store results
        await self._store_results(processed)
        
        # Update state
        self._last_run = start_time
        
        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds()
        self.metrics["last_run_duration_seconds"] = duration
        
        logger.info(f"Pipeline run completed in {duration:.1f}s, processed {len(processed)} articles")
        
        return processed
    
    async def run_forever(self):
        """
        Run the pipeline continuously at configured intervals.
        
        This method runs indefinitely, executing the pipeline every
        `fetch_interval_minutes` minutes.
        """
        logger.info(f"Starting continuous pipeline (interval: {self.config.fetch_interval_minutes} min)")
        
        while True:
            try:
                await self.run()
            except Exception as e:
                logger.error(f"Pipeline run failed: {e}")
            
            # Wait for next interval
            await asyncio.sleep(self.config.fetch_interval_minutes * 60)
    
    async def _fetch_all_news(self, since: datetime) -> List:
        """Fetch news from all connectors concurrently."""
        from streaming.connectors.base import NewsArticle
        
        tasks = []
        for connector in self.connectors:
            task = connector.fetch_news(
                symbols=self.config.symbols,
                since=since,
                limit=self.config.max_articles_per_source,
            )
            tasks.append(task)
        
        # Fetch from all sources concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        all_articles = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                connector_name = self.connectors[i].__class__.__name__
                logger.error(f"Fetch failed for {connector_name}: {result}")
                continue
            all_articles.extend(result)
        
        return all_articles
    
    def _deduplicate(self, articles: List) -> List:
        """
        Remove duplicate articles.
        
        Uses article_id (hash of URL + published_at) for deduplication.
        Tracks processed IDs to avoid reprocessing across runs.
        """
        new_articles = []
        
        for article in articles:
            if article.article_id not in self._processed_ids:
                new_articles.append(article)
                self._processed_ids.add(article.article_id)
        
        return new_articles
    
    async def _analyze_sentiment(self, articles: List) -> List[ProcessedArticle]:
        """
        Run sentiment analysis on articles.
        
        Uses hybrid analyzer (FinBERT + LLM) for sentiment scoring.
        """
        # Prepare texts for batch analysis
        texts = [f"{a.title}. {a.summary}" for a in articles]
        categories_list = [[c.value for c in a.categories] for a in articles]
        
        # Run sentiment analysis
        results = await self.sentiment_analyzer.analyze_batch(
            texts=texts,
            categories_list=categories_list,
        )
        
        # Combine articles with sentiment results
        processed = []
        for article, sentiment in zip(articles, results):
            processed_article = ProcessedArticle(
                article_id=article.article_id,
                title=article.title,
                summary=article.summary,
                url=article.url,
                source=article.source.value,
                source_name=article.source_name,
                published_at=article.published_at,
                fetched_at=article.fetched_at,
                symbols=article.symbols,
                categories=[c.value for c in article.categories],
                sentiment_score=sentiment.score,
                sentiment_label=sentiment.label.value,
                sentiment_confidence=sentiment.confidence,
                sentiment_analyzer=sentiment.analyzer,
                sentiment_reasoning=sentiment.reasoning,
                sentiment_aspects=sentiment.aspects,
                author=article.author,
                image_url=article.image_url,
            )
            processed.append(processed_article)
        
        return processed
    
    def _create_neutral_results(self, articles: List) -> List[ProcessedArticle]:
        """Create results with neutral sentiment (when analyzer not available)."""
        processed = []
        for article in articles:
            processed_article = ProcessedArticle(
                article_id=article.article_id,
                title=article.title,
                summary=article.summary,
                url=article.url,
                source=article.source.value,
                source_name=article.source_name,
                published_at=article.published_at,
                fetched_at=article.fetched_at,
                symbols=article.symbols,
                categories=[c.value for c in article.categories],
                sentiment_score=0.0,
                sentiment_label="neutral",
                sentiment_confidence=0.0,
                sentiment_analyzer="none",
                author=article.author,
                image_url=article.image_url,
            )
            processed.append(processed_article)
        return processed
    
    async def _store_results(self, articles: List[ProcessedArticle]):
        """Store processed articles to ClickHouse and cache to Redis."""
        # Store in ClickHouse
        if self.storage:
            try:
                await self.storage.insert_articles(articles)
            except Exception as e:
                logger.error(f"Failed to store in ClickHouse: {e}")
        
        # Cache in Redis
        if self.cache:
            try:
                await self.cache.cache_articles(articles)
                await self.cache.save_processed_ids(self._processed_ids)
            except Exception as e:
                logger.error(f"Failed to cache in Redis: {e}")
    
    async def close(self):
        """Clean up resources."""
        # Close connectors
        for connector in self.connectors:
            await connector.close()
        
        # Close storage
        if self.storage:
            await self.storage.close()
        
        if self.cache:
            await self.cache.close()
        
        logger.info("Pipeline closed")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get pipeline metrics for monitoring."""
        return {
            **self.metrics,
            "connectors_active": len(self.connectors),
            "sentiment_enabled": self.sentiment_analyzer is not None,
            "storage_enabled": self.storage is not None,
            "cache_enabled": self.cache is not None,
            "processed_ids_count": len(self._processed_ids),
        }


class ClickHouseStorage:
    """
    ClickHouse storage backend for news articles.
    
    Stores articles in a time-series optimized table for efficient
    querying by symbol, time range, and sentiment.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8123):
        self.host = host
        self.port = port
        self.client = None
    
    async def initialize(self):
        """Initialize ClickHouse connection and create tables."""
        try:
            import clickhouse_connect
            
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
            )
            
            # Create table if not exists
            await self._create_tables()
            
        except ImportError:
            raise ImportError("clickhouse-connect not installed. Run: pip install clickhouse-connect")
    
    async def _create_tables(self):
        """Create ClickHouse tables for news storage."""
        # Main articles table
        create_sql = """
        CREATE TABLE IF NOT EXISTS news_articles (
            article_id String,
            title String,
            summary String,
            url String,
            source String,
            source_name String,
            published_at DateTime,
            fetched_at DateTime,
            symbols Array(String),
            categories Array(String),
            sentiment_score Float32,
            sentiment_label String,
            sentiment_confidence Float32,
            sentiment_analyzer String,
            sentiment_reasoning Nullable(String),
            author Nullable(String),
            image_url Nullable(String)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(published_at)
        ORDER BY (published_at, article_id)
        """
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.client.command, create_sql)
    
    async def insert_articles(self, articles: List[ProcessedArticle]):
        """Insert articles into ClickHouse."""
        if not articles:
            return
        
        # Prepare data for insertion
        data = []
        for a in articles:
            row = [
                a.article_id,
                a.title,
                a.summary,
                a.url,
                a.source,
                a.source_name,
                a.published_at,
                a.fetched_at,
                a.symbols,
                a.categories,
                a.sentiment_score,
                a.sentiment_label,
                a.sentiment_confidence,
                a.sentiment_analyzer,
                a.sentiment_reasoning,
                a.author,
                a.image_url,
            ]
            data.append(row)
        
        columns = [
            "article_id", "title", "summary", "url", "source", "source_name",
            "published_at", "fetched_at", "symbols", "categories",
            "sentiment_score", "sentiment_label", "sentiment_confidence",
            "sentiment_analyzer", "sentiment_reasoning", "author", "image_url"
        ]
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.insert("news_articles", data, column_names=columns)
        )
        
        logger.debug(f"Inserted {len(articles)} articles into ClickHouse")
    
    async def close(self):
        """Close ClickHouse connection."""
        if self.client:
            self.client.close()


class RedisCache:
    """
    Redis cache for recent articles and processed IDs.
    
    Provides fast access to recent articles for the recommendation
    engine and tracks processed article IDs for deduplication.
    """
    
    def __init__(self, url: str = "redis://localhost:6379"):
        self.url = url
        self.client = None
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            import redis.asyncio as redis
            
            self.client = redis.from_url(self.url, decode_responses=True)
            await self.client.ping()
            
        except ImportError:
            raise ImportError("redis not installed. Run: pip install redis")
    
    async def cache_articles(self, articles: List[ProcessedArticle], ttl: int = 86400):
        """
        Cache articles in Redis.
        
        Articles are stored with 24-hour TTL for fast access by
        the recommendation engine.
        """
        if not self.client or not articles:
            return
        
        pipe = self.client.pipeline()
        
        for article in articles:
            key = f"article:{article.article_id}"
            pipe.set(key, json.dumps(article.to_dict()), ex=ttl)
            
            # Also index by symbol
            for symbol in article.symbols:
                pipe.zadd(
                    f"articles_by_symbol:{symbol}",
                    {article.article_id: article.published_at.timestamp()}
                )
                pipe.expire(f"articles_by_symbol:{symbol}", ttl)
        
        await pipe.execute()
    
    async def get_articles_for_symbol(
        self,
        symbol: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent articles for a symbol."""
        if not self.client:
            return []
        
        # Get article IDs sorted by time (newest first)
        article_ids = await self.client.zrevrange(
            f"articles_by_symbol:{symbol}",
            0,
            limit - 1
        )
        
        if not article_ids:
            return []
        
        # Fetch article data
        pipe = self.client.pipeline()
        for article_id in article_ids:
            pipe.get(f"article:{article_id}")
        
        results = await pipe.execute()
        
        articles = []
        for data in results:
            if data:
                articles.append(json.loads(data))
        
        return articles
    
    async def get_processed_ids(self) -> Set[str]:
        """Load processed article IDs from cache."""
        if not self.client:
            return set()
        
        ids = await self.client.smembers("processed_article_ids")
        return set(ids)
    
    async def save_processed_ids(self, ids: Set[str]):
        """Save processed article IDs to cache."""
        if not self.client or not ids:
            return
        
        # Use pipeline for efficiency
        pipe = self.client.pipeline()
        
        # Clear and re-add (simpler than diff)
        pipe.delete("processed_article_ids")
        
        # Add in chunks to avoid huge commands
        id_list = list(ids)
        chunk_size = 1000
        for i in range(0, len(id_list), chunk_size):
            chunk = id_list[i:i + chunk_size]
            pipe.sadd("processed_article_ids", *chunk)
        
        # Set TTL to prevent unbounded growth (7 days)
        pipe.expire("processed_article_ids", 604800)
        
        await pipe.execute()
    
    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()

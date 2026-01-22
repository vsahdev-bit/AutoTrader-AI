"""
News Features Module
====================

This module provides news sentiment features for the recommendation engine.
It fetches pre-computed news features from ClickHouse and transforms them
into input tensors for the ML model.

Features Provided:
- Short-term sentiment (1d, 3d)
- Medium-term sentiment (7d, 14d)
- Sentiment momentum and trends
- News volume indicators
- Category-specific sentiment
- Sentiment confidence/quality metrics

Integration:
The recommendation engine calls get_news_features() to retrieve the latest
news-derived features for symbols being analyzed. These features are combined
with technical indicators and social signals for final predictions.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class NewsFeatures:
    """
    News-derived features for a single symbol.
    
    These features capture the current news sentiment landscape
    and are used as inputs to the recommendation model.
    """
    symbol: str
    feature_date: date
    
    # Short-term sentiment
    sentiment_1d: float
    sentiment_3d: float
    sentiment_momentum: float  # 1d - 3d (positive = improving)
    
    # Medium-term sentiment
    sentiment_7d: float
    sentiment_14d: float
    sentiment_trend: float  # 7d - 14d (positive = improving)
    
    # News volume (attention indicators)
    article_count_1d: int
    article_count_7d: int
    volume_ratio: float  # Recent vs average (>1 = above average attention)
    
    # Quality/confidence metrics
    avg_confidence_1d: float
    high_confidence_ratio: float
    
    # Volatility (uncertainty indicators)
    sentiment_volatility_7d: float
    sentiment_range_7d: float
    
    # Category-specific (optional)
    earnings_sentiment: Optional[float] = None
    analyst_sentiment: Optional[float] = None
    product_sentiment: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "feature_date": self.feature_date.isoformat(),
            "sentiment_1d": self.sentiment_1d,
            "sentiment_3d": self.sentiment_3d,
            "sentiment_momentum": self.sentiment_momentum,
            "sentiment_7d": self.sentiment_7d,
            "sentiment_14d": self.sentiment_14d,
            "sentiment_trend": self.sentiment_trend,
            "article_count_1d": self.article_count_1d,
            "article_count_7d": self.article_count_7d,
            "volume_ratio": self.volume_ratio,
            "avg_confidence_1d": self.avg_confidence_1d,
            "high_confidence_ratio": self.high_confidence_ratio,
            "sentiment_volatility_7d": self.sentiment_volatility_7d,
            "sentiment_range_7d": self.sentiment_range_7d,
            "earnings_sentiment": self.earnings_sentiment,
            "analyst_sentiment": self.analyst_sentiment,
            "product_sentiment": self.product_sentiment,
        }
    
    def to_feature_vector(self) -> List[float]:
        """
        Convert to feature vector for ML model input.
        
        Returns list of floats suitable for model inference.
        Optional features use 0.0 if not available.
        """
        return [
            self.sentiment_1d,
            self.sentiment_3d,
            self.sentiment_momentum,
            self.sentiment_7d,
            self.sentiment_14d,
            self.sentiment_trend,
            float(self.article_count_1d) / 100.0,  # Normalize
            float(self.article_count_7d) / 500.0,  # Normalize
            self.volume_ratio,
            self.avg_confidence_1d,
            self.high_confidence_ratio,
            self.sentiment_volatility_7d,
            self.sentiment_range_7d,
            self.earnings_sentiment or 0.0,
            self.analyst_sentiment or 0.0,
            self.product_sentiment or 0.0,
        ]
    
    @classmethod
    def empty(cls, symbol: str) -> "NewsFeatures":
        """Create empty features (no news data available)."""
        return cls(
            symbol=symbol,
            feature_date=date.today(),
            sentiment_1d=0.0,
            sentiment_3d=0.0,
            sentiment_momentum=0.0,
            sentiment_7d=0.0,
            sentiment_14d=0.0,
            sentiment_trend=0.0,
            article_count_1d=0,
            article_count_7d=0,
            volume_ratio=0.0,
            avg_confidence_1d=0.0,
            high_confidence_ratio=0.0,
            sentiment_volatility_7d=0.0,
            sentiment_range_7d=0.0,
        )


class NewsFeatureProvider:
    """
    Provides news features for the recommendation engine.
    
    Fetches pre-computed features from ClickHouse and caches them
    for efficient access during recommendation generation.
    
    Example Usage:
        provider = NewsFeatureProvider(clickhouse_host="localhost")
        await provider.initialize()
        
        features = await provider.get_features(["AAPL", "GOOGL", "MSFT"])
        for symbol, feat in features.items():
            print(f"{symbol}: sentiment_1d={feat.sentiment_1d}")
    """
    
    def __init__(
        self,
        clickhouse_host: str = "localhost",
        clickhouse_port: int = 8123,
        clickhouse_user: str = "default",
        clickhouse_password: str = "",
        redis_url: Optional[str] = "redis://localhost:6379",
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize the feature provider.
        
        Args:
            clickhouse_host: ClickHouse server host
            clickhouse_port: ClickHouse HTTP port
            clickhouse_user: ClickHouse username
            clickhouse_password: ClickHouse password
            redis_url: Redis URL for caching (optional)
            cache_ttl_seconds: How long to cache features
        """
        self.clickhouse_host = clickhouse_host
        self.clickhouse_port = clickhouse_port
        self.clickhouse_user = clickhouse_user
        self.clickhouse_password = clickhouse_password
        self.redis_url = redis_url
        self.cache_ttl = cache_ttl_seconds
        
        self.ch_client = None
        self.redis_client = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize connections to ClickHouse and Redis."""
        if self._initialized:
            return
        
        # Initialize ClickHouse
        try:
            import clickhouse_connect
            
            self.ch_client = clickhouse_connect.get_client(
                host=self.clickhouse_host,
                port=self.clickhouse_port,
                username=self.clickhouse_user,
                password=self.clickhouse_password,
            )
            logger.info("Connected to ClickHouse")
        except Exception as e:
            logger.warning(f"ClickHouse not available: {e}")
            self.ch_client = None
        
        # Initialize Redis cache
        if self.redis_url:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                await self.redis_client.ping()
                logger.info("Connected to Redis cache")
            except Exception as e:
                logger.warning(f"Redis not available: {e}")
                self.redis_client = None
        
        self._initialized = True
    
    async def get_features(
        self,
        symbols: List[str],
        feature_date: Optional[date] = None,
    ) -> Dict[str, NewsFeatures]:
        """
        Get news features for multiple symbols.
        
        Args:
            symbols: List of stock symbols
            feature_date: Date to get features for (default: today)
            
        Returns:
            Dict mapping symbol to NewsFeatures
        """
        if not self._initialized:
            await self.initialize()
        
        feature_date = feature_date or date.today()
        
        # Try cache first
        cached = await self._get_from_cache(symbols, feature_date)
        
        # Find missing symbols
        missing = [s for s in symbols if s not in cached]
        
        # Fetch missing from ClickHouse
        if missing and self.ch_client:
            fetched = await self._fetch_from_clickhouse(missing, feature_date)
            cached.update(fetched)
            
            # Cache the fetched features
            if fetched and self.redis_client:
                await self._save_to_cache(fetched, feature_date)
        
        # Fill in empty features for any still missing
        for symbol in symbols:
            if symbol not in cached:
                cached[symbol] = NewsFeatures.empty(symbol)
        
        return cached
    
    async def get_features_single(
        self,
        symbol: str,
        feature_date: Optional[date] = None,
    ) -> NewsFeatures:
        """Get news features for a single symbol."""
        features = await self.get_features([symbol], feature_date)
        return features.get(symbol, NewsFeatures.empty(symbol))
    
    async def _get_from_cache(
        self,
        symbols: List[str],
        feature_date: date,
    ) -> Dict[str, NewsFeatures]:
        """Get cached features from Redis."""
        if not self.redis_client:
            return {}
        
        try:
            import json
            
            result = {}
            pipe = self.redis_client.pipeline()
            
            for symbol in symbols:
                key = f"news_features:{symbol}:{feature_date.isoformat()}"
                pipe.get(key)
            
            values = await pipe.execute()
            
            for symbol, value in zip(symbols, values):
                if value:
                    data = json.loads(value)
                    result[symbol] = self._dict_to_features(data)
            
            return result
            
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return {}
    
    async def _save_to_cache(
        self,
        features: Dict[str, NewsFeatures],
        feature_date: date,
    ):
        """Save features to Redis cache."""
        if not self.redis_client:
            return
        
        try:
            import json
            
            pipe = self.redis_client.pipeline()
            
            for symbol, feat in features.items():
                key = f"news_features:{symbol}:{feature_date.isoformat()}"
                pipe.set(key, json.dumps(feat.to_dict()), ex=self.cache_ttl)
            
            await pipe.execute()
            
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")
    
    async def _fetch_from_clickhouse(
        self,
        symbols: List[str],
        feature_date: date,
    ) -> Dict[str, NewsFeatures]:
        """Fetch features from ClickHouse."""
        if not self.ch_client:
            return {}
        
        try:
            # First try pre-computed features table
            result = await self._fetch_precomputed(symbols, feature_date)
            
            # For missing symbols, compute on-the-fly
            missing = [s for s in symbols if s not in result]
            if missing:
                computed = await self._compute_features(missing, feature_date)
                result.update(computed)
            
            return result
            
        except Exception as e:
            logger.error(f"ClickHouse fetch failed: {e}")
            return {}
    
    async def _fetch_precomputed(
        self,
        symbols: List[str],
        feature_date: date,
    ) -> Dict[str, NewsFeatures]:
        """Fetch from pre-computed features table."""
        symbols_str = ", ".join(f"'{s}'" for s in symbols)
        
        query = f"""
        SELECT
            symbol,
            feature_date,
            sentiment_1d,
            sentiment_3d,
            sentiment_momentum,
            sentiment_7d,
            sentiment_14d,
            sentiment_trend,
            article_count_1d,
            article_count_7d,
            volume_ratio,
            avg_confidence_1d,
            high_confidence_ratio,
            sentiment_volatility_7d,
            sentiment_range_7d,
            earnings_sentiment,
            analyst_sentiment,
            product_sentiment
        FROM symbol_news_features
        WHERE symbol IN ({symbols_str})
          AND feature_date = '{feature_date.isoformat()}'
        """
        
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None,
            lambda: self.ch_client.query(query).result_rows
        )
        
        result = {}
        for row in rows:
            features = NewsFeatures(
                symbol=row[0],
                feature_date=row[1],
                sentiment_1d=row[2] or 0.0,
                sentiment_3d=row[3] or 0.0,
                sentiment_momentum=row[4] or 0.0,
                sentiment_7d=row[5] or 0.0,
                sentiment_14d=row[6] or 0.0,
                sentiment_trend=row[7] or 0.0,
                article_count_1d=row[8] or 0,
                article_count_7d=row[9] or 0,
                volume_ratio=row[10] or 0.0,
                avg_confidence_1d=row[11] or 0.0,
                high_confidence_ratio=row[12] or 0.0,
                sentiment_volatility_7d=row[13] or 0.0,
                sentiment_range_7d=row[14] or 0.0,
                earnings_sentiment=row[15],
                analyst_sentiment=row[16],
                product_sentiment=row[17],
            )
            result[features.symbol] = features
        
        return result
    
    async def _compute_features(
        self,
        symbols: List[str],
        feature_date: date,
    ) -> Dict[str, NewsFeatures]:
        """
        Compute features on-the-fly from raw articles.
        
        Used when pre-computed features are not available.
        """
        symbols_str = ", ".join(f"'{s}'" for s in symbols)
        
        query = f"""
        WITH 
            '{feature_date.isoformat()}' as target_date,
            symbol_articles AS (
                SELECT
                    arrayJoin(symbols) as symbol,
                    sentiment_score,
                    sentiment_confidence,
                    published_at,
                    categories
                FROM news_articles
                WHERE has(symbols, symbol)
                  AND published_at >= toDate(target_date) - 14
                  AND published_at < toDate(target_date) + 1
            )
        SELECT
            symbol,
            
            -- 1-day sentiment
            avgIf(sentiment_score, published_at >= toDate(target_date) - 1) as sentiment_1d,
            
            -- 3-day sentiment  
            avgIf(sentiment_score, published_at >= toDate(target_date) - 3) as sentiment_3d,
            
            -- 7-day sentiment
            avgIf(sentiment_score, published_at >= toDate(target_date) - 7) as sentiment_7d,
            
            -- 14-day sentiment
            avg(sentiment_score) as sentiment_14d,
            
            -- Article counts
            countIf(published_at >= toDate(target_date) - 1) as article_count_1d,
            countIf(published_at >= toDate(target_date) - 7) as article_count_7d,
            
            -- Confidence
            avgIf(sentiment_confidence, published_at >= toDate(target_date) - 1) as avg_confidence_1d,
            
            -- Volatility
            stddevPopIf(sentiment_score, published_at >= toDate(target_date) - 7) as sentiment_volatility_7d,
            maxIf(sentiment_score, published_at >= toDate(target_date) - 7) - 
                minIf(sentiment_score, published_at >= toDate(target_date) - 7) as sentiment_range_7d
            
        FROM symbol_articles
        WHERE symbol IN ({symbols_str})
        GROUP BY symbol
        """
        
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            None,
            lambda: self.ch_client.query(query).result_rows
        )
        
        result = {}
        for row in rows:
            symbol = row[0]
            sentiment_1d = row[1] or 0.0
            sentiment_3d = row[2] or 0.0
            sentiment_7d = row[3] or 0.0
            sentiment_14d = row[4] or 0.0
            article_count_1d = row[5] or 0
            article_count_7d = row[6] or 0
            avg_confidence_1d = row[7] or 0.0
            sentiment_volatility_7d = row[8] or 0.0
            sentiment_range_7d = row[9] or 0.0
            
            # Calculate derived features
            sentiment_momentum = sentiment_1d - sentiment_3d
            sentiment_trend = sentiment_7d - sentiment_14d
            
            # Volume ratio (vs 14-day average)
            avg_daily = article_count_7d / 7.0 if article_count_7d > 0 else 1.0
            volume_ratio = article_count_1d / avg_daily if avg_daily > 0 else 0.0
            
            # High confidence ratio
            high_conf_ratio = 0.5  # Default, would need separate query
            
            features = NewsFeatures(
                symbol=symbol,
                feature_date=feature_date,
                sentiment_1d=sentiment_1d,
                sentiment_3d=sentiment_3d,
                sentiment_momentum=sentiment_momentum,
                sentiment_7d=sentiment_7d,
                sentiment_14d=sentiment_14d,
                sentiment_trend=sentiment_trend,
                article_count_1d=article_count_1d,
                article_count_7d=article_count_7d,
                volume_ratio=volume_ratio,
                avg_confidence_1d=avg_confidence_1d,
                high_confidence_ratio=high_conf_ratio,
                sentiment_volatility_7d=sentiment_volatility_7d,
                sentiment_range_7d=sentiment_range_7d,
            )
            result[symbol] = features
        
        return result
    
    def _dict_to_features(self, data: Dict[str, Any]) -> NewsFeatures:
        """Convert dictionary to NewsFeatures object."""
        return NewsFeatures(
            symbol=data["symbol"],
            feature_date=date.fromisoformat(data["feature_date"]),
            sentiment_1d=data["sentiment_1d"],
            sentiment_3d=data["sentiment_3d"],
            sentiment_momentum=data["sentiment_momentum"],
            sentiment_7d=data["sentiment_7d"],
            sentiment_14d=data["sentiment_14d"],
            sentiment_trend=data["sentiment_trend"],
            article_count_1d=data["article_count_1d"],
            article_count_7d=data["article_count_7d"],
            volume_ratio=data["volume_ratio"],
            avg_confidence_1d=data["avg_confidence_1d"],
            high_confidence_ratio=data["high_confidence_ratio"],
            sentiment_volatility_7d=data["sentiment_volatility_7d"],
            sentiment_range_7d=data["sentiment_range_7d"],
            earnings_sentiment=data.get("earnings_sentiment"),
            analyst_sentiment=data.get("analyst_sentiment"),
            product_sentiment=data.get("product_sentiment"),
        )
    
    async def get_news_articles(
        self,
        symbol: str,
        limit: int = 10,
        days_back: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Fetch actual news articles from ClickHouse for LLM context.
        
        Args:
            symbol: Stock ticker symbol
            limit: Maximum number of articles to return
            days_back: Number of days to look back for articles
            
        Returns:
            List of article dictionaries with title, source, summary, sentiment, etc.
        """
        if not self.ch_client:
            return []
        
        try:
            query = f"""
            SELECT
                title,
                source,
                summary,
                sentiment_score,
                sentiment_label,
                published_at,
                url
            FROM news_articles
            WHERE has(symbols, '{symbol}')
              AND published_at >= now() - INTERVAL {days_back} DAY
            ORDER BY published_at DESC
            LIMIT {limit}
            """
            
            loop = asyncio.get_event_loop()
            rows = await loop.run_in_executor(
                None,
                lambda: self.ch_client.query(query).result_rows
            )
            
            articles = []
            for row in rows:
                articles.append({
                    'title': row[0] or 'Unknown Title',
                    'source': row[1] or 'Unknown Source',
                    'summary': row[2] or '',
                    'sentiment_score': row[3],
                    'sentiment_label': row[4],
                    'published_at': row[5].isoformat() if row[5] else None,
                    'url': row[6] or '',
                })
            
            return articles
            
        except Exception as e:
            logger.warning(f"Failed to fetch news articles for {symbol}: {e}")
            return []
    
    async def close(self):
        """Close connections."""
        if self.redis_client:
            await self.redis_client.close()
        if self.ch_client:
            self.ch_client.close()

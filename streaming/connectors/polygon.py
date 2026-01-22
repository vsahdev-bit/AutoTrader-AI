"""
Polygon.io Market Data Connector
================================

Fetches market data, news, and ticker information from Polygon.io API.
Polygon.io provides comprehensive financial data including real-time and 
historical stock prices, options, forex, and crypto data.

API Documentation: https://polygon.io/docs/stocks

Features:
- Real-time and historical stock prices
- Stock news with sentiment
- Ticker details and financials
- Options, forex, and crypto data
- WebSocket streaming support

Rate Limits:
- Free tier: 5 requests/minute
- Starter: 100 requests/minute
- Developer: Unlimited

Required API Key: Get at https://polygon.io/dashboard/api-keys
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import os

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class PolygonConnector(BaseNewsConnector):
    """
    Market data connector for Polygon.io API.
    
    Polygon.io provides comprehensive market data including stock prices,
    news, and fundamental data. This connector focuses on news and 
    price data for the recommendation engine.
    
    Example Usage:
        connector = PolygonConnector(api_key="your_key")
        
        # Fetch news
        articles = await connector.fetch_news(
            symbols=["AAPL", "MSFT"],
            since=datetime.utcnow() - timedelta(hours=24),
            limit=50
        )
        
        # Fetch price data
        prices = await connector.get_stock_prices(
            symbol="AAPL",
            from_date=datetime.utcnow() - timedelta(days=30),
            to_date=datetime.utcnow()
        )
    """
    
    source = NewsSource.POLYGON
    base_url = "https://api.polygon.io"
    rate_limit_per_minute = 5  # Free tier limit
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[int] = None,
        timeout: int = 30,
    ):
        """
        Initialize the Polygon.io connector.
        
        Args:
            api_key: Polygon.io API key (or retrieved from Vault/POLYGON_API_KEY env var)
            rate_limit: Override default rate limit
            timeout: HTTP request timeout in seconds
        """
        # API key will be loaded lazily from Vault if not provided
        self._api_key_override = api_key
        self._api_key_loaded = api_key is not None
        super().__init__(api_key=api_key, rate_limit=rate_limit, timeout=timeout)
    
    async def _ensure_api_key(self):
        """Load API key from Vault if not already loaded."""
        if not self._api_key_loaded:
            from .base import get_api_key_from_vault
            self.api_key = self._api_key_override or await get_api_key_from_vault('polygon')
            self._api_key_loaded = True
            if not self.api_key:
                logger.warning("No Polygon.io API key found in Vault or environment")
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news from Polygon.io Ticker News API.
        
        Args:
            symbols: Stock symbols to filter news for (e.g., ["AAPL", "GOOGL"])
            since: Only return articles published after this time
            limit: Maximum articles to return (API max is 1000)
            
        Returns:
            List of NewsArticle objects
        """
        # Load API key from Vault if not already loaded
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("Polygon.io API key is required")
        
        # Build query parameters
        params: Dict[str, Any] = {
            "apiKey": self.api_key,
            "limit": min(limit, 1000),
            "order": "desc",
            "sort": "published_utc",
        }
        
        # Add ticker filter if symbols provided
        if symbols:
            params["ticker"] = symbols[0]  # Polygon filters by single ticker
        
        # Add time filter if since provided
        if since:
            params["published_utc.gte"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        url = f"{self.base_url}/v2/reference/news"
        logger.info(f"Fetching Polygon.io news for symbols={symbols}, since={since}")
        
        try:
            data = await self._make_request(url, params=params)
            
            # Check for API errors
            if data.get("status") == "ERROR":
                logger.error(f"Polygon.io API error: {data.get('error', 'Unknown error')}")
                return []
            
            # Parse articles from response
            results = data.get("results", [])
            articles = []
            
            for item in results:
                article = self._parse_article(item)
                if article:
                    articles.append(article)
            
            # If multiple symbols requested, fetch for each
            if symbols and len(symbols) > 1:
                for symbol in symbols[1:]:
                    params["ticker"] = symbol
                    additional_data = await self._make_request(url, params=params)
                    for item in additional_data.get("results", []):
                        article = self._parse_article(item)
                        if article and article.article_id not in [a.article_id for a in articles]:
                            articles.append(article)
            
            self.articles_fetched += len(articles)
            logger.info(f"Fetched {len(articles)} articles from Polygon.io")
            
            return articles[:limit]
            
        except Exception as e:
            logger.error(f"Failed to fetch Polygon.io news: {e}")
            raise
    
    def _parse_article(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """
        Parse a Polygon.io news item into a NewsArticle.
        
        Args:
            item: Raw news item from API response
            
        Returns:
            NewsArticle or None if parsing fails
        """
        try:
            # Parse publication time
            published_utc = item.get("published_utc", "")
            if published_utc:
                # Handle both formats: with and without milliseconds
                try:
                    published_at = datetime.strptime(published_utc, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    published_at = datetime.strptime(published_utc[:19], "%Y-%m-%dT%H:%M:%S")
            else:
                published_at = datetime.utcnow()
            
            # Extract symbols from tickers array
            symbols = item.get("tickers", [])
            
            # Categorize based on keywords
            title = item.get("title", "")
            description = item.get("description", "")
            categories = self._categorize_article(title, description)
            
            # Build metadata
            metadata = {
                "publisher": item.get("publisher", {}),
                "amp_url": item.get("amp_url"),
                "keywords": item.get("keywords", []),
                "insights": item.get("insights", []),
            }
            
            return NewsArticle(
                title=title,
                summary=description,
                url=item.get("article_url", ""),
                source=self.source,
                source_name=item.get("publisher", {}).get("name", "Polygon.io"),
                published_at=published_at,
                symbols=symbols,
                categories=categories,
                author=item.get("author", ""),
                image_url=item.get("image_url"),
                metadata=metadata,
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Polygon.io article: {e}")
            return None
    
    async def get_stock_prices(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timespan: str = "day",
        adjusted: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical stock prices from Polygon.io.
        
        Args:
            symbol: Stock ticker symbol
            from_date: Start date for price data
            to_date: End date for price data
            timespan: Aggregation period (minute, hour, day, week, month, quarter, year)
            adjusted: Whether to adjust for splits
            
        Returns:
            List of OHLCV price bars
        """
        if not self.api_key:
            raise ValueError("Polygon.io API key is required")
        
        url = (
            f"{self.base_url}/v2/aggs/ticker/{symbol}/range/1/{timespan}/"
            f"{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}"
        )
        
        params = {
            "apiKey": self.api_key,
            "adjusted": str(adjusted).lower(),
            "sort": "asc",
            "limit": 50000,
        }
        
        logger.info(f"Fetching Polygon.io prices for {symbol} from {from_date} to {to_date}")
        
        try:
            data = await self._make_request(url, params=params)
            
            if data.get("status") == "ERROR":
                logger.error(f"Polygon.io API error: {data.get('error', 'Unknown error')}")
                return []
            
            results = data.get("results", [])
            
            # Transform to standard format
            prices = []
            for bar in results:
                prices.append({
                    "timestamp": datetime.fromtimestamp(bar["t"] / 1000),
                    "open": bar["o"],
                    "high": bar["h"],
                    "low": bar["l"],
                    "close": bar["c"],
                    "volume": bar["v"],
                    "vwap": bar.get("vw"),
                    "transactions": bar.get("n"),
                })
            
            logger.info(f"Fetched {len(prices)} price bars from Polygon.io")
            return prices
            
        except Exception as e:
            logger.error(f"Failed to fetch Polygon.io prices: {e}")
            raise
    
    async def get_ticker_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a ticker.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with ticker details or None
        """
        if not self.api_key:
            raise ValueError("Polygon.io API key is required")
        
        url = f"{self.base_url}/v3/reference/tickers/{symbol}"
        params = {"apiKey": self.api_key}
        
        try:
            data = await self._make_request(url, params=params)
            
            if data.get("status") == "OK":
                return data.get("results", {})
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch ticker details: {e}")
            return None
    
    async def get_previous_close(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the previous day's OHLCV data for a ticker.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with previous close data or None
        """
        if not self.api_key:
            raise ValueError("Polygon.io API key is required")
        
        url = f"{self.base_url}/v2/aggs/ticker/{symbol}/prev"
        params = {"apiKey": self.api_key, "adjusted": "true"}
        
        try:
            data = await self._make_request(url, params=params)
            
            if data.get("status") == "OK" and data.get("results"):
                bar = data["results"][0]
                return {
                    "symbol": symbol,
                    "open": bar["o"],
                    "high": bar["h"],
                    "low": bar["l"],
                    "close": bar["c"],
                    "volume": bar["v"],
                    "vwap": bar.get("vw"),
                    "timestamp": datetime.fromtimestamp(bar["t"] / 1000),
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch previous close: {e}")
            return None
    
    async def get_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get a snapshot of current market data for a ticker.
        Includes current price, today's change, and previous day data.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with snapshot data or None
        """
        if not self.api_key:
            raise ValueError("Polygon.io API key is required")
        
        url = f"{self.base_url}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
        params = {"apiKey": self.api_key}
        
        try:
            data = await self._make_request(url, params=params)
            
            if data.get("status") == "OK":
                ticker = data.get("ticker", {})
                return {
                    "symbol": ticker.get("ticker"),
                    "day": ticker.get("day", {}),
                    "prev_day": ticker.get("prevDay", {}),
                    "min": ticker.get("min", {}),
                    "todays_change": ticker.get("todaysChange"),
                    "todays_change_perc": ticker.get("todaysChangePerc"),
                    "updated": ticker.get("updated"),
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch snapshot: {e}")
            return None

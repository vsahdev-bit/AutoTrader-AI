"""
Benzinga News Connector
=======================

Fetches news from Benzinga API, a premier financial news provider
known for real-time news, analyst ratings, and market insights.

API Documentation: https://docs.benzinga.io/

Features:
- Real-time financial news
- Analyst ratings and price targets
- Earnings announcements
- SEC filings alerts
- Options activity

Rate Limits:
- Depends on subscription tier
- Free tier: Limited requests

Required API Key: https://www.benzinga.com/apis/
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class BenzingaConnector(BaseNewsConnector):
    """
    News connector for Benzinga API.
    
    Benzinga provides high-quality financial news with fast delivery,
    making it valuable for time-sensitive trading signals.
    
    Example Usage:
        connector = BenzingaConnector(api_key="your_key")
        
        # Fetch news for symbols
        articles = await connector.fetch_news(
            symbols=["AAPL", "TSLA"],
            limit=50
        )
        
        # Fetch analyst ratings
        ratings = await connector.fetch_ratings(symbol="AAPL")
    """
    
    source = NewsSource.UNKNOWN  # Will create BENZINGA source
    base_url = "https://api.benzinga.com/api/v2"
    rate_limit_per_minute = 30
    
    # Benzinga content types
    CONTENT_TYPES = {
        "story": "News Story",
        "pressrelease": "Press Release", 
        "analyst_ratings": "Analyst Ratings",
        "sec_filings": "SEC Filings",
        "offerings": "Offerings",
        "mergers": "Mergers & Acquisitions",
    }
    
    # Map Benzinga channels to our categories
    CHANNEL_CATEGORY_MAP = {
        "earnings": NewsCategory.EARNINGS,
        "m&a": NewsCategory.MERGER_ACQUISITION,
        "analyst_ratings": NewsCategory.ANALYST,
        "sec": NewsCategory.REGULATORY,
        "technology": NewsCategory.PRODUCT,
        "politics": NewsCategory.MACROECONOMIC,
    }
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        # API key will be loaded lazily from Vault if not provided
        self._api_key_override = api_key
        self._api_key_loaded = api_key is not None
        super().__init__(api_key=api_key, **kwargs)
        self.source_name = "Benzinga"
    
    async def _ensure_api_key(self):
        """Load API key from Vault if not already loaded."""
        if not self._api_key_loaded:
            from .base import get_api_key_from_vault
            self.api_key = self._api_key_override or await get_api_key_from_vault('benzinga')
            self._api_key_loaded = True
            if not self.api_key:
                logger.warning("No Benzinga API key found in Vault or environment")
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news from Benzinga API.
        
        Args:
            symbols: Stock symbols to filter news
            since: Only return articles after this time
            limit: Maximum articles to return (max 100 per request)
            
        Returns:
            List of NewsArticle objects
        """
        # Load API key from Vault if not already loaded
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("Benzinga API key is required")
        
        # Build request parameters
        params: Dict[str, Any] = {
            "token": self.api_key,
            "pageSize": min(limit, 100),
            "displayOutput": "full",
        }
        
        # Add symbol filter
        if symbols:
            params["tickers"] = ",".join(symbols)
        
        # Add time filter
        if since:
            params["dateFrom"] = since.strftime("%Y-%m-%d")
        
        url = f"{self.base_url}/news"
        
        logger.info(f"Fetching Benzinga news for symbols={symbols}")
        
        try:
            # Benzinga API requires Accept header to return JSON
            headers = {
                "Accept": "application/json",
            }
            data = await self._make_request(url, params=params, headers=headers)
            
            articles = []
            for item in data:
                article = self._parse_article(item)
                if article:
                    articles.append(article)
            
            self.articles_fetched += len(articles)
            logger.info(f"Fetched {len(articles)} articles from Benzinga")
            
            return articles
            
        except Exception as e:
            logger.error(f"Failed to fetch Benzinga news: {e}")
            raise
    
    def _parse_article(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse Benzinga news item."""
        try:
            # Parse timestamps - Benzinga can return different formats
            created = item.get("created")
            published_at = None
            if created:
                # Try ISO format first
                try:
                    published_at = datetime.fromisoformat(created.replace("Z", "+00:00").replace("+00:00", ""))
                except ValueError:
                    # Try RFC 2822 format (e.g., "Tue, 13 Jan 2026 02:00:34 -0400")
                    try:
                        from email.utils import parsedate_to_datetime
                        published_at = parsedate_to_datetime(created)
                    except Exception:
                        pass
            
            if not published_at:
                published_at = datetime.utcnow()
            
            # Extract symbols from stocks array
            symbols = []
            stocks = item.get("stocks", [])
            for stock in stocks:
                if isinstance(stock, dict):
                    symbol = stock.get("name")
                elif isinstance(stock, str):
                    symbol = stock
                else:
                    continue
                if symbol:
                    symbols.append(symbol)
            
            # Map channels to categories
            categories = []
            channels = item.get("channels", [])
            for channel in channels:
                channel_name = channel.get("name", "").lower() if isinstance(channel, dict) else str(channel).lower()
                if channel_name in self.CHANNEL_CATEGORY_MAP:
                    categories.append(self.CHANNEL_CATEGORY_MAP[channel_name])
            
            if not categories:
                categories = [NewsCategory.GENERAL]
            
            # Get title and body
            title = item.get("title", "")
            body = item.get("body", "")
            teaser = item.get("teaser", "")
            
            return NewsArticle(
                title=title,
                summary=teaser or body[:500] if body else "",
                content=body,
                url=item.get("url", ""),
                source=self.source,
                source_name="Benzinga",
                published_at=published_at,
                symbols=symbols,
                categories=list(set(categories)),
                author=item.get("author"),
                image_url=item.get("image", [{}])[0].get("url") if item.get("image") else None,
                metadata={
                    "benzinga_id": item.get("id"),
                    "content_type": item.get("type"),
                    "channels": [c.get("name") if isinstance(c, dict) else c for c in channels],
                    "tags": item.get("tags", []),
                },
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Benzinga article: {e}")
            return None
    
    async def fetch_ratings(
        self,
        symbol: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch analyst ratings from Benzinga.
        
        Args:
            symbol: Stock symbol to get ratings for
            since: Only return ratings after this time
            limit: Maximum ratings to return
            
        Returns:
            List of rating objects with analyst, action, price target
        """
        if not self.api_key:
            raise ValueError("Benzinga API key is required")
        
        params = {
            "token": self.api_key,
            "pageSize": min(limit, 100),
        }
        
        if symbol:
            params["tickers"] = symbol
        
        if since:
            params["dateFrom"] = since.strftime("%Y-%m-%d")
        
        url = f"{self.base_url}/calendar/ratings"
        
        try:
            data = await self._make_request(url, params=params)
            ratings = data.get("ratings", [])
            
            parsed_ratings = []
            for rating in ratings:
                parsed_ratings.append({
                    "symbol": rating.get("ticker"),
                    "analyst": rating.get("analyst"),
                    "analyst_firm": rating.get("analyst_name"),
                    "action": rating.get("rating_current"),
                    "previous_rating": rating.get("rating_prior"),
                    "price_target": rating.get("pt_current"),
                    "previous_target": rating.get("pt_prior"),
                    "date": rating.get("date"),
                })
            
            return parsed_ratings
            
        except Exception as e:
            logger.error(f"Failed to fetch Benzinga ratings: {e}")
            return []
    
    async def fetch_earnings(
        self,
        symbol: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch earnings calendar from Benzinga.
        
        Args:
            symbol: Stock symbol to get earnings for
            since: Start date for earnings calendar
            
        Returns:
            List of upcoming/past earnings announcements
        """
        if not self.api_key:
            raise ValueError("Benzinga API key is required")
        
        params = {
            "token": self.api_key,
        }
        
        if symbol:
            params["tickers"] = symbol
        
        if since:
            params["dateFrom"] = since.strftime("%Y-%m-%d")
        
        url = f"{self.base_url}/calendar/earnings"
        
        try:
            data = await self._make_request(url, params=params)
            return data.get("earnings", [])
            
        except Exception as e:
            logger.error(f"Failed to fetch Benzinga earnings: {e}")
            return []

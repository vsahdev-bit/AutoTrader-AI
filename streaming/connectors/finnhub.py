"""
Finnhub News Connector
======================

Fetches company news from Finnhub API. Finnhub provides high-quality
financial news with good coverage of US stocks.

API Documentation: https://finnhub.io/docs/api/company-news

Features:
- Company-specific news filtering
- Market news (general financial news)
- Clean article metadata
- Good historical coverage

Rate Limits:
- Free tier: 60 requests/minute
- Premium: Higher limits based on plan

Required API Key: Get free key at https://finnhub.io/register
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class FinnhubConnector(BaseNewsConnector):
    """
    News connector for Finnhub Company News API.
    
    Finnhub provides company-specific news with good coverage and
    clean data formatting. It's particularly good for earnings and
    company announcement coverage.
    
    Example Usage:
        connector = FinnhubConnector(api_key="your_key")
        
        # Fetch news for specific companies
        articles = await connector.fetch_news(
            symbols=["AAPL", "MSFT"],
            since=datetime.utcnow() - timedelta(days=7)
        )
        
        # Fetch general market news
        market_news = await connector.fetch_market_news(category="general")
    """
    
    source = NewsSource.FINNHUB
    base_url = "https://finnhub.io/api/v1"
    rate_limit_per_minute = 60  # Free tier limit
    
    # Finnhub news categories for market news
    MARKET_NEWS_CATEGORIES = ["general", "forex", "crypto", "merger"]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[int] = None,
        timeout: int = 30,
    ):
        """
        Initialize the Finnhub connector.
        
        Args:
            api_key: Finnhub API key (or retrieved from Vault/FINNHUB_API_KEY env var)
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
            self.api_key = self._api_key_override or await get_api_key_from_vault('finnhub')
            self._api_key_loaded = True
            if not self.api_key:
                logger.warning("No Finnhub API key found in Vault or environment")
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch company news from Finnhub.
        
        Note: Finnhub requires fetching news per-symbol, so this method
        makes multiple API calls for multiple symbols.
        
        Args:
            symbols: Stock symbols to fetch news for (required for company news)
            since: Only return articles published after this time
            limit: Maximum articles to return per symbol
            
        Returns:
            List of NewsArticle objects aggregated from all symbols
        """
        # Load API key from Vault if not already loaded
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("Finnhub API key is required")
        
        # If no symbols provided, fetch general market news
        if not symbols:
            return await self.fetch_market_news(category="general", limit=limit)
        
        # Default time range: last 7 days
        if since is None:
            since = datetime.utcnow() - timedelta(days=7)
        
        end_date = datetime.utcnow()
        
        all_articles = []
        
        # Fetch news for each symbol (Finnhub API limitation)
        for symbol in symbols:
            try:
                articles = await self._fetch_company_news(
                    symbol=symbol,
                    from_date=since,
                    to_date=end_date,
                )
                all_articles.extend(articles)
                
            except Exception as e:
                logger.error(f"Failed to fetch news for {symbol}: {e}")
                continue
        
        # Sort by published date (newest first) and limit
        all_articles.sort(key=lambda a: a.published_at, reverse=True)
        
        # Deduplicate by article_id (same article might be returned for multiple symbols)
        seen_ids = set()
        unique_articles = []
        for article in all_articles:
            if article.article_id not in seen_ids:
                seen_ids.add(article.article_id)
                unique_articles.append(article)
        
        self.articles_fetched += len(unique_articles[:limit])
        return unique_articles[:limit]
    
    async def _fetch_company_news(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
    ) -> List[NewsArticle]:
        """
        Fetch news for a single company symbol.
        
        Args:
            symbol: Stock ticker symbol
            from_date: Start of date range
            to_date: End of date range
            
        Returns:
            List of NewsArticle objects for the symbol
        """
        params = {
            "symbol": symbol,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "token": self.api_key,
        }
        
        url = f"{self.base_url}/company-news"
        
        logger.debug(f"Fetching Finnhub news for {symbol}")
        
        data = await self._make_request(url, params=params)
        
        # Finnhub returns a list of articles directly
        if not isinstance(data, list):
            logger.warning(f"Unexpected response format from Finnhub: {type(data)}")
            return []
        
        articles = []
        for item in data:
            article = self._parse_article(item, primary_symbol=symbol)
            if article:
                articles.append(article)
        
        logger.info(f"Fetched {len(articles)} articles for {symbol} from Finnhub")
        return articles
    
    async def fetch_market_news(
        self,
        category: str = "general",
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch general market news (not company-specific).
        
        Args:
            category: News category - "general", "forex", "crypto", or "merger"
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects for market news
        """
        if category not in self.MARKET_NEWS_CATEGORIES:
            raise ValueError(f"Invalid category. Must be one of: {self.MARKET_NEWS_CATEGORIES}")
        
        params = {
            "category": category,
            "token": self.api_key,
        }
        
        url = f"{self.base_url}/news"
        
        logger.info(f"Fetching Finnhub market news for category={category}")
        
        data = await self._make_request(url, params=params)
        
        if not isinstance(data, list):
            return []
        
        articles = []
        for item in data[:limit]:
            article = self._parse_article(item)
            if article:
                articles.append(article)
        
        self.articles_fetched += len(articles)
        return articles
    
    def _parse_article(
        self,
        item: Dict[str, Any],
        primary_symbol: Optional[str] = None,
    ) -> Optional[NewsArticle]:
        """
        Parse a Finnhub news item into a NewsArticle.
        
        Finnhub article format:
        {
            "category": "company",
            "datetime": 1704067200,  // Unix timestamp
            "headline": "Article title",
            "id": 123456,
            "image": "https://...",
            "related": "AAPL",  // Related ticker
            "source": "Reuters",
            "summary": "Article summary...",
            "url": "https://..."
        }
        
        Args:
            item: Raw news item from API response
            primary_symbol: Symbol this article was fetched for
            
        Returns:
            NewsArticle or None if parsing fails
        """
        try:
            # Parse Unix timestamp
            timestamp = item.get("datetime", 0)
            if timestamp:
                published_at = datetime.utcfromtimestamp(timestamp)
            else:
                published_at = datetime.utcnow()
            
            # Extract symbols
            symbols = []
            if primary_symbol:
                symbols.append(primary_symbol)
            
            # Add related ticker if different from primary
            related = item.get("related", "")
            if related and related != primary_symbol:
                # Related might be comma-separated
                for sym in related.split(","):
                    sym = sym.strip()
                    if sym and sym not in symbols:
                        symbols.append(sym)
            
            # Categorize based on headline and summary
            title = item.get("headline", "")
            summary = item.get("summary", "")
            categories = self._categorize_article(title, summary)
            
            # Map Finnhub category to our NewsCategory
            finnhub_category = item.get("category", "").lower()
            if finnhub_category == "merger" and NewsCategory.MERGER_ACQUISITION not in categories:
                categories.append(NewsCategory.MERGER_ACQUISITION)
            
            return NewsArticle(
                title=title,
                summary=summary,
                url=item.get("url", ""),
                source=self.source,
                source_name=item.get("source", "Finnhub"),
                published_at=published_at,
                symbols=symbols,
                categories=categories,
                image_url=item.get("image"),
                metadata={
                    "finnhub_id": item.get("id"),
                    "finnhub_category": finnhub_category,
                },
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Finnhub article: {e}")
            return None

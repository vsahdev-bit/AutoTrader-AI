"""
Financial Modeling Prep (FMP) Connector
=======================================

Fetches news and financial data from Financial Modeling Prep API.
FMP provides comprehensive financial data including news, fundamentals,
price data, and SEC filings.

API Documentation: https://site.financialmodelingprep.com/developer/docs

Features:
- Stock news with sentiment
- Press releases
- SEC filings (8-K, 10-K, 10-Q)
- Earnings transcripts
- Real-time and historical prices
- Company fundamentals

Rate Limits:
- Free tier: 250 requests/day
- Paid plans: Higher limits

Required API Key: https://financialmodelingprep.com/developer
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class FinancialModelingPrepConnector(BaseNewsConnector):
    """
    Connector for Financial Modeling Prep API.
    
    FMP is excellent for combining news with fundamental data
    and SEC filings for comprehensive analysis.
    
    Example Usage:
        connector = FinancialModelingPrepConnector(api_key="your_key")
        
        # Fetch stock news
        articles = await connector.fetch_news(symbols=["AAPL"])
        
        # Fetch SEC filings
        filings = await connector.fetch_sec_filings(symbol="AAPL")
        
        # Fetch press releases
        releases = await connector.fetch_press_releases(symbol="AAPL")
    """
    
    source = NewsSource.UNKNOWN
    base_url = "https://financialmodelingprep.com/api"
    rate_limit_per_minute = 10  # Conservative for free tier
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        # API key will be loaded lazily from Vault if not provided
        self._api_key_override = api_key
        self._api_key_loaded = api_key is not None
        super().__init__(api_key=api_key, **kwargs)
        self.source_name = "Financial Modeling Prep"
    
    async def _ensure_api_key(self):
        """Load API key from Vault if not already loaded."""
        if not self._api_key_loaded:
            from .base import get_api_key_from_vault
            self.api_key = self._api_key_override or await get_api_key_from_vault('fmp')
            self._api_key_loaded = True
            if not self.api_key:
                logger.warning("No FMP API key found in Vault or environment")
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch stock news from FMP.
        
        Args:
            symbols: Stock symbols to fetch news for
            since: Only return articles after this time
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects
        """
        # Load API key from Vault if not already loaded
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        all_articles = []
        
        if symbols:
            # Fetch news for specific symbols
            for symbol in symbols:
                try:
                    articles = await self._fetch_stock_news(symbol, limit)
                    all_articles.extend(articles)
                except Exception as e:
                    logger.error(f"Failed to fetch FMP news for {symbol}: {e}")
        else:
            # Fetch general market news
            all_articles = await self._fetch_general_news(limit)
        
        # Filter by time
        if since:
            all_articles = [a for a in all_articles if a.published_at >= since]
        
        # Deduplicate
        seen = set()
        unique = []
        for a in all_articles:
            if a.article_id not in seen:
                seen.add(a.article_id)
                unique.append(a)
        
        self.articles_fetched += len(unique[:limit])
        return unique[:limit]
    
    async def _fetch_stock_news(self, symbol: str, limit: int) -> List[NewsArticle]:
        """Fetch news for a specific stock."""
        url = f"{self.base_url}/v3/stock_news"
        params = {
            "tickers": symbol,
            "limit": min(limit, 100),
            "apikey": self.api_key,
        }
        
        data = await self._make_request(url, params=params)
        
        articles = []
        for item in data:
            article = self._parse_article(item)
            if article:
                articles.append(article)
        
        return articles
    
    async def _fetch_general_news(self, limit: int) -> List[NewsArticle]:
        """Fetch general market news."""
        url = f"{self.base_url}/v3/fmp/articles"
        params = {
            "page": 0,
            "size": min(limit, 100),
            "apikey": self.api_key,
        }
        
        data = await self._make_request(url, params=params)
        content = data.get("content", [])
        
        articles = []
        for item in content:
            article = self._parse_fmp_article(item)
            if article:
                articles.append(article)
        
        return articles
    
    def _parse_article(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse FMP stock news item."""
        try:
            # Parse timestamp
            pub_date = item.get("publishedDate", "")
            if pub_date:
                published_at = datetime.fromisoformat(
                    pub_date.replace("Z", "+00:00").replace("+00:00", "")
                )
            else:
                published_at = datetime.utcnow()
            
            symbol = item.get("symbol", "")
            symbols = [symbol] if symbol else []
            
            title = item.get("title", "")
            text = item.get("text", "")
            
            return NewsArticle(
                title=title,
                summary=text[:500] if text else "",
                content=text,
                url=item.get("url", ""),
                source=self.source,
                source_name=item.get("site", "FMP"),
                published_at=published_at,
                symbols=symbols,
                categories=self._categorize_article(title, text),
                image_url=item.get("image"),
                metadata={
                    "fmp_symbol": symbol,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to parse FMP article: {e}")
            return None
    
    def _parse_fmp_article(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse FMP own articles."""
        try:
            pub_date = item.get("date", "")
            if pub_date:
                published_at = datetime.fromisoformat(pub_date.replace("Z", ""))
            else:
                published_at = datetime.utcnow()
            
            title = item.get("title", "")
            content = item.get("content", "")
            
            # Extract tickers from content
            tickers = item.get("tickers", "")
            symbols = [t.strip() for t in tickers.split(",") if t.strip()]
            
            return NewsArticle(
                title=title,
                summary=content[:500] if content else "",
                content=content,
                url=item.get("link", ""),
                source=self.source,
                source_name="Financial Modeling Prep",
                published_at=published_at,
                symbols=symbols,
                categories=self._categorize_article(title, content),
                author=item.get("author"),
                image_url=item.get("image"),
                metadata={},
            )
        except Exception as e:
            logger.warning(f"Failed to parse FMP article: {e}")
            return None
    
    async def fetch_press_releases(
        self,
        symbol: str,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """Fetch press releases for a symbol."""
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        url = f"{self.base_url}/v3/press-releases/{symbol}"
        params = {
            "limit": min(limit, 100),
            "apikey": self.api_key,
        }
        
        try:
            data = await self._make_request(url, params=params)
            
            articles = []
            for item in data:
                pub_date = item.get("date", "")
                if pub_date:
                    published_at = datetime.fromisoformat(pub_date)
                else:
                    published_at = datetime.utcnow()
                
                title = item.get("title", "")
                text = item.get("text", "")
                
                article = NewsArticle(
                    title=title,
                    summary=text[:500] if text else "",
                    content=text,
                    url="",
                    source=self.source,
                    source_name="Press Release",
                    published_at=published_at,
                    symbols=[symbol],
                    categories=[NewsCategory.GENERAL],
                    metadata={"type": "press_release"},
                )
                articles.append(article)
            
            return articles
        except Exception as e:
            logger.error(f"Failed to fetch FMP press releases: {e}")
            return []
    
    async def fetch_sec_filings(
        self,
        symbol: str,
        filing_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch SEC filings for a symbol.
        
        Args:
            symbol: Stock symbol
            filing_type: Filter by type (10-K, 10-Q, 8-K, etc.)
            limit: Maximum filings to return
            
        Returns:
            List of filing objects
        """
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        url = f"{self.base_url}/v3/sec_filings/{symbol}"
        params = {
            "limit": min(limit, 100),
            "apikey": self.api_key,
        }
        
        if filing_type:
            params["type"] = filing_type
        
        try:
            data = await self._make_request(url, params=params)
            return data
        except Exception as e:
            logger.error(f"Failed to fetch FMP SEC filings: {e}")
            return []
    
    async def fetch_earnings_surprises(
        self,
        symbol: str,
    ) -> List[Dict[str, Any]]:
        """Fetch earnings surprises for a symbol."""
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        url = f"{self.base_url}/v3/earnings-surprises/{symbol}"
        params = {"apikey": self.api_key}
        
        try:
            return await self._make_request(url, params=params)
        except Exception as e:
            logger.error(f"Failed to fetch FMP earnings: {e}")
            return []

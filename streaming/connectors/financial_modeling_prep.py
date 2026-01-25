"""
Financial Modeling Prep (FMP) Connector
=======================================

Fetches company profile, quote, and news data from Financial Modeling Prep API.
FMP provides comprehensive financial data including real-time quotes,
company profiles, price changes, and market articles.

API Documentation: https://site.financialmodelingprep.com/developer/docs

Features:
- Company profiles with detailed information
- Real-time stock quotes (full and short)
- Stock price changes (1D, 5D, 1M, 3M, 6M, 1Y, etc.)
- FMP market articles and news

Rate Limits:
- Free tier: 250 requests/day
- Paid plans: Higher limits

Note: As of August 2025, FMP deprecated legacy v3/v4 endpoints.
New accounts must use the /stable/ API endpoints.

Required API Key: https://financialmodelingprep.com/developer
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class FinancialModelingPrepConnector(BaseNewsConnector):
    """
    Connector for Financial Modeling Prep API.
    
    FMP provides company profiles and real-time quote data
    for comprehensive stock analysis.
    
    Example Usage:
        connector = FinancialModelingPrepConnector(api_key="your_key")
        
        # Fetch company profile
        profile = await connector.fetch_profile(symbol="AAPL")
        
        # Fetch stock quote
        quote = await connector.fetch_quote(symbol="AAPL")
        
        # Fetch multiple profiles
        profiles = await connector.fetch_profiles(symbols=["AAPL", "GOOGL", "MSFT"])
    """
    
    source = NewsSource.UNKNOWN
    base_url = "https://financialmodelingprep.com/stable"
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
    
    async def fetch_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch company profile for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            
        Returns:
            Dictionary containing company profile data including:
            - symbol, companyName, price, marketCap
            - sector, industry, description
            - ceo, website, exchange
            - beta, volume, averageVolume
            - range, change, changePercentage
        """
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        url = f"{self.base_url}/profile"
        params = {
            "symbol": symbol,
            "apikey": self.api_key,
        }
        
        try:
            data = await self._make_request(url, params=params)
            if data and isinstance(data, list) and len(data) > 0:
                return data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch FMP profile for {symbol}: {e}")
            return None
    
    async def fetch_profiles(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch company profiles for multiple symbols.
        
        Args:
            symbols: List of stock symbols (e.g., ["AAPL", "GOOGL", "MSFT"])
            
        Returns:
            List of dictionaries containing company profile data
        """
        profiles = []
        for symbol in symbols:
            profile = await self.fetch_profile(symbol)
            if profile:
                profiles.append(profile)
        return profiles
    
    async def fetch_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch real-time quote for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            
        Returns:
            Dictionary containing quote data including:
            - symbol, name, price
            - change, changePercentage
            - volume, dayLow, dayHigh
            - yearLow, yearHigh, marketCap
            - priceAvg50, priceAvg200
            - open, previousClose, timestamp
        """
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        url = f"{self.base_url}/quote"
        params = {
            "symbol": symbol,
            "apikey": self.api_key,
        }
        
        try:
            data = await self._make_request(url, params=params)
            if data and isinstance(data, list) and len(data) > 0:
                return data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch FMP quote for {symbol}: {e}")
            return None
    
    async def fetch_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch real-time quotes for multiple symbols.
        
        Args:
            symbols: List of stock symbols (e.g., ["AAPL", "GOOGL", "MSFT"])
            
        Returns:
            List of dictionaries containing quote data
        """
        quotes = []
        for symbol in symbols:
            quote = await self.fetch_quote(symbol)
            if quote:
                quotes.append(quote)
        return quotes
    
    async def fetch_quote_short(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a short/condensed quote for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            
        Returns:
            Dictionary containing condensed quote data:
            - symbol, price, change, volume
        """
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        url = f"{self.base_url}/quote-short"
        params = {
            "symbol": symbol,
            "apikey": self.api_key,
        }
        
        try:
            data = await self._make_request(url, params=params)
            if data and isinstance(data, list) and len(data) > 0:
                return data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch FMP quote-short for {symbol}: {e}")
            return None
    
    async def fetch_quotes_short(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch short/condensed quotes for multiple symbols.
        
        Args:
            symbols: List of stock symbols (e.g., ["AAPL", "GOOGL", "MSFT"])
            
        Returns:
            List of dictionaries containing condensed quote data
        """
        quotes = []
        for symbol in symbols:
            quote = await self.fetch_quote_short(symbol)
            if quote:
                quotes.append(quote)
        return quotes
    
    async def fetch_stock_price_change(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch stock price change data for various time periods.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            
        Returns:
            Dictionary containing price change percentages:
            - symbol, 1D, 5D, 1M, 3M, 6M, ytd, 1Y, 3Y, 5Y, 10Y, max
        """
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        url = f"{self.base_url}/stock-price-change"
        params = {
            "symbol": symbol,
            "apikey": self.api_key,
        }
        
        try:
            data = await self._make_request(url, params=params)
            if data and isinstance(data, list) and len(data) > 0:
                return data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to fetch FMP stock-price-change for {symbol}: {e}")
            return None
    
    async def fetch_stock_price_changes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch stock price change data for multiple symbols.
        
        Args:
            symbols: List of stock symbols (e.g., ["AAPL", "GOOGL", "MSFT"])
            
        Returns:
            List of dictionaries containing price change data
        """
        changes = []
        for symbol in symbols:
            change = await self.fetch_stock_price_change(symbol)
            if change:
                changes.append(change)
        return changes
    
    async def fetch_fmp_articles(self, page: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch FMP market articles and news.
        
        Args:
            page: Page number (0-indexed)
            limit: Number of articles to fetch (max 50)
            
        Returns:
            List of dictionaries containing article data:
            - title, date, content, tickers, image, link, author, site
        """
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        url = f"{self.base_url}/fmp-articles"
        params = {
            "page": page,
            "limit": min(limit, 50),
            "apikey": self.api_key,
        }
        
        try:
            data = await self._make_request(url, params=params)
            if data and isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error(f"Failed to fetch FMP articles: {e}")
            return []
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news articles from FMP.
        
        This method uses the fmp-articles endpoint which is available
        on the current subscription. For stock-specific news filtering,
        articles are filtered by the provided symbols.
        
        Args:
            symbols: Optional list of stock symbols to filter articles
            since: Optional datetime to filter articles after this time
            limit: Maximum number of articles to return
            
        Returns:
            List of NewsArticle objects
        """
        articles_data = await self.fetch_fmp_articles(page=0, limit=limit)
        
        articles = []
        for article in articles_data:
            # Filter by symbols if provided
            if symbols:
                article_tickers = article.get("tickers", "")
                if not any(symbol in article_tickers for symbol in symbols):
                    continue
            
            # Filter by date if provided
            article_date = None
            if article.get("date"):
                try:
                    article_date = datetime.strptime(article["date"], "%Y-%m-%d %H:%M:%S")
                    if since and article_date < since:
                        continue
                except ValueError:
                    pass
            
            # Extract symbol from tickers (format: "NASDAQ:MSFT" -> "MSFT")
            tickers_raw = article.get("tickers", "")
            symbols_list = []
            for ticker in tickers_raw.split(","):
                ticker = ticker.strip()
                if ":" in ticker:
                    ticker = ticker.split(":")[1]
                if ticker:
                    symbols_list.append(ticker)
            
            news_article = NewsArticle(
                title=article.get("title", ""),
                summary=article.get("content", "")[:500] if article.get("content") else "",
                url=article.get("link", ""),
                source=self.source,
                source_name=self.source_name,
                published_at=article_date or datetime.now(),
                content=article.get("content", ""),
                symbols=symbols_list,
                categories=[NewsCategory.MARKET],
                author=article.get("author"),
                image_url=article.get("image"),
            )
            articles.append(news_article)
        
        return articles[:limit]

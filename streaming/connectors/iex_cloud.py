"""
IEX Cloud API Connector
=======================

Fetches market data, news, and financial information from IEX Cloud API.
IEX Cloud provides institutional-quality financial data with excellent
documentation and reliable uptime.

API Documentation: https://iexcloud.io/docs/api/

Features:
- Real-time and historical stock prices
- Company news and press releases
- Fundamental data (earnings, financials, stats)
- Options, forex, crypto, and economic data
- Batch API for multiple symbols

Rate Limits:
- Free tier: 50,000 messages/month
- Launch: 5M messages/month
- Scale: 20M+ messages/month

Required API Key: Get at https://iexcloud.io/console/
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import os

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class IEXCloudConnector(BaseNewsConnector):
    """
    Market data connector for IEX Cloud API.
    
    IEX Cloud is known for high-quality data and developer-friendly API.
    This connector provides access to news, prices, and fundamental data.
    
    Example Usage:
        connector = IEXCloudConnector(api_key="your_key")
        
        # Fetch news
        articles = await connector.fetch_news(
            symbols=["AAPL", "MSFT"],
            limit=50
        )
        
        # Fetch price data
        quote = await connector.get_quote("AAPL")
        
        # Fetch batch data for multiple symbols
        data = await connector.get_batch(
            symbols=["AAPL", "MSFT"],
            types=["quote", "news", "stats"]
        )
    """
    
    source = NewsSource.IEX_CLOUD
    base_url = "https://cloud.iexapis.com/stable"
    sandbox_url = "https://sandbox.iexapis.com/stable"
    rate_limit_per_minute = 100  # Reasonable default
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[int] = None,
        timeout: int = 30,
        use_sandbox: bool = False,
    ):
        """
        Initialize the IEX Cloud connector.
        
        Args:
            api_key: IEX Cloud API key (or retrieved from Vault/IEX_CLOUD_API_KEY env var)
            rate_limit: Override default rate limit
            timeout: HTTP request timeout in seconds
            use_sandbox: Use sandbox environment for testing (free, no limits)
        """
        # API key will be loaded lazily from Vault if not provided
        self._api_key_override = api_key
        self._api_key_loaded = api_key is not None
        super().__init__(api_key=api_key, rate_limit=rate_limit, timeout=timeout)
        self.use_sandbox = use_sandbox
        
        # Use sandbox URL if specified
        if use_sandbox:
            self.base_url = self.sandbox_url
    
    # Connector is disabled until API key is configured
    enabled = False
    
    async def _ensure_api_key(self):
        """Load API key from Vault if not already loaded."""
        if not self._api_key_loaded:
            from .base import get_api_key_from_vault
            self.api_key = self._api_key_override or await get_api_key_from_vault('iex_cloud')
            self._api_key_loaded = True
            if self.api_key:
                self.__class__.enabled = True
            else:
                logger.info("IEX Cloud connector is disabled - no API key configured")
    
    def _get_url(self, endpoint: str) -> str:
        """Build full URL for an endpoint."""
        return f"{self.base_url}/{endpoint}"
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news from IEX Cloud News API.
        
        Args:
            symbols: Stock symbols to filter news for (e.g., ["AAPL", "GOOGL"])
            since: Only return articles published after this time (not directly supported)
            limit: Maximum articles per symbol to return (max 50 per symbol)
            
        Returns:
            List of NewsArticle objects
        """
        # Load API key from Vault if not already loaded
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("IEX Cloud API key is required")
        
        articles = []
        
        # If no symbols provided, fetch market news
        if not symbols:
            symbols = ["market"]
        
        for symbol in symbols:
            try:
                # IEX has different endpoints for company vs market news
                if symbol.lower() == "market":
                    url = self._get_url("news")
                else:
                    url = self._get_url(f"stock/{symbol}/news")
                
                params = {
                    "token": self.api_key,
                    "last": min(limit, 50),  # IEX max is 50 per request
                }
                
                logger.info(f"Fetching IEX Cloud news for {symbol}")
                
                data = await self._make_request(url, params=params)
                
                if isinstance(data, list):
                    for item in data:
                        article = self._parse_article(item, symbol)
                        if article:
                            # Filter by since if provided
                            if since and article.published_at < since:
                                continue
                            # Avoid duplicates
                            if article.article_id not in [a.article_id for a in articles]:
                                articles.append(article)
                
            except Exception as e:
                logger.error(f"Failed to fetch IEX Cloud news for {symbol}: {e}")
                continue
        
        self.articles_fetched += len(articles)
        logger.info(f"Fetched {len(articles)} articles from IEX Cloud")
        
        return articles[:limit]
    
    def _parse_article(self, item: Dict[str, Any], symbol: str) -> Optional[NewsArticle]:
        """
        Parse an IEX Cloud news item into a NewsArticle.
        
        Args:
            item: Raw news item from API response
            symbol: Symbol this news was fetched for
            
        Returns:
            NewsArticle or None if parsing fails
        """
        try:
            # Parse publication time (Unix timestamp in milliseconds)
            datetime_val = item.get("datetime")
            if datetime_val:
                if isinstance(datetime_val, int):
                    published_at = datetime.fromtimestamp(datetime_val / 1000)
                else:
                    published_at = datetime.fromisoformat(str(datetime_val).replace("Z", "+00:00"))
            else:
                published_at = datetime.utcnow()
            
            # Get related symbols
            related = item.get("related", "")
            symbols = [s.strip() for s in related.split(",") if s.strip()]
            if symbol.lower() != "market" and symbol not in symbols:
                symbols.insert(0, symbol)
            
            # Categorize based on content
            headline = item.get("headline", "")
            summary = item.get("summary", "")
            categories = self._categorize_article(headline, summary)
            
            # Build metadata
            metadata = {
                "hasPaywall": item.get("hasPaywall", False),
                "lang": item.get("lang", "en"),
                "provider": item.get("provider", ""),
                "qmUrl": item.get("qmUrl", ""),
            }
            
            return NewsArticle(
                title=headline,
                summary=summary,
                url=item.get("url", ""),
                source=self.source,
                source_name=item.get("source", "IEX Cloud"),
                published_at=published_at,
                symbols=symbols,
                categories=categories,
                author=None,  # IEX doesn't provide author
                image_url=item.get("image"),
                metadata=metadata,
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse IEX Cloud article: {e}")
            return None
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get real-time quote for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Quote data dictionary or None
        """
        if not self.api_key:
            raise ValueError("IEX Cloud API key is required")
        
        url = self._get_url(f"stock/{symbol}/quote")
        params = {"token": self.api_key}
        
        try:
            data = await self._make_request(url, params=params)
            return {
                "symbol": data.get("symbol"),
                "companyName": data.get("companyName"),
                "latestPrice": data.get("latestPrice"),
                "change": data.get("change"),
                "changePercent": data.get("changePercent"),
                "open": data.get("open"),
                "high": data.get("high"),
                "low": data.get("low"),
                "close": data.get("close"),
                "previousClose": data.get("previousClose"),
                "volume": data.get("volume"),
                "avgVolume": data.get("avgTotalVolume"),
                "marketCap": data.get("marketCap"),
                "peRatio": data.get("peRatio"),
                "week52High": data.get("week52High"),
                "week52Low": data.get("week52Low"),
                "latestTime": data.get("latestTime"),
                "latestUpdate": data.get("latestUpdate"),
            }
        except Exception as e:
            logger.error(f"Failed to fetch quote for {symbol}: {e}")
            return None
    
    async def get_historical_prices(
        self,
        symbol: str,
        range: str = "1m",
    ) -> List[Dict[str, Any]]:
        """
        Get historical price data for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            range: Time range (5d, 1m, 3m, 6m, 1y, 2y, 5y, max, ytd)
            
        Returns:
            List of historical price bars
        """
        if not self.api_key:
            raise ValueError("IEX Cloud API key is required")
        
        url = self._get_url(f"stock/{symbol}/chart/{range}")
        params = {"token": self.api_key}
        
        try:
            data = await self._make_request(url, params=params)
            
            prices = []
            for bar in data:
                prices.append({
                    "date": bar.get("date"),
                    "open": bar.get("open"),
                    "high": bar.get("high"),
                    "low": bar.get("low"),
                    "close": bar.get("close"),
                    "volume": bar.get("volume"),
                    "change": bar.get("change"),
                    "changePercent": bar.get("changePercent"),
                    "changeOverTime": bar.get("changeOverTime"),
                })
            
            logger.info(f"Fetched {len(prices)} price bars from IEX Cloud for {symbol}")
            return prices
            
        except Exception as e:
            logger.error(f"Failed to fetch historical prices for {symbol}: {e}")
            return []
    
    async def get_key_stats(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get key statistics for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Key stats dictionary or None
        """
        if not self.api_key:
            raise ValueError("IEX Cloud API key is required")
        
        url = self._get_url(f"stock/{symbol}/stats")
        params = {"token": self.api_key}
        
        try:
            data = await self._make_request(url, params=params)
            return {
                "companyName": data.get("companyName"),
                "marketCap": data.get("marketcap"),
                "week52High": data.get("week52high"),
                "week52Low": data.get("week52low"),
                "week52Change": data.get("week52change"),
                "sharesOutstanding": data.get("sharesOutstanding"),
                "avg10Volume": data.get("avg10Volume"),
                "avg30Volume": data.get("avg30Volume"),
                "day200MovingAvg": data.get("day200MovingAvg"),
                "day50MovingAvg": data.get("day50MovingAvg"),
                "employees": data.get("employees"),
                "ttmEPS": data.get("ttmEPS"),
                "ttmDividendRate": data.get("ttmDividendRate"),
                "dividendYield": data.get("dividendYield"),
                "nextDividendDate": data.get("nextDividendDate"),
                "exDividendDate": data.get("exDividendDate"),
                "nextEarningsDate": data.get("nextEarningsDate"),
                "peRatio": data.get("peRatio"),
                "beta": data.get("beta"),
            }
        except Exception as e:
            logger.error(f"Failed to fetch key stats for {symbol}: {e}")
            return None
    
    async def get_batch(
        self,
        symbols: List[str],
        types: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch request for multiple symbols and data types.
        
        This is more efficient than making individual requests.
        
        Args:
            symbols: List of stock ticker symbols
            types: List of data types (quote, news, chart, stats, etc.)
            
        Returns:
            Dictionary mapping symbols to their data
        """
        if not self.api_key:
            raise ValueError("IEX Cloud API key is required")
        
        url = self._get_url("stock/market/batch")
        params = {
            "token": self.api_key,
            "symbols": ",".join(symbols),
            "types": ",".join(types),
        }
        
        try:
            data = await self._make_request(url, params=params)
            return data
        except Exception as e:
            logger.error(f"Failed to fetch batch data: {e}")
            return {}
    
    async def get_intraday_prices(
        self,
        symbol: str,
    ) -> List[Dict[str, Any]]:
        """
        Get intraday minute-by-minute price data.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            List of intraday price bars
        """
        if not self.api_key:
            raise ValueError("IEX Cloud API key is required")
        
        url = self._get_url(f"stock/{symbol}/intraday-prices")
        params = {"token": self.api_key}
        
        try:
            data = await self._make_request(url, params=params)
            
            prices = []
            for bar in data:
                prices.append({
                    "date": bar.get("date"),
                    "minute": bar.get("minute"),
                    "open": bar.get("open"),
                    "high": bar.get("high"),
                    "low": bar.get("low"),
                    "close": bar.get("close"),
                    "volume": bar.get("volume"),
                    "average": bar.get("average"),
                    "numberOfTrades": bar.get("numberOfTrades"),
                })
            
            return prices
            
        except Exception as e:
            logger.error(f"Failed to fetch intraday prices for {symbol}: {e}")
            return []
    
    async def get_company_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get company information.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Company info dictionary or None
        """
        if not self.api_key:
            raise ValueError("IEX Cloud API key is required")
        
        url = self._get_url(f"stock/{symbol}/company")
        params = {"token": self.api_key}
        
        try:
            data = await self._make_request(url, params=params)
            return {
                "symbol": data.get("symbol"),
                "companyName": data.get("companyName"),
                "exchange": data.get("exchange"),
                "industry": data.get("industry"),
                "website": data.get("website"),
                "description": data.get("description"),
                "CEO": data.get("CEO"),
                "securityName": data.get("securityName"),
                "issueType": data.get("issueType"),
                "sector": data.get("sector"),
                "employees": data.get("employees"),
                "tags": data.get("tags", []),
                "address": data.get("address"),
                "city": data.get("city"),
                "state": data.get("state"),
                "zip": data.get("zip"),
                "country": data.get("country"),
                "phone": data.get("phone"),
            }
        except Exception as e:
            logger.error(f"Failed to fetch company info for {symbol}: {e}")
            return None

"""
Yahoo Finance Connector
=======================

Fetches news and market data from Yahoo Finance API.
Yahoo Finance provides comprehensive financial news coverage
and real-time/historical market data.

Features:
- Company-specific news
- Market news by category
- Real-time quotes
- Historical price data
- No API key required (uses public endpoints)

Rate Limits:
- No official rate limits, but be respectful
- Recommended: 5 requests/second max

Note: Yahoo Finance doesn't have an official API. This connector
uses the unofficial yfinance library and public endpoints.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import asyncio

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class YahooFinanceConnector(BaseNewsConnector):
    """
    News and data connector for Yahoo Finance.
    
    Uses the yfinance library for market data and scrapes news
    from Yahoo Finance's public API endpoints.
    
    Example Usage:
        connector = YahooFinanceConnector()
        
        # Fetch news for specific symbols
        articles = await connector.fetch_news(symbols=["AAPL", "MSFT"])
        
        # Fetch market data
        data = await connector.fetch_quote("AAPL")
    """
    
    source = NewsSource.RSS_YAHOO
    base_url = "https://query1.finance.yahoo.com"
    rate_limit_per_minute = 60
    
    # Yahoo Finance news categories
    NEWS_CATEGORIES = {
        "latest": "Latest News",
        "world": "World",
        "us": "US",
        "business": "Business",
        "technology": "Technology",
        "entertainment": "Entertainment",
    }
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news from Yahoo Finance.
        
        Args:
            symbols: Stock symbols to fetch news for
            since: Only return articles after this time
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects
        """
        all_articles = []
        
        if symbols:
            # Fetch news for each symbol
            for symbol in symbols:
                try:
                    articles = await self._fetch_symbol_news(symbol, limit)
                    all_articles.extend(articles)
                except Exception as e:
                    logger.error(f"Failed to fetch Yahoo news for {symbol}: {e}")
        else:
            # Fetch general market news
            all_articles = await self._fetch_market_news(limit)
        
        # Filter by time if specified
        if since:
            all_articles = [a for a in all_articles if a.published_at >= since]
        
        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)
        
        self.articles_fetched += len(unique_articles[:limit])
        return unique_articles[:limit]
    
    async def _fetch_symbol_news(self, symbol: str, limit: int) -> List[NewsArticle]:
        """Fetch news for a specific symbol using the quote summary endpoint."""
        # Use the v8 quote endpoint which is more reliable and less rate-limited
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
        
        try:
            # First try to get news from the search endpoint
            search_url = f"{self.base_url}/v1/finance/search"
            params = {
                "q": symbol,
                "newsCount": str(min(limit, 20)),
                "quotesCount": "0",
            }
            
            # Add headers to mimic browser request
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            
            data = await self._make_request(search_url, params=params, headers=headers)
            news_items = data.get("news", [])
            
            articles = []
            for item in news_items:
                article = self._parse_article(item, symbol)
                if article:
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.warning(f"Yahoo Finance news fetch failed for {symbol}: {e}")
            # Try fallback to RSS feed
            return await self._fetch_symbol_news_rss(symbol, limit)
    
    async def _fetch_symbol_news_rss(self, symbol: str, limit: int) -> List[NewsArticle]:
        """Fallback: Fetch news from Yahoo Finance RSS feed."""
        import xml.etree.ElementTree as ET
        
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        
        try:
            session = await self._get_session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Yahoo RSS feed returned status {response.status}")
                    return []
                
                xml_content = await response.text()
                
            # Parse RSS XML
            root = ET.fromstring(xml_content)
            articles = []
            
            for item in root.findall(".//item")[:limit]:
                try:
                    title = item.find("title")
                    link = item.find("link")
                    pub_date = item.find("pubDate")
                    description = item.find("description")
                    
                    if title is None or link is None:
                        continue
                    
                    # Parse date
                    published_at = datetime.utcnow()
                    if pub_date is not None and pub_date.text:
                        try:
                            from email.utils import parsedate_to_datetime
                            published_at = parsedate_to_datetime(pub_date.text)
                        except Exception:
                            pass
                    
                    article = NewsArticle(
                        title=title.text or "",
                        summary=description.text if description is not None else "",
                        url=link.text or "",
                        source=self.source,
                        source_name="Yahoo Finance",
                        published_at=published_at,
                        symbols=[symbol],
                        categories=self._categorize_article(title.text or "", ""),
                    )
                    articles.append(article)
                except Exception as e:
                    logger.debug(f"Failed to parse Yahoo RSS item: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.warning(f"Yahoo Finance RSS fetch failed for {symbol}: {e}")
            return []
    
    async def _fetch_market_news(self, limit: int) -> List[NewsArticle]:
        """Fetch general market news."""
        # Use the v2 news endpoint
        url = "https://query2.finance.yahoo.com/v2/finance/news"
        params = {
            "category": "business",
            "count": min(limit, 100),
        }
        
        try:
            data = await self._make_request(url, params=params)
            items = data.get("Content", {}).get("result", [])
            
            articles = []
            for item in items:
                article = self._parse_v2_article(item)
                if article:
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.warning(f"Yahoo Finance market news fetch failed: {e}")
            return []
    
    def _parse_article(
        self,
        item: Dict[str, Any],
        symbol: Optional[str] = None,
    ) -> Optional[NewsArticle]:
        """Parse Yahoo Finance news item."""
        try:
            # Parse timestamp (Unix epoch)
            publish_time = item.get("providerPublishTime", 0)
            if publish_time:
                published_at = datetime.utcfromtimestamp(publish_time)
            else:
                published_at = datetime.utcnow()
            
            # Extract symbols from related tickers
            symbols = []
            if symbol:
                symbols.append(symbol)
            
            related = item.get("relatedTickers", [])
            for ticker in related:
                if ticker not in symbols:
                    symbols.append(ticker)
            
            title = item.get("title", "")
            
            # Categorize
            categories = self._categorize_article(title, "")
            
            return NewsArticle(
                title=title,
                summary=item.get("summary", ""),
                url=item.get("link", ""),
                source=self.source,
                source_name=item.get("publisher", "Yahoo Finance"),
                published_at=published_at,
                symbols=symbols,
                categories=categories,
                image_url=item.get("thumbnail", {}).get("resolutions", [{}])[0].get("url") if item.get("thumbnail") else None,
                metadata={
                    "yahoo_uuid": item.get("uuid"),
                    "type": item.get("type"),
                },
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Yahoo article: {e}")
            return None
    
    def _parse_v2_article(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """Parse Yahoo Finance v2 API news item."""
        try:
            content = item.get("content", {})
            
            # Parse timestamp
            publish_time = content.get("pubDate")
            if publish_time:
                published_at = datetime.fromisoformat(publish_time.replace("Z", "+00:00").replace("+00:00", ""))
            else:
                published_at = datetime.utcnow()
            
            # Extract tickers from finance metadata
            finance = content.get("finance", {})
            symbols = finance.get("stockTickers", [])
            if isinstance(symbols, list):
                symbols = [s.get("symbol", "") for s in symbols if isinstance(s, dict)]
            
            title = content.get("title", "")
            summary = content.get("summary", "")
            
            return NewsArticle(
                title=title,
                summary=summary,
                url=content.get("clickThroughUrl", {}).get("url", ""),
                source=self.source,
                source_name=content.get("provider", {}).get("displayName", "Yahoo Finance"),
                published_at=published_at,
                symbols=symbols,
                categories=self._categorize_article(title, summary),
                image_url=content.get("thumbnail", {}).get("url"),
                metadata={
                    "yahoo_id": content.get("id"),
                    "content_type": content.get("contentType"),
                },
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Yahoo v2 article: {e}")
            return None
    
    async def fetch_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current quote for a symbol using v8/finance/chart endpoint.
        
        Note: v7/finance/quote requires authentication (cookies/crumb).
        v8/finance/chart is still accessible without auth and provides price data.
        
        Returns:
            Dict with price, volume, change, etc.
        """
        # Use v8/finance/chart endpoint which doesn't require authentication
        url = f"{self.base_url}/v8/finance/chart/{symbol}"
        params = {
            "interval": "1d",
            "range": "1d",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        
        try:
            data = await self._make_request(url, params=params, headers=headers)
            chart = data.get("chart", {}).get("result", [])
            
            if chart:
                result = chart[0]
                meta = result.get("meta", {})
                quote = result.get("indicators", {}).get("quote", [{}])[0]
                
                # Get the most recent values
                close_prices = quote.get("close", [])
                open_prices = quote.get("open", [])
                high_prices = quote.get("high", [])
                low_prices = quote.get("low", [])
                volumes = quote.get("volume", [])
                
                # Get latest non-null values
                current_price = meta.get("regularMarketPrice")
                prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
                
                return {
                    "regularMarketPrice": current_price,
                    "regularMarketPreviousClose": prev_close,
                    "regularMarketOpen": open_prices[-1] if open_prices else None,
                    "regularMarketDayHigh": high_prices[-1] if high_prices else None,
                    "regularMarketDayLow": low_prices[-1] if low_prices else None,
                    "regularMarketVolume": volumes[-1] if volumes else None,
                    "regularMarketChange": (current_price - prev_close) if current_price and prev_close else None,
                    "regularMarketChangePercent": ((current_price - prev_close) / prev_close * 100) if current_price and prev_close else None,
                    "fiftyTwoWeekHigh": meta.get("fiftyTwoWeekHigh"),
                    "fiftyTwoWeekLow": meta.get("fiftyTwoWeekLow"),
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch Yahoo quote for {symbol}: {e}")
            return None
    
    async def fetch_historical(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical price data.
        
        Args:
            symbol: Stock symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo)
            
        Returns:
            List of OHLCV data points
        """
        url = f"{self.base_url}/v8/finance/chart/{symbol}"
        params = {
            "period1": "0",
            "period2": str(int(datetime.utcnow().timestamp())),
            "interval": interval,
            "range": period,
        }
        
        try:
            data = await self._make_request(url, params=params)
            chart = data.get("chart", {}).get("result", [{}])[0]
            
            timestamps = chart.get("timestamp", [])
            indicators = chart.get("indicators", {}).get("quote", [{}])[0]
            
            ohlcv = []
            for i, ts in enumerate(timestamps):
                ohlcv.append({
                    "timestamp": datetime.utcfromtimestamp(ts),
                    "open": indicators.get("open", [None])[i],
                    "high": indicators.get("high", [None])[i],
                    "low": indicators.get("low", [None])[i],
                    "close": indicators.get("close", [None])[i],
                    "volume": indicators.get("volume", [None])[i],
                })
            
            return ohlcv
            
        except Exception as e:
            logger.error(f"Failed to fetch Yahoo historical for {symbol}: {e}")
            return []

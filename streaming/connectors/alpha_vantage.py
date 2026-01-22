"""
Alpha Vantage News Connector
============================

Fetches market news and sentiment data from Alpha Vantage API.
Alpha Vantage provides news articles with pre-computed sentiment scores
and relevance rankings for each mentioned ticker.

API Documentation: https://www.alphavantage.co/documentation/#news-sentiment

Features:
- News articles with sentiment scores (-1 to 1)
- Ticker relevance scores (0 to 1)
- Topics classification (technology, finance, etc.)
- Up to 1000 articles per request

Rate Limits:
- Free tier: 5 requests/minute, 500 requests/day
- Premium: Higher limits based on plan

Required API Key: Get free key at https://www.alphavantage.co/support/#api-key
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class AlphaVantageConnector(BaseNewsConnector):
    """
    News connector for Alpha Vantage News & Sentiment API.
    
    Alpha Vantage is unique in providing pre-computed sentiment scores
    with each article, making it valuable for financial analysis.
    
    Example Usage:
        connector = AlphaVantageConnector(api_key="your_key")
        articles = await connector.fetch_news(
            symbols=["AAPL", "MSFT"],
            since=datetime.utcnow() - timedelta(hours=24),
            limit=50
        )
        
        for article in articles:
            print(f"{article.title}: sentiment={article.metadata['sentiment_score']}")
    """
    
    source = NewsSource.ALPHA_VANTAGE
    base_url = "https://www.alphavantage.co/query"
    rate_limit_per_minute = 5  # Free tier limit
    
    # Map Alpha Vantage topics to our categories
    TOPIC_CATEGORY_MAP = {
        "earnings": NewsCategory.EARNINGS,
        "mergers_and_acquisitions": NewsCategory.MERGER_ACQUISITION,
        "financial_markets": NewsCategory.MARKET,
        "economy_fiscal": NewsCategory.MACROECONOMIC,
        "economy_monetary": NewsCategory.MACROECONOMIC,
        "technology": NewsCategory.PRODUCT,
        "ipo": NewsCategory.GENERAL,
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[int] = None,
        timeout: int = 30,
    ):
        """
        Initialize the Alpha Vantage connector.
        
        Args:
            api_key: Alpha Vantage API key (or retrieved from Vault/ALPHA_VANTAGE_API_KEY env var)
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
            self.api_key = self._api_key_override or await get_api_key_from_vault('alpha_vantage')
            self._api_key_loaded = True
            if not self.api_key:
                logger.warning("No Alpha Vantage API key found in Vault or environment")
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news from Alpha Vantage News & Sentiment API.
        
        Args:
            symbols: Stock symbols to filter news for (e.g., ["AAPL", "GOOGL"])
            since: Only return articles published after this time
            limit: Maximum articles to return (API max is 1000)
            
        Returns:
            List of NewsArticle objects with sentiment metadata
        """
        # Load API key from Vault if not already loaded
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("Alpha Vantage API key is required")
        
        # Build query parameters
        params: Dict[str, Any] = {
            "function": "NEWS_SENTIMENT",
            "apikey": self.api_key,
            "limit": min(limit, 1000),  # API max is 1000
        }
        
        # Add ticker filter if symbols provided
        if symbols:
            # Alpha Vantage accepts comma-separated tickers
            params["tickers"] = ",".join(symbols)
        
        # Add time filter if since provided
        if since:
            # Alpha Vantage uses format: YYYYMMDDTHHMM
            params["time_from"] = since.strftime("%Y%m%dT%H%M")
        
        logger.info(f"Fetching Alpha Vantage news for symbols={symbols}, since={since}")
        
        try:
            data = await self._make_request(self.base_url, params=params)
            
            # Check for API errors
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                return []
            
            if "Note" in data:
                # Rate limit warning
                logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                return []
            
            # Parse articles from response
            feed = data.get("feed", [])
            articles = []
            
            for item in feed:
                article = self._parse_article(item)
                if article:
                    articles.append(article)
            
            self.articles_fetched += len(articles)
            logger.info(f"Fetched {len(articles)} articles from Alpha Vantage")
            
            return articles
            
        except Exception as e:
            logger.error(f"Failed to fetch Alpha Vantage news: {e}")
            raise
    
    def _parse_article(self, item: Dict[str, Any]) -> Optional[NewsArticle]:
        """
        Parse an Alpha Vantage news item into a NewsArticle.
        
        Alpha Vantage provides rich metadata including:
        - overall_sentiment_score: Float from -1 (bearish) to 1 (bullish)
        - overall_sentiment_label: Bearish/Somewhat-Bearish/Neutral/Somewhat-Bullish/Bullish
        - ticker_sentiment: Per-ticker sentiment and relevance scores
        - topics: List of topic classifications
        
        Args:
            item: Raw news item from API response
            
        Returns:
            NewsArticle with sentiment metadata, or None if parsing fails
        """
        try:
            # Parse publication time (format: YYYYMMDDTHHMMSS)
            time_published = item.get("time_published", "")
            if time_published:
                published_at = datetime.strptime(time_published, "%Y%m%dT%H%M%S")
            else:
                published_at = datetime.utcnow()
            
            # Extract symbols from ticker_sentiment
            symbols = []
            ticker_sentiments = {}
            for ticker_data in item.get("ticker_sentiment", []):
                ticker = ticker_data.get("ticker", "")
                if ticker:
                    symbols.append(ticker)
                    ticker_sentiments[ticker] = {
                        "relevance_score": float(ticker_data.get("relevance_score", 0)),
                        "sentiment_score": float(ticker_data.get("ticker_sentiment_score", 0)),
                        "sentiment_label": ticker_data.get("ticker_sentiment_label", ""),
                    }
            
            # Map topics to categories
            categories = []
            topics = item.get("topics", [])
            for topic in topics:
                topic_name = topic.get("topic", "").lower()
                if topic_name in self.TOPIC_CATEGORY_MAP:
                    categories.append(self.TOPIC_CATEGORY_MAP[topic_name])
            
            if not categories:
                categories = [NewsCategory.GENERAL]
            
            # Build metadata with sentiment information
            metadata = {
                "sentiment_score": float(item.get("overall_sentiment_score", 0)),
                "sentiment_label": item.get("overall_sentiment_label", "Neutral"),
                "ticker_sentiments": ticker_sentiments,
                "topics": [t.get("topic", "") for t in topics],
                "banner_image": item.get("banner_image", ""),
            }
            
            return NewsArticle(
                title=item.get("title", ""),
                summary=item.get("summary", ""),
                url=item.get("url", ""),
                source=self.source,
                source_name=item.get("source", "Alpha Vantage"),
                published_at=published_at,
                symbols=symbols,
                categories=categories,
                author=", ".join(item.get("authors", [])),
                image_url=item.get("banner_image"),
                metadata=metadata,
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Alpha Vantage article: {e}")
            return None
    
    async def fetch_news_for_topic(
        self,
        topic: str,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news filtered by topic instead of symbols.
        
        Available topics:
        - technology, blockchain, earnings, ipo, mergers_and_acquisitions
        - financial_markets, economy_fiscal, economy_monetary
        - economy_macro, energy_transportation, finance, life_sciences
        - manufacturing, real_estate, retail_wholesale
        
        Args:
            topic: Topic filter string
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects for the topic
        """
        if not self.api_key:
            raise ValueError("Alpha Vantage API key is required")
        
        params = {
            "function": "NEWS_SENTIMENT",
            "apikey": self.api_key,
            "topics": topic,
            "limit": min(limit, 1000),
        }
        
        data = await self._make_request(self.base_url, params=params)
        
        feed = data.get("feed", [])
        articles = [self._parse_article(item) for item in feed]
        
        return [a for a in articles if a is not None]

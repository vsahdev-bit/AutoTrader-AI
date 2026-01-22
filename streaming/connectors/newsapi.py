"""
NewsAPI.org Connector
=====================

Fetches news from NewsAPI.org, which aggregates articles from 80,000+ sources
including major financial news outlets like Bloomberg, CNBC, and Reuters.

API Documentation: https://newsapi.org/docs

Features:
- Aggregated news from thousands of sources
- Full-text search capabilities
- Source filtering (e.g., only Bloomberg, Reuters)
- Good for broad market coverage

Rate Limits:
- Free tier: 100 requests/day (developer plan)
- Paid plans: Higher limits

Limitations:
- Free tier has 1-month historical limit
- Free tier requires attribution

Required API Key: Get free key at https://newsapi.org/register
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import urllib.parse

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class NewsAPIConnector(BaseNewsConnector):
    """
    News connector for NewsAPI.org.
    
    NewsAPI aggregates news from thousands of sources, making it excellent
    for broad coverage. It supports full-text search which is useful for
    finding articles mentioning specific companies or topics.
    
    Example Usage:
        connector = NewsAPIConnector(api_key="your_key")
        
        # Search for company mentions
        articles = await connector.fetch_news(
            symbols=["AAPL", "Apple"],
            since=datetime.utcnow() - timedelta(days=7)
        )
        
        # Get top headlines from business sources
        headlines = await connector.fetch_top_headlines(category="business")
    """
    
    source = NewsSource.NEWSAPI
    base_url = "https://newsapi.org/v2"
    rate_limit_per_minute = 10  # Conservative limit for free tier
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[int] = None,
        timeout: int = 30,
    ):
        """
        Initialize the NewsAPI connector.
        
        Args:
            api_key: NewsAPI key (or retrieved from Vault/NEWSAPI_API_KEY env var)
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
            self.api_key = self._api_key_override or await get_api_key_from_vault('newsapi')
            self._api_key_loaded = True
            if not self.api_key:
                logger.warning("No NewsAPI API key found in Vault or environment")
    
    # Premium financial news sources to prioritize
    FINANCIAL_SOURCES = [
        "bloomberg",
        "reuters",
        "the-wall-street-journal",
        "financial-times",
        "cnbc",
        "business-insider",
        "fortune",
        "the-economist",
    ]
    
    # Company name to symbol mapping for better search
    COMPANY_NAMES = {
        "AAPL": ["Apple", "iPhone", "iPad", "Mac"],
        "GOOGL": ["Google", "Alphabet", "Android", "YouTube"],
        "MSFT": ["Microsoft", "Windows", "Azure", "Office"],
        "AMZN": ["Amazon", "AWS", "Prime"],
        "TSLA": ["Tesla", "Elon Musk", "SpaceX"],
        "META": ["Meta", "Facebook", "Instagram", "WhatsApp"],
        "NVDA": ["Nvidia", "GeForce", "CUDA"],
        "NFLX": ["Netflix"],
        "JPM": ["JPMorgan", "JP Morgan", "Chase"],
        "V": ["Visa"],
    }
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news articles matching stock symbols or company names.
        
        Uses NewsAPI's 'everything' endpoint with full-text search.
        Searches for both ticker symbols and company names for better coverage.
        
        Args:
            symbols: Stock symbols to search for
            since: Only return articles published after this time
            limit: Maximum articles to return (API max per request is 100)
            
        Returns:
            List of NewsArticle objects matching the search
        """
        # Load API key from Vault if not already loaded
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("NewsAPI API key is required")
        
        # If no symbols, fetch general business news
        if not symbols:
            return await self.fetch_top_headlines(category="business", limit=limit)
        
        # Build search query from symbols and company names
        search_terms = []
        for symbol in symbols:
            search_terms.append(symbol)
            # Add known company names for the symbol
            if symbol in self.COMPANY_NAMES:
                search_terms.extend(self.COMPANY_NAMES[symbol])
        
        # Join with OR for broader search
        query = " OR ".join(f'"{term}"' for term in search_terms)
        
        # Default time range: last 7 days (free tier limit is 1 month)
        if since is None:
            since = datetime.utcnow() - timedelta(days=7)
        
        params = {
            "q": query,
            "from": since.strftime("%Y-%m-%d"),
            "to": datetime.utcnow().strftime("%Y-%m-%d"),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(limit, 100),  # API max is 100
            "apiKey": self.api_key,
        }
        
        url = f"{self.base_url}/everything"
        
        logger.info(f"Fetching NewsAPI articles for symbols={symbols}")
        
        try:
            data = await self._make_request(url, params=params)
            
            # Check for API errors
            if data.get("status") != "ok":
                error_msg = data.get("message", "Unknown error")
                logger.error(f"NewsAPI error: {error_msg}")
                return []
            
            articles = []
            for item in data.get("articles", []):
                article = self._parse_article(item, target_symbols=symbols)
                if article:
                    articles.append(article)
            
            self.articles_fetched += len(articles)
            logger.info(f"Fetched {len(articles)} articles from NewsAPI")
            
            return articles
            
        except Exception as e:
            logger.error(f"Failed to fetch NewsAPI news: {e}")
            raise
    
    async def fetch_top_headlines(
        self,
        category: str = "business",
        country: str = "us",
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch top headlines from major news sources.
        
        Args:
            category: News category (business, technology, general, etc.)
            country: Two-letter country code for localized news
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects for top headlines
        """
        params = {
            "category": category,
            "country": country,
            "pageSize": min(limit, 100),
            "apiKey": self.api_key,
        }
        
        url = f"{self.base_url}/top-headlines"
        
        logger.info(f"Fetching NewsAPI top headlines for category={category}")
        
        data = await self._make_request(url, params=params)
        
        if data.get("status") != "ok":
            return []
        
        articles = []
        for item in data.get("articles", []):
            article = self._parse_article(item)
            if article:
                articles.append(article)
        
        self.articles_fetched += len(articles)
        return articles
    
    async def fetch_from_sources(
        self,
        sources: Optional[List[str]] = None,
        query: Optional[str] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news from specific sources (e.g., only Bloomberg and Reuters).
        
        Args:
            sources: List of source IDs (use FINANCIAL_SOURCES for financial news)
            query: Optional search query
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects from specified sources
        """
        if sources is None:
            sources = self.FINANCIAL_SOURCES
        
        params = {
            "sources": ",".join(sources),
            "pageSize": min(limit, 100),
            "apiKey": self.api_key,
        }
        
        if query:
            params["q"] = query
        
        url = f"{self.base_url}/everything"
        
        data = await self._make_request(url, params=params)
        
        if data.get("status") != "ok":
            return []
        
        articles = []
        for item in data.get("articles", []):
            article = self._parse_article(item)
            if article:
                articles.append(article)
        
        return articles
    
    def _parse_article(
        self,
        item: Dict[str, Any],
        target_symbols: Optional[List[str]] = None,
    ) -> Optional[NewsArticle]:
        """
        Parse a NewsAPI article into a NewsArticle.
        
        NewsAPI article format:
        {
            "source": {"id": "bloomberg", "name": "Bloomberg"},
            "author": "John Doe",
            "title": "Article title",
            "description": "Brief description",
            "url": "https://...",
            "urlToImage": "https://...",
            "publishedAt": "2024-01-15T10:30:00Z",
            "content": "Full article content (truncated in free tier)"
        }
        
        Args:
            item: Raw article from API response
            target_symbols: Symbols that were searched for
            
        Returns:
            NewsArticle or None if parsing fails
        """
        try:
            # Parse publication time (ISO format)
            published_str = item.get("publishedAt", "")
            if published_str:
                # Handle various ISO formats
                published_str = published_str.replace("Z", "+00:00")
                published_at = datetime.fromisoformat(published_str.replace("+00:00", ""))
            else:
                published_at = datetime.utcnow()
            
            # Extract source info
            source_info = item.get("source", {})
            source_name = source_info.get("name", "Unknown")
            
            # Get title and description
            title = item.get("title", "")
            description = item.get("description", "") or ""
            
            # Skip articles with "[Removed]" placeholder (NewsAPI returns these for restricted content)
            if title == "[Removed]" or description == "[Removed]":
                return None
            
            # Extract symbols from text
            symbols = []
            if target_symbols:
                # Check which target symbols are actually mentioned
                text = f"{title} {description}".upper()
                for symbol in target_symbols:
                    if symbol in text:
                        symbols.append(symbol)
                    # Also check company names
                    if symbol in self.COMPANY_NAMES:
                        for name in self.COMPANY_NAMES[symbol]:
                            if name.upper() in text:
                                if symbol not in symbols:
                                    symbols.append(symbol)
                                break
            
            # Categorize the article
            categories = self._categorize_article(title, description)
            
            return NewsArticle(
                title=title,
                summary=description,
                content=item.get("content"),
                url=item.get("url", ""),
                source=self.source,
                source_name=source_name,
                published_at=published_at,
                symbols=symbols,
                categories=categories,
                author=item.get("author"),
                image_url=item.get("urlToImage"),
                metadata={
                    "newsapi_source_id": source_info.get("id"),
                },
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse NewsAPI article: {e}")
            return None

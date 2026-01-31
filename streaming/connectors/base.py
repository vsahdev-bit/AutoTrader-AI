"""
Base News Connector
===================

This module defines the base class and data models for all news connectors
in the AutoTrader AI platform. All news source connectors inherit from
BaseNewsConnector and normalize their output to the NewsArticle format.

Design Principles:
- Async-first: All I/O operations are asynchronous
- Retry logic: Built-in exponential backoff for API failures
- Rate limiting: Respect API rate limits to avoid bans
- Normalization: All sources produce identical NewsArticle objects
- Vault integration: API keys retrieved from HashiCorp Vault with env fallback
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import hashlib
import logging
import asyncio
import os
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from yarl import URL

logger = logging.getLogger(__name__)


# ============== VAULT INTEGRATION ==============

async def get_api_key_from_vault(provider: str) -> Optional[str]:
    """
    Retrieve an API key from Vault with fallback to environment variables.
    
    This function attempts to get the API key from Vault first, and if that
    fails (Vault unavailable, key not found), falls back to environment variables.
    
    Args:
        provider: Provider name (e.g., 'polygon', 'iex_cloud', 'alpha_vantage')
        
    Returns:
        API key string, or None if not found in either location
    """
    # Map provider names to environment variable names
    env_var_map = {
        'polygon': 'POLYGON_API_KEY',
        'iex_cloud': 'IEX_CLOUD_API_KEY',
        'alpha_vantage': 'ALPHA_VANTAGE_API_KEY',
        'nasdaq_data_link': 'NASDAQ_DATA_LINK_API_KEY',
        'finnhub': 'FINNHUB_API_KEY',
        'newsapi': 'NEWSAPI_API_KEY',
        'benzinga': 'BENZINGA_API_KEY',
        'twitter': 'TWITTER_BEARER_TOKEN',
        'stocktwits': 'STOCKTWITS_ACCESS_TOKEN',
        'fmp': 'FMP_API_KEY',
        # LLM Providers (in fallback order)
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'groq': 'GROQ_API_KEY',
    }
    
    # Try to import and use vault client
    try:
        # Import here to avoid circular imports and make vault optional
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ml-services'))
        from vault_client import get_api_key
        
        api_key = await get_api_key(provider)
        if api_key:
            logger.debug(f"Retrieved {provider} API key from Vault")
            return api_key
    except ImportError:
        logger.debug(f"Vault client not available, falling back to environment variables")
    except Exception as e:
        logger.warning(f"Could not retrieve {provider} API key from Vault: {e}")
    
    # Fall back to environment variable
    env_var = env_var_map.get(provider, f"{provider.upper()}_API_KEY")
    api_key = os.getenv(env_var)
    if api_key:
        logger.debug(f"Using {provider} API key from environment variable {env_var}")
    else:
        # Also check for QUANDL_API_KEY as fallback for nasdaq_data_link
        if provider == 'nasdaq_data_link':
            api_key = os.getenv('QUANDL_API_KEY')
            if api_key:
                logger.debug(f"Using nasdaq_data_link API key from QUANDL_API_KEY env var")
    
    return api_key


class NewsSource(Enum):
    """
    Enumeration of supported news data sources.
    Used for tracking article provenance and source-specific processing.
    """
    ALPHA_VANTAGE = "alpha_vantage"
    FINNHUB = "finnhub"
    NEWSAPI = "newsapi"
    RSS_REUTERS = "rss_reuters"
    RSS_BLOOMBERG = "rss_bloomberg"
    RSS_YAHOO = "rss_yahoo"
    RSS_CNBC = "rss_cnbc"
    POLYGON = "polygon"
    IEX_CLOUD = "iex_cloud"
    NASDAQ_DATA_LINK = "nasdaq_data_link"
    UNKNOWN = "unknown"


class NewsCategory(Enum):
    """
    Categories for classifying news articles.
    Helps in filtering and weighting news for different use cases.
    """
    EARNINGS = "earnings"           # Earnings reports, revenue, profits
    MERGER_ACQUISITION = "m&a"      # Mergers, acquisitions, spinoffs
    REGULATORY = "regulatory"       # SEC filings, legal, compliance
    PRODUCT = "product"             # Product launches, recalls
    EXECUTIVE = "executive"         # Leadership changes, executive news
    ANALYST = "analyst"             # Analyst ratings, price targets
    MARKET = "market"               # General market news
    MACROECONOMIC = "macro"         # Economic indicators, fed policy
    SECTOR = "sector"               # Industry/sector-specific news
    GENERAL = "general"             # Uncategorized news


@dataclass
class NewsArticle:
    """
    Normalized news article representation.
    
    All news connectors transform their source-specific formats into this
    common structure for downstream processing.
    
    Attributes:
        article_id: Unique identifier (hash of URL + published_at)
        title: Article headline
        summary: Brief description or first paragraph
        content: Full article text (if available)
        url: Link to original article
        source: Which connector fetched this article
        source_name: Human-readable source name (e.g., "Reuters")
        published_at: When the article was published
        fetched_at: When we retrieved the article
        symbols: Stock symbols mentioned in the article
        categories: Classified news categories
        author: Article author (if available)
        image_url: Thumbnail or header image URL
        metadata: Source-specific additional data
        
    The article_id is computed as MD5(url + published_at) to enable
    deduplication across fetches and sources.
    """
    title: str
    summary: str
    url: str
    source: NewsSource
    source_name: str
    published_at: datetime
    symbols: List[str] = field(default_factory=list)
    content: Optional[str] = None
    categories: List[NewsCategory] = field(default_factory=list)
    author: Optional[str] = None
    image_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    article_id: str = field(default="")
    
    def __post_init__(self):
        """Generate article_id if not provided."""
        if not self.article_id:
            # Create deterministic ID from URL and publish time
            id_string = f"{self.url}:{self.published_at.isoformat()}"
            self.article_id = hashlib.md5(id_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "article_id": self.article_id,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "url": self.url,
            "source": self.source.value,
            "source_name": self.source_name,
            "published_at": self.published_at.isoformat(),
            "fetched_at": self.fetched_at.isoformat(),
            "symbols": self.symbols,
            "categories": [c.value for c in self.categories],
            "author": self.author,
            "image_url": self.image_url,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NewsArticle":
        """Create NewsArticle from dictionary."""
        return cls(
            article_id=data.get("article_id", ""),
            title=data["title"],
            summary=data["summary"],
            content=data.get("content"),
            url=data["url"],
            source=NewsSource(data["source"]),
            source_name=data["source_name"],
            published_at=datetime.fromisoformat(data["published_at"]),
            fetched_at=datetime.fromisoformat(data.get("fetched_at", datetime.utcnow().isoformat())),
            symbols=data.get("symbols", []),
            categories=[NewsCategory(c) for c in data.get("categories", [])],
            author=data.get("author"),
            image_url=data.get("image_url"),
            metadata=data.get("metadata", {}),
        )


class BaseNewsConnector(ABC):
    """
    Abstract base class for all news data source connectors.
    
    Each connector implementation must:
    1. Override fetch_news() to retrieve articles from the source
    2. Transform source-specific data into NewsArticle objects
    3. Handle rate limiting and API errors gracefully
    
    Built-in Features:
    - Async HTTP client with connection pooling
    - Exponential backoff retry logic
    - Rate limit tracking
    - Request logging and metrics
    
    Configuration:
    - api_key: Authentication key for the news API
    - rate_limit: Max requests per minute (default varies by source)
    - timeout: HTTP request timeout in seconds
    
    Example Implementation:
        class MyConnector(BaseNewsConnector):
            async def fetch_news(self, symbols, since):
                async with self._get_session() as session:
                    response = await session.get(self.base_url, params={...})
                    data = await response.json()
                    return [self._parse_article(item) for item in data]
    """
    
    # Subclasses should override these
    source: NewsSource = NewsSource.UNKNOWN
    base_url: str = ""
    rate_limit_per_minute: int = 60
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[int] = None,
        timeout: int = 30,
    ):
        """
        Initialize the news connector.
        
        Args:
            api_key: API authentication key (required for most sources)
            rate_limit: Override default rate limit (requests per minute)
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.rate_limit = rate_limit or self.rate_limit_per_minute
        
        # Rate limiting state
        self._request_times: List[datetime] = []
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Metrics
        self.total_requests = 0
        self.failed_requests = 0
        self.articles_fetched = 0
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create an aiohttp session with connection pooling.
        Reuses connections for better performance.
        """
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close the HTTP session and release resources."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _wait_for_rate_limit(self):
        """
        Enforce rate limiting by waiting if necessary.
        Uses a sliding window to track requests per minute.
        """
        now = datetime.utcnow()
        # Remove requests older than 1 minute
        self._request_times = [
            t for t in self._request_times 
            if (now - t).total_seconds() < 60
        ]
        
        # If at rate limit, wait until oldest request expires
        if len(self._request_times) >= self.rate_limit:
            oldest = self._request_times[0]
            wait_seconds = 60 - (now - oldest).total_seconds()
            if wait_seconds > 0:
                logger.debug(f"Rate limit reached, waiting {wait_seconds:.1f}s")
                await asyncio.sleep(wait_seconds)
        
        # Record this request
        self._request_times.append(datetime.utcnow())
    
    @staticmethod
    def _is_retryable_exception(exc: Exception) -> bool:
        """Return True if a request exception should be retried.

        We avoid retrying authentication/authorization failures (401/403) because
        those are not transient and retries just add latency and noise.
        """
        if isinstance(exc, aiohttp.ClientResponseError):
            return exc.status not in (401, 403)
        return True

    @staticmethod
    def _sanitize_url_for_logs(url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Return a URL safe for logs (redacts common credential query params)."""
        try:
            u = URL(url)
            if params:
                u = u.update_query(params)
            q = dict(u.query)
            for key in ("token", "apikey", "api_key", "key", "access_token", "bearer"):  # common patterns
                if key in q:
                    q[key] = "REDACTED"
            return str(u.with_query(q))
        except Exception:
            return url

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_retryable_exception),
        reraise=True,
    )
    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with retry logic and rate limiting.
        
        Args:
            url: Full URL or endpoint path
            method: HTTP method (GET, POST)
            params: Query parameters
            headers: HTTP headers
            
        Returns:
            Parsed JSON response as dictionary
            
        Raises:
            aiohttp.ClientError: On network errors after retries
            ValueError: On non-JSON response
        """
        await self._wait_for_rate_limit()
        
        session = await self._get_session()
        self.total_requests += 1
        
        safe_url = self._sanitize_url_for_logs(url, params)

        try:
            if method.upper() == "GET":
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status >= 400:
                        # Capture body for better diagnostics (do not assume JSON on errors)
                        body = (await response.text())[:2000]
                        logger.warning(
                            "HTTP %s from %s (connector=%s). Response body (truncated): %r",
                            response.status,
                            safe_url,
                            self.__class__.__name__,
                            body,
                        )
                        response.raise_for_status()
                    return await response.json()
            else:
                async with session.post(url, json=params, headers=headers) as response:
                    if response.status >= 400:
                        body = (await response.text())[:2000]
                        logger.warning(
                            "HTTP %s from %s (connector=%s). Response body (truncated): %r",
                            response.status,
                            safe_url,
                            self.__class__.__name__,
                            body,
                        )
                        response.raise_for_status()
                    return await response.json()

        except Exception as e:
            self.failed_requests += 1
            logger.error(
                "Request failed for %s: %s (url=%s)",
                self.__class__.__name__,
                e,
                safe_url,
            )
            raise
    
    @abstractmethod
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news articles from the data source.
        
        This method must be implemented by each connector to handle
        source-specific API calls and data transformation.
        
        Args:
            symbols: List of stock symbols to fetch news for.
                     If None, fetch general market news.
            since: Only fetch articles published after this time.
                   If None, use source's default (usually last 24h).
            limit: Maximum number of articles to return.
            
        Returns:
            List of NewsArticle objects normalized from source data.
            
        Raises:
            ConnectionError: If unable to reach the API
            ValueError: If API returns invalid data
            AuthenticationError: If API key is invalid
        """
        pass
    
    def _extract_symbols_from_text(self, text: str, known_symbols: List[str]) -> List[str]:
        """
        Extract stock symbols mentioned in article text.
        
        Uses pattern matching to find stock symbols (1-5 uppercase letters)
        and validates against a list of known symbols to reduce false positives.
        
        Args:
            text: Article title, summary, or content
            known_symbols: List of valid stock symbols to match against
            
        Returns:
            List of symbols found in the text
        """
        import re
        # Pattern for stock symbols: 1-5 uppercase letters, word boundaries
        pattern = r'\b([A-Z]{1,5})\b'
        potential_symbols = set(re.findall(pattern, text))
        
        # Filter to only known valid symbols
        known_set = set(known_symbols)
        return list(potential_symbols & known_set)
    
    def _categorize_article(self, title: str, summary: str) -> List[NewsCategory]:
        """
        Automatically categorize an article based on keywords.
        
        This is a simple rule-based categorization. For production use,
        consider using ML-based classification.
        
        Args:
            title: Article headline
            summary: Article summary or first paragraph
            
        Returns:
            List of applicable NewsCategory values
        """
        text = f"{title} {summary}".lower()
        categories = []
        
        # Keyword mappings for each category
        keyword_map = {
            NewsCategory.EARNINGS: ["earnings", "revenue", "profit", "eps", "quarterly", "annual report"],
            NewsCategory.MERGER_ACQUISITION: ["merger", "acquisition", "acquire", "buyout", "takeover", "spinoff"],
            NewsCategory.REGULATORY: ["sec", "regulatory", "compliance", "lawsuit", "legal", "investigation"],
            NewsCategory.PRODUCT: ["launch", "product", "release", "recall", "innovation"],
            NewsCategory.EXECUTIVE: ["ceo", "cfo", "executive", "leadership", "appointed", "resigned"],
            NewsCategory.ANALYST: ["analyst", "rating", "upgrade", "downgrade", "price target", "buy rating"],
            NewsCategory.MACROECONOMIC: ["fed", "interest rate", "inflation", "gdp", "unemployment", "economic"],
        }
        
        for category, keywords in keyword_map.items():
            if any(kw in text for kw in keywords):
                categories.append(category)
        
        # Default to GENERAL if no specific category matched
        if not categories:
            categories.append(NewsCategory.GENERAL)
            
        return categories
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get connector statistics for monitoring.
        
        Returns:
            Dictionary with request counts and success rates
        """
        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                (self.total_requests - self.failed_requests) / self.total_requests * 100
                if self.total_requests > 0 else 0
            ),
            "articles_fetched": self.articles_fetched,
        }

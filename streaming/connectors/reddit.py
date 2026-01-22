"""
Reddit Connector
================

Fetches posts and comments from Reddit's finance-related subreddits.
Reddit has become a significant source of retail investor sentiment,
especially after events like GameStop (GME) in 2021.

API Documentation: https://www.reddit.com/dev/api/

Features:
- Posts from r/wallstreetbets, r/stocks, r/investing, etc.
- Comment sentiment analysis
- Trending tickers detection
- Upvote/award tracking for engagement
- Real-time and historical data

Rate Limits:
- OAuth: 60 requests/minute
- Public: 30 requests/minute

Required: Reddit API credentials (client_id, client_secret)
Get credentials at: https://www.reddit.com/prefs/apps
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set
import logging
import re
import base64

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class RedditConnector(BaseNewsConnector):
    """
    Connector for Reddit API.
    
    Monitors finance-related subreddits for stock mentions and sentiment.
    Particularly useful for tracking retail investor sentiment and trending stocks.
    
    Example Usage:
        connector = RedditConnector(
            client_id="your_client_id",
            client_secret="your_client_secret"
        )
        
        # Fetch posts mentioning symbols
        posts = await connector.fetch_news(symbols=["GME", "AMC"])
        
        # Fetch from specific subreddits
        posts = await connector.fetch_subreddit_posts(
            subreddit="wallstreetbets",
            limit=50
        )
    """
    
    source = NewsSource.UNKNOWN
    base_url = "https://oauth.reddit.com"
    auth_url = "https://www.reddit.com/api/v1/access_token"
    rate_limit_per_minute = 60
    
    # Finance-related subreddits to monitor
    DEFAULT_SUBREDDITS = [
        "wallstreetbets",
        "stocks",
        "investing",
        "stockmarket",
        "options",
        "thetagang",
        "dividends",
        "SecurityAnalysis",
        "ValueInvesting",
    ]
    
    # Pattern to detect stock tickers (1-5 uppercase letters)
    TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b|\b([A-Z]{1,5})\b')
    
    # Common words to exclude from ticker detection
    EXCLUDED_WORDS = {
        "I", "A", "AT", "IT", "TO", "IS", "IN", "ON", "OR", "AN", "AS", "BE",
        "BY", "DO", "GO", "IF", "NO", "OF", "SO", "UP", "WE", "ALL", "AND",
        "ARE", "BUT", "CAN", "FOR", "GET", "GOT", "HAD", "HAS", "HER", "HIM",
        "HIS", "HOW", "ITS", "LET", "MAY", "NEW", "NOT", "NOW", "OLD", "OUR",
        "OUT", "OWN", "SAY", "SHE", "THE", "TOO", "TRY", "USE", "WAY", "WHO",
        "WHY", "YES", "YOU", "YOLO", "IMO", "IMHO", "DD", "TA", "FA", "PM",
        "AM", "CEO", "CFO", "IPO", "EPS", "ETF", "SEC", "FDA", "FED", "GDP",
        "USA", "UK", "EU", "USD", "EUR", "GBP", "EOD", "ATH", "ATL", "HODL",
    }
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: str = "AutoTrader AI Platform v1.0",
        subreddits: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize Reddit connector.
        
        Args:
            client_id: Reddit API client ID (or retrieved from Vault)
            client_secret: Reddit API client secret (or retrieved from Vault)
            user_agent: User agent string for API requests
            subreddits: List of subreddits to monitor
        """
        super().__init__(api_key=None, **kwargs)
        self._client_id_override = client_id
        self._client_secret_override = client_secret
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.subreddits = subreddits or self.DEFAULT_SUBREDDITS
        self.source_name = "Reddit"
        
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._credentials_loaded = client_id is not None and client_secret is not None
    
    # Connector is disabled until credentials are configured
    enabled = False
    
    async def _ensure_credentials(self):
        """Load Reddit credentials from Vault if not already loaded."""
        if not self._credentials_loaded:
            from .base import get_api_key_from_vault
            import os
            
            # Try to get credentials from Vault
            try:
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'ml-services'))
                from vault_client import get_vault_client
                
                client = await get_vault_client()
                secret = await client.get_secret('reddit')
                if secret:
                    self.client_id = self._client_id_override or secret.get('client_id')
                    self.client_secret = self._client_secret_override or secret.get('client_secret')
            except Exception as e:
                logger.debug(f"Could not load Reddit credentials from Vault: {e}")
            
            # Fall back to environment variables
            if not self.client_id:
                self.client_id = os.getenv('REDDIT_CLIENT_ID')
            if not self.client_secret:
                self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
            
            self._credentials_loaded = True
            
            if self.client_id and self.client_secret:
                self.__class__.enabled = True
            else:
                logger.info("Reddit connector is disabled - no credentials configured")
    
    async def _get_access_token(self) -> str:
        """Get or refresh OAuth access token."""
        # Ensure credentials are loaded from Vault
        await self._ensure_credentials()
        
        # Check if we have a valid token
        if self._access_token and self._token_expires:
            if datetime.utcnow() < self._token_expires:
                return self._access_token
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Reddit client_id and client_secret required")
        
        # Request new token
        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        session = await self._get_session()
        
        async with session.post(
            self.auth_url,
            headers={
                "Authorization": f"Basic {auth}",
                "User-Agent": self.user_agent,
            },
            data={
                "grant_type": "client_credentials",
            }
        ) as response:
            response.raise_for_status()
            data = await response.json()
            
            self._access_token = data["access_token"]
            self._token_expires = datetime.utcnow() + timedelta(
                seconds=data.get("expires_in", 3600) - 60
            )
            
            return self._access_token
    
    async def _make_reddit_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Reddit API."""
        token = await self._get_access_token()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.user_agent,
        }
        
        await self._wait_for_rate_limit()
        
        session = await self._get_session()
        self.total_requests += 1
        
        try:
            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            self.failed_requests += 1
            raise
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch Reddit posts as news articles.
        
        Args:
            symbols: Stock symbols to filter for
            since: Only return posts after this time
            limit: Maximum posts to return
            
        Returns:
            List of NewsArticle objects from Reddit posts
        """
        all_posts = []
        posts_per_sub = max(10, limit // len(self.subreddits))
        
        for subreddit in self.subreddits:
            try:
                posts = await self.fetch_subreddit_posts(
                    subreddit=subreddit,
                    limit=posts_per_sub,
                    since=since,
                )
                all_posts.extend(posts)
            except Exception as e:
                logger.error(f"Failed to fetch r/{subreddit}: {e}")
        
        # Filter by symbols if specified
        if symbols:
            symbols_set = set(s.upper() for s in symbols)
            filtered = []
            for post in all_posts:
                post_symbols = set(post.symbols)
                if post_symbols & symbols_set:
                    # Keep only relevant symbols
                    post.symbols = list(post_symbols & symbols_set)
                    filtered.append(post)
            all_posts = filtered
        
        # Sort by time (newest first)
        all_posts.sort(key=lambda p: p.published_at, reverse=True)
        
        self.articles_fetched += len(all_posts[:limit])
        return all_posts[:limit]
    
    async def fetch_subreddit_posts(
        self,
        subreddit: str,
        sort: str = "hot",
        limit: int = 50,
        since: Optional[datetime] = None,
    ) -> List[NewsArticle]:
        """
        Fetch posts from a specific subreddit.
        
        Args:
            subreddit: Subreddit name (without r/)
            sort: Sort order (hot, new, top, rising)
            limit: Maximum posts to return
            since: Only return posts after this time
            
        Returns:
            List of NewsArticle objects
        """
        endpoint = f"/r/{subreddit}/{sort}"
        params = {
            "limit": min(limit, 100),
            "raw_json": 1,
        }
        
        if sort == "top":
            params["t"] = "day"  # top of day
        
        data = await self._make_reddit_request(endpoint, params)
        
        posts = []
        for child in data.get("data", {}).get("children", []):
            post = self._parse_post(child.get("data", {}), subreddit)
            if post:
                # Filter by time
                if since and post.published_at < since:
                    continue
                posts.append(post)
        
        return posts
    
    def _parse_post(
        self,
        data: Dict[str, Any],
        subreddit: str,
    ) -> Optional[NewsArticle]:
        """Parse Reddit post into NewsArticle."""
        try:
            # Parse timestamp
            created = data.get("created_utc", 0)
            published_at = datetime.utcfromtimestamp(created) if created else datetime.utcnow()
            
            title = data.get("title", "")
            selftext = data.get("selftext", "")
            
            # Extract stock symbols from title and text
            symbols = self._extract_tickers(f"{title} {selftext}")
            
            # Calculate engagement score
            score = data.get("score", 0)
            num_comments = data.get("num_comments", 0)
            awards = data.get("total_awards_received", 0)
            
            # Build URL
            permalink = data.get("permalink", "")
            url = f"https://reddit.com{permalink}" if permalink else ""
            
            return NewsArticle(
                title=f"[r/{subreddit}] {title}",
                summary=selftext[:500] if selftext else "",
                content=selftext,
                url=url,
                source=self.source,
                source_name=f"Reddit r/{subreddit}",
                published_at=published_at,
                symbols=symbols,
                categories=[NewsCategory.GENERAL],
                author=data.get("author"),
                metadata={
                    "subreddit": subreddit,
                    "reddit_id": data.get("id"),
                    "score": score,
                    "upvote_ratio": data.get("upvote_ratio", 0),
                    "num_comments": num_comments,
                    "awards": awards,
                    "is_dd": self._is_dd_post(title, selftext, data.get("link_flair_text")),
                    "engagement_score": self._calculate_engagement(score, num_comments, awards),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to parse Reddit post: {e}")
            return None
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract stock tickers from text."""
        if not text:
            return []
        
        tickers = set()
        
        # Find explicit tickers with $ prefix
        for match in re.finditer(r'\$([A-Z]{1,5})\b', text):
            ticker = match.group(1)
            if ticker not in self.EXCLUDED_WORDS:
                tickers.add(ticker)
        
        # Find potential tickers (all caps, 1-5 letters)
        for match in re.finditer(r'\b([A-Z]{2,5})\b', text):
            ticker = match.group(1)
            if ticker not in self.EXCLUDED_WORDS:
                tickers.add(ticker)
        
        return list(tickers)
    
    def _is_dd_post(
        self,
        title: str,
        text: str,
        flair: Optional[str],
    ) -> bool:
        """Check if post is Due Diligence (DD)."""
        if flair and "dd" in flair.lower():
            return True
        
        dd_indicators = ["dd", "due diligence", "analysis", "research", "deep dive"]
        combined = f"{title} {text}".lower()
        
        return any(ind in combined for ind in dd_indicators)
    
    def _calculate_engagement(
        self,
        score: int,
        comments: int,
        awards: int,
    ) -> float:
        """Calculate normalized engagement score (0-1)."""
        # Weighted engagement calculation
        raw_score = score + (comments * 2) + (awards * 10)
        
        # Normalize using sigmoid-like function
        # Scores > 1000 approach 1.0
        return raw_score / (raw_score + 1000)
    
    async def fetch_trending_tickers(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Find trending stock tickers across monitored subreddits.
        
        Returns:
            List of tickers with mention counts and sentiment
        """
        ticker_data: Dict[str, Dict[str, Any]] = {}
        
        for subreddit in self.subreddits[:5]:  # Top 5 subreddits
            try:
                posts = await self.fetch_subreddit_posts(
                    subreddit=subreddit,
                    sort="hot",
                    limit=50,
                )
                
                for post in posts:
                    for symbol in post.symbols:
                        if symbol not in ticker_data:
                            ticker_data[symbol] = {
                                "symbol": symbol,
                                "mentions": 0,
                                "total_score": 0,
                                "total_comments": 0,
                                "posts": [],
                            }
                        
                        ticker_data[symbol]["mentions"] += 1
                        ticker_data[symbol]["total_score"] += post.metadata.get("score", 0)
                        ticker_data[symbol]["total_comments"] += post.metadata.get("num_comments", 0)
                        ticker_data[symbol]["posts"].append(post.url)
                        
            except Exception as e:
                logger.error(f"Failed to fetch trending from r/{subreddit}: {e}")
        
        # Sort by mentions and return top tickers
        trending = sorted(
            ticker_data.values(),
            key=lambda x: x["mentions"],
            reverse=True
        )[:limit]
        
        # Clean up posts list (keep only top 3)
        for t in trending:
            t["posts"] = t["posts"][:3]
        
        return trending

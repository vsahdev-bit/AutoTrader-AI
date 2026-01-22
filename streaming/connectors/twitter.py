"""
X (Twitter) Connector
=====================

Fetches tweets and sentiment from X (formerly Twitter) API.
X remains a critical source for real-time market sentiment,
breaking news, and executive/company announcements.

API Documentation: https://developer.twitter.com/en/docs

Features:
- Real-time tweet streaming
- Search by cashtag ($AAPL)
- Company/executive account monitoring
- Engagement metrics
- Verified account filtering

Rate Limits (v2 API):
- Basic: 10k tweets/month
- Pro: 1M tweets/month
- Enterprise: Custom

Required: X API Bearer Token
Get credentials at: https://developer.twitter.com/
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import re

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class TwitterConnector(BaseNewsConnector):
    """
    Connector for X (Twitter) API v2.
    
    Monitors financial tweets, cashtags, and key accounts for
    market sentiment and breaking news.
    
    Example Usage:
        connector = TwitterConnector(bearer_token="your_token")
        
        # Search for cashtag mentions
        tweets = await connector.fetch_news(symbols=["AAPL", "TSLA"])
        
        # Search with custom query
        tweets = await connector.search_tweets(
            query="$AAPL earnings",
            limit=100
        )
    """
    
    source = NewsSource.UNKNOWN
    base_url = "https://api.twitter.com/2"
    rate_limit_per_minute = 60
    
    # Influential financial accounts to monitor
    INFLUENTIAL_ACCOUNTS = [
        "jimcramer",
        "Carl_C_Icahn", 
        "WarrenBuffett",
        "elikiara",
        "chaaborsen",
        "zaborsen",
        "DeItaone",  # Walter Bloomberg
        "FirstSquawk",
        "LiveSquawk",
        "Stocktwits",
    ]
    
    def __init__(
        self,
        bearer_token: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Twitter connector.
        
        Args:
            bearer_token: X API v2 bearer token (or retrieved from Vault/TWITTER_BEARER_TOKEN env var)
        """
        super().__init__(api_key=bearer_token, **kwargs)
        self._bearer_token_override = bearer_token
        self.bearer_token = bearer_token
        self.source_name = "X (Twitter)"
        self._token_loaded = bearer_token is not None
    
    # Connector is disabled until API key is configured
    enabled = False
    
    async def _ensure_bearer_token(self):
        """Load bearer token from Vault if not already loaded."""
        if not self._token_loaded:
            from .base import get_api_key_from_vault
            import os
            
            token = await get_api_key_from_vault('twitter')
            if not token:
                token = os.getenv('TWITTER_BEARER_TOKEN')
            
            self.bearer_token = self._bearer_token_override or token
            self.api_key = self.bearer_token
            self._token_loaded = True
            
            if self.bearer_token:
                self.__class__.enabled = True
            else:
                logger.info("Twitter connector is disabled - no bearer token configured")
    
    async def _make_twitter_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Twitter API."""
        # Load bearer token from Vault if not already loaded
        await self._ensure_bearer_token()
        
        if not self.bearer_token:
            raise ValueError("Twitter bearer token required")
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
        }
        
        await self._wait_for_rate_limit()
        
        session = await self._get_session()
        self.total_requests += 1
        
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 429:
                    # Rate limited
                    logger.warning("Twitter rate limit reached")
                    return {"data": [], "meta": {"result_count": 0}}
                
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
        Fetch tweets as news articles.
        
        Args:
            symbols: Stock symbols to search for (as cashtags)
            since: Only return tweets after this time
            limit: Maximum tweets to return
            
        Returns:
            List of NewsArticle objects from tweets
        """
        if not symbols:
            # Fetch from influential accounts
            return await self._fetch_from_accounts(limit, since)
        
        # Build cashtag query
        cashtags = [f"${s}" for s in symbols]
        query = " OR ".join(cashtags)
        
        return await self.search_tweets(query, limit, since)
    
    async def search_tweets(
        self,
        query: str,
        limit: int = 50,
        since: Optional[datetime] = None,
    ) -> List[NewsArticle]:
        """
        Search for tweets matching a query.
        
        Args:
            query: Search query (supports cashtags, keywords, operators)
            limit: Maximum tweets to return
            since: Only return tweets after this time
            
        Returns:
            List of NewsArticle objects
        """
        if not self.bearer_token:
            raise ValueError("Twitter bearer token required")
        
        endpoint = "/tweets/search/recent"
        
        # Build query with filters
        full_query = f"{query} -is:retweet lang:en"
        
        params = {
            "query": full_query,
            "max_results": min(limit, 100),
            "tweet.fields": "created_at,author_id,public_metrics,entities,context_annotations",
            "user.fields": "name,username,verified,public_metrics",
            "expansions": "author_id",
        }
        
        if since:
            params["start_time"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        try:
            data = await self._make_twitter_request(endpoint, params)
            
            # Build user lookup
            users = {}
            for user in data.get("includes", {}).get("users", []):
                users[user["id"]] = user
            
            tweets = []
            for tweet in data.get("data", []):
                article = self._parse_tweet(tweet, users)
                if article:
                    tweets.append(article)
            
            self.articles_fetched += len(tweets)
            return tweets
            
        except Exception as e:
            logger.error(f"Twitter search failed: {e}")
            return []
    
    async def _fetch_from_accounts(
        self,
        limit: int,
        since: Optional[datetime] = None,
    ) -> List[NewsArticle]:
        """Fetch tweets from influential financial accounts."""
        all_tweets = []
        tweets_per_account = max(5, limit // len(self.INFLUENTIAL_ACCOUNTS))
        
        for account in self.INFLUENTIAL_ACCOUNTS[:10]:
            try:
                tweets = await self._fetch_user_tweets(
                    username=account,
                    limit=tweets_per_account,
                    since=since,
                )
                all_tweets.extend(tweets)
            except Exception as e:
                logger.warning(f"Failed to fetch @{account}: {e}")
        
        # Sort by time
        all_tweets.sort(key=lambda t: t.published_at, reverse=True)
        return all_tweets[:limit]
    
    async def _fetch_user_tweets(
        self,
        username: str,
        limit: int = 10,
        since: Optional[datetime] = None,
    ) -> List[NewsArticle]:
        """Fetch tweets from a specific user."""
        # First get user ID
        user_endpoint = f"/users/by/username/{username}"
        user_params = {"user.fields": "name,username,verified,public_metrics"}
        
        user_data = await self._make_twitter_request(user_endpoint, user_params)
        user = user_data.get("data")
        
        if not user:
            return []
        
        user_id = user["id"]
        
        # Fetch tweets
        tweets_endpoint = f"/users/{user_id}/tweets"
        params = {
            "max_results": min(limit, 100),
            "tweet.fields": "created_at,public_metrics,entities",
            "exclude": "retweets,replies",
        }
        
        if since:
            params["start_time"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        data = await self._make_twitter_request(tweets_endpoint, params)
        
        tweets = []
        users = {user_id: user}
        
        for tweet in data.get("data", []):
            article = self._parse_tweet(tweet, users)
            if article:
                tweets.append(article)
        
        return tweets
    
    def _parse_tweet(
        self,
        tweet: Dict[str, Any],
        users: Dict[str, Dict[str, Any]],
    ) -> Optional[NewsArticle]:
        """Parse tweet into NewsArticle."""
        try:
            # Parse timestamp
            created = tweet.get("created_at", "")
            if created:
                published_at = datetime.fromisoformat(created.replace("Z", "+00:00").replace("+00:00", ""))
            else:
                published_at = datetime.utcnow()
            
            text = tweet.get("text", "")
            
            # Extract cashtags
            symbols = []
            entities = tweet.get("entities", {})
            for cashtag in entities.get("cashtags", []):
                symbols.append(cashtag.get("tag", "").upper())
            
            # Get author info
            author_id = tweet.get("author_id", "")
            author = users.get(author_id, {})
            author_name = author.get("name", "")
            author_username = author.get("username", "")
            is_verified = author.get("verified", False)
            
            # Get metrics
            metrics = tweet.get("public_metrics", {})
            likes = metrics.get("like_count", 0)
            retweets = metrics.get("retweet_count", 0)
            replies = metrics.get("reply_count", 0)
            
            # Build URL
            tweet_id = tweet.get("id", "")
            url = f"https://twitter.com/{author_username}/status/{tweet_id}" if author_username and tweet_id else ""
            
            return NewsArticle(
                title=f"@{author_username}: {text[:100]}{'...' if len(text) > 100 else ''}",
                summary=text,
                content=text,
                url=url,
                source=self.source,
                source_name="X (Twitter)",
                published_at=published_at,
                symbols=symbols,
                categories=[NewsCategory.GENERAL],
                author=author_name or author_username,
                metadata={
                    "tweet_id": tweet_id,
                    "author_id": author_id,
                    "author_username": author_username,
                    "is_verified": is_verified,
                    "likes": likes,
                    "retweets": retweets,
                    "replies": replies,
                    "engagement_score": self._calculate_engagement(likes, retweets, replies),
                    "author_followers": author.get("public_metrics", {}).get("followers_count", 0),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to parse tweet: {e}")
            return None
    
    def _calculate_engagement(
        self,
        likes: int,
        retweets: int,
        replies: int,
    ) -> float:
        """Calculate normalized engagement score."""
        raw_score = likes + (retweets * 2) + (replies * 1.5)
        return raw_score / (raw_score + 500)
    
    async def get_trending_cashtags(self) -> List[Dict[str, Any]]:
        """
        Get trending cashtags (requires elevated access).
        
        Note: This requires Twitter API v2 elevated access.
        """
        # Trending topics requires elevated access
        # For basic tier, we can search and aggregate
        logger.warning("Trending cashtags requires elevated Twitter API access")
        return []

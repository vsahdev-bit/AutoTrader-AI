"""
StockTwits Connector
====================

Fetches messages and sentiment from StockTwits, a social network
specifically designed for traders and investors.

API Documentation: https://api.stocktwits.com/developers

Features:
- Real-time stock-specific messages
- User sentiment labels (Bullish/Bearish)
- Trending symbols
- Watchlist tracking
- No API key required for basic access

Rate Limits:
- Unauthenticated: 200 requests/hour
- Authenticated: 400 requests/hour

Note: StockTwits is valuable because users explicitly label
their sentiment (Bullish/Bearish), making sentiment analysis easier.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class StockTwitsConnector(BaseNewsConnector):
    """
    Connector for StockTwits API.
    
    StockTwits provides pre-labeled sentiment data from retail investors,
    making it particularly valuable for sentiment analysis.
    
    Example Usage:
        connector = StockTwitsConnector()
        
        # Fetch messages for a symbol
        messages = await connector.fetch_news(symbols=["AAPL"])
        
        # Get trending symbols
        trending = await connector.get_trending()
        
        # Get sentiment breakdown
        sentiment = await connector.get_symbol_sentiment("AAPL")
    """
    
    source = NewsSource.UNKNOWN
    base_url = "https://api.stocktwits.com/api/2"
    rate_limit_per_minute = 3  # ~200/hour = 3.3/min
    
    def __init__(
        self,
        access_token: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize StockTwits connector.
        
        Args:
            access_token: Optional OAuth token for higher rate limits (from Vault/STOCKTWITS_ACCESS_TOKEN env var)
        """
        self._access_token_override = access_token
        self._token_loaded = access_token is not None
        super().__init__(api_key=access_token, **kwargs)
        self.access_token = access_token
        self.source_name = "StockTwits"
    
    async def _ensure_access_token(self):
        """Load access token from Vault if not already loaded (optional for StockTwits)."""
        if not self._token_loaded:
            from .base import get_api_key_from_vault
            import os
            
            token = await get_api_key_from_vault('stocktwits')
            if not token:
                token = os.getenv('STOCKTWITS_ACCESS_TOKEN')
            
            if token:
                self.access_token = self._access_token_override or token
                self.api_key = self.access_token
            
            self._token_loaded = True
            # Note: StockTwits works without auth, so no warning needed
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch StockTwits messages as news articles.
        
        Args:
            symbols: Stock symbols to fetch messages for
            since: Only return messages after this time
            limit: Maximum messages to return
            
        Returns:
            List of NewsArticle objects from StockTwits
        """
        all_messages = []
        
        if symbols:
            messages_per_symbol = max(10, limit // len(symbols))
            
            for symbol in symbols:
                try:
                    messages = await self.fetch_symbol_stream(
                        symbol=symbol,
                        limit=messages_per_symbol,
                    )
                    all_messages.extend(messages)
                except Exception as e:
                    logger.error(f"Failed to fetch StockTwits for {symbol}: {e}")
        else:
            # Fetch trending stream
            all_messages = await self._fetch_trending_stream(limit)
        
        # Filter by time
        if since:
            all_messages = [m for m in all_messages if m.published_at >= since]
        
        # Sort by time
        all_messages.sort(key=lambda m: m.published_at, reverse=True)
        
        self.articles_fetched += len(all_messages[:limit])
        return all_messages[:limit]
    
    async def fetch_symbol_stream(
        self,
        symbol: str,
        limit: int = 30,
    ) -> List[NewsArticle]:
        """
        Fetch message stream for a specific symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            limit: Maximum messages to return (max 30 per request)
            
        Returns:
            List of NewsArticle objects
        """
        endpoint = f"/streams/symbol/{symbol}.json"
        params = {"limit": min(limit, 30)}
        
        if self.access_token:
            params["access_token"] = self.access_token
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            data = await self._make_request(url, params=params)
            
            if data.get("response", {}).get("status") != 200:
                logger.warning(f"StockTwits API error for {symbol}")
                return []
            
            messages = []
            symbol_info = data.get("symbol", {})
            
            for msg in data.get("messages", []):
                article = self._parse_message(msg, symbol, symbol_info)
                if article:
                    messages.append(article)
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to fetch StockTwits stream for {symbol}: {e}")
            return []
    
    async def _fetch_trending_stream(self, limit: int) -> List[NewsArticle]:
        """Fetch trending/popular messages."""
        endpoint = "/streams/trending.json"
        params = {"limit": min(limit, 30)}
        
        if self.access_token:
            params["access_token"] = self.access_token
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            data = await self._make_request(url, params=params)
            
            messages = []
            for msg in data.get("messages", []):
                # Extract symbol from message
                symbols = [s.get("symbol", "") for s in msg.get("symbols", [])]
                symbol = symbols[0] if symbols else ""
                
                article = self._parse_message(msg, symbol, {})
                if article:
                    messages.append(article)
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to fetch StockTwits trending: {e}")
            return []
    
    def _parse_message(
        self,
        msg: Dict[str, Any],
        symbol: str,
        symbol_info: Dict[str, Any],
    ) -> Optional[NewsArticle]:
        """Parse StockTwits message into NewsArticle."""
        try:
            # Parse timestamp
            created = msg.get("created_at", "")
            if created:
                # StockTwits format: "2024-01-15T10:30:00Z"
                published_at = datetime.fromisoformat(created.replace("Z", "+00:00").replace("+00:00", ""))
            else:
                published_at = datetime.utcnow()
            
            body = msg.get("body", "")
            
            # Extract symbols from message
            symbols = [s.get("symbol", "") for s in msg.get("symbols", [])]
            if symbol and symbol not in symbols:
                symbols.insert(0, symbol)
            
            # Get user sentiment (Bullish/Bearish)
            entities = msg.get("entities", {})
            sentiment = entities.get("sentiment", {})
            user_sentiment = sentiment.get("basic")  # "Bullish" or "Bearish"
            
            # Convert to score
            sentiment_score = 0.0
            if user_sentiment == "Bullish":
                sentiment_score = 0.5
            elif user_sentiment == "Bearish":
                sentiment_score = -0.5
            
            # Get user info
            user = msg.get("user", {})
            username = user.get("username", "")
            followers = user.get("followers", 0)
            
            # Get likes count
            likes = msg.get("likes", {}).get("total", 0)
            
            return NewsArticle(
                title=f"${symbol}: {body[:80]}{'...' if len(body) > 80 else ''}",
                summary=body,
                content=body,
                url=f"https://stocktwits.com/{username}/message/{msg.get('id', '')}",
                source=self.source,
                source_name="StockTwits",
                published_at=published_at,
                symbols=symbols,
                categories=[NewsCategory.GENERAL],
                author=username,
                metadata={
                    "stocktwits_id": msg.get("id"),
                    "user_sentiment": user_sentiment,
                    "sentiment_score": sentiment_score,
                    "likes": likes,
                    "user_followers": followers,
                    "user_ideas": user.get("ideas", 0),
                    "is_official": user.get("official", False),
                    "symbol_watchlist_count": symbol_info.get("watchlist_count", 0),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to parse StockTwits message: {e}")
            return None
    
    async def get_trending(self) -> List[Dict[str, Any]]:
        """
        Get trending symbols on StockTwits.
        
        Returns:
            List of trending symbol info
        """
        endpoint = "/trending/symbols.json"
        params = {}
        
        if self.access_token:
            params["access_token"] = self.access_token
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            data = await self._make_request(url, params=params)
            
            trending = []
            for symbol in data.get("symbols", []):
                trending.append({
                    "symbol": symbol.get("symbol"),
                    "title": symbol.get("title"),
                    "watchlist_count": symbol.get("watchlist_count", 0),
                })
            
            return trending
            
        except Exception as e:
            logger.error(f"Failed to fetch StockTwits trending: {e}")
            return []
    
    async def get_symbol_sentiment(self, symbol: str) -> Dict[str, Any]:
        """
        Get aggregated sentiment for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with sentiment breakdown and metrics
        """
        messages = await self.fetch_symbol_stream(symbol, limit=30)
        
        if not messages:
            return {
                "symbol": symbol,
                "message_count": 0,
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0,
                "sentiment_ratio": 0.5,
            }
        
        bullish = 0
        bearish = 0
        neutral = 0
        
        for msg in messages:
            sentiment = msg.metadata.get("user_sentiment")
            if sentiment == "Bullish":
                bullish += 1
            elif sentiment == "Bearish":
                bearish += 1
            else:
                neutral += 1
        
        total_labeled = bullish + bearish
        sentiment_ratio = bullish / total_labeled if total_labeled > 0 else 0.5
        
        return {
            "symbol": symbol,
            "message_count": len(messages),
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
            "sentiment_ratio": round(sentiment_ratio, 3),
            "sentiment_score": round((sentiment_ratio - 0.5) * 2, 3),  # -1 to 1
        }

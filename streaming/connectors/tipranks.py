"""
TipRanks Connector
==================

Fetches analyst ratings, price targets, and insider trading data
from TipRanks, a platform that tracks and ranks financial analysts.

Features:
- Analyst ratings and price targets
- Analyst performance tracking
- Insider trading signals
- Hedge fund activity
- News sentiment scores
- Blogger opinions

Note: TipRanks doesn't have a public API. This connector uses
their public-facing endpoints. For production use, consider
their official data licensing program.

Rate Limits:
- No official API, be respectful with request frequency
- Recommended: 10 requests/minute max
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class TipRanksConnector(BaseNewsConnector):
    """
    Connector for TipRanks data.
    
    TipRanks is valuable for analyst consensus, price targets,
    and tracking analyst/insider activity.
    
    Example Usage:
        connector = TipRanksConnector()
        
        # Get analyst ratings as news
        articles = await connector.fetch_news(symbols=["AAPL"])
        
        # Get detailed analyst data
        data = await connector.get_analyst_data("AAPL")
        
        # Get price targets
        targets = await connector.get_price_targets("AAPL")
    """
    
    source = NewsSource.UNKNOWN
    base_url = "https://www.tipranks.com/api"
    rate_limit_per_minute = 10
    
    def __init__(self, **kwargs):
        super().__init__(api_key=None, **kwargs)
        self.source_name = "TipRanks"
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch analyst ratings and news as NewsArticle objects.
        
        Converts analyst ratings, price target changes, and other
        TipRanks data into news-like format for unified processing.
        
        Args:
            symbols: Stock symbols to fetch data for
            since: Only return articles after this time
            limit: Maximum articles to return
            
        Returns:
            List of NewsArticle objects
        """
        all_articles = []
        
        if not symbols:
            logger.warning("TipRanks requires specific symbols")
            return []
        
        for symbol in symbols:
            try:
                # Get analyst ratings as articles
                ratings = await self._fetch_analyst_ratings(symbol)
                all_articles.extend(ratings)
                
                # Get news sentiment
                news = await self._fetch_news_sentiment(symbol)
                all_articles.extend(news)
                
            except Exception as e:
                logger.error(f"Failed to fetch TipRanks data for {symbol}: {e}")
        
        # Filter by time
        if since:
            all_articles = [a for a in all_articles if a.published_at >= since]
        
        # Sort and limit
        all_articles.sort(key=lambda a: a.published_at, reverse=True)
        
        self.articles_fetched += len(all_articles[:limit])
        return all_articles[:limit]
    
    async def _fetch_analyst_ratings(self, symbol: str) -> List[NewsArticle]:
        """Fetch recent analyst ratings for a symbol."""
        url = f"{self.base_url}/stocks/getNewsSentiments/"
        params = {"ticker": symbol}
        
        try:
            # Note: This endpoint may require different parameters
            # The actual TipRanks API structure may vary
            data = await self._make_request(url, params=params)
            
            articles = []
            
            # Parse analyst ratings
            for rating in data.get("analystRatings", []):
                article = self._parse_rating(rating, symbol)
                if article:
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.warning(f"TipRanks ratings fetch failed for {symbol}: {e}")
            return []
    
    async def _fetch_news_sentiment(self, symbol: str) -> List[NewsArticle]:
        """Fetch news with TipRanks sentiment scores."""
        url = f"{self.base_url}/stocks/getNews/"
        params = {"ticker": symbol}
        
        try:
            data = await self._make_request(url, params=params)
            
            articles = []
            for item in data.get("news", [])[:10]:
                article = self._parse_news_item(item, symbol)
                if article:
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.warning(f"TipRanks news fetch failed for {symbol}: {e}")
            return []
    
    def _parse_rating(
        self,
        rating: Dict[str, Any],
        symbol: str,
    ) -> Optional[NewsArticle]:
        """Parse analyst rating into NewsArticle."""
        try:
            # Parse date
            date_str = rating.get("date", "")
            if date_str:
                published_at = datetime.fromisoformat(date_str.replace("Z", ""))
            else:
                published_at = datetime.utcnow()
            
            analyst = rating.get("analystName", "Unknown Analyst")
            firm = rating.get("firm", "Unknown Firm")
            action = rating.get("ratingAction", "")  # upgrade, downgrade, etc.
            rating_val = rating.get("rating", "")  # Buy, Hold, Sell
            price_target = rating.get("priceTarget")
            
            # Build descriptive title
            if action and rating_val:
                title = f"{firm}: {analyst} {action}s {symbol} to {rating_val}"
            else:
                title = f"{firm}: {analyst} rates {symbol} as {rating_val}"
            
            if price_target:
                title += f" with ${price_target} target"
            
            # Build summary
            summary = f"Analyst {analyst} from {firm} "
            if action:
                summary += f"{action}d {symbol} "
            summary += f"to {rating_val}."
            if price_target:
                summary += f" Price target: ${price_target}."
            
            return NewsArticle(
                title=title,
                summary=summary,
                url=f"https://www.tipranks.com/stocks/{symbol.lower()}/forecast",
                source=self.source,
                source_name="TipRanks",
                published_at=published_at,
                symbols=[symbol],
                categories=[NewsCategory.ANALYST],
                author=analyst,
                metadata={
                    "analyst_name": analyst,
                    "firm": firm,
                    "rating": rating_val,
                    "action": action,
                    "price_target": price_target,
                    "analyst_rank": rating.get("analystRank"),
                    "success_rate": rating.get("successRate"),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to parse TipRanks rating: {e}")
            return None
    
    def _parse_news_item(
        self,
        item: Dict[str, Any],
        symbol: str,
    ) -> Optional[NewsArticle]:
        """Parse TipRanks news item."""
        try:
            date_str = item.get("publishedDate", "")
            if date_str:
                published_at = datetime.fromisoformat(date_str.replace("Z", ""))
            else:
                published_at = datetime.utcnow()
            
            title = item.get("title", "")
            
            # TipRanks provides sentiment
            sentiment = item.get("sentiment")
            sentiment_score = 0.0
            if sentiment == "bullish":
                sentiment_score = 0.5
            elif sentiment == "bearish":
                sentiment_score = -0.5
            
            return NewsArticle(
                title=title,
                summary=item.get("description", ""),
                url=item.get("url", ""),
                source=self.source,
                source_name=item.get("site", "TipRanks"),
                published_at=published_at,
                symbols=[symbol],
                categories=[NewsCategory.GENERAL],
                metadata={
                    "tipranks_sentiment": sentiment,
                    "sentiment_score": sentiment_score,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to parse TipRanks news: {e}")
            return None
    
    async def get_analyst_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get comprehensive analyst data for a symbol.
        
        Returns:
            Dict with consensus rating, price targets, analyst breakdown
        """
        url = f"{self.base_url}/stocks/getData/"
        params = {"name": symbol}
        
        try:
            data = await self._make_request(url, params=params)
            
            return {
                "symbol": symbol,
                "consensus_rating": data.get("consensusRating"),
                "price_target": data.get("priceTarget"),
                "price_target_high": data.get("priceTargetHigh"),
                "price_target_low": data.get("priceTargetLow"),
                "num_analysts": data.get("numOfAnalysts"),
                "buy_count": data.get("buy", 0),
                "hold_count": data.get("hold", 0),
                "sell_count": data.get("sell", 0),
                "analyst_consensus": data.get("analystConsensus"),
            }
        except Exception as e:
            logger.error(f"Failed to get TipRanks analyst data: {e}")
            return {"symbol": symbol, "error": str(e)}
    
    async def get_price_targets(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get recent price target changes.
        
        Returns:
            List of price target updates
        """
        url = f"{self.base_url}/stocks/getPriceTargets/"
        params = {"ticker": symbol}
        
        try:
            data = await self._make_request(url, params=params)
            
            targets = []
            for pt in data.get("priceTargets", [])[:20]:
                targets.append({
                    "analyst": pt.get("analystName"),
                    "firm": pt.get("firm"),
                    "date": pt.get("date"),
                    "price_target": pt.get("priceTarget"),
                    "previous_target": pt.get("previousPriceTarget"),
                    "rating": pt.get("rating"),
                })
            
            return targets
        except Exception as e:
            logger.error(f"Failed to get TipRanks price targets: {e}")
            return []
    
    async def get_insider_trades(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get recent insider trading activity.
        
        Returns:
            List of insider transactions
        """
        url = f"{self.base_url}/stocks/getInsiders/"
        params = {"ticker": symbol}
        
        try:
            data = await self._make_request(url, params=params)
            
            trades = []
            for trade in data.get("insiders", [])[:20]:
                trades.append({
                    "insider": trade.get("name"),
                    "title": trade.get("title"),
                    "transaction_type": trade.get("transactionType"),
                    "shares": trade.get("shares"),
                    "value": trade.get("value"),
                    "date": trade.get("date"),
                })
            
            return trades
        except Exception as e:
            logger.error(f"Failed to get TipRanks insider trades: {e}")
            return []
    
    async def get_hedge_fund_activity(self, symbol: str) -> Dict[str, Any]:
        """
        Get hedge fund holdings and activity.
        
        Returns:
            Dict with hedge fund sentiment and holdings changes
        """
        url = f"{self.base_url}/stocks/getHedgeFunds/"
        params = {"ticker": symbol}
        
        try:
            data = await self._make_request(url, params=params)
            
            return {
                "symbol": symbol,
                "hedge_fund_sentiment": data.get("sentiment"),
                "num_hedge_funds": data.get("numOfHedgeFunds"),
                "shares_held": data.get("sharesHeld"),
                "value_held": data.get("valueHeld"),
                "change_in_shares": data.get("changeInShares"),
            }
        except Exception as e:
            logger.error(f"Failed to get TipRanks hedge fund data: {e}")
            return {"symbol": symbol, "error": str(e)}

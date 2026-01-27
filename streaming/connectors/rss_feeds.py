"""
RSS Feed Connector
==================

Fetches news from financial RSS feeds including CNBC, MarketWatch, 
Seeking Alpha, and other major financial news sources.

RSS feeds are free, reliable, and don't require API keys, making them
excellent for supplementing paid API sources.

Features:
- No API key required
- Real-time updates from major sources
- Good for breaking news
- Reliable and stable
- Category-based filtering (earnings, finance, economy, etc.)

Supported Feeds:
- CNBC (9 feeds: Top News, Finance, Earnings, Investing, Stock Blog, 
        Economy, Market Insider, Pro, World Markets)
- MarketWatch (Top Stories, Market Pulse)
- Seeking Alpha (Market Currents, Wall Street Breakfast)
- Investing.com (Stock News, Economy)
- Motley Fool
- Business Insider Markets

Usage:
    # All feeds
    connector = RSSFeedConnector()
    
    # CNBC feeds only
    connector = RSSFeedConnector.cnbc_only()
    
    # Earnings-focused feeds
    connector = RSSFeedConnector.by_category("earnings")
    
    # Specific feeds
    connector = RSSFeedConnector(enabled_feeds=["cnbc_earnings", "cnbc_finance"])
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import asyncio
import re
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import aiohttp

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


# RSS Feed definitions with their URLs and parsing info
RSS_FEEDS = {
    # =========================================================================
    # CNBC Feeds - Comprehensive financial news coverage
    # Source: https://www.cnbc.com/rss-feeds/
    # =========================================================================
    
    # CNBC Top News - Breaking financial news and headlines
    "cnbc_top_news": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "CNBC Top News",
        "category": "general",
    },
    # CNBC Finance - General finance news
    "cnbc_finance": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "CNBC Finance",
        "category": "finance",
    },
    # CNBC Earnings - Company earnings reports and analysis
    # Critical for stock recommendations during earnings season
    "cnbc_earnings": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "CNBC Earnings",
        "category": "earnings",
    },
    # CNBC Investing - Investment strategies and market analysis
    "cnbc_investing": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "CNBC Investing",
        "category": "investing",
    },
    # CNBC Stock Blog - Stock-specific news and analysis
    "cnbc_stock_blog": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "CNBC Stock Blog",
        "category": "stocks",
    },
    # CNBC Economy - Economic indicators and policy news
    "cnbc_economy": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "CNBC Economy",
        "category": "economy",
    },
    # CNBC Market Insider - Market movements and trends
    "cnbc_market_insider": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20409666",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "CNBC Market Insider",
        "category": "markets",
    },
    # CNBC Pro - CNBC Pro analysis and picks (publicly available items)
    "cnbc_pro": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=101147702",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "CNBC Pro",
        "category": "analysis",
    },
    # CNBC World Markets - International market news
    "cnbc_world_markets": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "CNBC World Markets",
        "category": "international",
    },
    
    # =========================================================================
    # Seeking Alpha Feeds
    # =========================================================================
    
    # Seeking Alpha - Market Currents (reliable, good financial news)
    "seeking_alpha_market": {
        "url": "https://seekingalpha.com/market_currents.xml",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "Seeking Alpha",
        "category": "markets",
    },
    # Seeking Alpha - Wall Street Breakfast
    "seeking_alpha_wsb": {
        "url": "https://seekingalpha.com/tag/wall-st-breakfast.xml",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "Seeking Alpha WSB",
        "category": "markets",
    },
    
    # =========================================================================
    # MarketWatch Feeds (Dow Jones)
    # =========================================================================
    
    # MarketWatch Top Stories (using Dow Jones CDN)
    "marketwatch_top": {
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "MarketWatch",
        "category": "general",
    },
    # MarketWatch Market Pulse (using Dow Jones CDN)
    "marketwatch_stocks": {
        "url": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "MarketWatch",
        "category": "markets",
    },
    
    # =========================================================================
    # Investing.com Feeds
    # =========================================================================
    
    # Investing.com - Stock News
    "investing_stock_news": {
        "url": "https://www.investing.com/rss/news_301.rss",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "Investing.com Stocks",
        "category": "stocks",
    },
    # Investing.com - Economy
    "investing_economy": {
        "url": "https://www.investing.com/rss/news_14.rss",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "Investing.com Economy",
        "category": "economy",
    },
    
    # =========================================================================
    # Other Financial News Feeds
    # =========================================================================
    
    # The Motley Fool
    "motley_fool": {
        "url": "https://www.fool.com/feeds/index.aspx",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "Motley Fool",
        "category": "investing",
    },
    # Business Insider Markets
    "business_insider": {
        "url": "https://markets.businessinsider.com/rss/news",
        "source": NewsSource.RSS_YAHOO,
        "source_name": "Business Insider Markets",
        "category": "markets",
    },
}


class RSSFeedConnector(BaseNewsConnector):
    """
    News connector for financial RSS feeds.
    
    This connector fetches and parses RSS/Atom feeds from multiple financial
    news sources. It's designed to complement API-based connectors and
    provide free, reliable news coverage.
    
    Example Usage:
        connector = RSSFeedConnector()
        
        # Fetch from all configured feeds
        articles = await connector.fetch_news(limit=100)
        
        # Fetch from specific feeds only
        connector = RSSFeedConnector(
            enabled_feeds=["reuters_business", "cnbc_top"]
        )
        articles = await connector.fetch_news()
    """
    
    source = NewsSource.RSS_REUTERS  # Default, actual source varies by feed
    base_url = ""  # Multiple URLs
    rate_limit_per_minute = 30  # Conservative for RSS feeds
    
    def __init__(
        self,
        enabled_feeds: Optional[List[str]] = None,
        timeout: int = 30,
    ):
        """
        Initialize RSS feed connector.
        
        Args:
            enabled_feeds: List of feed keys to enable (default: all feeds)
                          See RSS_FEEDS dict for available keys.
            timeout: HTTP request timeout in seconds
        """
        super().__init__(api_key=None, timeout=timeout)
        
        # Enable specified feeds or all feeds
        if enabled_feeds:
            self.feeds = {k: v for k, v in RSS_FEEDS.items() if k in enabled_feeds}
        else:
            self.feeds = RSS_FEEDS.copy()
        
        logger.info(f"RSS connector initialized with {len(self.feeds)} feeds: {list(self.feeds.keys())}")
    
    @classmethod
    def cnbc_only(cls, timeout: int = 30) -> "RSSFeedConnector":
        """
        Create connector with only CNBC feeds enabled.
        
        CNBC provides comprehensive financial coverage including:
        - Top News: Breaking financial news
        - Finance: General finance news
        - Earnings: Company earnings reports (critical for recommendations)
        - Investing: Investment strategies
        - Stock Blog: Stock-specific analysis
        - Economy: Economic indicators
        - Market Insider: Market movements
        - Pro: CNBC Pro analysis
        - World Markets: International news
        
        Returns:
            RSSFeedConnector configured for CNBC feeds only
        """
        cnbc_feeds = [k for k in RSS_FEEDS.keys() if k.startswith("cnbc_")]
        return cls(enabled_feeds=cnbc_feeds, timeout=timeout)
    
    @classmethod
    def by_category(cls, category: str, timeout: int = 30) -> "RSSFeedConnector":
        """
        Create connector with feeds filtered by category.
        
        Available categories:
        - "general": General news (CNBC Top News, MarketWatch Top)
        - "finance": Finance news
        - "earnings": Earnings reports and analysis
        - "investing": Investment strategies
        - "stocks": Stock-specific news
        - "economy": Economic news
        - "markets": Market movements and trends
        - "analysis": Professional analysis
        - "international": World markets
        
        Args:
            category: Category to filter by
            timeout: HTTP request timeout
            
        Returns:
            RSSFeedConnector configured for specified category
        """
        category_feeds = [
            k for k, v in RSS_FEEDS.items() 
            if v.get("category") == category
        ]
        if not category_feeds:
            logger.warning(f"No feeds found for category '{category}', using all feeds")
            return cls(timeout=timeout)
        return cls(enabled_feeds=category_feeds, timeout=timeout)
    
    @classmethod
    def by_source(cls, source_prefix: str, timeout: int = 30) -> "RSSFeedConnector":
        """
        Create connector with feeds filtered by source.
        
        Available source prefixes:
        - "cnbc": CNBC feeds
        - "seeking_alpha": Seeking Alpha feeds
        - "marketwatch": MarketWatch feeds
        - "investing": Investing.com feeds
        - "motley": Motley Fool
        - "business_insider": Business Insider
        
        Args:
            source_prefix: Prefix to filter feed keys by
            timeout: HTTP request timeout
            
        Returns:
            RSSFeedConnector configured for specified source
        """
        source_feeds = [k for k in RSS_FEEDS.keys() if k.startswith(source_prefix)]
        if not source_feeds:
            logger.warning(f"No feeds found for source '{source_prefix}', using all feeds")
            return cls(timeout=timeout)
        return cls(enabled_feeds=source_feeds, timeout=timeout)
    
    @staticmethod
    def list_available_feeds() -> Dict[str, Dict[str, Any]]:
        """
        List all available RSS feeds with their configuration.
        
        Returns:
            Dictionary of feed configurations
        """
        return RSS_FEEDS.copy()
    
    @staticmethod
    def list_categories() -> List[str]:
        """
        List all available feed categories.
        
        Returns:
            List of unique category names
        """
        categories = set()
        for feed in RSS_FEEDS.values():
            if "category" in feed:
                categories.add(feed["category"])
        return sorted(list(categories))
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch news from all enabled RSS feeds.
        
        RSS feeds don't support symbol filtering, so all articles are fetched
        and then filtered client-side if symbols are provided.
        
        Args:
            symbols: Stock symbols to filter for (post-fetch filtering)
            since: Only return articles published after this time
            limit: Maximum total articles to return
            
        Returns:
            List of NewsArticle objects from all feeds
        """
        # Default time filter: last 24 hours
        if since is None:
            since = datetime.utcnow() - timedelta(hours=24)
        
        # Fetch from all feeds concurrently
        tasks = [
            self._fetch_feed(feed_key, feed_config)
            for feed_key, feed_config in self.feeds.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate articles from all feeds
        all_articles = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Feed fetch failed: {result}")
                continue
            all_articles.extend(result)
        
        # Filter by time - handle timezone-aware vs naive datetime comparison
        since_naive = since.replace(tzinfo=None) if since.tzinfo else since
        articles = [a for a in all_articles if a.published_at.replace(tzinfo=None) >= since_naive]
        
        # Filter by symbols if provided
        if symbols:
            symbols_upper = [s.upper() for s in symbols]
            filtered = []
            for article in articles:
                # Check if article mentions any target symbol
                text = f"{article.title} {article.summary}".upper()
                for symbol in symbols_upper:
                    if symbol in text:
                        if symbol not in article.symbols:
                            article.symbols.append(symbol)
                
                # Include if any symbols found
                if article.symbols:
                    filtered.append(article)
            
            articles = filtered
        
        # Sort by published date and limit
        articles.sort(key=lambda a: a.published_at, reverse=True)
        
        # Deduplicate by URL (same article might appear in multiple feeds)
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)
        
        self.articles_fetched += len(unique_articles[:limit])
        logger.info(f"Fetched {len(unique_articles[:limit])} articles from RSS feeds")
        
        return unique_articles[:limit]
    
    async def _fetch_feed(
        self,
        feed_key: str,
        feed_config: Dict[str, Any],
    ) -> List[NewsArticle]:
        """
        Fetch and parse a single RSS feed.
        
        Args:
            feed_key: Identifier for the feed
            feed_config: Feed configuration with URL and source info
            
        Returns:
            List of NewsArticle objects from the feed
        """
        url = feed_config["url"]
        source = feed_config["source"]
        source_name = feed_config["source_name"]
        
        logger.debug(f"Fetching RSS feed: {feed_key}")
        
        try:
            session = await self._get_session()
            
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"RSS feed {feed_key} returned status {response.status}")
                    return []
                
                content = await response.text()
            
            # Parse RSS/Atom XML
            articles = self._parse_feed(content, source, source_name)
            
            logger.debug(f"Parsed {len(articles)} articles from {feed_key}")
            return articles
            
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {feed_key}: {e}")
            return []
    
    def _parse_feed(
        self,
        content: str,
        source: NewsSource,
        source_name: str,
    ) -> List[NewsArticle]:
        """
        Parse RSS/Atom XML content into NewsArticle objects.
        
        Handles both RSS 2.0 and Atom feed formats.
        
        Args:
            content: Raw XML content
            source: NewsSource enum value
            source_name: Human-readable source name
            
        Returns:
            List of parsed NewsArticle objects
        """
        articles = []
        
        try:
            root = ElementTree.fromstring(content)
            
            # Determine feed format and find items
            items = []
            
            # RSS 2.0 format
            channel = root.find("channel")
            if channel is not None:
                items = channel.findall("item")
            
            # Atom format
            if not items:
                # Handle Atom namespace
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                items = root.findall("atom:entry", ns)
                if not items:
                    items = root.findall("entry")
            
            for item in items:
                article = self._parse_item(item, source, source_name)
                if article:
                    articles.append(article)
                    
        except ElementTree.ParseError as e:
            logger.error(f"Failed to parse RSS XML: {e}")
        
        return articles
    
    def _parse_item(
        self,
        item: ElementTree.Element,
        source: NewsSource,
        source_name: str,
    ) -> Optional[NewsArticle]:
        """
        Parse a single RSS item/entry into a NewsArticle.
        
        Args:
            item: XML element for the item
            source: NewsSource enum value
            source_name: Human-readable source name
            
        Returns:
            NewsArticle or None if parsing fails
        """
        try:
            # Get title (RSS: title, Atom: title)
            title_elem = item.find("title")
            title = title_elem.text if title_elem is not None else ""
            
            if not title:
                return None
            
            # Get link/URL (RSS: link, Atom: link[@href])
            link_elem = item.find("link")
            if link_elem is not None:
                url = link_elem.get("href") or link_elem.text or ""
            else:
                url = ""
            
            # Get description/summary (RSS: description, Atom: summary or content)
            summary = ""
            for tag in ["description", "summary", "content"]:
                elem = item.find(tag)
                if elem is not None and elem.text:
                    summary = elem.text
                    break
            
            # Clean HTML from summary
            summary = self._strip_html(summary)
            
            # Get publication date (RSS: pubDate, Atom: published or updated)
            published_at = datetime.utcnow()
            for tag in ["pubDate", "published", "updated", "dc:date"]:
                date_elem = item.find(tag)
                if date_elem is not None and date_elem.text:
                    published_at = self._parse_date(date_elem.text)
                    break
            
            # Get author
            author = None
            for tag in ["author", "dc:creator"]:
                author_elem = item.find(tag)
                if author_elem is not None:
                    # Atom author has nested name element
                    name_elem = author_elem.find("name")
                    author = name_elem.text if name_elem is not None else author_elem.text
                    break
            
            # Get image (various enclosure formats)
            image_url = None
            enclosure = item.find("enclosure")
            if enclosure is not None:
                if "image" in enclosure.get("type", ""):
                    image_url = enclosure.get("url")
            
            # Media content (common in news feeds)
            media_ns = {"media": "http://search.yahoo.com/mrss/"}
            media_content = item.find("media:content", media_ns)
            if media_content is not None:
                image_url = media_content.get("url")
            
            # Extract symbols from title and summary
            symbols = self._extract_symbols_from_text(
                f"{title} {summary}",
                known_symbols=self._get_common_symbols()
            )
            
            # Categorize
            categories = self._categorize_article(title, summary)
            
            return NewsArticle(
                title=title,
                summary=summary[:500] if summary else "",  # Limit summary length
                url=url,
                source=source,
                source_name=source_name,
                published_at=published_at,
                symbols=symbols,
                categories=categories,
                author=author,
                image_url=image_url,
                metadata={},
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse RSS item: {e}")
            return None
    
    def _strip_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        # Simple HTML tag removal
        clean = re.sub(r'<[^>]+>', '', text)
        # Decode common entities
        clean = clean.replace('&amp;', '&')
        clean = clean.replace('&lt;', '<')
        clean = clean.replace('&gt;', '>')
        clean = clean.replace('&quot;', '"')
        clean = clean.replace('&#39;', "'")
        clean = clean.replace('&nbsp;', ' ')
        return clean.strip()
    
    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse various date formats found in RSS feeds.
        
        Args:
            date_str: Date string from RSS feed
            
        Returns:
            Parsed datetime (UTC)
        """
        try:
            # Try RFC 2822 format (common in RSS)
            return parsedate_to_datetime(date_str)
        except (TypeError, ValueError):
            pass
        
        # Try ISO format
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00").replace("+00:00", ""))
        except ValueError:
            pass
        
        # Fallback to current time
        return datetime.utcnow()
    
    def _get_common_symbols(self) -> List[str]:
        """
        Get list of common stock symbols for extraction.
        
        Returns:
            List of major US stock symbols
        """
        return [
            # Tech giants
            "AAPL", "GOOGL", "GOOG", "MSFT", "AMZN", "META", "NVDA", "TSLA",
            # Finance
            "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "AXP",
            # Healthcare
            "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY",
            # Consumer
            "WMT", "PG", "KO", "PEP", "COST", "NKE", "MCD",
            # Energy
            "XOM", "CVX", "COP",
            # Industrial
            "CAT", "BA", "HON", "UPS",
            # ETFs
            "SPY", "QQQ", "DIA", "IWM", "VTI",
            # Crypto-related
            "COIN", "MARA", "RIOT",
        ]
    
    def add_feed(
        self,
        feed_key: str,
        url: str,
        source_name: str,
        source: NewsSource = NewsSource.RSS_YAHOO,
    ):
        """
        Add a custom RSS feed to the connector.
        
        Args:
            feed_key: Unique identifier for the feed
            url: RSS feed URL
            source_name: Human-readable source name
            source: NewsSource enum value
        """
        self.feeds[feed_key] = {
            "url": url,
            "source": source,
            "source_name": source_name,
        }
        logger.info(f"Added RSS feed: {feed_key}")

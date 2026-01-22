"""
Recommendation Flow Service
============================

Scheduled service that runs every 2 hours to:
1. Collect data from all sources for each stock in the watchlist
2. Normalize the data
3. Generate recommendations using the RecommendationEngine
4. Persist recommendations to PostgreSQL database
5. Keep only the last 10 recommendations per symbol

This service integrates with:
- News features from ClickHouse
- Technical features from price data providers
- PostgreSQL for recommendation storage
- HashiCorp Vault for API key management

Data Sources (API keys loaded from Vault):
- Polygon.io: Real-time prices, news, ticker details
- IEX Cloud: Quotes, historical prices, key stats (DISABLED - no API key)
- Nasdaq Data Link: Historical prices, fundamentals, economic indicators
- Alpha Vantage: News with sentiment scores
- Finnhub: Company news and market data
- NewsAPI: News aggregation from thousands of sources
- Benzinga: Financial news and analysis
- Financial Modeling Prep (FMP): Financial data and news

Free Data Sources (no API keys required):
- Yahoo Finance: News and market data
- RSS Feeds: Reuters, Bloomberg, CNBC, MarketWatch, etc.
- SEC EDGAR: 10-K, 10-Q, 8-K filings and insider trading
- TipRanks: Analyst ratings and price targets

Social Media (optional API key for higher rate limits):
- StockTwits: Pre-labeled social sentiment (bullish/bearish)
"""

import logging
import os
import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import from sibling modules
try:
    from .main import RecommendationEngine, get_engine
    from .news_features import NewsFeatureProvider
    from .technical_features import TechnicalFeatureProvider
except ImportError:
    from main import RecommendationEngine, get_engine
    from news_features import NewsFeatureProvider
    from technical_features import TechnicalFeatureProvider

# Import market data connectors
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'streaming'))
try:
    from streaming.connectors import (
        # Market Data Connectors (require API keys)
        PolygonConnector,
        IEXCloudConnector,
        NasdaqDataLinkConnector,
        AlphaVantageConnector,
        FinnhubConnector,
        NewsAPIConnector,
        BenzingaConnector,
        FinancialModelingPrepConnector,
        # Free Connectors (no API keys required)
        YahooFinanceConnector,
        RSSFeedConnector,
        SECEdgarConnector,
        TipRanksConnector,
        # Social Media (optional API key for higher rate limits)
        StockTwitsConnector,
    )
except ImportError:
    # Fallback for standalone execution
    PolygonConnector = None
    IEXCloudConnector = None
    NasdaqDataLinkConnector = None
    AlphaVantageConnector = None
    FinnhubConnector = None
    NewsAPIConnector = None
    BenzingaConnector = None
    FinancialModelingPrepConnector = None
    YahooFinanceConnector = None
    RSSFeedConnector = None
    SECEdgarConnector = None
    TipRanksConnector = None
    StockTwitsConnector = None


@dataclass
class MarketDataSnapshot:
    """
    Aggregated market data snapshot for a symbol from all sources.
    
    Contains normalized data from multiple providers for use in
    recommendation generation.
    """
    symbol: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Price data (from multiple sources, averaged/reconciled)
    current_price: Optional[float] = None
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    previous_close: Optional[float] = None
    volume: Optional[int] = None
    vwap: Optional[float] = None
    
    # Change metrics
    change_amount: Optional[float] = None
    change_percent: Optional[float] = None
    
    # Technical indicators (calculated from price data)
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi: Optional[float] = None
    
    # Fundamental data
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    
    # News/Sentiment
    news_count_24h: int = 0
    news_sentiment_avg: Optional[float] = None
    news_articles: List[Dict[str, Any]] = field(default_factory=list)
    
    # Data source tracking
    data_sources: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'current_price': self.current_price,
            'open_price': self.open_price,
            'high_price': self.high_price,
            'low_price': self.low_price,
            'close_price': self.close_price,
            'previous_close': self.previous_close,
            'volume': self.volume,
            'vwap': self.vwap,
            'change_amount': self.change_amount,
            'change_percent': self.change_percent,
            'sma_20': self.sma_20,
            'sma_50': self.sma_50,
            'sma_200': self.sma_200,
            'rsi': self.rsi,
            'market_cap': self.market_cap,
            'pe_ratio': self.pe_ratio,
            'eps': self.eps,
            'dividend_yield': self.dividend_yield,
            'beta': self.beta,
            'week_52_high': self.week_52_high,
            'week_52_low': self.week_52_low,
            'news_count_24h': self.news_count_24h,
            'news_sentiment_avg': self.news_sentiment_avg,
            'data_sources': self.data_sources,
        }


class MarketDataAggregator:
    """
    Aggregates market data from multiple sources.
    
    Collects data from multiple providers including:
    - Polygon.io: Real-time prices, news, ticker details
    - IEX Cloud: Quotes, historical prices, key stats (disabled until API key added)
    - Nasdaq Data Link: Historical prices, fundamentals
    - Alpha Vantage: News with sentiment scores
    - Finnhub: Company news and market data
    - NewsAPI: News aggregation from thousands of sources
    - Benzinga: Financial news and analysis
    - Financial Modeling Prep (FMP): Financial data and news
    
    All connectors load API keys from Vault with fallback to environment variables.
    """
    
    def __init__(self):
        """Initialize the market data aggregator with all connectors."""
        # Connectors requiring API keys (loaded from Vault)
        self.polygon: Optional[PolygonConnector] = None
        self.iex: Optional[IEXCloudConnector] = None
        self.nasdaq: Optional[NasdaqDataLinkConnector] = None
        self.alpha_vantage: Optional[AlphaVantageConnector] = None
        self.finnhub: Optional[FinnhubConnector] = None
        self.newsapi: Optional[NewsAPIConnector] = None
        self.benzinga: Optional[BenzingaConnector] = None
        self.fmp: Optional[FinancialModelingPrepConnector] = None
        
        # Free connectors (no API keys required)
        self.yahoo: Optional[YahooFinanceConnector] = None
        self.rss: Optional[RSSFeedConnector] = None
        self.sec_edgar: Optional[SECEdgarConnector] = None
        self.tipranks: Optional[TipRanksConnector] = None
        
        # Social media connectors (optional API key for higher rate limits)
        self.stocktwits: Optional[StockTwitsConnector] = None
        
        self._initialized = False
    
    async def initialize(self):
        """
        Initialize all available connectors based on API keys from Vault.
        
        Connectors are initialized lazily - API keys are loaded from Vault
        on first use. This method creates the connector instances and checks
        the 'enabled' flag for disabled connectors.
        """
        logger.info("Initializing market data connectors...")
        
        # Initialize Polygon.io (loads API key from Vault on first use)
        if PolygonConnector:
            try:
                self.polygon = PolygonConnector()
                # Trigger API key loading to check if enabled
                await self.polygon._ensure_api_key()
                if self.polygon.api_key:
                    logger.info("✓ Polygon.io connector initialized")
                else:
                    logger.info("✗ Polygon.io connector skipped - no API key configured")
                    self.polygon = None
            except Exception as e:
                logger.warning(f"✗ Polygon.io connector failed: {e}")
                self.polygon = None
        
        # Initialize IEX Cloud (check enabled flag - disabled until API key added)
        if IEXCloudConnector:
            try:
                connector = IEXCloudConnector()
                await connector._ensure_api_key()
                # Check if connector is enabled (has API key)
                if getattr(connector, 'enabled', True) and connector.api_key:
                    self.iex = connector
                    logger.info("✓ IEX Cloud connector initialized")
                else:
                    logger.info("✗ IEX Cloud connector disabled - no API key configured")
            except Exception as e:
                logger.warning(f"✗ IEX Cloud connector failed: {e}")
        
        # Initialize Nasdaq Data Link (loads API key from Vault on first use)
        if NasdaqDataLinkConnector:
            try:
                self.nasdaq = NasdaqDataLinkConnector()
                await self.nasdaq._ensure_api_key()
                if self.nasdaq.api_key:
                    logger.info("✓ Nasdaq Data Link connector initialized")
                else:
                    logger.info("✗ Nasdaq Data Link connector skipped - no API key configured")
                    self.nasdaq = None
            except Exception as e:
                logger.warning(f"✗ Nasdaq Data Link connector failed: {e}")
                self.nasdaq = None
        
        # Initialize Alpha Vantage (loads API key from Vault on first use)
        if AlphaVantageConnector:
            try:
                self.alpha_vantage = AlphaVantageConnector()
                await self.alpha_vantage._ensure_api_key()
                if self.alpha_vantage.api_key:
                    logger.info("✓ Alpha Vantage connector initialized")
                else:
                    logger.info("✗ Alpha Vantage connector skipped - no API key configured")
                    self.alpha_vantage = None
            except Exception as e:
                logger.warning(f"✗ Alpha Vantage connector failed: {e}")
                self.alpha_vantage = None
        
        # Initialize Finnhub (loads API key from Vault on first use)
        if FinnhubConnector:
            try:
                self.finnhub = FinnhubConnector()
                await self.finnhub._ensure_api_key()
                if self.finnhub.api_key:
                    logger.info("✓ Finnhub connector initialized")
                else:
                    logger.info("✗ Finnhub connector skipped - no API key configured")
                    self.finnhub = None
            except Exception as e:
                logger.warning(f"✗ Finnhub connector failed: {e}")
                self.finnhub = None
        
        # Initialize NewsAPI (loads API key from Vault on first use)
        if NewsAPIConnector:
            try:
                self.newsapi = NewsAPIConnector()
                await self.newsapi._ensure_api_key()
                if self.newsapi.api_key:
                    logger.info("✓ NewsAPI connector initialized")
                else:
                    logger.info("✗ NewsAPI connector skipped - no API key configured")
                    self.newsapi = None
            except Exception as e:
                logger.warning(f"✗ NewsAPI connector failed: {e}")
                self.newsapi = None
        
        # Initialize Benzinga (loads API key from Vault on first use)
        if BenzingaConnector:
            try:
                self.benzinga = BenzingaConnector()
                await self.benzinga._ensure_api_key()
                if self.benzinga.api_key:
                    logger.info("✓ Benzinga connector initialized")
                else:
                    logger.info("✗ Benzinga connector skipped - no API key configured")
                    self.benzinga = None
            except Exception as e:
                logger.warning(f"✗ Benzinga connector failed: {e}")
                self.benzinga = None
        
        # Initialize Financial Modeling Prep (loads API key from Vault on first use)
        if FinancialModelingPrepConnector:
            try:
                self.fmp = FinancialModelingPrepConnector()
                await self.fmp._ensure_api_key()
                if self.fmp.api_key:
                    logger.info("✓ Financial Modeling Prep connector initialized")
                else:
                    logger.info("✗ Financial Modeling Prep connector skipped - no API key configured")
                    self.fmp = None
            except Exception as e:
                logger.warning(f"✗ Financial Modeling Prep connector failed: {e}")
                self.fmp = None
        
        # ============== FREE CONNECTORS (no API keys required) ==============
        
        # Initialize Yahoo Finance (free, no API key required)
        if YahooFinanceConnector:
            try:
                self.yahoo = YahooFinanceConnector()
                logger.info("✓ Yahoo Finance connector initialized (free)")
            except Exception as e:
                logger.warning(f"✗ Yahoo Finance connector failed: {e}")
                self.yahoo = None
        
        # Initialize RSS Feed connector (free, no API key required)
        if RSSFeedConnector:
            try:
                self.rss = RSSFeedConnector()
                logger.info("✓ RSS Feed connector initialized (free)")
            except Exception as e:
                logger.warning(f"✗ RSS Feed connector failed: {e}")
                self.rss = None
        
        # Initialize SEC EDGAR connector (free, no API key required)
        if SECEdgarConnector:
            try:
                self.sec_edgar = SECEdgarConnector()
                logger.info("✓ SEC EDGAR connector initialized (free)")
            except Exception as e:
                logger.warning(f"✗ SEC EDGAR connector failed: {e}")
                self.sec_edgar = None
        
        # Initialize TipRanks connector (free, no API key required)
        if TipRanksConnector:
            try:
                self.tipranks = TipRanksConnector()
                logger.info("✓ TipRanks connector initialized (free)")
            except Exception as e:
                logger.warning(f"✗ TipRanks connector failed: {e}")
                self.tipranks = None
        
        # ============== SOCIAL MEDIA CONNECTORS ==============
        
        # Initialize StockTwits connector (works without auth, optional token for higher limits)
        if StockTwitsConnector:
            try:
                self.stocktwits = StockTwitsConnector()
                # Try to load optional access token from Vault
                await self.stocktwits._ensure_access_token()
                if self.stocktwits.access_token:
                    logger.info("✓ StockTwits connector initialized (with auth - higher rate limits)")
                else:
                    logger.info("✓ StockTwits connector initialized (no auth - lower rate limits)")
            except Exception as e:
                logger.warning(f"✗ StockTwits connector failed: {e}")
                self.stocktwits = None
        
        self._initialized = True
        
        # Count active connectors
        paid_connectors = sum([
            self.polygon is not None,
            self.iex is not None,
            self.nasdaq is not None,
            self.alpha_vantage is not None,
            self.finnhub is not None,
            self.newsapi is not None,
            self.benzinga is not None,
            self.fmp is not None,
        ])
        free_connectors = sum([
            self.yahoo is not None,
            self.rss is not None,
            self.sec_edgar is not None,
            self.tipranks is not None,
        ])
        social_connectors = sum([
            self.stocktwits is not None,
        ])
        total_connectors = paid_connectors + free_connectors + social_connectors
        logger.info(f"Market data aggregator initialized with {total_connectors} connector(s) "
                   f"({paid_connectors} paid, {free_connectors} free, {social_connectors} social)")
    
    async def close(self):
        """Close all connector sessions."""
        # Close paid connectors
        if self.polygon:
            await self.polygon.close()
        if self.iex:
            await self.iex.close()
        if self.nasdaq:
            await self.nasdaq.close()
        if self.alpha_vantage:
            await self.alpha_vantage.close()
        if self.finnhub:
            await self.finnhub.close()
        if self.newsapi:
            await self.newsapi.close()
        if self.benzinga:
            await self.benzinga.close()
        if self.fmp:
            await self.fmp.close()
        # Close free connectors
        if self.yahoo:
            await self.yahoo.close()
        if self.rss:
            await self.rss.close()
        if self.sec_edgar:
            await self.sec_edgar.close()
        if self.tipranks:
            await self.tipranks.close()
        # Close social media connectors
        if self.stocktwits:
            await self.stocktwits.close()
    
    async def get_snapshot(self, symbol: str) -> MarketDataSnapshot:
        """
        Get aggregated market data snapshot for a symbol.
        
        Fetches data from all available sources concurrently and
        combines into a single normalized snapshot.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            MarketDataSnapshot with data from all sources
        """
        snapshot = MarketDataSnapshot(symbol=symbol)
        
        # Fetch data from all sources concurrently
        tasks = []
        
        if self.polygon:
            tasks.append(('polygon', self._fetch_polygon_data(symbol)))
        if self.iex:
            tasks.append(('iex', self._fetch_iex_data(symbol)))
        if self.nasdaq:
            tasks.append(('nasdaq', self._fetch_nasdaq_data(symbol)))
        if self.alpha_vantage:
            tasks.append(('alpha_vantage', self._fetch_alpha_vantage_data(symbol)))
        if self.finnhub:
            tasks.append(('finnhub', self._fetch_finnhub_data(symbol)))
        if self.newsapi:
            tasks.append(('newsapi', self._fetch_newsapi_data(symbol)))
        if self.benzinga:
            tasks.append(('benzinga', self._fetch_benzinga_data(symbol)))
        if self.fmp:
            tasks.append(('fmp', self._fetch_fmp_data(symbol)))
        # Free connectors (no API keys required)
        if self.yahoo:
            tasks.append(('yahoo', self._fetch_yahoo_data(symbol)))
        if self.rss:
            tasks.append(('rss', self._fetch_rss_data(symbol)))
        if self.sec_edgar:
            tasks.append(('sec_edgar', self._fetch_sec_edgar_data(symbol)))
        if self.tipranks:
            tasks.append(('tipranks', self._fetch_tipranks_data(symbol)))
        # Social media connectors
        if self.stocktwits:
            tasks.append(('stocktwits', self._fetch_stocktwits_data(symbol)))
        
        if not tasks:
            logger.warning(f"No data connectors available for {symbol}")
            return snapshot
        
        # Execute all fetches concurrently
        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True
        )
        
        # Process results from each source
        for (source_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                error_msg = f"{source_name}: {str(result)}"
                snapshot.errors.append(error_msg)
                logger.warning(f"Data fetch error for {symbol} from {source_name}: {result}")
            elif result:
                snapshot.data_sources.append(source_name)
                self._merge_data(snapshot, result, source_name)
        
        # Calculate derived metrics
        self._calculate_derived_metrics(snapshot)
        
        logger.debug(f"Snapshot for {symbol}: sources={snapshot.data_sources}, "
                    f"price={snapshot.current_price}, errors={len(snapshot.errors)}")
        
        return snapshot
    
    async def _fetch_polygon_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from Polygon.io."""
        data = {}
        
        try:
            # Get snapshot (current price and today's data)
            snapshot = await self.polygon.get_snapshot(symbol)
            if snapshot:
                data['snapshot'] = snapshot
            
            # Get previous close
            prev_close = await self.polygon.get_previous_close(symbol)
            if prev_close:
                data['prev_close'] = prev_close
            
            # Get news
            news = await self.polygon.fetch_news(symbols=[symbol], limit=10)
            if news:
                data['news'] = news
                
        except Exception as e:
            logger.warning(f"Polygon data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_iex_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from IEX Cloud."""
        data = {}
        
        try:
            # Get quote
            quote = await self.iex.get_quote(symbol)
            if quote:
                data['quote'] = quote
            
            # Get key stats
            stats = await self.iex.get_key_stats(symbol)
            if stats:
                data['stats'] = stats
            
            # Get news
            news = await self.iex.fetch_news(symbols=[symbol], limit=10)
            if news:
                data['news'] = news
                
        except Exception as e:
            logger.warning(f"IEX data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_nasdaq_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from Nasdaq Data Link."""
        data = {}
        
        try:
            # Get historical prices (last 30 days for technical analysis)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            
            prices = await self.nasdaq.get_stock_prices(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            if prices:
                data['prices'] = prices
                
        except Exception as e:
            logger.warning(f"Nasdaq data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_alpha_vantage_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from Alpha Vantage."""
        data = {}
        
        try:
            # Get news with sentiment
            since = datetime.utcnow() - timedelta(hours=24)
            news = await self.alpha_vantage.fetch_news(
                symbols=[symbol],
                since=since,
                limit=20
            )
            if news:
                data['news'] = news
                # Calculate average sentiment
                sentiments = [
                    article.metadata.get('sentiment_score', 0)
                    for article in news
                    if article.metadata.get('sentiment_score') is not None
                ]
                if sentiments:
                    data['avg_sentiment'] = sum(sentiments) / len(sentiments)
                    
        except Exception as e:
            logger.warning(f"Alpha Vantage data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_finnhub_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from Finnhub."""
        data = {}
        
        try:
            # Get company news
            since = datetime.utcnow() - timedelta(days=7)
            news = await self.finnhub.fetch_news(
                symbols=[symbol],
                since=since,
                limit=20
            )
            if news:
                data['news'] = news
                    
        except Exception as e:
            logger.warning(f"Finnhub data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_newsapi_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from NewsAPI."""
        data = {}
        
        try:
            # Search for news about the symbol
            since = datetime.utcnow() - timedelta(days=7)
            news = await self.newsapi.fetch_news(
                symbols=[symbol],
                since=since,
                limit=20
            )
            if news:
                data['news'] = news
                    
        except Exception as e:
            logger.warning(f"NewsAPI data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_benzinga_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from Benzinga."""
        data = {}
        
        try:
            # Get news articles
            since = datetime.utcnow() - timedelta(days=7)
            news = await self.benzinga.fetch_news(
                symbols=[symbol],
                since=since,
                limit=20
            )
            if news:
                data['news'] = news
                    
        except Exception as e:
            logger.warning(f"Benzinga data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_fmp_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from Financial Modeling Prep."""
        data = {}
        
        try:
            # Get news articles
            since = datetime.utcnow() - timedelta(days=7)
            news = await self.fmp.fetch_news(
                symbols=[symbol],
                since=since,
                limit=20
            )
            if news:
                data['news'] = news
                    
        except Exception as e:
            logger.warning(f"FMP data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    # ============== FREE CONNECTOR FETCH METHODS ==============
    
    async def _fetch_yahoo_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from Yahoo Finance (free, no API key required)."""
        data = {}
        
        try:
            # Get price quote
            quote = await self.yahoo.fetch_quote(symbol)
            if quote:
                data['quote'] = quote
            
            # Get news articles
            since = datetime.utcnow() - timedelta(days=7)
            news = await self.yahoo.fetch_news(
                symbols=[symbol],
                since=since,
                limit=20
            )
            if news:
                data['news'] = news
                    
        except Exception as e:
            logger.warning(f"Yahoo Finance data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_rss_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from RSS feeds (free, no API key required)."""
        data = {}
        
        try:
            # Get news from financial RSS feeds
            since = datetime.utcnow() - timedelta(days=7)
            news = await self.rss.fetch_news(
                symbols=[symbol],
                since=since,
                limit=20
            )
            if news:
                data['news'] = news
                    
        except Exception as e:
            logger.warning(f"RSS feed data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_sec_edgar_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from SEC EDGAR (free, no API key required)."""
        data = {}
        
        try:
            # Get SEC filings (10-K, 10-Q, 8-K, etc.)
            since = datetime.utcnow() - timedelta(days=30)  # Filings are less frequent
            filings = await self.sec_edgar.fetch_news(
                symbols=[symbol],
                since=since,
                limit=10
            )
            if filings:
                data['filings'] = filings
                    
        except Exception as e:
            logger.warning(f"SEC EDGAR data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    async def _fetch_tipranks_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from TipRanks (free, no API key required)."""
        data = {}
        
        try:
            # Get analyst ratings and news
            since = datetime.utcnow() - timedelta(days=7)
            news = await self.tipranks.fetch_news(
                symbols=[symbol],
                since=since,
                limit=20
            )
            if news:
                data['news'] = news
                    
        except Exception as e:
            logger.warning(f"TipRanks data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    # ============== SOCIAL MEDIA CONNECTOR FETCH METHODS ==============
    
    async def _fetch_stocktwits_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch data from StockTwits (works without auth, optional token for higher limits)."""
        data = {}
        
        try:
            # Get social sentiment and messages about the symbol
            since = datetime.utcnow() - timedelta(days=1)  # StockTwits is more real-time
            messages = await self.stocktwits.fetch_news(
                symbols=[symbol],
                since=since,
                limit=30
            )
            if messages:
                data['messages'] = messages
                # Calculate sentiment from pre-labeled messages
                bullish = sum(1 for m in messages if m.metadata.get('sentiment') == 'bullish')
                bearish = sum(1 for m in messages if m.metadata.get('sentiment') == 'bearish')
                total_labeled = bullish + bearish
                if total_labeled > 0:
                    # Sentiment score: 1.0 = all bullish, -1.0 = all bearish
                    data['social_sentiment'] = (bullish - bearish) / total_labeled
                    data['bullish_count'] = bullish
                    data['bearish_count'] = bearish
                    
        except Exception as e:
            logger.warning(f"StockTwits data fetch error for {symbol}: {e}")
            raise
        
        return data
    
    def _merge_data(self, snapshot: MarketDataSnapshot, data: Dict[str, Any], source: str):
        """
        Merge data from a source into the snapshot.
        
        Uses first-available strategy for most fields, but averages
        for news sentiment when multiple sources provide it.
        """
        if source == 'polygon':
            if 'snapshot' in data:
                s = data['snapshot']
                if snapshot.current_price is None:
                    snapshot.current_price = s.get('day', {}).get('c')
                if snapshot.open_price is None:
                    snapshot.open_price = s.get('day', {}).get('o')
                if snapshot.high_price is None:
                    snapshot.high_price = s.get('day', {}).get('h')
                if snapshot.low_price is None:
                    snapshot.low_price = s.get('day', {}).get('l')
                if snapshot.volume is None:
                    snapshot.volume = s.get('day', {}).get('v')
                if snapshot.vwap is None:
                    snapshot.vwap = s.get('day', {}).get('vw')
                if snapshot.change_amount is None:
                    snapshot.change_amount = s.get('todays_change')
                if snapshot.change_percent is None:
                    snapshot.change_percent = s.get('todays_change_perc')
                if snapshot.previous_close is None:
                    prev = s.get('prev_day', {})
                    snapshot.previous_close = prev.get('c')
            
            if 'news' in data:
                snapshot.news_articles.extend([
                    {'source': 'polygon', 'title': a.title, 'url': a.url}
                    for a in data['news'][:5]
                ])
        
        elif source == 'iex':
            if 'quote' in data:
                q = data['quote']
                if snapshot.current_price is None:
                    snapshot.current_price = q.get('latestPrice')
                if snapshot.open_price is None:
                    snapshot.open_price = q.get('open')
                if snapshot.high_price is None:
                    snapshot.high_price = q.get('high')
                if snapshot.low_price is None:
                    snapshot.low_price = q.get('low')
                if snapshot.close_price is None:
                    snapshot.close_price = q.get('close')
                if snapshot.previous_close is None:
                    snapshot.previous_close = q.get('previousClose')
                if snapshot.volume is None:
                    snapshot.volume = q.get('volume')
                if snapshot.change_amount is None:
                    snapshot.change_amount = q.get('change')
                if snapshot.change_percent is None:
                    snapshot.change_percent = q.get('changePercent')
                if snapshot.market_cap is None:
                    snapshot.market_cap = q.get('marketCap')
                if snapshot.pe_ratio is None:
                    snapshot.pe_ratio = q.get('peRatio')
                if snapshot.week_52_high is None:
                    snapshot.week_52_high = q.get('week52High')
                if snapshot.week_52_low is None:
                    snapshot.week_52_low = q.get('week52Low')
            
            if 'stats' in data:
                s = data['stats']
                if snapshot.sma_50 is None:
                    snapshot.sma_50 = s.get('day50MovingAvg')
                if snapshot.sma_200 is None:
                    snapshot.sma_200 = s.get('day200MovingAvg')
                if snapshot.beta is None:
                    snapshot.beta = s.get('beta')
                if snapshot.eps is None:
                    snapshot.eps = s.get('ttmEPS')
                if snapshot.dividend_yield is None:
                    snapshot.dividend_yield = s.get('dividendYield')
            
            if 'news' in data:
                snapshot.news_articles.extend([
                    {'source': 'iex', 'title': a.title, 'url': a.url}
                    for a in data['news'][:5]
                ])
        
        elif source == 'nasdaq':
            if 'prices' in data and data['prices']:
                # Use most recent price if no current price yet
                latest = data['prices'][0]  # Assuming sorted desc
                if snapshot.close_price is None:
                    snapshot.close_price = latest.get('close')
                if snapshot.open_price is None:
                    snapshot.open_price = latest.get('open')
                if snapshot.high_price is None:
                    snapshot.high_price = latest.get('high')
                if snapshot.low_price is None:
                    snapshot.low_price = latest.get('low')
                if snapshot.volume is None:
                    snapshot.volume = latest.get('volume')
        
        elif source == 'alpha_vantage':
            if 'news' in data:
                snapshot.news_count_24h += len(data['news'])
                snapshot.news_articles.extend([
                    {
                        'source': 'alpha_vantage',
                        'title': a.title,
                        'url': a.url,
                        'sentiment': a.metadata.get('sentiment_score')
                    }
                    for a in data['news'][:5]
                ])
            
            if 'avg_sentiment' in data:
                if snapshot.news_sentiment_avg is None:
                    snapshot.news_sentiment_avg = data['avg_sentiment']
                else:
                    # Average with existing sentiment
                    snapshot.news_sentiment_avg = (
                        snapshot.news_sentiment_avg + data['avg_sentiment']
                    ) / 2
        
        elif source == 'finnhub':
            if 'news' in data:
                snapshot.news_count_24h += len(data['news'])
                snapshot.news_articles.extend([
                    {
                        'source': 'finnhub',
                        'title': a.title,
                        'url': a.url,
                    }
                    for a in data['news'][:5]
                ])
        
        elif source == 'newsapi':
            if 'news' in data:
                snapshot.news_count_24h += len(data['news'])
                snapshot.news_articles.extend([
                    {
                        'source': 'newsapi',
                        'title': a.title,
                        'url': a.url,
                    }
                    for a in data['news'][:5]
                ])
        
        elif source == 'benzinga':
            if 'news' in data:
                snapshot.news_count_24h += len(data['news'])
                snapshot.news_articles.extend([
                    {
                        'source': 'benzinga',
                        'title': a.title,
                        'url': a.url,
                    }
                    for a in data['news'][:5]
                ])
        
        elif source == 'fmp':
            if 'news' in data:
                snapshot.news_count_24h += len(data['news'])
                snapshot.news_articles.extend([
                    {
                        'source': 'fmp',
                        'title': a.title,
                        'url': a.url,
                    }
                    for a in data['news'][:5]
                ])
        
        # ============== FREE CONNECTORS ==============
        
        elif source == 'yahoo':
            # Extract price from Yahoo quote
            if 'quote' in data:
                q = data['quote']
                if snapshot.current_price is None:
                    snapshot.current_price = q.get('regularMarketPrice')
                if snapshot.close_price is None:
                    snapshot.close_price = q.get('regularMarketPreviousClose')
                if snapshot.open_price is None:
                    snapshot.open_price = q.get('regularMarketOpen')
                if snapshot.high_price is None:
                    snapshot.high_price = q.get('regularMarketDayHigh')
                if snapshot.low_price is None:
                    snapshot.low_price = q.get('regularMarketDayLow')
                if snapshot.volume is None:
                    snapshot.volume = q.get('regularMarketVolume')
                if snapshot.change_amount is None:
                    snapshot.change_amount = q.get('regularMarketChange')
                if snapshot.change_percent is None:
                    snapshot.change_percent = q.get('regularMarketChangePercent')
                if snapshot.market_cap is None:
                    snapshot.market_cap = q.get('marketCap')
                if snapshot.pe_ratio is None:
                    snapshot.pe_ratio = q.get('trailingPE')
                if snapshot.week_52_high is None:
                    snapshot.week_52_high = q.get('fiftyTwoWeekHigh')
                if snapshot.week_52_low is None:
                    snapshot.week_52_low = q.get('fiftyTwoWeekLow')
            
            if 'news' in data:
                snapshot.news_count_24h += len(data['news'])
                snapshot.news_articles.extend([
                    {
                        'source': 'yahoo',
                        'title': a.title,
                        'url': a.url,
                    }
                    for a in data['news'][:5]
                ])
        
        elif source == 'rss':
            if 'news' in data:
                snapshot.news_count_24h += len(data['news'])
                snapshot.news_articles.extend([
                    {
                        'source': 'rss',
                        'title': a.title,
                        'url': a.url,
                    }
                    for a in data['news'][:5]
                ])
        
        elif source == 'sec_edgar':
            if 'filings' in data:
                # SEC filings are treated as high-importance news
                snapshot.news_articles.extend([
                    {
                        'source': 'sec_edgar',
                        'title': a.title,
                        'url': a.url,
                        'filing_type': a.metadata.get('filing_type') if hasattr(a, 'metadata') else None,
                    }
                    for a in data['filings'][:5]
                ])
        
        elif source == 'tipranks':
            if 'news' in data:
                snapshot.news_count_24h += len(data['news'])
                snapshot.news_articles.extend([
                    {
                        'source': 'tipranks',
                        'title': a.title,
                        'url': a.url,
                    }
                    for a in data['news'][:5]
                ])
        
        # ============== SOCIAL MEDIA CONNECTORS ==============
        
        elif source == 'stocktwits':
            if 'messages' in data:
                snapshot.news_articles.extend([
                    {
                        'source': 'stocktwits',
                        'title': m.title,
                        'url': m.url,
                        'sentiment': m.metadata.get('sentiment') if hasattr(m, 'metadata') else None,
                    }
                    for m in data['messages'][:5]
                ])
            
            # Use StockTwits social sentiment to influence overall sentiment
            if 'social_sentiment' in data:
                if snapshot.news_sentiment_avg is None:
                    snapshot.news_sentiment_avg = data['social_sentiment']
                else:
                    # Weight social sentiment at 30% vs 70% for news sentiment
                    snapshot.news_sentiment_avg = (
                        snapshot.news_sentiment_avg * 0.7 + data['social_sentiment'] * 0.3
                    )
    
    def _calculate_derived_metrics(self, snapshot: MarketDataSnapshot):
        """Calculate derived metrics from raw data."""
        # Calculate price vs SMA ratios if we have the data
        if snapshot.current_price and snapshot.sma_50:
            # This could be used for trend analysis
            pass
        
        # Use close price as current if not set
        if snapshot.current_price is None and snapshot.close_price:
            snapshot.current_price = snapshot.close_price


@dataclass
class WatchlistConfig:
    """Configuration for the watchlist of stocks to analyze."""
    symbols: List[str]
    
    @classmethod
    def from_env(cls) -> 'WatchlistConfig':
        """Load watchlist from environment variable or use defaults (fallback only)."""
        symbols_str = os.getenv('WATCHLIST_SYMBOLS', 'AAPL,GOOGL,MSFT')
        symbols = [s.strip().upper() for s in symbols_str.split(',') if s.strip()]
        return cls(symbols=symbols)
    
    @classmethod
    async def from_database(cls, db_pool) -> 'WatchlistConfig':
        """Load watchlist symbols from the user_watchlist database table.
        
        This fetches the actual symbols users have added during onboarding,
        rather than using hardcoded defaults.
        
        Args:
            db_pool: asyncpg connection pool
            
        Returns:
            WatchlistConfig with symbols from the database
        """
        try:
            async with db_pool.acquire() as conn:
                # Get all unique symbols from user watchlists
                rows = await conn.fetch("""
                    SELECT DISTINCT symbol 
                    FROM user_watchlist 
                    ORDER BY symbol
                """)
                symbols = [row['symbol'] for row in rows]
                
                if symbols:
                    logger.info(f"Loaded {len(symbols)} symbols from user_watchlist: {symbols}")
                    return cls(symbols=symbols)
                else:
                    logger.warning("No symbols found in user_watchlist, using env fallback")
                    return cls.from_env()
        except Exception as e:
            logger.error(f"Failed to load watchlist from database: {e}, using env fallback")
            return cls.from_env()


class RecommendationFlowService:
    """
    Service to orchestrate the recommendation generation flow.
    
    Runs on a schedule (every 2 hours) to:
    1. Fetch data from all sources for watchlist stocks
    2. Generate recommendations using ML engine
    3. Persist to database with full details
    4. Cleanup old recommendations (keep last 10 per symbol)
    
    Data Sources:
    - Polygon.io: Real-time prices, news, ticker details
    - IEX Cloud: Quotes, historical prices, key stats
    - Nasdaq Data Link: Historical prices, fundamentals
    - Alpha Vantage: News with sentiment scores
    """
    
    # Schedule interval: 2 hours in seconds
    SCHEDULE_INTERVAL_SECONDS = 2 * 60 * 60  # 7200 seconds
    
    def __init__(
        self,
        postgres_dsn: Optional[str] = None,
        watchlist: Optional[WatchlistConfig] = None,
    ):
        """
        Initialize the recommendation flow service.
        
        Args:
            postgres_dsn: PostgreSQL connection string
            watchlist: Configuration for stocks to analyze
        """
        self.postgres_dsn = postgres_dsn or os.getenv(
            'DATABASE_URL',
            'postgresql://autotrader:autotrader@localhost:5432/autotrader'
        )
        self.watchlist = watchlist or WatchlistConfig.from_env()
        self.engine: Optional[RecommendationEngine] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        self.data_aggregator: Optional[MarketDataAggregator] = None
        self._running = False
    
    async def initialize(self):
        """Initialize database connection, market data aggregator, and recommendation engine."""
        logger.info("Initializing Recommendation Flow Service...")
        
        # Initialize database pool
        try:
            self.db_pool = await asyncpg.create_pool(
                self.postgres_dsn,
                min_size=2,
                max_size=10,
            )
            logger.info("Database pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
        
        # Load watchlist from database (user's actual watchlist from onboarding)
        self.watchlist = await WatchlistConfig.from_database(self.db_pool)
        
        # Initialize market data aggregator with all connectors
        self.data_aggregator = MarketDataAggregator()
        await self.data_aggregator.initialize()
        
        # Initialize recommendation engine
        self.engine = await get_engine()
        logger.info(f"Recommendation engine initialized")
        logger.info(f"Watchlist: {self.watchlist.symbols}")
    
    async def close(self):
        """Clean up resources."""
        if self.data_aggregator:
            await self.data_aggregator.close()
            logger.info("Market data aggregator closed")
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Database pool closed")
    
    async def run_once(self) -> Dict[str, Any]:
        """
        Run a single iteration of the recommendation flow.
        
        This method:
        1. Collects data from all sources (Polygon, IEX, Nasdaq, Alpha Vantage)
        2. Normalizes the data into a unified snapshot
        3. Generates recommendations using the ML engine
        4. Persists recommendations to the database
        5. Cleans up old recommendations (keeps last 10 per symbol)
        
        Returns:
            Dict with execution metrics
        """
        start_time = datetime.utcnow()
        results = {
            'started_at': start_time.isoformat(),
            'symbols_processed': 0,
            'recommendations_generated': 0,
            'data_sources_used': set(),
            'errors': [],
        }
        
        logger.info(f"Starting recommendation flow for {len(self.watchlist.symbols)} symbols")
        
        for idx, symbol in enumerate(self.watchlist.symbols):
            # Add delay between symbols to avoid rate limiting (except for first symbol)
            if idx > 0:
                logger.debug(f"Waiting 5 seconds before processing {symbol} to avoid rate limits...")
                await asyncio.sleep(5)
            
            try:
                # Step 1: Collect data from all sources
                market_snapshot = None
                if self.data_aggregator:
                    market_snapshot = await self.data_aggregator.get_snapshot(symbol)
                    results['data_sources_used'].update(market_snapshot.data_sources)
                    
                    if market_snapshot.errors:
                        for error in market_snapshot.errors:
                            logger.warning(f"Data source error for {symbol}: {error}")
                
                # Step 2: Generate recommendation (engine uses its own data sources + snapshot)
                recommendation = await self.engine.generate_recommendation(
                    symbol=symbol,
                    include_features=True,
                )
                
                # Step 3: Persist to database with enriched data from snapshot
                await self._persist_recommendation(symbol, recommendation, market_snapshot)
                
                results['symbols_processed'] += 1
                results['recommendations_generated'] += 1
                
                # Log with data sources info
                sources_str = ', '.join(market_snapshot.data_sources) if market_snapshot else 'engine-only'
                logger.info(f"Generated {recommendation.action} recommendation for {symbol} "
                           f"(confidence: {recommendation.confidence:.3f}, sources: {sources_str})")
                
            except Exception as e:
                error_msg = f"Failed to process {symbol}: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        # Cleanup old recommendations
        await self._cleanup_old_recommendations()
        
        end_time = datetime.utcnow()
        results['completed_at'] = end_time.isoformat()
        results['duration_seconds'] = (end_time - start_time).total_seconds()
        results['data_sources_used'] = list(results['data_sources_used'])
        
        logger.info(f"Recommendation flow completed in {results['duration_seconds']:.2f}s. "
                   f"Processed: {results['symbols_processed']}, "
                   f"Data sources: {results['data_sources_used']}, "
                   f"Errors: {len(results['errors'])}")
        
        return results
    
    async def _persist_recommendation(
        self, 
        symbol: str, 
        recommendation, 
        market_snapshot: Optional[MarketDataSnapshot] = None
    ) -> None:
        """
        Persist a recommendation to PostgreSQL with enriched market data.
        
        Args:
            symbol: Stock ticker symbol
            recommendation: Recommendation object from engine
            market_snapshot: Optional aggregated market data from all sources
        """
        # Extract component scores from explanation
        explanation = recommendation.explanation
        signals = recommendation.signals
        
        # Get component scores directly from the recommendation object
        news_sentiment_score = recommendation.news_sentiment_score
        news_momentum_score = recommendation.news_momentum_score
        technical_trend_score = recommendation.technical_trend_score
        technical_momentum_score = recommendation.technical_momentum_score
        rsi = recommendation.rsi
        macd_histogram = recommendation.macd_histogram
        price_vs_sma20 = recommendation.price_vs_sma20
        news_sentiment_1d = recommendation.news_sentiment_1d
        article_count_24h = recommendation.article_count_24h or 0
        current_price = recommendation.price_at_recommendation
        
        # Enrich with data from market snapshot (from Polygon, IEX, Nasdaq, Alpha Vantage)
        if market_snapshot:
            # Use snapshot price if engine didn't provide one (check None or 0)
            if current_price is None or current_price == 0:
                current_price = market_snapshot.current_price
            # Fallback to close price
            if (current_price is None or current_price == 0) and market_snapshot.close_price:
                current_price = market_snapshot.close_price
            
            # Use snapshot RSI if available and engine didn't provide
            if rsi is None and market_snapshot.rsi is not None:
                rsi = market_snapshot.rsi
            
            # Use snapshot sentiment if available
            if news_sentiment_score is None and market_snapshot.news_sentiment_avg is not None:
                news_sentiment_score = market_snapshot.news_sentiment_avg
                news_sentiment_1d = market_snapshot.news_sentiment_avg
            
            # Use news count from snapshot
            if market_snapshot.news_count_24h > 0:
                article_count_24h = market_snapshot.news_count_24h
            
            # Calculate price vs SMA20 if we have the data
            if market_snapshot.current_price and market_snapshot.sma_20:
                price_vs_sma20 = (market_snapshot.current_price / market_snapshot.sma_20) - 1
            elif market_snapshot.current_price and market_snapshot.sma_50:
                # Fallback to SMA50 if SMA20 not available
                price_vs_sma20 = (market_snapshot.current_price / market_snapshot.sma_50) - 1
        
        # Use score and normalized_score from the recommendation object
        raw_score = recommendation.score if recommendation.score is not None else 0.0
        normalized_score = recommendation.normalized_score if recommendation.normalized_score is not None else (raw_score + 1) / 2
        
        # Build data sources list - combine engine and aggregator sources
        data_sources = []
        if explanation.get('news'):
            data_sources.append('news_sentiment')
        if explanation.get('technical'):
            data_sources.append('technical_analysis')
        
        # Add market data sources from snapshot
        if market_snapshot and market_snapshot.data_sources:
            for source in market_snapshot.data_sources:
                if source not in data_sources:
                    data_sources.append(source)
        
        # Enrich explanation with snapshot data
        enriched_explanation = dict(explanation)
        if market_snapshot:
            enriched_explanation['market_data'] = {
                'sources': market_snapshot.data_sources,
                'current_price': market_snapshot.current_price,
                'change_percent': market_snapshot.change_percent,
                'volume': market_snapshot.volume,
                'market_cap': market_snapshot.market_cap,
                'pe_ratio': market_snapshot.pe_ratio,
                'week_52_high': market_snapshot.week_52_high,
                'week_52_low': market_snapshot.week_52_low,
                'news_count_24h': market_snapshot.news_count_24h,
                'news_sentiment': market_snapshot.news_sentiment_avg,
            }
        
        # Insert into database
        query = """
            INSERT INTO stock_recommendations (
                symbol, action, score, normalized_score, confidence,
                price_at_recommendation,
                news_sentiment_score, news_momentum_score,
                technical_trend_score, technical_momentum_score,
                rsi, macd_histogram, price_vs_sma20,
                news_sentiment_1d, article_count_24h,
                explanation, data_sources_used, generated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18
            )
        """
        
        import json
        
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                query,
                symbol,
                recommendation.action,
                raw_score,
                normalized_score,
                recommendation.confidence,
                current_price,
                news_sentiment_score,
                news_momentum_score,
                technical_trend_score,
                technical_momentum_score,
                rsi,
                macd_histogram,
                price_vs_sma20,
                news_sentiment_1d,
                article_count_24h,
                json.dumps(enriched_explanation),
                data_sources,
                recommendation.generated_at,
            )
    
    async def _cleanup_old_recommendations(self) -> int:
        """
        Remove old recommendations, keeping only last 10 per symbol.
        
        Returns:
            Number of rows deleted
        """
        query = """
            DELETE FROM stock_recommendations
            WHERE id IN (
                SELECT id FROM (
                    SELECT 
                        id,
                        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY generated_at DESC) as rn
                    FROM stock_recommendations
                ) ranked
                WHERE rn > 10
            )
        """
        
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(query)
            # Parse the result to get count (format: "DELETE N")
            deleted_count = int(result.split()[-1]) if result else 0
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old recommendations")
            
            return deleted_count
    
    def _is_within_trading_hours(self) -> bool:
        """
        Check if current time is within trading hours (6 AM - 1 PM PST).
        
        Returns:
            True if within trading hours, False otherwise.
        """
        from datetime import timezone, timedelta
        
        # PST is UTC-8, PDT is UTC-7. For simplicity, we'll use PST (UTC-8)
        pst = timezone(timedelta(hours=-8))
        now_pst = datetime.now(pst)
        
        hour = now_pst.hour
        is_within = 6 <= hour < 13  # 6 AM to 1 PM (13:00)
        
        logger.info(f"Current PST time: {now_pst.strftime('%Y-%m-%d %H:%M:%S')} - "
                   f"Trading hours (6 AM - 1 PM): {'YES' if is_within else 'NO'}")
        
        return is_within
    
    def _get_seconds_until_trading_hours(self) -> int:
        """
        Calculate seconds until next trading window starts (6 AM PST).
        
        Returns:
            Number of seconds until 6 AM PST.
        """
        from datetime import timezone, timedelta
        
        pst = timezone(timedelta(hours=-8))
        now_pst = datetime.now(pst)
        
        # Calculate next 6 AM PST
        if now_pst.hour >= 13:  # After 1 PM, next window is tomorrow 6 AM
            next_start = now_pst.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
        elif now_pst.hour < 6:  # Before 6 AM, next window is today 6 AM
            next_start = now_pst.replace(hour=6, minute=0, second=0, microsecond=0)
        else:  # During trading hours - shouldn't be called
            return 0
        
        seconds_until = (next_start - now_pst).total_seconds()
        return int(seconds_until)
    
    async def start_scheduled(self):
        """
        Start the scheduled recommendation flow.
        
        Runs every 2 hours, but ONLY during trading hours (6 AM - 1 PM PST).
        Outside of trading hours, the service waits until the next trading window.
        """
        self._running = True
        logger.info(f"Starting scheduled recommendation flow "
                   f"(interval: {self.SCHEDULE_INTERVAL_SECONDS}s / "
                   f"{self.SCHEDULE_INTERVAL_SECONDS / 3600:.1f} hours)")
        logger.info("Trading hours: 6 AM - 1 PM PST (Monday-Sunday)")
        
        while self._running:
            try:
                # Check if within trading hours
                if self._is_within_trading_hours():
                    # Run the flow
                    await self.run_once()
                    
                    # Wait for next interval with periodic heartbeat logging
                    wait_seconds = self.SCHEDULE_INTERVAL_SECONDS
                    heartbeat_interval = 600  # Log heartbeat every 10 minutes
                    
                    logger.info(f"Next run in {wait_seconds / 3600:.1f} hours. Sleeping until next cycle...")
                    
                    elapsed = 0
                    while elapsed < wait_seconds and self._running:
                        sleep_chunk = min(heartbeat_interval, wait_seconds - elapsed)
                        await asyncio.sleep(sleep_chunk)
                        elapsed += sleep_chunk
                        
                        if elapsed < wait_seconds:
                            remaining = (wait_seconds - elapsed) / 60
                            logger.info(f"Heartbeat: {elapsed // 60:.0f} min elapsed, {remaining:.0f} min remaining until next run")
                    
                    logger.info("Sleep completed, starting next recommendation cycle...")
                else:
                    # Outside trading hours - wait until next trading window
                    wait_seconds = self._get_seconds_until_trading_hours()
                    wait_hours = wait_seconds / 3600
                    
                    logger.info(f"Outside trading hours. Waiting {wait_hours:.1f} hours until next trading window (6 AM PST)...")
                    
                    # Sleep until trading hours, with periodic heartbeat
                    heartbeat_interval = 1800  # Log every 30 minutes during off-hours
                    elapsed = 0
                    while elapsed < wait_seconds and self._running:
                        sleep_chunk = min(heartbeat_interval, wait_seconds - elapsed)
                        await asyncio.sleep(sleep_chunk)
                        elapsed += sleep_chunk
                        
                        if elapsed < wait_seconds:
                            remaining_hours = (wait_seconds - elapsed) / 3600
                            logger.info(f"Off-hours heartbeat: {remaining_hours:.1f} hours until trading window opens")
                    
                    logger.info("Trading hours starting, beginning recommendation cycle...")
                
            except asyncio.CancelledError:
                logger.info("Scheduled flow cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduled flow: {e}", exc_info=True)
                # Wait a bit before retrying on error
                await asyncio.sleep(60)
    
    def stop(self):
        """Stop the scheduled flow."""
        self._running = False
        logger.info("Stopping scheduled recommendation flow")


async def get_recommendations_history(
    db_pool: asyncpg.Pool,
    symbol: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Fetch the last N recommendations for a symbol from the database.
    
    Args:
        db_pool: Database connection pool
        symbol: Stock ticker symbol
        limit: Maximum number of recommendations to return (default: 10)
        
    Returns:
        List of recommendation dictionaries
    """
    query = """
        SELECT 
            id, symbol, action, score, normalized_score, confidence,
            price_at_recommendation,
            news_sentiment_score, news_momentum_score,
            technical_trend_score, technical_momentum_score,
            rsi, macd_histogram, price_vs_sma20,
            news_sentiment_1d, article_count_24h,
            explanation, data_sources_used, generated_at, created_at
        FROM stock_recommendations
        WHERE symbol = $1
        ORDER BY generated_at DESC
        LIMIT $2
    """
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, symbol.upper(), limit)
        
        results = []
        for row in rows:
            results.append({
                'id': str(row['id']),
                'symbol': row['symbol'],
                'action': row['action'],
                'score': float(row['score']) if row['score'] else None,
                'normalizedScore': float(row['normalized_score']) if row['normalized_score'] else None,
                'confidence': float(row['confidence']) if row['confidence'] else None,
                'priceAtRecommendation': float(row['price_at_recommendation']) if row['price_at_recommendation'] else None,
                'newsSentimentScore': float(row['news_sentiment_score']) if row['news_sentiment_score'] else None,
                'newsMomentumScore': float(row['news_momentum_score']) if row['news_momentum_score'] else None,
                'technicalTrendScore': float(row['technical_trend_score']) if row['technical_trend_score'] else None,
                'technicalMomentumScore': float(row['technical_momentum_score']) if row['technical_momentum_score'] else None,
                'rsi': float(row['rsi']) if row['rsi'] else None,
                'macdHistogram': float(row['macd_histogram']) if row['macd_histogram'] else None,
                'priceVsSma20': float(row['price_vs_sma20']) if row['price_vs_sma20'] else None,
                'newsSentiment1d': float(row['news_sentiment_1d']) if row['news_sentiment_1d'] else None,
                'articleCount24h': row['article_count_24h'],
                'explanation': row['explanation'],
                'dataSourcesUsed': row['data_sources_used'],
                'generatedAt': row['generated_at'].isoformat() if row['generated_at'] else None,
                'createdAt': row['created_at'].isoformat() if row['created_at'] else None,
            })
        
        return results


# =============================================================================
# Main Entry Point
# =============================================================================

async def main(run_once: bool = False):
    """
    Run the recommendation flow service.
    
    Configuration via environment variables:
    - DATABASE_URL: PostgreSQL connection string
    - WATCHLIST_SYMBOLS: Comma-separated list of stock symbols
    - CLICKHOUSE_HOST: ClickHouse server for news features
    - REDIS_URL: Redis for caching
    
    Args:
        run_once: If True, run once and exit. If False, run on schedule.
    """
    service = RecommendationFlowService()
    
    try:
        await service.initialize()
        
        if run_once:
            logger.info("Running recommendation flow once...")
            result = await service.run_once()
            print(f"\n✅ Recommendation flow complete:")
            print(f"   Symbols processed: {result.get('symbols_processed', 0)}")
            print(f"   Recommendations generated: {result.get('recommendations_generated', 0)}")
            print(f"   Data sources used: {result.get('data_sources_used', set())}")
            if result.get('errors'):
                print(f"   Errors: {len(result.get('errors', []))}")
        else:
            await service.start_scheduled()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        service.stop()
        await service.close()


async def run_http_server():
    """Run the HTTP server for on-demand recommendation generation."""
    from fastapi import FastAPI, BackgroundTasks
    from fastapi.responses import JSONResponse
    import uvicorn
    
    app = FastAPI(title="Recommendation Engine API")
    service = RecommendationFlowService()
    
    @app.on_event("startup")
    async def startup():
        await service.initialize()
        logger.info("HTTP API ready for on-demand recommendation generation")
    
    @app.on_event("shutdown")
    async def shutdown():
        service.stop()
        await service.close()
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    @app.post("/generate")
    async def generate_recommendations(background_tasks: BackgroundTasks):
        """Trigger recommendation generation in the background."""
        background_tasks.add_task(service.run_once)
        return JSONResponse(
            content={"success": True, "message": "Recommendation generation started"},
            status_code=202
        )
    
    @app.post("/generate-sync")
    async def generate_recommendations_sync():
        """Trigger recommendation generation and wait for completion."""
        try:
            result = await service.run_once()
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return JSONResponse(
                content={"success": False, "error": str(e)},
                status_code=500
            )
    
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_with_api():
    """Run both the scheduled service and HTTP API concurrently."""
    service = RecommendationFlowService()
    
    try:
        await service.initialize()
        
        # Run HTTP API in background task
        from fastapi import FastAPI, BackgroundTasks
        from fastapi.responses import JSONResponse
        import uvicorn
        
        app = FastAPI(title="Recommendation Engine API")
        
        @app.get("/health")
        async def health():
            return {"status": "healthy", "running": service._running}
        
        @app.post("/generate")
        async def generate_recommendations(background_tasks: BackgroundTasks):
            """Trigger recommendation generation in the background."""
            background_tasks.add_task(service.run_once)
            return JSONResponse(
                content={"success": True, "message": "Recommendation generation started"},
                status_code=202
            )
        
        # Run both the scheduler and HTTP server
        async def run_scheduler():
            await service.start_scheduled()
        
        async def run_api():
            config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
            server = uvicorn.Server(config)
            await server.serve()
        
        await asyncio.gather(
            run_scheduler(),
            run_api(),
        )
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        service.stop()
        await service.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Recommendation Flow Service')
    parser.add_argument('--once', action='store_true', help='Run once and exit (default: run on schedule)')
    parser.add_argument('--api', action='store_true', help='Run with HTTP API for on-demand generation')
    args = parser.parse_args()
    
    if args.once:
        asyncio.run(main(run_once=True))
    elif args.api:
        asyncio.run(run_with_api())
    else:
        asyncio.run(main(run_once=False))

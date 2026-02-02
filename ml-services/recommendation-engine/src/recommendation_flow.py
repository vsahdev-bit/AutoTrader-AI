"""
Recommendation Flow Service
============================

Scheduled service that runs at fixed times (7:30 AM and 12:00 PM PST daily) to:
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
import signal
import time
import asyncio
import asyncpg
import json
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
    from .main import (
        RecommendationEngine, get_engine,
        RegimeInfo, SignalWeightsInfo, PositionSizingInfo, StopLossInfo
    )
    from .news_features import NewsFeatureProvider
    from .technical_features import TechnicalFeatureProvider
    from .regime_classifier import RegimeClassifier
except ImportError:
    from main import (
        RecommendationEngine, get_engine,
        RegimeInfo, SignalWeightsInfo, PositionSizingInfo, StopLossInfo
    )
    from news_features import NewsFeatureProvider
    from technical_features import TechnicalFeatureProvider
    from regime_classifier import RegimeClassifier

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
    
    Runs on a fixed schedule (7:30 AM & 12:00 PM PST daily) to:
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
    # Fixed schedule times in PST (hour, minute)
    SCHEDULED_RUN_TIMES = [(7, 30), (12, 0)]  # 7:30 AM PST and 12:00 PM PST
    
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
    
    async def generate_single_recommendation(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Generate a recommendation for a single symbol on-demand.
        
        This is used for the "Get Recommendation" feature where users can
        look up any stock without adding it to their watchlist.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dict with recommendation data or None if generation fails
        """
        symbol = symbol.upper().strip()
        logger.info(f"Generating on-demand recommendation for {symbol}")
        
        try:
            # Ensure engine is initialized
            if self.engine is None:
                from main import RecommendationEngine
                self.engine = RecommendationEngine(enable_regime=True)
                await self.engine.initialize()
            
            # Generate recommendation using the engine
            recommendation = await self.engine.generate_recommendation(
                symbol=symbol,
                include_features=True,
            )
            
            # Convert recommendation to dict
            def _maybe_dict(obj):
                try:
                    if obj is None:
                        return None
                    if hasattr(obj, 'dict'):
                        return obj.dict()
                    if hasattr(obj, '__dict__'):
                        return dict(obj.__dict__)
                    return obj
                except Exception:
                    return None

            return {
                "symbol": symbol,
                # legacy combined
                "action": recommendation.action,
                "confidence": recommendation.confidence,
                "normalized_score": recommendation.normalized_score,
                "score": recommendation.score,
                # split tracks
                "news_action": getattr(recommendation, 'news_action', None),
                "news_confidence": getattr(recommendation, 'news_confidence', None),
                "news_normalized_score": getattr(recommendation, 'news_normalized_score', None),
                "technical_action": getattr(recommendation, 'technical_action', None),
                "technical_confidence": getattr(recommendation, 'technical_confidence', None),
                "technical_normalized_score": getattr(recommendation, 'technical_normalized_score', None),
                # raw components
                "news_sentiment_score": recommendation.news_sentiment_score,
                "news_momentum_score": recommendation.news_momentum_score,
                "technical_trend_score": recommendation.technical_trend_score,
                "technical_momentum_score": recommendation.technical_momentum_score,
                "price_at_recommendation": recommendation.price_at_recommendation,
                "rsi": recommendation.rsi,
                "macd_histogram": recommendation.macd_histogram,
                "explanation": recommendation.explanation,
                # Include regime + signal weights so the UI can match StockRecommendations
                "regime": _maybe_dict(getattr(recommendation, 'regime', None)),
                "signal_weights": _maybe_dict(getattr(recommendation, 'signal_weights', None)),
                "generated_at": recommendation.generated_at.isoformat() if recommendation.generated_at else datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Error generating on-demand recommendation for {symbol}: {e}")
            return None
    
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
                symbol,
                -- legacy combined
                action, score, normalized_score, confidence,
                -- split tracks
                news_action, news_normalized_score, news_confidence,
                technical_action, technical_normalized_score, technical_confidence,
                -- features
                price_at_recommendation,
                news_sentiment_score, news_momentum_score,
                technical_trend_score, technical_momentum_score,
                rsi, macd_histogram, price_vs_sma20,
                news_sentiment_1d, article_count_24h,
                explanation, data_sources_used, generated_at
            ) VALUES (
                $1,
                $2, $3, $4, $5,
                $6, $7, $8,
                $9, $10, $11,
                $12,
                $13, $14,
                $15, $16,
                $17, $18, $19,
                $20, $21,
                $22, $23, $24
            )
        """
        
        import json
        
        import math

        def _db_float(v, *, min_value=None, max_value=None):
            if v is None:
                return None
            try:
                n = float(v)
            except Exception:
                return None
            if not math.isfinite(n):
                return None
            if min_value is not None:
                n = max(min_value, n)
            if max_value is not None:
                n = min(max_value, n)
            return n

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                query,
                symbol,
                # legacy combined
                recommendation.action,
                _db_float(raw_score, min_value=-1.0, max_value=1.0),
                _db_float(normalized_score, min_value=0.0, max_value=1.0),
                _db_float(recommendation.confidence, min_value=0.0, max_value=1.0),
                # split tracks
                getattr(recommendation, 'news_action', None),
                _db_float(getattr(recommendation, 'news_normalized_score', None), min_value=0.0, max_value=1.0),
                _db_float(getattr(recommendation, 'news_confidence', None), min_value=0.0, max_value=1.0),
                getattr(recommendation, 'technical_action', None),
                _db_float(getattr(recommendation, 'technical_normalized_score', None), min_value=0.0, max_value=1.0),
                _db_float(getattr(recommendation, 'technical_confidence', None), min_value=0.0, max_value=1.0),
                # features
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
    
    def _get_next_scheduled_run(self) -> tuple:
        """
        Calculate the next scheduled run time.
        
        The service runs at fixed times: 7:30 AM PST and 12:00 PM PST daily.
        
        Returns:
            Tuple of (seconds_until_next_run, next_run_time_str, should_run_now)
            - seconds_until_next_run: Number of seconds until the next scheduled run
            - next_run_time_str: String representation of next run time in PST
            - should_run_now: True if we're within 1 minute of a scheduled time
        """
        from datetime import timezone, timedelta
        
        # PST is UTC-8, PDT is UTC-7. For simplicity, we'll use PST (UTC-8)
        pst = timezone(timedelta(hours=-8))
        now_pst = datetime.now(pst)
        
        logger.info(f"Current PST time: {now_pst.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Find the next scheduled run time
        candidates = []
        
        for hour, minute in self.SCHEDULED_RUN_TIMES:
            # Check today's scheduled time
            scheduled_today = now_pst.replace(hour=hour, minute=minute, second=0, microsecond=0)
            time_diff = (scheduled_today - now_pst).total_seconds()
            
            if time_diff > -60:  # Within 1 minute past or in the future
                candidates.append((time_diff, scheduled_today))
            
            # Also add tomorrow's time as a candidate
            scheduled_tomorrow = scheduled_today + timedelta(days=1)
            time_diff_tomorrow = (scheduled_tomorrow - now_pst).total_seconds()
            candidates.append((time_diff_tomorrow, scheduled_tomorrow))
        
        # Sort by time difference and get the nearest future (or current) run
        candidates.sort(key=lambda x: x[0])
        
        # Find first candidate that's not too far in the past
        for time_diff, scheduled_time in candidates:
            if time_diff >= -60:  # Allow up to 1 minute past
                should_run_now = -60 <= time_diff <= 60  # Within 1 minute window
                seconds_until = max(0, int(time_diff))
                time_str = scheduled_time.strftime('%Y-%m-%d %H:%M PST')
                return (seconds_until, time_str, should_run_now)
        
        # Fallback (shouldn't happen)
        return (0, now_pst.strftime('%Y-%m-%d %H:%M PST'), True)
    
    async def start_scheduled(self):
        """
        Start the scheduled recommendation flow.
        
        Runs at fixed times daily: 7:30 AM PST and 12:00 PM PST.
        """
        self._running = True
        schedule_times_str = ", ".join([f"{h}:{m:02d} AM PST" if h < 12 else f"{h}:00 PM PST" 
                                        for h, m in self.SCHEDULED_RUN_TIMES])
        logger.info(f"Starting scheduled recommendation flow")
        logger.info(f"Fixed schedule: {schedule_times_str} (daily)")
        
        while self._running:
            try:
                # Get next scheduled run time
                seconds_until, next_run_str, should_run_now = self._get_next_scheduled_run()
                
                if should_run_now:
                    # It's time to run
                    logger.info(f"Scheduled run time reached: {next_run_str}")
                    await self.run_once()
                    
                    # After running, wait a bit to avoid re-triggering within the same minute
                    await asyncio.sleep(90)
                else:
                    # Wait until the next scheduled time
                    wait_hours = seconds_until / 3600
                    wait_minutes = seconds_until / 60
                    
                    if wait_hours >= 1:
                        logger.info(f"Next scheduled run: {next_run_str} ({wait_hours:.1f} hours from now)")
                    else:
                        logger.info(f"Next scheduled run: {next_run_str} ({wait_minutes:.0f} minutes from now)")
                    
                    # Sleep until next scheduled time using wall-clock time
                    start_time = time.time()
                    target_time = start_time + seconds_until
                    heartbeat_interval = 1800  # Log every 30 minutes
                    
                    while time.time() < target_time and self._running:
                        remaining_seconds = target_time - time.time()
                        if remaining_seconds <= 0:
                            break
                        
                        sleep_chunk = min(heartbeat_interval, remaining_seconds)
                        await asyncio.sleep(sleep_chunk)
                        
                        # Log heartbeat
                        remaining_seconds = target_time - time.time()
                        if remaining_seconds > 60 and self._running:
                            remaining_hours = remaining_seconds / 3600
                            remaining_minutes = remaining_seconds / 60
                            if remaining_hours >= 1:
                                logger.info(f"Heartbeat: {remaining_hours:.1f} hours until next scheduled run ({next_run_str})")
                            else:
                                logger.info(f"Heartbeat: {remaining_minutes:.0f} minutes until next scheduled run ({next_run_str})")
                
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
                'newsSentimentScore': float(row['news_sentiment_score']) if row['news_sentiment_score'] is not None else None,
                'newsMomentumScore': float(row['news_momentum_score']) if row['news_momentum_score'] is not None else None,
                'technicalTrendScore': float(row['technical_trend_score']) if row['technical_trend_score'] is not None else None,
                'technicalMomentumScore': float(row['technical_momentum_score']) if row['technical_momentum_score'] is not None else None,
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
    - ENABLE_TRADING_HOURS_CHECK: Set to 'false' to run 24/7 (default: 'true')
    - SCHEDULED_RUN_TIMES: Fixed times for daily runs (default: 7:30 AM and 12:00 PM PST)
    
    Args:
        run_once: If True, run once and exit. If False, run on schedule.
    """
    service = RecommendationFlowService()
    
    # Set up signal handlers for graceful shutdown
    def handle_signal(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} signal, initiating graceful shutdown...")
        service.stop()
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
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
            logger.info("Recommendation service starting in scheduled mode...")
            await service.start_scheduled()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
    finally:
        service.stop()
        logger.info("Recommendation service shutdown complete")
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

    @app.post("/recommendations")
    async def generate_recommendations_sync(request: dict):
        """Synchronous batch recommendation generation (used by api-gateway).

        Request body:
          - user_id: string
          - symbols: list[string]
          - include_features: bool (optional)
          - save_to_db: bool (optional)

        Generates recommendations for the given symbols and optionally persists
        them into Postgres (stock_recommendations).
        """
        user_id = request.get("user_id", "system")
        symbols = request.get("symbols") or []
        include_features = bool(request.get("include_features", False))
        save_to_db = bool(request.get("save_to_db", False))

        if not isinstance(symbols, list) or len(symbols) == 0:
            return JSONResponse(content={"error": "symbols must be a non-empty list"}, status_code=400)

        # Ensure service is initialized
        if service.engine is None:
            await service.initialize()

        recs = []

        async def _save_to_db(symbol: str, rec_obj) -> None:
            if not service.db_pool:
                return
            # Insert minimal record required by schema
            await service.db_pool.execute(
                """
                INSERT INTO stock_recommendations (
                    symbol,
                    -- legacy combined
                    action, score, normalized_score, confidence,
                    -- split tracks
                    news_action, news_normalized_score, news_confidence,
                    technical_action, technical_normalized_score, technical_confidence,
                    -- features
                    price_at_recommendation,
                    news_sentiment_score, news_momentum_score,
                    technical_trend_score, technical_momentum_score,
                    rsi, macd_histogram, price_vs_sma20,
                    news_sentiment_1d, article_count_24h,
                    explanation, data_sources_used, generated_at
                ) VALUES (
                    $1,
                    $2,$3,$4,$5,
                    $6,$7,$8,
                    $9,$10,$11,
                    $12,
                    $13,$14,
                    $15,$16,
                    $17,$18,$19,
                    $20,$21,
                    $22,$23,NOW()
                )
                """,
                symbol,
                rec_obj.action,
                float(rec_obj.score) if rec_obj.score is not None else 0.0,
                float(rec_obj.normalized_score) if rec_obj.normalized_score is not None else 0.5,
                float(rec_obj.confidence) if rec_obj.confidence is not None else 0.0,
                getattr(rec_obj, 'news_action', None),
                getattr(rec_obj, 'news_normalized_score', None),
                getattr(rec_obj, 'news_confidence', None),
                getattr(rec_obj, 'technical_action', None),
                getattr(rec_obj, 'technical_normalized_score', None),
                getattr(rec_obj, 'technical_confidence', None),
                rec_obj.price_at_recommendation,
                rec_obj.news_sentiment_score,
                rec_obj.news_momentum_score,
                rec_obj.technical_trend_score,
                rec_obj.technical_momentum_score,
                rec_obj.rsi,
                rec_obj.macd_histogram,
                rec_obj.price_vs_sma20,
                rec_obj.news_sentiment_1d,
                rec_obj.article_count_24h or 0,
                json.dumps(rec_obj.explanation) if rec_obj.explanation else None,
                ['news', 'technical'],
            )

        for s in symbols:
            sym = str(s).upper().strip()
            try:
                rec_obj = await service.engine.generate_recommendation(symbol=sym, include_features=include_features)
                if save_to_db:
                    try:
                        await _save_to_db(sym, rec_obj)
                    except Exception as e:
                        logger.warning(f"Failed to persist {sym} (batch): {e}")

                recs.append(rec_obj.dict() if hasattr(rec_obj, 'dict') else rec_obj)
            except Exception as e:
                logger.error(f"Batch generation failed for {sym}: {e}")
                recs.append({
                    "symbol": sym,
                    "action": "HOLD",
                    "confidence": 0.0,
                    "score": 0.0,
                    "normalized_score": 0.5,
                    "explanation": {"summary": f"Unable to analyze {sym}", "error": str(e)},
                })

        return {
            "user_id": user_id,
            "recommendations": recs,
            "generated_at": datetime.utcnow().isoformat(),
        }
    
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
    
    @app.post("/generate/single")
    async def generate_single_recommendation(request: dict):
        """
        Generate an on-demand recommendation for a single stock.
        
        This endpoint is used for instant recommendations without saving to database.
        Useful for one-off lookups and the "Get Recommendation" feature.
        
        Request body:
            symbol: Stock ticker symbol (required)
            company_name: Company name (optional)
            save_to_db: Whether to save to database (default: False)
        
        Returns:
            Recommendation object with all scores and explanation
        """
        symbol = request.get("symbol", "").upper().strip()
        company_name = request.get("company_name", symbol)
        save_to_db = request.get("save_to_db", False)
        
        if not symbol:
            return JSONResponse(
                content={"error": "symbol is required"},
                status_code=400
            )
        
        logger.info(f"On-demand recommendation requested for {symbol}")
        
        try:
            # Generate recommendation using the service
            recommendation = await service.generate_single_recommendation(symbol)
            
            if recommendation is None:
                return JSONResponse(
                    content={"error": f"Failed to generate recommendation for {symbol}"},
                    status_code=500
                )
            
            # Optionally save to database
            if save_to_db and service.db_pool:
                try:
                    await service.save_recommendation(recommendation)
                    logger.info(f"Saved recommendation for {symbol} to database")
                except Exception as e:
                    logger.warning(f"Failed to save recommendation to database: {e}")
            
            # Return the recommendation
            return {
                "symbol": symbol,
                "company_name": company_name,
                "action": recommendation.get("action", "HOLD"),
                "confidence": recommendation.get("confidence", 0),
                "normalized_score": recommendation.get("normalized_score", 0),
                "score": recommendation.get("score", 0),
                "news_sentiment_score": recommendation.get("news_sentiment_score"),
                "news_momentum_score": recommendation.get("news_momentum_score"),
                "technical_trend_score": recommendation.get("technical_trend_score"),
                "technical_momentum_score": recommendation.get("technical_momentum_score"),
                "price_at_recommendation": recommendation.get("price_at_recommendation"),
                "rsi": recommendation.get("rsi"),
                "macd_histogram": recommendation.get("macd_histogram"),
                "explanation": recommendation.get("explanation"),
                "generated_at": recommendation.get("generated_at", datetime.now(timezone.utc).isoformat()),
            }
            
        except Exception as e:
            logger.error(f"Error generating recommendation for {symbol}: {e}")
            return JSONResponse(
                content={"error": str(e)},
                status_code=500
            )
    
    @app.get("/regime/{symbol}")
    async def get_regime(symbol: str):
        """
        Get the current market regime classification for a symbol.
        
        Returns regime classification across 4 dimensions:
        - Volatility: low / normal / high / extreme
        - Trend: strong_uptrend / uptrend / mean_reverting / choppy / downtrend / strong_downtrend
        - Liquidity: high / normal / thin / illiquid
        - Information: quiet / normal / news_driven / social_driven / earnings
        
        Also returns:
        - Signal weights optimized for current regime
        - Position sizing recommendations
        - Stop-loss recommendations
        """
        symbol = symbol.upper()
        
        try:
            engine = await get_engine()
            
            # Get features for regime classification
            news_features = None
            if engine.news_provider:
                try:
                    news_features = await engine.news_provider.get_features_single(symbol)
                except Exception as e:
                    logger.warning(f"Failed to get news features for {symbol}: {e}")
            
            technical_features = None
            if engine.technical_provider:
                try:
                    technical_features = await engine.technical_provider.get_features(symbol)
                except Exception as e:
                    logger.warning(f"Failed to get technical features for {symbol}: {e}")
            
            # Classify regime
            if not engine.regime_classifier:
                return JSONResponse(
                    content={"error": "Regime classification not available"},
                    status_code=503
                )
            
            regime_state = engine.regime_classifier.classify(
                symbol=symbol,
                technical_features=technical_features,
                news_features=news_features,
            )
            
            regime_weights = engine.regime_classifier.get_signal_weights(regime_state)
            regime_explanation = engine.regime_classifier.get_regime_explanation(regime_state)
            
            # Build response
            regime_info = {
                "regime_label": regime_explanation.get("regime_label", "Unknown"),
                "risk_level": regime_explanation.get("risk_level", "normal"),
                "volatility": regime_state.volatility.value,
                "trend": regime_state.trend.value,
                "liquidity": regime_state.liquidity.value,
                "information": regime_state.information.value,
                "risk_score": round(regime_state.regime_risk_score, 3),
                "regime_confidence": round(regime_state.regime_confidence, 3),
                "warnings": regime_explanation.get("warnings", []),
                "explanations": regime_explanation.get("explanations", []),
            }
            
            signal_weights_info = {
                "news_sentiment": round(regime_weights.news_sentiment, 4),
                "news_momentum": round(regime_weights.news_momentum, 4),
                "technical_trend": round(regime_weights.technical_trend, 4),
                "technical_momentum": round(regime_weights.technical_momentum, 4),
                "confidence_multiplier": round(regime_weights.confidence_multiplier, 3),
                "trade_frequency_modifier": round(regime_weights.trade_frequency_modifier, 3),
            }
            
            # Add position sizing info
            if regime_weights.position_sizing:
                ps = regime_weights.position_sizing
                signal_weights_info["position_sizing"] = {
                    "size_multiplier": round(ps.size_multiplier, 3),
                    "max_position_percent": round(ps.max_position_percent, 2),
                    "scale_in_entries": ps.scale_in_entries,
                    "scale_in_interval_hours": ps.scale_in_interval_hours,
                    "risk_per_trade_percent": round(ps.risk_per_trade_percent, 3),
                    "reasoning": ps.reasoning,
                }
            
            # Add stop-loss info
            if regime_weights.stop_loss:
                sl = regime_weights.stop_loss
                signal_weights_info["stop_loss"] = {
                    "atr_multiplier": round(sl.atr_multiplier, 2),
                    "percent_from_entry": round(sl.percent_from_entry, 2),
                    "use_trailing_stop": sl.use_trailing_stop,
                    "trailing_activation_percent": round(sl.trailing_activation_percent, 2),
                    "take_profit_atr_multiplier": round(sl.take_profit_atr_multiplier, 2),
                    "risk_reward_ratio": round(sl.risk_reward_ratio, 2),
                    "time_stop_days": sl.time_stop_days,
                    "reasoning": sl.reasoning,
                }
            
            return {
                "symbol": symbol,
                "regime": regime_info,
                "signal_weights": signal_weights_info,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to get regime for {symbol}: {e}")
            return JSONResponse(
                content={"error": str(e)},
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

        @app.post("/recommendations")
        async def generate_recommendations_sync(request: dict):
            """Synchronous batch recommendation generation (used by api-gateway).

            See run_http_server() version for docs. This is duplicated here because
            the production container runs run_with_api().
            """
            user_id = request.get("user_id", "system")
            symbols = request.get("symbols") or []
            include_features = bool(request.get("include_features", False))
            save_to_db = bool(request.get("save_to_db", False))

            if not isinstance(symbols, list) or len(symbols) == 0:
                return JSONResponse(content={"error": "symbols must be a non-empty list"}, status_code=400)

            if service.engine is None:
                await service.initialize()

            recs = []

            async def _save_to_db(symbol: str, rec_obj) -> None:
                if not service.db_pool:
                    return
                await service.db_pool.execute(
                    """
                    INSERT INTO stock_recommendations (
                        symbol,
                        -- legacy combined
                        action, score, normalized_score, confidence,
                        -- split tracks
                        news_action, news_normalized_score, news_confidence,
                        technical_action, technical_normalized_score, technical_confidence,
                        -- features
                        price_at_recommendation,
                        news_sentiment_score, news_momentum_score,
                        technical_trend_score, technical_momentum_score,
                        rsi, macd_histogram, price_vs_sma20,
                        news_sentiment_1d, article_count_24h,
                        explanation, data_sources_used, generated_at
                    ) VALUES (
                        $1,
                        $2,$3,$4,$5,
                        $6,$7,$8,
                        $9,$10,$11,
                        $12,
                        $13,$14,
                        $15,$16,
                        $17,$18,$19,
                        $20,$21,
                        $22,$23,NOW()
                    )
                    """,
                    symbol,
                    rec_obj.action,
                    float(rec_obj.score) if rec_obj.score is not None else 0.0,
                    float(rec_obj.normalized_score) if rec_obj.normalized_score is not None else 0.5,
                    float(rec_obj.confidence) if rec_obj.confidence is not None else 0.0,
                    getattr(rec_obj, 'news_action', None),
                    getattr(rec_obj, 'news_normalized_score', None),
                    getattr(rec_obj, 'news_confidence', None),
                    getattr(rec_obj, 'technical_action', None),
                    getattr(rec_obj, 'technical_normalized_score', None),
                    getattr(rec_obj, 'technical_confidence', None),
                    rec_obj.price_at_recommendation,
                    rec_obj.news_sentiment_score,
                    rec_obj.news_momentum_score,
                    rec_obj.technical_trend_score,
                    rec_obj.technical_momentum_score,
                    rec_obj.rsi,
                    rec_obj.macd_histogram,
                    rec_obj.price_vs_sma20,
                    rec_obj.news_sentiment_1d,
                    rec_obj.article_count_24h or 0,
                    json.dumps(rec_obj.explanation) if rec_obj.explanation else None,
                    ['news', 'technical'],
                )

            for s in symbols:
                sym = str(s).upper().strip()
                try:
                    rec_obj = await service.engine.generate_recommendation(symbol=sym, include_features=include_features)
                    if save_to_db:
                        try:
                            await _save_to_db(sym, rec_obj)
                        except Exception as e:
                            logger.warning(f"Failed to persist {sym} (batch): {e}")

                    recs.append(rec_obj.dict() if hasattr(rec_obj, 'dict') else rec_obj)
                except Exception as e:
                    logger.error(f"Batch generation failed for {sym}: {e}")
                    recs.append({
                        "symbol": sym,
                        "action": "HOLD",
                        "confidence": 0.0,
                        "score": 0.0,
                        "normalized_score": 0.5,
                        "explanation": {"summary": f"Unable to analyze {sym}", "error": str(e)},
                    })

            return {
                "user_id": user_id,
                "recommendations": recs,
                "generated_at": datetime.utcnow().isoformat(),
            }
        
        def _sanitize_for_json(obj):
            """Recursively replace NaN/Inf with None so JSON serialization never fails."""
            import math
            if obj is None:
                return None
            if isinstance(obj, float):
                return obj if math.isfinite(obj) else None
            if isinstance(obj, dict):
                return {k: _sanitize_for_json(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_sanitize_for_json(v) for v in obj]
            return obj

        @app.post("/generate/single")
        async def generate_single(request: dict):
            """Generate on-demand recommendation for a single stock."""
            symbol = request.get("symbol", "").upper().strip()
            company_name = request.get("company_name", symbol)
            
            if not symbol:
                return JSONResponse(content={"error": "symbol is required"}, status_code=400)
            
            logger.info(f"On-demand recommendation requested for {symbol}")
            
            try:
                recommendation = await service.generate_single_recommendation(symbol)
                
                if recommendation is None:
                    return JSONResponse(
                        content={"error": f"Failed to generate recommendation for {symbol}"},
                        status_code=500
                    )
                
                payload = {
                    "symbol": symbol,
                    "company_name": company_name,
                    "action": recommendation.get("action", "HOLD"),
                    "confidence": recommendation.get("confidence", 0),
                    "normalized_score": recommendation.get("normalized_score", 0),
                    # Include raw score for parity with stored recommendations
                    "score": recommendation.get("score"),
                    "news_sentiment_score": recommendation.get("news_sentiment_score"),
                    "news_momentum_score": recommendation.get("news_momentum_score"),
                    "technical_trend_score": recommendation.get("technical_trend_score"),
                    # Do not default to 0 if missing; allow null to show "-" in UI
                    "technical_momentum_score": recommendation.get("technical_momentum_score"),
                    "price_at_recommendation": recommendation.get("price_at_recommendation"),
                    "explanation": recommendation.get("explanation"),
                    # Pass through regime + signal weights if available
                    "regime": recommendation.get("regime"),
                    "signal_weights": recommendation.get("signal_weights"),
                    "generated_at": recommendation.get("generated_at"),
                }
                return _sanitize_for_json(payload)
            except Exception as e:
                logger.error(f"Error generating recommendation for {symbol}: {e}")
                return JSONResponse(content={"error": str(e)}, status_code=500)
        
        @app.get("/regime/{symbol}")
        async def get_regime_api(symbol: str):
            """Get regime classification for a symbol."""
            symbol = symbol.upper()
            try:
                engine = await get_engine()
                
                news_features = None
                if engine.news_provider:
                    try:
                        news_features = await engine.news_provider.get_features_single(symbol)
                    except Exception as e:
                        logger.warning(f"Failed to get news features for {symbol}: {e}")
                
                technical_features = None
                if engine.technical_provider:
                    try:
                        technical_features = await engine.technical_provider.get_features(symbol)
                    except Exception as e:
                        logger.warning(f"Failed to get technical features for {symbol}: {e}")
                
                if not engine.regime_classifier:
                    return JSONResponse(content={"error": "Regime not available"}, status_code=503)
                
                regime_state = engine.regime_classifier.classify(symbol, technical_features, news_features)
                regime_weights = engine.regime_classifier.get_signal_weights(regime_state)
                regime_explanation = engine.regime_classifier.get_regime_explanation(regime_state)
                
                response = {
                    "symbol": symbol,
                    "regime": {
                        "label": regime_explanation.get("regime_label"),
                        "risk_level": regime_explanation.get("risk_level"),
                        "volatility": regime_state.volatility.value,
                        "trend": regime_state.trend.value,
                        "liquidity": regime_state.liquidity.value,
                        "information": regime_state.information.value,
                        "risk_score": round(regime_state.regime_risk_score, 3),
                        "warnings": regime_explanation.get("warnings", []),
                    },
                    "signal_weights": {
                        "news_sentiment": round(regime_weights.news_sentiment, 4),
                        "news_momentum": round(regime_weights.news_momentum, 4),
                        "technical_trend": round(regime_weights.technical_trend, 4),
                        "technical_momentum": round(regime_weights.technical_momentum, 4),
                        "confidence_multiplier": round(regime_weights.confidence_multiplier, 3),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                if regime_weights.position_sizing:
                    ps = regime_weights.position_sizing
                    response["position_sizing"] = {
                        "size_multiplier": round(ps.size_multiplier, 3),
                        "max_position_percent": round(ps.max_position_percent, 2),
                        "scale_in_entries": ps.scale_in_entries,
                        "reasoning": ps.reasoning,
                    }
                
                if regime_weights.stop_loss:
                    sl = regime_weights.stop_loss
                    response["stop_loss"] = {
                        "atr_multiplier": round(sl.atr_multiplier, 2),
                        "percent_from_entry": round(sl.percent_from_entry, 2),
                        "use_trailing_stop": sl.use_trailing_stop,
                        "risk_reward_ratio": round(sl.risk_reward_ratio, 2),
                        "reasoning": sl.reasoning,
                    }
                
                return response
            except Exception as e:
                logger.error(f"Failed to get regime for {symbol}: {e}")
                return JSONResponse(content={"error": str(e)}, status_code=500)
        
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

"""
Price Data Provider
===================

This module provides price data fetching and management for technical
analysis. It supports multiple data sources and caches data for efficiency.

Supported Data Sources:
- Yahoo Finance (free, good coverage)
- Alpha Vantage (requires API key)
- Financial Modeling Prep (requires API key)

Features:
- Historical OHLCV data
- Real-time quotes
- Multi-symbol batch fetching
- Redis caching for efficiency
- Automatic data validation
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any
import asyncio
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PriceBar:
    """Single price bar (candle) data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass  
class Quote:
    """Real-time quote data."""
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class PriceDataProvider:
    """
    Provider for historical and real-time price data.
    
    Fetches data from Yahoo Finance (default) with caching support.
    
    Example Usage:
        provider = PriceDataProvider()
        await provider.initialize()
        
        # Get historical data as DataFrame
        df = await provider.get_historical("AAPL", period="1mo")
        
        # Get real-time quote
        quote = await provider.get_quote("AAPL")
        
        # Get data for multiple symbols
        data = await provider.get_historical_multi(
            ["AAPL", "GOOGL", "MSFT"],
            period="3mo"
        )
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = "redis://localhost:6379",
        cache_ttl_minutes: int = 5,
    ):
        """
        Initialize price data provider.
        
        Args:
            redis_url: Redis URL for caching (None to disable)
            cache_ttl_minutes: Cache TTL for price data
        """
        self.redis_url = redis_url
        self.cache_ttl = cache_ttl_minutes * 60
        self.redis_client = None
        self._session = None
    
    async def initialize(self):
        """Initialize connections."""
        # Initialize Redis cache
        if self.redis_url:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(
                    self.redis_url, 
                    decode_responses=True
                )
                await self.redis_client.ping()
                logger.info("Price data cache initialized")
            except Exception as e:
                logger.warning(f"Redis not available for caching: {e}")
                self.redis_client = None
        
        # Initialize HTTP session
        import aiohttp
        self._session = aiohttp.ClientSession()
    
    async def close(self):
        """Close connections."""
        if self._session:
            await self._session.close()
        if self.redis_client:
            await self.redis_client.close()
    
    async def get_historical(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo)
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        # Check cache first
        cache_key = f"price:{symbol}:{period}:{interval}"
        
        if self.redis_client:
            cached = await self._get_cached(cache_key)
            if cached is not None:
                return cached
        
        # Fetch from Yahoo Finance
        data = await self._fetch_yahoo(symbol, period, interval)
        
        # Cache the result
        if self.redis_client and not data.empty:
            await self._cache_dataframe(cache_key, data)
        
        return data
    
    async def get_historical_multi(
        self,
        symbols: List[str],
        period: str = "1mo",
        interval: str = "1d",
    ) -> Dict[str, pd.DataFrame]:
        """
        Get historical data for multiple symbols concurrently.
        
        Args:
            symbols: List of stock symbols
            period: Time period
            interval: Data interval
            
        Returns:
            Dict mapping symbol to DataFrame
        """
        tasks = [
            self.get_historical(symbol, period, interval)
            for symbol in symbols
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        data = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {symbol}: {result}")
                data[symbol] = pd.DataFrame()
            else:
                data[symbol] = result
        
        return data
    
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        """
        Get real-time quote for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Quote object or None if failed
        """
        url = f"https://query1.finance.yahoo.com/v7/finance/quote"
        params = {
            "symbols": symbol,
            "fields": "regularMarketPrice,regularMarketChange,regularMarketChangePercent,regularMarketVolume,marketCap",
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                results = data.get("quoteResponse", {}).get("result", [])
                
                if not results:
                    return None
                
                r = results[0]
                return Quote(
                    symbol=symbol,
                    price=r.get("regularMarketPrice", 0),
                    change=r.get("regularMarketChange", 0),
                    change_percent=r.get("regularMarketChangePercent", 0),
                    volume=r.get("regularMarketVolume", 0),
                    market_cap=r.get("marketCap"),
                )
                
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return None
    
    async def get_quotes_multi(
        self,
        symbols: List[str],
    ) -> Dict[str, Quote]:
        """Get quotes for multiple symbols."""
        url = f"https://query1.finance.yahoo.com/v7/finance/quote"
        params = {
            "symbols": ",".join(symbols),
            "fields": "regularMarketPrice,regularMarketChange,regularMarketChangePercent,regularMarketVolume,marketCap",
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    return {}
                
                data = await response.json()
                results = data.get("quoteResponse", {}).get("result", [])
                
                quotes = {}
                for r in results:
                    symbol = r.get("symbol", "")
                    quotes[symbol] = Quote(
                        symbol=symbol,
                        price=r.get("regularMarketPrice", 0),
                        change=r.get("regularMarketChange", 0),
                        change_percent=r.get("regularMarketChangePercent", 0),
                        volume=r.get("regularMarketVolume", 0),
                        market_cap=r.get("marketCap"),
                    )
                
                return quotes
                
        except Exception as e:
            logger.error(f"Failed to get quotes: {e}")
            return {}
    
    async def _fetch_yahoo(
        self,
        symbol: str,
        period: str,
        interval: str,
    ) -> pd.DataFrame:
        """Fetch historical data from Yahoo Finance."""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {
            "interval": interval,
            "range": period,
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Yahoo Finance returned {response.status} for {symbol}")
                    return pd.DataFrame()
                
                data = await response.json()
                chart = data.get("chart", {}).get("result", [{}])[0]
                
                timestamps = chart.get("timestamp", [])
                if not timestamps:
                    return pd.DataFrame()
                
                indicators = chart.get("indicators", {}).get("quote", [{}])[0]
                
                df = pd.DataFrame({
                    "timestamp": [datetime.utcfromtimestamp(ts) for ts in timestamps],
                    "open": indicators.get("open", []),
                    "high": indicators.get("high", []),
                    "low": indicators.get("low", []),
                    "close": indicators.get("close", []),
                    "volume": indicators.get("volume", []),
                })
                
                # Clean up NaN values
                df = df.dropna()
                
                return df
                
        except Exception as e:
            logger.error(f"Failed to fetch Yahoo data for {symbol}: {e}")
            return pd.DataFrame()
    
    async def _get_cached(self, key: str) -> Optional[pd.DataFrame]:
        """Get cached DataFrame from Redis."""
        try:
            import json
            data = await self.redis_client.get(key)
            if data:
                records = json.loads(data)
                df = pd.DataFrame(records)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                return df
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
        return None
    
    async def _cache_dataframe(self, key: str, df: pd.DataFrame):
        """Cache DataFrame to Redis."""
        try:
            import json
            # Convert to JSON-serializable format
            records = df.copy()
            records["timestamp"] = records["timestamp"].astype(str)
            await self.redis_client.set(
                key,
                json.dumps(records.to_dict(orient="records")),
                ex=self.cache_ttl
            )
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")


class TechnicalFeatureProvider:
    """
    Provides technical indicator features for the recommendation engine.
    
    Combines price data fetching with technical indicator calculation
    to produce ML-ready feature vectors.
    
    Example:
        provider = TechnicalFeatureProvider()
        await provider.initialize()
        
        # Get features for a symbol
        features = await provider.get_features("AAPL")
        
        # Get features for multiple symbols
        all_features = await provider.get_features_multi(["AAPL", "GOOGL"])
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = "redis://localhost:6379",
    ):
        self.price_provider = PriceDataProvider(redis_url=redis_url)
    
    async def initialize(self):
        """Initialize the provider."""
        await self.price_provider.initialize()
    
    async def close(self):
        """Close connections."""
        await self.price_provider.close()
    
    async def get_features(
        self,
        symbol: str,
        period: str = "3mo",
    ) -> Dict[str, float]:
        """
        Get technical indicator features for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            period: Historical period for calculation
            
        Returns:
            Dictionary of feature name to value
        """
        from .technical_indicators import calculate_feature_vector
        
        # Get historical data
        df = await self.price_provider.get_historical(symbol, period=period)
        
        if df.empty or len(df) < 50:
            logger.warning(f"Insufficient data for {symbol}")
            return self._empty_features()
        
        # Calculate features
        try:
            features = calculate_feature_vector(df)
            features["symbol"] = symbol
            return features
        except Exception as e:
            logger.error(f"Failed to calculate features for {symbol}: {e}")
            return self._empty_features()
    
    async def get_features_multi(
        self,
        symbols: List[str],
        period: str = "3mo",
    ) -> Dict[str, Dict[str, float]]:
        """Get features for multiple symbols."""
        tasks = [self.get_features(symbol, period) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        features = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get features for {symbol}: {result}")
                features[symbol] = self._empty_features()
            else:
                features[symbol] = result
        
        return features
    
    def _empty_features(self) -> Dict[str, float]:
        """Return empty feature vector."""
        return {
            "price_vs_sma20": 0.0,
            "price_vs_sma50": 0.0,
            "sma20_vs_sma50": 0.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_histogram": 0.0,
            "rsi": 0.5,
            "rsi_overbought": 0,
            "rsi_oversold": 0,
            "roc": 0.0,
            "bb_width": 0.0,
            "bb_position": 0.5,
            "volatility": 0.0,
        }

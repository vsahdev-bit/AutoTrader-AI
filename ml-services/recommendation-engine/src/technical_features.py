"""
Technical Features Module for Recommendation Engine
====================================================

This module provides technical indicator features for the recommendation
engine. It fetches price data and calculates technical indicators to
produce feature vectors for the ML model.

Features Provided:
-----------------
Trend Features:
- Price vs SMA (20, 50, 200)
- SMA crossover signals
- MACD line, signal, histogram

Momentum Features:
- RSI value and overbought/oversold flags
- Stochastic %K and %D
- Rate of Change (ROC)

Volatility Features:
- Bollinger Band width and position
- ATR (Average True Range)
- Historical volatility

Integration:
-----------
The recommendation engine calls get_technical_features() to retrieve
the latest technical features for symbols being analyzed. These features
are combined with news sentiment for final predictions.
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class TechnicalFeatures:
    """
    Technical indicator features for a single symbol.
    
    These features capture the current technical analysis landscape
    and are used as inputs to the recommendation model.
    """
    symbol: str
    timestamp: datetime
    
    # Price data
    current_price: float
    price_change_1d: float  # Percentage change
    price_change_5d: float
    price_change_20d: float
    
    # Trend features (normalized -1 to 1)
    price_vs_sma20: float  # (price - sma20) / sma20
    price_vs_sma50: float
    price_vs_sma200: float
    sma20_vs_sma50: float  # Short-term vs medium-term trend
    macd_normalized: float  # MACD / price (normalized)
    macd_histogram_normalized: float
    
    # Momentum features (0 to 1 or -1 to 1)
    rsi: float  # 0-100 scaled to 0-1
    rsi_signal: int  # -1 oversold, 0 neutral, 1 overbought
    stochastic_k: float  # 0-1
    stochastic_d: float  # 0-1
    roc: float  # Rate of change (normalized)
    
    # Volatility features
    bb_width: float  # Bollinger band width (normalized)
    bb_position: float  # Position within bands (0-1)
    atr_percent: float  # ATR as % of price
    volatility: float  # Historical volatility (annualized)
    
    # Volume features (if available)
    volume_ratio: float  # Current vs average volume
    obv_trend: float  # OBV slope (normalized)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_price": self.current_price,
            "price_change_1d": self.price_change_1d,
            "price_change_5d": self.price_change_5d,
            "price_change_20d": self.price_change_20d,
            "price_vs_sma20": self.price_vs_sma20,
            "price_vs_sma50": self.price_vs_sma50,
            "price_vs_sma200": self.price_vs_sma200,
            "sma20_vs_sma50": self.sma20_vs_sma50,
            "macd_normalized": self.macd_normalized,
            "macd_histogram_normalized": self.macd_histogram_normalized,
            "rsi": self.rsi,
            "rsi_signal": self.rsi_signal,
            "stochastic_k": self.stochastic_k,
            "stochastic_d": self.stochastic_d,
            "roc": self.roc,
            "bb_width": self.bb_width,
            "bb_position": self.bb_position,
            "atr_percent": self.atr_percent,
            "volatility": self.volatility,
            "volume_ratio": self.volume_ratio,
            "obv_trend": self.obv_trend,
        }
    
    def to_feature_vector(self) -> List[float]:
        """
        Convert to feature vector for ML model input.
        
        Returns list of normalized floats suitable for model inference.
        """
        return [
            self.price_change_1d,
            self.price_change_5d,
            self.price_change_20d,
            self.price_vs_sma20,
            self.price_vs_sma50,
            self.price_vs_sma200,
            self.sma20_vs_sma50,
            self.macd_normalized,
            self.macd_histogram_normalized,
            self.rsi,
            float(self.rsi_signal),
            self.stochastic_k,
            self.stochastic_d,
            self.roc,
            self.bb_width,
            self.bb_position,
            self.atr_percent,
            self.volatility,
            self.volume_ratio,
            self.obv_trend,
        ]
    
    def get_trend_signal(self) -> int:
        """
        Get overall trend signal from technical indicators.
        
        Returns:
            1 for bullish, -1 for bearish, 0 for neutral
        """
        signals = []
        
        # Price vs moving averages
        if self.price_vs_sma20 > 0.02:
            signals.append(1)
        elif self.price_vs_sma20 < -0.02:
            signals.append(-1)
        
        if self.price_vs_sma50 > 0.03:
            signals.append(1)
        elif self.price_vs_sma50 < -0.03:
            signals.append(-1)
        
        # MACD
        if self.macd_histogram_normalized > 0:
            signals.append(1)
        elif self.macd_histogram_normalized < 0:
            signals.append(-1)
        
        if not signals:
            return 0
        
        avg = sum(signals) / len(signals)
        if avg > 0.3:
            return 1
        elif avg < -0.3:
            return -1
        return 0
    
    def get_momentum_signal(self) -> int:
        """
        Get overall momentum signal from technical indicators.
        
        Returns:
            1 for bullish momentum, -1 for bearish, 0 for neutral
        """
        signals = []
        
        # RSI
        if self.rsi < 0.3:  # Oversold
            signals.append(1)  # Bullish reversal expected
        elif self.rsi > 0.7:  # Overbought
            signals.append(-1)  # Bearish reversal expected
        
        # Stochastic
        if self.stochastic_k < 0.2:
            signals.append(1)
        elif self.stochastic_k > 0.8:
            signals.append(-1)
        
        # ROC
        if self.roc > 0.05:
            signals.append(1)
        elif self.roc < -0.05:
            signals.append(-1)
        
        if not signals:
            return 0
        
        avg = sum(signals) / len(signals)
        if avg > 0.3:
            return 1
        elif avg < -0.3:
            return -1
        return 0
    
    @classmethod
    def empty(cls, symbol: str) -> "TechnicalFeatures":
        """Create empty features (no data available)."""
        return cls(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            current_price=0.0,
            price_change_1d=0.0,
            price_change_5d=0.0,
            price_change_20d=0.0,
            price_vs_sma20=0.0,
            price_vs_sma50=0.0,
            price_vs_sma200=0.0,
            sma20_vs_sma50=0.0,
            macd_normalized=0.0,
            macd_histogram_normalized=0.0,
            rsi=0.5,
            rsi_signal=0,
            stochastic_k=0.5,
            stochastic_d=0.5,
            roc=0.0,
            bb_width=0.0,
            bb_position=0.5,
            atr_percent=0.0,
            volatility=0.0,
            volume_ratio=1.0,
            obv_trend=0.0,
        )


class TechnicalFeatureProvider:
    """
    Provides technical indicator features for the recommendation engine.
    
    Fetches price data from Yahoo Finance and calculates technical
    indicators to produce feature vectors.
    
    Example Usage:
        provider = TechnicalFeatureProvider()
        await provider.initialize()
        
        features = await provider.get_features("AAPL")
        print(f"RSI: {features.rsi}")
        print(f"Trend: {features.get_trend_signal()}")
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = "redis://localhost:6379",
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize the feature provider.
        
        Args:
            redis_url: Redis URL for caching (optional)
            cache_ttl_seconds: How long to cache features
        """
        self.redis_url = redis_url
        self.cache_ttl = cache_ttl_seconds
        self.redis_client = None
        self._session = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize connections."""
        if self._initialized:
            return
        
        # Initialize Redis cache
        if self.redis_url:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(
                    self.redis_url, 
                    decode_responses=True
                )
                await self.redis_client.ping()
                logger.info("Technical features cache initialized")
            except Exception as e:
                logger.warning(f"Redis not available: {e}")
                self.redis_client = None
        
        # Initialize HTTP session
        import aiohttp
        self._session = aiohttp.ClientSession()
        
        self._initialized = True
    
    async def get_features(self, symbol: str) -> TechnicalFeatures:
        """
        Get technical features for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            TechnicalFeatures object
        """
        if not self._initialized:
            await self.initialize()
        
        # Check cache first
        if self.redis_client:
            cached = await self._get_cached(symbol)
            if cached:
                return cached
        
        # Fetch and calculate features
        try:
            features = await self._calculate_features(symbol)
            
            # Cache the result
            if self.redis_client:
                await self._cache_features(symbol, features)
            
            return features
            
        except Exception as e:
            logger.error(f"Failed to calculate technical features for {symbol}: {e}")
            return TechnicalFeatures.empty(symbol)
    
    async def get_features_multi(
        self,
        symbols: List[str],
    ) -> Dict[str, TechnicalFeatures]:
        """Get features for multiple symbols concurrently."""
        tasks = [self.get_features(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        features = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get features for {symbol}: {result}")
                features[symbol] = TechnicalFeatures.empty(symbol)
            else:
                features[symbol] = result
        
        return features
    
    async def _calculate_features(self, symbol: str) -> TechnicalFeatures:
        """Fetch price data and calculate all technical features."""
        import numpy as np
        
        # Fetch historical data (6 months for SMA 200)
        df = await self._fetch_price_data(symbol, period="6mo", interval="1d")
        
        if df is None or len(df) < 50:
            logger.warning(f"Insufficient price data for {symbol}")
            return TechnicalFeatures.empty(symbol)
        
        # Current price
        current_price = float(df["close"].iloc[-1])
        
        # Price changes
        price_change_1d = self._safe_pct_change(df["close"], 1)
        price_change_5d = self._safe_pct_change(df["close"], 5)
        price_change_20d = self._safe_pct_change(df["close"], 20)
        
        # Moving averages
        sma20 = df["close"].rolling(window=20).mean().iloc[-1]
        sma50 = df["close"].rolling(window=50).mean().iloc[-1]
        sma200 = df["close"].rolling(window=200).mean().iloc[-1] if len(df) >= 200 else sma50
        
        price_vs_sma20 = (current_price - sma20) / sma20 if sma20 else 0
        price_vs_sma50 = (current_price - sma50) / sma50 if sma50 else 0
        price_vs_sma200 = (current_price - sma200) / sma200 if sma200 else 0
        sma20_vs_sma50 = (sma20 - sma50) / sma50 if sma50 else 0
        
        # MACD
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        
        macd_normalized = float(macd_line.iloc[-1]) / current_price if current_price else 0
        macd_histogram_normalized = float(histogram.iloc[-1]) / current_price if current_price else 0
        
        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta).where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi_raw = 100 - (100 / (1 + rs))
        rsi = float(rsi_raw.iloc[-1]) / 100 if not np.isnan(rsi_raw.iloc[-1]) else 0.5
        
        # RSI signal
        rsi_signal = 0
        if rsi < 0.3:
            rsi_signal = -1  # Oversold
        elif rsi > 0.7:
            rsi_signal = 1  # Overbought
        
        # Stochastic
        low_14 = df["low"].rolling(window=14).min()
        high_14 = df["high"].rolling(window=14).max()
        stochastic_k_raw = 100 * (df["close"] - low_14) / (high_14 - low_14)
        stochastic_d_raw = stochastic_k_raw.rolling(window=3).mean()
        
        stochastic_k = float(stochastic_k_raw.iloc[-1]) / 100 if not np.isnan(stochastic_k_raw.iloc[-1]) else 0.5
        stochastic_d = float(stochastic_d_raw.iloc[-1]) / 100 if not np.isnan(stochastic_d_raw.iloc[-1]) else 0.5
        
        # Rate of Change
        roc = self._safe_pct_change(df["close"], 12)
        
        # Bollinger Bands
        bb_middle = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        bb_upper = bb_middle + (bb_std * 2)
        bb_lower = bb_middle - (bb_std * 2)
        
        bb_width_raw = (bb_upper - bb_lower) / bb_middle
        bb_width = float(bb_width_raw.iloc[-1]) if not np.isnan(bb_width_raw.iloc[-1]) else 0
        
        bb_position_raw = (df["close"] - bb_lower) / (bb_upper - bb_lower)
        bb_position = float(bb_position_raw.iloc[-1]) if not np.isnan(bb_position_raw.iloc[-1]) else 0.5
        bb_position = max(0, min(1, bb_position))  # Clamp to 0-1
        
        # ATR
        tr1 = df["high"] - df["low"]
        tr2 = abs(df["high"] - df["close"].shift(1))
        tr3 = abs(df["low"] - df["close"].shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        atr_percent = float(atr.iloc[-1]) / current_price if current_price else 0
        
        # Volatility (annualized)
        returns = df["close"].pct_change()
        volatility = float(returns.rolling(window=20).std().iloc[-1] * np.sqrt(252))
        volatility = volatility if not np.isnan(volatility) else 0
        
        # Volume ratio
        avg_volume = df["volume"].rolling(window=20).mean().iloc[-1]
        current_volume = df["volume"].iloc[-1]
        volume_ratio = float(current_volume / avg_volume) if avg_volume else 1.0
        
        # OBV trend
        obv = self._calculate_obv(df)
        obv_sma = obv.rolling(window=10).mean()
        obv_trend = (obv.iloc[-1] - obv_sma.iloc[-1]) / abs(obv_sma.iloc[-1]) if obv_sma.iloc[-1] != 0 else 0
        obv_trend = max(-1, min(1, obv_trend))  # Clamp to -1 to 1
        
        return TechnicalFeatures(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            current_price=current_price,
            price_change_1d=price_change_1d,
            price_change_5d=price_change_5d,
            price_change_20d=price_change_20d,
            price_vs_sma20=price_vs_sma20,
            price_vs_sma50=price_vs_sma50,
            price_vs_sma200=price_vs_sma200,
            sma20_vs_sma50=sma20_vs_sma50,
            macd_normalized=macd_normalized,
            macd_histogram_normalized=macd_histogram_normalized,
            rsi=rsi,
            rsi_signal=rsi_signal,
            stochastic_k=stochastic_k,
            stochastic_d=stochastic_d,
            roc=roc,
            bb_width=bb_width,
            bb_position=bb_position,
            atr_percent=atr_percent,
            volatility=volatility,
            volume_ratio=volume_ratio,
            obv_trend=obv_trend,
        )
    
    def _safe_pct_change(self, series, periods: int) -> float:
        """Calculate percentage change safely."""
        import numpy as np
        
        if len(series) <= periods:
            return 0.0
        
        current = series.iloc[-1]
        previous = series.iloc[-periods - 1]
        
        if previous == 0 or np.isnan(previous) or np.isnan(current):
            return 0.0
        
        return (current - previous) / previous
    
    def _calculate_obv(self, df) -> 'pd.Series':
        """Calculate On-Balance Volume."""
        import pandas as pd
        
        obv = pd.Series(index=df.index, dtype=float)
        obv.iloc[0] = 0
        
        for i in range(1, len(df)):
            if df["close"].iloc[i] > df["close"].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + df["volume"].iloc[i]
            elif df["close"].iloc[i] < df["close"].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - df["volume"].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return obv
    
    async def _fetch_price_data(
        self,
        symbol: str,
        period: str,
        interval: str,
    ):
        """Fetch historical price data with fallback sources.
        
        Tries multiple sources in order: Yahoo Finance, Polygon, FMP, Alpha Vantage.
        Falls back to demo data if all sources fail (for development/testing).
        """
        import pandas as pd
        
        # Try Yahoo Finance first
        df = await self._fetch_yahoo_price_data(symbol, period, interval)
        if df is not None and len(df) > 0:
            return df
        
        # Fallback to Polygon
        logger.info(f"Falling back to Polygon for {symbol}")
        df = await self._fetch_polygon_price_data(symbol, period)
        if df is not None and len(df) > 0:
            return df
        
        # Fallback to FMP
        logger.info(f"Falling back to Financial Modeling Prep for {symbol}")
        df = await self._fetch_fmp_price_data(symbol, period)
        if df is not None and len(df) > 0:
            return df
        
        # Fallback to Alpha Vantage
        logger.info(f"Falling back to Alpha Vantage for {symbol}")
        df = await self._fetch_alpha_vantage_price_data(symbol)
        if df is not None and len(df) > 0:
            return df
        
        # Final fallback: generate realistic demo data for development/testing
        logger.warning(f"All API sources failed for {symbol}, using demo data")
        df = await self._generate_demo_price_data(symbol, period)
        if df is not None and len(df) > 0:
            return df
        
        logger.error(f"All data sources failed for {symbol}")
        return None
    
    async def _fetch_alpha_vantage_price_data(self, symbol: str):
        """Fetch historical price data from Alpha Vantage (free tier available)."""
        import pandas as pd
        import os
        
        api_key = os.getenv('ALPHA_VANTAGE_API_KEY', 'demo')  # 'demo' key has limited access
        
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": api_key,
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Alpha Vantage returned {response.status} for {symbol}")
                    return None
                
                data = await response.json()
                
                # Check for error messages
                if "Error Message" in data or "Note" in data:
                    logger.warning(f"Alpha Vantage error for {symbol}: {data.get('Error Message') or data.get('Note')}")
                    return None
                
                time_series = data.get("Time Series (Daily)", {})
                if not time_series:
                    logger.warning(f"No Alpha Vantage data for {symbol}")
                    return None
                
                rows = []
                for date_str, values in time_series.items():
                    rows.append({
                        "timestamp": pd.to_datetime(date_str),
                        "open": float(values["1. open"]),
                        "high": float(values["2. high"]),
                        "low": float(values["3. low"]),
                        "close": float(values["4. close"]),
                        "volume": int(values["5. volume"]),
                    })
                
                df = pd.DataFrame(rows)
                df = df.sort_values("timestamp").reset_index(drop=True)
                df = df.dropna()
                
                logger.info(f"Alpha Vantage fetched {len(df)} rows for {symbol}")
                return df
                
        except Exception as e:
            logger.error(f"Failed to fetch Alpha Vantage data for {symbol}: {e}")
            return None
    
    async def _generate_demo_price_data(self, symbol: str, period: str):
        """Generate realistic demo price data for development/testing.
        
        This is used as a last resort when all API sources fail.
        The data is synthetic but follows realistic patterns.
        """
        import pandas as pd
        import numpy as np
        from datetime import datetime, timedelta
        
        # Base prices for common symbols (approximate)
        base_prices = {
            "AAPL": 185.0, "GOOGL": 140.0, "MSFT": 375.0, "AMZN": 155.0,
            "TSLA": 245.0, "META": 360.0, "NVDA": 490.0, "JPM": 170.0,
            "V": 265.0, "JNJ": 155.0, "WMT": 165.0, "PG": 150.0,
            "DIS": 95.0, "NFLX": 475.0, "INTC": 45.0, "AMD": 140.0,
        }
        
        base_price = base_prices.get(symbol.upper(), 100.0)
        
        # Determine number of days based on period
        period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
        num_days = period_days.get(period, 180)
        
        # Generate dates
        end_date = datetime.now()
        dates = [end_date - timedelta(days=i) for i in range(num_days, 0, -1)]
        
        # Generate realistic price movements using geometric Brownian motion
        np.random.seed(hash(symbol) % 2**32)  # Consistent for same symbol
        
        daily_return_mean = 0.0005  # Small positive drift
        daily_volatility = 0.02  # 2% daily volatility
        
        returns = np.random.normal(daily_return_mean, daily_volatility, num_days)
        price_multipliers = np.exp(np.cumsum(returns))
        
        close_prices = base_price * price_multipliers
        
        # Generate OHLCV data
        rows = []
        for i, date in enumerate(dates):
            close = close_prices[i]
            daily_range = close * np.random.uniform(0.01, 0.03)  # 1-3% daily range
            
            high = close + daily_range * np.random.uniform(0.3, 0.7)
            low = close - daily_range * np.random.uniform(0.3, 0.7)
            open_price = low + (high - low) * np.random.uniform(0.2, 0.8)
            
            # Volume with some randomness
            avg_volume = 50_000_000 if symbol in ["AAPL", "MSFT", "AMZN"] else 10_000_000
            volume = int(avg_volume * np.random.uniform(0.5, 1.5))
            
            rows.append({
                "timestamp": date,
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": volume,
            })
        
        df = pd.DataFrame(rows)
        logger.info(f"Generated {len(df)} demo data points for {symbol}")
        return df
    
    async def _fetch_yahoo_price_data(
        self,
        symbol: str,
        period: str,
        interval: str,
    ):
        """Fetch historical price data from Yahoo Finance."""
        import pandas as pd
        
        # First try the yfinance library (more reliable)
        df = await self._fetch_yfinance_data(symbol, period, interval)
        if df is not None and len(df) > 0:
            return df
        
        # Fallback to direct API with proper headers
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {
            "interval": interval,
            "range": period,
        }
        
        # Add headers to avoid rate limiting
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        try:
            async with self._session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Yahoo Finance API returned {response.status} for {symbol}")
                    return None
                
                data = await response.json()
                chart = data.get("chart", {}).get("result", [{}])[0]
                
                timestamps = chart.get("timestamp", [])
                if not timestamps:
                    return None
                
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
            logger.error(f"Failed to fetch Yahoo price data for {symbol}: {e}")
            return None
    
    async def _fetch_yfinance_data(
        self,
        symbol: str,
        period: str,
        interval: str,
    ):
        """Fetch historical price data using yfinance library (more reliable)."""
        try:
            import yfinance as yf
            import pandas as pd
            
            # Run yfinance in executor to avoid blocking
            loop = asyncio.get_event_loop()
            
            def fetch_data():
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=interval)
                return df
            
            df = await loop.run_in_executor(None, fetch_data)
            
            if df is None or df.empty:
                logger.warning(f"yfinance returned no data for {symbol}")
                return None
            
            # Rename columns to match expected format
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            
            # Rename 'date' or 'datetime' to 'timestamp'
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'timestamp'})
            elif 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'timestamp'})
            
            # Ensure we have required columns
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    logger.warning(f"yfinance missing column {col} for {symbol}")
                    return None
            
            df = df[required_cols]
            df = df.dropna()
            
            logger.info(f"yfinance fetched {len(df)} rows for {symbol}")
            return df
            
        except ImportError:
            logger.debug("yfinance not installed, skipping")
            return None
        except Exception as e:
            logger.warning(f"yfinance failed for {symbol}: {e}")
            return None
    
    async def _fetch_polygon_price_data(self, symbol: str, period: str):
        """Fetch historical price data from Polygon.io."""
        import pandas as pd
        import os
        from datetime import datetime, timedelta
        
        # Get API key from Vault or environment
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            try:
                from vault_client import VaultClient
                vault = VaultClient()
                secret = await vault.get_secret('connectors/polygon')
                api_key = secret.get('api_key') if secret else None
            except Exception as e:
                logger.warning(f"Failed to get Polygon API key from Vault: {e}")
                return None
        
        if not api_key:
            logger.warning("No Polygon API key available")
            return None
        
        # Convert period to date range
        end_date = datetime.now()
        period_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
        days = period_map.get(period, 180)
        start_date = end_date - timedelta(days=days)
        
        url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
        params = {"apiKey": api_key, "adjusted": "true", "sort": "asc", "limit": 500}
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Polygon returned {response.status} for {symbol}")
                    return None
                
                data = await response.json()
                results = data.get("results", [])
                
                if not results:
                    logger.warning(f"No Polygon data for {symbol}")
                    return None
                
                df = pd.DataFrame(results)
                df = df.rename(columns={
                    "t": "timestamp", "o": "open", "h": "high",
                    "l": "low", "c": "close", "v": "volume"
                })
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df[["timestamp", "open", "high", "low", "close", "volume"]]
                df = df.dropna()
                
                return df
                
        except Exception as e:
            logger.error(f"Failed to fetch Polygon price data for {symbol}: {e}")
            return None
    
    async def _fetch_fmp_price_data(self, symbol: str, period: str):
        """Fetch historical price data from Financial Modeling Prep."""
        import pandas as pd
        import os
        from datetime import datetime, timedelta
        
        # Get API key from Vault or environment
        api_key = os.getenv('FMP_API_KEY')
        if not api_key:
            try:
                from vault_client import VaultClient
                vault = VaultClient()
                secret = await vault.get_secret('connectors/fmp')
                api_key = secret.get('api_key') if secret else None
            except Exception as e:
                logger.warning(f"Failed to get FMP API key from Vault: {e}")
                return None
        
        if not api_key:
            logger.warning("No FMP API key available")
            return None
        
        # Convert period to date range
        end_date = datetime.now()
        period_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
        days = period_map.get(period, 180)
        start_date = end_date - timedelta(days=days)
        
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}"
        params = {
            "apikey": api_key,
            "from": start_date.strftime('%Y-%m-%d'),
            "to": end_date.strftime('%Y-%m-%d')
        }
        
        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"FMP returned {response.status} for {symbol}")
                    return None
                
                data = await response.json()
                historical = data.get("historical", [])
                
                if not historical:
                    logger.warning(f"No FMP data for {symbol}")
                    return None
                
                df = pd.DataFrame(historical)
                df["timestamp"] = pd.to_datetime(df["date"])
                df = df.rename(columns={"adjClose": "close"})
                df = df[["timestamp", "open", "high", "low", "close", "volume"]]
                df = df.sort_values("timestamp").reset_index(drop=True)
                df = df.dropna()
                
                return df
                
        except Exception as e:
            logger.error(f"Failed to fetch FMP price data for {symbol}: {e}")
            return None
    
    async def _get_cached(self, symbol: str) -> Optional[TechnicalFeatures]:
        """Get cached features from Redis."""
        try:
            import json
            
            key = f"technical_features:{symbol}"
            data = await self.redis_client.get(key)
            
            if data:
                d = json.loads(data)
                d["timestamp"] = datetime.fromisoformat(d["timestamp"])
                features = TechnicalFeatures(**d)
                
                # Don't return cached data if it has no price (empty/failed fetch)
                if features.current_price <= 0:
                    logger.info(f"Skipping cached empty data for {symbol}")
                    return None
                
                return features
                
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
        
        return None
    
    async def _cache_features(self, symbol: str, features: TechnicalFeatures):
        """Cache features to Redis."""
        try:
            import json
            
            key = f"technical_features:{symbol}"
            await self.redis_client.set(
                key,
                json.dumps(features.to_dict()),
                ex=self.cache_ttl
            )
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")
    
    async def close(self):
        """Close connections."""
        if self._session:
            await self._session.close()
        if self.redis_client:
            await self.redis_client.close()


# Import pandas at module level for type hints
try:
    import pandas as pd
except ImportError:
    pd = None

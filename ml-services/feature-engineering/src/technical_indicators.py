"""
Technical Indicators Module
===========================

This module provides comprehensive technical analysis indicators
for stock price data. These indicators are used by the recommendation
engine as features for ML models and rule-based trading signals.

Supported Indicators:
--------------------
Trend Indicators:
- SMA (Simple Moving Average)
- EMA (Exponential Moving Average)
- MACD (Moving Average Convergence Divergence)
- ADX (Average Directional Index)

Momentum Indicators:
- RSI (Relative Strength Index)
- Stochastic Oscillator
- Williams %R
- ROC (Rate of Change)
- MFI (Money Flow Index)

Volatility Indicators:
- Bollinger Bands
- ATR (Average True Range)
- Standard Deviation

Volume Indicators:
- OBV (On-Balance Volume)
- VWAP (Volume Weighted Average Price)
- A/D Line (Accumulation/Distribution)

Usage:
------
    from ml_services.feature_engineering.src.technical_indicators import (
        TechnicalIndicators,
        calculate_all_indicators
    )
    
    # Using class-based approach
    ti = TechnicalIndicators(prices_df)
    rsi = ti.rsi()
    macd = ti.macd()
    
    # Or calculate all at once
    features = calculate_all_indicators(prices_df)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class IndicatorResult:
    """
    Result container for technical indicators.
    
    Attributes:
        name: Indicator name (e.g., "RSI", "MACD")
        values: Main indicator values
        signal: Signal line (if applicable)
        upper: Upper band (if applicable)
        lower: Lower band (if applicable)
        histogram: Histogram values (if applicable)
    """
    name: str
    values: pd.Series
    signal: Optional[pd.Series] = None
    upper: Optional[pd.Series] = None
    lower: Optional[pd.Series] = None
    histogram: Optional[pd.Series] = None


class TechnicalIndicators:
    """
    Technical indicators calculator for stock price data.
    
    This class provides methods to calculate various technical analysis
    indicators from OHLCV (Open, High, Low, Close, Volume) data.
    
    Example:
        # Load price data
        df = pd.DataFrame({
            'open': [...],
            'high': [...],
            'low': [...],
            'close': [...],
            'volume': [...]
        })
        
        ti = TechnicalIndicators(df)
        
        # Calculate individual indicators
        rsi = ti.rsi(period=14)
        macd_result = ti.macd()
        
        # Access results
        print(f"RSI: {rsi.values.iloc[-1]}")
        print(f"MACD: {macd_result.values.iloc[-1]}")
        print(f"Signal: {macd_result.signal.iloc[-1]}")
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        open_col: str = "open",
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
        volume_col: str = "volume",
    ):
        """
        Initialize with OHLCV data.
        
        Args:
            df: DataFrame with OHLCV columns
            open_col: Name of open price column
            high_col: Name of high price column
            low_col: Name of low price column
            close_col: Name of close price column
            volume_col: Name of volume column
        """
        self.df = df.copy()
        self.open = df[open_col] if open_col in df.columns else None
        self.high = df[high_col] if high_col in df.columns else None
        self.low = df[low_col] if low_col in df.columns else None
        self.close = df[close_col]
        self.volume = df[volume_col] if volume_col in df.columns else None
    
    # =========================================================================
    # Trend Indicators
    # =========================================================================
    
    def sma(self, period: int = 20) -> IndicatorResult:
        """
        Simple Moving Average (SMA).
        
        The arithmetic mean of prices over a period. Used to identify
        trend direction and support/resistance levels.
        
        Args:
            period: Number of periods for the average
            
        Returns:
            IndicatorResult with SMA values
            
        Interpretation:
        - Price above SMA = bullish
        - Price below SMA = bearish
        - SMA slope indicates trend strength
        """
        sma = self.close.rolling(window=period).mean()
        return IndicatorResult(name=f"SMA_{period}", values=sma)
    
    def ema(self, period: int = 20) -> IndicatorResult:
        """
        Exponential Moving Average (EMA).
        
        Weighted moving average giving more weight to recent prices.
        More responsive to price changes than SMA.
        
        Args:
            period: Number of periods for the average
            
        Returns:
            IndicatorResult with EMA values
        """
        ema = self.close.ewm(span=period, adjust=False).mean()
        return IndicatorResult(name=f"EMA_{period}", values=ema)
    
    def macd(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> IndicatorResult:
        """
        Moving Average Convergence Divergence (MACD).
        
        Trend-following momentum indicator showing relationship
        between two EMAs. One of the most popular indicators.
        
        Args:
            fast_period: Period for fast EMA (default 12)
            slow_period: Period for slow EMA (default 26)
            signal_period: Period for signal line EMA (default 9)
            
        Returns:
            IndicatorResult with MACD line, signal line, and histogram
            
        Interpretation:
        - MACD above signal = bullish
        - MACD below signal = bearish
        - Histogram shows momentum strength
        - Divergence from price = potential reversal
        """
        fast_ema = self.close.ewm(span=fast_period, adjust=False).mean()
        slow_ema = self.close.ewm(span=slow_period, adjust=False).mean()
        
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return IndicatorResult(
            name="MACD",
            values=macd_line,
            signal=signal_line,
            histogram=histogram,
        )
    
    def adx(self, period: int = 14) -> IndicatorResult:
        """
        Average Directional Index (ADX).
        
        Measures trend strength regardless of direction.
        Useful for determining if market is trending.
        
        Args:
            period: Period for ADX calculation
            
        Returns:
            IndicatorResult with ADX values and +DI/-DI
            
        Interpretation:
        - ADX > 25 = strong trend
        - ADX < 20 = weak trend or ranging
        - +DI > -DI = bullish trend
        - -DI > +DI = bearish trend
        """
        if self.high is None or self.low is None:
            raise ValueError("High and Low prices required for ADX")
        
        # True Range
        tr1 = self.high - self.low
        tr2 = abs(self.high - self.close.shift(1))
        tr3 = abs(self.low - self.close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Directional Movement
        up_move = self.high - self.high.shift(1)
        down_move = self.low.shift(1) - self.low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Smoothed values
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr
        
        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return IndicatorResult(
            name="ADX",
            values=adx,
            upper=plus_di,  # +DI
            lower=minus_di,  # -DI
        )
    
    # =========================================================================
    # Momentum Indicators
    # =========================================================================
    
    def rsi(self, period: int = 14) -> IndicatorResult:
        """
        Relative Strength Index (RSI).
        
        Momentum oscillator measuring speed and magnitude of price changes.
        Ranges from 0 to 100.
        
        Args:
            period: Lookback period (default 14)
            
        Returns:
            IndicatorResult with RSI values
            
        Interpretation:
        - RSI > 70 = overbought (potential sell)
        - RSI < 30 = oversold (potential buy)
        - Divergence from price = potential reversal
        """
        delta = self.close.diff()
        
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return IndicatorResult(name="RSI", values=rsi)
    
    def stochastic(
        self,
        k_period: int = 14,
        d_period: int = 3,
    ) -> IndicatorResult:
        """
        Stochastic Oscillator.
        
        Compares closing price to price range over a period.
        Shows momentum and potential reversals.
        
        Args:
            k_period: Period for %K calculation
            d_period: Period for %D (signal) smoothing
            
        Returns:
            IndicatorResult with %K values and %D signal
            
        Interpretation:
        - %K > 80 = overbought
        - %K < 20 = oversold
        - %K crossing %D = buy/sell signal
        """
        if self.high is None or self.low is None:
            raise ValueError("High and Low prices required for Stochastic")
        
        lowest_low = self.low.rolling(window=k_period).min()
        highest_high = self.high.rolling(window=k_period).max()
        
        k = 100 * (self.close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=d_period).mean()
        
        return IndicatorResult(
            name="Stochastic",
            values=k,
            signal=d,
        )
    
    def williams_r(self, period: int = 14) -> IndicatorResult:
        """
        Williams %R.
        
        Momentum indicator similar to Stochastic but inverted.
        Ranges from -100 to 0.
        
        Args:
            period: Lookback period
            
        Returns:
            IndicatorResult with Williams %R values
            
        Interpretation:
        - %R > -20 = overbought
        - %R < -80 = oversold
        """
        if self.high is None or self.low is None:
            raise ValueError("High and Low prices required for Williams %R")
        
        highest_high = self.high.rolling(window=period).max()
        lowest_low = self.low.rolling(window=period).min()
        
        wr = -100 * (highest_high - self.close) / (highest_high - lowest_low)
        
        return IndicatorResult(name="Williams_R", values=wr)
    
    def roc(self, period: int = 12) -> IndicatorResult:
        """
        Rate of Change (ROC).
        
        Measures percentage change in price over a period.
        Simple momentum indicator.
        
        Args:
            period: Lookback period
            
        Returns:
            IndicatorResult with ROC values
            
        Interpretation:
        - Positive ROC = bullish momentum
        - Negative ROC = bearish momentum
        - Extreme values may indicate reversals
        """
        roc = ((self.close - self.close.shift(period)) / self.close.shift(period)) * 100
        
        return IndicatorResult(name="ROC", values=roc)
    
    def mfi(self, period: int = 14) -> IndicatorResult:
        """
        Money Flow Index (MFI).
        
        Volume-weighted RSI. Incorporates both price and volume.
        
        Args:
            period: Lookback period
            
        Returns:
            IndicatorResult with MFI values
            
        Interpretation:
        - MFI > 80 = overbought
        - MFI < 20 = oversold
        - Divergence from price = potential reversal
        """
        if self.high is None or self.low is None or self.volume is None:
            raise ValueError("High, Low, and Volume required for MFI")
        
        typical_price = (self.high + self.low + self.close) / 3
        raw_money_flow = typical_price * self.volume
        
        # Positive and negative money flow
        positive_flow = raw_money_flow.where(
            typical_price > typical_price.shift(1), 0
        )
        negative_flow = raw_money_flow.where(
            typical_price < typical_price.shift(1), 0
        )
        
        positive_mf = positive_flow.rolling(window=period).sum()
        negative_mf = negative_flow.rolling(window=period).sum()
        
        mfi = 100 - (100 / (1 + positive_mf / negative_mf))
        
        return IndicatorResult(name="MFI", values=mfi)
    
    # =========================================================================
    # Volatility Indicators
    # =========================================================================
    
    def bollinger_bands(
        self,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> IndicatorResult:
        """
        Bollinger Bands.
        
        Volatility bands placed above and below a moving average.
        Bands widen during volatility, narrow during consolidation.
        
        Args:
            period: Period for moving average
            std_dev: Number of standard deviations for bands
            
        Returns:
            IndicatorResult with middle, upper, and lower bands
            
        Interpretation:
        - Price near upper band = overbought
        - Price near lower band = oversold
        - Band squeeze = potential breakout coming
        - Band expansion = trend in progress
        """
        middle = self.close.rolling(window=period).mean()
        std = self.close.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return IndicatorResult(
            name="Bollinger",
            values=middle,
            upper=upper,
            lower=lower,
        )
    
    def atr(self, period: int = 14) -> IndicatorResult:
        """
        Average True Range (ATR).
        
        Measures volatility by decomposing the entire range of price.
        Used for position sizing and stop-loss placement.
        
        Args:
            period: Period for averaging
            
        Returns:
            IndicatorResult with ATR values
            
        Interpretation:
        - High ATR = high volatility
        - Low ATR = low volatility
        - ATR expansion = potential trend start
        - ATR contraction = potential trend end
        """
        if self.high is None or self.low is None:
            raise ValueError("High and Low prices required for ATR")
        
        tr1 = self.high - self.low
        tr2 = abs(self.high - self.close.shift(1))
        tr3 = abs(self.low - self.close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return IndicatorResult(name="ATR", values=atr)
    
    def volatility(self, period: int = 20) -> IndicatorResult:
        """
        Historical Volatility (Standard Deviation of Returns).
        
        Measures the dispersion of returns. Useful for risk assessment.
        
        Args:
            period: Period for calculation
            
        Returns:
            IndicatorResult with volatility values
        """
        returns = self.close.pct_change()
        vol = returns.rolling(window=period).std() * np.sqrt(252)  # Annualized
        
        return IndicatorResult(name="Volatility", values=vol)
    
    # =========================================================================
    # Volume Indicators
    # =========================================================================
    
    def obv(self) -> IndicatorResult:
        """
        On-Balance Volume (OBV).
        
        Cumulative volume indicator that relates volume to price change.
        Volume is added on up days, subtracted on down days.
        
        Returns:
            IndicatorResult with OBV values
            
        Interpretation:
        - Rising OBV = accumulation (bullish)
        - Falling OBV = distribution (bearish)
        - OBV divergence from price = potential reversal
        """
        if self.volume is None:
            raise ValueError("Volume required for OBV")
        
        price_change = self.close.diff()
        
        obv = pd.Series(index=self.close.index, dtype=float)
        obv.iloc[0] = 0
        
        for i in range(1, len(self.close)):
            if price_change.iloc[i] > 0:
                obv.iloc[i] = obv.iloc[i-1] + self.volume.iloc[i]
            elif price_change.iloc[i] < 0:
                obv.iloc[i] = obv.iloc[i-1] - self.volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return IndicatorResult(name="OBV", values=obv)
    
    def vwap(self) -> IndicatorResult:
        """
        Volume Weighted Average Price (VWAP).
        
        Average price weighted by volume. Important for institutional trading.
        
        Returns:
            IndicatorResult with VWAP values
            
        Interpretation:
        - Price above VWAP = bullish
        - Price below VWAP = bearish
        - Used as support/resistance
        """
        if self.high is None or self.low is None or self.volume is None:
            raise ValueError("High, Low, and Volume required for VWAP")
        
        typical_price = (self.high + self.low + self.close) / 3
        vwap = (typical_price * self.volume).cumsum() / self.volume.cumsum()
        
        return IndicatorResult(name="VWAP", values=vwap)
    
    def ad_line(self) -> IndicatorResult:
        """
        Accumulation/Distribution Line.
        
        Combines price and volume to show whether stock is being
        accumulated (bought) or distributed (sold).
        
        Returns:
            IndicatorResult with A/D Line values
            
        Interpretation:
        - Rising A/D = accumulation (bullish)
        - Falling A/D = distribution (bearish)
        - Divergence from price = potential reversal
        """
        if self.high is None or self.low is None or self.volume is None:
            raise ValueError("High, Low, and Volume required for A/D Line")
        
        clv = ((self.close - self.low) - (self.high - self.close)) / (self.high - self.low)
        clv = clv.fillna(0)  # Handle division by zero
        
        ad = (clv * self.volume).cumsum()
        
        return IndicatorResult(name="AD_Line", values=ad)
    
    # =========================================================================
    # Calculate All Indicators
    # =========================================================================
    
    def calculate_all(self) -> Dict[str, IndicatorResult]:
        """
        Calculate all available indicators.
        
        Returns:
            Dictionary mapping indicator names to IndicatorResult objects
        """
        results = {}
        
        # Trend indicators
        results["SMA_20"] = self.sma(20)
        results["SMA_50"] = self.sma(50)
        results["SMA_200"] = self.sma(200)
        results["EMA_12"] = self.ema(12)
        results["EMA_26"] = self.ema(26)
        results["MACD"] = self.macd()
        
        # Momentum indicators
        results["RSI"] = self.rsi()
        results["ROC"] = self.roc()
        
        # Volatility indicators
        results["Bollinger"] = self.bollinger_bands()
        results["Volatility"] = self.volatility()
        
        # Volume indicators (if volume available)
        if self.volume is not None:
            results["OBV"] = self.obv()
        
        # Indicators requiring OHLC
        if self.high is not None and self.low is not None:
            results["ATR"] = self.atr()
            results["Stochastic"] = self.stochastic()
            results["Williams_R"] = self.williams_r()
            results["ADX"] = self.adx()
            
            if self.volume is not None:
                results["MFI"] = self.mfi()
                results["VWAP"] = self.vwap()
                results["AD_Line"] = self.ad_line()
        
        return results


def calculate_all_indicators(
    df: pd.DataFrame,
    include_volume: bool = True,
) -> pd.DataFrame:
    """
    Calculate all technical indicators and return as a DataFrame.
    
    Convenience function that creates a TechnicalIndicators instance,
    calculates all indicators, and combines them into a single DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
        include_volume: Whether to calculate volume indicators
        
    Returns:
        DataFrame with all calculated indicator columns
    """
    ti = TechnicalIndicators(df)
    results = ti.calculate_all()
    
    # Build output DataFrame
    output = df.copy()
    
    for name, result in results.items():
        output[name] = result.values
        
        if result.signal is not None:
            output[f"{name}_signal"] = result.signal
        if result.upper is not None:
            output[f"{name}_upper"] = result.upper
        if result.lower is not None:
            output[f"{name}_lower"] = result.lower
        if result.histogram is not None:
            output[f"{name}_histogram"] = result.histogram
    
    return output


def calculate_feature_vector(
    df: pd.DataFrame,
    lookback: int = 1,
) -> Dict[str, float]:
    """
    Calculate a feature vector from the most recent data.
    
    Generates normalized features suitable for ML model input.
    
    Args:
        df: DataFrame with OHLCV data
        lookback: How many periods back to average
        
    Returns:
        Dictionary of feature name to value
    """
    ti = TechnicalIndicators(df)
    
    features = {}
    
    # Price features
    close = df["close"].iloc[-1]
    
    # Trend features
    sma20 = ti.sma(20).values.iloc[-1]
    sma50 = ti.sma(50).values.iloc[-1]
    ema12 = ti.ema(12).values.iloc[-1]
    
    features["price_vs_sma20"] = (close - sma20) / sma20 if sma20 else 0
    features["price_vs_sma50"] = (close - sma50) / sma50 if sma50 else 0
    features["sma20_vs_sma50"] = (sma20 - sma50) / sma50 if sma50 else 0
    
    # MACD features
    macd = ti.macd()
    features["macd"] = macd.values.iloc[-1] / close if close else 0
    features["macd_signal"] = macd.signal.iloc[-1] / close if close else 0
    features["macd_histogram"] = macd.histogram.iloc[-1] / close if close else 0
    
    # Momentum features
    rsi = ti.rsi().values.iloc[-1]
    features["rsi"] = rsi / 100 if not np.isnan(rsi) else 0.5
    features["rsi_overbought"] = 1 if rsi > 70 else 0
    features["rsi_oversold"] = 1 if rsi < 30 else 0
    
    roc = ti.roc().values.iloc[-1]
    features["roc"] = roc / 100 if not np.isnan(roc) else 0
    
    # Volatility features
    bb = ti.bollinger_bands()
    bb_width = (bb.upper.iloc[-1] - bb.lower.iloc[-1]) / bb.values.iloc[-1]
    features["bb_width"] = bb_width if not np.isnan(bb_width) else 0
    
    bb_position = (close - bb.lower.iloc[-1]) / (bb.upper.iloc[-1] - bb.lower.iloc[-1])
    features["bb_position"] = bb_position if not np.isnan(bb_position) else 0.5
    
    vol = ti.volatility().values.iloc[-1]
    features["volatility"] = vol if not np.isnan(vol) else 0
    
    # Additional features if OHLC available
    if "high" in df.columns and "low" in df.columns:
        atr = ti.atr().values.iloc[-1]
        features["atr_pct"] = atr / close if close and not np.isnan(atr) else 0
        
        stoch = ti.stochastic()
        features["stochastic_k"] = stoch.values.iloc[-1] / 100 if not np.isnan(stoch.values.iloc[-1]) else 0.5
        features["stochastic_d"] = stoch.signal.iloc[-1] / 100 if not np.isnan(stoch.signal.iloc[-1]) else 0.5
    
    return features


# =============================================================================
# Signal Generation Functions
# =============================================================================

def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate buy/sell signals based on technical indicators.
    
    Combines multiple indicators to produce trading signals.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        DataFrame with signal columns added
    """
    ti = TechnicalIndicators(df)
    signals = df.copy()
    
    # RSI signals
    rsi = ti.rsi().values
    signals["rsi_signal"] = np.where(rsi < 30, 1, np.where(rsi > 70, -1, 0))
    
    # MACD signals
    macd = ti.macd()
    signals["macd_signal"] = np.where(
        macd.values > macd.signal, 1,
        np.where(macd.values < macd.signal, -1, 0)
    )
    
    # Moving average crossover
    sma20 = ti.sma(20).values
    sma50 = ti.sma(50).values
    signals["ma_signal"] = np.where(sma20 > sma50, 1, np.where(sma20 < sma50, -1, 0))
    
    # Bollinger Band signals
    bb = ti.bollinger_bands()
    signals["bb_signal"] = np.where(
        df["close"] < bb.lower, 1,  # Buy when below lower band
        np.where(df["close"] > bb.upper, -1, 0)  # Sell when above upper band
    )
    
    # Combined signal (majority vote)
    signal_cols = ["rsi_signal", "macd_signal", "ma_signal", "bb_signal"]
    signals["combined_signal"] = signals[signal_cols].sum(axis=1)
    signals["final_signal"] = np.where(
        signals["combined_signal"] >= 2, 1,  # Buy if 2+ bullish signals
        np.where(signals["combined_signal"] <= -2, -1, 0)  # Sell if 2+ bearish
    )
    
    return signals

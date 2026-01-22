"""
Feature Engineering Package
============================

This package provides feature engineering capabilities for the
AutoTrader AI recommendation engine, including:

- Technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Price data fetching and caching
- Feature vector generation for ML models

Usage:
    from ml_services.feature_engineering.src import (
        TechnicalIndicators,
        PriceDataProvider,
        TechnicalFeatureProvider,
    )
    
    # Calculate technical indicators
    ti = TechnicalIndicators(price_df)
    rsi = ti.rsi()
    macd = ti.macd()
    
    # Get price data
    provider = PriceDataProvider()
    await provider.initialize()
    df = await provider.get_historical("AAPL", period="1mo")
    
    # Get ML features
    features = TechnicalFeatureProvider()
    await features.initialize()
    feature_dict = await features.get_features("AAPL")
"""

from .technical_indicators import (
    TechnicalIndicators,
    IndicatorResult,
    calculate_all_indicators,
    calculate_feature_vector,
    generate_signals,
)

from .price_data import (
    PriceDataProvider,
    TechnicalFeatureProvider,
    PriceBar,
    Quote,
)

__all__ = [
    # Technical indicators
    "TechnicalIndicators",
    "IndicatorResult",
    "calculate_all_indicators",
    "calculate_feature_vector",
    "generate_signals",
    
    # Price data
    "PriceDataProvider",
    "TechnicalFeatureProvider",
    "PriceBar",
    "Quote",
]

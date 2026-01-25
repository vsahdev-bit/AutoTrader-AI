"""
Unit Tests for Regime Classifier
=================================

Tests the regime classification model to ensure:
1. Correct regime detection across all 4 dimensions
2. Proper signal weight adjustments for different regimes
3. Hysteresis prevents flip-flopping
4. Edge cases are handled gracefully
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from regime_classifier import (
    RegimeClassifier,
    RegimeState,
    RegimeSignalWeights,
    VolatilityRegime,
    TrendRegime,
    LiquidityRegime,
    InformationRegime,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def classifier():
    """Create a regime classifier with hysteresis disabled for testing."""
    return RegimeClassifier(enable_hysteresis=False)


@pytest.fixture
def classifier_with_hysteresis():
    """Create a regime classifier with hysteresis enabled."""
    return RegimeClassifier(enable_hysteresis=True)


def create_mock_technical_features(
    volatility: float = 0.20,
    bb_width: float = 0.04,
    price_vs_sma20: float = 0.0,
    price_vs_sma50: float = 0.0,
    sma20_vs_sma50: float = 0.0,
    macd_histogram_normalized: float = 0.0,
    rsi: float = 0.5,
    volume_ratio: float = 1.0,
    current_price: float = 100.0,
    atr_percent: float = 0.02,
):
    """Create mock technical features for testing."""
    mock = Mock()
    mock.volatility = volatility
    mock.bb_width = bb_width
    mock.price_vs_sma20 = price_vs_sma20
    mock.price_vs_sma50 = price_vs_sma50
    mock.sma20_vs_sma50 = sma20_vs_sma50
    mock.macd_histogram_normalized = macd_histogram_normalized
    mock.rsi = rsi
    mock.volume_ratio = volume_ratio
    mock.current_price = current_price
    mock.atr_percent = atr_percent
    return mock


def create_mock_news_features(
    article_count_1d: int = 5,
    article_count_7d: int = 20,
    volume_ratio: float = 1.0,
    sentiment_volatility_7d: float = 0.1,
    earnings_sentiment: float = None,
):
    """Create mock news features for testing."""
    mock = Mock()
    mock.article_count_1d = article_count_1d
    mock.article_count_7d = article_count_7d
    mock.volume_ratio = volume_ratio
    mock.sentiment_volatility_7d = sentiment_volatility_7d
    mock.earnings_sentiment = earnings_sentiment
    return mock


# =============================================================================
# Volatility Regime Tests
# =============================================================================

class TestVolatilityRegime:
    """Tests for volatility regime classification."""
    
    def test_low_volatility(self, classifier):
        """Test low volatility regime detection."""
        tech = create_mock_technical_features(
            volatility=0.10,  # Well below mean of 0.20
            bb_width=0.02,    # Narrow bands
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.volatility == VolatilityRegime.LOW
        assert regime.volatility_zscore < -0.5
    
    def test_normal_volatility(self, classifier):
        """Test normal volatility regime detection."""
        tech = create_mock_technical_features(
            volatility=0.20,  # At mean
            bb_width=0.04,    # Normal bands
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.volatility == VolatilityRegime.NORMAL
        assert -0.5 <= regime.volatility_zscore <= 0.5
    
    def test_high_volatility(self, classifier):
        """Test high volatility regime detection."""
        tech = create_mock_technical_features(
            volatility=0.30,  # Above mean
            bb_width=0.08,    # Wide bands
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.volatility == VolatilityRegime.HIGH
        assert regime.volatility_zscore > 0.5
    
    def test_extreme_volatility(self, classifier):
        """Test extreme volatility regime detection."""
        tech = create_mock_technical_features(
            volatility=0.50,  # Very high
            bb_width=0.12,    # Very wide bands
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.volatility == VolatilityRegime.EXTREME
        assert regime.volatility_zscore > 1.5


# =============================================================================
# Trend Regime Tests
# =============================================================================

class TestTrendRegime:
    """Tests for trend regime classification."""
    
    def test_strong_uptrend(self, classifier):
        """Test strong uptrend detection."""
        tech = create_mock_technical_features(
            price_vs_sma20=0.05,   # 5% above SMA20
            price_vs_sma50=0.08,   # 8% above SMA50
            sma20_vs_sma50=0.03,   # SMA20 above SMA50
            macd_histogram_normalized=0.002,  # Positive MACD
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.trend == TrendRegime.STRONG_UPTREND
        assert regime.trend_strength >= 0.7
    
    def test_uptrend(self, classifier):
        """Test moderate uptrend detection."""
        tech = create_mock_technical_features(
            price_vs_sma20=0.03,
            price_vs_sma50=0.04,
            sma20_vs_sma50=0.02,
            macd_histogram_normalized=0.001,
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.trend in [TrendRegime.UPTREND, TrendRegime.STRONG_UPTREND]
    
    def test_downtrend(self, classifier):
        """Test downtrend detection."""
        tech = create_mock_technical_features(
            price_vs_sma20=-0.05,
            price_vs_sma50=-0.08,
            sma20_vs_sma50=-0.03,
            macd_histogram_normalized=-0.002,
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.trend in [TrendRegime.DOWNTREND, TrendRegime.STRONG_DOWNTREND]
    
    def test_choppy_market(self, classifier):
        """Test choppy/directionless market detection."""
        tech = create_mock_technical_features(
            price_vs_sma20=0.01,   # Near SMA20
            price_vs_sma50=-0.01,  # Near SMA50
            sma20_vs_sma50=0.005,  # SMAs close
            macd_histogram_normalized=0.0001,  # Near zero
            rsi=0.5,  # Neutral RSI
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.trend in [TrendRegime.CHOPPY, TrendRegime.MEAN_REVERTING]
    
    def test_mean_reverting(self, classifier):
        """Test mean-reverting regime detection."""
        tech = create_mock_technical_features(
            price_vs_sma20=0.07,  # Extended above
            rsi=0.75,  # Overbought - high reversion probability
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.reversion_probability > 0.6


# =============================================================================
# Liquidity Regime Tests
# =============================================================================

class TestLiquidityRegime:
    """Tests for liquidity regime classification."""
    
    def test_high_liquidity(self, classifier):
        """Test high liquidity detection."""
        tech = create_mock_technical_features(volume_ratio=2.0)  # 2x average volume
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.liquidity == LiquidityRegime.HIGH
    
    def test_normal_liquidity(self, classifier):
        """Test normal liquidity detection."""
        tech = create_mock_technical_features(volume_ratio=1.0)
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.liquidity == LiquidityRegime.NORMAL
    
    def test_thin_liquidity(self, classifier):
        """Test thin liquidity detection."""
        tech = create_mock_technical_features(volume_ratio=0.5)  # Half average
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.liquidity == LiquidityRegime.THIN
    
    def test_illiquid(self, classifier):
        """Test illiquid regime detection."""
        tech = create_mock_technical_features(volume_ratio=0.2)  # Very low
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.liquidity == LiquidityRegime.ILLIQUID


# =============================================================================
# Information Regime Tests
# =============================================================================

class TestInformationRegime:
    """Tests for information/news regime classification."""
    
    def test_quiet_market(self, classifier):
        """Test quiet news environment detection."""
        news = create_mock_news_features(article_count_1d=1)  # Very few articles
        
        regime = classifier.classify("AAPL", news_features=news)
        
        assert regime.information == InformationRegime.QUIET
    
    def test_normal_news(self, classifier):
        """Test normal news flow detection."""
        news = create_mock_news_features(article_count_1d=5)  # Normal
        
        regime = classifier.classify("AAPL", news_features=news)
        
        assert regime.information == InformationRegime.NORMAL
    
    def test_news_driven(self, classifier):
        """Test news-driven regime detection."""
        news = create_mock_news_features(article_count_1d=15)  # High news
        
        regime = classifier.classify("AAPL", news_features=news)
        
        assert regime.information == InformationRegime.NEWS_DRIVEN
    
    def test_earnings_regime(self, classifier):
        """Test earnings regime detection."""
        news = create_mock_news_features(
            article_count_1d=12,
            sentiment_volatility_7d=0.4,  # High sentiment volatility
            earnings_sentiment=0.5,
        )
        
        regime = classifier.classify("AAPL", news_features=news)
        
        assert regime.information == InformationRegime.EARNINGS


# =============================================================================
# Signal Weights Tests
# =============================================================================

class TestSignalWeights:
    """Tests for regime-adaptive signal weight calculation."""
    
    def test_default_weights_sum_to_one(self, classifier):
        """Test that default weights sum to 1.0."""
        tech = create_mock_technical_features()
        regime = classifier.classify("AAPL", technical_features=tech)
        weights = classifier.get_signal_weights(regime)
        
        total = (
            weights.news_sentiment +
            weights.news_momentum +
            weights.technical_trend +
            weights.technical_momentum
        )
        
        assert abs(total - 1.0) < 0.01
    
    def test_high_vol_reduces_confidence(self, classifier):
        """Test that high volatility reduces confidence multiplier."""
        tech = create_mock_technical_features(volatility=0.40, bb_width=0.10)
        regime = classifier.classify("AAPL", technical_features=tech)
        weights = classifier.get_signal_weights(regime)
        
        assert weights.confidence_multiplier < 1.0
    
    def test_extreme_vol_reduces_trade_frequency(self, classifier):
        """Test that extreme volatility reduces trade frequency."""
        tech = create_mock_technical_features(volatility=0.50, bb_width=0.12)
        regime = classifier.classify("AAPL", technical_features=tech)
        weights = classifier.get_signal_weights(regime)
        
        assert weights.trade_frequency_modifier < 1.0
        assert weights.risk_warning_level == 2
    
    def test_trending_market_weights_trend_higher(self, classifier):
        """Test that trending markets weight technical trend higher."""
        # Create strong uptrend
        tech = create_mock_technical_features(
            price_vs_sma20=0.06,
            price_vs_sma50=0.10,
            sma20_vs_sma50=0.04,
            macd_histogram_normalized=0.003,
        )
        regime = classifier.classify("AAPL", technical_features=tech)
        
        # Get weights for trending regime
        weights = classifier.get_signal_weights(regime)
        
        # Technical trend should be weighted higher than default (0.25)
        # After normalization, it should be > 0.25
        assert weights.technical_trend > 0.25
    
    def test_news_driven_weights_news_higher(self, classifier):
        """Test that news-driven regime weights news signals higher."""
        news = create_mock_news_features(article_count_1d=20)
        regime = classifier.classify("AAPL", news_features=news)
        weights = classifier.get_signal_weights(regime)
        
        # News signals should be weighted higher
        assert weights.news_sentiment > 0.30  # Default is 0.30
    
    def test_choppy_market_reduces_confidence(self, classifier):
        """Test that choppy market reduces confidence."""
        tech = create_mock_technical_features(
            price_vs_sma20=0.01,
            price_vs_sma50=-0.01,
            macd_histogram_normalized=0.0001,
        )
        regime = classifier.classify("AAPL", technical_features=tech)
        weights = classifier.get_signal_weights(regime)
        
        if regime.trend == TrendRegime.CHOPPY:
            assert weights.confidence_multiplier < 1.0


# =============================================================================
# Hysteresis Tests
# =============================================================================

class TestHysteresis:
    """Tests for regime hysteresis (prevents flip-flopping)."""
    
    def test_regime_persists_without_change(self, classifier_with_hysteresis):
        """Test that regime requires persistence to change."""
        classifier = classifier_with_hysteresis
        
        # First classification - normal volatility
        tech1 = create_mock_technical_features(volatility=0.20)
        regime1 = classifier.classify("AAPL", technical_features=tech1)
        
        # Second classification - slightly high volatility
        # Should NOT change yet due to hysteresis
        tech2 = create_mock_technical_features(volatility=0.28)
        regime2 = classifier.classify("AAPL", technical_features=tech2)
        
        # Volatility bar count should increase
        assert regime2.volatility_bars >= 1
    
    def test_persistent_regime_change_succeeds(self, classifier_with_hysteresis):
        """Test that persistent regime changes are accepted."""
        classifier = classifier_with_hysteresis
        
        # Classify multiple times with same high volatility
        for i in range(5):
            tech = create_mock_technical_features(volatility=0.40, bb_width=0.10)
            regime = classifier.classify("AAPL", technical_features=tech)
        
        # After enough persistence, regime should change
        assert regime.volatility == VolatilityRegime.HIGH


# =============================================================================
# Risk Score Tests
# =============================================================================

class TestRiskScore:
    """Tests for regime risk score calculation."""
    
    def test_low_risk_regime(self, classifier):
        """Test low risk regime has low risk score."""
        tech = create_mock_technical_features(
            volatility=0.10,
            bb_width=0.02,
            price_vs_sma20=0.03,
            price_vs_sma50=0.04,
            volume_ratio=1.2,
        )
        news = create_mock_news_features(article_count_1d=3)
        
        regime = classifier.classify("AAPL", technical_features=tech, news_features=news)
        
        # Low vol + uptrend + liquid + quiet = low risk
        assert regime.regime_risk_score < 0.4
    
    def test_high_risk_regime(self, classifier):
        """Test high risk regime has high risk score."""
        tech = create_mock_technical_features(
            volatility=0.45,
            bb_width=0.11,
            price_vs_sma20=0.01,
            price_vs_sma50=-0.01,
            volume_ratio=0.3,
        )
        news = create_mock_news_features(article_count_1d=20)
        
        regime = classifier.classify("AAPL", technical_features=tech, news_features=news)
        
        # High vol + choppy + thin liquidity + news-driven = high risk
        assert regime.regime_risk_score > 0.5
        assert regime.is_high_risk()


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_no_features(self, classifier):
        """Test classification with no features."""
        regime = classifier.classify("AAPL")
        
        # Should return default regimes
        assert regime.volatility == VolatilityRegime.NORMAL
        assert regime.trend == TrendRegime.CHOPPY
        assert regime.liquidity == LiquidityRegime.NORMAL
        assert regime.information == InformationRegime.NORMAL
    
    def test_partial_features(self, classifier):
        """Test classification with partial features."""
        tech = create_mock_technical_features(volatility=0.35)
        # No news features
        
        regime = classifier.classify("AAPL", technical_features=tech)
        
        assert regime.volatility == VolatilityRegime.HIGH
        assert regime.symbol == "AAPL"
    
    def test_regime_state_to_dict(self, classifier):
        """Test RegimeState serialization."""
        tech = create_mock_technical_features()
        regime = classifier.classify("AAPL", technical_features=tech)
        
        d = regime.to_dict()
        
        assert d["symbol"] == "AAPL"
        assert "volatility" in d
        assert "trend" in d
        assert "risk_score" in d
    
    def test_regime_label(self, classifier):
        """Test regime label generation."""
        tech = create_mock_technical_features(
            volatility=0.40,
            price_vs_sma20=-0.05,
            price_vs_sma50=-0.08,
        )
        
        regime = classifier.classify("AAPL", technical_features=tech)
        label = regime.get_regime_label()
        
        assert isinstance(label, str)
        assert len(label) > 0
    
    def test_explanation_generation(self, classifier):
        """Test regime explanation generation."""
        tech = create_mock_technical_features(volatility=0.35)
        news = create_mock_news_features(article_count_1d=15)
        
        regime = classifier.classify("AAPL", technical_features=tech, news_features=news)
        explanation = classifier.get_regime_explanation(regime)
        
        assert "regime_label" in explanation
        assert "risk_level" in explanation
        assert "dimensions" in explanation
        assert "explanations" in explanation


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

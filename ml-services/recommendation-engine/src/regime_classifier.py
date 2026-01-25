"""
Regime Classification Model
============================

This module implements a regime classification system for the recommendation engine.
Regime classification is critical because signals behave very differently across
market conditions - the same RSI oversold signal might be a buy in a calm market
but a trap in a crash.

Core Regime Dimensions:
----------------------
1. Volatility Regime: Low / Normal / High
2. Trend Regime: Trending / Mean-Reverting / Choppy
3. Liquidity Regime: Liquid / Thin
4. Information Regime: Quiet / News-Driven / Social-Driven

How Regime Is Used:
------------------
Regime does NOT decide BUY/SELL directly. It controls:
- Signal weights (tech vs news vs social)
- Confidence scaling (penalize bad fits)
- Trade frequency (fewer trades in chaos)
- Risk limits (smaller size in high vol)
- Explanation tone ("High-risk setup")

Example: Same Signal, Different Outcome
--------------------------------------
Signal: RSI oversold + Positive sentiment

| Regime                    | Action              |
|---------------------------|---------------------|
| Low vol, mean-reverting   | BUY (high confidence)|
| High vol, news shock      | HOLD (low confidence)|
| Retail-mania              | FADE or SKIP        |

This is why regime matters more than indicators.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

logger = logging.getLogger(__name__)


# =============================================================================
# Regime Enums
# =============================================================================

class VolatilityRegime(Enum):
    """Volatility regime classification."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"  # Crisis-level volatility


class TrendRegime(Enum):
    """Trend regime classification."""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    MEAN_REVERTING = "mean_reverting"
    CHOPPY = "choppy"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


class LiquidityRegime(Enum):
    """Liquidity regime classification."""
    HIGH = "high"
    NORMAL = "normal"
    THIN = "thin"
    ILLIQUID = "illiquid"


class InformationRegime(Enum):
    """Information/news flow regime classification."""
    QUIET = "quiet"
    NORMAL = "normal"
    NEWS_DRIVEN = "news_driven"
    SOCIAL_DRIVEN = "social_driven"
    EARNINGS = "earnings"  # Special case: earnings season


# =============================================================================
# Regime Data Classes
# =============================================================================

@dataclass
class RegimeState:
    """
    Complete regime state for a symbol at a point in time.
    
    This captures all four regime dimensions plus derived properties
    that affect how signals should be interpreted.
    """
    symbol: str
    timestamp: datetime
    
    # Core regime dimensions
    volatility: VolatilityRegime
    trend: TrendRegime
    liquidity: LiquidityRegime
    information: InformationRegime
    
    # Raw scores (for debugging and fine-grained control)
    volatility_zscore: float = 0.0
    trend_strength: float = 0.0  # 0 to 1, higher = stronger trend
    reversion_probability: float = 0.0  # 0 to 1
    volume_zscore: float = 0.0
    news_velocity: float = 0.0  # Articles per hour normalized
    social_velocity: float = 0.0  # Social mentions acceleration
    
    # Regime persistence tracking
    volatility_bars: int = 1  # How many bars in current volatility regime
    trend_bars: int = 1  # How many bars in current trend regime
    
    # Derived risk metrics
    regime_risk_score: float = 0.5  # 0 = very safe, 1 = very risky
    regime_confidence: float = 0.5  # Confidence in regime classification
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "volatility": self.volatility.value,
            "trend": self.trend.value,
            "liquidity": self.liquidity.value,
            "information": self.information.value,
            "volatility_zscore": round(self.volatility_zscore, 3),
            "trend_strength": round(self.trend_strength, 3),
            "reversion_probability": round(self.reversion_probability, 3),
            "volume_zscore": round(self.volume_zscore, 3),
            "news_velocity": round(self.news_velocity, 3),
            "social_velocity": round(self.social_velocity, 3),
            "volatility_bars": self.volatility_bars,
            "trend_bars": self.trend_bars,
            "regime_risk_score": round(self.regime_risk_score, 3),
            "regime_confidence": round(self.regime_confidence, 3),
        }
    
    def get_regime_label(self) -> str:
        """Get a human-readable regime label."""
        vol_label = {
            VolatilityRegime.LOW: "Calm",
            VolatilityRegime.NORMAL: "",
            VolatilityRegime.HIGH: "Volatile",
            VolatilityRegime.EXTREME: "Crisis",
        }[self.volatility]
        
        trend_label = {
            TrendRegime.STRONG_UPTREND: "Strong Bull",
            TrendRegime.UPTREND: "Bullish",
            TrendRegime.MEAN_REVERTING: "Range-Bound",
            TrendRegime.CHOPPY: "Choppy",
            TrendRegime.DOWNTREND: "Bearish",
            TrendRegime.STRONG_DOWNTREND: "Strong Bear",
        }[self.trend]
        
        info_label = {
            InformationRegime.QUIET: "",
            InformationRegime.NORMAL: "",
            InformationRegime.NEWS_DRIVEN: "News-Heavy",
            InformationRegime.SOCIAL_DRIVEN: "Social-Driven",
            InformationRegime.EARNINGS: "Earnings",
        }[self.information]
        
        parts = [p for p in [vol_label, trend_label, info_label] if p]
        return " / ".join(parts) if parts else "Normal Market"
    
    def is_high_risk(self) -> bool:
        """Check if current regime is high risk."""
        return (
            self.volatility in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME] or
            self.liquidity in [LiquidityRegime.THIN, LiquidityRegime.ILLIQUID] or
            self.regime_risk_score > 0.7
        )
    
    def is_favorable_for_signals(self) -> bool:
        """Check if regime is favorable for trading signals."""
        # Best regimes: calm, trending, liquid, not news-shocked
        return (
            self.volatility in [VolatilityRegime.LOW, VolatilityRegime.NORMAL] and
            self.trend not in [TrendRegime.CHOPPY] and
            self.liquidity in [LiquidityRegime.HIGH, LiquidityRegime.NORMAL] and
            self.information not in [InformationRegime.NEWS_DRIVEN, InformationRegime.SOCIAL_DRIVEN]
        )


@dataclass
class PositionSizingRecommendation:
    """
    Position sizing recommendation based on regime risk.
    
    Professional traders adjust position size based on market conditions.
    In high volatility or uncertain regimes, smaller positions reduce risk.
    """
    # Position size as percentage of normal (1.0 = 100% of standard size)
    size_multiplier: float = 1.0
    
    # Maximum position as percentage of portfolio
    max_position_percent: float = 5.0
    
    # Recommended number of entries (1 = all at once, 3 = scale in thirds)
    scale_in_entries: int = 1
    
    # Time between scale-in entries (in hours)
    scale_in_interval_hours: int = 0
    
    # Risk per trade as percentage of portfolio
    risk_per_trade_percent: float = 1.0
    
    # Explanation for the sizing
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "size_multiplier": self.size_multiplier,
            "max_position_percent": self.max_position_percent,
            "scale_in_entries": self.scale_in_entries,
            "scale_in_interval_hours": self.scale_in_interval_hours,
            "risk_per_trade_percent": self.risk_per_trade_percent,
            "reasoning": self.reasoning,
        }


@dataclass
class StopLossRecommendation:
    """
    Stop-loss recommendation based on regime.
    
    Stop-loss placement should adapt to market volatility:
    - Low volatility: tighter stops (less noise)
    - High volatility: wider stops (avoid whipsaws)
    """
    # Stop-loss as ATR multiplier (e.g., 2.0 = 2x ATR)
    atr_multiplier: float = 2.0
    
    # Stop-loss as percentage from entry
    percent_from_entry: float = 3.0
    
    # Use trailing stop (adjusts as price moves favorably)
    use_trailing_stop: bool = False
    
    # Trailing stop activation (profit % before trailing kicks in)
    trailing_activation_percent: float = 2.0
    
    # Take-profit as ATR multiplier (risk:reward ratio target)
    take_profit_atr_multiplier: float = 4.0
    
    # Recommended risk:reward ratio
    risk_reward_ratio: float = 2.0
    
    # Time-based stop (exit after N days if no movement)
    time_stop_days: Optional[int] = None
    
    # Explanation
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "atr_multiplier": self.atr_multiplier,
            "percent_from_entry": self.percent_from_entry,
            "use_trailing_stop": self.use_trailing_stop,
            "trailing_activation_percent": self.trailing_activation_percent,
            "take_profit_atr_multiplier": self.take_profit_atr_multiplier,
            "risk_reward_ratio": self.risk_reward_ratio,
            "time_stop_days": self.time_stop_days,
            "reasoning": self.reasoning,
        }


@dataclass
class RegimeSignalWeights:
    """
    Dynamic signal weights based on current regime.
    
    These weights determine how much each signal type contributes
    to the final recommendation score.
    """
    news_sentiment: float = 0.30
    news_momentum: float = 0.20
    technical_trend: float = 0.25
    technical_momentum: float = 0.25
    
    # Confidence multiplier (applied to final confidence)
    confidence_multiplier: float = 1.0
    
    # Trade frequency modifier (1.0 = normal, 0.5 = half, 0 = skip)
    trade_frequency_modifier: float = 1.0
    
    # Risk warning level (0 = none, 1 = caution, 2 = high risk)
    risk_warning_level: int = 0
    
    # Position sizing recommendation
    position_sizing: Optional[PositionSizingRecommendation] = None
    
    # Stop-loss recommendation
    stop_loss: Optional[StopLossRecommendation] = None
    
    def validate(self) -> bool:
        """Ensure weights sum to 1.0."""
        total = (
            self.news_sentiment + 
            self.news_momentum + 
            self.technical_trend + 
            self.technical_momentum
        )
        return abs(total - 1.0) < 0.01
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "news_sentiment": self.news_sentiment,
            "news_momentum": self.news_momentum,
            "technical_trend": self.technical_trend,
            "technical_momentum": self.technical_momentum,
            "confidence_multiplier": self.confidence_multiplier,
            "trade_frequency_modifier": self.trade_frequency_modifier,
            "risk_warning_level": self.risk_warning_level,
        }
        if self.position_sizing:
            result["position_sizing"] = self.position_sizing.to_dict()
        if self.stop_loss:
            result["stop_loss"] = self.stop_loss.to_dict()
        return result


# =============================================================================
# Regime Classifier
# =============================================================================

class RegimeClassifier:
    """
    Classifies market regime from technical and news features.
    
    This is the core regime detection system. It analyzes multiple
    dimensions of market behavior to determine the current regime
    and how signals should be weighted.
    
    Usage:
        classifier = RegimeClassifier()
        
        # Classify regime
        regime = classifier.classify(
            symbol="AAPL",
            technical_features=tech_features,
            news_features=news_features,
        )
        
        # Get signal weights for this regime
        weights = classifier.get_signal_weights(regime)
        
        # Use weights in recommendation calculation
        score = (
            news_sentiment * weights.news_sentiment +
            news_momentum * weights.news_momentum +
            ...
        )
    """
    
    # Volatility thresholds (z-score based)
    VOL_LOW_THRESHOLD = -0.5
    VOL_HIGH_THRESHOLD = 0.5
    VOL_EXTREME_THRESHOLD = 1.5
    
    # Trend strength thresholds
    TREND_STRONG_THRESHOLD = 0.7
    TREND_WEAK_THRESHOLD = 0.3
    
    # Volume thresholds (z-score based)
    VOLUME_LOW_THRESHOLD = -0.5
    VOLUME_HIGH_THRESHOLD = 0.5
    
    # News velocity thresholds
    NEWS_QUIET_THRESHOLD = 0.3
    NEWS_HIGH_THRESHOLD = 2.0
    
    # Hysteresis: minimum bars to confirm regime change
    REGIME_PERSISTENCE_BARS = 3
    
    def __init__(
        self,
        volatility_lookback: int = 20,
        trend_lookback: int = 14,
        enable_hysteresis: bool = True,
    ):
        """
        Initialize the regime classifier.
        
        Args:
            volatility_lookback: Periods for volatility calculation
            trend_lookback: Periods for trend detection
            enable_hysteresis: Whether to require regime persistence
        """
        self.volatility_lookback = volatility_lookback
        self.trend_lookback = trend_lookback
        self.enable_hysteresis = enable_hysteresis
        
        # State tracking for hysteresis
        self._previous_regimes: Dict[str, RegimeState] = {}
        self._regime_counters: Dict[str, Dict[str, int]] = {}
    
    def classify(
        self,
        symbol: str,
        technical_features: Optional[Any] = None,
        news_features: Optional[Any] = None,
        social_features: Optional[Dict[str, Any]] = None,
    ) -> RegimeState:
        """
        Classify the current market regime for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            technical_features: TechnicalFeatures object
            news_features: NewsFeatures object
            social_features: Optional social media features dict
            
        Returns:
            RegimeState with all regime dimensions classified
        """
        timestamp = datetime.utcnow()
        
        # Classify each dimension
        volatility, vol_zscore = self._classify_volatility(technical_features)
        trend, trend_strength, reversion_prob = self._classify_trend(technical_features)
        liquidity, volume_zscore = self._classify_liquidity(technical_features, news_features)
        information, news_vel, social_vel = self._classify_information(news_features, social_features)
        
        # Create initial regime state
        regime = RegimeState(
            symbol=symbol,
            timestamp=timestamp,
            volatility=volatility,
            trend=trend,
            liquidity=liquidity,
            information=information,
            volatility_zscore=vol_zscore,
            trend_strength=trend_strength,
            reversion_probability=reversion_prob,
            volume_zscore=volume_zscore,
            news_velocity=news_vel,
            social_velocity=social_vel,
        )
        
        # Apply hysteresis if enabled
        if self.enable_hysteresis:
            regime = self._apply_hysteresis(symbol, regime)
        
        # Calculate derived metrics
        regime.regime_risk_score = self._calculate_risk_score(regime)
        regime.regime_confidence = self._calculate_regime_confidence(regime, technical_features, news_features)
        
        # Store for next classification
        self._previous_regimes[symbol] = regime
        
        return regime
    
    def _classify_volatility(
        self,
        technical_features: Optional[Any],
    ) -> Tuple[VolatilityRegime, float]:
        """
        Classify volatility regime.
        
        Uses:
        - Historical volatility
        - ATR percentage
        - Bollinger Band width
        """
        if not technical_features or not hasattr(technical_features, 'volatility'):
            return VolatilityRegime.NORMAL, 0.0
        
        # Get volatility metrics
        hist_vol = getattr(technical_features, 'volatility', 0.0)
        atr_pct = getattr(technical_features, 'atr_percent', 0.0)
        bb_width = getattr(technical_features, 'bb_width', 0.0)
        
        # Calculate volatility z-score
        # Using typical stock volatility: mean ~20%, std ~10%
        # These are approximate values; ideally computed from historical data
        vol_mean = 0.20
        vol_std = 0.10
        
        vol_zscore = (hist_vol - vol_mean) / vol_std if vol_std > 0 else 0.0
        
        # Adjust with BB width (normalized, typical range 0.02-0.10)
        bb_mean = 0.04
        bb_std = 0.02
        bb_zscore = (bb_width - bb_mean) / bb_std if bb_std > 0 else 0.0
        
        # Combined volatility score (weighted average)
        combined_zscore = vol_zscore * 0.6 + bb_zscore * 0.4
        
        # Classify
        if combined_zscore >= self.VOL_EXTREME_THRESHOLD:
            regime = VolatilityRegime.EXTREME
        elif combined_zscore >= self.VOL_HIGH_THRESHOLD:
            regime = VolatilityRegime.HIGH
        elif combined_zscore <= self.VOL_LOW_THRESHOLD:
            regime = VolatilityRegime.LOW
        else:
            regime = VolatilityRegime.NORMAL
        
        return regime, combined_zscore
    
    def _classify_trend(
        self,
        technical_features: Optional[Any],
    ) -> Tuple[TrendRegime, float, float]:
        """
        Classify trend regime.
        
        Uses:
        - Price vs moving averages
        - MACD
        - ADX (if available)
        - Price momentum
        
        Returns:
            Tuple of (TrendRegime, trend_strength, reversion_probability)
        """
        if not technical_features:
            return TrendRegime.CHOPPY, 0.0, 0.5
        
        # Get trend indicators
        price_vs_sma20 = getattr(technical_features, 'price_vs_sma20', 0.0)
        price_vs_sma50 = getattr(technical_features, 'price_vs_sma50', 0.0)
        sma20_vs_sma50 = getattr(technical_features, 'sma20_vs_sma50', 0.0)
        macd_hist = getattr(technical_features, 'macd_histogram_normalized', 0.0)
        rsi = getattr(technical_features, 'rsi', 0.5)
        
        # Calculate trend strength (0 to 1)
        # Strong trend: price consistently above/below MAs, aligned MAs
        trend_signals = []
        
        # Price vs SMA20 signal
        if abs(price_vs_sma20) > 0.02:
            trend_signals.append(1 if price_vs_sma20 > 0 else -1)
        
        # Price vs SMA50 signal
        if abs(price_vs_sma50) > 0.03:
            trend_signals.append(1 if price_vs_sma50 > 0 else -1)
        
        # SMA alignment signal
        if abs(sma20_vs_sma50) > 0.01:
            trend_signals.append(1 if sma20_vs_sma50 > 0 else -1)
        
        # MACD signal
        if abs(macd_hist) > 0.0005:
            trend_signals.append(1 if macd_hist > 0 else -1)
        
        # Calculate trend strength and direction
        if trend_signals:
            avg_signal = sum(trend_signals) / len(trend_signals)
            trend_strength = abs(avg_signal)
            trend_direction = 1 if avg_signal > 0 else -1
        else:
            trend_strength = 0.0
            trend_direction = 0
        
        # Calculate reversion probability
        # High RSI + extended from MA = high reversion probability
        reversion_prob = 0.5
        
        if rsi > 0.7 and price_vs_sma20 > 0.05:
            reversion_prob = 0.7 + (rsi - 0.7) * 0.5
        elif rsi < 0.3 and price_vs_sma20 < -0.05:
            reversion_prob = 0.7 + (0.3 - rsi) * 0.5
        
        reversion_prob = min(1.0, max(0.0, reversion_prob))
        
        # Classify regime
        if trend_strength >= self.TREND_STRONG_THRESHOLD:
            if trend_direction > 0:
                regime = TrendRegime.STRONG_UPTREND
            else:
                regime = TrendRegime.STRONG_DOWNTREND
        elif trend_strength >= self.TREND_WEAK_THRESHOLD:
            if trend_direction > 0:
                regime = TrendRegime.UPTREND
            else:
                regime = TrendRegime.DOWNTREND
        elif reversion_prob > 0.6:
            regime = TrendRegime.MEAN_REVERTING
        else:
            regime = TrendRegime.CHOPPY
        
        return regime, trend_strength, reversion_prob
    
    def _classify_liquidity(
        self,
        technical_features: Optional[Any],
        news_features: Optional[Any],
    ) -> Tuple[LiquidityRegime, float]:
        """
        Classify liquidity regime.
        
        Uses:
        - Volume ratio (current vs average)
        - Spread (if available)
        """
        volume_zscore = 0.0
        
        # Get volume ratio from technical features
        if technical_features:
            volume_ratio = getattr(technical_features, 'volume_ratio', 1.0)
            # Convert ratio to z-score (ratio of 1.0 = normal)
            volume_zscore = (volume_ratio - 1.0) / 0.5
        
        # Classify
        if volume_zscore >= 1.0:
            regime = LiquidityRegime.HIGH
        elif volume_zscore >= self.VOLUME_LOW_THRESHOLD:
            regime = LiquidityRegime.NORMAL
        elif volume_zscore >= -1.0:
            regime = LiquidityRegime.THIN
        else:
            regime = LiquidityRegime.ILLIQUID
        
        return regime, volume_zscore
    
    def _classify_information(
        self,
        news_features: Optional[Any],
        social_features: Optional[Dict[str, Any]],
    ) -> Tuple[InformationRegime, float, float]:
        """
        Classify information regime.
        
        Uses:
        - News velocity (articles per time period)
        - News volume ratio
        - Social mention acceleration
        
        Returns:
            Tuple of (InformationRegime, news_velocity, social_velocity)
        """
        news_velocity = 0.0
        social_velocity = 0.0
        
        # Calculate news velocity
        if news_features:
            article_count_1d = getattr(news_features, 'article_count_1d', 0)
            article_count_7d = getattr(news_features, 'article_count_7d', 0)
            volume_ratio = getattr(news_features, 'volume_ratio', 1.0)
            
            # News velocity: articles per day normalized
            # Typical stock gets 2-5 articles per day
            news_velocity = article_count_1d / 5.0
            
            # Check for earnings-related news (high sentiment volatility + high volume)
            sentiment_volatility = getattr(news_features, 'sentiment_volatility_7d', 0.0)
            earnings_sentiment = getattr(news_features, 'earnings_sentiment', None)
            
            if earnings_sentiment is not None or (sentiment_volatility > 0.3 and article_count_1d > 10):
                return InformationRegime.EARNINGS, news_velocity, social_velocity
        
        # Calculate social velocity (if available)
        if social_features:
            mention_count = social_features.get('mention_count_1h', 0)
            mention_avg = social_features.get('mention_avg_1h', 1)
            social_velocity = mention_count / mention_avg if mention_avg > 0 else 0.0
        
        # Classify based on velocities
        if social_velocity > 3.0:
            regime = InformationRegime.SOCIAL_DRIVEN
        elif news_velocity >= self.NEWS_HIGH_THRESHOLD:
            regime = InformationRegime.NEWS_DRIVEN
        elif news_velocity <= self.NEWS_QUIET_THRESHOLD:
            regime = InformationRegime.QUIET
        else:
            regime = InformationRegime.NORMAL
        
        return regime, news_velocity, social_velocity
    
    def _apply_hysteresis(self, symbol: str, regime: RegimeState) -> RegimeState:
        """
        Apply hysteresis to prevent regime flip-flopping.
        
        A regime change only takes effect if it persists for
        REGIME_PERSISTENCE_BARS consecutive classifications.
        """
        previous = self._previous_regimes.get(symbol)
        
        if previous is None:
            # First classification, no hysteresis needed
            return regime
        
        # Initialize counters for this symbol if needed
        if symbol not in self._regime_counters:
            self._regime_counters[symbol] = {
                'volatility': 0,
                'trend': 0,
            }
        
        counters = self._regime_counters[symbol]
        
        # Check volatility regime change
        if regime.volatility != previous.volatility:
            counters['volatility'] += 1
            if counters['volatility'] < self.REGIME_PERSISTENCE_BARS:
                # Not enough persistence, revert to previous
                regime.volatility = previous.volatility
                regime.volatility_bars = previous.volatility_bars + 1
            else:
                # Regime change confirmed
                counters['volatility'] = 0
                regime.volatility_bars = 1
        else:
            counters['volatility'] = 0
            regime.volatility_bars = previous.volatility_bars + 1
        
        # Check trend regime change
        if regime.trend != previous.trend:
            counters['trend'] += 1
            if counters['trend'] < self.REGIME_PERSISTENCE_BARS:
                regime.trend = previous.trend
                regime.trend_bars = previous.trend_bars + 1
            else:
                counters['trend'] = 0
                regime.trend_bars = 1
        else:
            counters['trend'] = 0
            regime.trend_bars = previous.trend_bars + 1
        
        return regime
    
    def _calculate_risk_score(self, regime: RegimeState) -> float:
        """
        Calculate overall risk score for the regime.
        
        Returns 0-1 score where higher = more risky.
        """
        risk = 0.0
        
        # Volatility risk
        vol_risk = {
            VolatilityRegime.LOW: 0.0,
            VolatilityRegime.NORMAL: 0.2,
            VolatilityRegime.HIGH: 0.6,
            VolatilityRegime.EXTREME: 1.0,
        }
        risk += vol_risk[regime.volatility] * 0.35
        
        # Trend risk (choppy = high risk)
        trend_risk = {
            TrendRegime.STRONG_UPTREND: 0.1,
            TrendRegime.UPTREND: 0.15,
            TrendRegime.MEAN_REVERTING: 0.3,
            TrendRegime.CHOPPY: 0.7,
            TrendRegime.DOWNTREND: 0.4,
            TrendRegime.STRONG_DOWNTREND: 0.5,
        }
        risk += trend_risk[regime.trend] * 0.25
        
        # Liquidity risk
        liq_risk = {
            LiquidityRegime.HIGH: 0.0,
            LiquidityRegime.NORMAL: 0.1,
            LiquidityRegime.THIN: 0.5,
            LiquidityRegime.ILLIQUID: 0.9,
        }
        risk += liq_risk[regime.liquidity] * 0.20
        
        # Information risk
        info_risk = {
            InformationRegime.QUIET: 0.1,
            InformationRegime.NORMAL: 0.2,
            InformationRegime.NEWS_DRIVEN: 0.5,
            InformationRegime.SOCIAL_DRIVEN: 0.7,
            InformationRegime.EARNINGS: 0.6,
        }
        risk += info_risk[regime.information] * 0.20
        
        return min(1.0, max(0.0, risk))
    
    def _calculate_regime_confidence(
        self,
        regime: RegimeState,
        technical_features: Optional[Any],
        news_features: Optional[Any],
    ) -> float:
        """
        Calculate confidence in the regime classification.
        
        Higher confidence when:
        - Multiple indicators agree
        - Regime has persisted
        - Data quality is good
        """
        confidence = 0.5  # Base confidence
        
        # Persistence bonus (up to 0.2)
        min_bars = min(regime.volatility_bars, regime.trend_bars)
        persistence_bonus = min(0.2, min_bars * 0.02)
        confidence += persistence_bonus
        
        # Data quality bonus (up to 0.2)
        data_quality = 0.0
        if technical_features and hasattr(technical_features, 'current_price'):
            if technical_features.current_price > 0:
                data_quality += 0.1
        if news_features and hasattr(news_features, 'article_count_1d'):
            if news_features.article_count_1d > 0:
                data_quality += 0.1
        confidence += data_quality
        
        # Clear regime bonus (not borderline)
        if abs(regime.volatility_zscore) > 1.0:
            confidence += 0.05
        if regime.trend_strength > 0.6:
            confidence += 0.05
        
        return min(1.0, max(0.0, confidence))
    
    def get_signal_weights(self, regime: RegimeState) -> RegimeSignalWeights:
        """
        Get signal weights optimized for the current regime.
        
        This is the key method that adapts signal weighting to market conditions.
        
        General principles:
        - Trending markets: weight technical trend signals higher
        - Choppy markets: weight mean-reversion signals higher
        - News-driven: weight news sentiment higher
        - High volatility: reduce confidence, fewer trades
        """
        # Start with default weights
        weights = RegimeSignalWeights()
        
        # Adjust for volatility regime
        if regime.volatility == VolatilityRegime.HIGH:
            # In high vol: reduce momentum signals, increase caution
            weights.technical_momentum *= 0.7
            weights.confidence_multiplier = 0.7
            weights.risk_warning_level = 1
        elif regime.volatility == VolatilityRegime.EXTREME:
            # Extreme vol: significantly reduce all signals
            weights.technical_momentum *= 0.5
            weights.news_momentum *= 0.5
            weights.confidence_multiplier = 0.4
            weights.trade_frequency_modifier = 0.5
            weights.risk_warning_level = 2
        elif regime.volatility == VolatilityRegime.LOW:
            # Low vol: signals more reliable
            weights.confidence_multiplier = 1.1
        
        # Adjust for trend regime
        if regime.trend in [TrendRegime.STRONG_UPTREND, TrendRegime.STRONG_DOWNTREND]:
            # Strong trend: weight trend signals higher
            weights.technical_trend *= 1.3
            weights.news_sentiment *= 0.9
        elif regime.trend == TrendRegime.MEAN_REVERTING:
            # Mean reverting: weight momentum (contrarian) signals higher
            weights.technical_momentum *= 1.3
            weights.technical_trend *= 0.8
        elif regime.trend == TrendRegime.CHOPPY:
            # Choppy: reduce all technical signals
            weights.technical_trend *= 0.6
            weights.technical_momentum *= 0.7
            weights.confidence_multiplier *= 0.8
            weights.trade_frequency_modifier = 0.7
        
        # Adjust for information regime
        if regime.information == InformationRegime.NEWS_DRIVEN:
            # News-driven: weight news signals much higher
            weights.news_sentiment *= 1.5
            weights.news_momentum *= 1.3
            weights.technical_trend *= 0.7
        elif regime.information == InformationRegime.SOCIAL_DRIVEN:
            # Social-driven: be cautious, high noise
            weights.news_sentiment *= 0.8
            weights.confidence_multiplier *= 0.7
            weights.risk_warning_level = max(weights.risk_warning_level, 1)
        elif regime.information == InformationRegime.EARNINGS:
            # Earnings: news is key but uncertain
            weights.news_sentiment *= 1.4
            weights.technical_trend *= 0.6
            weights.confidence_multiplier *= 0.8
        elif regime.information == InformationRegime.QUIET:
            # Quiet: technical signals more reliable
            weights.technical_trend *= 1.1
            weights.technical_momentum *= 1.1
            weights.news_sentiment *= 0.8
        
        # Adjust for liquidity
        if regime.liquidity in [LiquidityRegime.THIN, LiquidityRegime.ILLIQUID]:
            weights.confidence_multiplier *= 0.7
            weights.trade_frequency_modifier *= 0.7
            weights.risk_warning_level = max(weights.risk_warning_level, 1)
        
        # Normalize weights to sum to 1.0
        total = (
            weights.news_sentiment +
            weights.news_momentum +
            weights.technical_trend +
            weights.technical_momentum
        )
        
        if total > 0:
            weights.news_sentiment /= total
            weights.news_momentum /= total
            weights.technical_trend /= total
            weights.technical_momentum /= total
        
        # Add position sizing recommendation
        weights.position_sizing = self.get_position_sizing(regime)
        
        # Add stop-loss recommendation
        weights.stop_loss = self.get_stop_loss_recommendation(regime)
        
        return weights
    
    def get_position_sizing(self, regime: RegimeState) -> PositionSizingRecommendation:
        """
        Get position sizing recommendation based on regime.
        
        Professional traders adjust position size based on market conditions:
        - High volatility: Smaller positions (more risk per unit)
        - Low liquidity: Smaller positions (harder to exit)
        - Choppy markets: Smaller positions (higher failure rate)
        - Strong trends: Can use larger positions
        
        Args:
            regime: Current regime state
            
        Returns:
            PositionSizingRecommendation with sizing parameters
        """
        # Start with default sizing
        sizing = PositionSizingRecommendation(
            size_multiplier=1.0,
            max_position_percent=5.0,
            scale_in_entries=1,
            scale_in_interval_hours=0,
            risk_per_trade_percent=1.0,
            reasoning="",
        )
        
        reasons = []
        
        # Adjust for volatility
        if regime.volatility == VolatilityRegime.EXTREME:
            sizing.size_multiplier *= 0.25
            sizing.max_position_percent = 2.0
            sizing.risk_per_trade_percent = 0.5
            sizing.scale_in_entries = 3
            sizing.scale_in_interval_hours = 24
            reasons.append("Extreme volatility: position reduced to 25%, scale in over 3 days")
        elif regime.volatility == VolatilityRegime.HIGH:
            sizing.size_multiplier *= 0.50
            sizing.max_position_percent = 3.0
            sizing.risk_per_trade_percent = 0.75
            sizing.scale_in_entries = 2
            sizing.scale_in_interval_hours = 12
            reasons.append("High volatility: position reduced to 50%, scale in over 2 entries")
        elif regime.volatility == VolatilityRegime.LOW:
            sizing.size_multiplier *= 1.25
            sizing.max_position_percent = 6.0
            reasons.append("Low volatility: can use slightly larger position")
        
        # Adjust for liquidity
        if regime.liquidity == LiquidityRegime.ILLIQUID:
            sizing.size_multiplier *= 0.30
            sizing.max_position_percent = min(sizing.max_position_percent, 1.5)
            sizing.scale_in_entries = max(sizing.scale_in_entries, 3)
            reasons.append("Illiquid: position capped at 1.5%, scale in carefully")
        elif regime.liquidity == LiquidityRegime.THIN:
            sizing.size_multiplier *= 0.60
            sizing.max_position_percent = min(sizing.max_position_percent, 3.0)
            sizing.scale_in_entries = max(sizing.scale_in_entries, 2)
            reasons.append("Thin liquidity: position reduced, use limit orders")
        
        # Adjust for trend
        if regime.trend == TrendRegime.CHOPPY:
            sizing.size_multiplier *= 0.60
            sizing.risk_per_trade_percent = min(sizing.risk_per_trade_percent, 0.5)
            reasons.append("Choppy market: smaller size due to higher failure rate")
        elif regime.trend in [TrendRegime.STRONG_UPTREND, TrendRegime.STRONG_DOWNTREND]:
            # Strong trends allow for slightly larger positions
            sizing.size_multiplier *= 1.15
            reasons.append("Strong trend: slightly larger position allowed")
        
        # Adjust for information regime
        if regime.information == InformationRegime.EARNINGS:
            sizing.size_multiplier *= 0.50
            sizing.max_position_percent = min(sizing.max_position_percent, 2.5)
            reasons.append("Earnings period: position halved due to gap risk")
        elif regime.information == InformationRegime.SOCIAL_DRIVEN:
            sizing.size_multiplier *= 0.40
            sizing.max_position_percent = min(sizing.max_position_percent, 2.0)
            sizing.scale_in_entries = max(sizing.scale_in_entries, 2)
            reasons.append("Social-driven: high reversal risk, minimal position")
        elif regime.information == InformationRegime.NEWS_DRIVEN:
            sizing.size_multiplier *= 0.75
            reasons.append("News-driven: slightly reduced position")
        
        # Clamp size multiplier
        sizing.size_multiplier = max(0.1, min(1.5, sizing.size_multiplier))
        
        # Set reasoning
        if reasons:
            sizing.reasoning = " | ".join(reasons)
        else:
            sizing.reasoning = "Normal conditions: standard position sizing"
        
        return sizing
    
    def get_stop_loss_recommendation(
        self,
        regime: RegimeState,
        atr_percent: float = 0.02,
    ) -> StopLossRecommendation:
        """
        Get stop-loss recommendation based on regime.
        
        Stop-loss placement should adapt to market conditions:
        - High volatility: wider stops to avoid whipsaws
        - Low volatility: tighter stops for capital efficiency
        - Trending: use trailing stops
        - Choppy: time-based stops may be useful
        
        Args:
            regime: Current regime state
            atr_percent: ATR as percentage of price (default 2%)
            
        Returns:
            StopLossRecommendation with stop parameters
        """
        # Start with default stop-loss
        stop = StopLossRecommendation(
            atr_multiplier=2.0,
            percent_from_entry=3.0,
            use_trailing_stop=False,
            trailing_activation_percent=2.0,
            take_profit_atr_multiplier=4.0,
            risk_reward_ratio=2.0,
            time_stop_days=None,
            reasoning="",
        )
        
        reasons = []
        
        # Adjust for volatility
        if regime.volatility == VolatilityRegime.EXTREME:
            stop.atr_multiplier = 3.5
            stop.percent_from_entry = 8.0
            stop.take_profit_atr_multiplier = 5.0
            stop.risk_reward_ratio = 1.5  # Accept lower R:R in extreme conditions
            reasons.append("Extreme vol: wide stop (3.5x ATR) to avoid whipsaw")
        elif regime.volatility == VolatilityRegime.HIGH:
            stop.atr_multiplier = 2.5
            stop.percent_from_entry = 5.0
            stop.take_profit_atr_multiplier = 4.5
            reasons.append("High vol: wider stop (2.5x ATR)")
        elif regime.volatility == VolatilityRegime.LOW:
            stop.atr_multiplier = 1.5
            stop.percent_from_entry = 2.0
            stop.take_profit_atr_multiplier = 3.0
            stop.risk_reward_ratio = 2.5  # Can target better R:R in calm markets
            reasons.append("Low vol: tight stop (1.5x ATR) for capital efficiency")
        
        # Adjust for trend
        if regime.trend in [TrendRegime.STRONG_UPTREND, TrendRegime.STRONG_DOWNTREND]:
            stop.use_trailing_stop = True
            stop.trailing_activation_percent = 1.5
            stop.take_profit_atr_multiplier *= 1.3  # Let winners run
            reasons.append("Strong trend: use trailing stop, let winners run")
        elif regime.trend == TrendRegime.UPTREND:
            stop.use_trailing_stop = True
            stop.trailing_activation_percent = 2.0
            reasons.append("Uptrend: trailing stop after 2% profit")
        elif regime.trend == TrendRegime.MEAN_REVERTING:
            stop.use_trailing_stop = False  # Fixed targets work better
            stop.take_profit_atr_multiplier = 3.0
            stop.risk_reward_ratio = 1.5
            reasons.append("Mean-reverting: fixed target, tighter R:R")
        elif regime.trend == TrendRegime.CHOPPY:
            stop.time_stop_days = 5  # Exit if no movement
            stop.risk_reward_ratio = 1.5
            reasons.append("Choppy: use time stop (5 days), accept lower R:R")
        
        # Adjust for liquidity
        if regime.liquidity in [LiquidityRegime.THIN, LiquidityRegime.ILLIQUID]:
            stop.atr_multiplier *= 1.3  # Wider stop for slippage
            stop.percent_from_entry *= 1.3
            reasons.append("Low liquidity: wider stop for slippage buffer")
        
        # Adjust for information regime
        if regime.information == InformationRegime.EARNINGS:
            stop.atr_multiplier = max(stop.atr_multiplier, 3.0)
            stop.percent_from_entry = max(stop.percent_from_entry, 6.0)
            stop.time_stop_days = 3  # Don't hold through uncertainty
            reasons.append("Earnings: wide stop for gap risk, short time horizon")
        elif regime.information == InformationRegime.NEWS_DRIVEN:
            stop.use_trailing_stop = True
            stop.trailing_activation_percent = 1.0  # Lock in gains quickly
            reasons.append("News-driven: quick trailing to lock gains")
        
        # Calculate actual percent based on ATR if provided
        if atr_percent > 0:
            calculated_stop_percent = atr_percent * stop.atr_multiplier * 100
            stop.percent_from_entry = max(stop.percent_from_entry, calculated_stop_percent)
        
        # Set reasoning
        if reasons:
            stop.reasoning = " | ".join(reasons)
        else:
            stop.reasoning = "Normal conditions: standard 2x ATR stop"
        
        return stop
    
    def get_regime_explanation(self, regime: RegimeState) -> Dict[str, Any]:
        """
        Generate a human-readable explanation of the current regime.
        
        Returns dict suitable for including in recommendation explanations.
        """
        explanations = []
        warnings = []
        
        # Volatility explanation
        vol_explanations = {
            VolatilityRegime.LOW: "Market volatility is low, providing a stable environment for signals.",
            VolatilityRegime.NORMAL: "Market volatility is at normal levels.",
            VolatilityRegime.HIGH: "Market volatility is elevated. Signals may be less reliable.",
            VolatilityRegime.EXTREME: "CAUTION: Extreme market volatility detected. High uncertainty.",
        }
        if regime.volatility != VolatilityRegime.NORMAL:
            explanations.append(vol_explanations[regime.volatility])
        if regime.volatility in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
            warnings.append("High volatility - consider smaller position sizes")
        
        # Trend explanation
        trend_explanations = {
            TrendRegime.STRONG_UPTREND: "Strong uptrend in progress. Trend-following signals favored.",
            TrendRegime.UPTREND: "Moderate uptrend detected.",
            TrendRegime.MEAN_REVERTING: "Price is range-bound. Mean-reversion signals may be effective.",
            TrendRegime.CHOPPY: "Choppy, directionless price action. Signals less reliable.",
            TrendRegime.DOWNTREND: "Moderate downtrend detected.",
            TrendRegime.STRONG_DOWNTREND: "Strong downtrend in progress. Caution advised for long positions.",
        }
        explanations.append(trend_explanations[regime.trend])
        if regime.trend == TrendRegime.CHOPPY:
            warnings.append("Choppy market - reduced signal reliability")
        
        # Information explanation
        info_explanations = {
            InformationRegime.QUIET: "Low news flow - technical signals weighted higher.",
            InformationRegime.NORMAL: None,
            InformationRegime.NEWS_DRIVEN: "High news activity driving price action. News sentiment weighted higher.",
            InformationRegime.SOCIAL_DRIVEN: "Social media activity elevated. Be cautious of noise.",
            InformationRegime.EARNINGS: "Earnings-related news detected. Higher uncertainty expected.",
        }
        if info_explanations[regime.information]:
            explanations.append(info_explanations[regime.information])
        if regime.information == InformationRegime.SOCIAL_DRIVEN:
            warnings.append("Social-driven moves may reverse quickly")
        
        # Liquidity explanation
        if regime.liquidity in [LiquidityRegime.THIN, LiquidityRegime.ILLIQUID]:
            explanations.append("Trading volume is below average. Liquidity may be limited.")
            warnings.append("Low liquidity - wider spreads possible")
        
        return {
            "regime_label": regime.get_regime_label(),
            "risk_level": "high" if regime.is_high_risk() else "normal",
            "explanations": explanations,
            "warnings": warnings,
            "dimensions": {
                "volatility": regime.volatility.value,
                "trend": regime.trend.value,
                "liquidity": regime.liquidity.value,
                "information": regime.information.value,
            },
            "metrics": {
                "risk_score": round(regime.regime_risk_score, 2),
                "confidence": round(regime.regime_confidence, 2),
            }
        }

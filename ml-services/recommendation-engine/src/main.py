"""
Recommendation Engine - Main Service
=====================================

This is the core ML service for the AutoTrader AI platform's Continuous
Intelligence Plane. It generates AI-powered trading recommendations by
analyzing multiple data signals and running ML inference.

Architecture Overview:
---------------------
The Recommendation Engine is part of the "always-on" intelligence layer:

1. Signal Ingestion:
   - News sentiment (from news processing pipeline)
   - Technical indicators (price, volume, RSI, MACD)
   - Social signals (future: Twitter, Reddit sentiment)

2. Feature Engineering:
   - News features from ClickHouse (sentiment_1d, momentum, etc.)
   - Technical features computed on-demand
   - Combined feature vectors for ML model

3. ML Inference (this service):
   - Rule-based model (current implementation)
   - Future: Trained ML model (XGBoost, Neural Network)
   - Confidence calibration
   - Explainable outputs

4. Output:
   - REST API for real-time recommendations
   - Cached results in Redis
   - Stored in PostgreSQL for history

API Endpoints:
-------------
- GET  /health              - Health check for load balancers
- POST /recommendations     - Generate recommendations for symbols
- GET  /recommendations/{symbol} - Get latest recommendation for symbol
- GET  /features/{symbol}   - Get current features for symbol (debugging)

Technology Stack:
----------------
- FastAPI: High-performance async web framework
- Pydantic: Request/response validation
- uvicorn: ASGI server
- ClickHouse: Feature storage
- Redis: Recommendation caching

Port: 8000 (configurable via environment)
"""
import logging
import os
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import uvicorn
import asyncpg
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Recommendation Engine",
    description="AI-powered trading recommendation service for AutoTrader AI",
    version="2.0.0",
)

# =============================================================================
# Pydantic Models
# =============================================================================

class RecommendationRequest(BaseModel):
    """Request model for generating recommendations."""
    user_id: str = Field(..., description="User ID requesting recommendations")
    symbols: List[str] = Field(..., description="Stock symbols to analyze")
    include_features: bool = Field(False, description="Include feature details in response")


class SignalExplanation(BaseModel):
    """Detailed explanation of signals contributing to recommendation."""
    # News signals
    news_sentiment: Optional[float] = Field(None, description="News sentiment score (-1 to 1)")
    news_momentum: Optional[float] = Field(None, description="Sentiment momentum (improving/declining)")
    news_volume: Optional[str] = Field(None, description="News volume indicator (low/normal/high)")
    
    # Technical signals
    technical_rsi: Optional[float] = Field(None, description="RSI indicator value (0-1)")
    technical_rsi_signal: Optional[str] = Field(None, description="RSI signal (oversold/neutral/overbought)")
    technical_macd: Optional[float] = Field(None, description="MACD histogram (normalized)")
    technical_trend: Optional[str] = Field(None, description="Price trend (bullish/neutral/bearish)")
    technical_bb_position: Optional[float] = Field(None, description="Bollinger Band position (0-1)")
    
    # Price info
    current_price: Optional[float] = Field(None, description="Current stock price")
    price_change_1d: Optional[float] = Field(None, description="1-day price change %")
    price_change_5d: Optional[float] = Field(None, description="5-day price change %")


class Recommendation(BaseModel):
    """A single stock recommendation."""
    symbol: str = Field(..., description="Stock ticker symbol")
    action: str = Field(..., description="Recommended action: BUY, SELL, or HOLD")
    score: Optional[float] = Field(None, description="Raw combined score (-1 to 1)")
    normalized_score: Optional[float] = Field(None, ge=0, le=1, description="Normalized score (0-1)")
    confidence: float = Field(..., ge=0, le=1, description="Model confidence (0-1)")
    price_at_recommendation: Optional[float] = Field(None, description="Stock price at recommendation time")
    news_sentiment_score: Optional[float] = Field(None, description="News sentiment component score (-1 to 1)")
    news_momentum_score: Optional[float] = Field(None, description="News momentum component score (-1 to 1)")
    technical_trend_score: Optional[float] = Field(None, description="Technical trend component score (-1 to 1)")
    technical_momentum_score: Optional[float] = Field(None, description="Technical momentum component score (-1 to 1)")
    rsi: Optional[float] = Field(None, description="RSI indicator value (0-1)")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram value (normalized)")
    price_vs_sma20: Optional[float] = Field(None, description="Price vs 20-day SMA ratio")
    news_sentiment_1d: Optional[float] = Field(None, description="1-day news sentiment score")
    article_count_24h: Optional[int] = Field(None, description="Number of articles in last 24 hours")
    explanation: Dict[str, Any] = Field(..., description="Human-readable explanation")
    signals: Optional[SignalExplanation] = Field(None, description="Signal breakdown")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class RecommendationResponse(BaseModel):
    """Response containing recommendations for requested symbols."""
    user_id: str
    recommendations: List[Recommendation]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    news_features_available: bool
    technical_features_available: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RecommendationHistoryItem(BaseModel):
    """A single recommendation history item from the database."""
    id: str = Field(..., description="Unique recommendation ID")
    symbol: str = Field(..., description="Stock ticker symbol")
    action: str = Field(..., description="Recommended action: BUY, SELL, or HOLD")
    score: Optional[float] = Field(None, description="Raw score from -1 to 1")
    normalized_score: Optional[float] = Field(None, description="Normalized score from 0 to 1")
    confidence: Optional[float] = Field(None, description="Model confidence (0-1)")
    price_at_recommendation: Optional[float] = Field(None, description="Stock price at recommendation time")
    news_sentiment_score: Optional[float] = Field(None, description="News sentiment component score")
    news_momentum_score: Optional[float] = Field(None, description="News momentum component score")
    technical_trend_score: Optional[float] = Field(None, description="Technical trend component score")
    technical_momentum_score: Optional[float] = Field(None, description="Technical momentum component score")
    rsi: Optional[float] = Field(None, description="RSI indicator value")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram value")
    price_vs_sma20: Optional[float] = Field(None, description="Price vs SMA20 ratio")
    news_sentiment_1d: Optional[float] = Field(None, description="1-day news sentiment")
    article_count_24h: Optional[int] = Field(None, description="Number of articles in last 24h")
    explanation: Optional[Dict[str, Any]] = Field(None, description="Human-readable explanation")
    data_sources_used: Optional[List[str]] = Field(None, description="Data sources used")
    generated_at: Optional[datetime] = Field(None, description="When recommendation was generated")
    created_at: Optional[datetime] = Field(None, description="When record was created")


class RecommendationHistoryResponse(BaseModel):
    """Response containing recommendation history for a symbol."""
    symbol: str
    recommendations: List[RecommendationHistoryItem]
    count: int


# =============================================================================
# Global State (initialized on startup)
# =============================================================================

# Feature providers (lazy initialized)
_news_provider = None
_technical_provider = None
_db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> Optional[asyncpg.Pool]:
    """Get or initialize the database connection pool."""
    global _db_pool
    
    if _db_pool is None:
        try:
            postgres_dsn = os.getenv(
                'DATABASE_URL',
                'postgresql://autotrader:autotrader@localhost:5432/autotrader'
            )
            _db_pool = await asyncpg.create_pool(
                postgres_dsn,
                min_size=2,
                max_size=10,
            )
            logger.info("Database pool created successfully")
        except Exception as e:
            logger.warning(f"Database pool not available: {e}")
            _db_pool = None
    
    return _db_pool


async def get_news_provider():
    """Get or initialize the news feature provider."""
    global _news_provider
    
    if _news_provider is None:
        try:
            from news_features import NewsFeatureProvider
            
            _news_provider = NewsFeatureProvider(
                clickhouse_host=os.getenv("CLICKHOUSE_HOST", "localhost"),
                clickhouse_port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
                clickhouse_user=os.getenv("CLICKHOUSE_USER", "default"),
                clickhouse_password=os.getenv("CLICKHOUSE_PASSWORD", ""),
                redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            )
            await _news_provider.initialize()
            logger.info("News feature provider initialized")
        except Exception as e:
            logger.warning(f"News features not available: {e}")
            _news_provider = None
    
    return _news_provider


async def get_technical_provider():
    """Get or initialize the technical feature provider."""
    global _technical_provider
    
    if _technical_provider is None:
        try:
            from technical_features import TechnicalFeatureProvider
            
            _technical_provider = TechnicalFeatureProvider(
                redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
                cache_ttl_seconds=300,  # 5 minutes cache
            )
            await _technical_provider.initialize()
            logger.info("Technical feature provider initialized")
        except Exception as e:
            logger.warning(f"Technical features not available: {e}")
            _technical_provider = None
    
    return _technical_provider


# =============================================================================
# Recommendation Logic
# =============================================================================

class RecommendationEngine:
    """
    Core recommendation engine logic.
    
    Combines news sentiment analysis with technical indicators to generate
    trading recommendations. Uses a weighted scoring system with configurable
    weights for different signal types.
    
    Signal Weights (configurable, should sum to 1.0):
    - News sentiment: 30%
    - News momentum: 20%
    - Technical trend: 25%
    - Technical momentum: 25%
    
    Thresholds:
    - BUY: Combined score > 0.25
    - SELL: Combined score < -0.25
    - HOLD: Otherwise
    
    Signal Agreement Bonus:
    - When news and technical signals agree, confidence is boosted
    - When they disagree, confidence is reduced
    """
    
    # Signal weights (should sum to 1.0)
    WEIGHT_NEWS_SENTIMENT = 0.30
    WEIGHT_NEWS_MOMENTUM = 0.20
    WEIGHT_TECHNICAL_TREND = 0.25
    WEIGHT_TECHNICAL_MOMENTUM = 0.25
    
    # Action thresholds (score range is -1 to 1, normalized to 0 to 1 for display)
    # Normalized score formula: normalized = (raw + 1) / 2
    # BUY: normalized score > 0.8 → raw score > 0.6
    # SELL: normalized score < 0.5 → raw score < 0.0
    # HOLD: 0.5 <= normalized score <= 0.8 → 0.0 <= raw score <= 0.6
    BUY_THRESHOLD = 0.6   # Raw score threshold: normalized > 0.8
    SELL_THRESHOLD = 0.0  # Raw score threshold: normalized < 0.5
    
    # Confidence adjustments
    AGREEMENT_BONUS = 0.15
    DISAGREEMENT_PENALTY = 0.10
    
    def __init__(self):
        self.news_provider = None
        self.technical_provider = None
    
    async def initialize(self):
        """Initialize the recommendation engine with all feature providers."""
        self.news_provider = await get_news_provider()
        self.technical_provider = await get_technical_provider()
        
        logger.info(f"Recommendation engine initialized - "
                   f"News: {'✓' if self.news_provider else '✗'}, "
                   f"Technical: {'✓' if self.technical_provider else '✗'}")
    
    async def generate_recommendation(
        self,
        symbol: str,
        include_features: bool = False,
    ) -> Recommendation:
        """
        Generate a recommendation for a single symbol.
        
        Combines news sentiment and technical analysis to produce a
        BUY/SELL/HOLD recommendation with confidence score.
        
        Args:
            symbol: Stock ticker symbol
            include_features: Whether to include detailed feature info
            
        Returns:
            Recommendation object with action, confidence, and explanation
        """
        # Get news features
        news_features = None
        if self.news_provider:
            try:
                news_features = await self.news_provider.get_features_single(symbol)
            except Exception as e:
                logger.warning(f"Failed to get news features for {symbol}: {e}")
        
        # Get technical features
        technical_features = None
        if self.technical_provider:
            try:
                technical_features = await self.technical_provider.get_features(symbol)
            except Exception as e:
                logger.warning(f"Failed to get technical features for {symbol}: {e}")
        
        # Calculate scores from each signal type
        news_sentiment_score = self._calculate_news_sentiment_score(news_features)
        news_momentum_score = self._calculate_news_momentum_score(news_features)
        technical_trend_score = self._calculate_technical_trend_score(technical_features)
        technical_momentum_score = self._calculate_technical_momentum_score(technical_features)
        
        # Combine scores with weights
        combined_score = (
            news_sentiment_score * self.WEIGHT_NEWS_SENTIMENT +
            news_momentum_score * self.WEIGHT_NEWS_MOMENTUM +
            technical_trend_score * self.WEIGHT_TECHNICAL_TREND +
            technical_momentum_score * self.WEIGHT_TECHNICAL_MOMENTUM
        )
        
        # Determine action
        if combined_score > self.BUY_THRESHOLD:
            action = "BUY"
        elif combined_score < self.SELL_THRESHOLD:
            action = "SELL"
        else:
            action = "HOLD"
        
        # Calculate confidence (based on signal agreement and strength)
        confidence = self._calculate_confidence(
            news_sentiment_score=news_sentiment_score,
            news_momentum_score=news_momentum_score,
            technical_trend_score=technical_trend_score,
            technical_momentum_score=technical_momentum_score,
            combined_score=combined_score,
            news_features=news_features,
            technical_features=technical_features,
        )
        
        # Fetch news articles from ClickHouse for LLM context
        news_articles = []
        if self.news_provider:
            try:
                news_articles = await self.news_provider.get_news_articles(symbol, limit=10)
            except Exception as e:
                logger.warning(f"Failed to get news articles for {symbol}: {e}")
        
        # Generate LLM-powered explanation using news articles (always generate for quality explanations)
        llm_analysis = None
        try:
            llm_analysis = await self._generate_llm_explanation(
                symbol=symbol,
                action=action,
                combined_score=combined_score,
                confidence=confidence,
                news_articles=news_articles,
                news_features=news_features,
                technical_features=technical_features,
            )
        except Exception as e:
            logger.warning(f"Failed to generate LLM explanation for {symbol}: {e}")
        
        # Generate explanation
        explanation = self._generate_explanation(
            symbol=symbol,
            action=action,
            combined_score=combined_score,
            news_features=news_features,
            technical_features=technical_features,
            llm_analysis=llm_analysis,
            news_articles=news_articles,
        )
        
        # Build signals breakdown
        signals = None
        if include_features:
            signals = self._build_signal_explanation(news_features, technical_features)
        
        # Get technical indicator values
        rsi = technical_features.rsi if technical_features else None
        macd_histogram = technical_features.macd_histogram_normalized if technical_features else None
        price_vs_sma20 = technical_features.price_vs_sma20 if technical_features else None
        current_price = technical_features.current_price if technical_features else None
        
        # Get news values
        news_sentiment_1d = news_features.sentiment_1d if news_features else None
        article_count_24h = news_features.article_count_1d if news_features else 0
        
        # Normalize score to 0-1 range
        normalized_score = (combined_score + 1) / 2
        
        return Recommendation(
            symbol=symbol,
            action=action,
            score=round(combined_score, 4),
            normalized_score=round(normalized_score, 4),
            confidence=round(confidence, 3),
            price_at_recommendation=current_price,
            news_sentiment_score=round(news_sentiment_score, 4),
            news_momentum_score=round(news_momentum_score, 4),
            technical_trend_score=round(technical_trend_score, 4),
            technical_momentum_score=round(technical_momentum_score, 4),
            rsi=round(rsi, 4) if rsi is not None else None,
            macd_histogram=round(macd_histogram, 6) if macd_histogram is not None else None,
            price_vs_sma20=round(price_vs_sma20, 4) if price_vs_sma20 is not None else None,
            news_sentiment_1d=round(news_sentiment_1d, 4) if news_sentiment_1d is not None else None,
            article_count_24h=article_count_24h,
            explanation=explanation,
            signals=signals,
        )
    
    def _calculate_news_sentiment_score(self, news_features) -> float:
        """
        Calculate score from news sentiment (short-term).
        
        Returns a score from -1 to 1 based on recent sentiment.
        """
        if not news_features:
            return 0.0
        
        # Use 1-day sentiment as primary signal
        sentiment = news_features.sentiment_1d
        
        # Adjust by confidence (weight more confident sentiment higher)
        confidence_factor = 0.5 + (news_features.avg_confidence_1d * 0.5)
        
        return sentiment * confidence_factor
    
    def _calculate_news_momentum_score(self, news_features) -> float:
        """
        Calculate score from news sentiment momentum.
        
        Captures whether sentiment is improving or declining.
        """
        if not news_features:
            return 0.0
        
        # Momentum is change in sentiment (1d - 3d)
        momentum = news_features.sentiment_momentum
        
        # Scale momentum to reasonable range (-1 to 1)
        # Momentum of 0.1 is significant
        scaled_momentum = max(-1.0, min(1.0, momentum * 5))
        
        return scaled_momentum
    
    def _calculate_technical_trend_score(self, technical_features) -> float:
        """
        Calculate score from technical trend indicators.
        
        Uses price vs moving averages and MACD.
        """
        if not technical_features:
            return 0.0
        
        score = 0.0
        signals = 0
        
        # Price vs SMA20 (short-term trend)
        if technical_features.price_vs_sma20 > 0.02:
            score += 0.5
            signals += 1
        elif technical_features.price_vs_sma20 < -0.02:
            score -= 0.5
            signals += 1
        
        # Price vs SMA50 (medium-term trend)
        if technical_features.price_vs_sma50 > 0.03:
            score += 0.5
            signals += 1
        elif technical_features.price_vs_sma50 < -0.03:
            score -= 0.5
            signals += 1
        
        # MACD histogram (momentum of trend)
        if technical_features.macd_histogram_normalized > 0.001:
            score += 0.5
            signals += 1
        elif technical_features.macd_histogram_normalized < -0.001:
            score -= 0.5
            signals += 1
        
        # SMA crossover (golden/death cross signal)
        if technical_features.sma20_vs_sma50 > 0.01:
            score += 0.3
            signals += 1
        elif technical_features.sma20_vs_sma50 < -0.01:
            score -= 0.3
            signals += 1
        
        # Normalize by number of signals
        if signals > 0:
            return max(-1.0, min(1.0, score / signals))
        return 0.0
    
    def _calculate_technical_momentum_score(self, technical_features) -> float:
        """
        Calculate score from technical momentum indicators.
        
        Uses RSI, Stochastic, and ROC for mean-reversion signals.
        """
        if not technical_features:
            return 0.0
        
        score = 0.0
        signals = 0
        
        # RSI - contrarian signal (oversold = buy, overbought = sell)
        rsi = technical_features.rsi
        if rsi < 0.30:  # Oversold
            score += 0.6  # Bullish signal
            signals += 1
        elif rsi > 0.70:  # Overbought
            score -= 0.6  # Bearish signal
            signals += 1
        elif 0.45 <= rsi <= 0.55:  # Neutral zone
            signals += 1  # Count but no score change
        
        # Stochastic - similar contrarian logic
        stoch_k = technical_features.stochastic_k
        if stoch_k < 0.20:  # Oversold
            score += 0.4
            signals += 1
        elif stoch_k > 0.80:  # Overbought
            score -= 0.4
            signals += 1
        
        # ROC - momentum direction
        roc = technical_features.roc
        if roc > 0.05:  # Strong upward momentum
            score += 0.4
            signals += 1
        elif roc < -0.05:  # Strong downward momentum
            score -= 0.4
            signals += 1
        
        # Bollinger Band position
        bb_pos = technical_features.bb_position
        if bb_pos < 0.1:  # Near lower band
            score += 0.3  # Potential bounce
            signals += 1
        elif bb_pos > 0.9:  # Near upper band
            score -= 0.3  # Potential pullback
            signals += 1
        
        # Normalize
        if signals > 0:
            return max(-1.0, min(1.0, score / signals))
        return 0.0
    
    def _calculate_confidence(
        self,
        news_sentiment_score: float,
        news_momentum_score: float,
        technical_trend_score: float,
        technical_momentum_score: float,
        combined_score: float,
        news_features,
        technical_features,
    ) -> float:
        """
        Calculate confidence in the recommendation.
        
        Higher confidence when:
        - Signal strength is high (combined score far from 0)
        - News and technical signals agree
        - Multiple indicators confirm the signal
        - News volume is normal/high (recent data available)
        - Technical data quality is good
        """
        # Base confidence from signal strength (0 to 0.4)
        strength_confidence = min(abs(combined_score) / 0.5, 1.0) * 0.4
        
        # News score direction
        news_direction = 1 if (news_sentiment_score + news_momentum_score) > 0.1 else (
            -1 if (news_sentiment_score + news_momentum_score) < -0.1 else 0
        )
        
        # Technical score direction
        tech_direction = 1 if (technical_trend_score + technical_momentum_score) > 0.1 else (
            -1 if (technical_trend_score + technical_momentum_score) < -0.1 else 0
        )
        
        # Agreement bonus/penalty (0 to 0.15)
        if news_direction != 0 and tech_direction != 0:
            if news_direction == tech_direction:
                agreement_factor = self.AGREEMENT_BONUS
            else:
                agreement_factor = -self.DISAGREEMENT_PENALTY
        else:
            agreement_factor = 0.0
        
        # Data quality factor (0 to 0.3)
        quality_score = 0.15  # Base
        
        if news_features:
            if news_features.article_count_1d > 0:
                quality_score += 0.075
            if news_features.avg_confidence_1d > 0.6:
                quality_score += 0.075
        
        if technical_features:
            if technical_features.current_price > 0:
                quality_score += 0.075
            if technical_features.volatility > 0:  # Have volatility data
                quality_score += 0.075
        
        # Base confidence (0.15)
        base_confidence = 0.15
        
        # Combine all factors
        confidence = (
            base_confidence +
            strength_confidence +
            agreement_factor +
            quality_score
        )
        
        return max(0.0, min(1.0, confidence))
    
    async def _generate_llm_explanation(
        self,
        symbol: str,
        action: str,
        combined_score: float,
        confidence: float,
        news_articles: List[Dict[str, Any]],
        news_features,
        technical_features,
    ) -> Optional[str]:
        """Use LLM to generate a detailed explanation based on news articles and signals."""
        
        # Build comprehensive context for LLM
        news_context = ""
        if news_articles:
            news_context = "Recent news articles and their sentiment:\n"
            for i, article in enumerate(news_articles[:7], 1):
                title = article.get('title', 'Unknown')
                source = article.get('source', 'Unknown')
                sentiment = article.get('sentiment_score')
                sentiment_label = article.get('sentiment_label', '')
                summary = article.get('summary', '')[:200]  # Truncate long summaries
                
                sentiment_str = ""
                if sentiment is not None:
                    sentiment_str = f" (sentiment: {sentiment:.2f})"
                elif sentiment_label:
                    sentiment_str = f" ({sentiment_label})"
                
                news_context += f"{i}. [{source}] {title}{sentiment_str}\n"
                if summary:
                    news_context += f"   Summary: {summary}...\n"
        else:
            news_context = "No recent news articles available for this stock."
        
        # Add news feature summary
        news_feature_context = ""
        if news_features and news_features.article_count_1d > 0:
            news_feature_context = f"""
News Analytics Summary:
- Articles in last 24h: {news_features.article_count_1d}
- Articles in last 7d: {news_features.article_count_7d}
- 1-day sentiment: {news_features.sentiment_1d:.2f} (-1 to +1 scale)
- Sentiment momentum: {"improving" if news_features.sentiment_momentum > 0.05 else "declining" if news_features.sentiment_momentum < -0.05 else "stable"}
- News volume: {"above average" if news_features.volume_ratio > 1.5 else "below average" if news_features.volume_ratio < 0.5 else "normal"}"""
        
        technical_context = ""
        if technical_features and technical_features.current_price and technical_features.current_price > 0:
            rsi_val = f"{technical_features.rsi * 100:.1f}" if technical_features.rsi else 'N/A'
            macd_signal = 'Bullish' if (technical_features.macd_histogram_normalized or 0) > 0 else 'Bearish'
            sma20_diff = ((technical_features.price_vs_sma20 or 1) - 1) * 100
            sma50_diff = ((technical_features.price_vs_sma50 or 1) - 1) * 100
            
            rsi_interpretation = ""
            if technical_features.rsi:
                if technical_features.rsi < 0.30:
                    rsi_interpretation = " (oversold - potential buying opportunity)"
                elif technical_features.rsi > 0.70:
                    rsi_interpretation = " (overbought - potential selling pressure)"
                else:
                    rsi_interpretation = " (neutral range)"
            
            technical_context = f"""Technical Indicators:
- Current Price: ${technical_features.current_price:.2f}
- RSI: {rsi_val}{rsi_interpretation}
- MACD Signal: {macd_signal}
- Price vs 20-day MA: {sma20_diff:+.1f}% ({"above" if sma20_diff > 0 else "below"} short-term trend)
- Price vs 50-day MA: {sma50_diff:+.1f}% ({"above" if sma50_diff > 0 else "below"} medium-term trend)
- 1-day price change: {technical_features.price_change_1d * 100:.2f}%
- Volatility: {technical_features.volatility * 100:.1f}%"""
        else:
            technical_context = "Technical data unavailable."
        
        prompt = f"""You are a professional financial analyst providing stock recommendations. Generate a clear, insightful explanation for this recommendation.

Stock: {symbol}
Recommendation: {action}
Overall Score: {combined_score:.2f} (scale: -1 strong sell to +1 strong buy)
Confidence Level: {confidence * 100:.0f}%

{news_context}
{news_feature_context}

{technical_context}

Based on the above data, provide a 3-4 sentence explanation that:
1. Summarizes the key factors driving this {action} recommendation
2. Highlights specific news events or technical signals supporting the decision
3. Mentions the confidence level and any caveats
4. Is actionable and helps the investor understand the reasoning

Be specific, cite actual data points, and avoid generic statements."""

        try:
            # Try OpenAI first, then Anthropic, then Groq
            for provider in ['openai', 'anthropic', 'groq']:
                try:
                    if provider == 'openai':
                        from openai import AsyncOpenAI
                        api_key = os.getenv('OPENAI_API_KEY')
                        if not api_key:
                            continue
                        client = AsyncOpenAI(api_key=api_key)
                        response = await client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=200,
                            temperature=0.7,
                        )
                        return response.choices[0].message.content
                    
                    elif provider == 'anthropic':
                        from anthropic import AsyncAnthropic
                        api_key = os.getenv('ANTHROPIC_API_KEY')
                        if not api_key:
                            continue
                        client = AsyncAnthropic(api_key=api_key)
                        response = await client.messages.create(
                            model="claude-3-haiku-20240307",
                            max_tokens=200,
                            messages=[{"role": "user", "content": prompt}],
                        )
                        return response.content[0].text
                    
                    elif provider == 'groq':
                        from groq import AsyncGroq
                        api_key = os.getenv('GROQ_API_KEY')
                        if not api_key:
                            continue
                        client = AsyncGroq(api_key=api_key)
                        response = await client.chat.completions.create(
                            model="llama-3.1-8b-instant",
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=200,
                        )
                        return response.choices[0].message.content
                        
                except Exception as e:
                    logger.warning(f"LLM provider {provider} failed: {e}")
                    continue
            
            return None
        except Exception as e:
            logger.error(f"Failed to generate LLM explanation: {e}")
            return None
    
    def _generate_explanation(
        self,
        symbol: str,
        action: str,
        combined_score: float,
        news_features,
        technical_features,
        llm_analysis: Optional[str] = None,
        news_articles: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate human-readable explanation for the recommendation."""
        
        # Build summary components
        news_summary = ""
        technical_summary = ""
        
        # News analysis summary
        if news_features and news_features.article_count_1d > 0:
            sentiment_desc = self._describe_sentiment(news_features.sentiment_1d)
            momentum_desc = self._describe_momentum(news_features.sentiment_momentum)
            news_summary = f"News sentiment is {sentiment_desc} with {momentum_desc} momentum."
        else:
            news_summary = "Limited recent news coverage."
        
        # Technical analysis summary
        if technical_features and technical_features.current_price > 0:
            trend_desc = self._describe_technical_trend(technical_features)
            momentum_desc = self._describe_technical_momentum(technical_features)
            technical_summary = f"Technical trend is {trend_desc}. Momentum indicators show {momentum_desc} conditions."
        else:
            technical_summary = "Technical data unavailable."
        
        # Action-specific summary
        if action == "BUY":
            action_summary = f"Consider buying {symbol}."
        elif action == "SELL":
            action_summary = f"Consider selling {symbol}."
        else:
            action_summary = f"Hold current position in {symbol}."
        
        summary = f"{news_summary} {technical_summary} {action_summary}"
        
        explanation = {
            "summary": summary,
            "score": round(combined_score, 3),
            "action": action,
        }
        
        # Build factors list for clear explanation of what drove the recommendation
        factors = []
        if news_features:
            if news_features.sentiment_1d > 0.2:
                factors.append(f"Positive news sentiment ({news_features.sentiment_1d:.2f})")
            elif news_features.sentiment_1d < -0.2:
                factors.append(f"Negative news sentiment ({news_features.sentiment_1d:.2f})")
            if news_features.sentiment_momentum > 0.1:
                factors.append("Improving sentiment trend")
            elif news_features.sentiment_momentum < -0.1:
                factors.append("Declining sentiment trend")
            if news_features.article_count_1d > 5:
                factors.append(f"High news volume ({news_features.article_count_1d} articles in 24h)")
        
        if technical_features and technical_features.current_price > 0:
            if technical_features.rsi < 0.30:
                factors.append(f"RSI indicates oversold ({technical_features.rsi * 100:.0f})")
            elif technical_features.rsi > 0.70:
                factors.append(f"RSI indicates overbought ({technical_features.rsi * 100:.0f})")
            if technical_features.price_vs_sma20 > 0.03:
                factors.append("Price above 20-day moving average")
            elif technical_features.price_vs_sma20 < -0.03:
                factors.append("Price below 20-day moving average")
            if technical_features.macd_histogram_normalized > 0.001:
                factors.append("MACD shows bullish momentum")
            elif technical_features.macd_histogram_normalized < -0.001:
                factors.append("MACD shows bearish momentum")
        
        if factors:
            explanation["factors"] = factors
        
        # Add news details if available
        if news_features and news_features.article_count_1d > 0:
            explanation["news"] = {
                "articles_24h": news_features.article_count_1d,
                "articles_7d": news_features.article_count_7d,
                "sentiment_1d": round(news_features.sentiment_1d, 3),
                "sentiment_trend": "improving" if news_features.sentiment_momentum > 0.05 else (
                    "declining" if news_features.sentiment_momentum < -0.05 else "stable"
                ),
            }
        
        # Add recent news articles for context
        if news_articles:
            explanation["recent_articles"] = [
                {
                    "title": article.get("title", ""),
                    "source": article.get("source", ""),
                    "sentiment": article.get("sentiment_label") or (
                        "positive" if (article.get("sentiment_score") or 0) > 0.1 else
                        "negative" if (article.get("sentiment_score") or 0) < -0.1 else "neutral"
                    ),
                }
                for article in news_articles[:5]
            ]
        
        # Add technical details if available
        if technical_features and technical_features.current_price > 0:
            explanation["technical"] = {
                "price": round(technical_features.current_price, 2),
                "change_1d": f"{technical_features.price_change_1d * 100:.2f}%",
                "change_5d": f"{technical_features.price_change_5d * 100:.2f}%",
                "rsi": round(technical_features.rsi * 100, 1),
                "trend": self._describe_technical_trend(technical_features),
                "volatility": f"{technical_features.volatility * 100:.1f}%",
            }
        
        # Add LLM analysis if available - this is the high-quality explanation
        if llm_analysis:
            explanation["llm_analysis"] = llm_analysis
            # Also update the summary to use LLM analysis
            explanation["summary"] = llm_analysis
        
        return explanation
    
    def _build_signal_explanation(
        self,
        news_features,
        technical_features,
    ) -> SignalExplanation:
        """Build detailed signal explanation for API response."""
        
        # News signals
        news_sentiment = None
        news_momentum = None
        news_volume = None
        
        if news_features:
            news_sentiment = round(news_features.sentiment_1d, 3)
            news_momentum = round(news_features.sentiment_momentum, 3)
            news_volume = self._categorize_volume(news_features.volume_ratio)
        
        # Technical signals
        technical_rsi = None
        technical_rsi_signal = None
        technical_macd = None
        technical_trend = None
        technical_bb_position = None
        current_price = None
        price_change_1d = None
        price_change_5d = None
        
        if technical_features and technical_features.current_price > 0:
            technical_rsi = round(technical_features.rsi, 3)
            
            # RSI signal interpretation
            if technical_features.rsi < 0.3:
                technical_rsi_signal = "oversold"
            elif technical_features.rsi > 0.7:
                technical_rsi_signal = "overbought"
            else:
                technical_rsi_signal = "neutral"
            
            technical_macd = round(technical_features.macd_histogram_normalized, 6)
            technical_trend = self._describe_technical_trend(technical_features)
            technical_bb_position = round(technical_features.bb_position, 3)
            current_price = round(technical_features.current_price, 2)
            price_change_1d = round(technical_features.price_change_1d * 100, 2)
            price_change_5d = round(technical_features.price_change_5d * 100, 2)
        
        return SignalExplanation(
            news_sentiment=news_sentiment,
            news_momentum=news_momentum,
            news_volume=news_volume,
            technical_rsi=technical_rsi,
            technical_rsi_signal=technical_rsi_signal,
            technical_macd=technical_macd,
            technical_trend=technical_trend,
            technical_bb_position=technical_bb_position,
            current_price=current_price,
            price_change_1d=price_change_1d,
            price_change_5d=price_change_5d,
        )
    
    def _describe_technical_trend(self, technical_features) -> str:
        """Describe the technical trend in human-readable terms."""
        if not technical_features:
            return "unknown"
        
        # Use price vs SMAs and MACD
        bullish_signals = 0
        bearish_signals = 0
        
        if technical_features.price_vs_sma20 > 0.02:
            bullish_signals += 1
        elif technical_features.price_vs_sma20 < -0.02:
            bearish_signals += 1
        
        if technical_features.price_vs_sma50 > 0.03:
            bullish_signals += 1
        elif technical_features.price_vs_sma50 < -0.03:
            bearish_signals += 1
        
        if technical_features.macd_histogram_normalized > 0:
            bullish_signals += 1
        elif technical_features.macd_histogram_normalized < 0:
            bearish_signals += 1
        
        if bullish_signals >= 2:
            return "bullish"
        elif bearish_signals >= 2:
            return "bearish"
        else:
            return "neutral"
    
    def _describe_technical_momentum(self, technical_features) -> str:
        """Describe technical momentum conditions."""
        if not technical_features:
            return "unknown"
        
        rsi = technical_features.rsi
        stoch = technical_features.stochastic_k
        
        if rsi < 0.3 or stoch < 0.2:
            return "oversold"
        elif rsi > 0.7 or stoch > 0.8:
            return "overbought"
        else:
            return "neutral"
    
    def _describe_sentiment(self, score: float) -> str:
        """Convert sentiment score to description."""
        if score > 0.5:
            return "very positive"
        elif score > 0.2:
            return "positive"
        elif score > -0.2:
            return "neutral"
        elif score > -0.5:
            return "negative"
        else:
            return "very negative"
    
    def _describe_momentum(self, momentum: float) -> str:
        """Convert momentum to description."""
        if momentum > 0.1:
            return "improving"
        elif momentum < -0.1:
            return "declining"
        else:
            return "stable"
    
    def _categorize_volume(self, ratio: float) -> str:
        """Categorize news volume."""
        if ratio > 2.0:
            return "high"
        elif ratio > 0.5:
            return "normal"
        else:
            return "low"


# Global engine instance
_engine: Optional[RecommendationEngine] = None


async def get_engine() -> RecommendationEngine:
    """Get or initialize the recommendation engine."""
    global _engine
    
    if _engine is None:
        _engine = RecommendationEngine()
        await _engine.initialize()
    
    return _engine


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    
    Returns service status and feature availability.
    """
    news_provider = await get_news_provider()
    technical_provider = await get_technical_provider()
    
    return HealthResponse(
        status="healthy",
        service="recommendation-engine",
        version="2.0.0",
        news_features_available=news_provider is not None,
        technical_features_available=technical_provider is not None,
    )


@app.post("/recommendations", response_model=RecommendationResponse)
async def generate_recommendations(request: RecommendationRequest):
    """
    Generate trading recommendations for the specified symbols.
    
    This endpoint analyzes news sentiment and other signals to produce
    BUY/SELL/HOLD recommendations with confidence scores and explanations.
    
    Args:
        request: RecommendationRequest with user_id and symbols
        
    Returns:
        RecommendationResponse with list of recommendations
    """
    logger.info(f"Generating recommendations for user {request.user_id}, symbols: {request.symbols}")
    
    engine = await get_engine()
    
    recommendations = []
    for symbol in request.symbols:
        try:
            rec = await engine.generate_recommendation(
                symbol=symbol.upper(),
                include_features=request.include_features,
            )
            recommendations.append(rec)
        except Exception as e:
            logger.error(f"Failed to generate recommendation for {symbol}: {e}")
            # Return neutral recommendation on error
            recommendations.append(Recommendation(
                symbol=symbol.upper(),
                action="HOLD",
                confidence=0.0,
                explanation={"summary": f"Unable to analyze {symbol}", "error": str(e)},
            ))
    
    return RecommendationResponse(
        user_id=request.user_id,
        recommendations=recommendations,
    )


@app.get("/recommendations/{symbol}", response_model=Recommendation)
async def get_recommendation(
    symbol: str,
    include_features: bool = Query(False, description="Include feature details"),
):
    """
    Get the latest recommendation for a specific symbol.
    
    This is a convenience endpoint for fetching a single recommendation.
    """
    engine = await get_engine()
    
    try:
        return await engine.generate_recommendation(
            symbol=symbol.upper(),
            include_features=include_features,
        )
    except Exception as e:
        logger.error(f"Failed to get recommendation for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommendations/history/{symbol}", response_model=RecommendationHistoryResponse)
async def get_recommendation_history(
    symbol: str,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of recommendations to return"),
):
    """
    Get the last N recommendations for a specific symbol from the database.
    
    Returns up to 10 most recent recommendations stored in the database,
    including component scores and explanations.
    
    Args:
        symbol: Stock ticker symbol
        limit: Maximum number of recommendations (default: 10, max: 50)
        
    Returns:
        RecommendationHistoryResponse with list of historical recommendations
    """
    db_pool = await get_db_pool()
    
    if not db_pool:
        raise HTTPException(
            status_code=503,
            detail="Database not available"
        )
    
    symbol = symbol.upper()
    
    try:
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
            rows = await conn.fetch(query, symbol, limit)
        
        recommendations = []
        for row in rows:
            recommendations.append(RecommendationHistoryItem(
                id=str(row['id']),
                symbol=row['symbol'],
                action=row['action'],
                score=float(row['score']) if row['score'] is not None else None,
                normalized_score=float(row['normalized_score']) if row['normalized_score'] is not None else None,
                confidence=float(row['confidence']) if row['confidence'] is not None else None,
                price_at_recommendation=float(row['price_at_recommendation']) if row['price_at_recommendation'] is not None else None,
                news_sentiment_score=float(row['news_sentiment_score']) if row['news_sentiment_score'] is not None else None,
                news_momentum_score=float(row['news_momentum_score']) if row['news_momentum_score'] is not None else None,
                technical_trend_score=float(row['technical_trend_score']) if row['technical_trend_score'] is not None else None,
                technical_momentum_score=float(row['technical_momentum_score']) if row['technical_momentum_score'] is not None else None,
                rsi=float(row['rsi']) if row['rsi'] is not None else None,
                macd_histogram=float(row['macd_histogram']) if row['macd_histogram'] is not None else None,
                price_vs_sma20=float(row['price_vs_sma20']) if row['price_vs_sma20'] is not None else None,
                news_sentiment_1d=float(row['news_sentiment_1d']) if row['news_sentiment_1d'] is not None else None,
                article_count_24h=row['article_count_24h'],
                explanation=row['explanation'],
                data_sources_used=row['data_sources_used'],
                generated_at=row['generated_at'],
                created_at=row['created_at'],
            ))
        
        return RecommendationHistoryResponse(
            symbol=symbol,
            recommendations=recommendations,
            count=len(recommendations),
        )
        
    except Exception as e:
        logger.error(f"Failed to get recommendation history for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/features/{symbol}")
async def get_features(symbol: str):
    """
    Get all features (news + technical) for a symbol.
    
    Returns the complete feature set used in recommendation generation.
    Useful for debugging and understanding recommendations.
    """
    symbol = symbol.upper()
    result = {"symbol": symbol}
    
    # Get news features
    news_provider = await get_news_provider()
    if news_provider:
        try:
            news_features = await news_provider.get_features_single(symbol)
            result["news"] = {
                "available": True,
                "features": news_features.to_dict(),
                "feature_vector": news_features.to_feature_vector(),
            }
        except Exception as e:
            logger.error(f"Failed to get news features for {symbol}: {e}")
            result["news"] = {"available": False, "error": str(e)}
    else:
        result["news"] = {"available": False, "error": "News provider not initialized"}
    
    # Get technical features
    technical_provider = await get_technical_provider()
    if technical_provider:
        try:
            tech_features = await technical_provider.get_features(symbol)
            result["technical"] = {
                "available": True,
                "features": tech_features.to_dict(),
                "feature_vector": tech_features.to_feature_vector(),
                "signals": {
                    "trend": tech_features.get_trend_signal(),
                    "momentum": tech_features.get_momentum_signal(),
                }
            }
        except Exception as e:
            logger.error(f"Failed to get technical features for {symbol}: {e}")
            result["technical"] = {"available": False, "error": str(e)}
    else:
        result["technical"] = {"available": False, "error": "Technical provider not initialized"}
    
    return result


@app.get("/technical/{symbol}")
async def get_technical_analysis(symbol: str):
    """
    Get detailed technical analysis for a symbol.
    
    Returns technical indicators and trading signals.
    """
    technical_provider = await get_technical_provider()
    
    if not technical_provider:
        raise HTTPException(
            status_code=503,
            detail="Technical analysis not available"
        )
    
    try:
        features = await technical_provider.get_features(symbol.upper())
        
        return {
            "symbol": symbol.upper(),
            "timestamp": features.timestamp.isoformat(),
            "price": {
                "current": features.current_price,
                "change_1d": f"{features.price_change_1d * 100:.2f}%",
                "change_5d": f"{features.price_change_5d * 100:.2f}%",
                "change_20d": f"{features.price_change_20d * 100:.2f}%",
            },
            "trend": {
                "signal": "bullish" if features.get_trend_signal() > 0 else (
                    "bearish" if features.get_trend_signal() < 0 else "neutral"
                ),
                "price_vs_sma20": f"{features.price_vs_sma20 * 100:.2f}%",
                "price_vs_sma50": f"{features.price_vs_sma50 * 100:.2f}%",
                "price_vs_sma200": f"{features.price_vs_sma200 * 100:.2f}%",
                "macd_histogram": features.macd_histogram_normalized,
            },
            "momentum": {
                "signal": "oversold" if features.get_momentum_signal() > 0 else (
                    "overbought" if features.get_momentum_signal() < 0 else "neutral"
                ),
                "rsi": f"{features.rsi * 100:.1f}",
                "stochastic_k": f"{features.stochastic_k * 100:.1f}",
                "stochastic_d": f"{features.stochastic_d * 100:.1f}",
                "roc": f"{features.roc * 100:.2f}%",
            },
            "volatility": {
                "bollinger_width": f"{features.bb_width * 100:.2f}%",
                "bollinger_position": f"{features.bb_position * 100:.1f}%",
                "atr_percent": f"{features.atr_percent * 100:.2f}%",
                "historical_volatility": f"{features.volatility * 100:.1f}%",
            },
            "volume": {
                "ratio_vs_avg": f"{features.volume_ratio:.2f}x",
                "obv_trend": "rising" if features.obv_trend > 0.1 else (
                    "falling" if features.obv_trend < -0.1 else "flat"
                ),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get technical analysis for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Application Lifecycle
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    logger.info("Starting Recommendation Engine...")
    
    # Pre-initialize engine
    await get_engine()
    
    logger.info("Recommendation Engine started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down Recommendation Engine...")
    
    if _news_provider:
        await _news_provider.close()
    
    if _technical_provider:
        await _technical_provider.close()
    
    logger.info("Recommendation Engine shutdown complete")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    """
    Run the recommendation engine service.
    
    Configuration via environment variables:
    - HOST: Bind address (default: 0.0.0.0)
    - PORT: Listen port (default: 8000)
    - CLICKHOUSE_HOST: ClickHouse server (default: localhost)
    - CLICKHOUSE_PORT: ClickHouse port (default: 8123)
    - REDIS_URL: Redis connection URL (default: redis://localhost:6379)
    
    Production deployment:
        uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
    """
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port)

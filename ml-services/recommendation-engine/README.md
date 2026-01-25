# How the Recommendation Service Works

## Overview

The recommendation service analyzes stocks by combining **news sentiment**, **technical indicators**, and **market regime classification** to generate BUY/HOLD/SELL recommendations with confidence scores.

**Key Innovation: Regime-Adaptive Signal Weighting**

The engine now classifies market conditions and adapts its behavior accordingly. The same signal (e.g., RSI oversold) can result in different actions depending on the market regime:

| Signal | Regime | Result |
|--------|--------|--------|
| RSI oversold + Positive sentiment | Low vol, mean-reverting | **BUY** (high confidence) |
| RSI oversold + Positive sentiment | High vol, news shock | **HOLD** (low confidence) |
| RSI oversold + Positive sentiment | Choppy, social-driven | **SKIP** (very low confidence) |

---

## Decision Flow

```
Raw Data → Feature Engineering → Regime Classification → Signal Weighting (by regime)
→ Expected Value Estimation → Confidence Scoring → Ranked Recommendations
```

---

## Step-by-Step Workflow

### 1. **Data Collection**

The service collects data from two main categories:

#### News Data (from ClickHouse)
- News articles are fetched from multiple connectors:
  - **Polygon** - Financial news
  - **Finnhub** - Market news
  - **NewsAPI** - General news
  - **Benzinga** - Trading news
  - **FMP** - Market articles
- Articles are stored in ClickHouse with sentiment scores
- The service queries articles from the last 14 days for the requested symbol

#### Technical Data (from Polygon API - api.massive.com)
- **Price data**: Open, High, Low, Close, Volume
- **Historical prices**: Last 60 days of daily data
- Used to calculate technical indicators

---

### 2. **News Feature Extraction**

The service calculates these news-based features:

| Feature | Description | How It's Calculated |
|---------|-------------|---------------------|
| `news_sentiment_score` | Overall sentiment | Weighted average of article sentiments (recent articles weighted more) |
| `news_sentiment_1d` | 24-hour sentiment | Average sentiment of articles from last 24 hours |
| `news_momentum_score` | Sentiment trend | Compares recent sentiment (3 days) vs older sentiment (7 days) |
| `article_count_24h` | News volume | Count of articles in last 24 hours |

**Sentiment Values:**
- Bullish: +0.5 to +1.0
- Neutral: -0.1 to +0.1
- Bearish: -0.5 to -1.0

---

### 3. **Technical Feature Extraction**

The service calculates these technical indicators from price data:

| Indicator | Description | Calculation |
|-----------|-------------|-------------|
| **RSI** | Relative Strength Index | Measures overbought (>70) or oversold (<30) conditions |
| **MACD** | Moving Average Convergence Divergence | Difference between 12-day and 26-day EMAs |
| **SMA20** | 20-day Simple Moving Average | Average price over 20 days |
| **Price vs SMA20** | Price position | How far current price is from 20-day average |
| **Volatility** | Price swings | Standard deviation of returns |
| **1D/5D Change** | Recent momentum | Price change over 1 and 5 days |

From these, it derives:

| Score | Description | How It's Calculated |
|-------|-------------|---------------------|
| `technical_trend_score` | Price trend direction | Based on price vs moving averages and recent changes |
| `technical_momentum_score` | Momentum strength | Based on RSI and MACD signals |

---

### 4. **Sentiment Analysis with LLM**

When news articles are ingested (via the News Ingestion Service), each article's sentiment is analyzed:

```
Article Title + Content
        ↓
   LLM Analysis (Anthropic/Groq with OpenAI fallback)
        ↓
   Returns: {score: 0.7, label: "bullish", confidence: 0.85}
```

**LLM Prompt** (simplified):
```
Analyze the sentiment of this financial news article.
Return a score from -1 (very bearish) to +1 (very bullish),
a label (very_bearish, bearish, neutral, bullish, very_bullish),
and your confidence level.
```

---

### 5. **Regime Classification** (NEW)

Before combining signals, the engine classifies the current market regime across 4 dimensions:

#### Regime Dimensions

| Dimension | States | Detection Method |
|-----------|--------|------------------|
| **Volatility** | Low / Normal / High / Extreme | Volatility z-score, Bollinger Band width |
| **Trend** | Strong Uptrend / Uptrend / Mean-Reverting / Choppy / Downtrend / Strong Downtrend | Price vs SMAs, MACD, trend strength |
| **Liquidity** | High / Normal / Thin / Illiquid | Volume ratio vs average |
| **Information** | Quiet / Normal / News-Driven / Social-Driven / Earnings | News velocity, social mentions |

#### How Regime Affects Recommendations

The regime does NOT decide BUY/SELL directly. It controls:

| Aspect | Effect |
|--------|--------|
| **Signal weights** | Tech vs news vs social emphasis |
| **Confidence scaling** | Penalize bad regime fits |
| **Trade frequency** | Fewer trades in chaotic markets |
| **Action thresholds** | Stricter in risky regimes |
| **Explanation tone** | "High-risk setup" warnings |

#### Regime-Specific Threshold Adjustments

```python
# Examples of threshold adjustments by regime:
"extreme_volatility": {"buy_adjust": +0.15, "sell_adjust": -0.10}  # Much stricter
"strong_uptrend":     {"buy_adjust": -0.10, "sell_adjust": +0.10}  # Easier to buy
"choppy":             {"buy_adjust": +0.15, "sell_adjust": -0.05}  # Much stricter for buy
"illiquid":           {"buy_adjust": +0.15, "sell_adjust": -0.10}  # Much stricter
```

---

### 6. **Score Combination with Regime Weights**

The final recommendation score combines news and technical signals using **regime-adaptive weights**:

```
                    News Signals                    Technical Signals
                         ↓                                ↓
              ┌─────────────────────┐         ┌─────────────────────┐
              │ news_sentiment: 0.4 │         │ trend_score: -0.3   │
              │ news_momentum: 0.1  │         │ momentum_score: 0.2 │
              └─────────────────────┘         └─────────────────────┘
                         ↓                                ↓
                  Regime-Adjusted              Regime-Adjusted
                    Weights                      Weights
                         ↓                                ↓
                         └────────────┬───────────────────┘
                                      ↓
                              Combined Score
                              (e.g., 0.05)
```

**Default Weights (adjusted by regime):**
- News Sentiment: 30%
- News Momentum: 20%
- Technical Trend: 25%
- Technical Momentum: 25%

**Regime Weight Adjustments:**
- **Trending markets**: Technical trend signals weighted +30% higher
- **Choppy markets**: All technical signals weighted lower, confidence reduced
- **News-driven**: News sentiment weighted +50% higher
- **High volatility**: Momentum signals reduced, confidence multiplier 0.7x
- **Quiet markets**: Technical signals more reliable, weighted higher

**Formula:**
```python
# Get regime-adjusted weights (normalized to sum to 1.0)
weights = regime_classifier.get_signal_weights(regime_state)

combined_score = (
    news_sentiment_score * weights.news_sentiment +
    news_momentum_score * weights.news_momentum +
    technical_trend_score * weights.technical_trend +
    technical_momentum_score * weights.technical_momentum
)
```

---

### 7. **Normalized Score & Action**

The combined score (-1 to +1) is normalized to 0-100%:

```python
normalized_score = (combined_score + 1) / 2  # Maps -1→0, 0→0.5, +1→1
```

**Default Action Thresholds:**
| Normalized Score | Action |
|-----------------|--------|
| > 80% | **BUY** |
| 50% - 80% | **HOLD** |
| < 50% | **SELL** |

**Regime-Adjusted Thresholds:**

The actual thresholds are adjusted based on regime. In risky regimes, stricter thresholds are used:

| Regime | Buy Threshold (normalized) | Effect |
|--------|---------------------------|--------|
| Default | 80% | Normal |
| Extreme Volatility | ~88% | Much stricter |
| Strong Uptrend | ~75% | Easier to buy |
| Choppy Market | ~88% | Much stricter |
| Illiquid | ~88% | Much stricter |

---

### 8. **Confidence Calculation**

Confidence reflects how reliable the recommendation is:

```python
confidence = base_confidence

# Boost if news and technical signals agree
if news_score > 0 and technical_score > 0:  # Both bullish
    confidence += 0.15
elif news_score < 0 and technical_score < 0:  # Both bearish
    confidence += 0.15

# Reduce if signals conflict
if (news_score > 0.2 and technical_score < -0.2) or vice versa:
    confidence -= 0.10

# Boost for high news volume
if article_count_24h > 10:
    confidence += 0.05

# Apply REGIME confidence multiplier (NEW)
confidence = confidence * regime_weights.confidence_multiplier
# Multipliers: 1.1x for low vol, 0.7x for high vol, 0.4x for extreme vol

# Cap between 0.0 and 1.0
confidence = max(0.0, min(1.0, confidence))
```

**Regime Confidence Multipliers:**
| Regime | Multiplier | Effect |
|--------|------------|--------|
| Low Volatility | 1.1x | Slight boost |
| Normal | 1.0x | No change |
| High Volatility | 0.7x | Reduced |
| Extreme Volatility | 0.4x | Significantly reduced |
| Choppy Market | 0.8x | Reduced |
| Social-Driven | 0.7x | Reduced (noise) |

---

### 9. **Explanation Generation**

The service generates a human-readable explanation:

```python
explanation = {
    "summary": "Moderate bullish sentiment with mixed technical signals...",
    "factors": [
        "News sentiment is positive (0.41)",
        "RSI indicates oversold conditions (9.4)",
        "Price is below 20-day moving average"
    ],
    "news": {
        "articles_24h": 67,
        "sentiment_1d": 0.45,
        "sentiment_trend": "stable"
    },
    "technical": {
        "price": 247.65,
        "change_1d": "+0.39%",
        "rsi": 9.4,
        "trend": "bearish"
    },
    "recent_articles": [
        {"title": "Apple announces...", "source": "Finnhub", "sentiment": "positive"}
    ]
}
```

---

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDATION SERVICE                           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  INPUT: Stock Symbol (e.g., "AAPL")                                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
          ┌───────────────────────┴───────────────────────┐
          ▼                                               ▼
┌─────────────────────┐                     ┌─────────────────────┐
│   NEWS FEATURES     │                     │ TECHNICAL FEATURES  │
│                     │                     │                     │
│ Source: ClickHouse  │                     │ Source: Polygon API │
│                     │                     │                     │
│ • Sentiment (LLM)   │                     │ • RSI               │
│ • Momentum          │                     │ • MACD              │
│ • Article Count     │                     │ • SMA20             │
│ • 14-day history    │                     │ • Volatility        │
└─────────────────────┘                     └─────────────────────┘
          │                                               │
          └───────────────────────┬───────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SCORE COMBINATION                                │
│                                                                     │
│   combined = 0.5 * news_signals + 0.5 * technical_signals          │
│   normalized = (combined + 1) / 2                                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ACTION DETERMINATION                             │
│                                                                     │
│   > 80%  →  BUY    │   50-80%  →  HOLD    │   < 50%  →  SELL       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    OUTPUT: Recommendation                           │
│                                                                     │
│  {                                                                  │
│    symbol: "AAPL",                                                  │
│    action: "HOLD",                                                  │
│    score: 0.053,                                                    │
│    normalized_score: 0.527,                                         │
│    confidence: 0.54,                                                │
│    price: 247.65,                                                   │
│    news_sentiment_score: 0.41,                                      │
│    technical_trend_score: -0.45,                                    │
│    explanation: {...}                                               │
│  }                                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Files

| File | Purpose |
|------|---------|
| `ml-services/recommendation-engine/src/main.py` | Main recommendation engine & API |
| `ml-services/recommendation-engine/src/regime_classifier.py` | **NEW** - Regime classification model |
| `ml-services/recommendation-engine/src/news_features.py` | News feature extraction from ClickHouse |
| `ml-services/recommendation-engine/src/technical_features.py` | Technical indicator calculations |
| `ml-services/recommendation-engine/tests/test_regime_classifier.py` | **NEW** - Unit tests for regime classifier |
| `ml-services/sentiment-analysis/src/analyzer.py` | LLM-based sentiment analysis |
| `ml-services/news_ingestion_service.py` | Fetches news & runs sentiment analysis |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check for load balancers |
| `/recommendations` | POST | Generate recommendations for symbols |
| `/recommendations/{symbol}` | GET | Get latest recommendation for symbol |
| `/features/{symbol}` | GET | Get current features for symbol (debugging) |
| `/regime/{symbol}` | GET | **NEW** - Get current regime classification |

### Regime Endpoint Example

```bash
curl http://localhost:8000/regime/AAPL
```

**Response:**
```json
{
  "symbol": "AAPL",
  "regime": {
    "regime_label": "Volatile / Bearish",
    "risk_level": "high",
    "volatility": "high",
    "trend": "downtrend",
    "liquidity": "normal",
    "information": "news_driven",
    "risk_score": 0.65,
    "regime_confidence": 0.72,
    "warnings": ["High volatility - consider smaller position sizes"],
    "explanations": [
      "Market volatility is elevated. Signals may be less reliable.",
      "Moderate downtrend detected.",
      "High news activity driving price action."
    ]
  },
  "signal_weights": {
    "news_sentiment": 0.35,
    "news_momentum": 0.22,
    "technical_trend": 0.25,
    "technical_momentum": 0.18,
    "confidence_multiplier": 0.7,
    "trade_frequency_modifier": 1.0
  },
  "timestamp": "2026-01-23T23:30:00Z"
}
```

---

## Usage

### Running the Recommendation Engine

```bash
# Generate recommendations via the API
curl http://localhost:8000/recommendations?symbols=AAPL,MSFT

# Or use the StartUpApplication script
python scripts/StartUpApplication.py --symbols AAPL,MSFT,GOOGL

# Check regime for a symbol
curl http://localhost:8000/regime/AAPL
```

### Running the News Ingestion Service

```bash
# Run once to fetch and analyze news
python ml-services/news_ingestion_service.py --once --symbols AAPL

# Run continuously (every 30 minutes)
python ml-services/news_ingestion_service.py --interval 30
```

---

## Regime Classification Details

### RegimeClassifier Class

The `RegimeClassifier` class in `regime_classifier.py` provides:

1. **`classify(symbol, technical_features, news_features)`** - Classifies current regime
2. **`get_signal_weights(regime_state)`** - Gets optimized weights for regime
3. **`get_regime_explanation(regime_state)`** - Gets human-readable explanation

### Hysteresis

The classifier includes **hysteresis** to prevent regime flip-flopping:
- A regime change must persist for 3 consecutive classifications
- This prevents noisy signals from causing rapid regime changes

### Risk Score

Each regime state includes a `risk_score` (0-1) calculated from:
- Volatility risk (35% weight)
- Trend risk (25% weight) - choppy = high risk
- Liquidity risk (20% weight)
- Information risk (20% weight)

A `risk_score > 0.7` triggers `is_high_risk()` warnings.

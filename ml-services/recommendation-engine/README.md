# Recommendation Engine

## Overview

The recommendation engine generates AI-powered trading recommendations for stocks in a user's watchlist. It runs automatically every 2 hours and combines news sentiment analysis with technical indicators to produce actionable BUY, SELL, or HOLD recommendations.

## How the Raw Recommendation Score is Calculated

### Architecture Overview

The recommendation system uses a **weighted scoring model** that combines **News Sentiment Analysis** and **Technical Indicators**. The current implementation uses a **rule-based scoring system** with the LLM used specifically for sentiment analysis of news articles.

---

## 1. Input Signals (4 Component Scores)

The system calculates 4 component scores, each ranging from **-1 to +1**:

| Component | Weight | Source | What it Measures |
|-----------|--------|--------|------------------|
| **News Sentiment** | 30% | NewsFeatureProvider (ClickHouse) | Recent news sentiment direction |
| **News Momentum** | 20% | NewsFeatureProvider | Is sentiment improving or declining |
| **Technical Trend** | 25% | TechnicalFeatureProvider | Price trend using MAs and MACD |
| **Technical Momentum** | 25% | TechnicalFeatureProvider | RSI, Stochastic, mean-reversion signals |

---

## 2. News Sentiment Score Calculation

```python
def _calculate_news_sentiment_score(news_features) -> float:
    # Uses 1-day sentiment as primary signal
    sentiment = news_features.sentiment_1d  # Range: -1 to +1
    
    # Adjust by confidence (weight higher confidence sentiment more)
    confidence_factor = 0.5 + (news_features.avg_confidence_1d * 0.5)
    
    return sentiment * confidence_factor  # Final range: -1 to +1
```

**Data Sources:**
- News articles from ClickHouse (ingested from NewsAPI, Benzinga, Alpha Vantage, RSS feeds)
- Each article has a sentiment score from the **LLM-based sentiment analyzer**

---

## 3. News Momentum Score Calculation

```python
def _calculate_news_momentum_score(news_features) -> float:
    # Momentum = change in sentiment (1d - 3d)
    momentum = news_features.sentiment_momentum
    
    # Scale momentum (0.1 change is significant)
    scaled_momentum = max(-1.0, min(1.0, momentum * 5))
    
    return scaled_momentum
```

**What it captures:** Is sentiment getting better or worse over time.

---

## 4. Technical Trend Score Calculation

```python
def _calculate_technical_trend_score(technical_features) -> float:
    score = 0.0
    signals = 0
    
    # Price vs SMA20 (short-term trend)
    if price_vs_sma20 > 0.02:   score += 0.5  # Above 20-day MA = bullish
    elif price_vs_sma20 < -0.02: score -= 0.5  # Below = bearish
    
    # Price vs SMA50 (medium-term trend)
    if price_vs_sma50 > 0.03:   score += 0.5
    elif price_vs_sma50 < -0.03: score -= 0.5
    
    # MACD histogram (momentum of trend)
    if macd_histogram_normalized > 0.001:  score += 0.5
    elif macd_histogram_normalized < -0.001: score -= 0.5
    
    # SMA crossover (golden/death cross)
    if sma20_vs_sma50 > 0.01:  score += 0.3
    elif sma20_vs_sma50 < -0.01: score -= 0.3
    
    return normalize(score / signals)  # Range: -1 to +1
```

---

## 5. Technical Momentum Score Calculation

```python
def _calculate_technical_momentum_score(technical_features) -> float:
    score = 0.0
    
    # RSI - contrarian signal
    if rsi < 0.30:  score += 0.6   # Oversold = BUY signal
    if rsi > 0.70:  score -= 0.6   # Overbought = SELL signal
    
    # Stochastic - similar contrarian logic
    if stochastic_k < 0.20: score += 0.4
    if stochastic_k > 0.80: score -= 0.4
    
    # ROC (Rate of Change)
    if roc > 0.05:  score += 0.4   # Strong upward momentum
    if roc < -0.05: score -= 0.4   # Strong downward momentum
    
    # Bollinger Band position
    if bb_position < 0.1: score += 0.3  # Near lower band = potential bounce
    if bb_position > 0.9: score -= 0.3  # Near upper band = potential pullback
    
    return normalize(score / signals)  # Range: -1 to +1
```

---

## 6. Combined Score Formula

```python
combined_score = (
    news_sentiment_score * 0.30 +    # 30% weight
    news_momentum_score * 0.20 +     # 20% weight
    technical_trend_score * 0.25 +   # 25% weight
    technical_momentum_score * 0.25  # 25% weight
)
# Result: -1 to +1
```

---

## 7. Action Determination

```python
BUY_THRESHOLD = 0.6   # Raw score > 0.6 → BUY (normalized > 80%)
SELL_THRESHOLD = 0.0  # Raw score < 0.0 → SELL (normalized < 50%)

if combined_score > 0.6:
    action = "BUY"
elif combined_score < 0.0:
    action = "SELL"
else:
    action = "HOLD"
```

---

## 8. Confidence Score Calculation

```python
confidence = (
    base_confidence (0.15) +
    strength_confidence (0-0.4 based on |combined_score|) +
    agreement_factor (+0.15 if news & technical agree, -0.10 if disagree) +
    quality_score (0-0.3 based on data availability)
)
```

---

## 9. Where LLM is Used

The **LLM (OpenAI/Anthropic/Groq)** is used in the **Sentiment Analysis Service** (`ml-services/sentiment-analysis/src/analyzer.py`) to:

1. **Analyze news article text** and extract sentiment (-1 to +1)
2. **Extract key entities** (companies, people, topics)
3. **Determine relevance** to specific stocks

The LLM is **NOT used** in:
- The final recommendation calculation (rule-based)
- Technical indicator computation (pure math)

---

## Visual Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION                                │
├─────────────────────────────────────────────────────────────────┤
│  News Articles ─────────► LLM Sentiment ─────► ClickHouse       │
│  (NewsAPI, Benzinga,      (OpenAI/Claude)      (sentiment_1d,   │
│   Alpha Vantage, RSS)                          momentum, etc.)  │
│                                                                  │
│  Price Data ─────────────────────────────────► Yahoo/Polygon    │
│  (Real-time quotes,                            (OHLCV data)     │
│   historical prices)                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FEATURE ENGINEERING                             │
├─────────────────────────────────────────────────────────────────┤
│  NewsFeatureProvider:                                            │
│    - sentiment_1d, sentiment_3d, sentiment_7d                   │
│    - sentiment_momentum (1d - 3d)                               │
│    - article_count, avg_confidence                              │
│                                                                  │
│  TechnicalFeatureProvider:                                       │
│    - SMA (20, 50, 200)                                          │
│    - RSI, MACD, Stochastic                                      │
│    - Bollinger Bands, ATR, ROC                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              RECOMMENDATION ENGINE (Rule-Based)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  combined_score = news_sentiment * 0.30                         │
│                 + news_momentum * 0.20                          │
│                 + technical_trend * 0.25                        │
│                 + technical_momentum * 0.25                     │
│                                                                  │
│  if score > 0.6 → BUY                                           │
│  if score < 0.0 → SELL                                          │
│  else           → HOLD                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OUTPUT                                      │
├─────────────────────────────────────────────────────────────────┤
│  {                                                               │
│    "action": "BUY",                                             │
│    "score": 0.72,                                               │
│    "confidence": 0.85,                                          │
│    "explanation": {...}                                         │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Understanding Raw Score vs Normalized Score vs Confidence

These three metrics serve different purposes:

| Metric | Range | What it Represents |
|--------|-------|-------------------|
| **Raw Score** | -1 to +1 | The weighted sum of all component signals |
| **Normalized Score** | 0 to 1 | Raw score converted to a 0-100% scale for UI display |
| **Confidence** | 0 to 1 | How reliable/trustworthy the recommendation is |

### 1. Raw Score (-1 to +1)

The raw score is the **actual recommendation signal** - it tells you the direction and strength of the recommendation.

```python
raw_score = (news_sentiment * 0.30) + (news_momentum * 0.20) 
          + (technical_trend * 0.25) + (technical_momentum * 0.25)
```

**Interpretation:**
- **+1.0** = Maximum bullish signal (strong BUY)
- **0.0** = Neutral (HOLD)
- **-1.0** = Maximum bearish signal (strong SELL)

**Example:** A raw score of `0.72` means moderately strong bullish signals.

### 2. Normalized Score (0 to 1)

The normalized score is simply the **raw score rescaled for display purposes**:

```python
normalized_score = (raw_score + 1) / 2
```

| Raw Score | Normalized Score | Display |
|-----------|-----------------|---------|
| -1.0 | 0.0 | 0% |
| 0.0 | 0.5 | 50% |
| +1.0 | 1.0 | 100% |
| +0.72 | 0.86 | 86% |

**Why normalize?** It's easier for users to understand "86% bullish" than "+0.72 on a -1 to +1 scale."

### 3. Confidence (0 to 1)

Confidence is **completely different** - it measures **how much you should trust the score**, not the score itself.

```python
confidence = (
    base_confidence (0.15) +
    strength_factor (0-0.4)   # Higher |score| = more confident
    agreement_factor (±0.15)  # News & technical agree = more confident
    data_quality (0-0.3)      # More data sources = more confident
)
```

**High confidence scenarios:**
- Strong signal (score far from 0)
- News and technical indicators agree
- Multiple data sources available
- Recent, high-quality data

**Low confidence scenarios:**
- Weak signal (score near 0)
- News says BUY but technicals say SELL
- Limited data sources
- Stale or missing data

### Example Comparison

| Scenario | Raw | Normalized | Confidence | Interpretation |
|----------|-----|------------|------------|----------------|
| Strong BUY, all signals agree | +0.85 | 92.5% | 0.92 | "Highly confident strong buy" |
| Weak BUY, mixed signals | +0.25 | 62.5% | 0.45 | "Uncertain, leaning buy" |
| Neutral, no data | 0.0 | 50% | 0.30 | "Don't know, low confidence" |
| Strong SELL, conflicting | -0.70 | 15% | 0.55 | "Sell signal but conflicting data" |

### How to Use Them Together

```
If normalized_score > 80% AND confidence > 0.7:
    → Strong conviction BUY
    
If normalized_score > 80% AND confidence < 0.5:
    → BUY signal but be cautious, data is uncertain
    
If normalized_score ~50% AND confidence > 0.8:
    → Confidently neutral - no clear direction
```

---

## Recommendation Object Structure

Each recommendation stored in the database contains:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `id` | UUID | Unique identifier | `93a10f32-16f0-48e1-b37b-3f55c3dfa28f` |
| `symbol` | VARCHAR | Stock ticker symbol | `AAPL` |
| `action` | VARCHAR | Trading action (BUY, SELL, HOLD) | `BUY` |
| `score` | NUMERIC | Raw recommendation score | `0.7200` |
| `normalized_score` | NUMERIC | Normalized score (0-1) | `0.7200` |
| `confidence` | NUMERIC | Confidence level (0-1) | `0.850` |
| `price_at_recommendation` | NUMERIC | Stock price when generated | `255.53` |
| **News Scores** | | | |
| `news_sentiment_score` | NUMERIC | Overall news sentiment (-1 to 1) | `0.6500` |
| `news_momentum_score` | NUMERIC | News momentum indicator | `0.7000` |
| `news_sentiment_1d` | NUMERIC | 1-day news sentiment | `0.6200` |
| `article_count_24h` | INTEGER | Articles in last 24 hours | `15` |
| **Technical Scores** | | | |
| `technical_trend_score` | NUMERIC | Technical trend indicator | `0.7500` |
| `technical_momentum_score` | NUMERIC | Technical momentum | `0.6800` |
| `rsi` | NUMERIC | Relative Strength Index | `0.5800` |
| `macd_histogram` | NUMERIC | MACD histogram value | `0.00125` |
| `price_vs_sma20` | NUMERIC | Price relative to 20-day SMA | `1.0250` |
| **Metadata** | | | |
| `explanation` | JSONB | AI-generated explanation | `{"summary": "...", "factors": [...]}` |
| `data_sources_used` | TEXT[] | Data sources used | `{polygon, newsapi, finnhub}` |
| `generated_at` | TIMESTAMP | When recommendation was generated | `2026-01-21 00:02:33` |
| `created_at` | TIMESTAMP | Database insert time | `2026-01-20 06:52:03` |

---

## Running the Recommendation Engine

### Scheduled Mode (Default)
```bash
python recommendation_flow.py
```
Runs every 2 hours automatically.

### On-Demand Mode
```bash
python recommendation_flow.py --once
```
Runs once and exits.

### Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `VAULT_ADDR` - Vault server address for API keys
- `VAULT_TOKEN` - Vault authentication token
- `WATCHLIST_SYMBOLS` - Fallback symbols (default reads from database)

---

## Future Enhancements

1. **ML Model Integration** - Replace rule-based scoring with trained ML models
2. **Backtesting Framework** - Validate recommendation accuracy against historical data
3. **Risk-Adjusted Scoring** - Factor in volatility and portfolio exposure
4. **Real-time Updates** - Stream-based recommendations on significant events

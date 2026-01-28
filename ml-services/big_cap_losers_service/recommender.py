"""Recommendation integration for Big Cap Losers.

Calls the recommendation-engine service and maps its response into fields stored
on big_cap_losers rows.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


def _safe_get(d: Optional[Dict[str, Any]], path: str):
    cur = d
    for part in path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


async def fetch_recommendation(session: aiohttp.ClientSession, symbol: str) -> Dict[str, Any]:
    """Fetch recommendation from recommendation-engine for a symbol.

    Compatibility notes:
    - Newer versions expose GET /recommendations/{symbol}?include_features=true
    - Some deployments may only expose POST /generate/single

    We try the GET endpoint first, and fall back to the POST endpoint on 404.
    """
    symbol = symbol.upper().strip()

    # Preferred: single-symbol convenience endpoint
    url = f"http://recommendation-engine:8000/recommendations/{symbol}?include_features=true"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
        if resp.status == 200:
            return await resp.json()
        text = await resp.text()
        # Fall back if this service doesn't implement the GET route
        if resp.status != 404:
            raise RuntimeError(f"recommendation-engine HTTP {resp.status}: {text[:200]}")

    # Fallback: on-demand single recommendation endpoint
    url2 = "http://recommendation-engine:8000/generate/single"
    payload = {"symbol": symbol, "save_to_db": False}
    async with session.post(url2, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"recommendation-engine HTTP {resp.status}: {text[:200]}")
        return await resp.json()


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # FastAPI typically serializes datetimes as ISO strings
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except Exception:
            return None
    return None


def map_recommendation_to_row(rec: Dict[str, Any], api_base: str, symbol: str) -> Dict[str, Any]:
    """Map recommendation-engine response JSON into big_cap_losers columns."""
    explanation = rec.get("explanation")
    # Top news: the recommendation engine includes recent_articles inside explanation.
    top_news = None
    if isinstance(explanation, dict):
        ra = explanation.get("recent_articles")
        if isinstance(ra, list):
            top_news = ra[:10]

    regime_label = _safe_get(rec, "regime.label") or _safe_get(rec, "regime.volatility")
    regime_conf = _safe_get(rec, "regime.confidence") or _safe_get(rec, "regime.risk_score")

    # Component scores (best-effort mapping)
    news_score = rec.get("news_sentiment_score")
    technical_score = rec.get("technical_trend_score")

    return {
        "action": rec.get("action"),
        "score": rec.get("score"),
        "normalized_score": rec.get("normalized_score"),
        "confidence": rec.get("confidence"),
        "market_regime": regime_label,
        "regime_confidence": regime_conf,
        "news_score": news_score,
        "technical_score": technical_score,
        # UI can use this as an explanation link target (page can open a modal using explanation/top_news)
        "details_url": f"{api_base}/big-cap-losers?symbol={symbol}",
        "top_news": top_news,
        "explanation": explanation,
        "recommendation_generated_at": _parse_dt(rec.get("generated_at")),
    }

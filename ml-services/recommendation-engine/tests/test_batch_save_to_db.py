import pytest
import sys
import os

# Match the existing test style: add src to path for imports.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# We avoid spinning up the FastAPI server; instead we directly call the handler function
# and monkeypatch its dependencies.


@pytest.mark.asyncio
async def test_batch_generate_recommendations_saves_to_db(monkeypatch):
    import main as main

    class DummyPool:
        def __init__(self):
            self.calls = []

        async def execute(self, query, *args):
            self.calls.append((query, args))

    dummy_pool = DummyPool()

    async def fake_get_db_pool():
        return dummy_pool

    class DummyEngine:
        async def generate_recommendation(self, symbol: str, include_features: bool = False):
            # Minimal Recommendation object satisfying the fields used in execute()
            return main.Recommendation(
                symbol=symbol,
                action="HOLD",
                score=0.0,
                normalized_score=0.5,
                confidence=0.1,
                price_at_recommendation=None,
                news_sentiment_score=None,
                news_momentum_score=None,
                technical_trend_score=None,
                technical_momentum_score=None,
                rsi=None,
                macd_histogram=None,
                price_vs_sma20=None,
                news_sentiment_1d=None,
                article_count_24h=0,
                explanation={"summary": "ok"},
                signals=None,
                regime=None,
                signal_weights=None,
            )

    async def fake_get_engine():
        return DummyEngine()

    monkeypatch.setattr(main, "get_db_pool", fake_get_db_pool)
    monkeypatch.setattr(main, "get_engine", fake_get_engine)

    req = main.RecommendationRequest(user_id="system", symbols=["COMP"], include_features=False, save_to_db=True)
    resp = await main.generate_recommendations(req)

    assert resp.user_id == "system"
    assert len(resp.recommendations) == 1
    assert dummy_pool.calls, "Expected at least one DB insert call when save_to_db=True"


@pytest.mark.asyncio
async def test_batch_generate_recommendations_does_not_save_without_flag(monkeypatch):
    import main as main

    class DummyPool:
        def __init__(self):
            self.calls = []

        async def execute(self, query, *args):
            self.calls.append((query, args))

    dummy_pool = DummyPool()

    async def fake_get_db_pool():
        return dummy_pool

    class DummyEngine:
        async def generate_recommendation(self, symbol: str, include_features: bool = False):
            return main.Recommendation(
                symbol=symbol,
                action="HOLD",
                confidence=0.1,
                explanation={"summary": "ok"},
            )

    async def fake_get_engine():
        return DummyEngine()

    monkeypatch.setattr(main, "get_db_pool", fake_get_db_pool)
    monkeypatch.setattr(main, "get_engine", fake_get_engine)

    req = main.RecommendationRequest(user_id="system", symbols=["COMP"], include_features=False, save_to_db=False)
    resp = await main.generate_recommendations(req)

    assert resp.user_id == "system"
    assert len(resp.recommendations) == 1
    assert dummy_pool.calls == [], "DB should not be written when save_to_db=False"

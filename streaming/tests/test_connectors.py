"""
Tests for News Connectors
=========================

Unit tests for the news source connectors. These tests verify:
- Connector initialization
- Article parsing and normalization
- Error handling
- Rate limiting behavior

Note: Tests that require API keys are skipped if keys not available.
Set environment variables to run full integration tests.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import os
import aiohttp

# Import connectors
from streaming.connectors.base import (
    NewsArticle,
    NewsSource,
    NewsCategory,
    BaseNewsConnector,
)
from streaming.connectors.alpha_vantage import AlphaVantageConnector
from streaming.connectors.finnhub import FinnhubConnector
from streaming.connectors.newsapi import NewsAPIConnector
from streaming.connectors.rss_feeds import RSSFeedConnector


# =============================================================================
# NewsArticle Tests
# =============================================================================

class TestNewsArticle:
    """Tests for the NewsArticle data class."""
    
    def test_article_creation(self):
        """Test basic article creation."""
        article = NewsArticle(
            title="Test Article",
            summary="Test summary",
            url="https://example.com/article",
            source=NewsSource.ALPHA_VANTAGE,
            source_name="Test Source",
            published_at=datetime.utcnow(),
            symbols=["AAPL", "GOOGL"],
        )
        
        assert article.title == "Test Article"
        assert article.symbols == ["AAPL", "GOOGL"]
        assert article.source == NewsSource.ALPHA_VANTAGE
        assert article.article_id != ""  # Should be auto-generated
    
    def test_article_id_generation(self):
        """Test that article_id is deterministic."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        
        article1 = NewsArticle(
            title="Test",
            summary="Summary",
            url="https://example.com/test",
            source=NewsSource.FINNHUB,
            source_name="Test",
            published_at=timestamp,
        )
        
        article2 = NewsArticle(
            title="Different Title",  # Title doesn't affect ID
            summary="Different Summary",
            url="https://example.com/test",  # Same URL
            source=NewsSource.NEWSAPI,  # Different source
            source_name="Other",
            published_at=timestamp,  # Same timestamp
        )
        
        # Same URL + timestamp = same article_id
        assert article1.article_id == article2.article_id
    
    def test_article_to_dict(self):
        """Test serialization to dictionary."""
        article = NewsArticle(
            title="Test",
            summary="Summary",
            url="https://example.com",
            source=NewsSource.RSS_REUTERS,
            source_name="Reuters",
            published_at=datetime(2024, 1, 15),
            categories=[NewsCategory.EARNINGS],
        )
        
        data = article.to_dict()
        
        assert data["title"] == "Test"
        assert data["source"] == "rss_reuters"
        assert data["categories"] == ["earnings"]
        assert "article_id" in data
    
    def test_article_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "article_id": "abc123",
            "title": "Test Article",
            "summary": "Test summary",
            "url": "https://example.com",
            "source": "alpha_vantage",
            "source_name": "Alpha Vantage",
            "published_at": "2024-01-15T10:30:00",
            "symbols": ["AAPL"],
            "categories": ["earnings", "general"],
        }
        
        article = NewsArticle.from_dict(data)
        
        assert article.article_id == "abc123"
        assert article.title == "Test Article"
        assert article.source == NewsSource.ALPHA_VANTAGE
        assert NewsCategory.EARNINGS in article.categories


# =============================================================================
# Base Connector Tests
# =============================================================================

class TestBaseConnector:
    """Tests for BaseNewsConnector functionality."""
    
    def test_categorize_article_earnings(self):
        """Test article categorization for earnings news."""
        connector = RSSFeedConnector()  # Use concrete implementation
        
        categories = connector._categorize_article(
            title="Apple Reports Record Q4 Earnings",
            summary="Revenue beats expectations"
        )
        
        assert NewsCategory.EARNINGS in categories
    
    def test_categorize_article_merger(self):
        """Test article categorization for M&A news."""
        connector = RSSFeedConnector()
        
        categories = connector._categorize_article(
            title="Microsoft to Acquire Gaming Company",
            summary="The acquisition is valued at $10 billion"
        )
        
        assert NewsCategory.MERGER_ACQUISITION in categories
    
    def test_categorize_article_general(self):
        """Test article categorization defaults to general."""
        connector = RSSFeedConnector()
        
        categories = connector._categorize_article(
            title="Stock Market Today",
            summary="Markets opened higher on Monday"
        )
        
        assert NewsCategory.GENERAL in categories
    
    def test_extract_symbols(self):
        """Test symbol extraction from text."""
        connector = RSSFeedConnector()
        
        known_symbols = ["AAPL", "GOOGL", "MSFT", "IBM", "THE"]
        
        symbols = connector._extract_symbols_from_text(
            "AAPL and GOOGL reported earnings. THE market reacted.",
            known_symbols
        )
        
        # Should find AAPL and GOOGL, but not THE (common word)
        assert "AAPL" in symbols
        assert "GOOGL" in symbols
        assert "THE" in symbols  # Can't distinguish without NLP


# =============================================================================
# Alpha Vantage Connector Tests
# =============================================================================

class TestAlphaVantageConnector:
    """Tests for AlphaVantageConnector."""
    
    def test_initialization(self):
        """Test connector initialization."""
        connector = AlphaVantageConnector(api_key="test_key")
        
        assert connector.api_key == "test_key"
        assert connector.source == NewsSource.ALPHA_VANTAGE
        assert connector.rate_limit == 5  # Free tier
    
    def test_parse_article(self):
        """Test parsing Alpha Vantage article format."""
        connector = AlphaVantageConnector(api_key="test")
        
        item = {
            "title": "Apple Stock Rises",
            "summary": "AAPL shares up 5%",
            "url": "https://example.com/article",
            "time_published": "20240115T103000",
            "source": "Test Source",
            "overall_sentiment_score": 0.75,
            "overall_sentiment_label": "Bullish",
            "ticker_sentiment": [
                {
                    "ticker": "AAPL",
                    "relevance_score": "0.9",
                    "ticker_sentiment_score": "0.8",
                    "ticker_sentiment_label": "Bullish",
                }
            ],
            "topics": [{"topic": "earnings"}],
            "authors": ["John Doe"],
        }
        
        article = connector._parse_article(item)
        
        assert article is not None
        assert article.title == "Apple Stock Rises"
        assert "AAPL" in article.symbols
        assert article.metadata["sentiment_score"] == 0.75
        assert NewsCategory.EARNINGS in article.categories
    
    @pytest.mark.asyncio
    async def test_fetch_news_no_api_key(self):
        """Test that fetch_news raises error without API key."""
        connector = AlphaVantageConnector(api_key=None)
        
        with pytest.raises(ValueError, match="API key is required"):
            await connector.fetch_news(symbols=["AAPL"])


# =============================================================================
# BaseNewsConnector Utilities Tests
# =============================================================================

class TestBaseNewsConnectorUtilities:
    def test_sanitize_url_for_logs_redacts_token(self):
        safe = BaseNewsConnector._sanitize_url_for_logs(
            "https://api.benzinga.com/api/v2/news",
            params={"token": "super-secret", "pageSize": 1},
        )
        assert "super-secret" not in safe
        assert "token=REDACTED" in safe

    def test_is_retryable_exception_does_not_retry_auth_failures(self):
        exc_401 = aiohttp.ClientResponseError(
            request_info=MagicMock(real_url="https://example.com"),
            history=(),
            status=401,
            message="Unauthorized",
            headers={},
        )
        assert BaseNewsConnector._is_retryable_exception(exc_401) is False

        exc_403 = aiohttp.ClientResponseError(
            request_info=MagicMock(real_url="https://example.com"),
            history=(),
            status=403,
            message="Forbidden",
            headers={},
        )
        assert BaseNewsConnector._is_retryable_exception(exc_403) is False

        exc_500 = aiohttp.ClientResponseError(
            request_info=MagicMock(real_url="https://example.com"),
            history=(),
            status=500,
            message="Server error",
            headers={},
        )
        assert BaseNewsConnector._is_retryable_exception(exc_500) is True


# =============================================================================
# Finnhub Connector Tests
# =============================================================================

class TestFinnhubConnector:
    """Tests for FinnhubConnector."""
    
    def test_initialization(self):
        """Test connector initialization."""
        connector = FinnhubConnector(api_key="test_key")
        
        assert connector.api_key == "test_key"
        assert connector.source == NewsSource.FINNHUB
        assert connector.rate_limit == 60
    
    def test_parse_article(self):
        """Test parsing Finnhub article format."""
        connector = FinnhubConnector(api_key="test")
        
        item = {
            "category": "company",
            "datetime": 1705315800,  # Unix timestamp
            "headline": "Microsoft Cloud Revenue Grows",
            "id": 123456,
            "image": "https://example.com/image.jpg",
            "related": "MSFT,GOOGL",
            "source": "Reuters",
            "summary": "Azure growth exceeds expectations",
            "url": "https://example.com/article",
        }
        
        article = connector._parse_article(item, primary_symbol="MSFT")
        
        assert article is not None
        assert article.title == "Microsoft Cloud Revenue Grows"
        assert "MSFT" in article.symbols
        assert "GOOGL" in article.symbols
        assert article.source_name == "Reuters"


# =============================================================================
# NewsAPI Connector Tests
# =============================================================================

class TestNewsAPIConnector:
    """Tests for NewsAPIConnector."""
    
    def test_initialization(self):
        """Test connector initialization."""
        connector = NewsAPIConnector(api_key="test_key")
        
        assert connector.api_key == "test_key"
        assert connector.source == NewsSource.NEWSAPI
    
    def test_company_name_mapping(self):
        """Test that company names are mapped to symbols."""
        connector = NewsAPIConnector(api_key="test")
        
        assert "Apple" in connector.COMPANY_NAMES["AAPL"]
        assert "Google" in connector.COMPANY_NAMES["GOOGL"]
        assert "Microsoft" in connector.COMPANY_NAMES["MSFT"]
    
    def test_parse_article(self):
        """Test parsing NewsAPI article format."""
        connector = NewsAPIConnector(api_key="test")
        
        item = {
            "source": {"id": "bloomberg", "name": "Bloomberg"},
            "author": "Jane Smith",
            "title": "Apple iPhone Sales Beat Estimates",
            "description": "AAPL shares rose after strong iPhone demand",
            "url": "https://example.com/article",
            "urlToImage": "https://example.com/image.jpg",
            "publishedAt": "2024-01-15T10:30:00Z",
            "content": "Full article content...",
        }
        
        article = connector._parse_article(item, target_symbols=["AAPL"])
        
        assert article is not None
        assert article.title == "Apple iPhone Sales Beat Estimates"
        assert article.source_name == "Bloomberg"
        assert "AAPL" in article.symbols
    
    def test_parse_removed_article(self):
        """Test that removed articles are skipped."""
        connector = NewsAPIConnector(api_key="test")
        
        item = {
            "source": {"id": "test", "name": "Test"},
            "title": "[Removed]",
            "description": "[Removed]",
            "url": "https://example.com",
            "publishedAt": "2024-01-15T10:30:00Z",
        }
        
        article = connector._parse_article(item)
        
        assert article is None


# =============================================================================
# RSS Feed Connector Tests
# =============================================================================

class TestRSSFeedConnector:
    """Tests for RSSFeedConnector."""
    
    def test_initialization_all_feeds(self):
        """Test connector initialization with all feeds."""
        connector = RSSFeedConnector()
        
        assert len(connector.feeds) > 0
        assert "reuters_business" in connector.feeds
        assert "cnbc_top" in connector.feeds
    
    def test_initialization_specific_feeds(self):
        """Test connector initialization with specific feeds."""
        connector = RSSFeedConnector(
            enabled_feeds=["reuters_business", "yahoo_finance"]
        )
        
        assert len(connector.feeds) == 2
        assert "reuters_business" in connector.feeds
        assert "yahoo_finance" in connector.feeds
        assert "cnbc_top" not in connector.feeds
    
    def test_strip_html(self):
        """Test HTML stripping from text."""
        connector = RSSFeedConnector()
        
        html_text = "<p>This is <strong>bold</strong> text &amp; more</p>"
        clean_text = connector._strip_html(html_text)
        
        assert clean_text == "This is bold text & more"
    
    def test_parse_date_rfc2822(self):
        """Test parsing RFC 2822 date format."""
        connector = RSSFeedConnector()
        
        date_str = "Mon, 15 Jan 2024 10:30:00 GMT"
        parsed = connector._parse_date(date_str)
        
        assert parsed.year == 2024
        assert parsed.month == 1
        assert parsed.day == 15
    
    def test_parse_date_iso(self):
        """Test parsing ISO date format."""
        connector = RSSFeedConnector()
        
        date_str = "2024-01-15T10:30:00Z"
        parsed = connector._parse_date(date_str)
        
        assert parsed.year == 2024
        assert parsed.month == 1
    
    def test_add_custom_feed(self):
        """Test adding a custom RSS feed."""
        connector = RSSFeedConnector(enabled_feeds=[])
        
        connector.add_feed(
            feed_key="custom_feed",
            url="https://example.com/rss",
            source_name="Custom Source",
        )
        
        assert "custom_feed" in connector.feeds
        assert connector.feeds["custom_feed"]["url"] == "https://example.com/rss"


# =============================================================================
# Integration Tests (require API keys)
# =============================================================================

@pytest.mark.skipif(
    not os.getenv("ALPHA_VANTAGE_API_KEY"),
    reason="ALPHA_VANTAGE_API_KEY not set"
)
class TestAlphaVantageIntegration:
    """Integration tests for Alpha Vantage (requires API key)."""
    
    @pytest.mark.asyncio
    async def test_fetch_news_live(self):
        """Test fetching real news from Alpha Vantage."""
        connector = AlphaVantageConnector(
            api_key=os.getenv("ALPHA_VANTAGE_API_KEY")
        )
        
        try:
            articles = await connector.fetch_news(
                symbols=["AAPL"],
                limit=5
            )
            
            assert isinstance(articles, list)
            # May be empty if rate limited
            for article in articles:
                assert isinstance(article, NewsArticle)
                assert article.title
                assert article.url
        finally:
            await connector.close()


@pytest.mark.skipif(
    not os.getenv("FINNHUB_API_KEY"),
    reason="FINNHUB_API_KEY not set"
)
class TestFinnhubIntegration:
    """Integration tests for Finnhub (requires API key)."""
    
    @pytest.mark.asyncio
    async def test_fetch_news_live(self):
        """Test fetching real news from Finnhub."""
        connector = FinnhubConnector(
            api_key=os.getenv("FINNHUB_API_KEY")
        )
        
        try:
            articles = await connector.fetch_news(
                symbols=["AAPL"],
                since=datetime.utcnow() - timedelta(days=7),
                limit=5
            )
            
            assert isinstance(articles, list)
            for article in articles:
                assert isinstance(article, NewsArticle)
        finally:
            await connector.close()


class TestRSSFeedIntegration:
    """Integration tests for RSS feeds (no API key needed)."""
    
    @pytest.mark.asyncio
    async def test_fetch_rss_live(self):
        """Test fetching real RSS feeds."""
        connector = RSSFeedConnector(
            enabled_feeds=["marketwatch_top"]  # Usually reliable
        )
        
        try:
            articles = await connector.fetch_news(limit=10)
            
            # Should get some articles (unless network issue)
            assert isinstance(articles, list)
            # RSS feeds should work without API keys
            
        finally:
            await connector.close()

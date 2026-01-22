"""
News & Social Media Connectors Package
======================================

This package contains connectors for various news and social media data sources
used by the AutoTrader AI Continuous Intelligence Plane. Each connector fetches
content about stocks and companies, which is then processed for sentiment
analysis and fed into the recommendation engine.

Supported Data Sources:
-----------------------
News APIs:
- Alpha Vantage News API (market news with sentiment scores)
- Finnhub News API (company-specific news)
- NewsAPI.org (80,000+ news sources)
- Benzinga News API (real-time financial news)
- Financial Modeling Prep API (news + fundamentals)
- Yahoo Finance (news + market data)
- RSS Feeds (Reuters, Bloomberg, CNBC, etc.)

Regulatory Filings:
- SEC EDGAR (10-K, 10-Q, 8-K, insider trading)

Social Media:
- Reddit (r/wallstreetbets, r/stocks, etc.)
- X/Twitter (cashtags, influential accounts)
- StockTwits (pre-labeled sentiment)

Research & Analytics:
- TipRanks (analyst ratings, price targets)

Architecture:
- All connectors inherit from BaseNewsConnector
- Connectors are designed for batch polling (scheduled execution)
- All content is normalized to a common NewsArticle format
- Deduplication is handled at the pipeline level

Usage:
    from streaming.connectors import (
        AlphaVantageConnector,
        RedditConnector,
        StockTwitsConnector
    )
    
    # News connector
    news = AlphaVantageConnector(api_key="your_key")
    articles = await news.fetch_news(symbols=["AAPL", "GOOGL"])
    
    # Social media connector
    reddit = RedditConnector(client_id="id", client_secret="secret")
    posts = await reddit.fetch_news(symbols=["GME", "AMC"])
"""

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

# News API Connectors
from .alpha_vantage import AlphaVantageConnector
from .finnhub import FinnhubConnector
from .newsapi import NewsAPIConnector
from .rss_feeds import RSSFeedConnector
from .yahoo_finance import YahooFinanceConnector
from .benzinga import BenzingaConnector
from .financial_modeling_prep import FinancialModelingPrepConnector

# Market Data Connectors
from .polygon import PolygonConnector
from .iex_cloud import IEXCloudConnector
from .nasdaq_data_link import NasdaqDataLinkConnector

# Regulatory Filings
from .sec_edgar import SECEdgarConnector

# Social Media Connectors
from .reddit import RedditConnector
from .twitter import TwitterConnector
from .stocktwits import StockTwitsConnector

# Research & Analytics
from .tipranks import TipRanksConnector

__all__ = [
    # Base classes
    "BaseNewsConnector",
    "NewsArticle", 
    "NewsSource",
    "NewsCategory",
    
    # News APIs
    "AlphaVantageConnector",
    "FinnhubConnector",
    "NewsAPIConnector",
    "RSSFeedConnector",
    "YahooFinanceConnector",
    "BenzingaConnector",
    "FinancialModelingPrepConnector",
    
    # Market Data APIs
    "PolygonConnector",
    "IEXCloudConnector",
    "NasdaqDataLinkConnector",
    
    # Regulatory
    "SECEdgarConnector",
    
    # Social Media
    "RedditConnector",
    "TwitterConnector",
    "StockTwitsConnector",
    
    # Research
    "TipRanksConnector",
]

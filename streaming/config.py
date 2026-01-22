"""
Streaming Pipeline Configuration
================================

Central configuration for the news processing pipeline and related
services. All settings can be overridden via environment variables.

Environment Variables:
---------------------
News API Keys:
- ALPHA_VANTAGE_API_KEY: Alpha Vantage news API key
- FINNHUB_API_KEY: Finnhub news API key
- NEWSAPI_API_KEY: NewsAPI.org API key
- BENZINGA_API_KEY: Benzinga news API key
- FMP_API_KEY: Financial Modeling Prep API key

Social Media API Keys:
- REDDIT_CLIENT_ID: Reddit API client ID
- REDDIT_CLIENT_SECRET: Reddit API client secret
- TWITTER_BEARER_TOKEN: X (Twitter) API bearer token
- STOCKTWITS_ACCESS_TOKEN: StockTwits access token (optional)

LLM API Keys:
- OPENAI_API_KEY: OpenAI API key (for LLM sentiment)
- ANTHROPIC_API_KEY: Anthropic API key (alternative LLM)

Infrastructure:
- CLICKHOUSE_HOST: ClickHouse server host
- CLICKHOUSE_PORT: ClickHouse server port
- REDIS_URL: Redis connection URL
- KAFKA_BOOTSTRAP_SERVERS: Kafka brokers (for future real-time)

Pipeline Settings:
- NEWS_FETCH_INTERVAL_MINUTES: How often to fetch news
- NEWS_LOOKBACK_HOURS: How far back to look for news
- ENABLE_SENTIMENT_ANALYSIS: Whether to run sentiment analysis
- ENABLE_LLM_ANALYSIS: Whether to use LLM for high-importance news
- ENABLE_SOCIAL_MEDIA: Whether to fetch from social media sources
- ENABLE_SEC_FILINGS: Whether to fetch SEC filings
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Config:
    """
    Pipeline configuration with environment variable overrides.
    
    Usage:
        config = Config.from_env()
        print(config.clickhouse_host)
    """
    
    # ==========================================================================
    # News API Keys
    # ==========================================================================
    alpha_vantage_api_key: Optional[str] = None
    finnhub_api_key: Optional[str] = None
    newsapi_api_key: Optional[str] = None
    benzinga_api_key: Optional[str] = None
    fmp_api_key: Optional[str] = None  # Financial Modeling Prep
    
    # ==========================================================================
    # Social Media API Keys
    # ==========================================================================
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    twitter_bearer_token: Optional[str] = None
    stocktwits_access_token: Optional[str] = None  # Optional, works without
    
    # ==========================================================================
    # LLM API Keys
    # ==========================================================================
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # ==========================================================================
    # Infrastructure
    # ==========================================================================
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    redis_url: str = "redis://localhost:6379"
    kafka_bootstrap_servers: str = "localhost:9092"
    
    # ==========================================================================
    # Pipeline Settings
    # ==========================================================================
    # Stock symbols to track
    symbols: List[str] = field(default_factory=lambda: [
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA",
        "JPM", "V", "JNJ", "WMT", "PG"
    ])
    
    # News fetching
    fetch_interval_minutes: int = 5
    lookback_hours: int = 24
    max_articles_per_source: int = 50
    
    # Sentiment analysis
    enable_sentiment: bool = True
    enable_llm: bool = False
    llm_provider: str = "openai"  # openai or anthropic
    finbert_device: str = "auto"  # cpu, cuda, mps, auto
    
    # Source toggles
    enable_social_media: bool = True
    enable_sec_filings: bool = True
    enable_analyst_data: bool = True  # TipRanks
    
    # RSS feeds to enable (empty = all)
    rss_feeds: List[str] = field(default_factory=list)
    
    # Reddit subreddits to monitor
    reddit_subreddits: List[str] = field(default_factory=lambda: [
        "wallstreetbets", "stocks", "investing", "stockmarket", "options"
    ])
    
    # ==========================================================================
    # Derived Settings
    # ==========================================================================
    
    @property
    def has_news_api_keys(self) -> bool:
        """Check if any news API keys are configured."""
        return any([
            self.alpha_vantage_api_key,
            self.finnhub_api_key,
            self.newsapi_api_key,
            self.benzinga_api_key,
            self.fmp_api_key,
        ])
    
    @property
    def has_social_media_keys(self) -> bool:
        """Check if social media API keys are configured."""
        return any([
            self.reddit_client_id and self.reddit_client_secret,
            self.twitter_bearer_token,
            # StockTwits works without auth
        ])
    
    @property
    def llm_api_key(self) -> Optional[str]:
        """Get the appropriate LLM API key based on provider."""
        if self.llm_provider == "openai":
            return self.openai_api_key
        elif self.llm_provider == "anthropic":
            return self.anthropic_api_key
        return None
    
    @classmethod
    def from_env(cls) -> "Config":
        """
        Create configuration from environment variables.
        
        All settings have sensible defaults that work for local development.
        """
        # Parse symbols from comma-separated env var
        symbols_str = os.getenv("SYMBOLS", "")
        symbols = [s.strip() for s in symbols_str.split(",") if s.strip()] if symbols_str else None
        
        # Parse RSS feeds
        rss_str = os.getenv("RSS_FEEDS", "")
        rss_feeds = [s.strip() for s in rss_str.split(",") if s.strip()] if rss_str else []
        
        # Parse subreddits
        subreddits_str = os.getenv("REDDIT_SUBREDDITS", "")
        subreddits = [s.strip() for s in subreddits_str.split(",") if s.strip()] if subreddits_str else None
        
        config = cls(
            # News API Keys
            alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY"),
            finnhub_api_key=os.getenv("FINNHUB_API_KEY"),
            newsapi_api_key=os.getenv("NEWSAPI_API_KEY"),
            benzinga_api_key=os.getenv("BENZINGA_API_KEY"),
            fmp_api_key=os.getenv("FMP_API_KEY"),
            
            # Social Media API Keys
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            twitter_bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
            stocktwits_access_token=os.getenv("STOCKTWITS_ACCESS_TOKEN"),
            
            # LLM API Keys
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            
            # Infrastructure
            clickhouse_host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            clickhouse_port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            
            # Pipeline settings
            fetch_interval_minutes=int(os.getenv("NEWS_FETCH_INTERVAL_MINUTES", "5")),
            lookback_hours=int(os.getenv("NEWS_LOOKBACK_HOURS", "24")),
            max_articles_per_source=int(os.getenv("MAX_ARTICLES_PER_SOURCE", "50")),
            enable_sentiment=os.getenv("ENABLE_SENTIMENT_ANALYSIS", "true").lower() == "true",
            enable_llm=os.getenv("ENABLE_LLM_ANALYSIS", "false").lower() == "true",
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            finbert_device=os.getenv("FINBERT_DEVICE", "auto"),
            enable_social_media=os.getenv("ENABLE_SOCIAL_MEDIA", "true").lower() == "true",
            enable_sec_filings=os.getenv("ENABLE_SEC_FILINGS", "true").lower() == "true",
            enable_analyst_data=os.getenv("ENABLE_ANALYST_DATA", "true").lower() == "true",
            rss_feeds=rss_feeds,
        )
        
        # Override symbols if provided
        if symbols:
            config.symbols = symbols
        
        # Override subreddits if provided
        if subreddits:
            config.reddit_subreddits = subreddits
        
        return config
    
    def to_pipeline_config(self):
        """Convert to NewsProcessorConfig for the pipeline."""
        from streaming.processors.news_pipeline import NewsProcessorConfig
        
        return NewsProcessorConfig(
            symbols=self.symbols,
            fetch_interval_minutes=self.fetch_interval_minutes,
            lookback_hours=self.lookback_hours,
            max_articles_per_source=self.max_articles_per_source,
            enable_sentiment=self.enable_sentiment,
            enable_llm=self.enable_llm,
            llm_api_key=self.llm_api_key,
            llm_provider=self.llm_provider,
            clickhouse_host=self.clickhouse_host,
            clickhouse_port=self.clickhouse_port,
            redis_url=self.redis_url,
            
            # News APIs
            alpha_vantage_key=self.alpha_vantage_api_key,
            finnhub_key=self.finnhub_api_key,
            newsapi_key=self.newsapi_api_key,
            benzinga_key=self.benzinga_api_key,
            fmp_key=self.fmp_api_key,
            
            # Social Media
            reddit_client_id=self.reddit_client_id,
            reddit_client_secret=self.reddit_client_secret,
            twitter_bearer_token=self.twitter_bearer_token,
            stocktwits_token=self.stocktwits_access_token,
            reddit_subreddits=self.reddit_subreddits,
            
            # Feature toggles
            enable_social_media=self.enable_social_media,
            enable_sec_filings=self.enable_sec_filings,
            enable_analyst_data=self.enable_analyst_data,
            
            rss_feeds=self.rss_feeds,
        )
    
    def print_summary(self):
        """Print configuration summary for debugging."""
        print("=" * 60)
        print("News & Social Media Pipeline Configuration")
        print("=" * 60)
        print(f"Symbols: {', '.join(self.symbols[:5])}{'...' if len(self.symbols) > 5 else ''}")
        print(f"Fetch interval: {self.fetch_interval_minutes} minutes")
        print(f"Lookback: {self.lookback_hours} hours")
        print()
        print("News API Keys:")
        print(f"  Alpha Vantage: {'✓' if self.alpha_vantage_api_key else '✗'}")
        print(f"  Finnhub: {'✓' if self.finnhub_api_key else '✗'}")
        print(f"  NewsAPI: {'✓' if self.newsapi_api_key else '✗'}")
        print(f"  Benzinga: {'✓' if self.benzinga_api_key else '✗'}")
        print(f"  Financial Modeling Prep: {'✓' if self.fmp_api_key else '✗'}")
        print()
        print("Social Media Keys:")
        print(f"  Reddit: {'✓' if self.reddit_client_id else '✗'}")
        print(f"  X (Twitter): {'✓' if self.twitter_bearer_token else '✗'}")
        print(f"  StockTwits: {'✓' if self.stocktwits_access_token else '○ (works without)'}")
        print()
        print("Other Sources:")
        print(f"  Yahoo Finance: ✓ (no key required)")
        print(f"  SEC EDGAR: ✓ (no key required)")
        print(f"  RSS Feeds: ✓ (no key required)")
        print(f"  TipRanks: ○ (unofficial API)")
        print()
        print("LLM Keys:")
        print(f"  OpenAI: {'✓' if self.openai_api_key else '✗'}")
        print(f"  Anthropic: {'✓' if self.anthropic_api_key else '✗'}")
        print()
        print("Features:")
        print(f"  Sentiment Analysis: {'✓' if self.enable_sentiment else '✗'}")
        print(f"  LLM Analysis: {'✓' if self.enable_llm else '✗'}")
        print(f"  Social Media: {'✓' if self.enable_social_media else '✗'}")
        print(f"  SEC Filings: {'✓' if self.enable_sec_filings else '✗'}")
        print(f"  Analyst Data: {'✓' if self.enable_analyst_data else '✗'}")
        print()
        print("Infrastructure:")
        print(f"  ClickHouse: {self.clickhouse_host}:{self.clickhouse_port}")
        print(f"  Redis: {self.redis_url}")
        print("=" * 60)

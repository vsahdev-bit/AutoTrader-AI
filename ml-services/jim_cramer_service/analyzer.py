"""
Jim Cramer Content Analyzer
============================

Uses LLM (Groq) to analyze Jim Cramer articles and extract:
1. Stock mentions with sentiment (bullish/bearish/neutral)
2. Specific recommendations (buy/sell/hold)
3. Key points and reasoning
4. Daily summary generation

Provider Priority: Groq (free, fast) > Anthropic > OpenAI
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StockMention:
    """A stock mentioned by Jim Cramer."""
    symbol: str
    company_name: Optional[str]
    sentiment: str  # 'bullish', 'bearish', 'neutral', 'mixed'
    sentiment_score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    recommendation: Optional[str]  # 'buy', 'sell', 'hold', 'avoid', 'watch'
    reasoning: Optional[str]
    quote: Optional[str]
    price_target: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "reasoning": self.reasoning,
            "quote": self.quote,
            "price_target": self.price_target,
        }


@dataclass 
class ArticleAnalysis:
    """Analysis results for a single article."""
    article_url: str
    stock_mentions: List[StockMention]
    overall_sentiment: str
    key_points: List[str]
    summary: str
    raw_response: Optional[Dict] = None


@dataclass
class DailySummary:
    """Daily summary of Jim Cramer's views."""
    summary_date: datetime
    market_sentiment: str
    market_sentiment_score: float
    summary_title: str
    summary_text: str
    key_points: List[str]
    top_bullish_picks: List[Dict[str, str]]
    top_bearish_picks: List[Dict[str, str]]
    stocks_to_watch: List[Dict[str, str]]
    sectors_bullish: List[str]
    sectors_bearish: List[str]
    total_articles: int
    total_stocks: int
    llm_provider: str
    llm_model: str


class JimCramerAnalyzer:
    """
    LLM-based analyzer for Jim Cramer content.
    """
    
    # Groq configuration (primary - free and fast)
    GROQ_MODEL = "llama-3.3-70b-versatile"  # More capable model for analysis
    GROQ_FAST_MODEL = "llama-3.3-70b-versatile"  # Using same model as 8b is deprecated
    
    # System prompts
    ARTICLE_ANALYSIS_PROMPT = """You are a financial analyst specializing in extracting stock recommendations from Jim Cramer's content.

Analyze the following article and extract:
1. All stock tickers mentioned with Jim Cramer's sentiment on each
2. Any specific recommendations (buy, sell, hold, avoid, watch)
3. Price targets if mentioned
4. Key quotes about each stock
5. Overall market sentiment

IMPORTANT:
- Use standard stock ticker symbols (e.g., AAPL for Apple, MSFT for Microsoft)
- Sentiment should be: bullish, bearish, neutral, or mixed
- Sentiment score: -1.0 (very bearish) to 1.0 (very bullish)
- Only include stocks that Jim Cramer specifically comments on
- Be accurate with recommendations - don't infer what isn't stated

Respond in JSON format:
{
    "stock_mentions": [
        {
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "sentiment": "bullish",
            "sentiment_score": 0.7,
            "confidence": 0.9,
            "recommendation": "buy",
            "reasoning": "Strong iPhone sales and services growth",
            "quote": "I think Apple is a buy here",
            "price_target": null
        }
    ],
    "overall_sentiment": "bullish",
    "key_points": [
        "Cramer is bullish on tech stocks",
        "Recommends avoiding retail sector"
    ],
    "summary": "Brief 2-3 sentence summary of the article"
}"""

    DAILY_SUMMARY_PROMPT = """You are a financial journalist creating a daily summary of Jim Cramer's stock recommendations and market views.

Based on the following articles and stock mentions from today, create a comprehensive daily summary.

IMPORTANT:
- Synthesize across all articles to identify consistent themes
- Highlight stocks that were mentioned multiple times
- Note any contradictions or changes in stance
- Be specific about sectors and market outlook
- Keep the summary informative but concise

Respond in JSON format:
{
    "market_sentiment": "bullish|bearish|neutral|mixed",
    "market_sentiment_score": 0.5,
    "summary_title": "Catchy headline summarizing today's views",
    "summary_text": "Detailed 200-300 word summary of Cramer's views today",
    "key_points": [
        "Key takeaway 1",
        "Key takeaway 2",
        "Key takeaway 3"
    ],
    "top_bullish_picks": [
        {"symbol": "AAPL", "reasoning": "Why Cramer likes it"}
    ],
    "top_bearish_picks": [
        {"symbol": "XYZ", "reasoning": "Why Cramer is negative"}
    ],
    "stocks_to_watch": [
        {"symbol": "ABC", "reasoning": "Why to watch this one"}
    ],
    "sectors_bullish": ["Technology", "Healthcare"],
    "sectors_bearish": ["Retail", "Real Estate"]
}"""

    def __init__(self):
        """Initialize the analyzer with API keys."""
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Determine available providers
        self.providers = []
        if self.groq_api_key:
            self.providers.append("groq")
        if self.anthropic_api_key:
            self.providers.append("anthropic")
        if self.openai_api_key:
            self.providers.append("openai")
        
        if not self.providers:
            logger.warning("No LLM API keys configured!")
        else:
            logger.info(f"Cramer analyzer initialized with providers: {self.providers}")
    
    async def analyze_article(self, title: str, content: str, url: str) -> ArticleAnalysis:
        """
        Analyze a single article for stock mentions and sentiment.
        
        Args:
            title: Article title
            content: Article content (can be description if full content not available)
            url: Article URL
            
        Returns:
            ArticleAnalysis with extracted stock mentions
        """
        # Prepare the content for analysis
        text_to_analyze = f"Title: {title}\n\nContent: {content[:4000]}"  # Limit content length
        
        # Try each provider in order
        for provider in self.providers:
            try:
                if provider == "groq":
                    result = await self._analyze_with_groq(text_to_analyze)
                elif provider == "anthropic":
                    result = await self._analyze_with_anthropic(text_to_analyze)
                elif provider == "openai":
                    result = await self._analyze_with_openai(text_to_analyze)
                else:
                    continue
                
                if result:
                    return self._parse_article_analysis(result, url)
                    
            except Exception as e:
                logger.warning(f"Error with {provider}: {e}")
                continue
        
        # Return empty analysis if all providers fail
        logger.error(f"All LLM providers failed for article: {title}")
        return ArticleAnalysis(
            article_url=url,
            stock_mentions=[],
            overall_sentiment="unknown",
            key_points=[],
            summary="Analysis failed",
        )
    
    async def generate_daily_summary(
        self,
        articles: List[Dict],
        stock_mentions: List[Dict],
    ) -> DailySummary:
        """
        Generate a daily summary from all articles and stock mentions.
        
        Args:
            articles: List of article dicts with title, url, summary
            stock_mentions: List of stock mention dicts
            
        Returns:
            DailySummary with comprehensive daily overview
        """
        # Prepare input data
        input_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_articles": len(articles),
            "articles": [
                {"title": a.get("title", ""), "summary": a.get("summary", "")}
                for a in articles[:10]  # Limit to top 10 articles
            ],
            "stock_mentions": self._aggregate_stock_mentions(stock_mentions),
        }
        
        prompt_content = f"""Today's Date: {input_data['date']}
Total Articles Analyzed: {input_data['total_articles']}

Articles:
{json.dumps(input_data['articles'], indent=2)}

Stock Mentions Summary:
{json.dumps(input_data['stock_mentions'], indent=2)}

Please generate a comprehensive daily summary."""

        # Try each provider
        provider_used = None
        model_used = None
        
        for provider in self.providers:
            try:
                if provider == "groq":
                    result = await self._summarize_with_groq(prompt_content)
                    model_used = self.GROQ_MODEL
                elif provider == "anthropic":
                    result = await self._summarize_with_anthropic(prompt_content)
                    model_used = "claude-3-haiku-20240307"
                elif provider == "openai":
                    result = await self._summarize_with_openai(prompt_content)
                    model_used = "gpt-4o-mini"
                else:
                    continue
                
                if result:
                    provider_used = provider
                    return self._parse_daily_summary(result, len(articles), len(stock_mentions), provider_used, model_used)
                    
            except Exception as e:
                logger.warning(f"Error with {provider} for daily summary: {e}")
                continue
        
        # Return minimal summary if all providers fail
        return DailySummary(
            summary_date=datetime.now(timezone.utc),
            market_sentiment="unknown",
            market_sentiment_score=0.0,
            summary_title="Daily Summary Generation Failed",
            summary_text="Unable to generate summary. Please check individual articles.",
            key_points=[],
            top_bullish_picks=[],
            top_bearish_picks=[],
            stocks_to_watch=[],
            sectors_bullish=[],
            sectors_bearish=[],
            total_articles=len(articles),
            total_stocks=len(stock_mentions),
            llm_provider="none",
            llm_model="none",
        )
    
    async def _analyze_with_groq(self, content: str) -> Optional[Dict]:
        """Call Groq API for article analysis."""
        import aiohttp
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.GROQ_FAST_MODEL,  # Use fast model for individual articles
            "messages": [
                {"role": "system", "content": self.ARTICLE_ANALYSIS_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"},
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.warning(f"Groq API error: {response.status} - {error}")
                    return None
                
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
    
    async def _summarize_with_groq(self, content: str) -> Optional[Dict]:
        """Call Groq API for daily summary."""
        import aiohttp
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.GROQ_MODEL,  # Use larger model for summary
            "messages": [
                {"role": "system", "content": self.DAILY_SUMMARY_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0.5,
            "max_tokens": 3000,
            "response_format": {"type": "json_object"},
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.warning(f"Groq API error: {response.status} - {error}")
                    return None
                
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
    
    async def _analyze_with_anthropic(self, content: str) -> Optional[Dict]:
        """Call Anthropic API for article analysis."""
        import aiohttp
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        
        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 2000,
            "system": self.ARTICLE_ANALYSIS_PROMPT,
            "messages": [
                {"role": "user", "content": content},
            ],
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.warning(f"Anthropic API error: {response.status} - {error}")
                    return None
                
                data = await response.json()
                text = data["content"][0]["text"]
                
                # Extract JSON from response
                json_match = re.search(r'\{[\s\S]*\}', text)
                if json_match:
                    return json.loads(json_match.group())
                return None
    
    async def _summarize_with_anthropic(self, content: str) -> Optional[Dict]:
        """Call Anthropic API for daily summary."""
        import aiohttp
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        
        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 3000,
            "system": self.DAILY_SUMMARY_PROMPT,
            "messages": [
                {"role": "user", "content": content},
            ],
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                text = data["content"][0]["text"]
                
                json_match = re.search(r'\{[\s\S]*\}', text)
                if json_match:
                    return json.loads(json_match.group())
                return None
    
    async def _analyze_with_openai(self, content: str) -> Optional[Dict]:
        """Call OpenAI API for article analysis."""
        import aiohttp
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": self.ARTICLE_ANALYSIS_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"},
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
    
    async def _summarize_with_openai(self, content: str) -> Optional[Dict]:
        """Call OpenAI API for daily summary."""
        import aiohttp
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": self.DAILY_SUMMARY_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0.5,
            "max_tokens": 3000,
            "response_format": {"type": "json_object"},
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
    
    def _parse_article_analysis(self, result: Dict, url: str) -> ArticleAnalysis:
        """Parse LLM response into ArticleAnalysis."""
        stock_mentions = []
        
        for mention in result.get("stock_mentions", []):
            stock_mentions.append(StockMention(
                symbol=mention.get("symbol", "").upper(),
                company_name=mention.get("company_name"),
                sentiment=mention.get("sentiment", "neutral"),
                sentiment_score=float(mention.get("sentiment_score", 0.0)),
                confidence=float(mention.get("confidence", 0.5)),
                recommendation=mention.get("recommendation"),
                reasoning=mention.get("reasoning"),
                quote=mention.get("quote"),
                price_target=float(mention["price_target"]) if mention.get("price_target") else None,
            ))
        
        return ArticleAnalysis(
            article_url=url,
            stock_mentions=stock_mentions,
            overall_sentiment=result.get("overall_sentiment", "neutral"),
            key_points=result.get("key_points", []),
            summary=result.get("summary", ""),
            raw_response=result,
        )
    
    def _parse_daily_summary(
        self,
        result: Dict,
        total_articles: int,
        total_stocks: int,
        provider: str,
        model: str,
    ) -> DailySummary:
        """Parse LLM response into DailySummary."""
        return DailySummary(
            summary_date=datetime.now(timezone.utc),
            market_sentiment=result.get("market_sentiment", "neutral"),
            market_sentiment_score=float(result.get("market_sentiment_score", 0.0)),
            summary_title=result.get("summary_title", "Jim Cramer Daily Summary"),
            summary_text=result.get("summary_text", ""),
            key_points=result.get("key_points", []),
            top_bullish_picks=result.get("top_bullish_picks", []),
            top_bearish_picks=result.get("top_bearish_picks", []),
            stocks_to_watch=result.get("stocks_to_watch", []),
            sectors_bullish=result.get("sectors_bullish", []),
            sectors_bearish=result.get("sectors_bearish", []),
            total_articles=total_articles,
            total_stocks=total_stocks,
            llm_provider=provider,
            llm_model=model,
        )
    
    def _aggregate_stock_mentions(self, mentions: List[Dict]) -> List[Dict]:
        """Aggregate stock mentions by symbol."""
        aggregated = {}
        
        for mention in mentions:
            symbol = mention.get("symbol", "").upper()
            if not symbol:
                continue
            
            if symbol not in aggregated:
                aggregated[symbol] = {
                    "symbol": symbol,
                    "company_name": mention.get("company_name"),
                    "mention_count": 0,
                    "sentiments": [],
                    "recommendations": [],
                    "reasonings": [],
                }
            
            aggregated[symbol]["mention_count"] += 1
            if mention.get("sentiment"):
                aggregated[symbol]["sentiments"].append(mention["sentiment"])
            if mention.get("recommendation"):
                aggregated[symbol]["recommendations"].append(mention["recommendation"])
            if mention.get("reasoning"):
                aggregated[symbol]["reasonings"].append(mention["reasoning"])
        
        # Calculate dominant sentiment
        for symbol, data in aggregated.items():
            if data["sentiments"]:
                from collections import Counter
                data["dominant_sentiment"] = Counter(data["sentiments"]).most_common(1)[0][0]
            else:
                data["dominant_sentiment"] = "neutral"
        
        return list(aggregated.values())

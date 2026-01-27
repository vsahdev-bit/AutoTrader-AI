"""
Hybrid Sentiment Analyzer
=========================

This module implements a hybrid sentiment analysis system that combines:
1. FinBERT: Pre-trained transformer model for financial sentiment (bulk processing)
2. LLM (OpenAI/Claude): For high-importance news requiring deeper analysis

The hybrid approach balances cost, speed, and accuracy:
- FinBERT: Fast, free, good for standard news (~85% accuracy)
- LLM: Slower, costs per token, excellent for nuanced analysis (~95% accuracy)

Architecture:
- All articles go through FinBERT first for baseline sentiment
- High-importance articles (earnings, M&A, etc.) also get LLM analysis
- Final sentiment is weighted combination based on article importance

Sentiment Scale:
- Score: -1.0 (very bearish) to +1.0 (very bullish)
- Labels: VERY_BEARISH, BEARISH, NEUTRAL, BULLISH, VERY_BULLISH
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
import asyncio
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SentimentLabel(Enum):
    """Categorical sentiment labels."""
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"
    
    @classmethod
    def from_score(cls, score: float) -> "SentimentLabel":
        """Convert numeric score to label."""
        if score <= -0.6:
            return cls.VERY_BEARISH
        elif score <= -0.2:
            return cls.BEARISH
        elif score <= 0.2:
            return cls.NEUTRAL
        elif score <= 0.6:
            return cls.BULLISH
        else:
            return cls.VERY_BULLISH


@dataclass
class SentimentResult:
    """
    Result of sentiment analysis on a piece of text.
    
    Attributes:
        score: Numeric sentiment from -1.0 (bearish) to +1.0 (bullish)
        label: Categorical sentiment label
        confidence: Model confidence in the prediction (0.0 to 1.0)
        analyzer: Which analyzer produced this result (finbert, llm)
        reasoning: Optional explanation (primarily from LLM)
        aspects: Aspect-based sentiment (e.g., {"revenue": 0.8, "guidance": -0.3})
    """
    score: float
    label: SentimentLabel
    confidence: float
    analyzer: str
    reasoning: Optional[str] = None
    aspects: Optional[Dict[str, float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "score": self.score,
            "label": self.label.value,
            "confidence": self.confidence,
            "analyzer": self.analyzer,
            "reasoning": self.reasoning,
            "aspects": self.aspects,
        }


class BaseSentimentAnalyzer(ABC):
    """Abstract base class for sentiment analyzers."""
    
    @abstractmethod
    async def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of a single text."""
        pass
    
    @abstractmethod
    async def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze sentiment of multiple texts."""
        pass


class FinBERTAnalyzer(BaseSentimentAnalyzer):
    """
    Sentiment analyzer using FinBERT model.
    
    FinBERT is a BERT model fine-tuned on financial text, providing
    good accuracy for financial news sentiment without API costs.
    
    Model: ProsusAI/finbert (available on HuggingFace)
    
    Performance:
    - Accuracy: ~85% on financial text
    - Speed: ~100 articles/second on GPU, ~10/second on CPU
    - Cost: Free (runs locally)
    
    Example:
        analyzer = FinBERTAnalyzer()
        await analyzer.load_model()
        result = await analyzer.analyze("Apple reports record earnings")
        print(result.score)  # 0.85 (bullish)
    """
    
    def __init__(self, device: str = "auto", batch_size: int = 32):
        """
        Initialize FinBERT analyzer.
        
        Args:
            device: Device to run model on ("cpu", "cuda", "mps", "auto")
            batch_size: Batch size for inference
        """
        self.device = device
        self.batch_size = batch_size
        self.model = None
        self.tokenizer = None
        self._loaded = False
    
    async def load_model(self):
        """
        Load FinBERT model and tokenizer.
        
        Downloads model from HuggingFace Hub on first run (~500MB).
        Subsequent runs use cached model.
        """
        if self._loaded:
            return
        
        logger.info("Loading FinBERT model...")
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model_sync)
        
        self._loaded = True
        logger.info(f"FinBERT model loaded on device: {self.device}")
    
    def _load_model_sync(self):
        """Synchronous model loading."""
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch
            
            model_name = "ProsusAI/finbert"
            
            # Determine device
            if self.device == "auto":
                if torch.cuda.is_available():
                    self.device = "cuda"
                elif torch.backends.mps.is_available():
                    self.device = "mps"
                else:
                    self.device = "cpu"
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            
        except ImportError:
            logger.error("transformers or torch not installed. Run: pip install transformers torch")
            raise
    
    async def analyze(self, text: str) -> SentimentResult:
        """
        Analyze sentiment of a single text.
        
        Args:
            text: Text to analyze (headline, summary, or content)
            
        Returns:
            SentimentResult with score, label, and confidence
        """
        results = await self.analyze_batch([text])
        return results[0]
    
    async def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """
        Analyze sentiment of multiple texts in batches.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of SentimentResult objects
        """
        if not self._loaded:
            await self.load_model()
        
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            self._analyze_batch_sync,
            texts
        )
        return results
    
    def _analyze_batch_sync(self, texts: List[str]) -> List[SentimentResult]:
        """Synchronous batch analysis."""
        import torch
        import torch.nn.functional as F
        
        results = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            
            # Tokenize
            inputs = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            ).to(self.device)
            
            # Inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = F.softmax(outputs.logits, dim=-1)
            
            # FinBERT labels: positive, negative, neutral (indices 0, 1, 2)
            # Convert to our format
            for j, prob in enumerate(probs):
                positive_prob = prob[0].item()
                negative_prob = prob[1].item()
                neutral_prob = prob[2].item()
                
                # Calculate score: positive contributes +, negative contributes -
                # Weighted by confidence
                score = positive_prob - negative_prob
                
                # Confidence is the probability of the predicted class
                confidence = max(positive_prob, negative_prob, neutral_prob)
                
                label = SentimentLabel.from_score(score)
                
                results.append(SentimentResult(
                    score=round(score, 4),
                    label=label,
                    confidence=round(confidence, 4),
                    analyzer="finbert",
                ))
        
        return results


class LLMAnalyzer(BaseSentimentAnalyzer):
    """
    Sentiment analyzer using Large Language Models (OpenAI/Claude).
    
    LLMs provide superior analysis for nuanced financial text, including:
    - Context-aware sentiment (understanding sarcasm, hedging)
    - Aspect-based sentiment (different sentiment for different topics)
    - Reasoning explanation for transparency
    
    Performance:
    - Accuracy: ~95% on financial text
    - Speed: ~2-5 seconds per article
    - Cost: $0.001-0.01 per article depending on length
    
    Example:
        analyzer = LLMAnalyzer(api_key="sk-...", provider="openai")
        result = await analyzer.analyze(
            "Apple reports record earnings but warns of supply chain issues"
        )
        print(result.aspects)  # {"earnings": 0.9, "guidance": -0.4}
    """
    
    def __init__(
        self,
        api_key: str,
        provider: str = "openai",
        model: Optional[str] = None,
    ):
        """
        Initialize LLM analyzer.
        
        Args:
            api_key: API key for the LLM provider
            provider: LLM provider ("openai" or "anthropic")
            model: Specific model to use (default: gpt-4o-mini or claude-3-haiku)
        """
        self.api_key = api_key
        self.provider = provider.lower()
        
        # Set default model based on provider
        if model:
            self.model = model
        elif self.provider == "openai":
            self.model = "gpt-4o-mini"  # Good balance of cost and quality
        elif self.provider == "anthropic":
            self.model = "claude-3-haiku-20240307"  # Fast and affordable
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        self.client = None
    
    async def _get_client(self):
        """Get or create API client."""
        if self.client is not None:
            return self.client
        
        if self.provider == "openai":
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        
        elif self.provider == "anthropic":
            try:
                from anthropic import AsyncAnthropic
                self.client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        return self.client
    
    async def analyze(self, text: str, context: Optional[str] = None) -> SentimentResult:
        """
        Analyze sentiment using LLM with detailed reasoning.
        
        Args:
            text: Text to analyze
            context: Optional additional context (e.g., company info)
            
        Returns:
            SentimentResult with score, aspects, and reasoning
        """
        client = await self._get_client()
        
        # Build prompt for structured sentiment analysis
        prompt = self._build_prompt(text, context)
        
        try:
            if self.provider == "openai":
                response = await self._analyze_openai(client, prompt)
            else:
                response = await self._analyze_anthropic(client, prompt)
            
            return self._parse_response(response)
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            # Return neutral sentiment on failure
            return SentimentResult(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                confidence=0.0,
                analyzer="llm",
                reasoning=f"Analysis failed: {str(e)}",
            )
    
    async def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """
        Analyze multiple texts concurrently.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of SentimentResult objects
        """
        tasks = [self.analyze(text) for text in texts]
        return await asyncio.gather(*tasks)
    
    def _build_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build structured prompt for sentiment analysis."""
        prompt = f"""Analyze the sentiment of this financial news article for stock trading purposes.

Article:
{text}

{"Context: " + context if context else ""}

Provide your analysis in the following JSON format:
{{
    "overall_score": <float from -1.0 (very bearish) to 1.0 (very bullish)>,
    "confidence": <float from 0.0 to 1.0>,
    "aspects": {{
        "<aspect1>": <score>,
        "<aspect2>": <score>
    }},
    "reasoning": "<brief explanation of the sentiment>"
}}

Consider:
- Impact on stock price (short-term and long-term)
- Tone and language used
- Specific metrics mentioned (revenue, earnings, guidance)
- Market context and competitive implications

Respond ONLY with the JSON, no other text."""
        return prompt
    
    async def _analyze_openai(self, client, prompt: str) -> str:
        """Call OpenAI API."""
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a financial analyst expert at sentiment analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Low temperature for consistent analysis
            max_tokens=500,
        )
        return response.choices[0].message.content
    
    async def _analyze_anthropic(self, client, prompt: str) -> str:
        """Call Anthropic API."""
        response = await client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        return response.content[0].text
    
    def _parse_response(self, response: str) -> SentimentResult:
        """Parse LLM JSON response into SentimentResult."""
        import json
        
        try:
            # Extract JSON from response (handle markdown code blocks)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            data = json.loads(response)
            
            score = float(data.get("overall_score", 0))
            confidence = float(data.get("confidence", 0.5))
            aspects = data.get("aspects", {})
            reasoning = data.get("reasoning", "")
            
            return SentimentResult(
                score=round(max(-1, min(1, score)), 4),  # Clamp to [-1, 1]
                label=SentimentLabel.from_score(score),
                confidence=round(confidence, 4),
                analyzer="llm",
                reasoning=reasoning,
                aspects=aspects,
            )
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return SentimentResult(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                confidence=0.0,
                analyzer="llm",
                reasoning=f"Parse error: {response[:200]}",
            )


class LLMAnalyzerWithFallback(BaseSentimentAnalyzer):
    """
    LLM Analyzer with automatic fallback through multiple providers.
    
    This analyzer tries multiple LLM providers in order until one succeeds:
    1. OpenAI (gpt-4o-mini) - Primary, paid
    2. Anthropic (claude-3-haiku) - Fallback 1, paid
    3. Google Gemini (gemini-1.5-flash) - Fallback 2, free tier available
    4. Groq (llama-3.1-8b) - Fallback 3, free tier available
    
    All API keys are loaded from Vault with fallback to environment variables.
    
    Example:
        analyzer = LLMAnalyzerWithFallback()  # Auto-loads keys from Vault
        result = await analyzer.analyze("Apple reports record earnings...")
        print(result.analyzer)  # "llm-openai", "llm-anthropic", "llm-gemini", or "llm-groq"
    """
    
    # Provider configuration in fallback order
    # Priority: Groq (free, fast) > Anthropic (reliable) > OpenAI (often rate-limited)
    # 
    # Groq is prioritized because:
    # 1. Free tier with generous limits
    # 2. Very fast inference (LPU hardware)
    # 3. Good quality for sentiment analysis
    #
    # OpenAI is last because it frequently hits quota limits (429 errors)
    PROVIDERS = [
        {
            'name': 'groq',
            'vault_key': 'groq',
            'env_var': 'GROQ_API_KEY',
            'model': 'llama-3.1-8b-instant',
            'description': 'Groq Llama 3.1 8B (free tier, fast)',
        },
        {
            'name': 'anthropic',
            'vault_key': 'anthropic',
            'env_var': 'ANTHROPIC_API_KEY',
            'model': 'claude-3-haiku-20240307',
            'description': 'Anthropic Claude 3 Haiku (paid, reliable)',
        },
        {
            'name': 'openai',
            'vault_key': 'openai',
            'env_var': 'OPENAI_API_KEY',
            'model': 'gpt-4o-mini',
            'description': 'OpenAI GPT-4o-mini (paid, often rate-limited)',
        },
    ]
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
    ):
        """
        Initialize LLM analyzer with multi-provider fallback support.
        
        Args:
            openai_api_key: OpenAI API key (or loaded from Vault/env)
            anthropic_api_key: Anthropic API key (or loaded from Vault/env)
            groq_api_key: Groq API key (or loaded from Vault/env)
        """
        self._api_keys = {
            'openai': openai_api_key,
            'anthropic': anthropic_api_key,
            'groq': groq_api_key,
        }
        self._keys_loaded = False
        self._analyzers: Dict[str, LLMAnalyzer] = {}
        self._clients: Dict[str, Any] = {}
    
    async def _load_keys_from_vault(self):
        """Load API keys from Vault if not already provided."""
        if self._keys_loaded:
            return
        
        import os
        
        # Try to load from Vault
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            from vault_client import get_api_key
            
            for provider in self.PROVIDERS:
                name = provider['name']
                if not self._api_keys.get(name):
                    key = await get_api_key(provider['vault_key'])
                    if key:
                        self._api_keys[name] = key
                        logger.info(f"Loaded {name} API key from Vault")
                    
        except Exception as e:
            logger.debug(f"Could not load LLM keys from Vault: {e}")
        
        # Fallback to environment variables
        for provider in self.PROVIDERS:
            name = provider['name']
            if not self._api_keys.get(name):
                key = os.getenv(provider['env_var'])
                if key:
                    self._api_keys[name] = key
                    logger.info(f"Loaded {name} API key from environment")
        
        # Initialize analyzers for providers with keys
        for provider in self.PROVIDERS:
            name = provider['name']
            if self._api_keys.get(name):
                if name in ('openai', 'anthropic'):
                    # Use existing LLMAnalyzer for OpenAI and Anthropic
                    self._analyzers[name] = LLMAnalyzer(
                        api_key=self._api_keys[name],
                        provider=name,
                        model=provider['model'],
                    )
                # Gemini and Groq will use direct API calls
        
        self._keys_loaded = True
        
        available = [p['name'] for p in self.PROVIDERS if self._api_keys.get(p['name'])]
        if available:
            logger.info(f"LLM providers available: {', '.join(available)}")
        else:
            logger.warning("No LLM API keys configured. LLM analysis will be unavailable.")
    
    async def _analyze_with_openai(self, text: str, context: Optional[str] = None) -> SentimentResult:
        """Analyze using OpenAI API directly (without catching exceptions)."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        client = AsyncOpenAI(api_key=self._api_keys['openai'])
        prompt = self._build_sentiment_prompt(text, context)
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a financial sentiment analyzer. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500,
        )
        
        return self._parse_llm_response(response.choices[0].message.content, "openai")
    
    async def _analyze_with_anthropic(self, text: str, context: Optional[str] = None) -> SentimentResult:
        """Analyze using Anthropic API directly (without catching exceptions)."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        client = AsyncAnthropic(api_key=self._api_keys['anthropic'])
        prompt = self._build_sentiment_prompt(text, context)
        
        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        
        return self._parse_llm_response(response.content[0].text, "anthropic")
    
    async def _analyze_with_groq(self, text: str, context: Optional[str] = None) -> SentimentResult:
        """Analyze using Groq API."""
        try:
            from groq import AsyncGroq
        except ImportError:
            raise ImportError("groq package not installed. Run: pip install groq")
        
        client = AsyncGroq(api_key=self._api_keys['groq'])
        
        prompt = self._build_sentiment_prompt(text, context)
        
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a financial sentiment analyzer. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500,
        )
        
        return self._parse_llm_response(response.choices[0].message.content, "groq")
    
    def _build_sentiment_prompt(self, text: str, context: Optional[str] = None) -> str:
        """Build the sentiment analysis prompt."""
        context_section = f"\nAdditional Context: {context}" if context else ""
        
        return f"""Analyze the sentiment of this financial news text. 
Provide a JSON response with:
- score: float from -1.0 (very negative) to 1.0 (very positive)
- label: one of "very_negative", "negative", "neutral", "positive", "very_positive"
- confidence: float from 0.0 to 1.0
- aspects: object with aspect-specific sentiment scores (e.g., "earnings": 0.8, "guidance": -0.3)
- reasoning: brief explanation of the sentiment

Text: {text}{context_section}

Respond with valid JSON only, no markdown formatting."""

    def _parse_llm_response(self, response: str, provider: str) -> SentimentResult:
        """Parse LLM response into SentimentResult."""
        import json
        import re
        
        # Clean up response - remove markdown code blocks if present
        response = response.strip()
        response = re.sub(r'^```json\s*', '', response)
        response = re.sub(r'^```\s*', '', response)
        response = re.sub(r'\s*```$', '', response)
        
        try:
            data = json.loads(response)
            
            score = float(data.get('score', 0.0))
            label_str = data.get('label', 'neutral').lower()
            
            label_map = {
                'very_negative': SentimentLabel.VERY_BEARISH,
                'very_bearish': SentimentLabel.VERY_BEARISH,
                'negative': SentimentLabel.BEARISH,
                'bearish': SentimentLabel.BEARISH,
                'neutral': SentimentLabel.NEUTRAL,
                'positive': SentimentLabel.BULLISH,
                'bullish': SentimentLabel.BULLISH,
                'very_positive': SentimentLabel.VERY_BULLISH,
                'very_bullish': SentimentLabel.VERY_BULLISH,
            }
            
            return SentimentResult(
                score=score,
                label=label_map.get(label_str, SentimentLabel.NEUTRAL),
                confidence=float(data.get('confidence', 0.8)),
                analyzer=f"llm-{provider}",
                aspects=data.get('aspects', {}),
                reasoning=data.get('reasoning', ''),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse {provider} response: {e}")
            raise ValueError(f"Invalid response from {provider}")
    
    async def analyze(self, text: str, context: Optional[str] = None) -> SentimentResult:
        """
        Analyze sentiment using LLM with automatic fallback through all providers.
        
        Tries providers in order: OpenAI → Anthropic → Gemini → Groq
        
        Args:
            text: Text to analyze
            context: Optional additional context
            
        Returns:
            SentimentResult with score, aspects, and reasoning
        """
        await self._load_keys_from_vault()
        
        errors = []
        
        for provider in self.PROVIDERS:
            name = provider['name']
            
            if not self._api_keys.get(name):
                continue
            
            try:
                logger.debug(f"Attempting sentiment analysis with {name}...")
                
                if name == 'openai':
                    result = await self._analyze_with_openai(text, context)
                elif name == 'anthropic':
                    result = await self._analyze_with_anthropic(text, context)
                elif name == 'groq':
                    result = await self._analyze_with_groq(text, context)
                else:
                    continue
                
                logger.debug(f"{name} analysis successful: score={result.score}")
                return result
                
            except Exception as e:
                error_msg = f"{name} failed: {str(e)[:100]}"
                errors.append(error_msg)
                logger.warning(f"{error_msg}, trying next provider...")
        
        # All providers failed
        logger.error(f"All LLM providers failed: {'; '.join(errors)}")
        return SentimentResult(
            score=0.0,
            label=SentimentLabel.NEUTRAL,
            confidence=0.0,
            analyzer="llm-failed",
            reasoning=f"All LLM providers failed: {'; '.join(errors)}",
        )
    
    async def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """
        Analyze multiple texts with automatic fallback.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            List of SentimentResult objects
        """
        await self._load_keys_from_vault()
        
        errors = []
        
        for provider in self.PROVIDERS:
            name = provider['name']
            
            if not self._api_keys.get(name):
                continue
            
            try:
                logger.debug(f"Attempting batch analysis of {len(texts)} texts with {name}...")
                
                if name in ('openai', 'anthropic') and name in self._analyzers:
                    results = await self._analyzers[name].analyze_batch(texts)
                    for r in results:
                        r.analyzer = f"llm-{name}"
                    return results
                elif name == 'groq':
                    # For Groq, analyze one by one
                    results = []
                    for text in texts:
                        result = await self._analyze_with_groq(text)
                        results.append(result)
                    return results
                    
            except Exception as e:
                error_msg = f"{name} batch failed: {str(e)[:100]}"
                errors.append(error_msg)
                logger.warning(f"{error_msg}, trying next provider...")
        
        # All providers failed
        logger.error(f"All LLM providers failed for batch: {'; '.join(errors)}")
        return [
            SentimentResult(
                score=0.0,
                label=SentimentLabel.NEUTRAL,
                confidence=0.0,
                analyzer="llm-failed",
                reasoning=f"All LLM providers failed",
            )
            for _ in texts
        ]
    
    @property
    def is_available(self) -> bool:
        """Check if at least one LLM provider is configured."""
        return any(self._api_keys.get(p['name']) for p in self.PROVIDERS)
    
    @property
    def available_providers(self) -> List[str]:
        """Get list of configured providers."""
        return [p['name'] for p in self.PROVIDERS if self._api_keys.get(p['name'])]


class HybridSentimentAnalyzer:
    """
    Hybrid sentiment analyzer combining FinBERT and LLM.
    
    Strategy:
    1. All articles are analyzed with FinBERT (fast, free)
    2. High-importance articles also get LLM analysis
    3. Final score is weighted combination based on importance
    
    Importance Criteria (triggers LLM analysis):
    - Earnings announcements
    - M&A news
    - Executive changes
    - Major product launches
    - High uncertainty from FinBERT (confidence < 0.6)
    
    Example:
        analyzer = HybridSentimentAnalyzer(
            llm_api_key="sk-...",
            llm_provider="openai"
        )
        await analyzer.initialize()
        
        # Analyze article with metadata
        result = await analyzer.analyze(
            text="Apple acquires AI startup for $1B",
            is_high_importance=True
        )
    """
    
    # Categories that trigger LLM analysis
    HIGH_IMPORTANCE_CATEGORIES = {
        "earnings", "m&a", "merger_acquisition", "executive", "regulatory"
    }
    
    def __init__(
        self,
        llm_api_key: Optional[str] = None,
        llm_provider: str = "openai",
        llm_model: Optional[str] = None,
        finbert_device: str = "auto",
        finbert_confidence_threshold: float = 0.6,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        use_fallback_llm: bool = True,
    ):
        """
        Initialize hybrid analyzer.
        
        Args:
            llm_api_key: API key for LLM provider (deprecated, use openai_api_key/anthropic_api_key)
            llm_provider: LLM provider ("openai" or "anthropic") - only used if llm_api_key is set
            llm_model: Specific LLM model to use
            finbert_device: Device for FinBERT ("cpu", "cuda", "mps", "auto")
            finbert_confidence_threshold: Below this, also use LLM
            openai_api_key: OpenAI API key (loaded from Vault if not provided)
            anthropic_api_key: Anthropic API key (loaded from Vault if not provided)
            use_fallback_llm: If True, use LLMAnalyzerWithFallback (tries OpenAI then Anthropic)
        """
        self.finbert = FinBERTAnalyzer(device=finbert_device)
        
        # Use the new fallback analyzer by default
        if use_fallback_llm:
            # LLMAnalyzerWithFallback loads keys from Vault automatically
            self.llm = LLMAnalyzerWithFallback(
                openai_api_key=openai_api_key,
                anthropic_api_key=anthropic_api_key,
            )
        elif llm_api_key:
            # Legacy: single provider mode
            self.llm = LLMAnalyzer(
                api_key=llm_api_key,
                provider=llm_provider,
                model=llm_model
            )
        else:
            self.llm = None
        
        self.confidence_threshold = finbert_confidence_threshold
        self._initialized = False
    
    async def initialize(self):
        """Initialize models (load FinBERT)."""
        if not self._initialized:
            await self.finbert.load_model()
            self._initialized = True
    
    async def analyze(
        self,
        text: str,
        categories: Optional[List[str]] = None,
        is_high_importance: bool = False,
        use_llm: Optional[bool] = None,
    ) -> SentimentResult:
        """
        Analyze sentiment with hybrid approach.
        
        Args:
            text: Text to analyze
            categories: Article categories (used to determine importance)
            is_high_importance: Force high-importance analysis
            use_llm: Override automatic LLM decision
            
        Returns:
            Combined SentimentResult
        """
        await self.initialize()
        
        # Always run FinBERT first
        finbert_result = await self.finbert.analyze(text)
        
        # Determine if LLM analysis is needed
        should_use_llm = use_llm
        if should_use_llm is None:
            should_use_llm = self._should_use_llm(
                finbert_result, categories, is_high_importance
            )
        
        # If no LLM needed or not configured, return FinBERT result
        if not should_use_llm or self.llm is None:
            return finbert_result
        
        # Run LLM analysis
        try:
            llm_result = await self.llm.analyze(text)
            
            # Combine results (weight LLM more for high-importance)
            return self._combine_results(finbert_result, llm_result)
            
        except Exception as e:
            logger.error(f"LLM analysis failed, using FinBERT only: {e}")
            return finbert_result
    
    async def analyze_batch(
        self,
        texts: List[str],
        categories_list: Optional[List[List[str]]] = None,
        importance_flags: Optional[List[bool]] = None,
    ) -> List[SentimentResult]:
        """
        Analyze multiple texts with hybrid approach.
        
        Args:
            texts: List of texts to analyze
            categories_list: Categories for each text
            importance_flags: High-importance flag for each text
            
        Returns:
            List of SentimentResult objects
        """
        await self.initialize()
        
        # Run FinBERT on all texts
        finbert_results = await self.finbert.analyze_batch(texts)
        
        if self.llm is None:
            return finbert_results
        
        # Determine which need LLM analysis
        final_results = []
        llm_indices = []
        llm_texts = []
        
        for i, (text, finbert_result) in enumerate(zip(texts, finbert_results)):
            categories = categories_list[i] if categories_list else None
            is_important = importance_flags[i] if importance_flags else False
            
            if self._should_use_llm(finbert_result, categories, is_important):
                llm_indices.append(i)
                llm_texts.append(text)
        
        # Run LLM on selected texts
        if llm_texts:
            try:
                llm_results = await self.llm.analyze_batch(llm_texts)
            except Exception as e:
                logger.error(f"Batch LLM analysis failed: {e}")
                llm_results = [None] * len(llm_texts)
        else:
            llm_results = []
        
        # Combine results
        llm_idx = 0
        for i, finbert_result in enumerate(finbert_results):
            if i in llm_indices and llm_idx < len(llm_results):
                llm_result = llm_results[llm_idx]
                llm_idx += 1
                if llm_result:
                    final_results.append(self._combine_results(finbert_result, llm_result))
                else:
                    final_results.append(finbert_result)
            else:
                final_results.append(finbert_result)
        
        return final_results
    
    def _should_use_llm(
        self,
        finbert_result: SentimentResult,
        categories: Optional[List[str]],
        is_high_importance: bool,
    ) -> bool:
        """Determine if LLM analysis should be used."""
        # Explicit high importance
        if is_high_importance:
            return True
        
        # Low confidence from FinBERT
        if finbert_result.confidence < self.confidence_threshold:
            return True
        
        # High-importance category
        if categories:
            category_set = {c.lower() for c in categories}
            if category_set & self.HIGH_IMPORTANCE_CATEGORIES:
                return True
        
        return False
    
    def _combine_results(
        self,
        finbert_result: SentimentResult,
        llm_result: SentimentResult,
    ) -> SentimentResult:
        """
        Combine FinBERT and LLM results.
        
        Weighting:
        - LLM is weighted more heavily (0.7) as it's more accurate
        - FinBERT provides fast baseline (0.3)
        """
        llm_weight = 0.7
        finbert_weight = 0.3
        
        combined_score = (
            finbert_result.score * finbert_weight +
            llm_result.score * llm_weight
        )
        
        # Use higher confidence of the two
        combined_confidence = max(finbert_result.confidence, llm_result.confidence)
        
        return SentimentResult(
            score=round(combined_score, 4),
            label=SentimentLabel.from_score(combined_score),
            confidence=round(combined_confidence, 4),
            analyzer="hybrid",
            reasoning=llm_result.reasoning,
            aspects=llm_result.aspects,
        )

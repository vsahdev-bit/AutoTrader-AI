#!/usr/bin/env python3
"""
Connector Health Check Service
==============================

Scheduled service that runs health checks on different intervals:
- Data connectors: every 3 hours
- LLM connectors: every 6 hours (to minimize token costs)

Features:
1. Test connectivity for all data connectors
2. Test LLM provider connectivity with minimal token usage
3. Update status in PostgreSQL database
4. Store historical status for trending

This service provides the backend for the Connectors page in the web app.

Configuration:
- DATABASE_URL: PostgreSQL connection string
- VAULT_ADDR: Vault server address (default: http://localhost:8200)
- DATA_CONNECTOR_INTERVAL: Interval in seconds for data connectors (default: 10800 = 3 hours)
- LLM_CONNECTOR_INTERVAL: Interval in seconds for LLM connectors (default: 21600 = 6 hours)

Usage:
    python connector_health_service.py          # Run continuously
    python connector_health_service.py --once   # Run once and exit
"""

import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import asyncpg

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streaming'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def _load_env_file_if_present(path: str) -> None:
    """Best-effort .env loader.

    This repo stores local dev configuration in `api-gateway/.env`.
    When running this Python script directly (outside Docker), developers
    often won't have exported `DATABASE_URL`.

    We keep this intentionally lightweight (no python-dotenv dependency).
    Existing environment variables are never overridden.
    """
    try:
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Never fail startup due to optional env loading
        return


# Try to load local dev env defaults if the user hasn't exported them.
# (Most importantly: DATABASE_URL)
_load_env_file_if_present(os.path.join(os.path.dirname(__file__), '..', 'api-gateway', '.env'))
_load_env_file_if_present(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://autotrader:autotrader@localhost:5432/autotrader')
DATA_CONNECTOR_INTERVAL = int(os.getenv('DATA_CONNECTOR_INTERVAL', 10800))  # 3 hours
LLM_CONNECTOR_INTERVAL = int(os.getenv('LLM_CONNECTOR_INTERVAL', 21600))  # 6 hours

# Test symbol for connector checks
TEST_SYMBOL = "AAPL"


@dataclass
class ConnectorCheckResult:
    """Result of a connector health check."""
    connector_name: str
    status: str  # 'connected', 'disconnected', 'error', 'disabled'
    status_message: str
    articles_fetched: int = 0
    response_time_ms: int = 0
    error_message: Optional[str] = None
    has_api_key: bool = False


@dataclass
class LLMCheckResult:
    """Result of an LLM provider health check."""
    provider_name: str
    status: str  # 'connected', 'disconnected', 'error'
    status_message: str
    response_time_ms: int = 0
    error_message: Optional[str] = None
    has_api_key: bool = False


class ConnectorHealthService:
    """
    Service to check health of all data connectors and LLM providers.
    
    Data connectors run every 3 hours to:
    1. Test each connector by fetching sample data
    2. Update connector_status table with results
    3. Store history in connector_status_history table
    
    LLM connectors run every 6 hours to:
    1. Test each LLM provider with minimal token usage
    2. Update llm_connector_status table with results
    """
    
    CONNECTORS_CONFIG = [
        # Paid connectors (require API keys)
        {'name': 'polygon', 'module': 'streaming.connectors.polygon', 'class': 'PolygonConnector', 'needs_key': True},
        {'name': 'alpha_vantage', 'module': 'streaming.connectors.alpha_vantage', 'class': 'AlphaVantageConnector', 'needs_key': True},
        {'name': 'finnhub', 'module': 'streaming.connectors.finnhub', 'class': 'FinnhubConnector', 'needs_key': True},
        {'name': 'newsapi', 'module': 'streaming.connectors.newsapi', 'class': 'NewsAPIConnector', 'needs_key': True},
        {'name': 'benzinga', 'module': 'streaming.connectors.benzinga', 'class': 'BenzingaConnector', 'needs_key': True},
        {'name': 'fmp', 'module': 'streaming.connectors.financial_modeling_prep', 'class': 'FinancialModelingPrepConnector', 'needs_key': True},
        {'name': 'nasdaq_data_link', 'module': 'streaming.connectors.nasdaq_data_link', 'class': 'NasdaqDataLinkConnector', 'needs_key': True},
        {'name': 'iex_cloud', 'module': 'streaming.connectors.iex_cloud', 'class': 'IEXCloudConnector', 'needs_key': True, 'disabled': True},
        
        # Free connectors (no API keys required)
        {'name': 'yahoo_finance', 'module': 'streaming.connectors.yahoo_finance', 'class': 'YahooFinanceConnector', 'needs_key': False},
        {'name': 'rss_feeds', 'module': 'streaming.connectors.rss_feeds', 'class': 'RSSFeedConnector', 'needs_key': False},
        {'name': 'sec_edgar', 'module': 'streaming.connectors.sec_edgar', 'class': 'SECEdgarConnector', 'needs_key': False},
        {'name': 'tipranks', 'module': 'streaming.connectors.tipranks', 'class': 'TipRanksConnector', 'needs_key': False},
        
        # Social connectors (optional API key)
        {'name': 'stocktwits', 'module': 'streaming.connectors.stocktwits', 'class': 'StockTwitsConnector', 'needs_key': False},
    ]
    
    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url
        self.db_pool: Optional[asyncpg.Pool] = None
        self._running = False
    
    async def initialize(self):
        """Initialize database connection pool."""
        logger.info("Initializing Connector Health Service...")
        
        try:
            self.db_pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=5,
            )
            logger.info("Database connection pool created")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise
    
    async def close(self):
        """Close database connection pool."""
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Database connection pool closed")
    
    async def check_connector(self, config: Dict[str, Any]) -> ConnectorCheckResult:
        """
        Check health of a single connector.
        
        Args:
            config: Connector configuration dict
            
        Returns:
            ConnectorCheckResult with status and metrics
        """
        connector_name = config['name']
        
        # Check if disabled
        if config.get('disabled', False):
            return ConnectorCheckResult(
                connector_name=connector_name,
                status='disabled',
                status_message='Connector is disabled',
                has_api_key=False,
            )
        
        try:
            # Import connector class
            module = __import__(config['module'], fromlist=[config['class']])
            connector_class = getattr(module, config['class'])
            connector = connector_class()
            
            # Check API key if needed
            has_api_key = True
            if config['needs_key']:
                if hasattr(connector, '_ensure_api_key'):
                    await connector._ensure_api_key()
                has_api_key = bool(connector.api_key)
                
                if not has_api_key:
                    await connector.close()
                    return ConnectorCheckResult(
                        connector_name=connector_name,
                        status='disconnected',
                        status_message='No API key configured',
                        has_api_key=False,
                    )
            elif hasattr(connector, '_ensure_access_token'):
                # Optional auth (like StockTwits)
                await connector._ensure_access_token()
                has_api_key = bool(getattr(connector, 'access_token', None))
            
            # Test fetching data
            start_time = time.time()
            since = datetime.utcnow() - timedelta(days=7)
            
            try:
                articles = await connector.fetch_news(
                    symbols=[TEST_SYMBOL],
                    since=since,
                    limit=5
                )
                response_time_ms = int((time.time() - start_time) * 1000)
                
                await connector.close()
                
                return ConnectorCheckResult(
                    connector_name=connector_name,
                    status='connected',
                    status_message=f'Successfully fetched {len(articles)} articles',
                    articles_fetched=len(articles),
                    response_time_ms=response_time_ms,
                    has_api_key=has_api_key,
                )
                
            except Exception as e:
                response_time_ms = int((time.time() - start_time) * 1000)
                await connector.close()
                
                error_msg = str(e)[:500]  # Truncate long errors
                
                # Determine if it's a temporary error or configuration issue
                if '403' in error_msg or '401' in error_msg:
                    status = 'error'
                    status_message = 'Authentication failed'
                elif '429' in error_msg:
                    status = 'connected'  # Rate limited but working
                    status_message = 'Rate limited (connector is working)'
                else:
                    status = 'error'
                    status_message = 'Failed to fetch data'
                
                return ConnectorCheckResult(
                    connector_name=connector_name,
                    status=status,
                    status_message=status_message,
                    response_time_ms=response_time_ms,
                    error_message=error_msg,
                    has_api_key=has_api_key,
                )
                
        except ImportError as e:
            return ConnectorCheckResult(
                connector_name=connector_name,
                status='error',
                status_message='Module import failed',
                error_message=str(e)[:500],
            )
        except Exception as e:
            return ConnectorCheckResult(
                connector_name=connector_name,
                status='error',
                status_message='Unexpected error',
                error_message=str(e)[:500],
            )
    
    async def check_all_connectors(self) -> List[ConnectorCheckResult]:
        """Check all connectors and return results."""
        logger.info(f"Starting health check for {len(self.CONNECTORS_CONFIG)} connectors...")
        
        results = []
        for config in self.CONNECTORS_CONFIG:
            logger.info(f"Checking {config['name']}...")
            result = await self.check_connector(config)
            results.append(result)
            logger.info(f"  {config['name']}: {result.status} - {result.status_message}")
        
        return results
    
    # LLM Provider configuration
    LLM_PROVIDERS = [
        {'name': 'openai', 'display_name': 'OpenAI', 'model': 'gpt-4o-mini', 'tier': 'paid'},
        {'name': 'anthropic', 'display_name': 'Anthropic', 'model': 'claude-3-haiku-20240307', 'tier': 'paid'},
        {'name': 'groq', 'display_name': 'Groq', 'model': 'llama-3.1-8b-instant', 'tier': 'free'},
    ]
    
    async def check_llm_provider(self, provider: Dict[str, Any]) -> LLMCheckResult:
        """
        Check health of a single LLM provider.
        
        Args:
            provider: LLM provider configuration dict
            
        Returns:
            LLMCheckResult with status and metrics
        """
        provider_name = provider['name']
        
        try:
            # Load API key from Vault
            from vault_client import get_api_key
            api_key = await get_api_key(provider_name)
            
            if not api_key:
                return LLMCheckResult(
                    provider_name=provider_name,
                    status='disconnected',
                    status_message='No API key configured',
                    has_api_key=False,
                )
            
            # Test the LLM with a minimal prompt to reduce token cost
            # Using single word prompt + max_tokens=1 for minimal API cost
            start_time = time.time()
            test_prompt = "Hi"
            
            if provider_name == 'openai':
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=api_key)
                response = await client.chat.completions.create(
                    model=provider['model'],
                    messages=[{"role": "user", "content": test_prompt}],
                    max_tokens=1,
                )
                _ = response.choices[0].message.content
                
            elif provider_name == 'anthropic':
                from anthropic import AsyncAnthropic
                client = AsyncAnthropic(api_key=api_key)
                response = await client.messages.create(
                    model=provider['model'],
                    max_tokens=1,
                    messages=[{"role": "user", "content": test_prompt}],
                )
                _ = response.content[0].text
                
            elif provider_name == 'groq':
                from groq import AsyncGroq
                client = AsyncGroq(api_key=api_key)
                response = await client.chat.completions.create(
                    model=provider['model'],
                    messages=[{"role": "user", "content": test_prompt}],
                    max_tokens=1,
                )
                _ = response.choices[0].message.content
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return LLMCheckResult(
                provider_name=provider_name,
                status='connected',
                status_message=f'Successfully connected ({response_time_ms}ms)',
                response_time_ms=response_time_ms,
                has_api_key=True,
            )
            
        except ImportError as e:
            return LLMCheckResult(
                provider_name=provider_name,
                status='error',
                status_message='SDK not installed',
                error_message=str(e)[:200],
                has_api_key=True,
            )
        except Exception as e:
            error_msg = str(e)[:200]
            
            # Determine status based on error type
            if '401' in error_msg or 'invalid_api_key' in error_msg.lower():
                status = 'error'
                status_message = 'Invalid API key'
            elif '429' in error_msg or 'rate' in error_msg.lower():
                status = 'connected'  # Rate limited but working
                status_message = 'Rate limited (provider is working)'
            else:
                status = 'error'
                status_message = 'Connection failed'
            
            return LLMCheckResult(
                provider_name=provider_name,
                status=status,
                status_message=status_message,
                error_message=error_msg,
                has_api_key=True,
            )
    
    async def check_all_llm_providers(self) -> List[LLMCheckResult]:
        """Check all LLM providers and return results."""
        logger.info(f"Starting health check for {len(self.LLM_PROVIDERS)} LLM providers...")
        
        results = []
        for provider in self.LLM_PROVIDERS:
            logger.info(f"Checking LLM provider {provider['name']}...")
            result = await self.check_llm_provider(provider)
            results.append(result)
            logger.info(f"  {provider['name']}: {result.status} - {result.status_message}")
        
        return results
    
    async def save_llm_results(self, results: List[LLMCheckResult]):
        """Save LLM check results to database."""
        now = datetime.utcnow()
        
        async with self.db_pool.acquire() as conn:
            for result in results:
                if result.status == 'connected':
                    await conn.execute("""
                        UPDATE llm_connector_status SET
                            status = $2::varchar,
                            status_message = $3,
                            last_check_at = $4,
                            last_success_at = $4,
                            response_time_ms = $5,
                            has_api_key = $6
                        WHERE provider_name = $1
                    """, 
                        result.provider_name,
                        result.status,
                        result.status_message,
                        now,
                        result.response_time_ms,
                        result.has_api_key,
                    )
                else:
                    await conn.execute("""
                        UPDATE llm_connector_status SET
                            status = $2::varchar,
                            status_message = $3,
                            last_check_at = $4,
                            last_error_at = $4,
                            last_error_message = $5,
                            response_time_ms = $6,
                            has_api_key = $7
                        WHERE provider_name = $1
                    """, 
                        result.provider_name,
                        result.status,
                        result.status_message,
                        now,
                        result.error_message,
                        result.response_time_ms,
                        result.has_api_key,
                    )
        
        logger.info(f"Saved {len(results)} LLM provider status results to database")
    
    async def save_results(self, results: List[ConnectorCheckResult]):
        """Save check results to database."""
        now = datetime.utcnow()
        
        async with self.db_pool.acquire() as conn:
            for result in results:
                # Update main status table
                # Use separate queries to avoid parameter type ambiguity
                if result.status == 'connected':
                    await conn.execute("""
                        UPDATE connector_status SET
                            status = $2::varchar,
                            status_message = $3,
                            last_check_at = $4,
                            last_success_at = $4,
                            articles_fetched = $5,
                            response_time_ms = $6,
                            has_api_key = $7
                        WHERE connector_name = $1
                    """, 
                        result.connector_name,
                        result.status,
                        result.status_message,
                        now,
                        result.articles_fetched,
                        result.response_time_ms,
                        result.has_api_key,
                    )
                else:
                    await conn.execute("""
                        UPDATE connector_status SET
                            status = $2::varchar,
                            status_message = $3,
                            last_check_at = $4,
                            last_error_at = $4,
                            last_error_message = $5,
                            articles_fetched = $6,
                            response_time_ms = $7,
                            has_api_key = $8
                        WHERE connector_name = $1
                    """, 
                        result.connector_name,
                        result.status,
                        result.status_message,
                        now,
                        result.error_message,
                        result.articles_fetched,
                        result.response_time_ms,
                        result.has_api_key,
                    )
                
                # Insert into history
                await conn.execute("""
                    INSERT INTO connector_status_history 
                        (connector_name, status, status_message, articles_fetched, response_time_ms, error_message, checked_at)
                    VALUES ($1, $2::varchar, $3, $4, $5, $6, $7)
                """,
                    result.connector_name,
                    result.status,
                    result.status_message,
                    result.articles_fetched,
                    result.response_time_ms,
                    result.error_message,
                    now,
                )
            
            # Cleanup old history
            await conn.execute("""
                DELETE FROM connector_status_history
                WHERE checked_at < NOW() - INTERVAL '7 days'
            """)
        
        logger.info(f"Saved {len(results)} connector status results to database")
    
    async def run_once(self) -> Dict[str, Any]:
        """Run a single health check cycle for both data connectors and LLM providers."""
        start_time = datetime.utcnow()
        
        # Check data connectors
        results = await self.check_all_connectors()
        await self.save_results(results)
        
        # Check LLM providers
        llm_results = await self.check_all_llm_providers()
        await self.save_llm_results(llm_results)
        
        # Summary for data connectors
        connected = sum(1 for r in results if r.status == 'connected')
        disconnected = sum(1 for r in results if r.status == 'disconnected')
        errors = sum(1 for r in results if r.status == 'error')
        disabled = sum(1 for r in results if r.status == 'disabled')
        
        # Summary for LLM providers
        llm_connected = sum(1 for r in llm_results if r.status == 'connected')
        llm_disconnected = sum(1 for r in llm_results if r.status == 'disconnected')
        llm_errors = sum(1 for r in llm_results if r.status == 'error')
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"Health check completed in {duration:.1f}s")
        logger.info(f"Data Connectors: {connected} connected, {disconnected} disconnected, {errors} errors, {disabled} disabled")
        logger.info(f"LLM Providers: {llm_connected} connected, {llm_disconnected} disconnected, {llm_errors} errors")
        
        return {
            'timestamp': start_time.isoformat(),
            'duration_seconds': duration,
            'data_connectors': {
                'connected': connected,
                'disconnected': disconnected,
                'errors': errors,
                'disabled': disabled,
                'total': len(results),
            },
            'llm_providers': {
                'connected': llm_connected,
                'disconnected': llm_disconnected,
                'errors': llm_errors,
                'total': len(llm_results),
            },
        }
    
    async def is_health_check_enabled(self, setting_key: str) -> bool:
        """Check if health check is enabled for the given setting key.
        
        Args:
            setting_key: 'data_connectors_health_check' or 'llm_connectors_health_check'
            
        Returns:
            True if enabled, False otherwise. Defaults to True if setting not found.
        """
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT enabled FROM health_check_settings WHERE setting_key = $1",
                    setting_key
                )
                if row:
                    return row['enabled']
                return True  # Default to enabled if not found
        except Exception as e:
            logger.warning(f"Error checking health check setting {setting_key}: {e}, defaulting to enabled")
            return True
    
    async def run_data_connectors_loop(self):
        """Run data connector health checks on their own schedule (every 3 hours)."""
        logger.info(f"Starting data connector health checks (interval: {DATA_CONNECTOR_INTERVAL}s / {DATA_CONNECTOR_INTERVAL/3600:.1f} hours)")
        
        while self._running:
            try:
                # Check if health check is enabled
                enabled = await self.is_health_check_enabled('data_connectors_health_check')
                
                if enabled:
                    logger.info("Running data connector health check...")
                    results = await self.check_all_connectors()
                    await self.save_results(results)
                    
                    connected = sum(1 for r in results if r.status == 'connected')
                    logger.info(f"Data Connectors: {connected}/{len(results)} connected")
                else:
                    logger.info("Data connector health check is DISABLED, skipping...")
                
                logger.info(f"Next data connector check in {DATA_CONNECTOR_INTERVAL/3600:.1f} hours")
                
                # Sleep using wall-clock time to handle system sleep/suspend correctly
                sleep_interval = 300  # 5 minutes
                start_time = time.time()
                target_time = start_time + DATA_CONNECTOR_INTERVAL
                
                while time.time() < target_time and self._running:
                    remaining_seconds = target_time - time.time()
                    if remaining_seconds <= 0:
                        break
                    sleep_time = min(sleep_interval, remaining_seconds)
                    await asyncio.sleep(sleep_time)
                    remaining_seconds = target_time - time.time()
                    if remaining_seconds > 0 and self._running:
                        logger.debug(f"Data connector health check: {remaining_seconds/3600:.1f} hours until next check")
                
            except asyncio.CancelledError:
                logger.info("Data connector health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in data connector health check: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def run_llm_connectors_loop(self):
        """Run LLM connector health checks on their own schedule (every 6 hours)."""
        logger.info(f"Starting LLM connector health checks (interval: {LLM_CONNECTOR_INTERVAL}s / {LLM_CONNECTOR_INTERVAL/3600:.1f} hours)")
        
        while self._running:
            try:
                # Check if health check is enabled
                enabled = await self.is_health_check_enabled('llm_connectors_health_check')
                
                if enabled:
                    logger.info("Running LLM connector health check...")
                    llm_results = await self.check_all_llm_providers()
                    await self.save_llm_results(llm_results)
                    
                    connected = sum(1 for r in llm_results if r.status == 'connected')
                    logger.info(f"LLM Providers: {connected}/{len(llm_results)} connected")
                else:
                    logger.info("LLM connector health check is DISABLED, skipping...")
                
                logger.info(f"Next LLM connector check in {LLM_CONNECTOR_INTERVAL/3600:.1f} hours")
                
                # Sleep using wall-clock time to handle system sleep/suspend correctly
                sleep_interval = 300  # 5 minutes
                start_time = time.time()
                target_time = start_time + LLM_CONNECTOR_INTERVAL
                
                while time.time() < target_time and self._running:
                    remaining_seconds = target_time - time.time()
                    if remaining_seconds <= 0:
                        break
                    sleep_time = min(sleep_interval, remaining_seconds)
                    await asyncio.sleep(sleep_time)
                    remaining_seconds = target_time - time.time()
                    if remaining_seconds > 0 and self._running:
                        logger.debug(f"LLM connector health check: {remaining_seconds/3600:.1f} hours until next check")
                
            except asyncio.CancelledError:
                logger.info("LLM connector health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in LLM connector health check: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _heartbeat_loop(self):
        """Log periodic heartbeat to show the service is alive."""
        heartbeat_interval = 3600  # Log every hour
        while self._running:
            try:
                await asyncio.sleep(heartbeat_interval)
                if self._running:
                    logger.info("💓 Health check service heartbeat - service is running")
            except asyncio.CancelledError:
                break
    
    async def start_scheduled(self):
        """Start the scheduled health check loops with separate intervals."""
        self._running = True
        logger.info(f"Starting scheduled health checks:")
        logger.info(f"  - Data connectors: every {DATA_CONNECTOR_INTERVAL/3600:.1f} hours")
        logger.info(f"  - LLM connectors: every {LLM_CONNECTOR_INTERVAL/3600:.1f} hours")
        logger.info(f"  - Heartbeat: every 1 hour")
        
        # Run all loops concurrently
        await asyncio.gather(
            self.run_data_connectors_loop(),
            self.run_llm_connectors_loop(),
            self._heartbeat_loop(),
            return_exceptions=True,  # Don't let one failing loop crash others
        )
    
    def stop(self):
        """Stop the scheduled loop."""
        self._running = False
        logger.info("Stopping health check service")


async def main(run_once: bool = False, data_only: bool = False, llm_only: bool = False):
    """Main entry point."""
    service = ConnectorHealthService()

    # Set up signal handlers for graceful shutdown
    def handle_signal(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} signal, initiating graceful shutdown...")
        service.stop()

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        await service.initialize()

        if run_once:
            start_time = datetime.utcnow()

            results: List[ConnectorCheckResult] = []
            llm_results: List[LLMCheckResult] = []

            if not llm_only:
                # Check data connectors
                results = await service.check_all_connectors()
                await service.save_results(results)

            if not data_only:
                # Check LLM providers
                llm_results = await service.check_all_llm_providers()
                await service.save_llm_results(llm_results)

            # Summary
            connected = sum(1 for r in results if r.status == 'connected')
            disconnected = sum(1 for r in results if r.status == 'disconnected')
            errors = sum(1 for r in results if r.status == 'error')
            disabled = sum(1 for r in results if r.status == 'disabled')

            llm_connected = sum(1 for r in llm_results if r.status == 'connected')
            llm_disconnected = sum(1 for r in llm_results if r.status == 'disconnected')
            llm_errors = sum(1 for r in llm_results if r.status == 'error')

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = {
                'timestamp': start_time.isoformat(),
                'duration_seconds': duration,
                'data_connectors': {
                    'connected': connected,
                    'disconnected': disconnected,
                    'errors': errors,
                    'disabled': disabled,
                    'total': len(results),
                },
                'llm_providers': {
                    'connected': llm_connected,
                    'disconnected': llm_disconnected,
                    'errors': llm_errors,
                    'total': len(llm_results),
                },
            }

            print(f"\n✅ Health check complete:")
            if not llm_only:
                data_conn = result.get('data_connectors', {})
                print(f"   Data Connectors: {data_conn.get('connected', 0)}/{data_conn.get('total', 0)} connected")
            if not data_only:
                llm_conn = result.get('llm_providers', {})
                print(f"   LLM Providers: {llm_conn.get('connected', 0)}/{llm_conn.get('total', 0)} connected")
        else:
            logger.info("Health check service starting in scheduled mode...")
            await service.start_scheduled()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
    finally:
        service.stop()
        await service.close()
        logger.info("Health check service shutdown complete")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Connector Health Check Service')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--data-only', action='store_true', help='Only check data connectors (skip LLM providers)')
    parser.add_argument('--llm-only', action='store_true', help='Only check LLM providers (skip data connectors)')
    args = parser.parse_args()

    if args.data_only and args.llm_only:
        raise SystemExit("--data-only and --llm-only are mutually exclusive")

    asyncio.run(main(run_once=args.once, data_only=args.data_only, llm_only=args.llm_only))

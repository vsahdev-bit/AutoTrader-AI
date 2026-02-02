"""
Vault Client for ML Services
============================

Python client for retrieving secrets from HashiCorp Vault.
Mirrors the functionality in api-gateway/src/vault.js for
consistency across the platform.

Configuration:
- VAULT_ADDR: Vault server address (default: http://localhost:8200)
- VAULT_TOKEN: Vault authentication token (default: dev-root-token)

The secrets are stored in the KV v2 secrets engine at:
- secret/data/autotrader/config/{key} - API keys and configuration
"""

import os
import logging
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger(__name__)

# Vault configuration (matching api-gateway/src/vault.js)
VAULT_ADDR = os.getenv('VAULT_ADDR', 'http://localhost:8200')
VAULT_TOKEN = os.getenv('VAULT_TOKEN', 'dev-root-token')
SECRETS_PATH = 'secret/data/autotrader'  # KV v2 secrets engine


class VaultClient:
    """
    Async client for HashiCorp Vault KV v2 secrets engine.
    
    Example Usage:
        client = VaultClient()
        
        # Store a secret
        await client.store_secret('polygon', {'api_key': 'your_key'})
        
        # Retrieve a secret
        secret = await client.get_secret('polygon')
        api_key = secret['api_key']
        
        # Get specific API key
        polygon_key = await client.get_api_key('polygon')
    """
    
    def __init__(
        self,
        vault_addr: Optional[str] = None,
        vault_token: Optional[str] = None,
    ):
        """
        Initialize the Vault client.
        
        Args:
            vault_addr: Vault server address (or use VAULT_ADDR env var)
            vault_token: Vault authentication token (or use VAULT_TOKEN env var)
        """
        self.vault_addr = vault_addr or VAULT_ADDR
        self.vault_token = vault_token or VAULT_TOKEN
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={'X-Vault-Token': self.vault_token}
            )
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def store_secret(self, key: str, value: Dict[str, Any]) -> bool:
        """
        Store a secret in Vault.
        
        Args:
            key: Secret key name (e.g., 'polygon', 'iex_cloud')
            value: Secret value(s) as a dictionary
            
        Returns:
            True if successful
        """
        url = f"{self.vault_addr}/v1/{SECRETS_PATH}/config/{key}"
        session = await self._get_session()
        
        try:
            async with session.post(url, json={'data': value}) as response:
                if response.status in (200, 204):
                    logger.info(f"✅ Stored secret '{key}' in Vault")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to store secret '{key}': {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error storing secret '{key}' in Vault: {e}")
            raise
    
    async def get_secret(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a secret from Vault.
        
        Args:
            key: Secret key name (e.g., 'polygon', 'iex_cloud')
            
        Returns:
            Secret value(s) as a dictionary, or None if not found
        """
        url = f"{self.vault_addr}/v1/{SECRETS_PATH}/config/{key}"
        session = await self._get_session()
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    # KV v2 returns data nested under data.data
                    return result.get('data', {}).get('data')
                elif response.status == 404:
                    logger.debug(f"Secret '{key}' not found in Vault")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to retrieve secret '{key}': {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error retrieving secret '{key}' from Vault: {e}")
            return None
    
    async def get_api_key(self, provider: str) -> Optional[str]:
        """
        Get an API key for a specific provider.
        
        Convenience method that retrieves the 'api_key' field from a provider's secret.
        
        Args:
            provider: Provider name (e.g., 'polygon', 'iex_cloud', 'alpha_vantage')
            
        Returns:
            API key string, or None if not found
        """
        secret = await self.get_secret(provider)
        if secret:
            return secret.get('api_key')
        return None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check Vault health status.
        
        Returns:
            Dictionary with health information
        """
        url = f"{self.vault_addr}/v1/sys/health"
        session = await self._get_session()
        
        try:
            async with session.get(url) as response:
                if response.status in (200, 429, 472, 473, 501, 503):
                    health = await response.json()
                    return {
                        'healthy': not health.get('sealed', True),
                        'initialized': health.get('initialized', False),
                        'sealed': health.get('sealed', True),
                        'version': health.get('version'),
                    }
                else:
                    return {
                        'healthy': False,
                        'error': f"Unexpected status: {response.status}",
                    }
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
            }


# Singleton instance for convenience
_vault_client: Optional[VaultClient] = None


async def get_vault_client() -> VaultClient:
    """Get or create the singleton Vault client instance."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client


async def get_api_key(provider: str) -> Optional[str]:
    """Convenience function to get an API key from Vault.

    Falls back to environment variable if Vault is unavailable.

    NOTE: This function uses a singleton VaultClient which maintains an
    aiohttp session. We explicitly close it after each call to avoid
    "Unclosed client session" warnings in short-lived scripts (like
    `connector_health_service.py --once`).

    Args:
        provider: Provider name (e.g., 'polygon', 'iex_cloud')

    Returns:
        API key string, or None if not found
    """
    # Map provider names to environment variable names
    env_var_map = {
        'polygon': 'POLYGON_API_KEY',
        'iex_cloud': 'IEX_CLOUD_API_KEY',
        'alpha_vantage': 'ALPHA_VANTAGE_API_KEY',
        'nasdaq_data_link': 'NASDAQ_DATA_LINK_API_KEY',
        'finnhub': 'FINNHUB_API_KEY',
        'newsapi': 'NEWSAPI_API_KEY',
    }

    client: Optional[VaultClient] = None

    # Try Vault first
    try:
        client = await get_vault_client()
        api_key = await client.get_api_key(provider)
        if api_key:
            logger.debug(f"Retrieved {provider} API key from Vault")
            return api_key
    except Exception as e:
        logger.warning(f"Could not retrieve {provider} API key from Vault: {e}")
    finally:
        # Best-effort cleanup for short-lived processes
        try:
            if client is not None:
                await client.close()
        except Exception:
            pass

    # Fall back to environment variable
    env_var = env_var_map.get(provider, f"{provider.upper()}_API_KEY")
    api_key = os.getenv(env_var)
    if api_key:
        logger.debug(f"Using {provider} API key from environment variable {env_var}")
    return api_key

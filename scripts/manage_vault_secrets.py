#!/usr/bin/env python3
"""
Vault Secrets Management Script
===============================

Script to manage API keys and secrets in HashiCorp Vault for the AutoTrader AI platform.

Usage:
    # Store a secret
    python scripts/manage_vault_secrets.py store polygon --api-key "your_api_key"
    
    # Retrieve a secret
    python scripts/manage_vault_secrets.py get polygon
    
    # List all stored API keys
    python scripts/manage_vault_secrets.py list
    
    # Check Vault health
    python scripts/manage_vault_secrets.py health

Environment Variables:
    VAULT_ADDR: Vault server address (default: http://localhost:8200)
    VAULT_TOKEN: Vault authentication token (default: dev-root-token)

Supported Providers:
    - polygon: Polygon.io market data
    - iex_cloud: IEX Cloud market data
    - alpha_vantage: Alpha Vantage news & sentiment
    - nasdaq_data_link: Nasdaq Data Link (formerly Quandl)
    - finnhub: Finnhub financial data
    - newsapi: NewsAPI news aggregation
"""

import argparse
import asyncio
import sys
import os

# Add ml-services to path for vault_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ml-services'))

from vault_client import VaultClient


SUPPORTED_PROVIDERS = [
    'polygon',
    'iex_cloud', 
    'alpha_vantage',
    'nasdaq_data_link',
    'finnhub',
    'newsapi',
    'benzinga',
    'twitter',
    'reddit',
    'stocktwits',
    'fmp',
    # LLM Providers (in fallback order)
    'openai',      # Primary - paid
    'anthropic',   # Fallback 1 - paid
    'groq',        # Fallback 2 - free tier available
]


async def store_secret(provider: str, api_key: str, extra_data: dict = None):
    """Store an API key in Vault."""
    if provider not in SUPPORTED_PROVIDERS:
        print(f"❌ Unknown provider: {provider}")
        print(f"   Supported providers: {', '.join(SUPPORTED_PROVIDERS)}")
        return False
    
    client = VaultClient()
    try:
        data = {'api_key': api_key}
        if extra_data:
            data.update(extra_data)
        
        success = await client.store_secret(provider, data)
        if success:
            print(f"✅ Successfully stored {provider} API key in Vault")
            # Mask the key for display
            masked_key = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else '****'
            print(f"   Key: {masked_key}")
        return success
    finally:
        await client.close()


async def get_secret(provider: str):
    """Retrieve an API key from Vault."""
    client = VaultClient()
    try:
        secret = await client.get_secret(provider)
        if secret:
            api_key = secret.get('api_key', '')
            # Mask the key for display
            masked_key = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else '****'
            print(f"✅ Found {provider} secret in Vault")
            print(f"   API Key: {masked_key}")
            # Show other fields if present
            for key, value in secret.items():
                if key != 'api_key':
                    print(f"   {key}: {value}")
        else:
            print(f"❌ No secret found for {provider} in Vault")
        return secret
    finally:
        await client.close()


async def list_secrets():
    """List all stored API keys (checks each provider)."""
    client = VaultClient()
    try:
        print("Checking Vault for stored API keys...\n")
        found = []
        missing = []
        
        for provider in SUPPORTED_PROVIDERS:
            secret = await client.get_secret(provider)
            if secret and secret.get('api_key'):
                api_key = secret['api_key']
                masked_key = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else '****'
                found.append((provider, masked_key))
            else:
                missing.append(provider)
        
        if found:
            print("✅ Configured API keys:")
            for provider, masked_key in found:
                print(f"   - {provider}: {masked_key}")
        
        if missing:
            print("\n❌ Missing API keys:")
            for provider in missing:
                print(f"   - {provider}")
        
        print(f"\nTotal: {len(found)} configured, {len(missing)} missing")
        return found, missing
    finally:
        await client.close()


async def check_health():
    """Check Vault health status."""
    client = VaultClient()
    try:
        health = await client.health_check()
        
        if health.get('healthy'):
            print("✅ Vault is healthy")
            print(f"   Version: {health.get('version', 'unknown')}")
            print(f"   Initialized: {health.get('initialized', False)}")
            print(f"   Sealed: {health.get('sealed', True)}")
        else:
            print("❌ Vault is not healthy")
            if health.get('error'):
                print(f"   Error: {health['error']}")
        
        return health
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(
        description='Manage API keys in HashiCorp Vault',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Store command
    store_parser = subparsers.add_parser('store', help='Store an API key in Vault')
    store_parser.add_argument('provider', choices=SUPPORTED_PROVIDERS, help='Provider name')
    store_parser.add_argument('--api-key', '-k', required=True, help='API key to store')
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Retrieve an API key from Vault')
    get_parser.add_argument('provider', help='Provider name')
    
    # List command
    subparsers.add_parser('list', help='List all stored API keys')
    
    # Health command
    subparsers.add_parser('health', help='Check Vault health')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Run the appropriate async function
    if args.command == 'store':
        asyncio.run(store_secret(args.provider, args.api_key))
    elif args.command == 'get':
        asyncio.run(get_secret(args.provider))
    elif args.command == 'list':
        asyncio.run(list_secrets())
    elif args.command == 'health':
        asyncio.run(check_health())


if __name__ == '__main__':
    main()

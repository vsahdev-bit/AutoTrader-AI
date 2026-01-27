#!/bin/bash
# Start Jim Cramer Service with API keys from Vault
# This script retrieves the GROQ API key from Vault and starts the service

set -e

echo "=============================================="
echo "Starting Jim Cramer Service"
echo "=============================================="

# Get GROQ API key from Vault
echo "Retrieving GROQ API key from Vault..."
GROQ_API_KEY=$(docker exec autotrader-vault sh -c 'VAULT_TOKEN=dev-root-token vault kv get -field=api_key secret/autotrader/config/groq' 2>/dev/null)

if [ -z "$GROQ_API_KEY" ]; then
    echo "ERROR: Could not retrieve GROQ API key from Vault"
    exit 1
fi

echo "✓ GROQ API key retrieved"

# Export for docker-compose
export GROQ_API_KEY

# Build and start the jim-cramer-service
echo "Building and starting Jim Cramer service..."
cd infrastructure/docker
docker-compose up -d --build jim-cramer-service

echo ""
echo "=============================================="
echo "Jim Cramer Service Started!"
echo "=============================================="
echo "• Runs daily at 9:00 AM PST (17:00 UTC)"
echo "• View logs: docker logs -f autotrader-jim-cramer"
echo "• View results: http://localhost:5173/jim-cramer-advice"
echo "=============================================="

#!/bin/bash
set -e

echo "Running PostgreSQL migrations..."
docker exec -i autotrader-postgres psql -U autotrader -d autotrader < V1__initial_schema.sql
echo "✅ Migrations completed"

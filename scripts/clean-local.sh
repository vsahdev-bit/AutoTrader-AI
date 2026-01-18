#!/bin/bash
echo "🧹 Cleaning AutoTrader AI local environment..."
cd ../infrastructure/docker
docker-compose down -v
echo "✅ All data cleaned"

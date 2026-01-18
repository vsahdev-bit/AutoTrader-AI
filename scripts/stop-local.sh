#!/bin/bash
echo "🛑 Stopping AutoTrader AI services..."
cd ../infrastructure/docker
docker-compose down
echo "✅ All services stopped"

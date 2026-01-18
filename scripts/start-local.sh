#!/bin/bash
set -e

echo "🚀 Starting AutoTrader AI Local Development Environment..."

# Start infrastructure
echo "📦 Starting Docker containers..."
cd ../infrastructure/docker
docker-compose up -d

echo "⏳ Waiting for services to be healthy..."
sleep 10

# Run database migrations
echo "🗄️  Running database migrations..."
cd ../../database/postgres
./migrate.sh

echo "✅ Infrastructure ready!"
echo ""
echo "Services running:"
echo "  PostgreSQL: localhost:5432"
echo "  Redis: localhost:6379"
echo "  Kafka: localhost:9092"
echo "  ClickHouse: localhost:8123"
echo "  Vault: localhost:8200"
echo ""
echo "Next steps:"
echo "  1. Start backend services: cd services && mvn spring-boot:run -pl auth-service"
echo "  2. Start ML services: cd ml-services && python -m recommendation_engine.src.main"
echo "  3. Start frontend: cd web-app && npm run dev"

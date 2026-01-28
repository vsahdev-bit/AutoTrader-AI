#!/bin/bash
set -e

echo "Starting AutoTrader AI Local Development Environment..."

# Prefer `docker compose` (plugin). Fall back to legacy `docker-compose`.
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "ERROR: Neither 'docker compose' nor 'docker-compose' is available."
  echo "Install Docker Desktop / Docker Engine with the compose plugin."
  exit 1
fi

echo "Starting Docker Compose stack..."
(
  cd infrastructure/docker
  "${COMPOSE_CMD[@]}" up -d --build
)

echo "Waiting briefly for services to become ready..."
sleep 10

echo "Running PostgreSQL migrations..."
(
  cd database/postgres
  ./migrate.sh
)

echo "✅ Local environment started."
echo ""
echo "Service URLs:"
echo "  Web App:               http://localhost:5173"
echo "  API Gateway:           http://localhost:3001  (health: /health)"
echo "  Recommendation Engine: http://localhost:8000  (health: /health)"
echo "  PostgreSQL:            localhost:5432"
echo "  Redis:                 localhost:6379"
echo "  Kafka:                 localhost:9092"
echo "  ClickHouse:            http://localhost:8123"
echo "  Vault:                 http://localhost:8200"
echo ""
echo "Logs:"
echo "  ${COMPOSE_CMD[*]} -f infrastructure/docker/docker-compose.yml logs -f [service]"

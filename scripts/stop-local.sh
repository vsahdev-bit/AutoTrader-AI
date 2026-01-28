#!/bin/bash
set -e

echo "Stopping AutoTrader AI services..."

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "ERROR: Neither 'docker compose' nor 'docker-compose' is available."
  exit 1
fi

(
  cd infrastructure/docker
  "${COMPOSE_CMD[@]}" down
)

echo "✅ All services stopped"

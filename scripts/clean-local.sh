#!/bin/bash
set -e

echo "Cleaning AutoTrader AI local environment (this deletes volumes/data)..."

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
  "${COMPOSE_CMD[@]}" down -v
)

echo "✅ All data cleaned"

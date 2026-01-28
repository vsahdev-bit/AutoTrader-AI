#!/bin/bash
set -e

echo "AutoTrader AI - Local Status"

echo ""
# Prefer `docker compose` (plugin). Fall back to legacy `docker-compose`.
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "ERROR: Neither 'docker compose' nor 'docker-compose' is available."
  exit 1
fi

COMPOSE_FILE="infrastructure/docker/docker-compose.yml"

echo "Compose services:"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" ps

echo ""
echo "Health checks:"

check_url() {
  name="$1"
  url="$2"
  if curl -sS -m 3 -o /dev/null -I "$url"; then
    echo "  OK   $name -> $url"
  else
    echo "  FAIL $name -> $url"
  fi
}

check_url "Web App" "http://localhost:5173/"
check_url "API Gateway" "http://localhost:3001/health"
check_url "Recommendation Engine" "http://localhost:8000/health"
check_url "Vault" "http://localhost:8200/v1/sys/health"
check_url "ClickHouse" "http://localhost:8123/ping"

echo ""
echo "Tip: view logs with: ${COMPOSE_CMD[*]} -f $COMPOSE_FILE logs -f <service>"

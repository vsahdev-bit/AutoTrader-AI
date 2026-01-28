#!/bin/bash
set -e

echo "Starting AutoTrader AI Local Development Environment..."

# Optional flags
CLEAN=false
for arg in "$@"; do
  case "$arg" in
    --clean)
      CLEAN=true
      ;;
  esac
done

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

echo "Syncing repo (main)... (best-effort)"
# Best-effort: only pull if we're in a git repo with origin configured
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git fetch origin main >/dev/null 2>&1 || true
  git checkout main >/dev/null 2>&1 || true
  git pull origin main || true
fi

echo "Starting Docker Compose stack..."
if [ "$CLEAN" = true ]; then
  echo "WARNING: --clean requested; stopping stack and removing volumes (data will be lost)"
  (
    cd infrastructure/docker
    "${COMPOSE_CMD[@]}" down -v
  )
fi

(
  cd infrastructure/docker
  "${COMPOSE_CMD[@]}" up -d --build
)

echo "Waiting for Vault bootstrap (init/unseal) to complete..."
# vault-bootstrap is one-shot; wait up to 2 minutes
for i in $(seq 1 120); do
  # container may not exist the very first second; ignore errors
  status=$("${COMPOSE_CMD[@]}" -f infrastructure/docker/docker-compose.yml ps -q vault-bootstrap 2>/dev/null | xargs -I{} docker inspect -f '{{.State.Status}}' {} 2>/dev/null || true)
  if [ "$status" = "exited" ]; then
    exit_code=$("${COMPOSE_CMD[@]}" -f infrastructure/docker/docker-compose.yml ps -q vault-bootstrap 2>/dev/null | xargs -I{} docker inspect -f '{{.State.ExitCode}}' {} 2>/dev/null || echo "")
    if [ "$exit_code" = "0" ]; then
      echo "Vault bootstrap completed"
      break
    else
      echo "ERROR: vault-bootstrap exited non-zero (ExitCode=$exit_code)."
      echo "Check: ${COMPOSE_CMD[*]} -f infrastructure/docker/docker-compose.yml logs vault-bootstrap"
      break
    fi
  fi
  sleep 1
  if [ "$i" = "120" ]; then
    echo "WARNING: vault-bootstrap did not finish within timeout."
    echo "Check: ${COMPOSE_CMD[*]} -f infrastructure/docker/docker-compose.yml logs vault-bootstrap"
  fi
done

echo "Waiting briefly for services to become ready..."
sleep 5

# Optional: restart news-ingestion after vault bootstrap so it can read secrets
echo "Restarting news-ingestion to pick up Vault token/secrets..."
(
  cd infrastructure/docker
  "${COMPOSE_CMD[@]}" up -d --force-recreate news-ingestion >/dev/null 2>&1 || true
)


echo "Running PostgreSQL migrations..."
(
  cd database/postgres
  ./migrate.sh
)

echo "Local environment started."
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

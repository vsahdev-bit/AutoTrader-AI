#!/bin/sh
set -eu

VAULT_ADDR=${VAULT_ADDR:-http://vault:8200}
INIT_JSON=${INIT_JSON:-/vault/file/init.json}
UNSEAL_KEY_FILE=${UNSEAL_KEY_FILE:-/vault/file/unseal.key}
ROOT_TOKEN_FILE=${ROOT_TOKEN_FILE:-/vault/file/root.token}
TOKEN_ID=${VAULT_TOKEN_ID:-local-dev-token}
POLICY_NAME=${POLICY_NAME:-autotrader-local}

log() { echo "[vault-bootstrap] $*"; }

wait_http() {
  log "Waiting for Vault HTTP at $VAULT_ADDR ..."
  for i in $(seq 1 180); do
    # We only need an HTTP response (200/429/472/501/503 etc.); any JSON body means it's reachable.
    if curl -sS "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  log "ERROR: Vault did not become reachable" >&2
  exit 1
}

health_json() {
  curl -sS "$VAULT_ADDR/v1/sys/health"
}

is_initialized() {
  health_json | jq -r '.initialized'
}

is_sealed() {
  health_json | jq -r '.sealed'
}

init_vault() {
  log "Initializing Vault (persisting init materials to volume)..."
  tmp="$INIT_JSON.tmp"
  curl -sS -X PUT \
    -H 'Content-Type: application/json' \
    --data '{"secret_shares":1,"secret_threshold":1}' \
    "$VAULT_ADDR/v1/sys/init" > "$tmp"

  # Validate JSON
  jq -e . "$tmp" >/dev/null

  # Persist unseal key + root token in separate files
  jq -r '.keys_base64[0] // .unseal_keys_b64[0]' "$tmp" > "$UNSEAL_KEY_FILE"
  jq -r '.root_token' "$tmp" > "$ROOT_TOKEN_FILE"

  # Atomic move
  mv "$tmp" "$INIT_JSON"
  log "Init material written: $INIT_JSON"
}

unseal_vault() {
  key=$(cat "$UNSEAL_KEY_FILE")
  if [ -z "$key" ]; then
    log "ERROR: unseal key file empty: $UNSEAL_KEY_FILE" >&2
    exit 1
  fi
  log "Unsealing Vault..."
  curl -sS -X PUT \
    -H 'Content-Type: application/json' \
    --data "{\"key\":\"$key\"}" \
    "$VAULT_ADDR/v1/sys/unseal" >/dev/null
}

ensure_kv2() {
  token=$(cat "$ROOT_TOKEN_FILE")
  log "Ensuring KV v2 enabled at secret/..."
  # Enable if not present
  mounts=$(curl -sS -H "X-Vault-Token: $token" "$VAULT_ADDR/v1/sys/mounts")
  echo "$mounts" | jq -e 'has("secret/")' >/dev/null 2>&1 && return 0

  curl -sS -X POST \
    -H "X-Vault-Token: $token" \
    -H 'Content-Type: application/json' \
    --data '{"type":"kv","options":{"version":"2"}}' \
    "$VAULT_ADDR/v1/sys/mounts/secret" >/dev/null
}

ensure_policy_and_token() {
  token=$(cat "$ROOT_TOKEN_FILE")

  log "Writing policy $POLICY_NAME and creating stable service token id=$TOKEN_ID"

  policy=$(cat <<'EOF'
path "secret/data/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "secret/metadata/*" {
  capabilities = ["read", "list"]
}
EOF
)

  curl -sS -X PUT \
    -H "X-Vault-Token: $token" \
    -H 'Content-Type: application/json' \
    --data "$(jq -n --arg p "$policy" '{policy:$p}')" \
    "$VAULT_ADDR/v1/sys/policies/acl/$POLICY_NAME" >/dev/null

  # Create a token with a fixed id; ignore if already exists
  curl -sS -X POST \
    -H "X-Vault-Token: $token" \
    -H 'Content-Type: application/json' \
    --data "$(jq -n --arg id "$TOKEN_ID" --arg pol "$POLICY_NAME" '{id:$id, policies:[$pol], period:"168h"}')" \
    "$VAULT_ADDR/v1/auth/token/create" >/dev/null 2>&1 || true
}

main() {
  wait_http

  init=$(is_initialized)
  sealed=$(is_sealed)
  log "Vault state: initialized=$init sealed=$sealed"

  if [ "$init" = "false" ]; then
    init_vault
    sealed=$(is_sealed)
  else
    # If initialized already, we require init materials to exist to unseal.
    if [ ! -f "$UNSEAL_KEY_FILE" ] || [ ! -f "$ROOT_TOKEN_FILE" ]; then
      log "ERROR: Vault is initialized but init materials are missing in volume. You must reset vault_data." >&2
      exit 1
    fi
  fi

  if [ "$(is_sealed)" = "true" ]; then
    unseal_vault
  fi

  if [ "$(is_sealed)" = "true" ]; then
    log "ERROR: Vault still sealed after unseal attempt" >&2
    exit 1
  fi

  ensure_kv2
  ensure_policy_and_token

  log "Vault initialized/unsealed. Service token id: $TOKEN_ID"
}

main

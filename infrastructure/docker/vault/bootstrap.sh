#!/bin/sh
set -eu

# Bootstrap Vault for local development.
# - Initializes + unseals Vault (file-backed, persisted via docker volume)
# - Ensures KV v2 is enabled at secret/
# - Creates a stable token id for services (local-dev-token)

VAULT_ADDR=${VAULT_ADDR:-http://vault:8200}
INIT_FILE=${INIT_FILE:-/vault/file/init.json}
TOKEN_ID=${VAULT_TOKEN_ID:-local-dev-token}
POLICY_NAME=${POLICY_NAME:-autotrader-local}

wait_ready() {
  echo "[vault-bootstrap] Waiting for Vault HTTP..."
  for i in $(seq 1 120); do
    # Use HTTP reachability; /v1/sys/health returns 501 while uninitialized, which is OK.
    if wget -qO- "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1; then
      return 0
    fi
    # Some wget builds return non-zero on 501; still treat any response body as reachable.
    if wget -qO- "$VAULT_ADDR/v1/sys/health" 2>/dev/null | grep -q '"version"'; then
      return 0
    fi
    sleep 1
  done
  echo "[vault-bootstrap] Vault did not become reachable" >&2
  exit 1
}

parse_unseal_key() {
  # init.json contains: "unseal_keys_b64":["..."],"root_token":"..."
  sed -n 's/.*"unseal_keys_b64"[[:space:]]*:[[:space:]]*\["\([^"]*\)"\].*/\1/p' "$INIT_FILE" | head -n 1
}

parse_root_token() {
  sed -n 's/.*"root_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$INIT_FILE" | head -n 1
}

wait_ready

if [ ! -f "$INIT_FILE" ]; then
  echo "[vault-bootstrap] Initializing Vault..."
  VAULT_ADDR="$VAULT_ADDR" vault operator init -key-shares=1 -key-threshold=1 -format=json > "$INIT_FILE"
  echo "[vault-bootstrap] Wrote init material to $INIT_FILE"
fi

UNSEAL_KEY=$(parse_unseal_key)
ROOT_TOKEN=$(parse_root_token)

if [ -z "$UNSEAL_KEY" ] || [ -z "$ROOT_TOKEN" ]; then
  echo "[vault-bootstrap] ERROR: could not parse init file: $INIT_FILE" >&2
  exit 1
fi

# Unseal if sealed
if VAULT_ADDR="$VAULT_ADDR" vault status 2>/dev/null | grep -qi "sealed[[:space:]]*true"; then
  echo "[vault-bootstrap] Unsealing Vault..."
  VAULT_ADDR="$VAULT_ADDR" vault operator unseal "$UNSEAL_KEY" >/dev/null
fi

# Authenticate as root for setup steps
export VAULT_ADDR
export VAULT_TOKEN="$ROOT_TOKEN"

# Enable KV v2 at secret/ (ignore if already enabled)
vault secrets enable -path=secret kv-v2 >/dev/null 2>&1 || true

# Write policy
POLICY_FILE="/tmp/${POLICY_NAME}.hcl"
cat > "$POLICY_FILE" <<'EOF'
path "secret/data/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "secret/metadata/*" {
  capabilities = ["read", "list"]
}
EOF

vault policy write "$POLICY_NAME" "$POLICY_FILE" >/dev/null

# Create stable token id for services (ignore if already exists)
vault token create -id="$TOKEN_ID" -policy="$POLICY_NAME" -period="168h" >/dev/null 2>&1 || true

echo "[vault-bootstrap] Vault initialized/unsealed. Service token id: $TOKEN_ID"

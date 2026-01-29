#!/bin/sh
set -eu

# Bootstrap Vault for local development.
# - Initializes + unseals Vault (file-backed, persisted via docker volume)
# - Ensures KV v2 is enabled at secret/
# - Creates a stable token id for services (local-dev-token)

VAULT_ADDR=${VAULT_ADDR:-http://vault:8200}
INIT_FILE=${INIT_FILE:-/vault/file/init.json}
UNSEAL_KEY_FILE=${UNSEAL_KEY_FILE:-/vault/file/unseal.key}
ROOT_TOKEN_FILE=${ROOT_TOKEN_FILE:-/vault/file/root.token}
TOKEN_ID=${VAULT_TOKEN_ID:-local-dev-token}
POLICY_NAME=${POLICY_NAME:-autotrader-local}

wait_ready() {
  echo "[vault-bootstrap] Waiting for Vault HTTP..."
  for i in $(seq 1 120); do
    # Use vault CLI (available in image). We consider Vault "reachable" as soon as
    # the status command returns *any* meaningful response (including "not initialized").
    out=$(VAULT_ADDR="$VAULT_ADDR" vault status 2>&1 || true)

    # Treat as reachable once the status table is returned (it contains an 'Initialized' row)
    echo "$out" | grep -qi "^Initialized" && return 0

    # Some versions include a more verbose header
    echo "$out" | grep -qi "Vault server status" && return 0

    # If we got here, we likely can't connect yet.
    # Only log occasionally to avoid noisy logs.
    if [ $((i % 10)) -eq 0 ]; then
      echo "[vault-bootstrap] still waiting... last error: ${out}" >&2
    fi

    sleep 1
  done
  echo "[vault-bootstrap] Vault did not become reachable" >&2
  exit 1
}

# We avoid parsing init JSON with sed/jq/python; instead we persist the unseal key
# and root token into separate files on first initialization.


wait_ready

if [ ! -f "$INIT_FILE" ] || [ ! -f "$UNSEAL_KEY_FILE" ] || [ ! -f "$ROOT_TOKEN_FILE" ]; then
  echo "[vault-bootstrap] Initializing Vault..."
  VAULT_ADDR="$VAULT_ADDR" vault operator init -key-shares=1 -key-threshold=1 -format=json > "$INIT_FILE"

  # Extract and persist init materials for future runs.
  # The JSON output contains unseal_keys_b64 and root_token.
  UNSEAL_KEY=$(sed -n 's/.*"unseal_keys_b64"[[:space:]]*:[[:space:]]*\["\([^"]*\)"\].*/\1/p' "$INIT_FILE" | head -n 1)
  ROOT_TOKEN=$(sed -n 's/.*"root_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$INIT_FILE" | head -n 1)

  if [ -z "$UNSEAL_KEY" ] || [ -z "$ROOT_TOKEN" ]; then
    echo "[vault-bootstrap] ERROR: could not extract unseal/root token from init json" >&2
    exit 1
  fi

  echo "$UNSEAL_KEY" > "$UNSEAL_KEY_FILE"
  echo "$ROOT_TOKEN" > "$ROOT_TOKEN_FILE"

  echo "[vault-bootstrap] Wrote init material to $INIT_FILE"
fi

UNSEAL_KEY=$(cat "$UNSEAL_KEY_FILE")
ROOT_TOKEN=$(cat "$ROOT_TOKEN_FILE")

if [ -z "$UNSEAL_KEY" ] || [ -z "$ROOT_TOKEN" ]; then
  echo "[vault-bootstrap] ERROR: init materials missing/empty" >&2
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

#!/bin/sh
set -eu

VAULT_ADDR=${VAULT_ADDR:-http://vault:8200}
INIT_FILE=${INIT_FILE:-/vault/file/init.json}
TOKEN_ID=${VAULT_TOKEN_ID:-local-dev-token}

wait_ready() {
  echo "[vault-bootstrap] Waiting for Vault HTTP..."
  for i in $(seq 1 60); do
    if curl -sS "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "[vault-bootstrap] Vault did not become reachable" >&2
  exit 1
}

wait_ready

# If not initialized, initialize and persist init material to disk.
if [ ! -f "$INIT_FILE" ]; then
  echo "[vault-bootstrap] Initializing Vault..."
  curl -sS --request POST --data '{"secret_shares":1,"secret_threshold":1}' \
    "$VAULT_ADDR/v1/sys/init" > "$INIT_FILE"
  echo "[vault-bootstrap] Wrote init material to $INIT_FILE"
fi

UNSEAL_KEY=$(cat "$INIT_FILE" | python3 -c "import sys,json; print(json.load(sys.stdin)['keys_base64'][0])")
ROOT_TOKEN=$(cat "$INIT_FILE" | python3 -c "import sys,json; print(json.load(sys.stdin)['root_token'])")

# Unseal if needed
SEALED=$(curl -sS "$VAULT_ADDR/v1/sys/health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sealed', True))")
if [ "$SEALED" = "True" ] || [ "$SEALED" = "true" ]; then
  echo "[vault-bootstrap] Unsealing Vault..."
  curl -sS --request POST --data "{\"key\":\"$UNSEAL_KEY\"}" \
    "$VAULT_ADDR/v1/sys/unseal" >/dev/null
fi

# Ensure KV v2 is enabled at secret/
# (If already enabled, this may error; ignore.)
if ! curl -sS -H "X-Vault-Token: $ROOT_TOKEN" "$VAULT_ADDR/v1/sys/mounts" | grep -q '"secret/"'; then
  echo "[vault-bootstrap] Enabling KV v2 at secret/..."
  curl -sS -H "X-Vault-Token: $ROOT_TOKEN" --request POST \
    --data '{"type":"kv","options":{"version":"2"}}' \
    "$VAULT_ADDR/v1/sys/mounts/secret" >/dev/null
fi

# Create or renew a stable token id for services.
# Using a fixed token id lets docker-compose set VAULT_TOKEN deterministically.
# If it already exists, ignore the error.
POLICY_NAME=autotrader-local
POLICY_FILE=/tmp/${POLICY_NAME}.hcl
cat > "$POLICY_FILE" <<'EOF'
path "secret/data/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "secret/metadata/*" {
  capabilities = ["read", "list"]
}
EOF

POLICY_JSON=$(python3 -c "import json; print(json.dumps({'policy': open('$POLICY_FILE').read()}))")

curl -sS -H "X-Vault-Token: $ROOT_TOKEN" --request PUT \
  --data "$POLICY_JSON" \
  "$VAULT_ADDR/v1/sys/policies/acl/$POLICY_NAME" >/dev/null 2>&1 || true

# Create token with fixed id
curl -sS -H "X-Vault-Token: $ROOT_TOKEN" --request POST \
  --data "{\"id\":\"$TOKEN_ID\",\"policies\":[\"$POLICY_NAME\"],\"period\":\"168h\"}" \
  "$VAULT_ADDR/v1/auth/token/create" >/dev/null 2>&1 || true

echo "[vault-bootstrap] Vault is initialized/unsealed. Service token id: $TOKEN_ID"

ui = true

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

storage "file" {
  path = "/vault/file"
}

disable_mlock = true

# Required so other containers can reach Vault via docker network name
api_addr = "http://vault:8200"

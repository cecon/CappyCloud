#!/bin/sh
# Entrypoint do agentmemory do CappyCloud (adaptado de rohitg00/agentmemory
# deploy/coolify, Apache-2.0, via kodra/docker/agentmemory).
#
# Roda como root para:
#   1. sobrescrever o iii-config.yaml do pacote (que escuta em 127.0.0.1 e
#      usa ./data relativo) por um que escuta em 0.0.0.0 e usa /data;
#   2. dar ao usuário `node` a posse do volume /data.
# Exige AGENTMEMORY_SECRET no ambiente (o mesmo valor do sandbox). Depois
# executa o CLI do agentmemory como `node`, via gosu.

set -eu

DATA_DIR="${AGENTMEMORY_DATA_DIR:-/data}"
RUN_AS="node:node"
III_CONFIG="/opt/agentmemory/node_modules/@agentmemory/agentmemory/dist/iii-config.yaml"

mkdir -p "$DATA_DIR"
chown -R "$RUN_AS" "$DATA_DIR"

cat > "$III_CONFIG" <<'EOF'
workers:
  - name: iii-http
    config:
      port: 3111
      host: 0.0.0.0
      default_timeout: 180000
      cors:
        allowed_origins:
          - "http://localhost:3111"
          - "http://localhost:3113"
          - "http://127.0.0.1:3111"
          - "http://127.0.0.1:3113"
        allowed_methods: [GET, POST, PUT, DELETE, OPTIONS]
  - name: iii-state
    config:
      adapter:
        name: kv
        config:
          store_method: file_based
          file_path: /data/state_store.db
  - name: iii-queue
    config:
      adapter:
        name: builtin
  - name: iii-pubsub
    config:
      adapter:
        name: local
  - name: iii-cron
    config:
      adapter:
        name: kv
  - name: iii-stream
    config:
      port: 3112
      host: 0.0.0.0
      adapter:
        name: kv
        config:
          store_method: file_based
          file_path: /data/stream_store
  - name: iii-observability
    config:
      enabled: true
      service_name: agentmemory
      exporter: memory
      sampling_ratio: 1.0
      metrics_enabled: true
      logs_enabled: true
      logs_console_output: true
EOF
chown "$RUN_AS" "$III_CONFIG"

# CappyCloud: o segredo é obrigatório. O sandbox usa o mesmo valor
# para autenticar; gerar um aqui (e imprimi-lo no log, como no upstream) não
# serviria a ninguém.
if [ -z "${AGENTMEMORY_SECRET:-}" ]; then
  echo "agentmemory: defina AGENTMEMORY_SECRET (o mesmo valor no sandbox)." >&2
  exit 1
fi
export AGENTMEMORY_SECRET

exec gosu "$RUN_AS" agentmemory "$@"

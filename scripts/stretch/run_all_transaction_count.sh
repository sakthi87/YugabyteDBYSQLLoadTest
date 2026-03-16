#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

usage() {
  cat <<'EOF'
Usage: bash scripts/stretch/run_all_transaction_count.sh [options]

Runs Stretch Cluster transaction count configs (plain, index, fk, index_fk).

Options:
  --run-root PATH          Run set folder (default: runs/stretch_<timestamp>_transaction_count)
  --host HOST              DB host (default: 127.0.0.1)
  --port PORT              DB port (default: 5433)
  --user USER              DB user (default: yugabyte)
  --password PASS          DB password (default: empty)
  --dbname NAME            DB name (default: yb_load_test)
  --tserver-url URLS       TServer metrics URL(s), comma-separated
  --env-label LABEL        Optional label for run_description
  -h, --help               Show help
EOF
}

run_root=""
host="127.0.0.1"
port="5433"
user="yugabyte"
password=""
dbname="yb_load_test"
tserver_url="http://127.0.0.1:9000/metrics"
env_label=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-root) run_root="$2"; shift 2 ;;
    --host) host="$2"; shift 2 ;;
    --port) port="$2"; shift 2 ;;
    --user) user="$2"; shift 2 ;;
    --password) password="$2"; shift 2 ;;
    --dbname) dbname="$2"; shift 2 ;;
    --tserver-url) tserver_url="$2"; shift 2 ;;
    --env-label) env_label="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

[[ -z "$run_root" ]] && run_root="runs/stretch_$(date +%Y%m%d-%H%M%S)_transaction_count"
mkdir -p "$run_root"

export YB_HOST="$host" YB_PORT="$port" YB_USER="$user" YB_PASSWORD="$password" YB_DBNAME="$dbname" YB_TSERVER_METRICS="$tserver_url" YB_ENV_LABEL="$env_label"

for cfg in config/stretch/transaction_count/plain.json config/stretch/transaction_count/index.json config/stretch/transaction_count/fk.json config/stretch/transaction_count/index_fk.json; do
  echo "Running: $cfg"
  python3 -m ysqlload.cli --config "$cfg" --run-root "$run_root"
done

echo "Stretch transaction count run set completed: $run_root"
echo "Starting dashboard at http://127.0.0.1:8787"
python3 -m ysqlload.cli --serve-only --run-root "$run_root"

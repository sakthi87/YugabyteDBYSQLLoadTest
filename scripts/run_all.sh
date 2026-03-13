#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/run_all.sh [options]

Options:
  --run-root PATH          Run set folder under runs/ (default: runs/<timestamp>_run)
  --host HOST              DB host (default: 127.0.0.1)
  --port PORT              DB port (default: 5433)
  --user USER              DB user (default: yugabyte)
  --password PASS          DB password (default: empty)
  --dbname NAME            DB name (default: yb_load_test)
  --tserver-url URL        TServer metrics URL (default: http://127.0.0.1:9000/metrics)
  --env-label LABEL        Optional label to append to run_description
  -h, --help               Show help

Examples:
  bash scripts/run_all.sh --run-root runs/stage_2026_03_12_run1 --host 10.20.30.40 --port 5433 --user yugabyte --password secret
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

if [[ -z "$run_root" ]]; then
  run_root="runs/$(date +%Y%m%d-%H%M%S)_run"
fi

mkdir -p "$run_root"

export YB_HOST="$host"
export YB_PORT="$port"
export YB_USER="$user"
export YB_PASSWORD="$password"
export YB_DBNAME="$dbname"
export YB_TSERVER_METRICS="$tserver_url"
export YB_ENV_LABEL="$env_label"

configs=(
  "config/scenario_plain.json"
  "config/scenario_index.json"
  "config/scenario_fk.json"
  "config/scenario_index_fk.json"
)

for cfg in "${configs[@]}"; do
  echo "Running: $cfg"
  python3 -m ysqlload.cli --config "$cfg" --run-root "$run_root"
done

echo "Run set completed: $run_root"

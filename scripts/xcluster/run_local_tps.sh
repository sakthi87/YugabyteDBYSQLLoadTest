#!/usr/bin/env bash
# Run XCluster TPS load test against local Docker setup.
# Requires: bash scripts/xcluster/setup_local_docker.sh (already run)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

export YB_HOST="${YB_HOST:-127.0.0.1}"
export YB_PORT="${YB_PORT:-5411}"
export YB_USER="${YB_USER:-yugabyte}"
export YB_PASSWORD="${YB_PASSWORD:-}"
export YB_DBNAME="${YB_DBNAME:-yb_load_test}"
export YB_TSERVER_METRICS="${YB_TSERVER_METRICS:-http://127.0.0.1:9011/prometheus-metrics}"
export YB_ENV_LABEL="${YB_ENV_LABEL:-local-xcluster}"

# Always use unique folder per run (timestamp in path) to avoid confusion
TS=$(date +%Y%m%d-%H%M%S)
if [[ -n "${1:-}" ]]; then
  if [[ "$1" =~ [0-9]{8}-[0-9]{6} ]]; then
    run_root="$1"
  else
    run_root="${1}_${TS}"
  fi
else
  run_root="runs/xcluster_local_${TS}_tps"
fi
mkdir -p "$run_root"

echo "Running XCluster TPS (local Docker)"
echo "  Host: $YB_HOST:$YB_PORT"
echo "  Metrics: $YB_TSERVER_METRICS"
echo "  Output: $run_root"
echo ""

python3 -m ysqlload.cli --config config/xcluster/local/plain.json --run-root "$run_root"

echo ""
echo "Run completed: $run_root"
echo "Start dashboard: python3 -m ysqlload.cli --serve-only --run-root $run_root"

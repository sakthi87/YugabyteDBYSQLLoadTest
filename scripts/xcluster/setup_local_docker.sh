#!/usr/bin/env bash
# Setup XCluster active-passive locally in Docker for lag metrics testing.
# Run from project root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

YB_IMAGE="${YB_IMAGE:-yugabytedb/yugabyte:2024.2.8.0-b85}"
NETWORK="xcluster-lab"
SOURCE_NODE="Lab11"
TARGET_NODE="Lab21"
DBNAME="yb_load_test"
MASTER_ADDRS_SRC="Lab11:7100"
MASTER_ADDRS_TGT="Lab21:7100"

echo "=== XCluster Local Docker Setup ==="
echo "Image: $YB_IMAGE"
echo ""

# Cleanup existing
echo "[1/9] Cleaning up any existing containers..."
docker rm -f $SOURCE_NODE $TARGET_NODE 2>/dev/null || true
docker network create $NETWORK 2>/dev/null || true

# Start source cluster (single node)
echo "[2/9] Starting SOURCE cluster ($SOURCE_NODE)..."
docker run -d --name $SOURCE_NODE --hostname $SOURCE_NODE --network $NETWORK \
  -p 5411:5433 -p 7011:7000 -p 9011:9000 \
  "$YB_IMAGE" \
  bin/yugabyted start --daemon=false --listen $SOURCE_NODE

# Start target cluster (single node)
echo "[3/9] Starting TARGET cluster ($TARGET_NODE)..."
docker run -d --name $TARGET_NODE --hostname $TARGET_NODE --network $NETWORK \
  -p 5421:5433 -p 7021:7000 -p 9021:9000 \
  "$YB_IMAGE" \
  bin/yugabyted start --daemon=false --listen $TARGET_NODE

echo "[4/9] Waiting for clusters to form (45 sec)..."
sleep 45

# Create DB and schema on source
echo "[5/9] Creating schema on SOURCE..."
docker exec $SOURCE_NODE bin/ysqlsh -h $SOURCE_NODE -U yugabyte -c "CREATE DATABASE $DBNAME;" 2>/dev/null || true
docker cp scripts/scenarios/schema_plain.sql $SOURCE_NODE:/tmp/
docker cp scripts/scenarios/preload_10_tables.sql $SOURCE_NODE:/tmp/
docker exec $SOURCE_NODE bin/ysqlsh -h $SOURCE_NODE -U yugabyte -d $DBNAME -f /tmp/schema_plain.sql
echo "      Preloading data (100k rows x 10 tables - may take 2-3 min)..."
docker exec $SOURCE_NODE bin/ysqlsh -h $SOURCE_NODE -U yugabyte -d $DBNAME -f /tmp/preload_10_tables.sql

# Get source UUID and table IDs
echo "[6/9] Getting source UUID and table IDs..."
CONFIG_JSON=$(docker exec $SOURCE_NODE bin/yb-admin -master_addresses $MASTER_ADDRS_SRC get_universe_config 2>/dev/null || echo "{}")
SOURCE_UUID=$(echo "$CONFIG_JSON" | grep -o '"clusterUuid"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
if [[ -z "$SOURCE_UUID" ]]; then
  SOURCE_UUID=$(echo "$CONFIG_JSON" | grep -o '"universeUuid"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
fi
if [[ -z "$SOURCE_UUID" ]]; then
  echo "ERROR: Could not get source cluster UUID. get_universe_config output:"
  docker exec $SOURCE_NODE bin/yb-admin -master_addresses $MASTER_ADDRS_SRC get_universe_config 2>&1 || true
  exit 1
fi

TABLES_OUT=$(docker exec $SOURCE_NODE bin/yb-admin -master_addresses $MASTER_ADDRS_SRC list_tables include_table_id include_db_type include_table_type 2>/dev/null || true)
# Extract table IDs (32-char hex) for base tables only (exclude index)
TABLE_IDS=$(echo "$TABLES_OUT" | awk -v db="$DBNAME" 'index($0,"ysql."db) && / table$/ { print $(NF-1) }' | tr '\n' ',' | sed 's/,$//')
if [[ -z "$TABLE_IDS" ]]; then
  # Fallback: any 32-char hex from ysql tables
  TABLE_IDS=$(echo "$TABLES_OUT" | grep "ysql\.$DBNAME" | grep -oE '[0-9a-f]{32}' | sort -u | tr '\n' ',' | sed 's/,$//')
fi
if [[ -z "$TABLE_IDS" ]]; then
  echo "ERROR: Could not get table IDs. list_tables output:"
  echo "$TABLES_OUT"
  exit 1
fi

echo "      Source UUID: $SOURCE_UUID"
echo "      Table IDs: $TABLE_IDS"

# Create same schema on target
echo "[7/9] Creating schema on TARGET..."
docker exec $TARGET_NODE bin/ysqlsh -h $TARGET_NODE -U yugabyte -c "CREATE DATABASE $DBNAME;" 2>/dev/null || true
docker cp scripts/scenarios/schema_plain.sql $TARGET_NODE:/tmp/
docker cp scripts/scenarios/preload_10_tables.sql $TARGET_NODE:/tmp/
docker exec $TARGET_NODE bin/ysqlsh -h $TARGET_NODE -U yugabyte -d $DBNAME -f /tmp/schema_plain.sql
# Target can stay empty - replication will stream data; or preload for consistency
docker exec $TARGET_NODE bin/ysqlsh -h $TARGET_NODE -U yugabyte -d $DBNAME -f /tmp/preload_10_tables.sql

# Setup xCluster replication (from target, pointing to source)
echo "[8/9] Setting up XCluster replication..."
docker exec $TARGET_NODE bin/yb-admin \
  -master_addresses $MASTER_ADDRS_TGT \
  setup_universe_replication "${SOURCE_UUID}_xcluster1" \
  "$MASTER_ADDRS_SRC" \
  "$TABLE_IDS"

# Verify
echo "[9/9] Verifying replication..."
sleep 5
STATUS=$(docker exec $TARGET_NODE bin/yb-admin -master_addresses $MASTER_ADDRS_TGT get_replication_status 2>/dev/null || echo "{}")
if echo "$STATUS" | grep -q '"errors"' && ! echo "$STATUS" | grep -q '"errors": \[\]'; then
  echo "WARNING: Replication may have errors:"
  echo "$STATUS"
else
  echo "      Replication status OK"
fi

echo ""
echo "=== XCluster setup complete ==="
echo ""
echo "Connection info:"
echo "  YSQL (SOURCE): 127.0.0.1:5411"
echo "  TServer metrics (SOURCE): http://127.0.0.1:9011/prometheus-metrics"
echo ""
echo "Run load test:"
echo "  bash scripts/xcluster/run_local_tps.sh"
echo ""
echo "Or manually:"
echo "  bash scripts/xcluster/run_all_tps.sh \\"
echo "    --host 127.0.0.1 --port 5411 --dbname $DBNAME \\"
echo "    --tserver-url \"http://127.0.0.1:9011/prometheus-metrics\" \\"
echo "    --env-label local-xcluster"
echo ""
echo "Cleanup: docker rm -f $SOURCE_NODE $TARGET_NODE"

# XCluster Active-Passive Setup for Local Testing

This guide walks through setting up two YugabyteDB clusters locally (Docker) with XCluster replication, so you can run the load test and verify replication lag metrics.

## Prerequisites

- Docker
- `yb-admin` (from YugabyteDB package, or run inside a container)
- `ysqlsh`, `psql`, `pgbench` (for load test)

## Overview

| Component | Source (Active) | Target (Passive) |
|-----------|-----------------|-----------------|
| Cluster | Lab1 (3 nodes) | Lab2 (3 nodes) |
| YSQL | Lab11:5433, Lab12:5433, Lab13:5433 | Lab21:5433, Lab22:5433, Lab23:5433 |
| Master | Lab11:7100, Lab12:7100, Lab13:7100 | Lab21:7100, Lab22:7100, Lab23:7100 |
| TServer metrics | Lab11:9000/prometheus-metrics | Lab21:9000/prometheus-metrics |

Replication lag metrics (`async_replication_committed_lag_micros`) are on the **SOURCE** cluster tservers.

---

## Step 1: Create Docker Network

```bash
docker network create xcluster-lab 2>/dev/null || true
```

---

## Step 2: Start Source Cluster (3 nodes)

```bash
# Node 1
docker run -d --name Lab11 --hostname Lab11 --network xcluster-lab \
  -p 15411:15433 -p 7011:7000 -p 9011:9000 -p 5411:5433 \
  yugabytedb/yugabyte:2024.2.8.0-b85 \
  bin/yugabyted start --daemon=false --listen Lab11

# Node 2 (join)
docker run -d --name Lab12 --hostname Lab12 --network xcluster-lab \
  -p 15412:15433 -p 7012:7000 -p 9012:9000 -p 5412:5433 \
  yugabytedb/yugabyte:2024.2.8.0-b85 \
  bin/yugabyted start --daemon=false --listen Lab12 --join Lab11

# Node 3 (join)
docker run -d --name Lab13 --hostname Lab13 --network xcluster-lab \
  -p 15413:15433 -p 7013:7000 -p 9013:9000 -p 5413:5433 \
  yugabytedb/yugabyte:2024.2.8.0-b85 \
  bin/yugabyted start --daemon=false --listen Lab13 --join Lab11
```

Wait ~30 seconds for the cluster to form.

---

## Step 3: Start Target Cluster (3 nodes)

```bash
# Node 1
docker run -d --name Lab21 --hostname Lab21 --network xcluster-lab \
  -p 15421:15433 -p 7021:7000 -p 9021:9000 -p 5421:5433 \
  yugabytedb/yugabyte:2024.2.8.0-b85 \
  bin/yugabyted start --daemon=false --listen Lab21

# Node 2 (join)
docker run -d --name Lab22 --hostname Lab22 --network xcluster-lab \
  -p 15422:15433 -p 7022:7000 -p 9022:9000 -p 5422:5433 \
  yugabytedb/yugabyte:2024.2.8.0-b85 \
  bin/yugabyted start --daemon=false --listen Lab22 --join Lab21

# Node 3 (join)
docker run -d --name Lab23 --hostname Lab23 --network xcluster-lab \
  -p 15423:15433 -p 7023:7000 -p 9023:9000 -p 5423:5433 \
  yugabytedb/yugabyte:2024.2.8.0-b85 \
  bin/yugabyted start --daemon=false --listen Lab23 --join Lab21
```

Wait ~30 seconds.

---

## Step 4: Create Schema and Tables on Source

From your project root:

```bash
# Create DB and tables (use load test schema)
docker exec Lab11 bin/ysqlsh -h Lab11 -U yugabyte -c "CREATE DATABASE yb_load_test;"

# Copy schema from project
docker cp scripts/scenarios/schema_plain.sql Lab11:/tmp/
docker cp scripts/scenarios/preload_10_tables.sql Lab11:/tmp/

docker exec Lab11 bin/ysqlsh -h Lab11 -U yugabyte -d yb_load_test -f /tmp/schema_plain.sql
docker exec Lab11 bin/ysqlsh -h Lab11 -U yugabyte -d yb_load_test -f /tmp/preload_10_tables.sql
```

---

## Step 5: Get Source UUID and Table IDs

```bash
# Source cluster UUID
docker exec Lab11 bin/yb-admin -master_addresses Lab11:7100,Lab12:7100,Lab13:7100 get_universe_config | grep clusterUuid

# Or from varz:
docker exec Lab11 curl -s http://Lab11:7000/varz?raw | grep cluster_uuid

# Table IDs (from inside Lab11)
docker exec Lab11 bin/yb-admin -master_addresses Lab11:7100,Lab12:7100,Lab13:7100 list_tables include_table_id include_db_type | grep ysql.yb_load_test
```

Save the source UUID (e.g. `e260b8b6-e89f-4505-bb8e-b31f74aa29f3`) and the table IDs.

---

## Step 6: Create Same Schema on Target

```bash
docker exec Lab21 bin/ysqlsh -h Lab21 -U yugabyte -c "CREATE DATABASE yb_load_test;"
docker cp scripts/scenarios/schema_plain.sql Lab21:/tmp/
docker cp scripts/scenarios/preload_10_tables.sql Lab21:/tmp/
docker exec Lab21 bin/ysqlsh -h Lab21 -U yugabyte -d yb_load_test -f /tmp/schema_plain.sql
docker exec Lab21 bin/ysqlsh -h Lab21 -U yugabyte -d yb_load_test -f /tmp/preload_10_tables.sql
```

---

## Step 7: Setup XCluster Replication

Run from **target** cluster, pointing to **source**:

```bash
# Replace SOURCE_UUID and TABLE_IDS with actual values from Step 5
SOURCE_UUID="<your-source-uuid>"
TABLE_IDS="<comma-separated-table-ids>"   # e.g. 000030a5000030008000000000004000,000030a5000030008000000000004005

docker exec Lab21 bin/yb-admin \
  -master_addresses Lab21:7100,Lab22:7100,Lab23:7100 \
  setup_universe_replication ${SOURCE_UUID}_xcluster1 \
  Lab11:7100,Lab12:7100,Lab13:7100 \
  $TABLE_IDS
```

---

## Step 8: Verify Replication

```bash
# Check replication status (on target)
docker exec Lab21 bin/yb-admin -master_addresses Lab21:7100,Lab22:7100,Lab23:7100 get_replication_status
```

Empty `errors` means healthy.

---

## Step 9: Run XCluster Load Test

From your host (where the load test project is):

```bash
# Connect to SOURCE cluster (Lab11). Port 5411 is mapped from host.
# TServer metrics: SOURCE cluster Lab11:9000 -> host port 9011
# Use host.docker.internal or 127.0.0.1 depending on your setup

# If running from host, use host port:
bash scripts/xcluster/run_all_tps.sh \
  --host 127.0.0.1 --port 5411 --user yugabyte --password "" \
  --dbname yb_load_test \
  --tserver-url "http://127.0.0.1:9011/prometheus-metrics" \
  --env-label local-xcluster
```

**Note:** If you run the load test from inside a container on the same Docker network, use `--host Lab11 --port 5433 --tserver-url "http://Lab11:9000/prometheus-metrics"`.

---

## Step 10: Cleanup

```bash
docker rm -f Lab11 Lab12 Lab13 Lab21 Lab22 Lab23
docker network rm xcluster-lab
```

---

## Simplified Single-Node Option (Minimal)

For a quicker test with two single-node clusters:

```bash
# Source
docker run -d --name yb-source --network xcluster-lab \
  -p 15431:15433 -p 7031:7000 -p 9031:9000 -p 5434:5433 \
  yugabytedb/yugabyte:2024.2.8.0-b85 \
  bin/yugabyted start --daemon=false --listen yb-source

# Target (after source is up)
docker run -d --name yb-target --network xcluster-lab \
  -p 15432:15433 -p 7032:7000 -p 9032:9000 -p 5435:5433 \
  yugabytedb/yugabyte:2024.2.8.0-b85 \
  bin/yugabyted start --daemon=false --listen yb-target
```

Then follow the same setup steps using `yb-source` and `yb-target` instead of Lab11/Lab21.

---

## Troubleshooting

| Issue | Check |
|-------|-------|
| Lag metrics all null | `--tserver-url` must point to **SOURCE** cluster tserver(s). Use `/prometheus-metrics` path. |
| Connection refused | Ensure containers are running and ports are mapped. |
| `get_replication_status` shows errors | Verify table IDs match. Ensure schema exists on both clusters. |
| No `async_replication_committed_lag_micros` in metrics | Run load during the test; metric appears when replication is active. |

## References

- [YugabyteDB xCluster Async Replication](https://docs.yugabyte.com/stable/deploy/multi-dc/async-replication/async-deployment/)
- [Cross-cluster async replication (dev.to)](https://dev.to/yugabyte/cross-cluster-async-replication-with-yugabytedb-xcluster-34mg)

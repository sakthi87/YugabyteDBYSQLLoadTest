YSQL Load Test Toolkit (Hybrid)
================================

This repo provides a lightweight, hybrid load-testing harness for YugabyteDB YSQL:

- Pure database load using `pgbench` for accurate TPS control.
- Optional HTTP/API load using an external runner (JMeter/Gatling/anything).
- One config file to create schema, prepopulate data, and run phases.

The goal is to make it easy to plug into an automated intake flow where a new
schema or API can be validated and benchmarked in a single run.

Requirements
------------

- `pgbench` (YSQL-compatible)
- `psql`
- Python 3.9+

Prerequisites (DB + Tables)
---------------------------

The tool can create the database and tables for you using the config:

- `schema.create_db`: create the database
- `schema.drop_db`: drop the database before create
- `schema.schema_sql_file`: schema SQL (tables/index/FKs)
- `schema.preload_sql_file`: initial data load

If you want to create tables manually, run the schema scripts with `psql`:

  psql -h <host> -p <port> -U <user> -d <dbname> -f scripts/scenarios/schema_plain.sql
  psql -h <host> -p <port> -U <user> -d <dbname> -f scripts/scenarios/preload_10_tables.sql

Quick Start
-----------

1) Copy the example config:

   cp config/example.json config/run.json

2) Edit connection info and SQL paths in `config/run.json`.

3) Run:

   python -m ysqlload.cli --config config/run.json

4) Start the local dashboard (optional):

   python -m ysqlload.cli --serve-only

Outputs
-------

Each run writes logs and a `summary.json` into `runs/<timestamp>/`.
If reports are enabled, `report.csv` and `report.html` are generated in the
same run directory.

Hybrid Approach
---------------

Use `pgbench` for database-level load and an optional external HTTP runner for
end-to-end API tests. This makes it easy to separate database performance from
API overhead, while still supporting full-system validation when needed.

Config Reference (JSON)
-----------------------

{
  "db": {
    "host": "127.0.0.1",
    "port": 5433,
    "user": "yugabyte",
    "password": "",
    "dbname": "yb_load_test"
  },
  "schema": {
    "create_db": true,
    "drop_db": true,
    "schema_sql_file": "scripts/schema.sql",
    "preload_sql_file": "scripts/preload.sql"
  },
  "reports": {
    "csv": true,
    "html": true
  },
  "phases": [
    {
      "name": "oltp_readwrite",
      "type": "pgbench",
      "clients": 16,
      "jobs": 4,
      "mix": [
        { "script": "scripts/pgbench/select.sql", "weight": 60 },
        { "script": "scripts/pgbench/update.sql", "weight": 25 },
        { "script": "scripts/pgbench/insert.sql", "weight": 10 },
        { "script": "scripts/pgbench/delete.sql", "weight": 5 }
      ],
      "ramp": [
        { "duration_sec": 60, "target_tps": 500 },
        { "duration_sec": 60, "target_tps": 800 },
        { "duration_sec": 120, "target_tps": 1200 }
      ]
    },
    {
      "name": "api_load_optional",
      "type": "http",
      "command": "jmeter",
      "args": ["-n", "-t", "api_test.jmx", "-l", "results.jtl"]
    }
  ]
}

Notes
-----

- You can omit the `http` phase if you only want DB load.
- Set `target_tps` for precise throttling in pgbench.
- Use `schema_sql_file` and `preload_sql_file` for Scenario A or B.
- For workload mixes, use the `mix` array with per-script weights.
- For ramp profiles, use `ramp` with multiple steps (duration + target TPS).
- For percentiles, set `log_transactions: true` in a pgbench phase (uses `-l`).
- `--serve` starts a local dashboard after the run.
- `--serve-only` starts the dashboard without running a new test.

Run by Transaction Count
------------------------

If you want a fixed number of transactions instead of a time-based run, use:

- `total_transactions`: total tx across all clients (we split across clients)
- `transactions_per_client`: exact tx per client

Example (1,000,000 total transactions per phase):

{
  "name": "select",
  "type": "pgbench",
  "clients": 8,
  "jobs": 2,
  "log_transactions": true,
  "report_per_script": true,
  "script": "scripts/pgbench10/select.sql",
  "total_transactions": 1000000
}

Note: `ramp` can include `total_transactions` or `transactions_per_client` for record-based runs.

Config & Script Organization
-----------------------------

Configs are organized by environment and mode:

| Environment | Mode | Config path | Run script |
|-------------|------|-------------|------------|
| dev | TPS | `config/dev/tps/` | `scripts/dev/run_all_tps.sh` or `scripts/run_all.sh` |
| dev | Transaction count | `config/dev/transaction_count/` | `scripts/dev/run_all_transaction_count.sh` |
| dev | Capacity | `config/dev/capacity/` | `scripts/dev/run_all_capacity.sh` |
| dev | **All** (TPS + tx count + capacity) | — | `scripts/dev/run_all.sh` |
| **validation** | **All** (~45 min, script testing) | `config/validation/` | `scripts/validation/run_all.sh` |
| **stretch** | TPS | `config/stretch/tps/` | `scripts/stretch/run_all_tps.sh` |
| **stretch** | Transaction count | `config/stretch/transaction_count/` | `scripts/stretch/run_all_transaction_count.sh` |
| **stretch** | Capacity | `config/stretch/capacity/` | `scripts/stretch/run_all_capacity.sh` |
| **stretch** | **All** (TPS + tx count + capacity) | — | `scripts/stretch/run_all.sh` |
| **xcluster** | TPS | `config/xcluster/tps/` | `scripts/xcluster/run_all_tps.sh` |
| **xcluster** | Transaction count | `config/xcluster/transaction_count/` | `scripts/xcluster/run_all_transaction_count.sh` |
| **xcluster** | Capacity | `config/xcluster/capacity/` | `scripts/xcluster/run_all_capacity.sh` |
| **xcluster** | **All** (TPS + tx count + capacity) | — | `scripts/xcluster/run_all.sh` |
| production | TPS | `config/production/tps/` | `scripts/production/run_all_tps.sh` or `scripts/run_all_production.sh` |
| production | Transaction count | `config/production/transaction_count/` | `scripts/production/run_all_transaction_count.sh` |
| production | Capacity | `config/production/capacity/` | `scripts/production/run_all_capacity.sh` |
| production | **All** (TPS + tx count + capacity) | — | `scripts/production/run_all.sh` |

Each mode has 4 schema variants: `plain`, `index`, `fk`, `index_fk`.

- **TPS**: Rate-limited (`target_tps`). Dev: 200/400/600 TPS. Production: 1K–10K TPS.
- **Transaction count**: Fixed records (`total_transactions`). Dev: 10K/20K/50K. Production: 50K/100K/200K.
- **Capacity**: Max throughput (`duration_sec` only, no rate limit). Dev: 60/120 sec. Production: 60/120 sec with scaled clients.

See `docs/CAPACITY_TESTING_AND_PGBOUNCER.md` for:
- Clients/jobs scaling, connection reuse, PgBouncer setup
- Stretch Cluster and XCluster implementation steps
- Finding replication lag thresholds

See `docs/VALIDATION_RUNBOOK.md` for:
- Dev script validation plan and duration estimates
- Quick validation (~30 min) via `scripts/validation/run_all.sh`
- What to verify (scripts, dashboard, connection count)

See `docs/REPLICATION_GUIDE.md` for propagating validation changes to dev/production.

See `docs/CAPACITY_ASSESSMENT_APPROACHES.md` for:
- Comparing pgbench vs pgbench+PgBouncer vs app drivers
- What each approach can and cannot evaluate
- Recommended assessment plan for Stretch Cluster and XCluster

**Stretch vs XCluster Configs:**
- **Stretch Cluster** (`config/stretch/`): `cluster_type: stretch`, production parameters (1K–10K TPS, 50K–200K tx, 60/120 sec capacity). No replication lag collection.
- **XCluster** (`config/xcluster/`): `cluster_type: xcluster`, `xcluster_enabled: true`, production parameters. Collects replication lag every 5 sec during load. Dashboard shows Replication Lag Over Time and Schema Decision Table includes Avg Lag, P95 Lag, Max Lag, DR Risk.

---

Running Stretch Cluster Load Tests
---------------------------------

Follow these steps to run load tests on a Stretch Cluster (2c-2e-1onprem or similar).

**Prerequisites:**
- pgbench, psql, Python 3.9+
- VM in the same region as your Stretch Cluster leaders (e.g., Azure Central)
- YugabyteDB Stretch Cluster running with YSQL enabled

**Step 1: Set connection parameters**

Replace placeholders with your actual values:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--host` | YSQL endpoint (load balancer or any node) | `stretch-ysql.example.com` |
| `--port` | YSQL port | `5433` |
| `--user` | DB user | `yugabyte` |
| `--password` | DB password (empty if none) | `""` |
| `--dbname` | Database name | `yb_load_test` |
| `--tserver-url` | TServer metrics URL(s) for before/after snapshots | `http://tserver1:9000/metrics` or comma-separated for multiple |
| `--env-label` | Optional label for run description | `prod-stretch` |
| `--run-root` | Custom output folder (default: `runs/stretch_<timestamp>`) | `runs/my_stretch_run` |

**Step 2: Run the load test**

Choose one of:

```bash
# TPS only (4 configs: plain, index, fk, index_fk)
bash scripts/stretch/run_all_tps.sh \
  --host <YSQL_HOST> --port 5433 --user yugabyte --password "" \
  --dbname yb_load_test \
  --tserver-url "http://<TSERVER>:9000/metrics" \
  --env-label prod-stretch

# Transaction count only (4 configs)
bash scripts/stretch/run_all_transaction_count.sh \
  --host <YSQL_HOST> --port 5433 --user yugabyte --password "" \
  --dbname yb_load_test \
  --tserver-url "http://<TSERVER>:9000/metrics" \
  --env-label prod-stretch

# Capacity only (4 configs)
bash scripts/stretch/run_all_capacity.sh \
  --host <YSQL_HOST> --port 5433 --user yugabyte --password "" \
  --dbname yb_load_test \
  --tserver-url "http://<TSERVER>:9000/metrics" \
  --env-label prod-stretch

# All 12 configs (TPS + transaction count + capacity)
bash scripts/stretch/run_all.sh \
  --host <YSQL_HOST> --port 5433 --user yugabyte --password "" \
  --dbname yb_load_test \
  --tserver-url "http://<TSERVER>:9000/metrics" \
  --env-label prod-stretch
```

**Step 3: View results**

The script starts the dashboard automatically. Open `http://127.0.0.1:8787`, select the run set, and review Summary Comparison, per-run charts, and raw outputs in each run folder.

---

Running XCluster Load Tests
---------------------------

Follow these steps to run load tests on an XCluster setup (active-passive DR).

**Local testing:** You can run XCluster active-passive locally using Docker. See [docs/XCLUSTER_LOCAL_SETUP.md](docs/XCLUSTER_LOCAL_SETUP.md) for step-by-step instructions (two clusters, schema setup, replication config, and load test commands).

**Prerequisites:**
- Same as Stretch Cluster
- XCluster replication configured (source → target)
- **Important:** `--tserver-url` must point to **SOURCE cluster** tserver(s) for replication lag metrics

**Step 1: Set connection parameters**

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--host` | YSQL endpoint of **SOURCE (active)** cluster | `xcluster-source-ysql.example.com` |
| `--port` | YSQL port | `5433` |
| `--user` | DB user | `yugabyte` |
| `--password` | DB password | `""` |
| `--dbname` | Database name | `yb_load_test` |
| `--tserver-url` | **SOURCE cluster** tserver metrics URL(s) — required for replication lag | `http://source-tserver1:9000/prometheus-metrics` |
| `--env-label` | Optional label | `prod-xcluster` |
| `--run-root` | Custom output folder (default: `runs/xcluster_<timestamp>`) | `runs/my_xcluster_run` |

**Step 2: Run the load test**

```bash
# TPS only (collects replication lag every 5 sec during load)
bash scripts/xcluster/run_all_tps.sh \
  --host <SOURCE_YSQL_HOST> --port 5433 --user yugabyte --password "" \
  --dbname yb_load_test \
  --tserver-url "http://<SOURCE_TSERVER>:9000/prometheus-metrics" \
  --env-label prod-xcluster

# Transaction count only
bash scripts/xcluster/run_all_transaction_count.sh \
  --host <SOURCE_YSQL_HOST> --port 5433 --user yugabyte --password "" \
  --dbname yb_load_test \
  --tserver-url "http://<SOURCE_TSERVER>:9000/prometheus-metrics" \
  --env-label prod-xcluster

# Capacity only
bash scripts/xcluster/run_all_capacity.sh \
  --host <SOURCE_YSQL_HOST> --port 5433 --user yugabyte --password "" \
  --dbname yb_load_test \
  --tserver-url "http://<SOURCE_TSERVER>:9000/prometheus-metrics" \
  --env-label prod-xcluster

# All 12 configs
bash scripts/xcluster/run_all.sh \
  --host <SOURCE_YSQL_HOST> --port 5433 --user yugabyte --password "" \
  --dbname yb_load_test \
  --tserver-url "http://<SOURCE_TSERVER>:9000/prometheus-metrics" \
  --env-label prod-xcluster
```

**Step 3: View results**

Open `http://127.0.0.1:8787`. For XCluster runs you will see:
- **Replication Lag Over Time** chart (per step)
- **Schema Decision Table** with Avg Lag, P95 Lag, Max Lag, DR Risk columns
- DR Risk: Safe (<100 ms), Warning (100–500 ms), High Risk (>500 ms)

**XCluster metrics captured:**
- `async_replication_committed_lag_micros` (source) or `consumer_safe_time_lag` (target). Use `http://host:9000/prometheus-metrics` (YugabyteDB default); `/metrics` is tried as fallback.
- Polled every 5 sec during each load step
- Stored in `replication_lag_over_time.json` per step
- Aggregated to avg, p95, max in `report.csv` and dashboard

---

Tunable Parameters for Load Testing
-----------------------------------

Edit the JSON configs in `config/stretch/` or `config/xcluster/` to tune load. Key parameters:

| Parameter | Location | Description | Production default |
|-----------|----------|-------------|--------------------|
| `duration_sec` | `phases[].ramp[].duration_sec` | Seconds per step | 60 (TPS), 60/120 (capacity) |
| `target_tps` | `phases[].ramp[].target_tps` | Rate limit (TPS mode) | 1000, 2000, 5000, 8000, 10000 |
| `total_transactions` | `phases[].ramp[].total_transactions` | Fixed tx count (transaction_count mode) | 50000, 100000, 200000 |
| `clients` | `phases[].ramp[].clients` | pgbench clients (≈ DB connections) | 32–256 (scaled with TPS) |
| `jobs` | `phases[].ramp[].jobs` | pgbench worker threads | 4–8 |
| `replication_metrics.interval_sec` | Top-level (XCluster only) | Replication lag poll interval | 5 |

**Guidelines:**
- **clients:** `clients ≥ target_tps × avg_latency_sec` (with 2–4× headroom). For 10K TPS @ 25 ms avg: ~256 clients.
- **jobs:** Typically ≤ CPU count, ≤ clients.
- **target_tps:** Start low (1K) and ramp up to find capacity; use replication lag (XCluster) to identify DR risk threshold.
- **duration_sec:** Longer runs (60–120 sec) give stable metrics; shorter (20 sec) for quick validation.

See `docs/CAPACITY_TESTING_AND_PGBOUNCER.md` for clients/jobs scaling and PgBouncer setup.

---

Runbook (5-Minute Setup)
------------------------

1) Start YugabyteDB (Docker example):

   docker run -d --name yb-load \
     -p 7001:7000 -p 9001:9000 -p 5434:5433 -p 9043:9042 \
     yugabytedb/yugabyte:2025.2.0.0-b131 \
     bin/yugabyted start --daemon=false

2) Run all 4 scenarios as a single run set:

   bash scripts/run_all.sh \
     --run-root runs/stage_2026_03_12_run1 \
     --host 127.0.0.1 --port 5434 --user yugabyte --password "" \
     --dbname yb_load_test \
     --tserver-url http://127.0.0.1:9001/metrics \
     --env-label stage

3) Launch the dashboard:

   python3 -m ysqlload.cli --serve-only

4) Open:

   http://127.0.0.1:8787

Review the Results
------------------

1) Open the dashboard and select the run set.
2) Use Summary Comparison to compare scenarios.
3) Use the run tabs for per-operation charts and details.
4) Raw outputs are in each run folder:

   - `summary.json`
   - `report.csv`
   - `report.html`
   - `latency_histogram.csv` (per step)

Understanding Latency Metrics (pgbench vs pg_stat_statements)
-------------------------------------------------------------

All latency values in this toolkit are in **milliseconds (ms)**. The dashboard
and reports show p50/p90/p95/p99 in ms.

- **pgbench (client)**: Measures *client-side* round-trip time per transaction.
  Includes network, connection, and full transaction execution.

- **pg_stat_statements (server)**: *Server-side* query execution time at the DB
  level. Enable with `server_metrics.pg_stat_statements: true` in config. The
  schema scripts create the extension automatically.

- **Overhead**: Approximate network + connection + protocol overhead =
  pgbench client avg − pg_stat server mean.

The dashboard "Latency Breakdown" chart shows client vs server vs overhead per
step. Use server (pg_stat) for DB-level latency; use client (pgbench) for
end-to-end application latency.

**yb_latency_histogram** (YugabyteDB 2.18.1+): When enabled, the tool also
fetches P50/P90/P95/P99 from `pg_stat_statements.yb_latency_histogram` via
`yb_get_percentile`. See `docs/PG_STAT_STATEMENTS_ANALYSIS.md` for retention,
long-run behavior, and optional periodic polling.

TServer Metrics URL(s)
----------------------

The `--tserver-url` option accepts a single URL or comma-separated URLs for
multi-node clusters. Metrics are captured from each URL before and after each step.

**Single URL:**

   bash scripts/run_all.sh --tserver-url http://127.0.0.1:9001/metrics

**Multiple URLs (comma-separated):**

   bash scripts/run_all.sh --tserver-url "http://node1:9000/metrics,http://node2:9000/metrics,http://node3:9000/metrics"

**Stretch cluster (2 Central + 2 East + 1 on-prem):**

   bash scripts/run_all_production.sh \
     --tserver-url "http://central1:9000/metrics,http://central2:9000/metrics,http://east1:9000/metrics,http://east2:9000/metrics,http://onprem1:9000/metrics"

Parameterization
----------------

All config files support environment variables:

- `YB_HOST`, `YB_PORT`, `YB_USER`, `YB_PASSWORD`, `YB_DBNAME`
- `YB_TSERVER_METRICS` (example: `http://host:9000/metrics` or comma-separated URLs)
- `YB_ENV_LABEL` (optional label used in run description)
- `server_metrics.pg_stat_statements`: true to capture server-side latency
- `server_metrics.pg_stat_statements_interval_sec`: 5 to poll every 5 sec and build latency-over-time

The `scripts/run_all.sh` script sets these automatically from CLI flags.

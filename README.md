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

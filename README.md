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

Note: `ramp` cannot be used together with `total_transactions` or `transactions_per_client`.

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

Parameterization
----------------

All `config/scenario_*.json` files support environment variables:

- `YB_HOST`, `YB_PORT`, `YB_USER`, `YB_PASSWORD`, `YB_DBNAME`
- `YB_TSERVER_METRICS` (example: `http://host:9000/metrics`)
- `YB_ENV_LABEL` (optional label used in run description)

The `scripts/run_all.sh` script sets these automatically from CLI flags.

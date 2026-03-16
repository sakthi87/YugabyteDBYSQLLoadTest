# Dev Scripts Validation Runbook

Use this runbook to validate that dev scripts work correctly, metrics are reported properly, and the dashboard displays all data including connection count.

---

## Quick Validation (~30 min)

**For script/config testing**, use the validation suite instead of full dev:

```bash
bash scripts/validation/run_all.sh \
  --run-root runs/validation_$(date +%Y%m%d) \
  --host 127.0.0.1 --port 5434 --tserver-url http://127.0.0.1:9001/metrics
```

- **12 configs**: TPS + transaction count + capacity, each with plain, index, fk, index_fk
- **~45 min** total
- Same structure as dev/production, shorter ramp values

After validation passes, replicate changes to dev/production using `docs/REPLICATION_GUIDE.md`.

---

## Duration Estimates (Dev)

| Script | Configs | Est. duration | Notes |
|--------|---------|---------------|-------|
| `scripts/dev/run_all_tps.sh` | 4 (plain, index, fk, index_fk) | **~35–45 min** | 4 phases × 3 steps × 120 sec + schema/preload |
| `scripts/dev/run_all_transaction_count.sh` | 4 | **~25–40 min** | 10K/20K/50K tx; duration depends on cluster speed |
| `scripts/dev/run_all_capacity.sh` | 4 | **~45–55 min** | 4 phases × 2 steps × (60+120) sec |
| `scripts/dev/run_all.sh` | 12 (all modes) | **~2–2.5 hours** | Sum of above |

**Per-config breakdown (dev TPS):**
- Schema create + preload: ~30–60 sec
- 4 phases × (30+30+60) sec = 8 min pgbench per config
- Total: ~9–10 min per config

---

## Validation Plan

### Phase 1: Individual scripts (recommended order)

1. **`scripts/dev/run_all_tps.sh`** (~40 min)
   - Validates: TPS mode, rate limiting, schema variants
   - Check: TPS values match target (200/400/600), latency charts, connection count in dashboard

2. **`scripts/dev/run_all_transaction_count.sh`** (~30 min)
   - Validates: Fixed-record mode, transaction splitting
   - Check: Total tx completed, TPS = tx/elapsed, connection count per step

3. **`scripts/dev/run_all_capacity.sh`** (~50 min)
   - Validates: Max-throughput mode (no -R)
   - Check: TPS not throttled, duration fixed (60/120 sec), connection count

### Phase 2: Combined script

4. **`scripts/dev/run_all.sh`** (~2–2.5 hours)
   - Validates: All 12 configs in sequence, no conflicts
   - Check: All runs appear in dashboard, labels correct, no duplicate run names

---

## What to Verify

### Scripts
- [ ] No errors or exit codes
- [ ] All 4 schema configs run per script (plain, index, fk, index_fk)
- [ ] Dashboard starts at end
- [ ] Run-root created with correct timestamp suffix

### Dashboard
- [ ] **Summary Comparison**: Run labels, TPS, p90/p95/p99, **clients** column
- [ ] **Connection Count chart**: Clients per step (bar chart)
- [ ] **Latency Breakdown**: Client vs server vs overhead
- [ ] **Server P50/P90/P95/P99**: yb_latency_histogram (if YugabyteDB 2.18.1+)
- [ ] **Latency Over Time**: pg_stat snapshots (if interval enabled)
- [ ] **Run Details table**: clients, jobs, duration_sec, target_tps, total_transactions
- [ ] **Per-operation charts**: TPS and latency p90/p95/p99 for select/insert/update/delete

### Reports
- [ ] `report.csv` has `clients` and `jobs` columns
- [ ] `summary.json` includes step-level clients/jobs
- [ ] `latency_histogram.csv` present when `log_transactions: true`

---

## Quick Validation (single config)

To validate without running the full suite:

```bash
# Run one config only (~10 min)
python3 -m ysqlload.cli --config config/dev/tps/plain.json --run-root runs/validation_test

# Start dashboard
python3 -m ysqlload.cli --serve-only --run-root runs/validation_test
```

Check: 4 runs (select, insert, update, delete), each with 3 steps. Connection count should show 8 clients for all steps.

---

## Prerequisites

- YugabyteDB running (e.g. Docker on port 5434)
- `pgbench` and `psql` in PATH
- `YB_TSERVER_METRICS` or `--tserver-url` for server metrics (optional but recommended)

Example:

```bash
bash scripts/dev/run_all_tps.sh \
  --run-root runs/validation_dev_tps_$(date +%Y%m%d) \
  --host 127.0.0.1 --port 5434 --user yugabyte --password "" \
  --tserver-url http://127.0.0.1:9001/metrics
```

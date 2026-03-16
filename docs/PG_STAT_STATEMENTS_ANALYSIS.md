# pg_stat_statements: Retention, Long Runs, and yb_latency_histogram

## Can pgbench alone split latency (network vs connection vs server)?

**No.** pgbench measures only **total round-trip time** per transaction from the client. It outputs a single `time_us` value per transaction. There is no way to decompose it into network, connection, and server execution from pgbench data alone.

**Approximation (without pg_stat_statements):** Run a trivial query (e.g. `SELECT 1`) many times and measure avg latency. That approximates network + connection + minimal server work. Then: `server_time ≈ transaction_latency - baseline`. This is rough and assumes the baseline matches real-query overhead. **pg_stat_statements is the reliable way** to get server-side execution time.

## 1. Does pg_stat_statements hold all details for 1-hour or multi-hour loads?

**Yes.** pg_stat_statements stores **cumulative** statistics. There is no time-based expiration.

### How it works

- **Persistence**: Data persists from the last `pg_stat_statements_reset()` (or from extension creation) until you reset again.
- **Aggregation**: Counts, total_time, mean_time, min_time, max_time, and `yb_latency_histogram` are **aggregated** over all executions in that period.
- **No need to poll**: For a 1-hour or 3-hour load, you can:
  1. Reset before the run
  2. Run the load
  3. Query once at the end

  You will get full aggregated stats for the entire run.

### Statement limit (pg_stat_statements.max)

- **Default**: 5000 distinct statements
- **Eviction**: When the limit is reached, the least-executed statements are evicted
- **Impact**: For typical workloads (e.g. SELECT/INSERT/UPDATE/DELETE on a few tables), you stay well under 5000 statements
- **Tuning**: Increase via `pg_stat_statements.max` in postgresql.conf if needed

### Do you need to retrieve every 5 seconds?

**No.** Polling every 5 seconds is only needed if you want **time-series** data (e.g. how P99 changed over the run). For that you would:

- Poll at intervals (e.g. every 30–60 seconds)
- Store each snapshot (or compute deltas)
- Build a time-series view

For **overall run statistics** (mean, P50, P90, P95, P99 for the whole run), a single query at the end is enough.

### Summary for long runs

| Goal | Approach |
|------|----------|
| Full run stats (mean, P99, etc.) | Reset before run, query once at end |
| Per-step stats (e.g. 200/400/600 TPS) | Reset before each step, query after each step (current behavior) |
| Time-series within one long step | Poll periodically (e.g. every 30–60 sec), store snapshots, compute deltas (advanced) |

### Periodic polling for latency-over-time (implemented)

Set `pg_stat_statements_interval_sec: 5` in config to poll every 5 seconds during each pgbench step. The tool will:

1. Reset pg_stat_statements before the step
2. Run pgbench in background
3. Poll every N seconds and record cumulative stats (mean, P50, P90, P95, P99)
4. Save to `pg_stat_statements_over_time.json` per step

Snapshots are **cumulative** (from step start). The dashboard "Latency Over Time" chart shows how server-side latency evolves during the run.

---

## 2. yb_latency_histogram

### Structure

- **Type**: JSONB
- **Format**: Array of `{ "[latency_low, latency_high)": count }` pairs
- **Example**: `[{"[0.1,0.2)": 4}, {"[0.2,0.3)": 2}]` = 4 executions in 0.1–0.2 ms, 2 in 0.2–0.3 ms

### yb_get_percentile

YugabyteDB provides `yb_get_percentile(histogram, percentile)` to compute percentiles from the histogram:

```sql
SELECT query, calls,
  yb_get_percentile(yb_latency_histogram, 50) as p50_ms,
  yb_get_percentile(yb_latency_histogram, 90) as p90_ms,
  yb_get_percentile(yb_latency_histogram, 95) as p95_ms,
  yb_get_percentile(yb_latency_histogram, 99) as p99_ms
FROM pg_stat_statements
WHERE query LIKE '%FROM t%';
```

### Availability

- Requires YugabyteDB 2.18.1+ or 2.19.1+
- Not available in vanilla PostgreSQL

### Integration in this toolkit

The tool stores P50/P90/P95/P99 from `yb_get_percentile` per step. The raw
histogram is not stored (it can be large). To capture it, query
`pg_stat_statements` directly after a run.

---

## 3. Comparison: pgbench vs pg_stat_statements

| Aspect | pgbench (-l logs) | pg_stat_statements |
|--------|-------------------|---------------------|
| **Scope** | Client round-trip | Server execution |
| **Percentiles** | From transaction log | From yb_latency_histogram (YugabyteDB) |
| **Retention** | Per-run log files | Cumulative until reset |
| **Long runs** | Full log, compute at end | Single query at end |
| **Time-series** | Per-transaction timestamps | Requires periodic polling |

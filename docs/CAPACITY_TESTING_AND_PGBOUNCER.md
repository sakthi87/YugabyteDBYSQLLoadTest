# Capacity Testing, Connection Reuse, and PgBouncer

This guide covers how to run capacity tests, minimize client overhead, use connection reuse, and set up PgBouncer for YugabyteDB load testing.

---

## 1. Co-location (Your Plan)

**Run pgbench on a VM in the same VPC/region as YugabyteDB.**

- **Stretch Cluster**: Leaders in Central → run pgbench VM in Azure Central
- **XCluster**: Active region Central → run pgbench VM in Azure Central

This minimizes network latency and reduces the "overhead" component in the Latency Breakdown chart.

---

## 2. Clients & Jobs Scaling

The runner now supports **per-step clients and jobs**. Rule of thumb:

| Target TPS | Clients | Jobs |
|------------|---------|------|
| 1,000      | 32      | 4   |
| 2,000      | 64      | 8   |
| 5,000      | 128     | 8   |
| 8,000      | 192     | 8   |
| 10,000     | 256     | 8   |

Formula: `clients ≥ target_tps × avg_latency_sec` (with 2–4× headroom).  
`jobs` should be ≤ `clients` and typically ≤ CPU count.

**Config example** (`config/production/tps/plain.json`):

```json
"ramp": [
  { "duration_sec": 60, "target_tps": 1000, "clients": 32, "jobs": 4 },
  { "duration_sec": 60, "target_tps": 10000, "clients": 256, "jobs": 8 }
]
```

---

## 3. TPS vs Records (Transaction-Based) Mode

### TPS mode (rate-limited, with sleep/wake)

- Uses `-R <target_tps>` → pgbench throttles to that TPS
- Adds sleep/wake cycles and can increase latency variance
- Use for: sustained load at a fixed rate

### Records / transaction-based mode (no sleep/wake)

- Uses `-t <transactions_per_client>` or `total_transactions`
- No `-R` → pgbench runs at maximum speed
- No sleep/wake cycles
- Use for: capacity testing, fixed-record runs

**Config examples:**

```json
// Run 50,000 total transactions (split across clients)
{ "total_transactions": 50000, "clients": 64, "jobs": 8 }

// Run for 120 seconds at max speed (capacity test)
{ "duration_sec": 120, "clients": 64, "jobs": 8 }
```

Use `config/scenario_capacity.json` for capacity and record-based tests.

---

## 3a. Transaction Count-Based (Detailed)

**Config:** `{ "total_transactions": 50000, "clients": 64, "jobs": 8 }`  
**pgbench flag:** `-t 782` (per client)

### How it works

- You specify a **fixed total number of transactions** to run.
- The runner divides this across clients: `transactions_per_client = ceil(total_transactions / clients)`.
- Example: 50,000 total ÷ 64 clients → 782 per client (50,000 ÷ 64 = 781.25, ceiling = 782).
- pgbench is invoked with `-t 782` (or 781 depending on rounding). Each client runs that many transactions, then exits.
- **No `-R` (rate limit)** → pgbench runs as fast as it can. No sleep/wake between transactions.

### When to use

- **Fixed workload size**: e.g. "run exactly 10,000 inserts" or "50,000 selects".
- **Reproducible runs**: same number of transactions every time.
- **No sleep/wake**: avoids rate-limiting overhead and latency spikes from throttling.

### Duration

- Duration is **not fixed**; it depends on cluster speed.
- Faster cluster → shorter run. Slower cluster → longer run.
- TPS = total_transactions ÷ actual_duration_sec (reported by pgbench).

---

## 3b. Capacity (Duration, Max Speed) (Detailed)

**Config:** `{ "duration_sec": 120, "clients": 64, "jobs": 8 }`  
**pgbench flag:** `-T 120` (no `-R`)

### How it works

- You specify a **fixed duration** in seconds.
- pgbench runs for exactly that long at **maximum throughput**.
- **No `-R`** → no rate limit. pgbench sends transactions as fast as the cluster can handle them.
- No sleep/wake cycles; clients stay busy.

### When to use

- **Capacity testing**: "What is the max TPS this cluster can sustain for 2 minutes?"
- **Stress testing**: push the cluster to its limit for a known time.
- **Throughput baseline**: measure raw throughput without artificial throttling.

### Comparison with TPS mode

| Aspect        | Capacity (`-T` only)     | TPS mode (`-T` + `-R`)      |
|---------------|--------------------------|-----------------------------|
| Rate limit    | None                     | Throttled to target TPS      |
| Sleep/wake    | No                       | Yes (at low TPS)            |
| Duration      | Fixed                    | Fixed                       |
| Transaction count | Variable (depends on speed) | Approximately fixed     |
| Use case      | Max throughput           | Sustained load at fixed rate |

---

## 4. Connection Reuse

**pgbench reuses connections by default.** Each client keeps one connection open.

- Do **not** use `-C` (connect per transaction) — that would create a new connection for every transaction.
- The runner does **not** use `-C`, so connection reuse is already enabled.

**Verification:** Check pgbench logs; connection setup should happen once per client at startup, not per transaction.

---

## 5. PgBouncer

### What is PgBouncer?

PgBouncer is a **connection pooler** that sits between clients and PostgreSQL/YugabyteDB:

```
pgbench → PgBouncer → YugabyteDB
```

- Clients connect to PgBouncer
- PgBouncer keeps a pool of connections to the DB
- Many client connections map to fewer DB connections

### Benefits

- Fewer connections to the DB (avoids `max_connections` limits)
- Connection reuse across clients
- Can reduce connection setup overhead when many clients connect

### Does it add latency?

- Adds one hop (client → PgBouncer → DB)
- If PgBouncer is co-located with the DB, extra latency is usually sub-millisecond
- Often improves throughput when you have many clients

### Setup (Docker)

```bash
# Create pgbouncer.ini
cat > pgbouncer.ini << 'EOF'
[databases]
yb_load_test = host=YUGABYTE_HOST port=5433 dbname=yb_load_test

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 50
EOF

# Create userlist.txt (md5 of password)
# echo "yugabyte" | md5sum  -> use in userlist
echo '"yugabyte" "md5<your_md5_hash>"' > userlist.txt

# Run PgBouncer
docker run -d --name pgbouncer \
  -p 6432:6432 \
  -v $(pwd)/pgbouncer.ini:/etc/pgbouncer/pgbouncer.ini \
  -v $(pwd)/userlist.txt:/etc/pgbouncer/userlist.txt \
  edoburu/pgbouncer
```

### Use with load test

Point the config at PgBouncer instead of YugabyteDB:

```bash
export YB_HOST=pgbouncer-host
export YB_PORT=6432
python3 -m ysqlload.cli --config config/production/tps/plain.json --run-root runs/prod_run
```

---

## 6. Implementation Steps for Stretch & XCluster

### Phase 1: Prepare

1. **VM in Central**  
   - Create a VM in the same VPC as YugabyteDB (Azure Central)
2. **Install tools**  
   - pgbench, psql, Python 3
3. **Clone repo**  
   - Copy the YSQL Load Test project to the VM

### Phase 2: Run capacity tests (Stretch Cluster)

1. Set env vars:
   ```bash
   export YB_HOST=<stretch-cluster-ysql-endpoint>
   export YB_PORT=5433
   export YB_TSERVER_METRICS=http://<tserver>:9000/metrics
   ```
2. Run capacity test (max throughput, no rate limit):
   ```bash
   python3 -m ysqlload.cli --config config/scenario_capacity.json --run-root runs/stretch_capacity
   ```
3. Run production TPS test (1K–10K):
   ```bash
   python3 -m ysqlload.cli --config config/production/tps/plain.json --run-root runs/stretch_production
   ```

### Phase 3: Run capacity tests (XCluster)

1. Point to the **active** (Central) cluster
2. Run the same configs as above
3. **Monitor replication lag** during the run:
   - YugabyteDB metrics: `async_replication_sent_lag_micros`
   - Or query `yb_servers()` / replication status

### Phase 4: Find replication lag threshold (XCluster)

1. Run production config with increasing TPS (1K → 2K → 5K → 8K → 10K)
2. For each step, record:
   - Achieved TPS
   - Replication lag (micros or ms)
3. Identify the TPS where lag starts to grow
4. Use that as the capacity limit for the consumer

### Phase 5: Optional PgBouncer

1. Deploy PgBouncer in the same VPC as YugabyteDB
2. Configure it to connect to the YSQL endpoint
3. Point pgbench at PgBouncer (port 6432)
4. Re-run tests and compare latency/throughput

---

## 7. Config Reference

| Ramp field             | Description                                      |
|------------------------|--------------------------------------------------|
| `duration_sec`         | Run for N seconds                               |
| `target_tps`           | Rate limit to N TPS (omit for max throughput)   |
| `total_transactions`   | Run exactly N transactions (no rate limit)      |
| `transactions_per_client` | N transactions per client                    |
| `clients`              | Number of pgbench clients                       |
| `jobs`                 | Number of pgbench worker threads                |

**Modes:**

- **Rate-limited**: `duration_sec` + `target_tps` → `-T` + `-R`
- **Capacity**: `duration_sec` only → `-T` (no `-R`)
- **Records**: `total_transactions` → `-t` (no `-T`, no `-R`)

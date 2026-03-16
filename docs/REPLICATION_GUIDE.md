# Replication Guide: Validation → Dev → Production

When you change validation configs or scripts and want to replicate those changes to dev and production, use this guide.

---

## Config Structure Mapping

| Validation | Dev | Production |
|------------|-----|------------|
| `config/validation/tps/plain.json` | `config/dev/tps/plain.json` | `config/production/tps/plain.json` |
| `config/validation/tps/index.json` | `config/dev/tps/index.json` | `config/production/tps/index.json` |
| `config/validation/transaction_count/plain.json` | `config/dev/transaction_count/plain.json` | `config/production/transaction_count/plain.json` |
| `config/validation/transaction_count/index.json` | `config/dev/transaction_count/index.json` | `config/production/transaction_count/index.json` |
| `config/validation/capacity/plain.json` | `config/dev/capacity/plain.json` | `config/production/capacity/plain.json` |
| `config/validation/capacity/index.json` | `config/dev/capacity/index.json` | `config/production/capacity/index.json` |
| `config/validation/capacity/fk.json` | `config/dev/capacity/fk.json` | `config/production/capacity/fk.json` |
| `config/validation/capacity/index_fk.json` | `config/dev/capacity/index_fk.json` | `config/production/capacity/index_fk.json` |
| `config/validation/tps/fk.json` | `config/dev/tps/fk.json` | `config/production/tps/fk.json` |
| `config/validation/tps/index_fk.json` | `config/dev/tps/index_fk.json` | `config/production/tps/index_fk.json` |
| `config/validation/transaction_count/fk.json` | `config/dev/transaction_count/fk.json` | `config/production/transaction_count/fk.json` |
| `config/validation/transaction_count/index_fk.json` | `config/dev/transaction_count/index_fk.json` | `config/production/transaction_count/index_fk.json` |

**Note:** Validation has all 4 schemas (plain, index, fk, index_fk), matching dev and production.

---

## What to Replicate

### From validation configs
- **Schema paths** (`schema_sql_file`, `preload_sql_file`) — adjust `../` depth for dev/production (`../../../scripts/`)
- **Phase structure** (names, script paths, ramp shape)
- **Server metrics** (pg_stat_statements, interval)
- **New phases or operations**

### Do NOT blindly copy
- **Ramp values** — validation uses short durations (20 sec, 1K/2K tx). Dev/production use full values (30–120 sec, 10K–200K tx).
- **run_label** — keep environment-specific labels

---

## Replication Workflow

### 1. Change validation first
Edit `config/validation/{mode}/{schema}.json` and run:

```bash
bash scripts/validation/run_all.sh --run-root runs/validation_test
```

Verify the change works (~30 min).

### 2. Replicate to dev
For each changed validation config, update the corresponding dev config:

```bash
# Example: you changed validation/tps/plain.json phase structure
# Update dev/tps/plain.json with same structure, but restore dev ramp values:
# - TPS: 30+30+60 sec, 200/400/600 target_tps
# - Transaction count: 10K/20K/50K, clients 8/16/32
# - Capacity: 60+120 sec, clients 8/16
```

Copy the **structure** (phases, scripts, server_metrics), then restore **dev ramp values** from the table below.

### 3. Replicate to production
Same as dev, but use **production ramp values**:

| Mode | Dev ramp | Production ramp |
|------|----------|-----------------|
| TPS | 30+30+60 sec, 200/400/600 TPS | 60 sec × 5 steps, 1K–10K TPS, clients 32–256 |
| Transaction count | 10K/20K/50K, clients 8/16/32 | 50K/100K/200K, clients 32/64/128 |
| Capacity | 60+120 sec, clients 8/16 | 60+120+120 sec, clients 64/128/256 |

### 4. Replicate to fk and index_fk
If you added a new phase or changed structure, replicate to `fk.json` and `index_fk.json` in dev and production, using the appropriate schema paths (`schema_fk.sql`, `schema_index_fk.sql`).

---

## Script Replication

Validation uses one script: `scripts/validation/run_all.sh`.

Dev and production have:
- `run_all_tps.sh`
- `run_all_transaction_count.sh`
- `run_all_capacity.sh`
- `run_all.sh` (all modes)

If you change **script logic** (e.g. new CLI flag, env handling) in `scripts/validation/run_all.sh`, replicate to:
1. `scripts/dev/run_all_tps.sh` (and transaction_count, capacity, run_all)
2. `scripts/production/run_all_tps.sh` (and transaction_count, capacity, run_all)

The scripts share the same structure; only the `configs` array and default `run_root` suffix differ.

---

## Quick Reference: Path Depths

| Config location | Schema/script path |
|-----------------|--------------------|
| `config/validation/tps/` | `../../../scripts/` |
| `config/dev/tps/` | `../../../scripts/` |
| `config/production/tps/` | `../../../scripts/` |

All nested configs use `../../../scripts/scenarios/` and `../../../scripts/pgbench10/` to reach project root.

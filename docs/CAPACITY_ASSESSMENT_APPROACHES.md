# YugabyteDB Capacity Assessment: pgbench vs PgBouncer vs App Drivers

This document compares three approaches for YugabyteDB cluster capacity assessment (Stretch Cluster and XCluster). Use it to plan what to evaluate and what each approach cannot measure.

---

## 1. pgbench (Direct to YugabyteDB)

| What you can evaluate | What you cannot evaluate |
|-----------------------|---------------------------|
| **Raw DB throughput** (TPS) | App-level latency (network from app to DB) |
| **Server-side latency** (pg_stat_statements) | Connection pooling behavior |
| **Latency distribution** (P50/P90/P95/P99) | Smart Driver load balancing |
| **Per-operation performance** (select, insert, update, delete) | Multi-region routing (topology awareness) |
| **Schema impact** (plain vs index vs FK) | Session/transaction pooling trade-offs |
| **Capacity at high connection count** (up to max_connections) | Production-like connection patterns |
| **Stretch Cluster:** Leader-region performance | Stretch: cross-region latency from app perspective |
| **XCluster:** Active-region performance | XCluster: failover behavior |

**Best for:** Baseline DB capacity, schema and workload impact, stress testing with many connections.

---

## 2. pgbench + PgBouncer

| What you can evaluate | What you cannot evaluate |
|-----------------------|---------------------------|
| **DB throughput with pooling** | Raw DB capacity without pooling |
| **Pool sizing impact** (pool_size vs TPS/latency) | Smart Driver behavior |
| **Connection limit behavior** (avoiding max_connections) | Topology-aware routing |
| **Pool contention** (wait time when pool is saturated) | App driver overhead |
| **Stretch Cluster:** Performance through a single pooler endpoint | Stretch: per-region connection distribution |
| **XCluster:** Performance through pooler | XCluster: failover with app drivers |
| **Production-like connection pattern** (many clients, few DB conns) | Exact app stack behavior |

**Best for:** Production-style connection counts, pool sizing, impact of pooling on TPS and latency.

---

## 3. App Drivers (Smart Driver, JDBC, etc.)

| What you can evaluate | What you cannot evaluate |
|-----------------------|---------------------------|
| **End-to-end app latency** (app → DB → app) | Pure DB capacity (includes driver/network) |
| **Smart Driver load balancing** (cluster-aware) | Isolated DB performance |
| **Topology-aware routing** (Stretch: nearest region) | pgbench-style raw TPS |
| **Read replica routing** (primary vs RR) | PgBouncer interaction |
| **Stretch Cluster:** Cross-region latency from app perspective | Stretch: DB-only latency |
| **XCluster:** Failover and routing behavior | XCluster: DB-only metrics |
| **Real app stack** (ORM, connection pool, driver) | Schema-only impact (mixed with app logic) |

**Best for:** Production-like app behavior, topology and failover, real-world latency.

---

## Comparison Matrix

| Evaluation goal | pgbench | pgbench + PgBouncer | App drivers |
|-----------------|---------|---------------------|-------------|
| Raw DB TPS capacity | ✅ | ⚠️ (through pool) | ❌ (mixed with app) |
| DB latency (server-side) | ✅ | ✅ | ⚠️ (includes app) |
| Connection limit behavior | ✅ | ✅ | ⚠️ (depends on app pool) |
| Pool sizing impact | ❌ | ✅ | ⚠️ (app pool) |
| Smart Driver load balancing | ❌ | ❌ | ✅ |
| Topology-aware routing | ❌ | ❌ | ✅ |
| Stretch: leader-region DB perf | ✅ | ✅ | ⚠️ |
| Stretch: cross-region from app | ❌ | ❌ | ✅ |
| XCluster: active-region DB perf | ✅ | ✅ | ⚠️ |
| XCluster: failover behavior | ❌ | ❌ | ✅ |
| Schema impact (plain/index/FK) | ✅ | ✅ | ⚠️ |
| Setup complexity | Low | Medium | High |

---

## Recommended Assessment Plan

### Phase 1: DB baseline (pgbench direct)

- Run pgbench directly to YugabyteDB.
- Measure raw TPS, server latency, schema impact.
- Use for Stretch (leader region) and XCluster (active region).
- Outcome: DB capacity and latency baseline.

### Phase 2: Pooling behavior (pgbench + PgBouncer)

- Add PgBouncer in front of YugabyteDB.
- Use high client counts (e.g. 256) with moderate pool sizes (e.g. 50–100).
- Compare TPS and latency vs Phase 1.
- Outcome: Pool sizing and impact of pooling.

### Phase 3: Production-like behavior (app drivers)

- Use your app stack (Smart Driver, connection pool, ORM).
- Measure end-to-end latency and throughput.
- For Stretch: topology-aware routing to nearest region.
- For XCluster: failover and routing behavior.
- Outcome: Production-like capacity and latency.

---

## Stretch vs XCluster Focus

| Scenario | pgbench | pgbench + PgBouncer | App drivers |
|----------|---------|---------------------|-------------|
| **Stretch Cluster** | DB capacity in leader region | DB capacity with pooling | Cross-region routing, latency from app |
| **XCluster** | DB capacity in active region | DB capacity with pooling | Failover, routing, app-level latency |

---

## Summary

- **pgbench:** Isolated DB capacity and latency.
- **pgbench + PgBouncer:** DB capacity with connection pooling and pool sizing.
- **App drivers:** Production-like behavior, topology, and failover.

Use all three in sequence: pgbench for baseline, PgBouncer for pooling, app drivers for production behavior.

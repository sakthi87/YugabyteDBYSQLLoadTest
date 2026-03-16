import json
import math
import os
import re
import subprocess
import threading
import time

from ysqlload.metrics import capture_metrics
from ysqlload.report import generate_reports
from ysqlload.replication_metrics import (
    fetch_replication_lag_ms,
    poll_replication_lag,
    aggregate_lag_snapshot,
)


def _timestamp():
    return time.strftime("%Y%m%d-%H%M%S")


def _run_command(cmd, env, log_path, dry_run=False, cwd=None):
    if dry_run:
        return {"cmd": cmd, "exit_code": 0, "stdout_tail": "", "stderr_tail": ""}

    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.run(
            cmd,
            env=env,
            cwd=cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

    return {"cmd": cmd, "exit_code": proc.returncode}


def _run_pgbench_with_polling(
    cmd, env, log_path, cwd, db, dbname, poll_interval_sec,
    replication_urls=None, replication_interval_sec=0,
):
    """
    Run pgbench in background and poll pg_stat_statements every poll_interval_sec.
    Optionally poll replication lag when replication_urls and replication_interval_sec set.
    Returns (result_dict, snapshots_list, replication_snapshots_list).
    """
    snapshots = []
    replication_snapshots = []
    stop_polling = threading.Event()
    poll_replication = bool(replication_urls and replication_interval_sec > 0)
    rep_interval = replication_interval_sec or poll_interval_sec

    def poll_loop():
        rep_counter = 0
        while not stop_polling.is_set():
            stats = _query_pg_stat_statements(db, dbname, env, reset_before=False)
            if stats:
                snapshots.append({
                    "elapsed_sec": int(time.time() - start_time),
                    "mean_ms": stats.get("mean_exec_time_ms"),
                    "min_ms": stats.get("min_exec_time_ms"),
                    "max_ms": stats.get("max_exec_time_ms"),
                    "calls": stats.get("calls"),
                    "yb_p50_ms": stats.get("yb_p50_ms"),
                    "yb_p90_ms": stats.get("yb_p90_ms"),
                    "yb_p95_ms": stats.get("yb_p95_ms"),
                    "yb_p99_ms": stats.get("yb_p99_ms"),
                })
            if poll_replication and rep_counter % max(1, rep_interval // max(1, poll_interval_sec)) == 0:
                lag = fetch_replication_lag_ms(replication_urls, timeout_sec=3)
                replication_snapshots.append({
                    "elapsed_sec": int(time.time() - start_time),
                    "timestamp": int(time.time()),
                    "lag_ms": round(lag, 2) if lag is not None else None,
                })
            rep_counter += 1
            for _ in range(poll_interval_sec):
                if stop_polling.wait(timeout=1):
                    return

    start_time = time.time()
    poller = threading.Thread(target=poll_loop, daemon=True)
    poller.start()

    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.run(
            cmd,
            env=env,
            cwd=cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

    stop_polling.set()
    poller.join(timeout=poll_interval_sec + 2)

    # Final snapshot
    stats = _query_pg_stat_statements(db, dbname, env, reset_before=False)
    if stats:
        snapshots.append({
            "elapsed_sec": int(time.time() - start_time),
            "mean_ms": stats.get("mean_exec_time_ms"),
            "min_ms": stats.get("min_exec_time_ms"),
            "max_ms": stats.get("max_exec_time_ms"),
            "calls": stats.get("calls"),
            "yb_p50_ms": stats.get("yb_p50_ms"),
            "yb_p90_ms": stats.get("yb_p90_ms"),
            "yb_p95_ms": stats.get("yb_p95_ms"),
            "yb_p99_ms": stats.get("yb_p99_ms"),
        })
    if poll_replication:
        lag = fetch_replication_lag_ms(replication_urls, timeout_sec=3)
        replication_snapshots.append({
            "elapsed_sec": int(time.time() - start_time),
            "timestamp": int(time.time()),
            "lag_ms": round(lag, 2) if lag is not None else None,
        })

    return {"cmd": cmd, "exit_code": proc.returncode}, snapshots, replication_snapshots


def _run_psql_query(db, dbname, sql, env):
    """Run psql -t -A and return (stdout, exit_code)."""
    cmd = [
        "psql",
        "-h", str(db["host"]),
        "-p", str(db["port"]),
        "-U", str(db["user"]),
        "-d", dbname,
        "-t", "-A",
        "-c", sql,
    ]
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.stdout or "").strip(), proc.returncode


def _query_pg_stat_statements(db, dbname, env, reset_before=False):
    """
    Query pg_stat_statements for server-side execution time of our workload (t1-t10).
    Returns dict with mean/min/max, calls, and optionally yb_latency_histogram percentiles (YugabyteDB).
    Requires: CREATE EXTENSION pg_stat_statements; (and superuser for reset).
    """
    if reset_before:
        _, code = _run_psql_query(db, dbname, "SELECT pg_stat_statements_reset();", env)
        if code != 0:
            return None  # reset may need superuser
    # PostgreSQL 14+ / YugabyteDB: total_exec_time, min_exec_time, max_exec_time
    sql = """
    SELECT json_build_object(
      'mean', COALESCE(SUM(total_exec_time)::float / NULLIF(SUM(calls), 0), 0),
      'min', COALESCE(MIN(min_exec_time), 0),
      'max', COALESCE(MAX(max_exec_time), 0),
      'calls', COALESCE(SUM(calls), 0)::bigint
    )::text
    FROM pg_stat_statements
    WHERE (query LIKE '%FROM t%' OR query LIKE '%INTO t%' OR query LIKE '%UPDATE t%' OR query LIKE '%DELETE FROM t%')
      AND query NOT LIKE '%pg_stat_statements%'
    """
    out, code = _run_psql_query(db, dbname, sql, env)
    if code != 0 or not out:
        return None
    result = None
    try:
        data = json.loads(out)
        result = {
            "mean_exec_time_ms": round(float(data.get("mean", 0)), 3),
            "min_exec_time_ms": round(float(data.get("min", 0)), 3),
            "max_exec_time_ms": round(float(data.get("max", 0)), 3),
            "calls": int(data.get("calls", 0)),
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        return None

    # YugabyteDB: yb_latency_histogram + yb_get_percentile for P50/P90/P95/P99 (dominant query by calls)
    sql_hist = """
    WITH top AS (
      SELECT yb_latency_histogram
      FROM pg_stat_statements
      WHERE (query LIKE '%FROM t%' OR query LIKE '%INTO t%' OR query LIKE '%UPDATE t%' OR query LIKE '%DELETE FROM t%')
        AND query NOT LIKE '%pg_stat_statements%'
        AND yb_latency_histogram IS NOT NULL
      ORDER BY calls DESC
      LIMIT 1
    )
    SELECT json_build_object(
      'p50', yb_get_percentile(yb_latency_histogram, 50),
      'p90', yb_get_percentile(yb_latency_histogram, 90),
      'p95', yb_get_percentile(yb_latency_histogram, 95),
      'p99', yb_get_percentile(yb_latency_histogram, 99),
      'histogram', yb_latency_histogram
    )::text
    FROM top
    """
    out_hist, code_hist = _run_psql_query(db, dbname, sql_hist, env)
    if code_hist == 0 and out_hist:
        try:
            hist_data = json.loads(out_hist)
            result["yb_p50_ms"] = _round_safe(hist_data.get("p50"))
            result["yb_p90_ms"] = _round_safe(hist_data.get("p90"))
            result["yb_p95_ms"] = _round_safe(hist_data.get("p95"))
            result["yb_p99_ms"] = _round_safe(hist_data.get("p99"))
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            pass
    return result


def _round_safe(val):
    if val is None:
        return None
    try:
        f = float(val)
        if not math.isfinite(f):
            return None  # inf, -inf, nan -> null in JSON
        return round(f, 3)
    except (ValueError, TypeError):
        return None


def _parse_pgbench_stats(log_path):
    tps = None
    tps_excluding = None
    latency_avg_ms = None
    latency_stddev_ms = None
    tps_re = re.compile(r"^tps = ([0-9.]+)")
    tps_excl_re = re.compile(r"^tps = ([0-9.]+) \((excluding connections establishing)\)")
    lat_avg_re = re.compile(r"^latency average = ([0-9.]+) ms")
    lat_std_re = re.compile(r"^latency stddev = ([0-9.]+) ms")
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            match = tps_re.search(stripped)
            if match:
                tps = float(match.group(1))
            match = tps_excl_re.search(stripped)
            if match:
                tps_excluding = float(match.group(1))
            match = lat_avg_re.search(stripped)
            if match:
                latency_avg_ms = float(match.group(1))
            match = lat_std_re.search(stripped)
            if match:
                latency_stddev_ms = float(match.group(1))
    return {
        "tps": tps,
        "tps_excluding": tps_excluding,
        "latency_avg_ms": latency_avg_ms,
        "latency_stddev_ms": latency_stddev_ms,
    }


def _compute_percentiles(values, percentiles):
    if not values:
        return {}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    results = {}
    for pct in percentiles:
        if n == 1:
            results[pct] = sorted_vals[0]
            continue
        rank = pct * (n - 1)
        lower = int(rank)
        upper = min(lower + 1, n - 1)
        weight = rank - lower
        value = sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight
        results[pct] = value
    return results


def _extract_latency_samples(log_dir):
    samples = []
    for name in os.listdir(log_dir):
        if not name.startswith("pgbench_log"):
            continue
        path = os.path.join(log_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                values = _parse_pgbench_log_line(line)
                if values:
                    samples.append(values)
    return samples


def _parse_pgbench_log_line(line):
    """Parse pgbench -l log line. Format: client_id transaction_no time_us script_no time_epoch time_us [schedule_lag]
    Column 2 = transaction elapsed time in MICROSECONDS. Column 4 = Unix epoch (seconds)."""
    parts = line.strip().split()
    if len(parts) < 6:
        return None
    try:
        ints = [int(p) for p in parts]
    except ValueError:
        return None  # skip "skipped", "failed", etc.

    # Per PostgreSQL docs: col 0=client_id, 1=transaction_no, 2=latency_us, 3=script_no, 4=time_epoch, 5=time_us
    latency_us = ints[2]
    time_sec = ints[4]
    if not (0 <= latency_us <= 60_000_000):  # 0 to 60 sec max
        return None
    return {"time_sec": time_sec, "latency_us": latency_us}


def _parse_pgbench_latency_logs(log_dir):
    samples = _extract_latency_samples(log_dir)
    latencies_ms = [s["latency_us"] / 1000.0 for s in samples]
    pct_values = _compute_percentiles(latencies_ms, [0.50, 0.90, 0.95, 0.99])
    return {
        "latency_samples": len(latencies_ms),
        "latency_p50_ms": pct_values.get(0.50),
        "latency_p90_ms": pct_values.get(0.90),
        "latency_p95_ms": pct_values.get(0.95),
        "latency_p99_ms": pct_values.get(0.99),
    }


def _write_latency_histogram(log_dir, output_path):
    samples = _extract_latency_samples(log_dir)
    buckets = {}
    for sample in samples:
        sec = sample["time_sec"]
        buckets.setdefault(sec, []).append(sample["latency_us"] / 1000.0)

    lines = ["epoch_sec,count,avg_ms,p50_ms,p95_ms,p99_ms"]
    for sec in sorted(buckets.keys()):
        vals = buckets[sec]
        avg = sum(vals) / len(vals) if vals else 0.0
        pcts = _compute_percentiles(vals, [0.50, 0.95, 0.99])
        lines.append(
            f"{sec},{len(vals)},{avg:.3f},"
            f"{_fmt(pcts.get(0.50))},{_fmt(pcts.get(0.95))},{_fmt(pcts.get(0.99))}"
        )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _fmt(value):
    if value is None:
        return ""
    return f"{value:.3f}"


def _list_pgbench_logs(log_dir):
    files = []
    for name in os.listdir(log_dir):
        if name.startswith("pgbench_log"):
            files.append(os.path.join(log_dir, name))
    return sorted(files)


def run_all(config, run_root, dry_run=False):
    run_dir = os.path.join(run_root, _timestamp())
    os.makedirs(run_dir, exist_ok=True)

    db = config["db"]
    schema = config["schema"]
    phases = config["phases"]
    server_metrics = config.get("server_metrics", {})
    cluster = config.get("cluster", {})
    summary = {
        "run_dir": run_dir,
        "run_label": config.get("run_label", ""),
        "run_description": config.get("run_description", ""),
        "cluster_type": cluster.get("cluster_type", "stretch"),
        "cluster_topology": cluster.get("cluster_topology", ""),
        "replication_mode": cluster.get("replication_mode", "none"),
        "xcluster_enabled": bool(cluster.get("xcluster_enabled", False)),
        "phases": [],
        "schema": {},
    }

    base_env = os.environ.copy()
    if db.get("password"):
        base_env["PGPASSWORD"] = db["password"]

    if schema.get("drop_db"):
        summary["schema"]["drop_db"] = _run_psql_command(
            db,
            db["admin_dbname"],
            f"DROP DATABASE IF EXISTS {db['dbname']};",
            run_dir,
            base_env,
            "drop_db",
            dry_run,
        )

    if schema.get("create_db"):
        summary["schema"]["create_db"] = _run_psql_command(
            db,
            db["admin_dbname"],
            f"CREATE DATABASE {db['dbname']};",
            run_dir,
            base_env,
            "create_db",
            dry_run,
        )

    if schema.get("schema_sql_file"):
        summary["schema"]["schema_sql_file"] = _run_psql_file(
            db,
            db["dbname"],
            schema["schema_sql_file"],
            run_dir,
            base_env,
            "schema_sql",
            dry_run,
        )

    if schema.get("preload_sql_file"):
        summary["schema"]["preload_sql_file"] = _run_psql_file(
            db,
            db["dbname"],
            schema["preload_sql_file"],
            run_dir,
            base_env,
            "preload_sql",
            dry_run,
        )

    for phase in phases:
        phase_type = phase.get("type")
        name = phase.get("name", phase_type or "phase")
        if phase_type == "pgbench" and (
            server_metrics.get("tserver_urls")
            or server_metrics.get("pg_stat_statements")
            or server_metrics.get("pg_stat_statements_interval_sec")
        ):
            phase.setdefault("server_metrics", server_metrics)
        if phase_type == "pgbench":
            result = _run_pgbench_phase(db, phase, run_dir, base_env, dry_run, config)
        elif phase_type == "http":
            result = _run_http_phase(phase, run_dir, base_env, dry_run)
        else:
            result = {"name": name, "type": phase_type, "error": "unknown phase type"}
        summary["phases"].append(result)

    summary_path = os.path.join(run_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    latest_path = os.path.join(run_root, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump({"latest": os.path.basename(run_dir)}, f, indent=2)

    generate_reports(
        summary,
        run_dir,
        enabled_csv=config.get("reports", {}).get("csv", True),
        enabled_html=config.get("reports", {}).get("html", True),
    )

    return summary


def _run_psql_command(db, dbname, sql, run_dir, env, label, dry_run):
    log_path = os.path.join(run_dir, f"{label}.log")
    cmd = [
        "psql",
        "-h",
        str(db["host"]),
        "-p",
        str(db["port"]),
        "-U",
        str(db["user"]),
        "-d",
        str(dbname),
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    ]
    result = _run_command(cmd, env, log_path, dry_run=dry_run)
    result.update({"label": label, "log": log_path})
    return result


def _run_psql_file(db, dbname, sql_file, run_dir, env, label, dry_run):
    log_path = os.path.join(run_dir, f"{label}.log")
    cmd = [
        "psql",
        "-h",
        str(db["host"]),
        "-p",
        str(db["port"]),
        "-U",
        str(db["user"]),
        "-d",
        str(dbname),
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        sql_file,
    ]
    result = _run_command(cmd, env, log_path, dry_run=dry_run)
    result.update({"label": label, "log": log_path, "sql_file": sql_file})
    return result


def _run_pgbench_phase(db, phase, run_dir, env, dry_run, config=None):
    name = phase.get("name", "pgbench")
    steps = []
    ramp = phase.get("ramp", [])
    tx_per_client = phase.get("transactions_per_client")
    total_tx = phase.get("total_transactions")

    if ramp and (tx_per_client or total_tx):
        raise ValueError("ramp is not compatible with transactions_per_client/total_transactions")

    if tx_per_client or total_tx:
        clients = int(phase.get("clients", 1))
        if tx_per_client is None and total_tx is not None:
            tx_per_client = max(1, (int(total_tx) + clients - 1) // clients)
        tps_label = f"{tx_per_client}tpc"
        steps.append(
            {
                "name": f"{name}_{tps_label}",
                "duration_sec": None,
                "target_tps": phase.get("target_tps"),
                "transactions_per_client": int(tx_per_client),
                "total_transactions": int(total_tx) if total_tx is not None else None,
            }
        )
    elif ramp:
        for idx, step in enumerate(ramp, start=1):
            target_tps = step.get("target_tps", phase.get("target_tps"))
            total_tx = step.get("total_transactions")
            tx_per_client = step.get("transactions_per_client")
            clients = step.get("clients", phase.get("clients", 8))
            jobs = step.get("jobs", phase.get("jobs", 2))
            if total_tx and not tx_per_client:
                tx_per_client = max(1, (int(total_tx) + clients - 1) // clients)
            if total_tx or tx_per_client:
                label = f"{total_tx or tx_per_client * clients}tx"
            elif target_tps is not None:
                label = f"{target_tps}tps"
            else:
                label = f"capacity_step{idx}"
            steps.append(
                {
                    "name": f"{name}_{label}",
                    "duration_sec": step.get("duration_sec"),
                    "target_tps": target_tps,
                    "transactions_per_client": int(tx_per_client) if tx_per_client else None,
                    "total_transactions": int(total_tx) if total_tx else None,
                    "clients": clients,
                    "jobs": jobs,
                }
            )
    else:
        steps.append(
            {
                "name": name,
                "duration_sec": phase.get("duration_sec", 60),
                "target_tps": phase.get("target_tps"),
            }
        )

    results = []
    for step in steps:
        step_dir = os.path.join(run_dir, step["name"])
        os.makedirs(step_dir, exist_ok=True)
        log_path = os.path.join(step_dir, "pgbench.log")
        cmd = _build_pgbench_cmd(db, phase, step)
        if phase.get("report_per_script"):
            cmd.append("-r")
        server_metrics = []
        tserver_urls = phase.get("tserver_urls")
        if not tserver_urls:
            tserver_urls = phase.get("server_metrics", {}).get("tserver_urls")
        if not tserver_urls:
            tserver_urls = []
        if tserver_urls and not dry_run:
            server_metrics.extend(
                capture_metrics(tserver_urls, step_dir, f"{step['name']}_before")
            )
        sm = phase.get("server_metrics", {})
        pg_stat_enabled = sm.get("pg_stat_statements", False)
        poll_interval = int(sm.get("pg_stat_statements_interval_sec", 0) or 0)
        config = config or {}
        xcluster_enabled = bool(config.get("cluster", {}).get("xcluster_enabled", False))
        replication_interval = int(config.get("replication_metrics", {}).get("interval_sec", 0) or 0)
        replication_urls = sm.get("tserver_urls", []) if xcluster_enabled and replication_interval > 0 else None
        replication_snapshots = []
        if pg_stat_enabled and not dry_run:
            _query_pg_stat_statements(db, db["dbname"], env, reset_before=True)
        if poll_interval > 0 and pg_stat_enabled and not dry_run:
            result, pg_stat_snapshots, replication_snapshots = _run_pgbench_with_polling(
                cmd, env, log_path, step_dir, db, db["dbname"], poll_interval,
                replication_urls=replication_urls,
                replication_interval_sec=replication_interval if replication_urls else 0,
            )
            snapshots_path = os.path.join(step_dir, "pg_stat_statements_over_time.json")
            with open(snapshots_path, "w", encoding="utf-8") as f:
                json.dump({"interval_sec": poll_interval, "snapshots": pg_stat_snapshots}, f, indent=2)
            if replication_snapshots:
                rep_path = os.path.join(step_dir, "replication_lag_over_time.json")
                with open(rep_path, "w", encoding="utf-8") as f:
                    json.dump({"interval_sec": replication_interval, "snapshots": replication_snapshots}, f, indent=2)
            pg_stat_stats = None
            if pg_stat_snapshots:
                last = pg_stat_snapshots[-1]
                pg_stat_stats = {
                    "mean_exec_time_ms": last.get("mean_ms"),
                    "min_exec_time_ms": last.get("min_ms"),
                    "max_exec_time_ms": last.get("max_ms"),
                    "calls": last.get("calls"),
                    "yb_p50_ms": last.get("yb_p50_ms"),
                    "yb_p90_ms": last.get("yb_p90_ms"),
                    "yb_p95_ms": last.get("yb_p95_ms"),
                    "yb_p99_ms": last.get("yb_p99_ms"),
                }
        else:
            result = _run_command(cmd, env, log_path, dry_run=dry_run, cwd=step_dir)
            pg_stat_stats = None
            if pg_stat_enabled and not dry_run:
                pg_stat_stats = _query_pg_stat_statements(db, db["dbname"], env, reset_before=False)
        if tserver_urls and not dry_run:
            server_metrics.extend(
                capture_metrics(tserver_urls, step_dir, f"{step['name']}_after")
            )
        result.update(
            {
                "name": name,
                "step": step["name"],
                "type": "pgbench",
                "log": log_path,
                "log_dir": step_dir,
                "duration_sec": step["duration_sec"],
                "target_tps": step["target_tps"],
                "transactions_per_client": step.get("transactions_per_client"),
                "total_transactions": step.get("total_transactions"),
                "clients": step.get("clients"),
                "jobs": step.get("jobs"),
            }
        )
        if pg_stat_stats:
            result["pg_stat_statements"] = pg_stat_stats
        if poll_interval > 0 and pg_stat_enabled and not dry_run:
            result["pg_stat_statements_over_time"] = os.path.join(step_dir, "pg_stat_statements_over_time.json")
        if replication_snapshots and not dry_run:
            result["replication_lag_over_time"] = os.path.join(step_dir, "replication_lag_over_time.json")
            rep_agg = aggregate_lag_snapshot(replication_snapshots)
            if rep_agg:
                result["replication_summary"] = rep_agg
        if not dry_run:
            result.update(_parse_pgbench_stats(log_path))
            if phase.get("log_transactions"):
                result.update(_parse_pgbench_latency_logs(step_dir))
                histogram_path = os.path.join(step_dir, "latency_histogram.csv")
                _write_latency_histogram(step_dir, histogram_path)
                result["latency_histogram_csv"] = histogram_path
            result["pgbench_log_files"] = _list_pgbench_logs(step_dir)
            if server_metrics:
                result["server_metrics"] = server_metrics
        results.append(result)

    summary = {"name": name, "type": "pgbench", "steps": results}
    if results:
        summary["tps"] = results[-1].get("tps")
        summary["tps_excluding"] = results[-1].get("tps_excluding")
    return summary


def _build_pgbench_cmd(db, phase, step):
    clients = step.get("clients", phase.get("clients", 1))
    jobs = step.get("jobs", phase.get("jobs", 1))
    cmd = [
        "pgbench",
        "-h",
        str(db["host"]),
        "-p",
        str(db["port"]),
        "-U",
        str(db["user"]),
        "-d",
        str(db["dbname"]),
        "-n",
        "-c",
        str(clients),
        "-j",
        str(jobs),
    ]
    tx_per_client = step.get("transactions_per_client")
    if tx_per_client:
        cmd.extend(["-t", str(tx_per_client)])
    elif step.get("duration_sec") is not None:
        cmd.extend(["-T", str(step.get("duration_sec", 60))])

    scripts = []
    mix = phase.get("mix", [])
    if mix:
        for item in mix:
            script = item.get("script")
            weight = item.get("weight", 1)
            if script:
                scripts.append((script, weight))
    else:
        script = phase.get("script")
        if script:
            scripts.append((script, 1))

    if not scripts:
        raise ValueError("pgbench phase requires script or mix")

    for script, weight in scripts:
        if weight == 1:
            cmd.extend(["-f", script])
        else:
            cmd.extend(["-f", f"{script}@{weight}"])

    if phase.get("log_transactions"):
        cmd.append("-l")

    target_tps = step.get("target_tps")
    if target_tps:
        cmd.extend(["-R", str(target_tps)])

    return cmd


def _run_http_phase(phase, run_dir, env, dry_run):
    name = phase.get("name", "http")
    log_path = os.path.join(run_dir, f"{name}.log")
    command = phase.get("command")
    args = phase.get("args", [])

    if not command:
        return {"name": name, "type": "http", "error": "missing command"}

    cmd = [command] + args
    result = _run_command(cmd, env, log_path, dry_run=dry_run)
    result.update({"name": name, "type": "http", "log": log_path})
    return result

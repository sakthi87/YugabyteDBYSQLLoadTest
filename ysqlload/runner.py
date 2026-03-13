import json
import os
import re
import subprocess
import time

from ysqlload.metrics import capture_metrics
from ysqlload.report import generate_reports


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
    parts = line.strip().split()
    if len(parts) < 6:
        return None
    try:
        ints = [int(p) for p in parts]
    except ValueError:
        return None

    epoch_idx = None
    for i, val in enumerate(ints):
        if val > 1_500_000_000:
            epoch_idx = i
            break
    if epoch_idx is None or epoch_idx < 2:
        return None

    time_sec = ints[epoch_idx]
    latency_candidates = [ints[epoch_idx - 2], ints[epoch_idx - 1]]
    latency_us = None
    for candidate in latency_candidates:
        if 0 <= candidate <= 10_000_000:
            latency_us = candidate
            break
    if latency_us is None:
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
    summary = {
        "run_dir": run_dir,
        "run_label": config.get("run_label", ""),
        "run_description": config.get("run_description", ""),
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
        if phase_type == "pgbench" and server_metrics.get("tserver_urls"):
            phase.setdefault("server_metrics", server_metrics)
        if phase_type == "pgbench":
            result = _run_pgbench_phase(db, phase, run_dir, base_env, dry_run)
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


def _run_pgbench_phase(db, phase, run_dir, env, dry_run):
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
            tps_label = f"{target_tps}tps" if target_tps is not None else f"step{idx}"
            steps.append(
                {
                    "name": f"{name}_{tps_label}",
                    "duration_sec": step.get("duration_sec"),
                    "target_tps": target_tps,
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
        result = _run_command(cmd, env, log_path, dry_run=dry_run, cwd=step_dir)
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
            }
        )
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
        str(phase.get("clients", 1)),
        "-j",
        str(phase.get("jobs", 1)),
    ]
    if step.get("duration_sec") is not None:
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

    tx_per_client = step.get("transactions_per_client")
    if tx_per_client:
        cmd.extend(["-t", str(tx_per_client)])

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

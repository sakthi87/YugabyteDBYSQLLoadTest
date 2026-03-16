import json
import os
import re


def _parse_interval(val):
    """Parse pg_stat_statements_interval_sec: 0 = disabled, positive = poll every N sec."""
    if val is None:
        return 0
    try:
        v = int(val)
        return max(0, v)
    except (TypeError, ValueError):
        return 0


_DBNAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _abspath(base_dir, path_value):
    if not path_value:
        return path_value
    if os.path.isabs(path_value):
        return path_value
    candidate = os.path.abspath(os.path.join(base_dir, path_value))
    if os.path.exists(candidate):
        return candidate
    parent_dir = os.path.abspath(os.path.join(base_dir, os.pardir))
    parent_candidate = os.path.abspath(os.path.join(parent_dir, path_value))
    if os.path.exists(parent_candidate):
        return parent_candidate
    return candidate


def _expand_tserver_urls(urls):
    """Expand tserver_urls: split comma-separated strings into a flat list of URLs."""
    if not urls:
        return []
    result = []
    for u in urls:
        if isinstance(u, str):
            result.extend(x.strip() for x in u.split(",") if x.strip())
        else:
            result.append(u)
    return result


def _validate_dbname(dbname):
    if dbname and dbname.startswith("${") and dbname.endswith("}"):
        return
    if not _DBNAME_RE.match(dbname):
        raise ValueError(
            "dbname must be alphanumeric/underscore for safety: %r" % dbname
        )


def _expand_env(value):
    if isinstance(value, str):
        def repl(match):
            key = match.group(1)
            return os.environ.get(key, match.group(0))
        return _ENV_RE.sub(repl, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    raw = _expand_env(raw)

    base_dir = os.path.dirname(os.path.abspath(path))
    db = raw.get("db", {})
    schema = raw.get("schema", {})
    phases = raw.get("phases", [])
    reports = raw.get("reports", {})
    server_metrics = raw.get("server_metrics", {})

    dbname = db.get("dbname")
    if not dbname:
        raise ValueError("db.dbname is required")
    _validate_dbname(dbname)

    admin_dbname = db.get("admin_dbname", "postgres")
    _validate_dbname(admin_dbname)

    schema["schema_sql_file"] = _abspath(base_dir, schema.get("schema_sql_file"))
    schema["preload_sql_file"] = _abspath(base_dir, schema.get("preload_sql_file"))

    for phase in phases:
        if phase.get("type") == "pgbench":
            phase["script"] = _abspath(base_dir, phase.get("script"))
            if "mix" in phase and isinstance(phase["mix"], list):
                for mix_item in phase["mix"]:
                    mix_item["script"] = _abspath(base_dir, mix_item.get("script"))

    port_value = db.get("port", 5433)
    if isinstance(port_value, str) and port_value.startswith("${") and port_value.endswith("}"):
        port_value = os.environ.get(port_value[2:-1], port_value)
    try:
        port_value = int(port_value)
    except (TypeError, ValueError):
        raise ValueError("db.port must be an integer")

    cluster = raw.get("cluster", {})
    cluster_type = cluster.get("cluster_type", "stretch")
    xcluster_enabled = bool(cluster.get("xcluster_enabled", False))
    if cluster_type == "xcluster":
        xcluster_enabled = True

    return {
        "run_label": raw.get("run_label", ""),
        "run_description": raw.get("run_description", ""),
        "cluster": {
            "cluster_type": cluster_type,
            "cluster_topology": cluster.get("cluster_topology", ""),
            "replication_mode": cluster.get("replication_mode", "none" if cluster_type == "stretch" else "active-passive"),
            "xcluster_enabled": xcluster_enabled,
        },
        "db": {
            "host": db.get("host", "127.0.0.1"),
            "port": port_value,
            "user": db.get("user", "yugabyte"),
            "password": db.get("password", ""),
            "dbname": dbname,
            "admin_dbname": admin_dbname,
        },
        "schema": {
            "create_db": bool(schema.get("create_db", False)),
            "drop_db": bool(schema.get("drop_db", False)),
            "schema_sql_file": schema.get("schema_sql_file"),
            "preload_sql_file": schema.get("preload_sql_file"),
        },
        "phases": phases,
        "reports": {
            "csv": bool(reports.get("csv", True)),
            "html": bool(reports.get("html", True)),
        },
        "server_metrics": {
            "tserver_urls": _expand_tserver_urls(server_metrics.get("tserver_urls", [])),
            "pg_stat_statements": bool(server_metrics.get("pg_stat_statements", False)),
            "pg_stat_statements_interval_sec": _parse_interval(
                server_metrics.get("pg_stat_statements_interval_sec")
            ),
        },
        "replication_metrics": {
            "interval_sec": _parse_interval(
                raw.get("replication_metrics", {}).get("interval_sec", 5)
            ) if xcluster_enabled else 0,
        },
    }

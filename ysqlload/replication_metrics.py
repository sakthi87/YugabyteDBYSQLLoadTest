"""
Replication lag metrics for XCluster benchmarking.
Fetches async_replication_committed_lag_micros from YugabyteDB tserver /metrics.
"""
import re
import time
from urllib.request import urlopen


# Prometheus metric: async_replication_committed_lag_micros (source cluster)
# consumer_safe_time_lag (target cluster, ms)
_LAG_MICROS_RE = re.compile(
    r"async_replication_committed_lag_micros(?:\{[^}]*\})?\s+([\d.e+-]+)"
)
_LAG_MS_RE = re.compile(
    r"consumer_safe_time_lag(?:\{[^}]*\})?\s+([\d.e+-]+)"
)


def _fetch_metrics(url, timeout_sec=5):
    try:
        with urlopen(url, timeout=timeout_sec) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return ""


def _parse_lag_micros(text):
    """Parse async_replication_committed_lag_micros from Prometheus output."""
    for match in _LAG_MICROS_RE.finditer(text):
        try:
            micros = float(match.group(1))
            return micros / 1000.0  # convert to ms
        except (ValueError, TypeError):
            continue
    return None


def _parse_lag_ms(text):
    """Parse consumer_safe_time_lag from Prometheus output (already in ms)."""
    for match in _LAG_MS_RE.finditer(text):
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            continue
    return None


def fetch_replication_lag_ms(urls, timeout_sec=5):
    """
    Fetch replication lag from first available tserver URL.
    Tries async_replication_committed_lag_micros (source) then consumer_safe_time_lag (target).
    Returns lag in milliseconds or None if unavailable.
    """
    if not urls:
        return None
    for url in urls:
        text = _fetch_metrics(url, timeout_sec)
        if not text:
            continue
        lag_ms = _parse_lag_micros(text)
        if lag_ms is not None:
            return lag_ms
        lag_ms = _parse_lag_ms(text)
        if lag_ms is not None:
            return lag_ms
    return None


def poll_replication_lag(urls, interval_sec, duration_sec, stop_event=None):
    """
    Poll replication lag every interval_sec for up to duration_sec.
    Returns list of {"timestamp": unix_sec, "elapsed_sec": int, "lag_ms": float}.
    """
    snapshots = []
    start = time.time()
    while (time.time() - start) < duration_sec:
        if stop_event and stop_event.is_set():
            break
        lag = fetch_replication_lag_ms(urls, timeout_sec=3)
        elapsed = int(time.time() - start)
        snapshots.append({
            "timestamp": int(time.time()),
            "elapsed_sec": elapsed,
            "lag_ms": round(lag, 2) if lag is not None else None,
        })
        for _ in range(interval_sec):
            if stop_event and stop_event.is_set():
                return snapshots
            time.sleep(1)
    return snapshots


def aggregate_lag_snapshot(snapshots):
    """Compute avg, p95, max from lag snapshots (ms)."""
    vals = [s["lag_ms"] for s in snapshots if s.get("lag_ms") is not None]
    if not vals:
        return None
    vals = sorted(vals)
    n = len(vals)
    p95_idx = max(0, int(n * 0.95) - 1)
    return {
        "avg_lag_ms": round(sum(vals) / n, 2),
        "p95_lag_ms": round(vals[p95_idx], 2),
        "max_lag_ms": round(max(vals), 2),
        "samples": n,
    }

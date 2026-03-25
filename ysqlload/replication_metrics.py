"""
Replication lag metrics for XCluster benchmarking.
Fetches async_replication_committed_lag_micros from YugabyteDB tserver.
YugabyteDB exposes metrics at /prometheus-metrics (port 9000 for tserver).
"""
import math
import re
import time
from urllib.request import urlopen
from urllib.parse import urlparse, urlunparse


# Prometheus metrics (source cluster): async_replication_committed_lag_micros
# Alternative: async_replication_sent_lag_micros (older versions)
# Target cluster: consumer_safe_time_lag (ms, transactional xCluster)
_LAG_PATTERNS = [
    (re.compile(r"async_replication_committed_lag_micros(?:\{[^}]*\})?\s+([\d.e+-]+)"), 1.0 / 1000.0),  # micros -> ms
    (re.compile(r"async_replication_sent_lag_micros(?:\{[^}]*\})?\s+([\d.e+-]+)"), 1.0 / 1000.0),  # micros -> ms
    (re.compile(r"consumer_safe_time_lag(?:\{[^}]*\})?\s+([\d.e+-]+)"), 1.0),  # already ms
]


def _url_with_path(url, path):
    """Replace path in URL. e.g. http://host:9000/metrics -> http://host:9000/prometheus-metrics"""
    parsed = urlparse(url)
    new = parsed._replace(path=path)
    return urlunparse(new)


def _fetch_metrics(url, timeout_sec=5):
    try:
        with urlopen(url, timeout=timeout_sec) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return ""


def _parse_lag_from_text(text):
    """
    Parse replication lag from Prometheus output.
    Tries all known metric patterns. For metrics with multiple lines (per tablet/stream),
    returns the max value (worst-case lag).
    """
    best_ms = None
    for pattern, scale in _LAG_PATTERNS:
        for match in pattern.finditer(text):
            try:
                val = float(match.group(1)) * scale
                if best_ms is None or val > best_ms:
                    best_ms = val
            except (ValueError, TypeError):
                continue
    return round(best_ms, 2) if best_ms is not None else None


def fetch_replication_lag_ms(urls, timeout_sec=5):
    """
    Fetch replication lag from first available tserver URL.
    YugabyteDB uses /prometheus-metrics; tries /metrics as fallback.
    Returns lag in milliseconds or None if unavailable.
    """
    if not urls:
        return None
    for url in urls:
        # Try URL as-is first
        text = _fetch_metrics(url, timeout_sec)
        if not text or "async_replication" not in text and "consumer_safe_time" not in text:
            # YugabyteDB uses /prometheus-metrics; try alternate path
            parsed = urlparse(url)
            alt_path = "/metrics" if parsed.path.rstrip("/").endswith("prometheus-metrics") else "/prometheus-metrics"
            alt_url = urlunparse(parsed._replace(path=alt_path))
            text2 = _fetch_metrics(alt_url, timeout_sec)
            if text2:
                text = text2
        if not text:
            continue
        lag_ms = _parse_lag_from_text(text)
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
    # Use ceil so sparse spikes count toward P95 (int() was too low for small n, e.g. n=6 -> idx 4 not 5)
    p95_idx = max(0, min(n - 1, int(math.ceil(n * 0.95)) - 1))
    return {
        "min_lag_ms": round(vals[0], 2),
        "avg_lag_ms": round(sum(vals) / n, 2),
        "p95_lag_ms": round(vals[p95_idx], 2),
        "max_lag_ms": round(max(vals), 2),
        "samples": n,
    }

import os
import time
from urllib.request import urlopen
from urllib.parse import urlparse, urlunparse


def fetch_metrics(url, timeout_sec=5):
    """Fetch Prometheus metrics from URL. Tries /prometheus-metrics if /metrics fails (YugabyteDB default)."""
    def _get(u):
        try:
            with urlopen(u, timeout=timeout_sec) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            return ""

    content = _get(url)
    if not content or len(content) < 100:
        parsed = urlparse(url)
        alt_path = "/metrics" if "prometheus-metrics" in parsed.path else "/prometheus-metrics"
        alt_url = urlunparse(parsed._replace(path=alt_path))
        content = _get(alt_url)
    return content


def capture_metrics(urls, output_dir, label):
    os.makedirs(output_dir, exist_ok=True)
    captured = []
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    for idx, url in enumerate(urls, start=1):
        filename = f"{label}_metrics_{idx}_{timestamp}.txt"
        path = os.path.join(output_dir, filename)
        content = fetch_metrics(url)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        captured.append({"url": url, "path": path})
    return captured

import os
import time
from urllib.request import urlopen


def fetch_metrics(url, timeout_sec=5):
    with urlopen(url, timeout=timeout_sec) as resp:
        return resp.read().decode("utf-8")


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

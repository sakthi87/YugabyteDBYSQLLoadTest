import json
import os
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote


_RUN_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def serve_dashboard(run_root, port):
    run_root = os.path.abspath(run_root)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = unquote(self.path.split("?", 1)[0])
            if path == "/":
                self._send_file(_static_path("dashboard.html"), "text/html")
                return
            if path == "/api/runsets":
                self._send_json(_list_runsets(run_root))
                return
            if path.startswith("/api/runset/"):
                parts = path.split("/")
                if len(parts) < 4:
                    self._send_error(404, "Invalid runset path")
                    return
                runset = parts[3]
                if not _RUN_NAME_RE.match(runset):
                    self._send_error(400, "Invalid runset name")
                    return
                runset_dir = os.path.join(run_root, runset)
                if path.endswith("/runs_with_labels"):
                    self._send_json(_list_runs_with_labels(runset_dir))
                    return
                if path.endswith("/runs"):
                    self._send_json(_list_runs(runset_dir))
                    return
            if path.startswith("/api/run/"):
                parts = path.split("/")
                if len(parts) < 5:
                    self._send_error(404, "Invalid run path")
                    return
                runset = parts[3]
                run_name = parts[4]
                if not _RUN_NAME_RE.match(runset) or not _RUN_NAME_RE.match(run_name):
                    self._send_error(400, "Invalid run name")
                    return
                run_dir = os.path.join(run_root, runset, run_name)
                if not os.path.isdir(run_dir):
                    self._send_error(404, "Run not found")
                    return
                if len(parts) == 5 or parts[5] == "summary":
                    self._send_json_file_sanitized(
                        os.path.join(run_dir, "summary.json")
                    )
                    return
                if parts[5] == "report.csv":
                    self._send_file(os.path.join(run_dir, "report.csv"), "text/csv")
                    return
                if parts[5] == "report.html":
                    self._send_file(os.path.join(run_dir, "report.html"), "text/html")
                    return
                if len(parts) >= 8 and parts[5] == "step":
                    step_name = parts[6]
                    if _RUN_NAME_RE.match(step_name):
                        if parts[7] == "pg_stat_over_time":
                            path = os.path.join(run_dir, step_name, "pg_stat_statements_over_time.json")
                            self._send_json_file_sanitized(path)
                            return
                        if parts[7] == "replication_lag_over_time":
                            path = os.path.join(run_dir, step_name, "replication_lag_over_time.json")
                            self._send_json_file_sanitized(path)
                            return
            self._send_error(404, "Not found")

        def log_message(self, format, *args):
            return

        def _send_json(self, payload):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_file(self, path, content_type):
            if not os.path.isfile(path):
                self._send_error(404, "File not found")
                return
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json_file_sanitized(self, path):
            """Serve JSON file with invalid floats (-Infinity, Infinity, NaN) replaced by null for browser parse."""
            if not os.path.isfile(path):
                self._send_error(404, "File not found")
                return
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            text = text.replace("-Infinity", "null").replace("Infinity", "null").replace("NaN", "null")
            data = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_error(self, status, message):
            data = json.dumps({"error": message}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Dashboard running at http://127.0.0.1:{port}")
    server.serve_forever()


def _static_path(name):
    base = os.path.join(os.path.dirname(__file__), "static")
    return os.path.join(base, name)


def _list_runs(run_root):
    if not os.path.isdir(run_root):
        return {"runs": []}
    runs = [
        name
        for name in os.listdir(run_root)
        if os.path.isdir(os.path.join(run_root, name))
    ]
    runs.sort()
    return {"runs": runs}


def _load_json_sanitized(path):
    """Load JSON file, sanitizing invalid float literals (-Infinity, Infinity, NaN) for parsing."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        text = text.replace("-Infinity", "null").replace("Infinity", "null").replace("NaN", "null")
        return json.loads(text)
    except (json.JSONDecodeError, OSError):
        return None


def _list_runs_with_labels(run_root):
    """List runs with run_label from each summary.json. Single API call, no fetch failures."""
    if not os.path.isdir(run_root):
        return {"runs": [], "labels": {}}
    runs = [
        name
        for name in os.listdir(run_root)
        if os.path.isdir(os.path.join(run_root, name))
    ]
    runs.sort()
    labels = {}
    for name in runs:
        summary_path = os.path.join(run_root, name, "summary.json")
        if os.path.isfile(summary_path):
            data = _load_json_sanitized(summary_path)
            labels[name] = data.get("run_label", "") if data else ""
        else:
            labels[name] = ""
    return {"runs": runs, "labels": labels}

def _list_runsets(run_root):
    runsets = _list_runs(run_root).get("runs", [])
    filtered = []
    for name in runsets:
        run_dir = os.path.join(run_root, name)
        runs = _list_runs(run_dir).get("runs", [])
        # Include run sets with at least 1 run (was 4; single-run / XCluster quick tests need visibility)
        if len(runs) >= 1:
            filtered.append(name)
    return {"runsets": filtered}

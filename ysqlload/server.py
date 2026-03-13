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
            if path.startswith("/api/runset/") and path.endswith("/runs"):
                parts = path.split("/")
                if len(parts) < 4:
                    self._send_error(404, "Invalid runset path")
                    return
                runset = parts[3]
                if not _RUN_NAME_RE.match(runset):
                    self._send_error(400, "Invalid runset name")
                    return
                self._send_json(_list_runs(os.path.join(run_root, runset)))
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
                    self._send_file(
                        os.path.join(run_dir, "summary.json"), "application/json"
                    )
                    return
                if parts[5] == "report.csv":
                    self._send_file(os.path.join(run_dir, "report.csv"), "text/csv")
                    return
                if parts[5] == "report.html":
                    self._send_file(os.path.join(run_dir, "report.html"), "text/html")
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

def _list_runsets(run_root):
    runs = _list_runs(run_root).get("runs", [])
    return {"runsets": runs}

import argparse
import os
import re

from ysqlload.config import load_config
from ysqlload.runner import run_all
from ysqlload.server import serve_dashboard


def _project_root():
    """Project root = parent of ysqlload package."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_serve_root(run_root):
    """Resolve run_root for serve_dashboard. If run_root is a run set (has timestamp
    subdirs with summary.json), use its parent so the dashboard finds run sets."""
    if not os.path.isdir(run_root):
        return run_root
    subdirs = [
        n for n in os.listdir(run_root)
        if os.path.isdir(os.path.join(run_root, n))
    ]
    # Check if any subdir looks like a run (timestamp pattern) and has summary.json
    ts_re = re.compile(r"^\d{8}-\d{6}$")
    for name in subdirs[:5]:
        if ts_re.match(name):
            summary_path = os.path.join(run_root, name, "summary.json")
            if os.path.isfile(summary_path):
                return os.path.dirname(run_root)
    return run_root


def main():
    parser = argparse.ArgumentParser(
        description="Hybrid YSQL load test runner (pgbench + optional HTTP)."
    )
    parser.add_argument(
        "--config", required=False, help="Path to JSON config file."
    )
    parser.add_argument(
        "--run-root", default="runs", help="Directory to store run outputs."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands only."
    )
    parser.add_argument(
        "--serve", action="store_true", help="Start local dashboard after run."
    )
    parser.add_argument(
        "--serve-only", action="store_true", help="Start dashboard without running."
    )
    parser.add_argument(
        "--port", type=int, default=8787, help="Dashboard port (default: 8787)."
    )

    args = parser.parse_args()
    run_root = args.run_root
    if not os.path.isabs(run_root):
        run_root = os.path.join(_project_root(), run_root)
    run_root = os.path.abspath(run_root)
    if args.serve_only:
        # If run_root points to a run set (has timestamp subdirs with summary.json),
        # use its parent so the dashboard finds run sets correctly.
        serve_root = _resolve_serve_root(run_root)
        serve_dashboard(serve_root, args.port)
        return
    if not args.config:
        raise SystemExit("--config is required unless --serve-only is set.")
    config = load_config(args.config)
    run_all(config, run_root, dry_run=args.dry_run)
    if args.serve:
        serve_root = _resolve_serve_root(run_root)
        serve_dashboard(serve_root, args.port)


if __name__ == "__main__":
    main()

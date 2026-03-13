import argparse
import os

from ysqlload.config import load_config
from ysqlload.runner import run_all
from ysqlload.server import serve_dashboard


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
    run_root = os.path.abspath(args.run_root)
    if args.serve_only:
        serve_dashboard(run_root, args.port)
        return
    if not args.config:
        raise SystemExit("--config is required unless --serve-only is set.")
    config = load_config(args.config)
    run_all(config, run_root, dry_run=args.dry_run)
    if args.serve:
        serve_dashboard(run_root, args.port)


if __name__ == "__main__":
    main()

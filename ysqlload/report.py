import csv
import os


def _flatten_rows(summary):
    rows = []
    for phase in summary.get("phases", []):
        operation = phase.get("name")
        if phase.get("type") == "pgbench" and "steps" in phase:
            for step in phase["steps"]:
                rows.append(
                    {
                        "phase": phase.get("name"),
                        "operation": operation,
                        "step": step.get("step"),
                        "type": phase.get("type"),
                        "exit_code": step.get("exit_code"),
                        "duration_sec": step.get("duration_sec"),
                        "target_tps": step.get("target_tps"),
                        "transactions_per_client": step.get("transactions_per_client"),
                        "total_transactions": step.get("total_transactions"),
                        "tps": step.get("tps"),
                        "tps_excluding": step.get("tps_excluding"),
                        "latency_avg_ms": step.get("latency_avg_ms"),
                        "latency_stddev_ms": step.get("latency_stddev_ms"),
                        "latency_p50_ms": step.get("latency_p50_ms"),
                        "latency_p90_ms": step.get("latency_p90_ms"),
                        "latency_p95_ms": step.get("latency_p95_ms"),
                        "latency_p99_ms": step.get("latency_p99_ms"),
                        "latency_samples": step.get("latency_samples"),
                        "latency_histogram_csv": step.get("latency_histogram_csv"),
                        "pgbench_log_files": _join_list(step.get("pgbench_log_files")),
                        "server_metrics": _join_metrics(step.get("server_metrics")),
                        "log": step.get("log"),
                    }
                )
        else:
            rows.append(
                {
                    "phase": phase.get("name"),
                    "operation": operation,
                    "step": "",
                    "type": phase.get("type"),
                    "exit_code": phase.get("exit_code"),
                    "duration_sec": phase.get("duration_sec"),
                    "target_tps": phase.get("target_tps"),
                    "transactions_per_client": phase.get("transactions_per_client"),
                    "total_transactions": phase.get("total_transactions"),
                    "tps": phase.get("tps"),
                    "tps_excluding": phase.get("tps_excluding"),
                    "latency_avg_ms": phase.get("latency_avg_ms"),
                    "latency_stddev_ms": phase.get("latency_stddev_ms"),
                    "latency_p50_ms": phase.get("latency_p50_ms"),
                    "latency_p90_ms": phase.get("latency_p90_ms"),
                    "latency_p95_ms": phase.get("latency_p95_ms"),
                    "latency_p99_ms": phase.get("latency_p99_ms"),
                    "latency_samples": phase.get("latency_samples"),
                    "latency_histogram_csv": phase.get("latency_histogram_csv"),
                    "pgbench_log_files": _join_list(phase.get("pgbench_log_files")),
                    "server_metrics": _join_metrics(phase.get("server_metrics")),
                    "log": phase.get("log"),
                }
            )
    return rows


def generate_reports(summary, run_dir, enabled_csv=True, enabled_html=True):
    rows = _flatten_rows(summary)
    if enabled_csv:
        _write_csv(rows, os.path.join(run_dir, "report.csv"))
    if enabled_html:
        _write_html(rows, os.path.join(run_dir, "report.html"))


def _write_csv(rows, path):
    fieldnames = [
        "phase",
        "operation",
        "step",
        "type",
        "exit_code",
        "duration_sec",
        "target_tps",
        "transactions_per_client",
        "total_transactions",
        "tps",
        "tps_excluding",
        "latency_avg_ms",
        "latency_stddev_ms",
        "latency_p50_ms",
        "latency_p90_ms",
        "latency_p95_ms",
        "latency_p99_ms",
        "latency_samples",
        "latency_histogram_csv",
        "pgbench_log_files",
        "server_metrics",
        "log",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_html(rows, path):
    header = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>YSQL Load Test Report</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 24px; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border: 1px solid #ddd; padding: 8px; font-size: 13px; }
      th { background: #f4f4f4; text-align: left; }
      tr:nth-child(even) { background: #fafafa; }
      .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    </style>
  </head>
  <body>
    <h2>YSQL Load Test Report</h2>
    <table>
      <thead>
        <tr>
          <th>phase</th>
          <th>operation</th>
          <th>step</th>
          <th>type</th>
          <th>exit_code</th>
          <th>duration_sec</th>
          <th>target_tps</th>
          <th>tps</th>
          <th>tps_excluding</th>
          <th>latency_avg_ms</th>
          <th>latency_stddev_ms</th>
          <th>latency_p50_ms</th>
          <th>latency_p90_ms</th>
          <th>latency_p95_ms</th>
          <th>latency_p99_ms</th>
          <th>latency_samples</th>
          <th>latency_histogram_csv</th>
          <th>pgbench_log_files</th>
          <th>server_metrics</th>
          <th>log</th>
        </tr>
      </thead>
      <tbody>
"""

    rows_html = []
    for row in rows:
        rows_html.append(
            "        <tr>"
            + "".join(
                [
                    f"<td>{_html(row.get('phase'))}</td>",
                    f"<td>{_html(row.get('operation'))}</td>",
                    f"<td>{_html(row.get('step'))}</td>",
                    f"<td>{_html(row.get('type'))}</td>",
                    f"<td>{_html(row.get('exit_code'))}</td>",
                    f"<td>{_html(row.get('duration_sec'))}</td>",
                    f"<td>{_html(row.get('target_tps'))}</td>",
                    f"<td>{_html(row.get('tps'))}</td>",
                    f"<td>{_html(row.get('tps_excluding'))}</td>",
                    f"<td>{_html(row.get('latency_avg_ms'))}</td>",
                    f"<td>{_html(row.get('latency_stddev_ms'))}</td>",
                    f"<td>{_html(row.get('latency_p50_ms'))}</td>",
                    f"<td>{_html(row.get('latency_p90_ms'))}</td>",
                    f"<td>{_html(row.get('latency_p95_ms'))}</td>",
                    f"<td>{_html(row.get('latency_p99_ms'))}</td>",
                    f"<td>{_html(row.get('latency_samples'))}</td>",
                    f"<td class=\"mono\">{_html(row.get('latency_histogram_csv'))}</td>",
                    f"<td class=\"mono\">{_html(row.get('pgbench_log_files'))}</td>",
                    f"<td class=\"mono\">{_html(row.get('server_metrics'))}</td>",
                    f"<td class=\"mono\">{_html(row.get('log'))}</td>",
                ]
            )
            + "</tr>"
        )

    footer = """
      </tbody>
    </table>
  </body>
</html>
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(rows_html))
        f.write(footer)


def _html(value):
    if value is None:
        return ""
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _join_list(values):
    if not values:
        return ""
    return ";".join(values)


def _join_metrics(values):
    if not values:
        return ""
    return ";".join([v.get("path", "") for v in values if v.get("path")])

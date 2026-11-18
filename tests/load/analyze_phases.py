"""Split Locust CSV full-history into warm-up / steady / spike windows.

Reads locust_stats_history.csv (from --csv-full-history) and phase_boundaries.json.
Prints p95 / failure rates per phase; pass/fail table uses steady only.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

RESULTS = Path(os.environ.get("STOCKPILOT_LOAD_RESULTS_DIR", "/results"))
READ_NAMES = {
    "GET /products",
    "GET /inventory",
    "GET /orders",
    "GET /dashboard",
    "GET /members",
    "GET /inventory/movements",
    "GET /customers",
    "GET /api/v1/me",
}
CMD_NAMES = {
    "POST /orders",
    "POST /orders/{id}/reserve",
    "POST /orders/{id}/confirm",
    "POST /orders/{id}/cancel",
}


def _p95_from_history_rows(rows: list[dict[str, str]]) -> float | None:
    """Approximate p95 from Locust history '95%' column (already aggregated)."""
    vals: list[float] = []
    for r in rows:
        raw = r.get("95%") or r.get("95%ile") or ""
        if raw in ("", "N/A", "None"):
            continue
        try:
            vals.append(float(raw))
        except ValueError:
            continue
    if not vals:
        return None
    vals.sort()
    idx = min(len(vals) - 1, max(0, math.ceil(0.95 * len(vals)) - 1))
    return vals[idx]


def _phase_for(timestamp_s: float, warmup: float, steady: float, spike: float) -> str:
    if timestamp_s < warmup:
        return "warmup"
    if timestamp_s < steady:
        return "steady"
    if timestamp_s <= spike:
        return "spike"
    return "after"


def main() -> int:
    boundaries_path = RESULTS / "phase_boundaries.json"
    history_path = RESULTS / "locust_stats_history.csv"
    if not boundaries_path.is_file():
        print(f"missing {boundaries_path}", file=sys.stderr)
        return 1
    if not history_path.is_file():
        print(f"missing {history_path}", file=sys.stderr)
        return 1
    bounds = json.loads(boundaries_path.read_text(encoding="utf-8"))
    warmup = float(bounds["warmup_end_s"])
    steady = float(bounds["steady_end_s"])
    spike = float(bounds["spike_end_s"])

    by_phase: dict[str, list[dict[str, str]]] = defaultdict(list)
    with history_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Locust full-history: Timestamp is unix seconds or relative; prefer Relative.
            rel = row.get("Timestamp") or row.get("timestamp")
            try:
                # Locust 2.x stats_history: first column often User Count + Timestamp (unix).
                ts = float(rel)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            # If absolute unix, convert using wall_start if present.
            wall = bounds.get("wall_start_unix")
            if wall and ts > 1_000_000_000:
                ts = ts - float(wall)
            name = row.get("Name") or row.get("name") or ""
            if name in ("Aggregated", ""):
                # Keep Aggregated rows for overall phase stats.
                pass
            phase = _phase_for(ts, warmup, steady, spike)
            by_phase[phase].append(row)

    print("phase,window_s,requests_approx,p95_ms_agg_rows,fail_ratio_hint")
    summary: dict[str, dict[str, float | None]] = {}
    for phase in ("warmup", "steady", "spike"):
        rows = [r for r in by_phase[phase] if (r.get("Name") or "") == "Aggregated"]
        if not rows:
            rows = by_phase[phase]
        p95 = _p95_from_history_rows(rows)
        # Failure: use last Aggregated row's Failures / Requests if present.
        fail_ratio = None
        if rows:
            last = rows[-1]
            try:
                req = float(last.get("Total Request Count") or last.get("Request Count") or 0)
                fails = float(last.get("Total Failure Count") or last.get("Failures") or 0)
                fail_ratio = (fails / req) if req else 0.0
            except ValueError:
                fail_ratio = None
        summary[phase] = {"p95_ms": p95, "fail_ratio": fail_ratio}
        print(f"{phase},{phase},{len(by_phase[phase])},{p95},{fail_ratio}")

    # Endpoint-group steady p95 from Name rows in steady window.
    steady_rows = by_phase["steady"]
    read_p95 = _p95_from_history_rows(
        [r for r in steady_rows if (r.get("Name") or "") in READ_NAMES]
    )
    cmd_p95 = _p95_from_history_rows(
        [r for r in steady_rows if (r.get("Name") or "") in CMD_NAMES]
    )
    print("---")
    print(f"steady_read_p95_ms={read_p95}")
    print(f"steady_command_p95_ms={cmd_p95}")
    print(f"steady_fail_ratio={summary['steady'].get('fail_ratio')}")
    out = {
        "phases": summary,
        "steady_read_p95_ms": read_p95,
        "steady_command_p95_ms": cmd_p95,
        "targets": {
            "read_p95_ms": 300,
            "command_p95_ms": 800,
            "5xx_ratio": 0.01,
        },
    }
    (RESULTS / "phase_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {RESULTS / 'phase_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

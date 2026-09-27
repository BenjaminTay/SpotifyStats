#!/usr/bin/env python3
"""Summarize interleaved exact-ready D/F runtime samples without idle-window leakage."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


def _timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _events(path: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return {str(row["event"]): row for row in rows}


def _service(point: dict[str, Any], label: str) -> dict[str, Any] | None:
    return next(
        (item for item in point.get("services", []) if item.get("label") == label),
        None,
    )


def _round(value: float | int | None, digits: int = 3) -> float | None:
    return round(float(value), digits) if value is not None else None


def run_metrics(run: Path) -> dict[str, Any]:
    events = _events(run / "events.jsonl")
    resources = json.loads((run / "resources.json").read_text(encoding="utf-8"))
    spa = json.loads((run / "spa.json").read_text(encoding="utf-8"))
    samples = {str(item["phase"]): item for item in spa["samples"]}
    process_start = events["process_start"]
    health = events["health_ready"]
    first_ready = events["core_page_ready"]
    necessary = events["necessary_maintenance_complete"]
    publication = events["publication_exact_validated"]
    exact = events["core_page_exact"]
    idle_start = events["idle_start"]
    idle_end = events["idle_end"]
    start_monotonic = float(process_start["monotonic"])
    start_epoch = _timestamp(str(process_start["timestamp"]))
    first_epoch = float(first_ready["observed_epoch"])
    exact_at = _timestamp(str(exact["timestamp"]))
    idle_start_at = _timestamp(str(idle_start["timestamp"]))
    idle_end_at = _timestamp(str(idle_end["timestamp"]))
    series = resources["time_series"]
    startup_points = [point for point in series if float(point["timestamp"]) <= exact_at]
    backend = [
        service
        for point in startup_points
        if (service := _service(point, "backend")) and service.get("status") == "ok"
    ]
    idle_points = [
        point for point in series if idle_start_at + 5 <= float(point["timestamp"]) <= idle_end_at
    ]
    idle_cpu_seconds = sum(
        float(service.get("cpu_seconds_delta") or 0)
        for point in idle_points
        for service in point.get("services", [])
        if service.get("role") == "application" and service.get("status") == "ok"
    )
    idle_window = max(
        0.001,
        (float(idle_points[-1]["timestamp"]) - float(idle_points[0]["timestamp"]))
        if len(idle_points) > 1
        else idle_end_at - (idle_start_at + 5),
    )
    footprint = [
        float(item["physical_footprint_mb"])
        for item in backend
        if item.get("physical_footprint_mb") is not None
    ]
    return {
        "run": run.name,
        "health_seconds": _round(float(health["monotonic"]) - start_monotonic),
        "first_business_ready_seconds": _round(first_epoch - start_epoch),
        "first_core_ready_ms": _round(samples["first"]["core_ready_ms"]),
        "revisit_core_ready_ms": _round(samples["revisit"]["core_ready_ms"]),
        "first_snapshot_state": samples["first"]["snapshot_state"],
        "revisit_snapshot_state": samples["revisit"]["snapshot_state"],
        "same_document": spa["same_document"],
        "final_publication_ready": bool(publication["publication_readiness"]["ready"]),
        "final_core_exact": "exact" in exact.get("snapshot_states", []),
        "necessary_maintenance_seconds": _round(float(necessary["monotonic"]) - start_monotonic),
        "final_exact_seconds": _round(float(exact["monotonic"]) - start_monotonic),
        "startup_backend_cpu_seconds": _round(
            sum(float(item.get("cpu_seconds_delta") or 0) for item in backend), 6
        ),
        "startup_backend_peak_rss_mb": _round(max(float(item["rss_mb"]) for item in backend)),
        "startup_backend_peak_footprint_mb": _round(max(footprint) if footprint else None),
        "idle_application_cpu_percent": _round(idle_cpu_seconds / idle_window * 100),
        "sampling_valid": resources["sampling_integrity"]["valid"],
        "operation_exit": resources["operation_exit"],
        "competitors_start": process_start.get("external_competitors", []),
        "competitors_end": events["shutdown_complete"].get("external_competitors", []),
    }


def _median(rows: list[dict[str, Any]], key: str) -> float:
    return float(statistics.median(float(row[key]) for row in rows))


def _relative_or_absolute_gate(
    *, baseline: float, actual: float, absolute_limit: float
) -> dict[str, Any]:
    baseline_already_light = baseline <= absolute_limit
    limit = absolute_limit if baseline_already_light else baseline * 0.7
    return {
        "baseline_d_median": _round(baseline),
        "f_median": _round(actual),
        "mode": "absolute" if baseline_already_light else "relative_30_percent_reduction",
        "limit": _round(limit),
        "pass": actual <= limit,
    }


def summarize(runs: list[Path]) -> dict[str, Any]:
    rows = [run_metrics(path) for path in runs]
    groups = {
        name: [row for row in rows if str(row["run"]).startswith(name)] for name in ("D", "F")
    }
    keys = (
        "health_seconds",
        "first_business_ready_seconds",
        "first_core_ready_ms",
        "revisit_core_ready_ms",
        "necessary_maintenance_seconds",
        "final_exact_seconds",
        "startup_backend_cpu_seconds",
        "startup_backend_peak_rss_mb",
        "startup_backend_peak_footprint_mb",
        "idle_application_cpu_percent",
    )
    medians = {
        group: {key: _round(_median(values, key)) for key in keys}
        for group, values in groups.items()
    }
    gates: dict[str, dict[str, Any]] = {}
    for key in ("first_core_ready_ms", "revisit_core_ready_ms"):
        baseline = float(medians["D"][key])
        actual = float(medians["F"][key])
        allowance = max(100.0, baseline * 0.1)
        gates[key] = {
            "baseline_d_median": baseline,
            "f_median": actual,
            "allowance_ms": _round(allowance),
            "limit_ms": _round(baseline + allowance),
            "pass": actual <= baseline + allowance,
        }
    gates["idle_application_cpu_percent"] = {
        "limit": 1.0,
        "f_median": medians["F"]["idle_application_cpu_percent"],
        "pass": float(medians["F"]["idle_application_cpu_percent"]) <= 1.0,
    }
    gates["startup_backend_cpu_seconds"] = _relative_or_absolute_gate(
        baseline=float(medians["D"]["startup_backend_cpu_seconds"]),
        actual=float(medians["F"]["startup_backend_cpu_seconds"]),
        absolute_limit=5.0,
    )
    gates["startup_backend_peak_rss_mb"] = _relative_or_absolute_gate(
        baseline=float(medians["D"]["startup_backend_peak_rss_mb"]),
        actual=float(medians["F"]["startup_backend_peak_rss_mb"]),
        absolute_limit=768.0,
    )
    gates["startup_backend_peak_footprint_mb"] = {
        "limit": 768.0,
        "f_median": medians["F"]["startup_backend_peak_footprint_mb"],
        "pass": float(medians["F"]["startup_backend_peak_footprint_mb"]) <= 768.0,
    }
    validity = {
        "six_successful_runs": len(rows) == 6 and all(row["operation_exit"] == 0 for row in rows),
        "sampling_valid": all(row["sampling_valid"] for row in rows),
        "no_competitors": all(
            not row[side] for row in rows for side in ("competitors_start", "competitors_end")
        ),
        "ready_same_spa": all(
            row["same_document"]
            and row["first_snapshot_state"] in {"exact", "LKG"}
            and row["revisit_snapshot_state"] in {"exact", "LKG"}
            for row in rows
        ),
        "final_exact": all(
            row["final_publication_ready"] and row["final_core_exact"] for row in rows
        ),
    }
    return {
        "schema_version": 1,
        "order": [path.name for path in runs],
        "runs": rows,
        "medians": medians,
        "gates": gates,
        "validity": validity,
        "pass": all(validity.values()) and all(gate["pass"] for gate in gates.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.run) != 6:
        raise ValueError("exactly six interleaved D/F runs are required")
    report = summarize(args.run)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

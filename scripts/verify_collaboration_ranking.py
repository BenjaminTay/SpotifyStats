#!/usr/bin/env python3
"""Compare collaboration records against an earlier builder on an explicit DB copy."""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def differences(left, right, prefix=""):
    if isinstance(left, dict) and isinstance(right, dict):
        return [
            path
            for key in sorted(set(left) | set(right))
            for path in differences(left.get(key), right.get(key), f"{prefix}/{key}")
        ]
    return [] if left == right else [prefix]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-copy", type=Path, required=True)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--merge-level", type=int, choices=(2, 3), default=2)
    parser.add_argument("--json-output", type=Path, required=True)
    args = parser.parse_args()
    db = args.db_copy.resolve()
    if not db.is_file() or db == (ROOT / "data/spotify_stats.db").resolve():
        parser.error("--db-copy must be an existing, explicit database copy")
    if args.json_output.exists() or not args.json_output.parent.is_dir():
        parser.error("--json-output must be a new file in an existing directory")

    # Establish isolated paths before importing the application. This tool never
    # migrates the copy and opens the statistics source read-only.
    os.environ["SPOTIFY_STATS_DB_PATH"] = str(db)
    os.environ["SPOTIFY_STATS_WARMUP"] = "0"
    sys.path.insert(0, str(ROOT))
    from backend.core.db import get_db, load_plays
    from backend.domains.metadata.track_credits import get_effective_track_credits
    from backend.domains.playback import records as records_module
    from backend.domains.playback.counting import assign_logical_event_id
    from backend.domains.settings.repository import SettingsRepository
    from backend.services.analysis_records_service import _get_analysis_records_uncached

    source = subprocess.check_output(
        ["git", "show", f"{args.baseline_ref}:backend/domains/playback/records_discovery.py"],
        cwd=ROOT,
        text=True,
    )
    baseline = types.ModuleType("collaboration_baseline")
    exec(compile(source, "<git baseline records_discovery>", "exec"), baseline.__dict__)
    current = records_module.compute_discovery_records
    conn = get_db(readonly=True)
    try:
        settings = SettingsRepository(conn).load_all()
        filters = {
            key: settings[key]
            for key in ("min_ms", "music_only", "merge_enabled", "max_merge_gap_minutes")
        }
        filters["dynamic_threshold"] = True
        params = {
            **filters,
            "period": "lifetime",
            "start_date": None,
            "end_date": None,
            "merge_level": args.merge_level,
            "include_compilations": False,
        }
        outputs = {}
        elapsed = {}
        for name, implementation in (
            ("before", baseline.compute_discovery_records),
            ("after", current),
        ):
            records_module.compute_discovery_records = implementation
            started = time.perf_counter()
            outputs[name] = _get_analysis_records_uncached(conn=conn, **params)
            elapsed[name] = round(time.perf_counter() - started, 3)
            print(f"{name}: completed in {elapsed[name]}s", flush=True)
        normalized = copy.deepcopy(outputs)
        for payload in normalized.values():
            payload["meta"].pop("generated_at", None)
            payload["records"]["discovery"].pop("feat_lover", None)
        other_differences = differences(normalized["before"], normalized["after"])

        events = assign_logical_event_id(load_plays(conn, **filters))
        if "representative_track_id" not in events:
            raise ValueError("The real event frame has no representative_track_id")
        credits = get_effective_track_credits(
            conn, events["representative_track_id"].unique().tolist()
        )
        members = {}
        for credit in credits:
            members.setdefault(int(credit["track_id"]), {})[int(credit["artist_id"])] = credit[
                "artist_name"
            ]
        collaborations = {track_id for track_id, artists in members.items() if len(artists) >= 2}
        actual_collaboration_events = events[events["representative_track_id"].isin(collaborations)]
        expected_count = int(actual_collaboration_events["_logical_event_id"].nunique())
        after_rows = outputs["after"]["records"]["discovery"]["feat_lover"]["track"]
        summary = next(
            (
                row
                for row in after_rows
                if row.get("rank") == 0
                or "播放" in row.get("name", "")
                and "比" in row.get("name", "")
            ),
            {},
        )
        actual_count = int(summary.get("secondary_value") or 0)
        examples = []
        for row in conn.execute(
            "SELECT track_id, track_name FROM tracks WHERE track_id IN (175,1782) ORDER BY track_id"
        ):
            track_id = int(row["track_id"])
            matching = events[events["representative_track_id"].eq(track_id)]
            examples.append(
                {
                    "track_id": track_id,
                    "track_name": row["track_name"],
                    "artists": list(members.get(track_id, {}).values()),
                    "before_eligible": baseline._has_feat_marker(row["track_name"]),
                    "after_eligible": track_id in collaborations,
                    "effective_event_count": int(matching["_logical_event_id"].nunique()),
                }
            )
        report = {
            "database_copy": str(db),
            "baseline_ref": args.baseline_ref,
            "parameters": params,
            "elapsed_seconds": elapsed,
            "other_records_unchanged": not other_differences,
            "other_difference_paths": other_differences,
            "expected_collaboration_events": expected_count,
            "reported_collaboration_events": actual_count,
            "count_conserved": expected_count == actual_count,
            "examples": examples,
            "outputs": outputs,
        }
        with args.json_output.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
        print(
            json.dumps(
                {key: value for key, value in report.items() if key != "outputs"},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not other_differences and actual_count == expected_count else 1
    finally:
        records_module.compute_discovery_records = current
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

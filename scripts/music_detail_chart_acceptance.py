#!/usr/bin/env python3
"""Owned-copy music-detail correctness and resource acceptance.

This measures real service calls or the complete in-process HTTP route. Each cold sample
is a fresh interpreter, without lifespan, startup warmup or network enrichment.
Preparation uses SQLite Online Backup, never filesystem-copy of a live DB.
Private payloads stay in the explicitly supplied ignored output directory.
"""

from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TABLES = (
    "plays",
    "tracks",
    "track_artists",
    "albums",
    "artists",
    "spotify_track_meta",
    "track_l1_identities",
    "track_l1_source_links",
    "track_l1_external_ids",
    "track_groups",
    "track_group_members",
    "track_group_l1_members",
    "album_projects",
    "album_project_tracks",
    "album_project_albums",
    "l3_song_album_attributions",
    "artist_identity_groups",
    "artist_identity_members",
    "track_credit_overrides",
    "track_credit_override_artists",
    "artist_identity_aliases",
    "artist_identity_external_ids",
    "artist_identity_events",
    "artist_identity_state",
    "artist_genre_overrides",
    "artist_metadata_attribution_overrides",
    "track_identity_state",
    "track_identity_events",
    "track_merge_overrides",
    "track_group_migration_audit",
    "album_project_revision_state",
    "album_project_external_ids",
    "l3_song_album_attribution_overrides",
    "l3_song_album_attribution_issues",
    "l3_song_album_attribution_exclusions",
    "l3_album_attribution_revision_state",
    "governance_source_revisions",
    "analysis_source_revisions",
    "music_search_revision_state",
    "release_groups",
    "release_group_members",
    "track_id_aliases",
    "track_albums",
    "album_spotify_links",
    "track_credit_events",
    "track_credit_change_sets",
    "version_governance_events",
    "version_governance_runs",
    "artist_language_evidence",
    "artist_language_sources",
    "artist_language_review_queue",
    "artist_genre_sources",
    "artist_genre_review_queue",
    "spotify_auto_track_credits",
    "spotify_track_credit_sets",
    "spotify_track_artist_credits",
    "spotify_album_artist_credits",
    "spotify_album_credit_sets",
)
COMMON = (30000, True, 30, 20, 20, 4, 12, None, None, True, 5, True, 2, False)
SAMPLES = [
    {"kind": "track", "identity": [1493], "label": "vampire"},
    {"kind": "album", "identity": ["Midnights", "Taylor Swift"], "label": "Midnights"},
    {"kind": "artist", "identity": ["Taylor Swift"], "label": "Taylor Swift"},
]
UI_FIELDS = {
    "track": (
        "found",
        "chart_status",
        "effective_play_count",
        "track_name",
        "artist_name",
        "artist_names",
        "primary_artist_name",
        "cover_url",
        "meta",
        "summary",
        "history",
        "chart_data",
    ),
    "album": (
        "found",
        "chart_status",
        "effective_play_count",
        "album_name",
        "artist_name",
        "cover_url",
        "meta",
        "chart_summary",
        "album_weekly_history",
        "album_no1_by_week",
        "best_singles_overlay",
    ),
    "artist": (
        "found",
        "chart_status",
        "effective_play_count",
        "artist_name",
        "cover_url",
        "meta",
        "chart_summary",
        "artist_weekly_history",
        "artist_no1_by_week",
        "week_no1_albums",
        "best_singles_overlay",
        "best_albums_overlay",
    ),
}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def readonly(database: Path):
    conn = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def source_facts(database: Path) -> dict:
    facts = {}
    conn = readonly(database)
    try:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in SOURCE_TABLES:
            if table not in tables:
                continue
            columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
            # Some governance tables use WITHOUT ROWID; stable column ordering
            # handles both forms and avoids assuming a hidden rowid exists.
            order = ",".join('"' + col.replace('"', '""') + '"' for col in columns)
            digest, count = hashlib.sha256(), 0
            for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY {order}'):
                digest.update(
                    json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str).encode()
                )
                digest.update(b"\n")
                count += 1
            facts[table] = {"rows": count, "sha256": digest.hexdigest()}
    finally:
        conn.close()
    return facts


def prepare(source: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / "main.db").exists():
        raise ValueError("destination already contains main.db; choose a fresh directory")
    copied = []
    for filename in (
        "main.db",
        "billboard_cache.db",
        "yearly_review_cache.db",
        "analysis_cache.db",
        "governance_cache.db",
        "community_cache.db",
        "account_archive_cache.db",
    ):
        original = source / filename
        if not original.exists():
            continue
        incoming, outgoing = readonly(original), sqlite3.connect(destination / filename)
        try:
            incoming.backup(outgoing, pages=256, sleep=0.01)
            # Online Backup retains a source WAL header. These owned copies
            # have no live WAL and must remain readable by mode=ro workers.
            outgoing.execute("PRAGMA journal_mode=DELETE")
        finally:
            outgoing.close()
            incoming.close()
        copied.append(filename)
    conn = readonly(destination / "main.db")
    try:
        report = {
            "source": str(source),
            "destination": str(destination),
            "copied": copied,
            "integrity": conn.execute("PRAGMA quick_check").fetchone()[0],
            "schema_version": conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[
                0
            ],
            "plays": conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0],
            "snapshots": [
                dict(
                    zip(
                        (
                            "snapshot_key",
                            "builder_version",
                            "merge_level",
                            "dynamic_threshold",
                            "status",
                        ),
                        row,
                    )
                )
                for row in conn.execute(
                    "SELECT snapshot_key,builder_version,merge_level,dynamic_threshold,status FROM music_search_snapshot_meta"
                )
            ],
            "protected_source_facts": source_facts(destination / "main.db"),
        }
    finally:
        conn.close()
    write_json(destination.parent / (destination.name + "-preparation.json"), report)
    return report


def environment(runtime: Path) -> dict:
    env = dict(os.environ)
    env.update(
        SPOTIFY_RUNTIME_MEASUREMENT="1",
        SPOTIFY_STATS_WARMUP="0",
        SPOTIFY_STATS_SEARCH_STARTUP_REBUILD="0",
        SPOTIFY_STATS_L3_STARTUP_RECONCILE="0",
        SPOTIFY_STATS_EXTERNAL_COVERS="0",
        SPOTIFY_STATS_DB_PATH=str(runtime / "main.db"),
    )
    for key, filename in (
        ("BILLBOARD", "billboard_cache.db"),
        ("YEARLY", "yearly_review_cache.db"),
        ("ANALYSIS", "analysis_cache.db"),
        ("GOVERNANCE", "governance_cache.db"),
        ("COMMUNITY", "community_cache.db"),
        ("ARCHIVE", "account_archive_cache.db"),
    ):
        env[f"SPOTIFY_STATS_{key}_CACHE_PATH"] = str(runtime / filename)
    return env


class Monitor:
    def __init__(self):
        import psutil

        self.process = psutil.Process()
        self.samples = []
        self.stop = threading.Event()

    def __enter__(self):
        gc.collect()
        self.before = self.process.memory_info().rss
        self.started, self.cpu = time.perf_counter(), time.process_time()
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()
        return self

    def _sample(self):
        while not self.stop.is_set():
            self.samples.append(
                (
                    round((time.perf_counter() - self.started) * 1000, 3),
                    self.process.memory_info().rss,
                )
            )
            self.stop.wait(0.002)

    def __exit__(self, *_):
        self.wall_ms = (time.perf_counter() - self.started) * 1000
        self.cpu_ms = (time.process_time() - self.cpu) * 1000
        self.stop.set()
        self.thread.join()
        self.after = self.process.memory_info().rss
        gc.collect()
        self.settled = self.process.memory_info().rss

    def report(self):
        peak = max([self.before, self.after, self.settled] + [row[1] for row in self.samples])
        return {
            "wall_ms": self.wall_ms,
            "cpu_ms": self.cpu_ms,
            "baseline_rss_bytes": self.before,
            "peak_rss_bytes": peak,
            "peak_delta_bytes": peak - self.before,
            "end_rss_bytes": self.after,
            "settled_rss_bytes": self.settled,
            "samples": self.samples,
        }


def worker(args):
    os.environ.update(environment(args.runtime))
    sys.path.insert(0, str(args.source_root))
    from backend.core.access_surface import set_public_readonly_db_guard

    set_public_readonly_db_guard(True)
    from backend.domains.billboard import detail_views

    functions = {
        "track": detail_views.get_track_detail_view,
        "album": detail_views.get_album_detail_view,
        "artist": detail_views.get_artist_detail_view,
    }
    client = None
    if args.http:
        from fastapi.testclient import TestClient
        from backend.main import app

        # No lifespan: startup maintenance must not repair or warm the target.
        client = TestClient(app)

    def invoke(sample, common, view):
        if client is None:
            return functions[sample["kind"]](*sample["identity"], *common, view=view), None
        from urllib.parse import quote
        from backend.core.access_surface import SURFACE_HEADER

        names = (
            "min_ms",
            "music_only",
            "bb_top_n",
            "bb_album_top_n",
            "bb_artist_top_n",
            "bb_week_start_dow",
            "bb_week_start_hour",
            "year_start",
            "year_end",
            "dynamic_threshold",
            "max_merge_gap_minutes",
            "merge_enabled",
            "merge_level",
            "include_compilations",
        )
        params = {key: value for key, value in zip(names, common) if value is not None}
        params["view"] = view
        identity = sample["identity"]
        if sample["kind"] == "track":
            path = f"/api/billboard/track/canonical/{identity[0]}"
        elif sample["kind"] == "album":
            path = "/api/billboard/album/" + quote(str(identity[0]), safe="")
            params["artist_name"] = identity[1]
        else:
            path = "/api/billboard/artist/" + quote(str(identity[0]), safe="")
        response = client.get(path, params=params, headers={SURFACE_HEADER: "public-readonly"})
        value = response.json()
        if response.status_code != 200:
            return value, {
                "type": "HTTPError",
                "status": response.status_code,
                "message": str(value),
            }
        return value, None

    spec = json.loads(args.spec.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Persist every response immediately. Retaining all 324 cohort payloads or
    # RSS samples in the probe would itself create a false linear memory rise.
    with args.output.open("w") as report:
        header = {
            "source_root": str(args.source_root),
            "runtime": str(args.runtime),
            "rounds": args.rounds,
            "transport": "http" if args.http else "service",
        }
        report.write(json.dumps(header)[:-1] + ',"rows":[')
        first = True
        for iteration in range(args.rounds):
            for sample in spec:
                for view in args.views.split(","):
                    if view == "project" and sample["kind"] != "album":
                        continue
                    with Monitor() as monitor:
                        try:
                            common = list(sample.get("common", COMMON))
                            value, error = invoke(sample, common, view)
                        except Exception as exc:
                            value, error = None, {"type": type(exc).__name__, "message": str(exc)}
                    row = {
                        "iteration": iteration,
                        "sample": sample,
                        "view": view,
                        "payload": value,
                        "error": error,
                        "metrics": monitor.report(),
                    }
                    if not first:
                        report.write(",")
                    report.write(json.dumps(row, ensure_ascii=False, default=str))
                    report.flush()
                    first = False
                    del row, value, monitor
            print(json.dumps({"completed_round": iteration + 1, "samples": len(spec)}), flush=True)
        report.write("]}\n")
    if client is not None:
        client.close()


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    spec_path = args.spec or args.output / "samples.json"
    if args.spec is None:
        write_json(spec_path, SAMPLES)
    summaries = []
    for sample_index, sample in enumerate(json.loads(spec_path.read_text())):
        single_spec = args.output / f"sample-{sample_index}.json"
        write_json(single_spec, [sample])
        for run_index in range(args.repeat):
            target = args.output / f"cold-{sample_index}-{run_index}.json"
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "worker",
                "--source-root",
                str(args.source_root),
                "--runtime",
                str(args.runtime),
                "--spec",
                str(single_spec),
                "--output",
                str(target),
                "--rounds",
                "2",
                "--views",
                "overview",
            ]
            if args.http:
                command.append("--http")
            result = subprocess.run(
                command, capture_output=True, text=True, env=environment(args.runtime), timeout=180
            )
            if result.returncode:
                write_json(
                    target,
                    {
                        "exit_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    },
                )
                summaries.append({"sample": sample, "run": run_index, "process_failed": True})
                continue
            data = json.loads(target.read_text())
            metrics = [
                {k: v for k, v in row["metrics"].items() if k != "samples"} for row in data["rows"]
            ]
            summaries.append(
                {
                    "sample": sample,
                    "run": run_index,
                    "metrics": metrics,
                    "errors": [row["error"] for row in data["rows"]],
                }
            )
    write_json(args.output / "summary.json", summaries)
    violations = []
    for row in summaries:
        if row.get("process_failed") or any(row.get("errors", [])):
            violations.append(
                {"sample": row["sample"], "run": row["run"], "reason": "request_failed"}
            )
            continue
        cold, hot = row["metrics"]
        for reason, observed, limit in (
            ("cold_ms", cold["wall_ms"], 500),
            ("hot_ms", hot["wall_ms"], 100),
            ("cold_peak_delta_bytes", cold["peak_delta_bytes"], 64 * 2**20),
        ):
            if observed > limit:
                violations.append(
                    {
                        "sample": row["sample"],
                        "run": row["run"],
                        "reason": reason,
                        "observed": observed,
                        "limit": limit,
                    }
                )
    write_json(args.output / "gates.json", {"enforced": args.enforce, "violations": violations})
    print(
        json.dumps(
            {"samples": summaries, "enforced": args.enforce, "violations": violations},
            ensure_ascii=False,
            indent=2,
        )
    )
    return int(args.enforce and bool(violations))


def differences(expected, actual, path=""):
    if type(expected) is not type(actual):
        return [{"path": path, "expected": expected, "actual": actual}]
    if isinstance(expected, dict):
        result = []
        for key in sorted(set(expected) | set(actual)):
            result.extend(differences(expected.get(key), actual.get(key), f"{path}.{key}"))
        return result
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [{"path": path + ".length", "expected": len(expected), "actual": len(actual)}]
        result = []
        for index, (left, right) in enumerate(zip(expected, actual)):
            result.extend(differences(left, right, f"{path}[{index}]"))
        return result
    return [] if expected == actual else [{"path": path, "expected": expected, "actual": actual}]


def ui_payload(row):
    """Compare consumed facts; auxiliary legacy full-view fields are separate.

    Album release_group is consumed by project/statistics, not chart overview.
    Artist/album history renders seven ranking fields, not member counts.
    The project payload is compared in full so attribution is never discarded.
    """
    payload = copy.deepcopy(row["payload"] or {})
    kind, view = row["sample"]["kind"], row["view"]
    if view == "project":
        return {key: payload.get(key) for key in ("found", "effective_play_count", "album_project")}
    if kind == "album" and isinstance(payload.get("meta"), dict):
        payload["meta"].pop("release_group", None)
    for key in ("album_weekly_history", "artist_weekly_history"):
        for entry in payload.get(key) or []:
            entry.pop("tracks_count", None)
            entry.pop("albums_count", None)
    fields = UI_FIELDS[kind]
    if view == "overview":
        fields += ("year_end_status", "year_end_summary", "year_end_history")
    return {key: payload.get(key) for key in fields}


def compare(args):
    expected, actual = json.loads(args.baseline.read_text()), json.loads(args.candidate.read_text())
    result = []
    project_counts = {
        json.dumps(row["sample"], sort_keys=True): (row["payload"] or {})
        .get("album_project", {})
        .get("unique_canonical_songs")
        for row in expected["rows"]
        if row["sample"]["kind"] == "album"
        and row["view"] == "project"
        and isinstance((row["payload"] or {}).get("album_project"), dict)
    }
    if len(expected["rows"]) != len(actual["rows"]):
        raise ValueError("baseline and candidate sample counts differ")
    for old, new in zip(expected["rows"], actual["rows"]):
        if (old["sample"], old["view"], old["iteration"]) != (
            new["sample"],
            new["view"],
            new["iteration"],
        ):
            raise ValueError("baseline and candidate sample order differs")
        left, right = ui_payload(old), ui_payload(new)
        count_key = json.dumps(old["sample"], sort_keys=True)
        if (
            old["sample"]["kind"] == "album"
            and old["view"] in {"summary", "overview"}
            and count_key in project_counts
        ):
            left["unique_canonical_songs"] = project_counts[count_key]
            right["unique_canonical_songs"] = (new["payload"] or {}).get("unique_canonical_songs")
        result.append(
            {
                "sample": old["sample"],
                "view": old["view"],
                "errors": [old["error"], new["error"]],
                "differences": differences(left, right),
            }
        )
    write_json(args.output, result)
    print(
        json.dumps(
            {"rows": len(result), "differences": sum(len(row["differences"]) for row in result)},
            indent=2,
        )
    )
    return int(any(row["differences"] or any(row["errors"]) for row in result))


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as incoming:
        for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fault_worker(args):
    os.environ.update(environment(args.runtime))
    sys.path.insert(0, str(args.source_root))
    from backend.core.access_surface import set_public_readonly_db_guard
    from backend.domains.billboard import (
        chart_compute,
        chart_year_end_api,
        data_loader,
        detail_views,
        details,
        year_end,
    )
    from backend.domains.billboard.detail_summary import _filter_values, _snapshot_resolution
    from backend.domains.music_search import year_end_projection
    from backend.domains.playback import logical_timeline
    from backend.services import entity_stats_service

    database = args.runtime / "main.db"
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    key, freshness = _snapshot_resolution(conn, _filter_values((1493, *COMMON)))
    if key is None or freshness != "current":
        raise RuntimeError("fault fixture requires the exact ready search publication")
    statements = {
        "missing_aux": (
            "DELETE FROM music_search_detail_projection_state WHERE snapshot_key=?",
            (key,),
        ),
        "corrupt_context": (
            "UPDATE music_search_entity_context SET play_events=play_events+1 WHERE snapshot_key=?",
            (key,),
        ),
        "missing_ledger": (
            "DELETE FROM music_search_weekly_chart_context WHERE snapshot_key=?",
            (key,),
        ),
        "old_projection": (
            "UPDATE music_search_detail_projection_state SET projection_version='old_test_version' WHERE snapshot_key=?",
            (key,),
        ),
        "revision_drift": (
            "UPDATE music_search_revision_state SET metadata_revision=metadata_revision+1 WHERE state_id=1",
            (),
        ),
    }
    conn.execute(*statements[args.fault])
    conn.commit()
    conn.close()
    forbidden = []

    def reject(name):
        def call(*_args, **_kwargs):
            forbidden.append(name)
            raise AssertionError("forbidden heavy fallback: " + name)

        return call

    for module, names in (
        (
            detail_views,
            (
                "get_track_history",
                "get_album_chart_detail",
                "get_artist_chart_detail",
                "_get_album_project_payload",
                "_load_album_project_detail_events",
            ),
        ),
        (
            details,
            (
                "compute_billboard_data",
                "_load_detail_weighted_frame",
                "_load_album_project_detail_events",
                "_get_album_project_payload",
                "_load_detail_access_stats",
            ),
        ),
        (data_loader, ("load_billboard_raw", "_try_load_from_agg")),
        (chart_compute, ("compute_billboard_data", "compute_weekly_data")),
        (chart_year_end_api, ("compute_year_end_staged",)),
        (year_end, ("build_year_end_metric_frame", "build_year_end_response")),
        (year_end_projection, ("build_year_end_projection_rows",)),
        (
            logical_timeline,
            (
                "reconstruct_listening_intervals",
                "reconstruct_logical_plays",
                "build_billboard_weighted_frame",
            ),
        ),
        (entity_stats_service, ("get_track_stats", "get_album_stats", "get_artist_stats")),
    ):
        for name in names:
            if hasattr(module, name):
                setattr(module, name, reject(module.__name__ + "." + name))
    set_public_readonly_db_guard(True)
    before = file_digest(database)
    rows = []
    for sample in SAMPLES:
        for view in ("summary", "overview"):
            try:
                value = getattr(detail_views, f"get_{sample['kind']}_detail_view")(
                    *sample["identity"], *COMMON, view=view
                )
                rows.append(
                    {"sample": sample, "view": view, "unexpected_response": value, "passed": False}
                )
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                detail = getattr(exc, "detail", str(exc))
                rows.append(
                    {
                        "sample": sample,
                        "view": view,
                        "status": status,
                        "detail": detail,
                        "passed": status == 503
                        and isinstance(detail, dict)
                        and detail.get("error") == "snapshot_unavailable",
                    }
                )
    after = file_digest(database)
    report = {
        "fault": args.fault,
        "rows": rows,
        "forbidden_calls": forbidden,
        "main_db_before_sha256": before,
        "main_db_after_sha256": after,
        "all_source_publication_queue_bytes_unchanged": before == after,
    }
    report["passed"] = all(row["passed"] for row in rows) and not forbidden and before == after
    write_json(args.output, report)
    return int(not report["passed"])


def faults(args):
    args.output.mkdir(parents=True, exist_ok=True)
    reports = []
    for fault in (
        "missing_aux",
        "corrupt_context",
        "missing_ledger",
        "old_projection",
        "revision_drift",
    ):
        runtime = args.output / fault / "fault-runtime"
        prepare(args.runtime, runtime)
        target = runtime.parent / "report.json"
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "fault-worker",
                "--runtime",
                str(runtime),
                "--source-root",
                str(args.source_root),
                "--fault",
                fault,
                "--output",
                str(target),
            ],
            capture_output=True,
            text=True,
            env=environment(runtime),
            timeout=180,
        )
        if target.exists():
            report = json.loads(target.read_text())
        else:
            report = {
                "fault": fault,
                "passed": False,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        reports.append(report)
        print(json.dumps({"fault": fault, "passed": report["passed"]}), flush=True)
    write_json(args.output / "summary.json", reports)
    return int(not all(report["passed"] for report in reports))


def version_weights(args):
    """Independent logical-event/duration reconstruction on an owned copy.

    This intentionally runs the timeline as a maintenance audit. It is never
    a GET, performance sample, publication builder or formal-database probe.
    """
    os.environ.update(environment(args.runtime))
    sys.path.insert(0, str(args.source_root))
    from backend.core.access_surface import set_public_readonly_db_guard

    set_public_readonly_db_guard(True)
    from backend.domains.billboard.detail_summary import _filter_values, _snapshot_resolution
    from backend.domains.billboard.details import _load_detail_weighted_frame

    groups = json.loads(args.groups.read_text())
    identities = sorted({int(member["l1_id"]) for group in groups for member in group["members"]})
    database = args.runtime / "main.db"
    before = file_digest(database)
    conn = readonly(database)
    conn.row_factory = sqlite3.Row
    rows = []
    try:
        for dynamic in (True, False):
            weighted = _load_detail_weighted_frame(
                min_ms=30000,
                music_only=True,
                week_start_dow=4,
                week_start_hour=12,
                dynamic_threshold=dynamic,
                max_merge_gap_minutes=5,
                merge_enabled=True,
            )
            weights = (
                weighted[weighted.track_id.isin(identities)]
                .groupby("track_id")[["play_count", "total_ms"]]
                .sum()
                .to_dict("index")
            )
            independent = {
                identity: {
                    "play_count": int(weights.get(identity, {}).get("play_count", 0)),
                    "total_ms": int(weights.get(identity, {}).get("total_ms", 0)),
                }
                for identity in identities
            }
            for level in (2, 3):
                common = list(COMMON)
                common[9], common[12] = dynamic, level
                key, freshness = _snapshot_resolution(
                    conn, _filter_values((identities[0], *common))
                )
                if key is None or freshness != "current":
                    raise RuntimeError("version audit needs an exact ready search publication")
                placeholders = ",".join("?" for _ in identities)
                source = {
                    int(row["l1_id"]): {
                        "play_count": int(row["plays"] or 0),
                        "total_ms": int(row["duration"] or 0),
                    }
                    for row in conn.execute(
                        f"SELECT l1_id,SUM(play_count) plays,SUM(total_ms) duration FROM music_search_detail_source_facts WHERE snapshot_key=? AND l1_id IN ({placeholders}) GROUP BY l1_id",
                        (key, *identities),
                    )
                }
                source = {
                    identity: source.get(identity, {"play_count": 0, "total_ms": 0})
                    for identity in identities
                }
                rows.append(
                    {
                        "merge_level": level,
                        "dynamic_threshold": dynamic,
                        "snapshot_key": key,
                        "freshness": freshness,
                        "independent_owned_raw_timeline": independent,
                        "published_source_facts": source,
                        "equal": source == independent,
                    }
                )
    finally:
        conn.close()
    after = file_digest(database)
    report = {
        "scope": "owned-copy maintenance audit; no GET or performance evidence",
        "ids": identities,
        "rows": rows,
        "main_db_before_sha256": before,
        "main_db_after_sha256": after,
        "source_publication_queue_bytes_unchanged": before == after,
    }
    report["passed"] = before == after and all(row["equal"] for row in rows)
    write_json(args.output, report)
    print(
        json.dumps({"passed": report["passed"], "variants": len(rows), "l1_ids": len(identities)})
    )
    return int(not report["passed"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    backup = sub.add_parser("prepare")
    backup.add_argument("--source", type=Path, required=True)
    backup.add_argument("--destination", type=Path, required=True)
    for mode in ("run", "worker"):
        command = sub.add_parser(mode)
        command.add_argument("--source-root", type=Path, default=ROOT)
        command.add_argument("--runtime", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--spec", type=Path, required=mode == "worker")
        command.add_argument("--rounds", type=int, default=1)
        command.add_argument("--views", default="overview")
        command.add_argument(
            "--http", action="store_true", help="include public HTTP gate and serialization"
        )
        command.add_argument("--repeat", type=int, default=3)
        command.add_argument(
            "--enforce",
            action="store_true",
            help="fail cold/hot/RSS gates at the frozen plan thresholds",
        )
    comparison = sub.add_parser("compare")
    comparison.add_argument("--baseline", type=Path, required=True)
    comparison.add_argument("--candidate", type=Path, required=True)
    comparison.add_argument("--output", type=Path, required=True)
    for mode in ("faults", "fault-worker"):
        command = sub.add_parser(mode)
        command.add_argument("--source-root", type=Path, default=ROOT)
        command.add_argument("--runtime", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if mode == "fault-worker":
            command.add_argument("--fault", required=True)
    weights = sub.add_parser("version-weights")
    weights.add_argument("--source-root", type=Path, default=ROOT)
    weights.add_argument("--runtime", type=Path, required=True)
    weights.add_argument("--groups", type=Path, required=True)
    weights.add_argument("--output", type=Path, required=True)
    weights.add_argument("--owned-copy", action="store_true", required=True)
    args = parser.parse_args()
    for attr in (
        "source_root",
        "runtime",
        "source",
        "destination",
        "output",
        "spec",
        "baseline",
        "candidate",
        "groups",
    ):
        if getattr(args, attr, None) is not None:
            setattr(args, attr, getattr(args, attr).resolve())
    if args.mode == "prepare":
        report = prepare(args.source, args.destination)
        print(
            json.dumps(
                {
                    k: report[k]
                    for k in ("destination", "integrity", "schema_version", "plays", "copied")
                },
                indent=2,
            )
        )
    elif args.mode == "worker":
        worker(args)
    elif args.mode == "run":
        return run(args)
    elif args.mode == "compare":
        return compare(args)
    elif args.mode == "faults":
        return faults(args)
    elif args.mode == "version-weights":
        return version_weights(args)
    else:
        return fault_worker(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

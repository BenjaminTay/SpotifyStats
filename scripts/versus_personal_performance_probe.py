#!/usr/bin/env python3
"""Owned-copy Versus API correctness, latency and resource acceptance.

Every fresh sample uses a separate Python process. Requests execute the real
FastAPI router through TestClient, with no lifespan/startup warmup and no
external transport; this is local API evidence, not HTTPS/browser acceptance.
The supplied source is opened read-only and copied with SQLite Online Backup.
Private rank maintenance writes only the owned derived store.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import itertools
import json
import math
import os
import platform
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
KINDS = ("track", "album", "artist")
COUNTS = (2, 4)
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
)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")
    temporary.replace(path)


def protected_facts(database):
    """Only source/identity/attribution relationships reachable by this work."""
    facts = {}
    # The input contract is a closed Online Backup. A WAL-mode header can
    # survive the backup even though the independent file has no WAL/SHM.
    # Never use immutable when a live sidecar is present.
    immutable = "&immutable=1" if not Path(str(database) + "-wal").exists() else ""
    with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro{immutable}", uri=True)) as conn:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in SOURCE_TABLES:
            if table not in tables:
                continue
            digest = hashlib.sha256()
            count = 0
            for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
                digest.update(
                    json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str).encode()
                )
                digest.update(b"\n")
                count += 1
            facts[table] = {"rows": count, "digest": digest.hexdigest()}
    return facts


class Monitor:
    """Sample current RSS separately from peak RSS and process lifetime peak."""

    def __init__(self):
        import psutil

        self.process = psutil.Process()
        gc.collect()
        self.idle = self.process.memory_info().rss
        self.samples = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        self.process.cpu_percent(None)
        while not self.stop.is_set():
            self.samples.append(
                {
                    "elapsed_ms": (time.perf_counter() - self.started) * 1000,
                    "rss_bytes": self.process.memory_info().rss,
                    "cpu_percent": self.process.cpu_percent(None),
                }
            )
            self.stop.wait(0.02)

    def __enter__(self):
        self.started = time.perf_counter()
        self.cpu_before = self.process.cpu_times()
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join()
        self.elapsed = time.perf_counter() - self.started
        gc.collect()
        self.settled = self.process.memory_info().rss
        self.cpu_after = self.process.cpu_times()

    def report(self):
        peak = max([self.idle, self.settled] + [row["rss_bytes"] for row in self.samples])
        cpu = (
            self.cpu_after.user
            + self.cpu_after.system
            - self.cpu_before.user
            - self.cpu_before.system
        )
        return {
            "idle_rss_mb": self.idle / 2**20,
            "peak_rss_mb": peak / 2**20,
            "settled_rss_mb": self.settled / 2**20,
            "peak_delta_mb": (peak - self.idle) / 2**20,
            "settled_delta_mb": (self.settled - self.idle) / 2**20,
            "cpu_seconds": cpu,
            "elapsed_ms": self.elapsed * 1000,
            "max_cpu_percent": max((row["cpu_percent"] for row in self.samples), default=None),
            "samples": self.samples,
        }


def bootstrap(work):
    sys.path.insert(0, str(ROOT))
    # Config dotenv uses setdefault, so these explicit child values isolate all
    # derived outputs before product imports. No application lifespan is run.
    os.environ.update(
        SPOTIFY_STATS_DB_PATH=str(work / "main.db"),
        SPOTIFY_STATS_WARMUP="0",
        SPOTIFY_STATS_SEARCH_STARTUP_REBUILD="0",
        SPOTIFY_STATS_L3_STARTUP_RECONCILE="0",
    )
    for family in ("ANALYSIS", "BILLBOARD", "COMMUNITY", "ARCHIVE", "YEARLY", "GOVERNANCE"):
        os.environ[f"SPOTIFY_STATS_{family}_CACHE_PATH"] = str(work / f"{family.lower()}.db")
    from fastapi.testclient import TestClient

    from backend.main import app

    return TestClient(app)


def inventory(conn):
    from backend.domains.metadata.artist_identity import get_artist_identity_map
    from backend.domains.metadata.track_credits import get_effective_track_credits
    from backend.domains.playback.track_groups import resolve_track_aggregation_scope
    from backend.services.versus_personal_context import normalise_filters, resolve_selection

    tracks = []
    seen = set()
    rows = conn.execute("""SELECT COALESCE(links.l1_id,p.track_id) AS identity_id,COUNT(*) AS n
        FROM plays p LEFT JOIN track_l1_source_links links ON links.track_id=p.track_id
        WHERE p.track_id IS NOT NULL GROUP BY identity_id ORDER BY n DESC,identity_id""").fetchall()
    for row in rows:
        scope = resolve_track_aggregation_scope(conn, int(row[0]), 2)
        if scope.primary_track_id not in seen:
            seen.add(scope.primary_track_id)
            tracks.append(int(row[0]))
        if len(tracks) == 24:
            break
    albums = []
    for row in conn.execute("""SELECT ap.canonical_name,a.artist_name,COUNT(p.play_id) AS n
        FROM album_projects ap JOIN artists a ON a.artist_id=ap.artist_id
        JOIN album_project_tracks apt ON apt.project_id=ap.project_id
        JOIN plays p ON p.track_id=apt.track_id WHERE ap.scope='release'
        GROUP BY ap.project_id ORDER BY n DESC,ap.project_id"""):
        item = {"album_name": str(row[0]), "artist_name": str(row[1])}
        if item not in albums:
            albums.append(item)
        if len(albums) == 24:
            break
    artists = get_artist_identity_map(conn)
    play_counts = {
        int(row[0]): int(row[1])
        for row in conn.execute(
            "SELECT t.artist_id,COUNT(*) FROM plays p JOIN tracks t ON t.track_id=p.track_id GROUP BY t.artist_id"
        )
    }
    canonical_counts = {}
    for artist_id, count in play_counts.items():
        name = artists[artist_id].display_name
        canonical_counts[name] = canonical_counts.get(name, 0) + count
    credits = get_effective_track_credits(conn)
    collaboration_counts = {}
    per_track = {}
    for row in credits:
        per_track[row["track_id"]] = per_track.get(row["track_id"], 0) + 1
    for row in credits:
        if per_track[row["track_id"]] > 1:
            collaboration_counts[row["artist_name"]] = (
                collaboration_counts.get(row["artist_name"], 0) + 1
            )
    names = sorted(canonical_counts, key=lambda n: (-canonical_counts[n], n))
    selected_artists = ["Taylor Swift"] if "Taylor Swift" in names else []
    collaborators = sorted(
        (name for name in collaboration_counts if name in names),
        key=lambda n: (-collaboration_counts[n], -canonical_counts[n], n),
    )
    for name in collaborators[:1] + names:
        if name not in selected_artists:
            selected_artists.append(name)
        if len(selected_artists) >= 24:
            break
    selections = {"track": tracks, "album": albums, "artist": selected_artists}
    # L3 may merge two selected projects or recordings. Find four identities
    # that remain unique in both contracts, and retain a larger switching pool.
    for kind in KINDS:
        unique = []
        keys = {2: set(), 3: set()}
        for item in selections[kind]:
            try:
                entities = (
                    {
                        level: resolve_selection(conn, kind, [item, selections[kind][-1]], level)[0]
                        for level in (2, 3)
                    }
                    if item != selections[kind][-1]
                    else None
                )
            except ValueError:
                continue
            if entities is None or any(
                entity.entity_key in keys[level] for level, entity in entities.items()
            ):
                continue
            unique.append(item)
            for level, entity in entities.items():
                keys[level].add(entity.entity_key)
        if len(unique) < 4:
            raise ValueError(f"Not enough unique L2/L3 {kind} selections")
        selections[kind] = unique
    return {
        "filters": normalise_filters(conn, {}),
        "selections": selections,
        "artist_collaboration_counts": {
            name: collaboration_counts.get(name, 0) for name in selections["artist"]
        },
    }


def body(kind, items):
    return (
        {"track_ids": items}
        if kind == "track"
        else ({"albums": items} if kind == "album" else {"artist_names": items})
    )


def request(client, kind, items, filters, endpoint):
    from backend.core.access_surface import SURFACE_HEADER

    started = time.perf_counter()
    response = client.post(
        f"/api/billboard/versus/{kind}/personal-{endpoint}",
        json=body(kind, items),
        params=filters,
        headers={SURFACE_HEADER: "public-readonly"},
    )
    elapsed = (time.perf_counter() - started) * 1000
    row = {
        "kind": kind,
        "objects": len(items),
        "endpoint": endpoint,
        "elapsed_ms": elapsed,
        "status": response.status_code,
        "payload_bytes": len(response.content),
        "server_timing": response.headers.get("Server-Timing"),
        "request_id": response.headers.get("X-Request-ID"),
    }
    payload = response.json()
    if response.status_code != 200:
        row["error"] = payload
    return row, payload


def forbid_public_builds():
    from backend.core.job_queue import JobQueue
    from backend.services import analysis_snapshot_store as store
    from backend.services import versus_rank_context_service as ranks

    counters = {"builder": 0, "publish": 0, "enqueue": 0}

    def block(name):
        def fail(*a, **kw):
            counters[name] += 1
            raise AssertionError(f"Public personal read attempted {name}")

        return fail

    ranks.build_payload = block("builder")
    store.publish = block("publish")
    JobQueue.enqueue_if_not_pending = block("enqueue")
    return counters


def legacy_request(client, kind, item, filters):
    params = {key: value for key, value in filters.items() if key != "include_compilations"}
    params["include_rank_context"] = True
    if kind == "track":
        endpoint = f"/api/music/tracks/l1/{item}/stats"
    elif kind == "album":
        endpoint = f"/api/music/albums/{quote(item['album_name'], safe='')}/stats"
        params["artist"] = item["artist_name"]
    else:
        endpoint = f"/api/music/artists/{quote(item, safe='')}/stats"
    started = time.perf_counter()
    response = client.get(endpoint, params=params)
    return {
        "status": response.status_code,
        "elapsed_ms": (time.perf_counter() - started) * 1000,
        "payload_bytes": len(response.content),
        "endpoint": endpoint,
        **({"error": response.json()} if response.status_code != 200 else {}),
    }


def worker(args):
    work = args.work_dir.resolve()
    client = bootstrap(work)
    from backend.core import db
    from backend.services import versus_rank_context_service as ranks

    state = (
        json.loads((work / "inventory.json").read_text())
        if args.phase not in ("prepare", "maintenance")
        else None
    )
    filters = state["filters"] if state else None
    if args.phase == "maintenance":
        from backend.core.job_queue import Job
        from backend.core.migrations import run_migrations

        run_migrations()
        conn = db.get_db(readonly=True)
        records = []
        try:
            process_idle_mb = Monitor().idle / 2**20
            for variant in ranks.default_configurations(conn):
                params, key, metadata, family = ranks.request_context(conn, variant)
                job = Job.create(
                    ranks.JOB_TYPE, family, key, params_json=json.dumps(params, sort_keys=True)
                )
                with Monitor() as monitor:
                    result = ranks.handle_rebuild(job)
                resources = monitor.report()
                resources["peak_delta_from_process_idle_mb"] = (
                    resources["peak_rss_mb"] - process_idle_mb
                )
                resources["settled_delta_from_process_idle_mb"] = (
                    resources["settled_rss_mb"] - process_idle_mb
                )
                records.append(
                    {
                        "filters": params,
                        "context": metadata,
                        "result": result,
                        "resources": resources,
                        "global_play_frames": {
                            "plays": db._load_plays_cached.cache_info().currsize,
                            "artists": db._load_plays_for_artists_cached.cache_info().currsize,
                        },
                    }
                )
            return {
                "phase": "maintenance",
                "invocation": "handle_rebuild(Job.create(...))_four_serial_variants",
                "process_idle_rss_mb": process_idle_mb,
                "rank_builder_version": ranks.VERSION,
                "variants": records,
            }
        finally:
            conn.close()
    if args.phase == "prepare":
        from backend.core.job_queue import Job
        from backend.core.migrations import run_migrations

        run_migrations()
        conn = db.get_db(readonly=True)
        try:
            state = inventory(conn)
            from backend.services.versus_personal_context import context

            state["context"] = context(conn, state["filters"])
            state["rank_builder_version"] = ranks.VERSION
            state["schema_version"] = conn.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            state["plays"] = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
            state["rank_contexts"] = []
            state["maintenance_invocation"] = "handle_rebuild(Job.create(...))"
            for variant in ranks.default_configurations(conn):
                params, key, _, family = ranks.request_context(conn, variant)
                job = Job.create(
                    ranks.JOB_TYPE, family, key, params_json=json.dumps(params, sort_keys=True)
                )
                with Monitor() as monitor:
                    started = time.perf_counter()
                    result = ranks.handle_rebuild(job)
                state["rank_contexts"].append(
                    {
                        "filters": variant,
                        "result": result,
                        "elapsed_ms": (time.perf_counter() - started) * 1000,
                        "resources": monitor.report(),
                    }
                )
            write_json(work / "inventory.json", state)
            return state
        finally:
            conn.close()
    items = state["selections"][args.kind][: args.count]
    if args.phase == "old":
        from backend.services import entity_stats_service

        # Exercise the original full-library rank calculation even for artists
        # now served by the unrelated artist detail rank publication.
        entity_stats_service._is_primary_connection = lambda conn: False
        with Monitor() as monitor:
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=args.count) as pool:
                samples = list(
                    pool.map(lambda item: legacy_request(client, args.kind, item, filters), items)
                )
            wall = (time.perf_counter() - started) * 1000
        return {
            "phase": "legacy_full_detail_concurrent",
            "baseline_mode": "full_library_detail_builder_primary_publication_and_entity_cache_bypassed",
            "kind": args.kind,
            "count": args.count,
            "batch_wall_ms": wall,
            "samples": samples,
            "resources": monitor.report(),
        }
    if args.phase == "oracle":
        return correctness(client, state)
    counters = forbid_public_builds()
    samples = []
    with Monitor() as monitor:
        repeats = 1 if args.phase == "fresh" else args.warm_runs + 1
        for sequence in range(repeats):
            for endpoint in ("stats", "ranks"):
                sample, _ = request(client, args.kind, items, filters, endpoint)
                sample.update(
                    sequence=sequence,
                    process_pid=os.getpid(),
                    process_state="fresh" if sequence == 0 else "same_process",
                )
                samples.append(sample)
    resources = monitor.report()
    switching = []
    switch_resources = None
    if args.phase == "warm" and args.count == 4:
        pool = state["selections"][args.kind]
        with Monitor() as switch_monitor:
            queues = list(itertools.islice(itertools.combinations(pool, 4), 20))
            for selected_tuple in queues:
                selected = list(selected_tuple)
                for endpoint in ("stats", "ranks"):
                    sample, _ = request(client, args.kind, selected, filters, endpoint)
                    sample["selection"] = selected
                    switching.append(sample)
        switch_resources = switch_monitor.report()
    return {
        "phase": args.phase,
        "kind": args.kind,
        "count": args.count,
        "samples": samples,
        "resources": resources,
        "switch_samples": switching,
        "switch_resources": switch_resources,
        "public_side_effects": counters,
        "aggregate_cache": __import__(
            "backend.services.versus_personal_stats_service", fromlist=["_RESULT_CACHE"]
        )._RESULT_CACHE.cache_stats(),
        "global_play_frames": {
            "plays": db._load_plays_cached.cache_info().currsize,
            "artists": db._load_plays_for_artists_cached.cache_info().currsize,
        },
    }


def correctness(client, state):
    from backend.core import db
    from backend.domains.playback.album_projects import apply_canonical_song_keys
    from backend.domains.playback.logical_timeline import get_listening_duration_frame
    from backend.domains.playback.track_groups import resolve_track_aggregation_scope
    from backend.services import entity_stats_service
    from backend.services.analysis_stats_service import (
        _daily_metrics,
        _daily_trend,
        _summary,
        build_duration_frame,
        chart_rows,
        filter_period_events,
        resolve_period,
    )
    from backend.services.versus_personal_context import resolve_selection

    comparisons = []
    rank_comparisons = []
    published_api_comparisons = []
    edge_differences = []
    conn = db.get_db(readonly=True)
    try:
        for level in (2, 3):
            for dynamic in (False, True):
                params = {**state["filters"], "merge_level": level, "dynamic_threshold": dynamic}
                from backend.services import versus_rank_context_service as ranks

                published_variants = {}
                for compilations in (False, True):
                    rank_params = {**params, "include_compilations": compilations}
                    # This is explicit owned-copy maintenance, outside public
                    # requests. Validate the actual builder and publication,
                    # not only its rank aggregation on the oracle's frames.
                    ranks.ensure(conn, rank_params)
                    published_variants[compilations], _ = ranks.read(conn, rank_params)
                loader_params = {
                    key: params[key]
                    for key in (
                        "min_ms",
                        "music_only",
                        "merge_enabled",
                        "dynamic_threshold",
                        "max_merge_gap_minutes",
                    )
                }
                for kind in KINDS:
                    loader = db.load_plays_for_artists if kind == "artist" else db.load_plays
                    events = loader(conn, **loader_params)
                    duration = get_listening_duration_frame(events)
                    if duration is None:
                        raise AssertionError("Full oracle missing listening-duration track")
                    if kind == "album":
                        events = apply_canonical_song_keys(events, conn, level)
                        duration = apply_canonical_song_keys(duration, conn, level)
                    selected = resolve_selection(conn, kind, state["selections"][kind][:4], level)
                    expected = {}
                    for item in selected:
                        if kind == "track":
                            scope = resolve_track_aggregation_scope(conn, item.track_id, level)
                            entity_events = events[events["track_id"].isin(scope.member_track_ids)]
                            entity_duration = duration[
                                duration["track_id"].isin(scope.member_track_ids)
                            ]
                        elif kind == "album":
                            keys = entity_stats_service._resolve_album_project_song_keys(
                                conn, item.album_name, item.artist_name, level, item.project_id
                            )
                            entity_events = events[events["canonical_song_key"].isin(keys)]
                            entity_duration = duration[duration["canonical_song_key"].isin(keys)]
                        else:
                            entity_events = events[events["artist_name"] == item.artist_name]
                            entity_duration = duration[duration["artist_name"] == item.artist_name]
                        slices = build_duration_frame(
                            entity_events, duration_source=entity_duration
                        )
                        summary = _summary(entity_events, slices)
                        daily = _daily_metrics(summary)
                        expected[item.entity_key] = {
                            **{
                                key: summary[key]
                                for key in ("total_plays", "total_hours", "active_days")
                            },
                            **{key: daily[key] for key in ("avg_daily_plays", "avg_daily_hours")},
                            "max_daily_plays": max(
                                (row["plays"] for row in _daily_trend(entity_events, slices)),
                                default=0,
                            ),
                        }
                        old_slices = build_duration_frame(
                            entity_events,
                            resolve_period(events, "lifetime", None, None),
                            duration_source=entity_duration,
                        )
                        if int(old_slices["ms_played"].sum()) != int(slices["ms_played"].sum()):
                            edge_differences.append(
                                {
                                    "entity_key": item.entity_key,
                                    "filters": params,
                                    "old_clipped_ms": int(old_slices["ms_played"].sum()),
                                    "all_listening_ms": int(slices["ms_played"].sum()),
                                    "reason": "count-qualified lifetime boundaries omitted edge listening",
                                }
                            )
                    for compilations in (
                        (False, True) if kind == "album" else (params["include_compilations"],)
                    ):
                        batch_params = {**params, "include_compilations": compilations}
                        for count in (2, 3, 4):
                            sample, payload = request(
                                client,
                                kind,
                                state["selections"][kind][:count],
                                batch_params,
                                "stats",
                            )
                            mismatches = []
                            for entity in payload.get("entities", []):
                                if entity["metrics"] != expected.get(entity["entity_key"]):
                                    mismatches.append(
                                        {
                                            "entity": entity,
                                            "expected": expected.get(entity["entity_key"]),
                                        }
                                    )
                            comparisons.append(
                                {
                                    "filters": batch_params,
                                    "sample": sample,
                                    "observed_entities": payload.get("entities"),
                                    "expected_entities": {
                                        entity["entity_key"]: expected[entity["entity_key"]]
                                        for entity in payload.get("entities", [])
                                    },
                                    "mismatches": mismatches,
                                    "pass": sample["status"] == 200 and not mismatches,
                                }
                            )
                            rank_sample, rank_response = request(
                                client,
                                kind,
                                state["selections"][kind][:count],
                                batch_params,
                                "ranks",
                            )
                            identities = {item.entity_key: item for item in selected}
                            expected_api_ranks = {
                                item.entity_key: {
                                    period: published_variants[compilations]["ranks"][kind][
                                        period
                                    ].get(item.rank_key)
                                    for period in ranks.PERIODS
                                }
                                for item in selected[:count]
                            }
                            rank_mismatches = [
                                {
                                    "entity": entity,
                                    "expected": expected_api_ranks.get(entity["entity_key"]),
                                }
                                for entity in rank_response.get("entities", [])
                                if entity["entity_key"] not in identities
                                or entity["ranks"] != expected_api_ranks.get(entity["entity_key"])
                            ]
                            published_api_comparisons.append(
                                {
                                    "filters": batch_params,
                                    "sample": rank_sample,
                                    "expected_entities": expected_api_ranks,
                                    "observed_entities": rank_response.get("entities"),
                                    "mismatches": rank_mismatches,
                                    "pass": rank_sample["status"] == 200
                                    and len(rank_response.get("entities", [])) == count
                                    and not rank_mismatches,
                                }
                            )
                    slices = build_duration_frame(events, duration_source=duration)
                    # Complete public chart serialization is the independent
                    # rank oracle; it must not be truncated to a top-N page.
                    for compilations in (
                        (False, True) if kind == "album" else (params["include_compilations"],)
                    ):
                        rank_params = {**params, "include_compilations": compilations}
                        for period in ranks.PERIODS:
                            bounds = resolve_period(events, period, None, None)
                            period_events = filter_period_events(events, bounds)
                            period_duration = (
                                slices
                                if period == "lifetime"
                                else ranks._filter_slices(slices, bounds)
                            )
                            _, rows = chart_rows(
                                conn,
                                period_events,
                                kind,
                                "plays",
                                1_000_000,
                                0,
                                merge_level=level,
                                include_compilations=compilations,
                                duration_frame=period_duration,
                            )
                            key_name = {
                                "track": "track_id",
                                "album": "album_project_id",
                                "artist": "artist_name",
                            }[kind]
                            oracle_map = {}
                            for row in rows:
                                if row["plays"] > 0:
                                    key = (
                                        str(row[key_name])
                                        if kind == "artist"
                                        else str(int(row[key_name]))
                                    )
                                    oracle_map.setdefault(key, row["rank"])
                            observed = published_variants[compilations]["ranks"][kind][period]
                            rank_comparisons.append(
                                {
                                    "kind": kind,
                                    "period": period,
                                    "filters": rank_params,
                                    "oracle_entities": len(oracle_map),
                                    "actual_entities": len(observed),
                                    "pass": observed == oracle_map,
                                    "mismatches": [
                                        {
                                            "key": key,
                                            "expected": oracle_map.get(key),
                                            "actual": observed.get(key),
                                        }
                                        for key in set(oracle_map) | set(observed)
                                        if oracle_map.get(key) != observed.get(key)
                                    ],
                                }
                            )
                    del events, duration, slices
    finally:
        conn.close()
    return {
        "basic_comparisons": comparisons,
        "rank_comparisons": rank_comparisons,
        "published_rank_api_comparisons": published_api_comparisons,
        "lifetime_edge_corrections": edge_differences,
        "pass": all(
            row["pass"] for row in comparisons + rank_comparisons + published_api_comparisons
        ),
    }


def summary(results, args):
    gates = [
        {
            "requirement": "complete_sample_counts",
            "fresh_runs": args.fresh_runs,
            "warm_runs": args.warm_runs,
            "pass": args.fresh_runs >= 5 and args.warm_runs >= 21,
        }
    ]
    for row in results:
        if row.get("phase") not in ("fresh", "warm"):
            continue
        if row["phase"] == "fresh":
            for sample in row["samples"]:
                budget = (
                    500
                    if sample["endpoint"] == "ranks"
                    else (1500 if row["kind"] == "artist" else 1000)
                )
                gates.append(
                    {
                        "requirement": "fresh_api",
                        "kind": row["kind"],
                        "count": row["count"],
                        "endpoint": sample["endpoint"],
                        "observed_ms": sample["elapsed_ms"],
                        "budget_ms": budget,
                        "pass": sample["status"] == 200 and sample["elapsed_ms"] <= budget,
                    }
                )
        else:
            for endpoint in ("stats", "ranks"):
                samples = [
                    sample
                    for sample in row["samples"]
                    if sample["endpoint"] == endpoint and sample["sequence"] > 0
                ]
                values = sorted(sample["elapsed_ms"] for sample in samples)
                p95 = values[math.ceil(len(values) * 0.95) - 1]
                gates.append(
                    {
                        "requirement": "same_process_p95",
                        "kind": row["kind"],
                        "count": row["count"],
                        "endpoint": endpoint,
                        "samples": len(values),
                        "observed_ms": p95,
                        "budget_ms": 500,
                        "pass": all(sample["status"] == 200 for sample in samples) and p95 <= 500,
                    }
                )
        if row["count"] == 4:
            gates.append(
                {
                    "requirement": "four_object_peak_rss",
                    "kind": row["kind"],
                    "delta_mb": row["resources"]["peak_delta_mb"],
                    "budget_mb": 256,
                    "pass": row["resources"]["peak_delta_mb"] <= 256,
                }
            )
        if row.get("switch_resources"):
            gates.append(
                {
                    "requirement": "twenty_switch_settled_rss",
                    "kind": row["kind"],
                    "delta_mb": row["switch_resources"]["settled_delta_mb"],
                    "budget_mb": 128,
                    "distinct_selections": len(
                        {
                            json.dumps(sample["selection"], sort_keys=True)
                            for sample in row["switch_samples"]
                        }
                    ),
                    "pass": row["switch_resources"]["settled_delta_mb"] <= 128
                    and len(
                        {
                            json.dumps(sample["selection"], sort_keys=True)
                            for sample in row["switch_samples"]
                        }
                    )
                    >= 20
                    and all(sample["status"] == 200 for sample in row["switch_samples"]),
                }
            )
        gates.append(
            {
                "requirement": "public_no_build_publish_enqueue",
                "kind": row["kind"],
                "observed": row["public_side_effects"],
                "pass": not any(row["public_side_effects"].values()),
            }
        )
    return {
        "gates": gates,
        "pass": all(gate["pass"] for gate in gates),
        "fresh_process_runs_per_case": args.fresh_runs,
        "warm_observations_after_first": args.warm_runs,
        "sampling_limits": "Five fresh observations are individually reported; no fresh P95 claim.",
    }


def main(args):
    if args.worker:
        write_json(args.worker_output, worker(args))
        return 0
    source = args.database.expanduser().resolve()
    work = args.work_dir.expanduser().resolve()
    if (
        source == (ROOT / "data/spotify_stats.db").resolve()
        or (ROOT / "data").resolve() in work.parents
    ):
        raise ValueError("Use an explicitly owned Online Backup and an output work directory")
    work.mkdir(parents=True, exist_ok=True)
    owned = work / "main.db"
    if owned.exists():
        raise FileExistsError(
            "Acceptance work directory already has main.db; choose a new run directory"
        )
    source_before = protected_facts(source)
    immutable = "&immutable=1" if not Path(str(source) + "-wal").exists() else ""
    with (
        closing(sqlite3.connect(f"{source.as_uri()}?mode=ro{immutable}", uri=True)) as src,
        closing(sqlite3.connect(owned)) as dst,
    ):
        src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")
    report = {
        "contract": "versus-personal-performance/1",
        "transport": "in_process_fastapi_testclient_no_lifespan",
        "source_database": str(source),
        "owned_database": str(owned),
        "machine": {
            "platform": platform.platform(),
            "python": sys.version,
            "cpu_count": os.cpu_count(),
        },
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "working_tree": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        "source_facts_before": source_before,
        "results": [],
    }
    jobs = [("prepare", "track", 2, 0)]
    jobs += [("old", kind, count, 0) for kind in KINDS for count in COUNTS]
    jobs += [
        ("fresh", kind, count, run)
        for kind in KINDS
        for count in COUNTS
        for run in range(args.fresh_runs)
    ]
    jobs += [("warm", kind, count, 0) for kind in KINDS for count in COUNTS]
    jobs += [("oracle", "track", 4, 0)]
    if args.maintenance_only:
        jobs = [("maintenance", "track", 4, 0)]
    for index, (phase, kind, count, run) in enumerate(jobs):
        print(f"[{index + 1}/{len(jobs)}] {phase} {kind} {count} run={run + 1}", flush=True)
        target = work / f"{index:03d}-{phase}-{kind}-{count}.json"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--phase",
            phase,
            "--kind",
            kind,
            "--count",
            str(count),
            "--work-dir",
            str(work),
            "--worker-output",
            str(target),
            "--warm-runs",
            str(args.warm_runs),
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if completed.returncode:
            report["failure"] = {
                "phase": phase,
                "kind": kind,
                "count": count,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
            write_json(args.json_output, report)
            print(completed.stderr, file=sys.stderr)
            return completed.returncode
        result = json.loads(target.read_text())
        result["fresh_run_index"] = run
        report["results"].append(result)
        write_json(args.json_output, report)
    report["source_facts_after"] = protected_facts(source)
    report["owned_facts_after"] = protected_facts(owned)
    report["protected_source_unchanged"] = source_before == report["source_facts_after"]
    report["protected_owned_unchanged"] = source_before == report["owned_facts_after"]
    if args.maintenance_only:
        variants = report["results"][0]["variants"]
        peak_delta = max(row["resources"]["peak_delta_from_process_idle_mb"] for row in variants)
        budget = args.available_memory_mb * 0.75 if args.available_memory_mb else None
        report["performance"] = {
            "peak_added_rss_mb": peak_delta,
            "available_memory_mb": args.available_memory_mb,
            "added_rss_budget_mb": budget,
            "budget_basis": "New RSS above process idle compared with 75% of available memory",
            "no_retained_global_play_frames": all(
                not any(row["global_play_frames"].values()) for row in variants
            ),
            "pass": all(row["result"]["exact"] for row in variants)
            and all(not any(row["global_play_frames"].values()) for row in variants)
            and (budget is None or peak_delta <= budget),
        }
    else:
        report["performance"] = summary(report["results"], args)
    report["pass"] = (
        report["performance"]["pass"]
        and (args.maintenance_only or report["results"][-1]["pass"])
        and report["protected_source_unchanged"]
        and report["protected_owned_unchanged"]
    )
    write_json(args.json_output, report)
    print(
        json.dumps({"pass": report["pass"], "report": str(args.json_output)}, ensure_ascii=False),
        flush=True,
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--fresh-runs", type=int, default=5)
    parser.add_argument("--warm-runs", type=int, default=21)
    parser.add_argument(
        "--maintenance-only", action="store_true", help="Measure four real serial rebuild jobs"
    )
    parser.add_argument(
        "--available-memory-mb", type=float, help="Available memory for the added RSS budget"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--phase",
        choices=("prepare", "maintenance", "old", "fresh", "warm", "oracle"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--kind", choices=KINDS, default="track", help=argparse.SUPPRESS)
    parser.add_argument("--count", type=int, choices=COUNTS, default=2, help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if not arguments.worker and (not arguments.database or not arguments.json_output):
        parser.error("--database and --json-output are required")
    if arguments.fresh_runs < 1 or arguments.warm_runs < 1:
        parser.error("Sample counts must be positive")
    raise SystemExit(main(arguments))

#!/usr/bin/env python3
"""Verify lightweight detail shells, lossless subviews, and latency gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import urlopen

DEFAULT_QUERY = {
    "min_ms": 30_000,
    "music_only": "true",
    "merge_enabled": "true",
    "dynamic_threshold": "true",
    "max_merge_gap_minutes": 5,
    "merge_level": 2,
    "include_compilations": "false",
    "bb_top_n": 30,
    "bb_album_top_n": 20,
    "bb_artist_top_n": 20,
    "bb_week_start_dow": 4,
    "bb_week_start_hour": 12,
}


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def fetch(base_url: str, path: str, **params: Any) -> tuple[Any, dict[str, Any]]:
    query = {**DEFAULT_QUERY, **params}
    url = f"{base_url.rstrip('/')}{path}?{urlencode(query)}"
    started = time.perf_counter()
    with urlopen(url, timeout=120) as response:  # noqa: S310 - explicit local probe URL
        raw = response.read()
        server_timing = response.headers.get("Server-Timing")
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return json.loads(raw), {
        "elapsed_ms": elapsed_ms,
        "bytes": len(raw),
        "server_timing": server_timing,
    }


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label} differs: {digest(actual)} != {digest(expected)}")


def verify_track(base_url: str, track_id: int) -> tuple[dict, dict]:
    path = f"/api/billboard/track/{track_id}"
    summary, summary_metric = fetch(base_url, path, view="summary")
    full, full_metric = fetch(base_url, path, view="full")
    overview, overview_metric = fetch(base_url, path, view="overview")

    assert_equal(overview, full, "track overview/full")
    for key in (
        "found",
        "chart_status",
        "track_id",
        "track_name",
        "artist_name",
        "artist_names",
        "primary_artist_name",
        "cover_url",
        "summary",
    ):
        assert_equal(summary.get(key), full.get(key), f"track summary.{key}")
    expected_meta = dict(full.get("meta") or {})
    expected_meta.pop("version_group", None)
    assert_equal(summary.get("meta"), expected_meta or None, "track summary.meta")
    assert_equal(summary.get("history"), [], "track summary.history")
    assert_equal(summary.get("chart_data"), {}, "track summary.chart_data")
    return full, {"full": full_metric, "summary": summary_metric, "overview": overview_metric}


def verify_album(base_url: str, album_name: str, artist_name: str) -> tuple[dict, dict]:
    path = f"/api/billboard/album/{quote(album_name, safe='')}"
    common = {"artist_name": artist_name}
    summary, summary_metric = fetch(base_url, path, **common, view="summary")
    full, full_metric = fetch(base_url, path, **common, view="full")
    overview, overview_metric = fetch(base_url, path, **common, view="overview")
    tracks, tracks_metric = fetch(base_url, path, **common, view="tracks")
    project, project_metric = fetch(base_url, path, **common, view="project")

    shared = (
        "found",
        "chart_status",
        "effective_play_count",
        "album_name",
        "artist_name",
        "cover_url",
        "chart_summary",
    )
    for key in shared:
        assert_equal(summary.get(key), full.get(key), f"album summary.{key}")
    expected_meta = dict(full.get("meta") or {})
    expected_meta.pop("release_group", None)
    assert_equal(summary.get("meta"), expected_meta, "album summary.meta")
    assert_equal(summary.get("info"), None, "album summary.info")
    assert_equal(summary.get("track_chart_status"), None, "album summary.track_chart_status")
    for key in ("album_weekly_history", "album_no1_by_week", "best_singles_overlay"):
        assert_equal(overview.get(key), full.get(key), f"album overview.{key}")
    assert_equal(tracks.get("tracks"), full.get("tracks"), "album tracks")
    assert_equal(project.get("album_project"), full.get("album_project"), "album project")
    assert_equal(project.get("meta"), full.get("meta"), "album project.meta")
    return full, {
        "full": full_metric,
        "summary": summary_metric,
        "overview": overview_metric,
        "tracks": tracks_metric,
        "project": project_metric,
    }


def verify_artist(base_url: str, artist_name: str, page_size: int) -> tuple[dict, dict]:
    path = f"/api/billboard/artist/{quote(artist_name, safe='')}"
    summary, summary_metric = fetch(base_url, path, view="summary")
    full, full_metric = fetch(base_url, path, view="full")
    overview, overview_metric = fetch(base_url, path, view="overview")
    albums, albums_metric = fetch(base_url, path, view="albums")

    shared = (
        "found",
        "chart_status",
        "effective_play_count",
        "artist_name",
        "cover_url",
        "meta",
        "chart_summary",
    )
    for key in shared:
        assert_equal(summary.get(key), full.get(key), f"artist summary.{key}")
    assert_equal(summary.get("info"), None, "artist summary.info")
    assert_equal(summary.get("track_chart_status"), None, "artist summary.track_chart_status")
    assert_equal(summary.get("album_chart_status"), None, "artist summary.album_chart_status")
    for key in (
        "artist_weekly_history",
        "artist_no1_by_week",
        "week_no1_albums",
        "best_singles_overlay",
        "best_albums_overlay",
    ):
        assert_equal(overview.get(key), full.get(key), f"artist overview.{key}")
    assert_equal(albums.get("albums"), full.get("albums"), "artist albums")

    pages: list[dict] = []
    rebuilt_tracks: list[dict] = []
    total = len(full.get("tracks") or [])
    for offset in range(0, total, page_size):
        page, metric = fetch(base_url, path, view="tracks", limit=page_size, offset=offset)
        assert_equal(page.get("tracks_total"), total, "artist tracks_total")
        rebuilt_tracks.extend(page.get("tracks") or [])
        pages.append(metric)
    assert_equal(rebuilt_tracks, full.get("tracks") or [], "artist paginated tracks")
    return full, {
        "full": full_metric,
        "summary": summary_metric,
        "overview": overview_metric,
        "albums": albums_metric,
        "track_pages": pages,
    }


def compare_baseline(payload: dict, baseline_dir: Path | None, filename: str) -> bool | None:
    if baseline_dir is None:
        return None
    expected = json.loads((baseline_dir / filename).read_text(encoding="utf-8"))
    assert_equal(payload, expected, f"baseline {filename}")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--track-id", type=int, required=True)
    parser.add_argument("--album-name", required=True)
    parser.add_argument("--album-artist", required=True)
    parser.add_argument("--artist-name", required=True)
    parser.add_argument("--artist-track-page-size", type=int, default=50)
    parser.add_argument("--baseline-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-summary-ms", type=float, default=500.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    track, track_metrics = verify_track(args.base_url, args.track_id)
    album, album_metrics = verify_album(args.base_url, args.album_name, args.album_artist)
    artist, artist_metrics = verify_artist(
        args.base_url,
        args.artist_name,
        args.artist_track_page_size,
    )
    summary_times = {
        "track": track_metrics["summary"]["elapsed_ms"],
        "album": album_metrics["summary"]["elapsed_ms"],
        "artist": artist_metrics["summary"]["elapsed_ms"],
    }
    too_slow = {
        kind: elapsed for kind, elapsed in summary_times.items() if elapsed > args.max_summary_ms
    }
    if too_slow:
        raise AssertionError(
            f"detail summary latency exceeds {args.max_summary_ms:.0f}ms: {too_slow}"
        )
    report = {
        "status": "pass",
        "facts": {
            "track": {
                "sha256": digest(track),
                "baseline_equal": compare_baseline(track, args.baseline_dir, "track_detail.json"),
            },
            "album": {
                "sha256": digest(album),
                "baseline_equal": compare_baseline(album, args.baseline_dir, "album_detail.json"),
            },
            "artist": {
                "sha256": digest(artist),
                "baseline_equal": compare_baseline(artist, args.baseline_dir, "artist_detail.json"),
            },
        },
        "metrics": {"track": track_metrics, "album": album_metrics, "artist": artist_metrics},
        "gates": {
            "max_summary_ms": args.max_summary_ms,
            "summary_elapsed_ms": summary_times,
        },
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

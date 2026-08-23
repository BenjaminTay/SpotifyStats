from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from backend.domains.playback.logical_delta import (
    TRACK_LOGICAL_DELTA_COLUMNS,
    build_tail_track_logical_delta,
    project_track_logical_delta,
    project_track_logical_delta_levels,
)

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL,
            ts_date TEXT,
            ts_year INTEGER,
            ts_month INTEGER,
            ts_dow INTEGER,
            ts_hour INTEGER,
            track_id INTEGER,
            source_album_id INTEGER,
            ms_played INTEGER NOT NULL,
            import_generation_id TEXT
        );
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            album_id INTEGER,
            artist_id INTEGER,
            spotify_track_id TEXT
        );
        CREATE TABLE spotify_track_meta(
            spotify_track_id TEXT PRIMARY KEY,
            duration_ms INTEGER
        );
        CREATE INDEX idx_test_plays_ts ON plays(ts, play_id);
        """
    )
    return conn


def _add_track(conn: sqlite3.Connection, track_id: int, *, duration_ms: int) -> None:
    conn.execute(
        "INSERT INTO tracks VALUES (?, ?, ?, ?)",
        (track_id, track_id * 10, track_id * 100, f"track-{track_id}"),
    )
    conn.execute(
        "INSERT INTO spotify_track_meta VALUES (?, ?)",
        (f"track-{track_id}", duration_ms),
    )


def _add_play(
    conn: sqlite3.Connection,
    *,
    play_id: int,
    ts: str,
    track_id: int,
    source_album_id: int | None,
    ms_played: int,
    generation_id: str,
) -> None:
    parsed = pd.Timestamp(ts).tz_convert("Asia/Shanghai")
    conn.execute(
        """INSERT INTO plays(
               play_id, ts, ts_date, ts_year, ts_month, ts_dow, ts_hour,
               track_id, source_album_id, ms_played, import_generation_id
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            play_id,
            ts,
            parsed.date().isoformat(),
            parsed.year,
            parsed.month,
            parsed.dayofweek,
            parsed.hour,
            track_id,
            source_album_id,
            ms_played,
            generation_id,
        ),
    )


@pytest.mark.parametrize("dynamic_threshold", [False, True])
def test_tail_delta_walks_long_preceding_chain_without_lifetime_scan(
    dynamic_threshold: bool,
) -> None:
    conn = _connection()
    try:
        _add_track(conn, 1, duration_ms=60_000)
        base = pd.Timestamp("2026-01-01T00:00:00Z")
        for index in range(300):
            _add_play(
                conn,
                play_id=index + 1,
                ts=(base + pd.Timedelta(seconds=index + 1)).isoformat(),
                track_id=1,
                source_album_id=11,
                ms_played=1_000,
                generation_id="base",
            )
        _add_play(
            conn,
            play_id=301,
            ts=(base + pd.Timedelta(seconds=330)).isoformat(),
            track_id=1,
            source_album_id=11,
            ms_played=30_000,
            generation_id="append",
        )
        statements: list[str] = []
        conn.set_trace_callback(statements.append)

        delta = build_tail_track_logical_delta(
            conn,
            generation_id="append",
            min_ms=30_000,
            music_only=True,
            dynamic_threshold=dynamic_threshold,
            max_gap_minutes=5,
        )
        conn.set_trace_callback(None)

        assert delta.to_dict("records") == [
            {
                "track_id": 1,
                "source_album_id": 11,
                "play_events": 1,
                "total_ms": 30_000,
            }
        ]
        source_queries = [sql for sql in statements if "FROM plays p" in sql and "SELECT" in sql]
        assert source_queries
        assert all("WHERE" in sql for sql in source_queries)
        preceding_queries = [sql for sql in source_queries if "ORDER BY p.ts DESC" in sql]
        assert len(preceding_queries) >= 2
        assert all("LIMIT" in sql for sql in preceding_queries)
    finally:
        conn.close()


def test_tail_delta_distinguishes_static_and_dynamic_thresholds() -> None:
    conn = _connection()
    try:
        _add_track(conn, 1, duration_ms=600_000)
        _add_play(
            conn,
            play_id=1,
            ts="2026-01-01T00:00:30Z",
            track_id=1,
            source_album_id=11,
            ms_played=30_000,
            generation_id="append",
        )

        fixed = build_tail_track_logical_delta(
            conn,
            generation_id="append",
            min_ms=30_000,
            music_only=True,
            dynamic_threshold=False,
            max_gap_minutes=5,
        )
        dynamic = build_tail_track_logical_delta(
            conn,
            generation_id="append",
            min_ms=30_000,
            music_only=True,
            dynamic_threshold=True,
            max_gap_minutes=5,
        )

        assert fixed[["play_events", "total_ms"]].to_dict("records") == [
            {"play_events": 1, "total_ms": 30_000}
        ]
        assert dynamic.empty
        assert tuple(dynamic.columns) == TRACK_LOGICAL_DELTA_COLUMNS
    finally:
        conn.close()


def test_tail_delta_preserves_source_album_run_boundary() -> None:
    conn = _connection()
    try:
        _add_track(conn, 1, duration_ms=60_000)
        _add_play(
            conn,
            play_id=1,
            ts="2026-01-01T00:00:00Z",
            track_id=1,
            source_album_id=11,
            ms_played=30_000,
            generation_id="base",
        )
        _add_play(
            conn,
            play_id=2,
            ts="2026-01-01T00:00:30Z",
            track_id=1,
            source_album_id=12,
            ms_played=30_000,
            generation_id="append",
        )

        delta = build_tail_track_logical_delta(
            conn,
            generation_id="append",
            min_ms=30_000,
            music_only=True,
            dynamic_threshold=True,
            max_gap_minutes=5,
        )

        assert delta.to_dict("records") == [
            {
                "track_id": 1,
                "source_album_id": 12,
                "play_events": 1,
                "total_ms": 30_000,
            }
        ]
    finally:
        conn.close()


def test_tail_delta_keeps_full_duration_when_interval_crosses_billboard_week() -> None:
    conn = _connection()
    try:
        _add_track(conn, 1, duration_ms=10_800_000)
        _add_play(
            conn,
            play_id=1,
            ts="2026-01-01T16:30:00Z",
            track_id=1,
            source_album_id=11,
            ms_played=7_200_000,
            generation_id="append",
        )

        delta = build_tail_track_logical_delta(
            conn,
            generation_id="append",
            min_ms=30_000,
            music_only=True,
            dynamic_threshold=True,
            max_gap_minutes=5,
        )

        assert delta.to_dict("records") == [
            {
                "track_id": 1,
                "source_album_id": 11,
                "play_events": 1,
                "total_ms": 7_200_000,
            }
        ]
    finally:
        conn.close()


def test_track_delta_projects_to_l1_l2_l3_without_losing_source_boundary() -> None:
    delta = pd.DataFrame(
        [
            {"track_id": 1, "source_album_id": 11, "play_events": 1, "total_ms": 10},
            {"track_id": 2, "source_album_id": 11, "play_events": 2, "total_ms": 20},
            {"track_id": 3, "source_album_id": 12, "play_events": 3, "total_ms": 30},
            {"track_id": 4, "source_album_id": None, "play_events": 4, "total_ms": 40},
        ]
    )

    levels = project_track_logical_delta_levels(
        delta,
        track_group_keys={
            2: {2: 1},
            3: {2: 1, 3: 1},
        },
    )

    assert levels[1][["track_id", "play_events", "total_ms"]].to_dict("records") == [
        {"track_id": 1, "play_events": 1, "total_ms": 10},
        {"track_id": 2, "play_events": 2, "total_ms": 20},
        {"track_id": 3, "play_events": 3, "total_ms": 30},
        {"track_id": 4, "play_events": 4, "total_ms": 40},
    ]
    assert levels[2].to_dict("records") == [
        {"track_id": 1, "source_album_id": 11, "play_events": 3, "total_ms": 30},
        {"track_id": 3, "source_album_id": 12, "play_events": 3, "total_ms": 30},
        {"track_id": 4, "source_album_id": None, "play_events": 4, "total_ms": 40},
    ]
    assert levels[3].to_dict("records") == [
        {"track_id": 1, "source_album_id": 11, "play_events": 3, "total_ms": 30},
        {"track_id": 1, "source_album_id": 12, "play_events": 3, "total_ms": 30},
        {"track_id": 4, "source_album_id": None, "play_events": 4, "total_ms": 40},
    ]


def test_track_delta_projection_rejects_missing_or_conflicting_group_proof() -> None:
    delta = pd.DataFrame(
        [{"track_id": 2, "source_album_id": 11, "play_events": 1, "total_ms": 30_000}]
    )
    with pytest.raises(ValueError, match="required"):
        project_track_logical_delta(delta, merge_level=2)
    with pytest.raises(ValueError, match="conflicting"):
        project_track_logical_delta(
            delta,
            merge_level=3,
            track_group_keys=pd.DataFrame({"track_id": [2, 2], "track_agg_id": [1, 3]}),
        )

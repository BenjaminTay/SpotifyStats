from __future__ import annotations

import json
import sqlite3

import pandas as pd

from backend.core.migrations import migrate_042, migrate_046
from backend.domains.billboard.year_end import build_year_end_response
from backend.domains.music_search.context import MusicSearchFilterContext
from backend.domains.music_search.year_end_projection import (
    build_year_end_projection_rows,
    clear_year_end_projection,
    fail_pending_year_end_projection_set,
    load_entity_year_end,
    mark_year_end_projection_set_pending,
    publish_year_end_projection,
    year_end_projection_set_status,
)


def _payload(**values: object) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _ledger_rows() -> list[tuple[str, str, str, int, int, int, str]]:
    return [
        (
            "track",
            "2025-01-03",
            "track:1",
            1,
            10,
            10_000,
            _payload(entity_id=1, track_name="Track A", artist_name="Artist A"),
        ),
        (
            "track",
            "2025-01-03",
            "track:2",
            2,
            8,
            8_000,
            _payload(entity_id=2, track_name="Track B", artist_name="Artist B"),
        ),
        (
            "track",
            "2025-01-10",
            "track:2",
            1,
            12,
            12_000,
            _payload(entity_id=2, track_name="Track B", artist_name="Artist B"),
        ),
        (
            "track",
            "2025-01-10",
            "track:1",
            2,
            9,
            9_000,
            _payload(entity_id=1, track_name="Track A", artist_name="Artist A"),
        ),
        (
            "album",
            "2025-01-03",
            "album_project:10",
            1,
            10,
            10_000,
            _payload(entity_id=10, album_name="Album A", artist_name="Artist A"),
        ),
        (
            "artist",
            "2025-01-03",
            "artist:20",
            1,
            10,
            10_000,
            _payload(entity_id=20, artist_name="Artist A"),
        ),
        (
            "track",
            "2024-12-27",
            "track:1",
            1,
            20,
            20_000,
            _payload(entity_id=1, track_name="Track A", artist_name="Artist A"),
        ),
    ]


def _candidate_keys() -> set[str]:
    return {"track:1", "track:2", "album_project:10", "artist:20"}


def _context() -> MusicSearchFilterContext:
    return MusicSearchFilterContext(
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        merge_level=2,
        include_compilations=False,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        year_start=None,
        year_end=None,
        playback_revision=1,
        billboard_aggregation_revision=1,
        metadata_revision=1,
        settings_revision=1,
        artist_identity_revision=0,
        track_credit_revision=0,
        semantic_base_key="base",
        filter_fingerprint="fingerprint",
        source_revision="source",
    )


def test_projection_uses_shared_year_end_semantics_and_keeps_years_separate() -> None:
    meta_rows, entity_rows = build_year_end_projection_rows(
        _ledger_rows(),
        _candidate_keys(),
        track_top_n=50,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
    )

    assert [row[0] for row in meta_rows] == [2024, 2025]
    assert meta_rows[1][1] == "year_to_date"
    track_2025 = [row for row in entity_rows if row[0] == "track" and row[2] == 2025]
    assert [(row[1], row[3]) for row in track_2025] == [("track:2", 1), ("track:1", 2)]

    public_weekly = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp(week),
                "track_id": int(entity_key.split(":")[1]),
                "track_name": json.loads(payload)["track_name"],
                "artist_name": json.loads(payload)["artist_name"],
                "artist_names": [json.loads(payload)["artist_name"]],
                "album_name": None,
                "play_count": plays,
                "total_ms": total_ms,
                "rank": rank,
                "cover_url": None,
            }
            for family, week, entity_key, rank, plays, total_ms, payload in _ledger_rows()
            if family == "track"
        ]
    )
    public_album = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp(week),
                "album_name": json.loads(payload)["album_name"],
                "artist_name": json.loads(payload)["artist_name"],
                "play_count": plays,
                "total_ms": total_ms,
                "rank": rank,
                "cover_url": None,
            }
            for family, week, _entity_key, rank, plays, total_ms, payload in _ledger_rows()
            if family == "album"
        ]
    )
    public_artist = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp(week),
                "artist_name": json.loads(payload)["artist_name"],
                "play_count": plays,
                "total_ms": total_ms,
                "rank": rank,
                "cover_url": None,
            }
            for family, week, _entity_key, rank, plays, total_ms, payload in _ledger_rows()
            if family == "artist"
        ]
    )
    public = build_year_end_response(
        weekly=public_weekly,
        weekly_album=public_album,
        weekly_artist=public_artist,
        year=2025,
        top_n=50,
        album_top_n=30,
        artist_top_n=30,
        week_start_dow=4,
        week_start_hour=0,
    )
    projected_by_id = {int(row[1].split(":")[1]): row for row in track_2025}
    for row in public["tracks"]:
        projected = projected_by_id[row["track_id"]]
        assert projected[3:12] == (
            row["year_end_rank"],
            row["year_end_score"],
            row["peak_position"],
            row["weeks_on_chart"],
            row["weeks_at_peak"],
            row["weeks_at_no1"],
            row["weeks_top5"],
            row["weeks_top10"],
            row["chart_plays"],
        )
    for family, public_key, entity_key in (
        ("album", "albums", "album_project:10"),
        ("artist", "artists", "artist:20"),
    ):
        projected = next(
            row
            for row in entity_rows
            if row[0] == family and row[1] == entity_key and row[2] == 2025
        )
        public_row = public[public_key][0]
        assert projected[3:12] == tuple(
            public_row[key]
            for key in (
                "year_end_rank",
                "year_end_score",
                "peak_position",
                "weeks_on_chart",
                "weeks_at_peak",
                "weeks_at_no1",
                "weeks_top5",
                "weeks_top10",
                "chart_plays",
            )
        )


def _projection_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """CREATE TABLE music_search_snapshot_meta (
               snapshot_key TEXT PRIMARY KEY,
               filter_fingerprint TEXT NOT NULL UNIQUE,
               source_revision TEXT NOT NULL,
               status TEXT NOT NULL,
               created_at TEXT NOT NULL DEFAULT (datetime('now')),
               activated_at TEXT,
               last_accessed_at TEXT,
               last_error TEXT,
               semantic_base_key TEXT,
               merge_level INTEGER,
               dynamic_threshold INTEGER,
               builder_version TEXT
           )"""
    )
    conn.execute(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status
           ) VALUES ('snapshot', 'fingerprint', 'source', 'ready')"""
    )
    migrate_042(conn)
    migrate_046(conn)
    return conn


def test_projection_read_state_and_summary_do_not_trigger_computation() -> None:
    conn = _projection_connection()
    try:
        assert load_entity_year_end(
            conn,
            snapshot_key="snapshot",
            family="track",
            entity_key="track:2",
            include_history=True,
        ) == {"status": "unavailable", "summary": None, "history": []}

        conn.execute(
            """INSERT INTO music_search_weekly_chart_context(
                   snapshot_key, family, week, entity_key, rank,
                   play_count, total_ms, stable_sort_key
               ) VALUES ('snapshot', 'track', '2025-01-03', 'track:2', 1, 1, 1, ?)""",
            (_payload(entity_id=2, track_name="Track B", artist_name="Artist B"),),
        )
        assert (
            load_entity_year_end(
                conn,
                snapshot_key="snapshot",
                family="track",
                entity_key="track:2",
                include_history=False,
            )["status"]
            == "warming"
        )

        conn.execute(
            """INSERT INTO music_search_year_end_projection_state(
                   snapshot_key, builder_version, status
               ) VALUES ('snapshot', 'music_search_year_end_projection_v1', 'running')
               ON CONFLICT(snapshot_key) DO UPDATE SET status='running'"""
        )
        assert (
            load_entity_year_end(
                conn,
                snapshot_key="snapshot",
                family="track",
                entity_key="track:2",
                include_history=False,
            )["status"]
            == "warming"
        )

        meta_rows, entity_rows = build_year_end_projection_rows(
            _ledger_rows(),
            _candidate_keys(),
            track_top_n=50,
            album_top_n=30,
            artist_top_n=30,
            week_start_dow=4,
        )
        publish_year_end_projection(conn, "snapshot", meta_rows, entity_rows)
        result = load_entity_year_end(
            conn,
            snapshot_key="snapshot",
            family="track",
            entity_key="track:2",
            include_history=True,
        )

        assert result["status"] == "ready"
        assert result["summary"] == {
            "best_year": 2025,
            "best_rank": 1,
            "best_year_is_complete": False,
            "latest_year": 2025,
            "latest_rank": 1,
            "latest_year_is_complete": False,
            "ranked_years": 1,
        }
        assert result["history"][0]["coverage_status"] == "year_to_date"
        assert result["history"][0]["year_end_score"] > 0

        clear_year_end_projection(conn, "snapshot")
        assert (
            load_entity_year_end(
                conn,
                snapshot_key="snapshot",
                family="track",
                entity_key="track:2",
                include_history=True,
            )["status"]
            == "warming"
        )
    finally:
        conn.close()


def test_projection_set_status_and_pending_marker_accept_empty_ready_projection() -> None:
    conn = _projection_connection()
    try:
        conn.execute(
            """UPDATE music_search_snapshot_meta
               SET builder_version='music_search_snapshot_v3'
               WHERE snapshot_key='snapshot'"""
        )

        contexts = (_context(),)
        missing = year_end_projection_set_status(conn, contexts)
        assert missing["status"] == "incomplete"
        assert missing["variants"][0]["reason"] == "projection_missing"

        assert mark_year_end_projection_set_pending(conn, contexts) == 1
        warming = year_end_projection_set_status(conn, contexts)
        assert warming["status"] == "warming"
        assert (
            load_entity_year_end(
                conn,
                snapshot_key="snapshot",
                family="track",
                entity_key="track:2",
                include_history=False,
            )["status"]
            == "warming"
        )

        conn.execute(
            """UPDATE music_search_year_end_projection_state
               SET status='ready' WHERE snapshot_key='snapshot'"""
        )
        ready = year_end_projection_set_status(conn, contexts)
        assert ready["status"] == "ready"
        assert ready["ready_count"] == 1

        conn.execute(
            """UPDATE music_search_year_end_projection_state
               SET builder_version='old-version' WHERE snapshot_key='snapshot'"""
        )
        stale = year_end_projection_set_status(conn, contexts)
        assert stale["status"] == "incomplete"
        assert stale["variants"][0]["reason"] == "builder_version_mismatch"

        assert mark_year_end_projection_set_pending(conn, contexts) == 1
        assert (
            fail_pending_year_end_projection_set(
                conn,
                contexts,
                error_type="RuntimeError",
            )
            == 1
        )
        failed = conn.execute(
            """SELECT status, last_error
               FROM music_search_year_end_projection_state
               WHERE snapshot_key='snapshot'"""
        ).fetchone()
        assert tuple(failed) == ("failed", "RuntimeError")
        assert (
            load_entity_year_end(
                conn,
                snapshot_key="snapshot",
                family="track",
                entity_key="track:2",
                include_history=False,
            )["status"]
            == "unavailable"
        )
    finally:
        conn.close()

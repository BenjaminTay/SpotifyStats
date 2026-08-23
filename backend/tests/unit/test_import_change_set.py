from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest

from backend.core.db import _publish_aggregation_shadows, check_agg_valid
from backend.core.migrations import migrate_037, migrate_038, migrate_039, migrate_040
from backend.domains.imports.change_set import (
    build_playback_change_set,
    publish_year_partition_state,
)
from backend.domains.imports.incremental import FingerprintRecord, build_import_plan

pytestmark = pytest.mark.unit


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY, ts TEXT, ts_date TEXT,
            ts_year INTEGER, ts_month INTEGER, track_id INTEGER,
            source_album_id INTEGER, ms_played INTEGER DEFAULT 0,
            content_type TEXT DEFAULT 'audio',
            spotify_track_id_at_play TEXT,
            spotify_album_id_at_play TEXT
        );
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY, album_id INTEGER, artist_id INTEGER,
            spotify_track_id TEXT
        );
        CREATE TABLE track_artists(track_id INTEGER, artist_id INTEGER, role TEXT);
        """
    )
    migrate_037(conn)
    migrate_038(conn)
    migrate_039(conn)
    migrate_040(conn)
    return conn


def _record(char: str, timestamp: str) -> FingerprintRecord:
    return FingerprintRecord(
        "audio",
        char * 64,
        datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
    )


def test_append_change_set_uses_only_generation_rows_and_credit_closure() -> None:
    conn = _connection()
    try:
        existing = [_record("a", "2025-12-31T23:00:00Z")]
        plan = build_import_plan(
            [*existing, _record("b", "2026-01-02T01:00:00Z")],
            existing_records=existing,
        )
        conn.executemany(
            """INSERT INTO tracks(
                   track_id, album_id, artist_id, spotify_track_id
               ) VALUES (?, ?, ?, ?)""",
            [(1, 11, 21, "canonical-old"), (2, 12, 22, "canonical-new")],
        )
        conn.executemany(
            "INSERT INTO track_artists VALUES (?, ?, ?)",
            [(2, 22, "primary"), (2, 23, "featured")],
        )
        conn.executemany(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, track_id,
                   source_album_id, spotify_track_id_at_play,
                   spotify_album_id_at_play, content_type, source_fingerprint,
                   source_fingerprint_version, import_generation_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'audio', ?, 1, ?)""",
            [
                (
                    1,
                    "2025-12-31T23:00:00Z",
                    "2026-01-01",
                    2026,
                    1,
                    1,
                    11,
                    "play-old",
                    "album-old",
                    "a" * 64,
                    "old",
                ),
                (
                    2,
                    "2026-01-02T01:00:00Z",
                    "2026-01-02",
                    2026,
                    1,
                    2,
                    13,
                    "play-new",
                    "album-new",
                    "b" * 64,
                    "new",
                ),
            ],
        )

        change_set = build_playback_change_set(
            conn, generation_id="new", strategy="incremental", plan=plan
        )

        assert change_set.track_ids == {2}
        assert change_set.album_ids == {12, 13}
        assert change_set.source_album_ids == {13}
        assert change_set.artist_ids == {22, 23}
        assert change_set.spotify_track_ids == {"canonical-new", "play-new"}
        assert change_set.spotify_album_ids == {"album-new"}
        assert change_set.years == {2026}
        assert change_set.dates == {"2026-01-02"}
        assert change_set.added_count == 1
    finally:
        conn.close()


def test_change_set_fails_closed_when_generation_count_does_not_match_plan() -> None:
    conn = _connection()
    try:
        plan = build_import_plan([_record("a", "2026-01-01T00:00:00Z")], existing_records=[])
        with pytest.raises(RuntimeError, match="generation scope mismatch"):
            build_playback_change_set(
                conn, generation_id="missing", strategy="incremental", plan=plan
            )
    finally:
        conn.close()


def test_aggregate_gate_rejects_previous_playback_generation() -> None:
    conn = _connection()
    try:
        conn.execute("CREATE TABLE agg_config(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO agg_config VALUES ('param_hash', 'params')")
        conn.execute("UPDATE playback_import_state SET active_generation_id='new' WHERE state_id=1")

        assert check_agg_valid(conn, "params") is False

        conn.execute("INSERT INTO agg_config VALUES ('data_generation_id', 'new')")
        assert check_agg_valid(conn, "params") is True
    finally:
        conn.close()


def test_aggregate_publish_rejects_generation_drift_without_replacing_live_rows() -> None:
    conn = _connection()
    try:
        for table in (
            "agg_weekly_tracks",
            "agg_weekly_albums",
            "agg_weekly_track_sources",
            "agg_weekly_artists",
        ):
            conn.execute(f"CREATE TABLE {table}(marker TEXT)")
            conn.execute(f"INSERT INTO {table} VALUES ('live')")
            conn.execute(f"CREATE TEMP TABLE {table}_shadow(marker TEXT)")
            conn.execute(f"INSERT INTO {table}_shadow VALUES ('shadow')")
        conn.execute("CREATE TABLE agg_config(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO agg_config VALUES ('param_hash', 'old')")
        conn.execute("UPDATE playback_import_state SET active_generation_id='new' WHERE state_id=1")
        conn.commit()

        with pytest.raises(RuntimeError, match="generation changed"):
            _publish_aggregation_shadows(
                conn,
                param_hash="next",
                data_generation_id="old",
            )

        for table in (
            "agg_weekly_tracks",
            "agg_weekly_albums",
            "agg_weekly_track_sources",
            "agg_weekly_artists",
        ):
            assert conn.execute(f"SELECT marker FROM {table}").fetchone()[0] == "live"
        assert (
            conn.execute("SELECT value FROM agg_config WHERE key='param_hash'").fetchone()[0]
            == "old"
        )
    finally:
        conn.close()


def test_year_prefix_digest_keeps_older_year_stable_after_latest_append() -> None:
    conn = _connection()
    try:
        baseline = [
            _record("a", "2025-01-01T00:00:00Z"),
            _record("b", "2026-01-01T00:00:00Z"),
        ]
        conn.executemany(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, content_type,
                   source_fingerprint, source_fingerprint_version, import_generation_id
               ) VALUES (?, ?, ?, ?, 1, 'audio', ?, 1, 'base')""",
            [
                (1, "2025-01-01T00:00:00Z", "2025-01-01", 2025, "a" * 64),
                (2, "2026-01-01T00:00:00Z", "2026-01-01", 2026, "b" * 64),
            ],
        )
        baseline_change = build_playback_change_set(
            conn,
            generation_id="base",
            strategy="full",
            plan=build_import_plan(baseline, existing_records=[]),
        )
        publish_year_partition_state(conn, baseline_change)
        before = {
            int(row[0]): str(row[1])
            for row in conn.execute(
                "SELECT report_year, prefix_digest FROM playback_year_partition_state"
            )
        }

        append_plan = build_import_plan(
            [*baseline, _record("c", "2026-02-01T00:00:00Z")],
            existing_records=baseline,
        )
        conn.execute(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, content_type,
                   source_fingerprint, source_fingerprint_version, import_generation_id
               ) VALUES (3, '2026-02-01T00:00:00Z', '2026-02-01', 2026, 2,
                         'audio', ?, 1, 'append')""",
            ("c" * 64,),
        )
        append_change = build_playback_change_set(
            conn, generation_id="append", strategy="incremental", plan=append_plan
        )
        publish_year_partition_state(conn, append_change)
        after = {
            int(row[0]): str(row[1])
            for row in conn.execute(
                "SELECT report_year, prefix_digest FROM playback_year_partition_state"
            )
        }

        assert after[2025] == before[2025]
        assert after[2026] != before[2026]
    finally:
        conn.close()


def test_first_incremental_partition_publish_bootstraps_missing_older_years() -> None:
    conn = _connection()
    try:
        existing = [
            _record("a", "2024-06-01T00:00:00Z"),
            _record("b", "2025-06-01T00:00:00Z"),
        ]
        incoming = [*existing, _record("c", "2026-06-01T00:00:00Z")]
        conn.executemany(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, content_type,
                   source_fingerprint, source_fingerprint_version, import_generation_id
               ) VALUES (?, ?, ?, ?, 6, 'audio', ?, 1, ?)""",
            [
                (1, "2024-06-01T00:00:00Z", "2024-06-01", 2024, "a" * 64, "base"),
                (2, "2025-06-01T00:00:00Z", "2025-06-01", 2025, "b" * 64, "base"),
                (3, "2026-06-01T00:00:00Z", "2026-06-01", 2026, "c" * 64, "append"),
            ],
        )
        change_set = build_playback_change_set(
            conn,
            generation_id="append",
            strategy="incremental",
            plan=build_import_plan(incoming, existing_records=existing),
        )

        publish_year_partition_state(conn, change_set)

        assert [
            int(row[0])
            for row in conn.execute(
                "SELECT report_year FROM playback_year_partition_state ORDER BY report_year"
            )
        ] == [2024, 2025, 2026]
    finally:
        conn.close()


def test_append_change_set_includes_previous_year_for_cross_year_merge_chain() -> None:
    conn = _connection()
    try:
        existing = [_record("a", "2025-12-31T15:59:50Z")]
        incoming = [*existing, _record("b", "2025-12-31T16:00:20Z")]
        conn.execute("INSERT INTO tracks(track_id, album_id, artist_id) VALUES (1, 1, 1)")
        conn.executemany(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, track_id,
                   source_album_id, ms_played, content_type, source_fingerprint,
                   source_fingerprint_version, import_generation_id
               ) VALUES (?, ?, ?, ?, 1, 1, 1, ?, 'audio', ?, 1, ?)""",
            [
                (
                    1,
                    "2025-12-31T15:59:50Z",
                    "2025-12-31",
                    2025,
                    30_000,
                    "a" * 64,
                    "base",
                ),
                (
                    2,
                    "2025-12-31T16:00:20Z",
                    "2026-01-01",
                    2026,
                    30_000,
                    "b" * 64,
                    "append",
                ),
            ],
        )

        change_set = build_playback_change_set(
            conn,
            generation_id="append",
            strategy="incremental",
            plan=build_import_plan(incoming, existing_records=existing),
        )

        assert change_set.years == {2025, 2026}
        assert change_set.billboard_scope_exact is False
    finally:
        conn.close()

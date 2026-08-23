from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd
import pytest

from backend.core.db import (
    _aggregation_fact_dependencies,
    _partition_base_generation,
    _played_track_credit_membership_revision,
    _publish_aggregation_shadows,
    check_agg_valid,
)
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
            ts_year INTEGER, ts_month INTEGER, ts_dow INTEGER, ts_hour INTEGER,
            track_id INTEGER,
            source_album_id INTEGER, ms_played INTEGER DEFAULT 0,
            content_type TEXT DEFAULT 'audio',
            spotify_track_id_at_play TEXT,
            spotify_album_id_at_play TEXT
        );
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY, album_id INTEGER, artist_id INTEGER,
            spotify_track_id TEXT
        );
        CREATE TABLE artists(
            artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL
        );
        CREATE TABLE track_artists(track_id INTEGER, artist_id INTEGER, role TEXT);
        CREATE TABLE spotify_track_meta(
            spotify_track_id TEXT PRIMARY KEY, duration_ms INTEGER,
            spotify_album_id TEXT
        );
        CREATE INDEX idx_test_plays_ts ON plays(ts, play_id);
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
        assert check_agg_valid(conn, "params") is False

        conn.execute(
            "UPDATE playback_import_state SET dataset_digest='dataset-current' WHERE state_id=1"
        )
        dependencies = _aggregation_fact_dependencies(conn)
        conn.executemany(
            "INSERT INTO agg_config(key, value) VALUES (?, ?)",
            [
                ("source_dataset_digest", "dataset-current"),
                *dependencies.items(),
            ],
        )
        assert check_agg_valid(conn, "params") is True
    finally:
        conn.close()


def test_aggregate_gate_accepts_legacy_config_only_while_playback_is_unbound() -> None:
    conn = _connection()
    try:
        conn.execute("CREATE TABLE agg_config(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO agg_config VALUES ('param_hash', 'legacy-params')")

        assert check_agg_valid(conn, "legacy-params") is True

        conn.execute(
            """UPDATE playback_import_state
               SET active_generation_id='generation', dataset_digest='dataset-v1'
               WHERE state_id=1"""
        )
        assert check_agg_valid(conn, "legacy-params") is False
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


def test_partition_base_rejects_duration_semantic_drift() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE agg_config(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        dependencies = {
            "builder_version": "builder-v1",
            "playback_policy_version": "policy-v1",
            "identity_revision": "1",
            "track_credit_revision": "2",
            "album_project_revision": "album-v1",
            "duration_revision": "duration-old",
        }
        conn.executemany(
            "INSERT INTO agg_config(key, value) VALUES (?, ?)",
            [
                ("param_hash", "params"),
                ("source_dataset_digest", "dataset-old"),
                ("data_generation_id", "generation-old"),
                *dependencies.items(),
            ],
        )

        assert (
            _partition_base_generation(
                conn,
                param_hash="params",
                previous_dataset_digest="dataset-old",
                semantic_dependencies=dependencies,
            )
            == "generation-old"
        )
        album_project_changed = {
            key: value for key, value in dependencies.items() if key != "album_project_revision"
        }
        assert (
            _partition_base_generation(
                conn,
                param_hash="params",
                previous_dataset_digest="dataset-old",
                semantic_dependencies=album_project_changed,
            )
            == "generation-old"
        )
        changed = {**dependencies, "duration_revision": "duration-new"}
        assert (
            _partition_base_generation(
                conn,
                param_hash="params",
                previous_dataset_digest="dataset-old",
                semantic_dependencies=changed,
            )
            is None
        )
    finally:
        conn.close()


def test_tail_billboard_events_honor_static_and_dynamic_threshold_modes() -> None:
    from backend.domains.imports.change_set import _logical_billboard_events

    rows = [
        {
            "play_id": 1,
            "ts": "2026-01-01T00:00:40Z",
            "ts_date": "2026-01-01",
            "ts_dow": 3,
            "ts_hour": 8,
            "ms_played": 40_000,
            "track_id": 1,
            "source_album_id": 1,
            "album_id": 1,
            "artist_id": 1,
            "duration_ms": 600_000,
        }
    ]

    static = _logical_billboard_events(
        rows,
        min_ms=30_000,
        dynamic_threshold=False,
        max_gap_minutes=5,
    )
    dynamic = _logical_billboard_events(
        rows,
        min_ms=30_000,
        dynamic_threshold=True,
        max_gap_minutes=5,
    )

    assert len(static) == 1
    assert dynamic.empty


def test_played_credit_digest_excludes_new_only_tracks_but_detects_existing_track_credit() -> None:
    conn = _connection()
    try:
        conn.executemany(
            "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
            [(1, "Artist One"), (2, "Artist Two")],
        )
        conn.executemany(
            "INSERT INTO tracks(track_id, album_id, artist_id, spotify_track_id) "
            "VALUES (?, 1, ?, ?)",
            [(1, 1, "track-1"), (2, 2, "track-2")],
        )
        conn.execute("INSERT INTO track_artists VALUES (1, 1, 'primary')")
        conn.execute(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, track_id,
                   source_album_id, ms_played, import_generation_id
               ) VALUES (1, '2026-01-01T00:01:00Z', '2026-01-01', 2026, 1,
                         1, 1, 60000, 'base')"""
        )
        baseline = _played_track_credit_membership_revision(conn)
        conn.execute("CREATE TABLE agg_config(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.executemany(
            "INSERT INTO agg_config(key, value) VALUES (?, ?)",
            [
                ("param_hash", "params"),
                ("source_dataset_digest", "dataset-old"),
                ("data_generation_id", "generation-old"),
                ("credit_membership_revision", baseline),
            ],
        )

        conn.execute("INSERT INTO track_artists VALUES (2, 2, 'primary')")
        conn.execute(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, track_id,
                   source_album_id, ms_played, import_generation_id
               ) VALUES (2, '2026-01-01T00:02:00Z', '2026-01-01', 2026, 1,
                         2, 1, 60000, 'append')"""
        )

        assert _played_track_credit_membership_revision(conn) != baseline
        assert (
            _played_track_credit_membership_revision(
                conn,
                excluded_generation_id="append",
            )
            == baseline
        )
        assert (
            _partition_base_generation(
                conn,
                param_hash="params",
                previous_dataset_digest="dataset-old",
                semantic_dependencies={
                    "credit_membership_revision": _played_track_credit_membership_revision(
                        conn,
                        excluded_generation_id="append",
                    )
                },
            )
            == "generation-old"
        )

        conn.execute("INSERT INTO track_artists VALUES (1, 2, 'featured')")
        changed_base_digest = _played_track_credit_membership_revision(
            conn,
            excluded_generation_id="append",
        )
        assert changed_base_digest != baseline
        assert (
            _partition_base_generation(
                conn,
                param_hash="params",
                previous_dataset_digest="dataset-old",
                semantic_dependencies={
                    "credit_membership_revision": changed_base_digest,
                },
            )
            is None
        )
    finally:
        conn.close()


def test_aggregate_read_gate_consumes_source_duration_and_credit_dependencies() -> None:
    conn = _connection()
    try:
        conn.executemany(
            "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
            [(1, "Artist One"), (2, "Artist Two")],
        )
        conn.execute(
            "INSERT INTO tracks(track_id, album_id, artist_id, spotify_track_id) "
            "VALUES (1, 1, 1, 'track-1')"
        )
        conn.execute("INSERT INTO track_artists VALUES (1, 1, 'primary')")
        conn.execute(
            "INSERT INTO spotify_track_meta(spotify_track_id, duration_ms) "
            "VALUES ('track-1', 180000)"
        )
        conn.execute(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, track_id,
                   source_album_id, ms_played, import_generation_id
               ) VALUES (1, '2026-01-01T00:01:00Z', '2026-01-01', 2026, 1,
                         1, 1, 60000, 'generation')"""
        )
        conn.execute(
            """UPDATE playback_import_state
               SET active_generation_id='generation', dataset_digest='dataset-v1'
               WHERE state_id=1"""
        )
        conn.execute("CREATE TABLE agg_config(key TEXT PRIMARY KEY, value TEXT NOT NULL)")

        def publish_valid_config() -> None:
            conn.execute("DELETE FROM agg_config")
            conn.executemany(
                "INSERT INTO agg_config(key, value) VALUES (?, ?)",
                [
                    ("param_hash", "params"),
                    ("data_generation_id", "generation"),
                    ("source_dataset_digest", "dataset-v1"),
                    *_aggregation_fact_dependencies(conn).items(),
                ],
            )

        publish_valid_config()
        assert check_agg_valid(conn, "params") is True

        conn.execute(
            "UPDATE spotify_track_meta SET duration_ms=240000 WHERE spotify_track_id='track-1'"
        )
        assert check_agg_valid(conn, "params") is False

        publish_valid_config()
        conn.execute("INSERT INTO track_artists VALUES (1, 2, 'featured')")
        assert check_agg_valid(conn, "params") is False

        publish_valid_config()
        conn.execute(
            "UPDATE playback_import_state SET dataset_digest='dataset-v2' WHERE state_id=1"
        )
        assert check_agg_valid(conn, "params") is False
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
        assert change_set.billboard_scope_exact is True
        assert change_set.billboard_weeks == {"2025-12-26"}
    finally:
        conn.close()


def test_billboard_scope_walks_entire_long_preceding_merge_chain() -> None:
    from backend.domains.imports.change_set import build_billboard_tail_contribution_frames

    conn = _connection()
    try:
        conn.execute(
            "INSERT INTO tracks(track_id, album_id, artist_id, spotify_track_id) "
            "VALUES (1, 1, 1, 'track-1')"
        )
        conn.execute(
            "INSERT INTO spotify_track_meta(spotify_track_id, duration_ms) "
            "VALUES ('track-1', 60000)"
        )
        base = pd.Timestamp("2026-01-01T00:00:00Z")
        old_rows = []
        for index in range(300):
            timestamp = base + pd.Timedelta(seconds=index + 1)
            old_rows.append(
                (
                    index + 1,
                    timestamp.isoformat().replace("+00:00", "Z"),
                    "2026-01-01",
                    2026,
                    1,
                    3,
                    8,
                    1,
                    1,
                    1000,
                    f"{index:064x}",
                    "base",
                )
            )
        conn.executemany(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, ts_dow, ts_hour,
                   track_id, source_album_id, ms_played, content_type,
                   source_fingerprint, source_fingerprint_version,
                   import_generation_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'audio', ?, 1, ?)""",
            old_rows,
        )
        new_ts = base + pd.Timedelta(seconds=330)
        conn.execute(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, ts_dow, ts_hour,
                   track_id, source_album_id, ms_played, content_type,
                   source_fingerprint, source_fingerprint_version,
                   import_generation_id
               ) VALUES (301, ?, '2026-01-01', 2026, 1, 3, 8,
                         1, 1, 30000, 'audio', ?, 1, 'append')""",
            (new_ts.isoformat().replace("+00:00", "Z"), "b" * 64),
        )

        old_events, new_events = build_billboard_tail_contribution_frames(
            conn,
            generation_id="append",
            min_ms=30000,
            music_only=True,
            dynamic_threshold=True,
            max_gap_minutes=5,
        )

        assert int(old_events["ms_played"].sum()) == 300_000
        assert int(new_events["ms_played"].sum()) == 330_000
    finally:
        conn.close()


def test_billboard_scope_includes_duration_slices_on_both_sides_of_week_boundary() -> None:
    conn = _connection()
    try:
        existing = [_record("a", "2026-01-01T14:00:00Z")]
        incoming = [*existing, _record("b", "2026-01-01T16:30:00Z")]
        conn.executemany(
            "INSERT INTO tracks(track_id, album_id, artist_id, spotify_track_id) "
            "VALUES (?, ?, ?, ?)",
            [(1, 1, 1, "track-1"), (2, 2, 2, "track-2")],
        )
        conn.executemany(
            "INSERT INTO spotify_track_meta(spotify_track_id, duration_ms) VALUES (?, ?)",
            [("track-1", 180000), ("track-2", 10_800_000)],
        )
        conn.executemany(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, ts_dow, ts_hour,
                   track_id, source_album_id, ms_played, content_type,
                   source_fingerprint, source_fingerprint_version,
                   import_generation_id
               ) VALUES (?, ?, ?, 2026, 1, 3, ?, ?, ?, ?, 'audio', ?, 1, ?)""",
            [
                (1, "2026-01-01T14:00:00Z", "2026-01-01", 22, 1, 1, 60000, "a" * 64, "base"),
                (
                    2,
                    "2026-01-01T16:30:00Z",
                    "2026-01-02",
                    0,
                    2,
                    2,
                    7_200_000,
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

        assert change_set.billboard_scope_exact is True
        assert {"2025-12-26", "2026-01-02"}.issubset(change_set.billboard_weeks)
    finally:
        conn.close()


def test_billboard_preceding_chain_stops_at_different_track() -> None:
    from backend.domains.imports.change_set import build_billboard_tail_contribution_frames

    conn = _connection()
    try:
        conn.executemany(
            "INSERT INTO tracks(track_id, album_id, artist_id, spotify_track_id) "
            "VALUES (?, ?, ?, ?)",
            [(1, 1, 1, "track-1"), (2, 2, 2, "track-2")],
        )
        conn.executemany(
            "INSERT INTO spotify_track_meta(spotify_track_id, duration_ms) VALUES (?, 60000)",
            [("track-1",), ("track-2",)],
        )
        conn.executemany(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, ts_dow, ts_hour,
                   track_id, source_album_id, ms_played, content_type,
                   source_fingerprint, source_fingerprint_version,
                   import_generation_id
               ) VALUES (?, ?, '2026-01-01', 2026, 1, 3, 8,
                         ?, ?, 30000, 'audio', ?, 1, ?)""",
            [
                (1, "2026-01-01T00:00:00Z", 1, 1, "a" * 64, "base"),
                (2, "2026-01-01T00:00:30Z", 2, 2, "b" * 64, "base"),
                (3, "2026-01-01T00:01:00Z", 1, 1, "c" * 64, "append"),
            ],
        )

        old_events, new_events = build_billboard_tail_contribution_frames(
            conn,
            generation_id="append",
            min_ms=30000,
            music_only=True,
            dynamic_threshold=True,
            max_gap_minutes=5,
        )

        assert old_events.empty
        assert set(new_events["track_id"]) == {1}
        assert int(new_events["ms_played"].sum()) == 30000
    finally:
        conn.close()


def test_billboard_scope_queries_generation_and_bounded_preceding_pages_only() -> None:
    from backend.domains.imports.change_set import build_billboard_tail_contribution_frames

    conn = _connection()
    try:
        conn.execute(
            "INSERT INTO tracks(track_id, album_id, artist_id, spotify_track_id) "
            "VALUES (1, 1, 1, 'track-1')"
        )
        conn.execute(
            "INSERT INTO spotify_track_meta(spotify_track_id, duration_ms) "
            "VALUES ('track-1', 60000)"
        )
        conn.executemany(
            """INSERT INTO plays(
                   play_id, ts, ts_date, ts_year, ts_month, ts_dow, ts_hour,
                   track_id, source_album_id, ms_played, content_type,
                   source_fingerprint, source_fingerprint_version,
                   import_generation_id
               ) VALUES (?, ?, '2026-01-01', 2026, 1, 3, 8,
                         1, 1, 30000, 'audio', ?, 1, ?)""",
            [
                (1, "2026-01-01T00:00:00Z", "a" * 64, "base"),
                (2, "2026-01-01T00:00:30Z", "b" * 64, "append"),
            ],
        )
        statements: list[str] = []
        conn.set_trace_callback(statements.append)

        build_billboard_tail_contribution_frames(
            conn,
            generation_id="append",
            min_ms=30000,
            music_only=True,
            dynamic_threshold=True,
            max_gap_minutes=5,
        )
        conn.set_trace_callback(None)

        source_queries = [sql for sql in statements if "FROM plays p" in sql and "SELECT" in sql]
        assert source_queries
        assert all("WHERE" in sql for sql in source_queries)
        preceding = [sql for sql in source_queries if "ORDER BY p.ts DESC" in sql]
        assert preceding and all("LIMIT" in sql for sql in preceding)
    finally:
        conn.close()

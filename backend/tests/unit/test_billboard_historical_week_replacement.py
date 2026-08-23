from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_WEEKS = (
    "2026-01-02",
    "2026-01-09",
    "2026-01-16",
    "2026-01-23",
    "2026-01-30",
    "2026-02-06",
    "2026-02-13",
    "2026-02-20",
)
_TABLES = (
    "agg_weekly_tracks",
    "agg_weekly_albums",
    "agg_weekly_track_sources",
    "agg_weekly_artists",
)


def _insert_play(
    conn: sqlite3.Connection,
    *,
    play_id: int,
    timestamp: str,
    track_id: int,
    album_id: int,
    ms_played: int,
    fingerprint: str,
    generation_id: str,
) -> None:
    conn.execute(
        """INSERT INTO plays(
               play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
               ts_date, platform, ms_played, conn_country, track_id,
               content_type, source_album_id, source_fingerprint,
               source_fingerprint_version, import_generation_id
           ) VALUES (?, ?, 2026, 1, 1, 5, 12, substr(?, 1, 10), 'test', ?,
                     'CN', ?, 'audio', ?, ?, 1, ?)""",
        (
            play_id,
            timestamp,
            timestamp,
            ms_played,
            track_id,
            album_id,
            fingerprint,
            generation_id,
        ),
    )


def _publish_state(conn: sqlite3.Connection, generation_id: str) -> tuple[str, str]:
    from backend.domains.imports.state import publish_playback_import_state

    summary = publish_playback_import_state(
        conn,
        generation_id=generation_id,
        account_identity_hash="test-account",
        relation="reconciled_snapshot",
        strategy="full",
    )
    conn.commit()
    return generation_id, summary.dataset_digest


def _seed_database(path: Path, monkeypatch, *, include_boundary_chain: bool = False) -> None:
    from backend.core import db as db_module
    from backend.core.migrations import run_migrations

    monkeypatch.setattr(db_module, "DB_PATH", str(path))
    db_module.init_db()
    run_migrations()
    conn = sqlite3.connect(path)
    conn.executemany(
        "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
        [(1, "Artist One"), (2, "Artist Two")],
    )
    conn.executemany(
        "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)",
        [(1, "Album One", 1), (2, "Album Two", 2)],
    )
    conn.executemany(
        """INSERT INTO tracks(
               track_id, track_name, artist_id, album_id, spotify_track_id
           ) VALUES (?, ?, ?, ?, ?)""",
        [(1, "Track One", 1, 1, "spotify-one"), (2, "Track Two", 2, 2, "spotify-two")],
    )
    conn.executemany(
        "INSERT INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'primary')",
        [(1, 1), (2, 2)],
    )
    conn.executemany(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, duration_ms
           ) VALUES (?, ?, 180000)""",
        [("spotify-one", "Track One"), ("spotify-two", "Track Two")],
    )
    for index, week in enumerate(_WEEKS, start=1):
        timestamp = f"{week}T04:00:00Z"
        _insert_play(
            conn,
            play_id=index,
            timestamp=timestamp,
            track_id=1 if index % 2 else 2,
            album_id=1 if index % 2 else 2,
            ms_played=60_000,
            fingerprint=f"weekly-{index}",
            generation_id="base-generation",
        )
    if include_boundary_chain:
        for play_id, timestamp, played_ms in (
            (101, "2026-01-22T15:59:30Z", 20_000),
            (102, "2026-01-22T16:00:10Z", 30_000),
            (103, "2026-01-22T16:00:40Z", 20_000),
        ):
            _insert_play(
                conn,
                play_id=play_id,
                timestamp=timestamp,
                track_id=1,
                album_id=1,
                ms_played=played_ms,
                fingerprint=f"chain-{play_id}",
                generation_id="base-generation",
            )
    _publish_state(conn, "base-generation")
    conn.close()
    report = db_module.build_aggregations(
        min_ms=30_000,
        music_only=True,
        week_start_dow=4,
        week_start_hour=0,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
        expected_generation_id="base-generation",
    )
    assert report["build_strategy"] == "full"


def _online_backup(source: Path, destination: Path) -> None:
    source_conn = sqlite3.connect(source)
    target_conn = sqlite3.connect(destination)
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()


def _table_rows(path: Path, table: str, where: str = "") -> list[tuple]:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(f'SELECT * FROM "{table}" {where} ORDER BY 1, 2, 3').fetchall()
    finally:
        conn.close()


def _replace_weekly_fact(path: Path) -> tuple[str, str, str]:
    conn = sqlite3.connect(path)
    previous_digest = str(
        conn.execute(
            "SELECT dataset_digest FROM playback_import_state WHERE state_id=1"
        ).fetchone()[0]
    )
    conn.execute("DELETE FROM plays WHERE play_id=3")
    _insert_play(
        conn,
        play_id=303,
        timestamp="2026-01-16T04:00:00Z",
        track_id=2,
        album_id=2,
        ms_played=90_000,
        fingerprint="weekly-corrected",
        generation_id="corrected-generation",
    )
    result = _publish_state(conn, "corrected-generation")
    conn.close()
    return (*result, previous_digest)


def _assert_aggregate_equivalence(left: Path, right: Path) -> None:
    conn = sqlite3.connect(left)
    try:
        conn.execute("ATTACH DATABASE ? AS reference", (str(right),))
        for table in _TABLES:
            left_only = conn.execute(
                f'SELECT * FROM main."{table}" EXCEPT SELECT * FROM reference."{table}"'
            ).fetchall()
            right_only = conn.execute(
                f'SELECT * FROM reference."{table}" EXCEPT SELECT * FROM main."{table}"'
            ).fetchall()
            assert left_only == [], table
            assert right_only == [], table
    finally:
        conn.close()


def test_historical_one_delete_one_insert_matches_full_and_preserves_other_weeks(
    tmp_path, monkeypatch
) -> None:
    from backend.core import db as db_module

    partition_path = tmp_path / "partition.db"
    full_path = tmp_path / "full.db"
    _seed_database(partition_path, monkeypatch)
    unaffected_before = {
        table: _table_rows(
            partition_path,
            table,
            "WHERE billboard_week != '2026-01-16'",
        )
        for table in _TABLES
    }
    generation_id, digest, previous_digest = _replace_weekly_fact(partition_path)
    _online_backup(partition_path, full_path)

    report = db_module.build_aggregations_for_replaced_weeks(
        {"2026-01-16"},
        replacement_scope_exact=True,
        expected_generation_id=generation_id,
        expected_dataset_digest=digest,
        previous_dataset_digest=previous_digest,
        min_ms=30_000,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
    )

    assert report["build_strategy"] == "historical_partition"
    assert report.get("fallback_reason") is None
    for table in _TABLES:
        assert (
            _table_rows(
                partition_path,
                table,
                "WHERE billboard_week != '2026-01-16'",
            )
            == unaffected_before[table]
        )

    monkeypatch.setattr(db_module, "DB_PATH", str(full_path))
    full = db_module.build_aggregations(
        min_ms=30_000,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
        expected_generation_id=generation_id,
    )
    assert full["build_strategy"] == "full"
    _assert_aggregate_equivalence(partition_path, full_path)


def test_cross_week_interval_and_merge_chain_match_full_rebuild(tmp_path, monkeypatch) -> None:
    from backend.core import db as db_module

    partition_path = tmp_path / "partition-chain.db"
    full_path = tmp_path / "full-chain.db"
    _seed_database(partition_path, monkeypatch, include_boundary_chain=True)
    conn = sqlite3.connect(partition_path)
    previous_digest = str(
        conn.execute(
            "SELECT dataset_digest FROM playback_import_state WHERE state_id=1"
        ).fetchone()[0]
    )
    conn.execute("DELETE FROM plays WHERE play_id=102")
    _insert_play(
        conn,
        play_id=202,
        timestamp="2026-01-22T16:00:10Z",
        track_id=1,
        album_id=1,
        ms_played=50_000,
        fingerprint="chain-corrected",
        generation_id="chain-corrected-generation",
    )
    generation_id, digest = _publish_state(conn, "chain-corrected-generation")
    conn.close()
    _online_backup(partition_path, full_path)
    observed_ids: set[int] = set()
    original_loader = db_module._load_historical_week_replacement_frame

    def observe_loader(*args, **kwargs):
        frame = original_loader(*args, **kwargs)
        observed_ids.update(int(value) for value in frame["play_id"].tolist())
        return frame

    monkeypatch.setattr(db_module, "_load_historical_week_replacement_frame", observe_loader)
    report = db_module.build_aggregations_for_replaced_weeks(
        {"2026-01-16", "2026-01-23"},
        replacement_scope_exact=True,
        expected_generation_id=generation_id,
        expected_dataset_digest=digest,
        previous_dataset_digest=previous_digest,
        min_ms=30_000,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
    )

    assert report["build_strategy"] == "historical_partition"
    assert {101, 202, 103} <= observed_ids
    monkeypatch.setattr(db_module, "DB_PATH", str(full_path))
    monkeypatch.setattr(db_module, "_load_historical_week_replacement_frame", original_loader)
    db_module.build_aggregations(
        min_ms=30_000,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
        expected_generation_id=generation_id,
    )
    _assert_aggregate_equivalence(partition_path, full_path)


@pytest.mark.parametrize("gate", ["lineage", "base_lineage", "dependency", "ratio", "row_limit"])
def test_historical_replacement_gate_falls_back_to_full(tmp_path, monkeypatch, gate: str) -> None:
    from backend.core import db as db_module

    path = tmp_path / f"fallback-{gate}.db"
    _seed_database(path, monkeypatch, include_boundary_chain=gate == "row_limit")
    conn = sqlite3.connect(path)
    state = conn.execute(
        "SELECT active_generation_id, dataset_digest FROM playback_import_state"
    ).fetchone()
    conn.close()
    generation_id, digest = str(state[0]), str(state[1])
    previous_digest: str | None = digest
    weeks = {"2026-01-16"}
    if gate == "lineage":
        generation_id = "stale-generation"
    elif gate == "base_lineage":
        previous_digest = "stale-digest"
    elif gate == "dependency":
        conn = sqlite3.connect(path)
        conn.execute(
            "UPDATE spotify_track_meta SET duration_ms=240000 WHERE spotify_track_id='spotify-one'"
        )
        conn.commit()
        conn.close()
    elif gate == "ratio":
        weeks = {"2026-01-09", "2026-01-16", "2026-01-23"}
    else:
        monkeypatch.setattr(db_module, "_HISTORICAL_WEEK_REPLACEMENT_MAX_ROWS", 1)
    full_calls: list[dict] = []

    def fake_full(**kwargs):
        full_calls.append(kwargs)
        return {"build_strategy": "full"}

    monkeypatch.setattr(db_module, "build_aggregations", fake_full)

    report = db_module.build_aggregations_for_replaced_weeks(
        weeks,
        replacement_scope_exact=True,
        expected_generation_id=generation_id,
        expected_dataset_digest=digest,
        previous_dataset_digest=previous_digest,
        min_ms=30_000,
        dynamic_threshold=False,
        max_merge_gap_minutes=5,
    )

    assert report["build_strategy"] == "full"
    assert report["fallback_reason"]
    assert len(full_calls) == 1

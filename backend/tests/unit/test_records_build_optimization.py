"""Records-only batching: semantic bytes, query growth and frame ownership."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from backend.domains.playback.logical_timeline import attach_listening_duration_frame
from backend.domains.playback.records_album_facts import load_original_memberships
from backend.domains.playback.records_discovery import _no_repeat_streak
from backend.domains.playback.records_helpers import (
    grouped_records_duration,
    records_duration_frame,
)
from backend.services.analysis_snapshot_revision import COMMON, RECORDS, _table_digest

pytestmark = pytest.mark.unit


def test_records_batched_digest_keeps_every_byte(isolated_test_database):
    with sqlite3.connect(isolated_test_database) as conn:
        conn.row_factory = sqlite3.Row
        for table in COMMON + RECORDS:
            assert _table_digest(conn, table, batch=True) == _table_digest(conn, table)
        conn.execute("CREATE TEMP TABLE digest_edges (id INTEGER PRIMARY KEY, value, extra)")
        conn.executemany(
            "INSERT INTO digest_edges VALUES(?,?,?)",
            [
                (i, "quote'\n中文\\" if i % 2 else None, b"\x00\xff" if i % 3 else 1.25)
                for i in range(1030)
            ],
        )
        assert _table_digest(conn, "digest_edges", batch=True) == _table_digest(
            conn, "digest_edges"
        )
        before = _table_digest(conn, "digest_edges", batch=True)
        conn.execute("UPDATE digest_edges SET value=? WHERE id=513", ("changed",))
        assert _table_digest(conn, "digest_edges", batch=True) != before
        assert conn.row_factory is sqlite3.Row


def test_no_repeat_preserves_reset_rule_and_stable_ties(monkeypatch):
    frame = pd.DataFrame(
        {"ts": ["t"] * 6, "play_id": [5, 2, 4, 1, 6, 3], "track_id": ["a", "b", "a", "a", "d", "c"]}
    )

    def no_rows(*args, **kwargs):
        pytest.fail("Records sequence recreated a Series for each play")

    monkeypatch.setattr(pd.DataFrame, "iterrows", no_rows)
    # a b c a a d: reset-on-repeat yields 3, not a sliding-window metric.
    assert _no_repeat_streak(frame, "track_id", "track").iloc[0]["value"] == 3


def test_readonly_duration_aggregation_does_not_mutate_attached_frame():
    events = pd.DataFrame({"track_id": [1], "ms_played": [1000]})
    duration = pd.DataFrame(
        {"track_id": [1, 1], "ms_played": [1000, 2000], "slice_start_at": ["a", "b"]}
    )
    original = duration.copy(deep=True)
    attach_listening_duration_frame(events, duration)
    assert grouped_records_duration(events, ["track_id"]).iloc[0]["total_ms"] == 3000
    independent = records_duration_frame(events)
    independent.loc[0, "ms_played"] = -1
    assert_frame_equal(duration, original)


def _album_fixture(count):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
      CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT);
      INSERT INTO artists VALUES(1, 'artist');
      CREATE TABLE albums (album_id INTEGER PRIMARY KEY, album_name TEXT);
      CREATE TABLE album_projects (project_id INTEGER PRIMARY KEY, primary_album_id INTEGER,
        canonical_name TEXT, release_date TEXT, artist_id INTEGER);
      CREATE TABLE album_project_albums (project_id INTEGER, album_id INTEGER, role TEXT, source_bucket TEXT);
      CREATE TABLE tracks (track_id INTEGER PRIMARY KEY, spotify_track_id TEXT, track_name TEXT);
      CREATE TABLE album_project_tracks (project_id INTEGER, source_album_id INTEGER, track_id INTEGER,
        membership_role TEXT, min_merge_level INTEGER);
      CREATE TABLE album_spotify_links (album_id INTEGER, spotify_album_id TEXT, confidence REAL,
        play_count INTEGER, track_count INTEGER);
      CREATE TABLE spotify_album_meta (spotify_album_id TEXT, album_name TEXT, album_artists TEXT,
        release_date TEXT, total_tracks INTEGER, track_list TEXT, album_type TEXT);
    """)
    import json

    for i in range(count):
        c.execute("INSERT INTO albums VALUES(?,?)", (i, str(i)))
        c.execute("INSERT INTO album_projects VALUES(?,?,?,NULL,1)", (i, i, str(i)))
        c.execute("INSERT INTO album_project_albums VALUES(?,?,'primary','original_album')", (i, i))
        ids = [str(2 * i), str(2 * i + 1)]
        for track in ids:
            c.execute("INSERT INTO tracks VALUES(?,?,?)", (int(track), track, track))
            c.execute(
                "INSERT INTO album_project_tracks VALUES(?,?,?,'standard',1)", (i, i, int(track))
            )
        c.execute("INSERT INTO album_spotify_links VALUES(?,?,1,10,2)", (i, str(i)))
        c.execute(
            "INSERT INTO spotify_album_meta VALUES(?,?,?,NULL,2,?,'album')",
            (str(i), str(i), "artist", json.dumps(ids)),
        )
    return c


def test_original_membership_query_count_is_constant():
    counts = []
    for size in [1, 100]:
        conn = _album_fixture(size)
        sql = []
        conn.set_trace_callback(sql.append)
        facts = load_original_memberships(conn, 1)
        assert len(facts) == size
        assert all(value == ({str(i * 2), str(i * 2 + 1)}, 2) for i, value in facts.items())
        counts.append(len(sql))
        conn.close()
    assert counts[0] == counts[1]
    assert counts[1] <= 5


def test_album_total_batch_preserves_legacy_selection(isolated_test_database):
    from backend.domains.playback.records_discovery import (
        _get_album_total_tracks,
        _load_album_total_tracks,
    )

    with sqlite3.connect(isolated_test_database) as conn:
        conn.row_factory = sqlite3.Row
        statements = []
        conn.set_trace_callback(statements.append)
        totals = _load_album_total_tracks(conn)
        assert len(statements) == 1
        for (album, artist), total in totals.items():
            assert total == _get_album_total_tracks(conn, album, artist)

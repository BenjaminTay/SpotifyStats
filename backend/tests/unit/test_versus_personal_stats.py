"""Union-loader equivalence at logical event and listening boundaries."""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.core.db import merge_consecutive_plays
from backend.domains.playback.counting import filter_effective_plays
from backend.domains.playback.logical_timeline import reconstruct_listening_intervals
from backend.services import versus_personal_stats_service as service
from backend.services.analysis_stats_service import build_duration_frame

pytestmark = pytest.mark.unit

FILTERS = dict(
    min_ms=30_000,
    music_only=True,
    merge_enabled=True,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    merge_level=2,
)


@pytest.fixture
def timeline_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY,artist_name TEXT);
        CREATE TABLE albums(album_id INTEGER PRIMARY KEY,album_name TEXT);
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY,track_name TEXT,
                            artist_id INTEGER,album_id INTEGER,spotify_track_id TEXT);
        CREATE TABLE spotify_track_meta(spotify_track_id TEXT,duration_ms INTEGER);
        CREATE TABLE plays(play_id INTEGER PRIMARY KEY,ts TEXT,ts_date TEXT,ts_hour INTEGER,
                           ms_played INTEGER,track_id INTEGER,source_album_id INTEGER,
                           spotify_track_id_at_play TEXT,source_fingerprint TEXT);
        INSERT INTO artists VALUES(1,'One'),(2,'Two');
        INSERT INTO albums VALUES(1,'Shared');
        INSERT INTO tracks VALUES(1,'Target',1,1,'one'),(2,'Other target',2,1,'two'),
                                 (3,'Interrupter',2,1,'three');
        INSERT INTO spotify_track_meta VALUES('one',60000),('two',60000),('three',60000);
    """)
    yield conn
    conn.close()


def add_rows(conn, rows):
    conn.executemany(
        """INSERT INTO plays(play_id,track_id,ts,ms_played,source_album_id,
                            source_fingerprint,ts_date,ts_hour)
           VALUES(?,?,?,?,?,?,?,?)""",
        [
            (
                *row,
                str(pd.Timestamp(row[2]).tz_convert("Asia/Shanghai").date()),
                pd.Timestamp(row[2]).tz_convert("Asia/Shanghai").hour,
            )
            for row in rows
        ],
    )


def full_oracle(conn, source_ids, params):
    # Independent full-library read in the same deterministic order. This
    # intentionally never uses the scoped SQL or its boundary selection.
    raw = pd.read_sql_query(
        """
        SELECT p.*,p.track_id AS source_track_id,p.track_id AS l1_id,
               p.track_id AS representative_track_id,t.track_name,t.artist_id,
               a.artist_name,al.album_name,stm.duration_ms
        FROM plays p LEFT JOIN tracks t ON t.track_id=p.track_id
        LEFT JOIN artists a ON a.artist_id=t.artist_id
        LEFT JOIN albums al ON al.album_id=t.album_id
        LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id=t.spotify_track_id
        ORDER BY p.ts,COALESCE(p.source_fingerprint,''),p.play_id
    """,
        conn,
    )
    if params["music_only"]:
        raw = raw[raw["track_id"].notna()]
    durations = reconstruct_listening_intervals(
        raw,
        identity_column="l1_id",
        max_gap_minutes=params["max_merge_gap_minutes"],
        boundary_column="source_album_id",
    )
    events = (
        merge_consecutive_plays(
            raw,
            params["min_ms"],
            max_gap_minutes=params["max_merge_gap_minutes"],
            boundary_column="source_album_id",
            dynamic_threshold=params["dynamic_threshold"],
        )
        if params["merge_enabled"]
        else raw
    )
    events = filter_effective_plays(
        events,
        min_ms=params["min_ms"],
        dynamic_threshold=params["dynamic_threshold"],
    )
    return (
        events[events["source_track_id"].isin(source_ids)],
        durations[durations["source_track_id"].isin(source_ids)],
    )


def assert_oracle(conn, source_ids, params):
    events, durations = service._load_target_timeline(conn, source_ids, params)
    events = events[events["source_track_id"].isin(source_ids)]
    durations = durations[durations["source_track_id"].isin(source_ids)]
    expected_events, expected_durations = full_oracle(conn, source_ids, params)
    for actual, expected in [(events, expected_events), (durations, expected_durations)]:
        cols = ["play_id", "track_id", "ms_played", "ts_date"]
        if "_listening_intervals_ns" in expected.columns:
            cols += ["_listening_intervals_ns"]
        pd.testing.assert_frame_equal(
            actual[cols].reset_index(drop=True), expected[cols].reset_index(drop=True)
        )
    actual_slices = build_duration_frame(events, duration_source=durations)
    expected_slices = build_duration_frame(expected_events, duration_source=expected_durations)
    assert service._metrics(events, actual_slices) == service._metrics(
        expected_events, expected_slices
    )
    assert service._metrics(events, service._basic_duration_frame(durations)) == service._metrics(
        expected_events, expected_slices
    )
    return events, durations, actual_slices


@pytest.mark.parametrize("merge", [False, True])
@pytest.mark.parametrize("dynamic", [False, True])
def test_union_preserves_interruptions_source_changes_and_unqualified_duration(
    timeline_conn, merge, dynamic
):
    add_rows(
        timeline_conn,
        [
            (1, 1, "2026-01-01T00:01:00Z", 20_000, 1, "a"),
            (2, 3, "2026-01-01T00:01:20Z", 20_000, 1, "b"),
            (3, 1, "2026-01-01T00:01:40Z", 20_000, 1, "c"),
            (4, 2, "2026-01-02T00:01:00Z", 60_000, 1, "d"),
            (5, 1, "2026-01-02T00:02:00Z", 60_000, 1, "e"),
            (6, 1, "2026-01-02T00:02:59Z", 60_000, 2, "f"),
            (7, 3, "2026-01-03T00:00:01Z", 1_000, 1, "g"),
        ],
    )
    params = {**FILTERS, "merge_enabled": merge, "dynamic_threshold": dynamic}
    events, durations, _ = assert_oracle(timeline_conn, (1, 2), params)
    assert len(events) == 3
    assert durations["ms_played"].sum() == 220_000


def test_equal_timestamp_predecessor_uses_source_fingerprint(timeline_conn):
    add_rows(
        timeline_conn,
        [
            (1, 1, "2026-01-01T00:01:00Z", 1_000, 1, "a"),
            (2, 1, "2026-01-01T00:01:00Z", 1_000, 1, "z"),
            (3, 3, "2026-01-01T00:01:00Z", 1_000, 1, "m"),
        ],
    )
    events, durations, _ = assert_oracle(timeline_conn, (1,), {**FILTERS, "min_ms": 1_500})
    assert events.empty
    assert durations["ms_played"].sum() == 2_000


def test_cross_midnight_overlap_needs_left_run_but_no_right_clip(timeline_conn):
    add_rows(
        timeline_conn,
        [
            (1, 1, "2026-01-01T16:00:00Z", 60_000, 1, "a"),
            (2, 1, "2026-01-01T16:00:59Z", 60_000, 1, "b"),
            (3, 3, "2026-01-01T16:01:01Z", 60_000, 1, "c"),
            (4, 2, "2026-01-02T16:00:10Z", 10_000, 1, "d"),
        ],
    )
    events, durations, slices = assert_oracle(timeline_conn, (1, 2), FILTERS)
    assert len(events) == 2
    assert durations["ms_played"].sum() == 130_000
    assert slices["ts_date"].nunique() == 3
    assert service._metrics(events, slices)["active_days"] == 3


def test_metrics_use_rounded_hours_active_days_and_event_max():
    events = pd.DataFrame({"ts_date": ["2026-01-01"] * 3 + ["2026-01-03"]})
    durations = pd.DataFrame(
        {
            "ts_date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "ms_played": [3_600_000, 360_000, 72_000],
        }
    )
    assert service._metrics(events, durations) == dict(
        total_plays=4,
        total_hours=1.1,
        active_days=3,
        avg_daily_plays=1.33,
        avg_daily_hours=0.37,
        max_daily_plays=3,
    )


def test_lifetime_retains_unqualified_edge_days(timeline_conn):
    from backend.services.analysis_stats_service import resolve_period

    add_rows(
        timeline_conn,
        [
            (1, 1, "2026-01-01T04:00:00Z", 20_000, 1, "a"),
            (2, 1, "2026-01-02T04:00:00Z", 60_000, 1, "b"),
            (3, 1, "2026-01-03T04:00:00Z", 20_000, 1, "c"),
        ],
    )
    events, durations, slices = assert_oracle(timeline_conn, (1,), FILTERS)
    assert service._metrics(events, slices)["active_days"] == 3
    assert slices["ms_played"].sum() == 100_000
    # Existing full-details lifetime clipped duration to count-qualified
    # dates, omitting short fragments at coverage edges. The new contract
    # explicitly fixes that conflict with the count/duration two-track rule.
    old = build_duration_frame(
        events, resolve_period(events, "lifetime", None, None), duration_source=durations
    )
    assert old["ms_played"].sum() == 60_000
    assert old["ts_date"].nunique() == 1


def test_effective_credit_alias_and_collaboration_keep_expanded_events(timeline_conn):
    timeline_conn.executescript("""
        INSERT INTO artists VALUES(4,'One alias');
        CREATE TABLE artist_identity_aliases(alias_artist_id INTEGER,canonical_artist_id INTEGER);
        INSERT INTO artist_identity_aliases VALUES(4,1);
        CREATE TABLE track_artists(track_id INTEGER,artist_id INTEGER,role TEXT);
        INSERT INTO track_artists VALUES(1,1,'primary'),(1,4,'featured'),(1,2,'featured');
    """)
    add_rows(timeline_conn, [(1, 1, "2026-01-01T04:00:00Z", 125_000, 1, "a")])
    events, durations = service._load_target_timeline(timeline_conn, (1,), FILTERS)
    artist_events, artist_durations = service._artist_frames(
        timeline_conn, events, durations, {1, 2}
    )
    assert artist_events.groupby("artist_id").size().to_dict() == {1: 2, 2: 2}
    assert artist_durations.groupby("artist_id")["ms_played"].sum().to_dict() == {
        1: 125_000,
        2: 125_000,
    }
    assert artist_events["_logical_event_id"].nunique() == 2


@pytest.mark.parametrize("manual", [False, True])
@pytest.mark.parametrize("resolved_credits", [False, True])
def test_skipping_primary_projection_preserves_effective_artist_rows_and_metrics(
    timeline_conn, manual, resolved_credits
):
    from backend.domains.metadata.track_credits import get_effective_track_credit_frame

    timeline_conn.executescript("""
        INSERT INTO artists VALUES(4,'One alias'),(5,'Manual guest');
        CREATE TABLE artist_identity_aliases(alias_artist_id INTEGER,canonical_artist_id INTEGER);
        INSERT INTO artist_identity_aliases VALUES(4,1);
        CREATE TABLE track_artists(track_id INTEGER,artist_id INTEGER,role TEXT);
        INSERT INTO track_artists VALUES(1,1,'primary'),(1,4,'featured'),(1,2,'featured');
    """)
    timeline_conn.execute("UPDATE tracks SET artist_id=4 WHERE track_id=1")
    if manual:
        timeline_conn.executescript("""
            CREATE TABLE track_credit_overrides(
                override_id INTEGER,track_id INTEGER,artist_id INTEGER,action TEXT,role TEXT,
                evidence_type TEXT,evidence_source TEXT,reason TEXT,actor TEXT,revision INTEGER,
                created_at TEXT,active INTEGER);
            INSERT INTO track_credit_overrides VALUES
                (1,1,2,'remove',NULL,'manual','fixture','remove credit','test',1,'2026-01-01',1),
                (2,1,5,'add','featured','manual','fixture','add credit','test',1,'2026-01-01',1);
        """)
    add_rows(timeline_conn, [(1, 1, "2026-01-01T04:00:00Z", 125_000, 1, "a")])
    old = service._load_target_timeline(timeline_conn, (1,), FILTERS)
    new = service._load_target_timeline(timeline_conn, (1,), FILTERS, canonicalize_artists=False)
    credits = get_effective_track_credit_frame(timeline_conn, [1])
    selection = (
        [
            SimpleNamespace(
                artist_id=int(row.artist_id),
                artist_name=row.artist_name,
                credited_track_ids=(1,),
            )
            for row in credits.itertuples()
        ]
        if resolved_credits
        else None
    )
    old_frames = service._artist_frames(timeline_conn, *old, {1, 2, 5}, selection=selection)
    new_frames = service._artist_frames(timeline_conn, *new, {1, 2, 5}, selection=selection)
    for old_frame, new_frame in zip(old_frames, new_frames):
        pd.testing.assert_frame_equal(old_frame, new_frame)
    expected_ids = {1, 5} if manual else {1, 2}
    assert new_frames[0].groupby("artist_id").size().to_dict() == {
        artist_id: 2 for artist_id in expected_ids
    }
    assert new_frames[0]["_logical_event_id"].nunique() == 2
    old_slices = service._basic_duration_frame(old_frames[1])
    new_slices = service._basic_duration_frame(new_frames[1])
    for artist_id in expected_ids:
        assert service._metrics(
            old_frames[0][old_frames[0]["artist_id"] == artist_id],
            old_slices[old_slices["artist_id"] == artist_id],
        ) == service._metrics(
            new_frames[0][new_frames[0]["artist_id"] == artist_id],
            new_slices[new_slices["artist_id"] == artist_id],
        )


def test_compact_duration_projection_keeps_long_intervals_and_fractional_hour_rounding(
    timeline_conn,
):
    add_rows(
        timeline_conn,
        [
            (1, 1, "2026-01-03T16:00:00.000500Z", 180_000_000, 1, "a"),
            (2, 2, "2026-01-05T16:00:00.000500Z", 1, 1, "b"),
        ],
    )
    events, durations = service._load_target_timeline(timeline_conn, (1, 2), FILTERS)
    projected = service._basic_duration_frame(durations)
    oracle = build_duration_frame(events, duration_source=durations)
    assert (
        projected.groupby("track_id")["ms_played"].sum().to_dict()
        == oracle.groupby("track_id")["ms_played"].sum().to_dict()
    )
    for track_id in (1, 2):
        assert set(projected.loc[projected["track_id"] == track_id, "ts_date"]) == set(
            oracle.loc[oracle["track_id"] == track_id, "ts_date"]
        )


@pytest.mark.parametrize("music_only", [False, True])
@pytest.mark.parametrize(
    "rows",
    [
        [],
        [(None, None)],
        [(None, "2020-01-01"), (1, None)],
        [(None, "2020-01-01"), (1, "2023-01-01"), (2, "2021-01-01"), (None, "2024-01-01")],
    ],
)
def test_coverage_edges_preserve_aggregate_null_and_music_rules(timeline_conn, music_only, rows):
    timeline_conn.executemany("INSERT INTO plays(track_id,ts_date) VALUES(?,?)", rows)
    where = "WHERE track_id IS NOT NULL" if music_only else ""
    expected = tuple(
        timeline_conn.execute(f"SELECT MIN(ts_date),MAX(ts_date) FROM plays {where}").fetchone()
    )
    assert service._coverage_bounds(timeline_conn, music_only) == expected


def test_date_labels_preserve_repeated_dates_nat_and_nonsequential_index():
    dates = pd.Series(
        pd.to_datetime(["2026-01-01", "2026-01-01", None, "2026-01-03"]), index=[9, 4, 8, 1]
    ).dt.tz_localize("Asia/Shanghai")
    pd.testing.assert_series_equal(service._date_labels(dates), dates.dt.strftime("%Y-%m-%d"))


def test_album_song_union_preserves_keys_for_each_frame_and_empty_selection(
    monkeypatch, timeline_conn
):
    from backend.domains.playback import album_projects

    calls = []

    def resolve(frame, conn, level):
        calls.append(frame["track_id"].tolist())
        assert level == 3
        return frame.assign(canonical_song_key=frame["track_id"].map({1: "work:7", 2: "l1:2"}))

    monkeypatch.setattr(album_projects, "apply_canonical_song_keys", resolve)
    events = pd.DataFrame(
        {"track_id": [1, 1], "track_name": ["Alias", "Song"], "ms_played": [10, 20]}, index=[5, 8]
    )
    durations = pd.DataFrame(
        {"track_id": [2, 1], "track_name": ["Other", "Song"], "ms_played": [5, 40]}, index=[3, 9]
    )
    actual_events, actual_durations = service._album_song_frames(
        timeline_conn, events, durations, 3
    )
    assert calls == [[1, 2]]
    pd.testing.assert_frame_equal(
        actual_events, events.assign(canonical_song_key=["work:7", "work:7"])
    )
    pd.testing.assert_frame_equal(
        actual_durations, durations.assign(canonical_song_key=["l1:2", "work:7"])
    )
    empty = pd.DataFrame(columns=["track_id"])
    a, b = service._album_song_frames(timeline_conn, empty, empty, 3)
    assert a.empty and b.empty and "canonical_song_key" in a and "canonical_song_key" in b

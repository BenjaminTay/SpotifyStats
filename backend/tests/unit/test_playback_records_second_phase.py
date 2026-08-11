from __future__ import annotations

import sqlite3

import pandas as pd

from backend.domains.playback.records_behavior import _milestone_targets, _playback_milestones
from backend.domains.playback.records_discovery import _discovery_day, _same_name_diff_artist
from backend.domains.playback.records_obsession import _consecutive_marathon, _top_daily_entity
from backend.domains.playback.records_output import _add_cover_urls_to_records
from backend.domains.playback.records_time import _late_night_trajectory


def test_same_name_diff_artist_returns_complete_aligned_artist_profiles():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE artists (
               artist_id INTEGER PRIMARY KEY,
               artist_name TEXT,
               image_path TEXT,
               image_url TEXT
           )"""
    )
    conn.executemany(
        "INSERT INTO artists VALUES (?, ?, ?, ?)",
        [
            (1, "Most Played", "/tmp/most.jpg", None),
            (2, "Second Artist", None, None),
            (3, "Third Artist", None, "https://example.com/third.jpg"),
        ],
    )
    frame = pd.DataFrame(
        {
            "track_name": ["Home"] * 6 + ["Other"],
            "artist_name": [
                "Second Artist",
                "Most Played",
                "Most Played",
                "Third Artist",
                "Most Played",
                "Second Artist",
                "Solo",
            ],
        }
    )

    result = _same_name_diff_artist(frame, conn).iloc[0]

    assert result["name"] == "Home"
    assert result["artist_names"] == ["Most Played", "Second Artist", "Third Artist"]
    assert result["artist_cover_urls"] == [
        "/covers/artists/1.jpg",
        None,
        "/covers/artists/3.jpg",
    ]
    assert result["artist_play_counts"] == [3, 2, 1]
    assert result["caption"] == "Most Played、Second Artist、Third Artist"


def test_discovery_day_uses_entity_specific_chinese_units():
    frame = pd.DataFrame(
        {
            "track_id": [1, 2],
            "track_name": ["A", "B"],
            "artist_name": ["Artist", "Artist"],
            "ts_date": ["2026-01-01", "2026-01-01"],
        }
    )

    assert (
        _discovery_day(frame, "track_id", "track_name", "artist_name", "track").iloc[0]["unit"]
        == "首新歌"
    )
    assert (
        _discovery_day(frame, "track_id", "track_name", "artist_name", "album").iloc[0]["unit"]
        == "张新专辑"
    )
    assert (
        _discovery_day(frame, "track_id", "track_name", "artist_name", "artist").iloc[0]["unit"]
        == "位新艺人"
    )


def test_daily_top_track_keeps_real_member_track_id_for_detail_link():
    frame = pd.DataFrame(
        {
            "ts_date": ["2026-01-01", "2026-01-01"],
            "canonical_track_id": ["group:9", "group:9"],
            "canonical_track_name": ["Grouped Song", "Grouped Song"],
            "track_id": [101.0, 102.0],
            "artist_name": ["Artist", "Artist"],
            "play_id": [1, 2],
            "ms_played": [180000, 180000],
        }
    )

    result = _top_daily_entity(
        frame,
        "canonical_track_id",
        "canonical_track_name",
        "artist_name",
        "track",
    )

    assert result["2026-01-01"]["top_track_entity_id"] == "101"


def test_artist_marathon_uses_logical_event_continuity_across_featured_credits():
    frame = pd.DataFrame(
        [
            {
                "_artist_event_id": 0,
                "play_id": 1,
                "ts": "2026-01-01T00:00:00Z",
                "ms_played": 180000,
                "artist_name": "Taylor Swift",
            },
            {
                "_artist_event_id": 1,
                "play_id": 2,
                "ts": "2026-01-01T00:03:00Z",
                "ms_played": 180000,
                "artist_name": "Taylor Swift",
            },
            {
                "_artist_event_id": 1,
                "play_id": 2,
                "ts": "2026-01-01T00:03:00Z",
                "ms_played": 180000,
                "artist_name": "Lana Del Rey",
            },
            {
                "_artist_event_id": 2,
                "play_id": 3,
                "ts": "2026-01-01T00:06:00Z",
                "ms_played": 180000,
                "artist_name": "Taylor Swift",
            },
        ]
    )

    result = _consecutive_marathon(
        frame,
        "artist_name",
        "artist_name",
        "artist_name",
        "artist",
    )

    taylor = result[result["name"] == "Taylor Swift"].iloc[0]
    lana = result[result["name"] == "Lana Del Rey"].iloc[0]
    assert taylor["value"] == 3
    assert taylor["secondary_value"] == 0.2
    assert lana["value"] == 1


def test_hourly_track_float_entity_id_resolves_album_cover(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT,
            artist_id INTEGER,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT,
            artist_id INTEGER,
            album_id INTEGER
        );
        INSERT INTO artists VALUES (1, 'Olivia Rodrigo', NULL, NULL);
        INSERT INTO albums VALUES (18, 'GUTS', 1, '/tmp/guts.jpg', NULL);
        INSERT INTO tracks VALUES (1493, 'vampire', 1, 18);
        """
    )
    monkeypatch.setattr("backend.domains.playback.records_output.get_db", lambda: conn)
    records = {
        "time_hourly_track": pd.DataFrame(
            [{"entity_type": "track", "entity_id": "1493.0", "name": "vampire"}]
        )
    }

    _add_cover_urls_to_records(records)

    assert records["time_hourly_track"].iloc[0]["cover_url"] == "/covers/albums/18.jpg"


def test_feat_track_name_fallback_adds_stable_track_id_and_cover(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT,
            artist_id INTEGER,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT,
            artist_id INTEGER,
            album_id INTEGER
        );
        INSERT INTO artists VALUES (1, 'Taylor Swift', NULL, NULL);
        INSERT INTO albums VALUES (13, 'reputation', 1, '/tmp/reputation.jpg', NULL);
        INSERT INTO tracks VALUES (221, 'End Game (feat. Ed Sheeran & Future)', 1, 13);
        """
    )
    monkeypatch.setattr("backend.domains.playback.records_output.get_db", lambda: conn)
    records = {
        "discovery_feat_lover_track": pd.DataFrame(
            [
                {
                    "rank": 1,
                    "name": "End Game (feat. Ed Sheeran & Future)",
                    "artist_name": "Taylor Swift",
                    "value": 12,
                    "unit": "次",
                }
            ]
        )
    }

    _add_cover_urls_to_records(records)

    row = records["discovery_feat_lover_track"].iloc[0]
    assert row["entity_id"] == "221"
    assert row["cover_url"] == "/covers/albums/13.jpg"


def test_late_night_trajectory_applies_monthly_and_quarterly_sample_thresholds():
    events = []

    def add_period(date: str, total: int, late: int):
        start = len(events)
        events.extend(
            {
                "play_id": start + index,
                "ts_date": date,
                "ts_hour": 1 if index < late else 12,
            }
            for index in range(total)
        )

    add_period("2026-01-15", 499, 100)
    add_period("2026-02-15", 500, 50)
    add_period("2026-03-15", 501, 0)
    add_period("2026-04-15", 1499, 300)

    monthly, quarterly = _late_night_trajectory(pd.DataFrame(events))
    january = monthly[monthly["name"] == "2026-01"].iloc[0]
    february = monthly[monthly["name"] == "2026-02"].iloc[0]
    q1 = quarterly[quarterly["name"] == "2026Q1"].iloc[0]
    q2 = quarterly[quarterly["name"] == "2026Q2"].iloc[0]

    assert bool(january["qualified"]) is False
    assert january["value"] == 20.0
    assert bool(february["qualified"]) is True
    assert february["value"] == 10.0
    assert q1["total_plays"] == 1500
    assert bool(q1["qualified"]) is True
    assert q2["total_plays"] == 1499
    assert bool(q2["qualified"]) is False


def test_dynamic_milestone_targets_cover_small_totals_and_3k_boundary():
    assert _milestone_targets(499) == []
    assert _milestone_targets(500) == [500]
    assert _milestone_targets(2999) == [500, 1000, 1500, 2000, 2500]
    assert _milestone_targets(3000) == [1000, 2000, 3000]
    assert _milestone_targets(3001) == [1000, 2000, 3000]


def test_dynamic_milestone_targets_cover_medium_totals_and_10k_boundary():
    assert _milestone_targets(7999) == [1000, 2000, 5000, 7000]
    assert _milestone_targets(8000) == [1000, 2000, 5000, 8000]
    assert _milestone_targets(10000) == [1000, 2000, 5000, 8000, 10000]
    assert _milestone_targets(10001) == [1000, 5000, 10000]


def test_dynamic_milestone_targets_cover_large_totals_and_10k_steps():
    assert _milestone_targets(19999) == [1000, 5000, 10000]
    assert _milestone_targets(20000) == [1000, 5000, 10000, 20000]
    assert _milestone_targets(64986) == [
        1000,
        5000,
        10000,
        20000,
        30000,
        40000,
        50000,
        60000,
    ]


def test_playback_milestone_rows_include_track_artist_date_and_current_total():
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=500, freq="min"),
            "ts_date": ["2026-01-01"] * 500,
            "track_name": [f"Track {index}" for index in range(500)],
            "artist_name": [f"Artist {index}" for index in range(500)],
            "track_id": list(range(1, 501)),
        }
    )

    row = _playback_milestones(frame).iloc[0]

    assert row["value"] == 500
    assert row["name"] == "Track 499"
    assert row["artist_name"] == "Artist 499"
    assert row["date"] == "2026-01-01"
    assert row["total_plays"] == 500
    assert row["entity_type"] == "track"
    assert row["entity_id"] == "500"
    assert row["caption"] == "第 500 次播放"

import sqlite3

import pandas as pd
import pytest

from backend.domains.billboard import entity_lists, versus


def test_picker_keeps_ids_and_labels_same_name_editions(monkeypatch):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
      CREATE TABLE albums(album_id INTEGER,album_name TEXT);
      CREATE TABLE album_projects(project_id INTEGER,canonical_name TEXT,primary_album_id INTEGER,release_date TEXT);
      CREATE TABLE album_spotify_links(album_id INTEGER,spotify_album_id TEXT,confidence REAL);
      CREATE TABLE spotify_album_meta(spotify_album_id TEXT,album_name TEXT,release_date TEXT,release_date_precision TEXT,album_type TEXT);
      INSERT INTO albums VALUES(1,'Same'),(2,'Same');
      INSERT INTO album_projects VALUES(10,'Same',1,'1994-01-01'),(20,'Same',2,'2019-07-10');
      INSERT INTO album_spotify_links VALUES(1,'old',1),(2,'new',1);
      INSERT INTO spotify_album_meta VALUES('old','Same','1994-01-01','day','album'),('new','Same','2019-07-10','day','album');
    """)
    rows = [
        {
            "album_name": "Same",
            "artist_name": "Cast",
            "album_project_id": pid,
            "power_score": 100 - pid,
        }
        for pid in (10, 20)
    ]
    payload = {
        "track_summary": [],
        "album_power_scores": rows,
        "album_track_counts": rows,
        "artist_power_scores": [],
        "artist_track_counts": [],
    }
    monkeypatch.setattr(entity_lists, "compute_billboard_data", lambda *a, **k: payload)
    monkeypatch.setattr(entity_lists, "get_db", lambda **k: c)
    result = entity_lists.get_billboard_entity_lists(30000, True, 30, 20, 20, 4, 13, None, None)[
        "albums"
    ]
    assert [r["project_id"] for r in result] == [10, 20]
    assert "1994" in result[0]["display"] and "2019" in result[1]["display"]


def test_same_label_chart_metrics_are_selected_by_project_id(monkeypatch):
    weekly = pd.DataFrame(
        [
            {
                "album_name": "Same",
                "artist_name": "Cast",
                "album_project_id": pid,
                "billboard_week": "2026-01-02",
                "rank": rank,
                "play_count": plays,
            }
            for pid, rank, plays in [(10, 1, 100), (20, 2, 20)]
        ]
    )
    powers = weekly.assign(power_score=[200, 30])
    counts = weekly.assign(
        total_tracks=1, top1=[1, 0], weeks_at_no1=[1, 0], best_peak=[1, 2], total_weeks=1
    )
    members = pd.DataFrame(
        [
            {
                "album_project_id": 10,
                "album_name": "Same",
                "album_artist_name": "Cast",
                "track_id": 1,
            },
            {
                "album_project_id": 20,
                "album_name": "Same",
                "album_artist_name": "Cast",
                "track_id": 2,
            },
        ]
    )
    tracks = pd.DataFrame(
        [
            {"track_id": 1, "power_score": 100, "peak_position": 1, "weeks_on_chart": 1},
            {"track_id": 2, "power_score": 10, "peak_position": 2, "weeks_on_chart": 1},
        ]
    )
    ranks = versus._compute_album_track_ranks(members, tracks)
    monkeypatch.setattr(versus, "_vs_spotify_album_meta", lambda *a: None)
    result = [
        versus._build_album_entity(
            "Same", "Cast", weekly, powers, tracks, counts, members, ranks, project_id=pid
        )
        for pid in (10, 20)
    ]
    assert [r["metrics"]["total_plays"] for r in result] == [100, 20]
    assert [r["metrics"]["track_power_sum"] for r in result] == [100, 10]
    assert [r["metrics"]["power_rank"] for r in result] == [1, 2]


def _payload():
    return {
        "weekly": [
            {
                "track_id": 1,
                "track_name": "Advance Single",
                "artist_name": "Artist",
                "album_name": "Advance Single",
                "billboard_week": "2026-01-02",
                "rank": 1,
                "play_count": 10,
            },
            {
                "track_id": 2,
                "track_name": "Album Track",
                "artist_name": "Artist",
                "album_name": "Deluxe",
                "billboard_week": "2026-01-09",
                "rank": 1,
                "play_count": 8,
            },
        ],
        "weekly_album": [
            {
                "album_name": "Original",
                "artist_name": "Artist",
                "billboard_week": "2026-01-09",
                "rank": 1,
                "play_count": 18,
            },
        ],
        "album_power_scores": [
            {"album_name": "Original", "artist_name": "Artist", "power_score": 100},
        ],
        "power_scores": [
            {"track_id": 1, "power_score": 60, "peak_position": 1, "weeks_on_chart": 1},
            {"track_id": 2, "power_score": 40, "peak_position": 1, "weeks_on_chart": 1},
        ],
        "album_track_counts": [
            {
                "album_name": "Original",
                "artist_name": "Artist",
                "total_tracks": 2,
                "best_peak": 1,
                "total_weeks": 2,
                "top1": 2,
                "weeks_at_no1": 2,
            },
        ],
        "track_per_album": [
            {"album_name": "Original", "artist_name": "Artist", "track_id": 1},
            {"album_name": "Original", "artist_name": "Artist", "track_id": 2},
        ],
    }


def test_album_versus_uses_detail_project_membership(monkeypatch):
    payload = _payload()
    monkeypatch.setattr(versus, "compute_billboard_data", lambda *args, **kwargs: payload)
    monkeypatch.setattr(versus, "_vs_spotify_album_meta", lambda *args: None)

    result = versus.get_versus_album_multi(
        [
            {"album_name": "Original", "artist_name": "Artist"},
            {"album_name": "Original", "artist_name": "Artist"},
        ],
        30000,
        True,
        30,
        20,
        20,
        4,
        12,
        None,
        None,
    )

    metrics = result["entities"][0]["metrics"]
    assert metrics["num_tracks"] == 2
    assert metrics["num_no1_tracks"] == 2
    assert metrics["total_no1_track_weeks"] == 2
    assert metrics["track_power_sum"] == 100


@pytest.mark.parametrize(
    ("dynamic", "gap", "merge_level", "include_compilations", "merge_enabled"),
    [
        (False, None, 1, False, False),
        (True, 45, 2, False, True),
        (True, 90, 3, True, True),
    ],
)
def test_versus_forwards_complete_filter_context(
    monkeypatch, dynamic, gap, merge_level, include_compilations, merge_enabled
):
    captured = {}

    def fake_compute(*args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        payload = _payload()
        payload["track_summary"] = []
        return payload

    monkeypatch.setattr(versus, "compute_billboard_data", fake_compute)
    monkeypatch.setattr(versus, "_vs_spotify_track_meta", lambda *args: None)
    versus.get_versus_track_multi(
        [1, 2],
        30000,
        True,
        30,
        20,
        20,
        4,
        12,
        2024,
        2025,
        dynamic,
        gap,
        merge_level,
        include_compilations,
        merge_enabled,
    )

    assert captured == {
        "args": (30000, True, 30, 20, 20, 4, 12, 2024, 2025),
        "dynamic_threshold": dynamic,
        "max_merge_gap_minutes": gap,
        "merge_level": merge_level,
        "include_compilations": include_compilations,
        "merge_enabled": merge_enabled,
    }


def test_album_rank_is_disambiguated_by_artist():
    membership = pd.DataFrame(
        [
            {"track_id": 1, "album_name": "Same", "artist_name": "A"},
            {"track_id": 2, "album_name": "Same", "artist_name": "B"},
        ]
    )
    scores = pd.DataFrame(
        [
            {"track_id": 1, "power_score": 100, "peak_position": 1, "weeks_on_chart": 2},
            {"track_id": 2, "power_score": 10, "peak_position": 5, "weeks_on_chart": 1},
        ]
    )

    ranks = versus._compute_album_track_ranks(membership, scores)

    assert versus._lookup_album_track_rank(ranks, "Same", "A") == 1
    assert versus._lookup_album_track_rank(ranks, "Same", "B") == 2


def test_entity_picker_excludes_entities_without_detail_contract(monkeypatch):
    payload = {
        "track_summary": [],
        "album_power_scores": [
            {"album_name": "Valid", "artist_name": "A", "power_score": 2},
            {"album_name": "Ghost", "artist_name": "A", "power_score": 1},
        ],
        "album_track_counts": [
            {"album_name": "Valid", "artist_name": "A"},
        ],
        "artist_power_scores": [
            {"artist_name": "A", "power_score": 2},
            {"artist_name": "Ghost", "power_score": 1},
        ],
        "artist_track_counts": [{"artist_name": "A"}],
    }
    monkeypatch.setattr(entity_lists, "compute_billboard_data", lambda *args, **kwargs: payload)

    result = entity_lists.get_billboard_entity_lists(30000, True, 30, 20, 20, 4, 12, None, None)

    assert [row["album_name"] for row in result["albums"]] == ["Valid"]
    assert [row["artist_name"] for row in result["artists"]] == ["A"]


def test_album_versus_retains_performer_credit_but_selects_by_project(monkeypatch):
    payload = _payload()
    for name in ("weekly_album", "album_power_scores", "album_track_counts", "track_per_album"):
        for row in payload[name]:
            row["album_project_id"] = 42
    for row in payload["track_per_album"]:
        row["album_artist_name"] = row["artist_name"]
        row["artist_name"] = "Different Performer, Guest"
    monkeypatch.setattr(versus, "compute_billboard_data", lambda *a, **kw: payload)
    monkeypatch.setattr(versus, "_vs_spotify_album_meta", lambda *a: None)
    result = versus.get_versus_album_multi(
        [{"album_name": "Original", "artist_name": "Artist"}] * 2,
        30000,
        True,
        30,
        20,
        20,
        4,
        12,
        None,
        None,
    )
    assert result["entities"][0]["metrics"]["track_power_sum"] == 100
    assert result["entities"][0]["metrics"]["num_tracks"] == 2

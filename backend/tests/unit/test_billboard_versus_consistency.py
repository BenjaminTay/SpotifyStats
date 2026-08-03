import pandas as pd
import pytest

from backend.domains.billboard import entity_lists, versus


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
    ("dynamic", "gap", "merge_level", "include_compilations"),
    [(False, None, 1, False), (True, 45, 2, False), (True, 90, 3, True)],
)
def test_versus_forwards_complete_filter_context(
    monkeypatch, dynamic, gap, merge_level, include_compilations
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
    )

    assert captured == {
        "args": (30000, True, 30, 20, 20, 4, 12, 2024, 2025),
        "dynamic_threshold": dynamic,
        "max_merge_gap_minutes": gap,
        "merge_level": merge_level,
        "include_compilations": include_compilations,
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

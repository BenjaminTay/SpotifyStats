from __future__ import annotations

import pandas as pd

from backend.domains.billboard import details


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def test_album_chart_does_not_require_a_charting_member_track(monkeypatch):
    payload = {
        "weekly": [
            {
                "billboard_week": "2026-07-17",
                "track_id": 1,
                "track_name": "Other Track",
                "artist_name": "Other Artist",
                "rank": 1,
                "play_count": 20,
                "cover_url": None,
            }
        ],
        "weekly_album": [
            {
                "billboard_week": "2026-07-03",
                "album_project_id": 41194,
                "album_name": "CONFESSIONS II",
                "artist_name": "Madonna",
                "play_count": 6,
                "total_ms": 1_484_217,
                "rank": 19,
                "tracks_count": 0,
                "running_peak": 19,
                "running_wks": 1,
                "running_peak_wks": 1,
                "cover_url": "/covers/albums/20503.jpg",
            },
            {
                "billboard_week": "2026-07-17",
                "album_project_id": 41194,
                "album_name": "CONFESSIONS II",
                "artist_name": "Madonna",
                "play_count": 11,
                "total_ms": 2_623_179,
                "rank": 4,
                "tracks_count": 0,
                "running_peak": 4,
                "running_wks": 2,
                "running_peak_wks": 1,
                "cover_url": "/covers/albums/20503.jpg",
            },
        ],
        "album_track_counts": [
            {"album_name": "Other Album", "artist_name": "Other Artist", "total_tracks": 1}
        ],
        "track_per_album": [
            {
                "album_name": "Other Album",
                "artist_name": "Other Artist",
                "track_id": 1,
                "track_name": "Other Track",
                "peak_position": 1,
                "weeks_on_chart": 1,
            }
        ],
        "power_scores": [{"track_id": 1, "power_score": 1}],
        "album_power_scores": [
            {"album_name": "CONFESSIONS II", "artist_name": "Madonna", "power_score": 288}
        ],
    }
    monkeypatch.setattr(details, "compute_billboard_data", lambda *args, **kwargs: payload)
    monkeypatch.setattr(
        details,
        "_load_album_project_detail_events",
        lambda *args, **kwargs: pd.DataFrame(),
    )
    monkeypatch.setattr(
        details,
        "_get_album_project_payload",
        lambda *args, **kwargs: {"album_project_id": 41194, "play_count": 18},
    )
    monkeypatch.setattr(details, "_get_album_spotify_meta", lambda *args, **kwargs: None)

    result = details.get_album_chart_detail(
        "CONFESSIONS II", "Madonna", 30_000, True, 30, 20, 20, 4, 12, None, None
    )

    assert result["chart_status"] == "charted"
    assert result["track_chart_status"] == "not_charted"
    assert result["chart_summary"] == {
        "peak_position": 4,
        "weeks_on_chart": 2,
        "first_week": "2026-07-03",
        "first_peak_week": "2026-07-17",
        "latest_week": "2026-07-17",
        "no1_weeks": 0,
        "peak_weeks": 1,
        "power_score": 288,
        "power_rank": 1,
    }
    assert result["tracks"] == []
    assert result["info"] is None


def test_artist_chart_track_and_album_statuses_are_independent(monkeypatch):
    payload = {
        "weekly": [
            {
                "billboard_week": "2026-07-17",
                "track_id": 1,
                "track_name": "Other Track",
                "artist_name": "Other Artist",
                "rank": 1,
                "play_count": 20,
                "cover_url": None,
            }
        ],
        "weekly_artist": [
            {
                "billboard_week": "2026-07-17",
                "artist_name": "Aggregate Artist",
                "rank": 4,
                "play_count": 11,
                "tracks_count": 0,
                "albums_count": 1,
                "running_peak": 4,
                "running_wks": 1,
                "running_peak_wks": 1,
                "cover_url": None,
            }
        ],
        "weekly_album": [
            {
                "billboard_week": "2026-07-17",
                "album_name": "Aggregate Album",
                "artist_name": "Aggregate Artist",
                "rank": 4,
                "play_count": 11,
                "cover_url": None,
            }
        ],
        "artist_track_counts": [{"artist_name": "Other Artist", "total_tracks": 1}],
        "artist_summary": [
            {
                "artist_name": "Other Artist",
                "track_id": 1,
                "track_name": "Other Track",
                "peak_position": 1,
                "weeks_on_chart": 1,
            }
        ],
        "track_summary": [{"track_id": 1, "weeks_at_no1": 1, "first_peak_week": "2026-07-17"}],
        "power_scores": [{"track_id": 1, "power_score": 1}],
        "album_power_scores": [
            {"album_name": "Aggregate Album", "artist_name": "Aggregate Artist", "power_score": 9}
        ],
        "artist_power_scores": [
            {
                "artist_name": "Aggregate Artist",
                "power_score": 12,
                "track_power_rank": 3,
                "album_power_rank": 4,
            }
        ],
    }
    monkeypatch.setattr(details, "compute_billboard_data", lambda *args, **kwargs: payload)
    monkeypatch.setattr(details, "fan_out_weekly_for_artists", lambda frame: frame.copy())
    monkeypatch.setattr(details, "_get_artist_spotify_meta", lambda *args, **kwargs: None)

    result = details.get_artist_chart_detail(
        "Aggregate Artist", 30_000, True, 30, 20, 20, 4, 12, None, None
    )

    assert result["chart_status"] == "charted"
    assert result["track_chart_status"] == "not_charted"
    assert result["album_chart_status"] == "charted"
    assert result["tracks"] == []
    assert [album["album_name"] for album in result["albums"]] == ["Aggregate Album"]
    assert result["info"]["track_power_rank"] == 3
    assert result["info"]["album_power_rank"] == 4
    assert result["info"]["total_albums"] == 1
    assert result["info"]["total_album_weeks"] == 1

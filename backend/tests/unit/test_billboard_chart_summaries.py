from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.billboard.chart_summaries import (
    compute_album_track_counts,
    compute_artist_track_counts,
)

pytestmark = pytest.mark.unit


def test_compute_artist_track_counts_picks_best_peak_track_and_counts_no1s():
    artist_summary = pd.DataFrame(
        [
            {
                "artist_name": "Artist A",
                "track_id": 1,
                "track_name": "Second Best",
                "peak_position": 2,
                "weeks_on_chart": 3,
            },
            {
                "artist_name": "Artist A",
                "track_id": 2,
                "track_name": "Best One",
                "peak_position": 1,
                "weeks_on_chart": 5,
            },
            {
                "artist_name": "Artist B",
                "track_id": 3,
                "track_name": "Only Track",
                "peak_position": 8,
                "weeks_on_chart": 2,
            },
        ]
    )
    track_summary = pd.DataFrame(
        [
            {"artist_name": "Artist A", "weeks_at_no1": 2},
            {"artist_name": "Artist A", "weeks_at_no1": 1},
            {"artist_name": "Artist B", "weeks_at_no1": 0},
        ]
    )
    weekly_album = pd.DataFrame(
        [
            {
                "artist_name": "Artist A",
                "album_name": "Album A",
                "rank": 1,
                "billboard_week": "2026-01-02",
            },
            {
                "artist_name": "Artist A",
                "album_name": "Album A",
                "rank": 1,
                "billboard_week": "2026-01-09",
            },
            {
                "artist_name": "Artist B",
                "album_name": "Album B",
                "rank": 3,
                "billboard_week": "2026-01-02",
            },
        ]
    )
    weekly_artist = pd.DataFrame(
        [
            {"artist_name": "Artist A", "rank": 1, "billboard_week": "2026-01-02"},
            {"artist_name": "Artist A", "rank": 2, "billboard_week": "2026-01-09"},
        ]
    )

    result = compute_artist_track_counts(artist_summary, track_summary, weekly_album, weekly_artist)

    artist_a = result[result["artist_name"] == "Artist A"].iloc[0]
    assert artist_a["best_peak_track"] == "Best One"
    assert int(artist_a["top1"]) == 1
    assert int(artist_a["top5"]) == 2
    assert int(artist_a["weeks_at_no1"]) == 3
    assert int(artist_a["num_no1_albums"]) == 1
    assert int(artist_a["album_no1_weeks"]) == 2
    assert int(artist_a["artist_chart_no1_weeks"]) == 1


def test_compute_artist_track_counts_defaults_missing_no1_weeks_to_zero():
    artist_summary = pd.DataFrame(
        [
            {
                "artist_name": "Artist A",
                "track_id": 1,
                "track_name": "Primary Hit",
                "peak_position": 1,
                "weeks_on_chart": 5,
            },
            {
                "artist_name": "Featured Artist",
                "track_id": 2,
                "track_name": "Featured Entry",
                "peak_position": 8,
                "weeks_on_chart": 2,
            },
        ]
    )
    track_summary = pd.DataFrame(
        [
            {"artist_name": "Artist A", "weeks_at_no1": 3},
        ]
    )
    weekly_album = pd.DataFrame(columns=["artist_name", "album_name", "rank", "billboard_week"])
    weekly_artist = pd.DataFrame(columns=["artist_name", "rank", "billboard_week"])

    result = compute_artist_track_counts(artist_summary, track_summary, weekly_album, weekly_artist)

    featured = result[result["artist_name"] == "Featured Artist"].iloc[0]
    assert int(featured["weeks_at_no1"]) == 0


def test_compute_album_track_counts_picks_best_peak_track_per_album_artist():
    track_summary = pd.DataFrame(
        [
            {
                "track_id": 1,
                "track_name": "Album Opener",
                "artist_name": "Artist A",
                "album_name": "Source Album",
                "peak_position": 7,
                "weeks_on_chart": 2,
                "weeks_at_no1": 0,
            },
            {
                "track_id": 2,
                "track_name": "Album Hit",
                "artist_name": "Artist A",
                "album_name": "Source Album",
                "peak_position": 1,
                "weeks_on_chart": 5,
                "weeks_at_no1": 3,
            },
            {
                "track_id": 3,
                "track_name": "Other Artist Track",
                "artist_name": "Artist B",
                "album_name": "Other Source",
                "peak_position": 4,
                "weeks_on_chart": 4,
                "weeks_at_no1": 0,
            },
        ]
    )
    album_map = pd.DataFrame(
        [
            {"track_id": 1, "album_list": ["Album A"]},
            {"track_id": 2, "album_list": ["Album A"]},
            {"track_id": 3, "album_list": ["Album A"]},
        ]
    )
    weekly_album = pd.DataFrame(
        [
            {
                "album_name": "Album A",
                "artist_name": "Artist A",
                "rank": 1,
                "billboard_week": "2026-01-02",
            },
            {
                "album_name": "Album A",
                "artist_name": "Artist B",
                "rank": 2,
                "billboard_week": "2026-01-02",
            },
        ]
    )

    album_counts, track_per_album = compute_album_track_counts(
        track_summary,
        album_map,
        weekly_album,
    )

    artist_a_album = album_counts[
        (album_counts["album_name"] == "Album A") & (album_counts["artist_name"] == "Artist A")
    ].iloc[0]
    assert artist_a_album["best_peak_track"] == "Album Hit"
    assert int(artist_a_album["total_tracks"]) == 2
    assert int(artist_a_album["top1"]) == 1
    assert int(artist_a_album["weeks_at_no1"]) == 3
    assert int(artist_a_album["album_chart_no1_weeks"]) == 1
    assert set(track_per_album["album_name"]) == {"Album A"}

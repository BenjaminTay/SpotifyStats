from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.billboard.chart_power_score import (
    compute_album_power_scores,
    compute_artist_power_scores,
    compute_power_scores,
)
from backend.domains.billboard.chart_ranking import (
    compute_album_weekly_rankings,
    compute_artist_weekly_rankings,
    compute_weekly_rankings,
)

pytestmark = pytest.mark.unit


def _shuffled(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.sample(frac=1, random_state=20260823).reset_index(drop=True)


def test_track_weekly_ties_use_track_id_not_input_order() -> None:
    frame = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2026-08-07"),
                "track_id": 20,
                "track_name": "Beta",
                "artist_name": "Artist B",
                "album_name": "Album B",
                "play_count": 5,
                "total_ms": 500_000,
            },
            {
                "billboard_week": pd.Timestamp("2026-08-07"),
                "track_id": 10,
                "track_name": "Alpha",
                "artist_name": "Artist A",
                "album_name": "Album A",
                "play_count": 5,
                "total_ms": 500_000,
            },
        ]
    )

    expected = compute_weekly_rankings(frame, 30, pre_agg=frame, merge_level=1)
    actual = compute_weekly_rankings(frame, 30, pre_agg=_shuffled(frame), merge_level=1)

    assert expected[["track_id", "rank"]].to_dict("records") == [
        {"track_id": 10, "rank": 1},
        {"track_id": 20, "rank": 2},
    ]
    pd.testing.assert_frame_equal(expected.reset_index(drop=True), actual.reset_index(drop=True))


def test_artist_weekly_ties_use_artist_id_not_input_order() -> None:
    frame = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2026-08-07"),
                "artist_id": 8,
                "artist_name": "Artist B",
                "play_count": 5,
                "total_ms": 500_000,
            },
            {
                "billboard_week": pd.Timestamp("2026-08-07"),
                "artist_id": 3,
                "artist_name": "Artist A",
                "play_count": 5,
                "total_ms": 500_000,
            },
        ]
    )

    expected = compute_artist_weekly_rankings(frame, 20, pre_agg=frame)
    actual = compute_artist_weekly_rankings(frame, 20, pre_agg=_shuffled(frame))

    assert expected[["artist_id", "rank"]].to_dict("records") == [
        {"artist_id": 3, "rank": 1},
        {"artist_id": 8, "rank": 2},
    ]
    pd.testing.assert_frame_equal(expected.reset_index(drop=True), actual.reset_index(drop=True))


def test_album_weekly_ties_use_album_project_id_not_input_order(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2026-08-07"),
                "track_id": 2,
                "album_project_id": 22,
                "album_project_name": "Beta",
                "artist_name": "Artist B",
                "play_count": 5,
                "total_ms": 500_000,
                "unique_canonical_songs": 1,
            },
            {
                "billboard_week": pd.Timestamp("2026-08-07"),
                "track_id": 1,
                "album_project_id": 11,
                "album_project_name": "Alpha",
                "artist_name": "Artist A",
                "play_count": 5,
                "total_ms": 500_000,
                "unique_canonical_songs": 1,
            },
        ]
    )

    class _Connection:
        def close(self) -> None:
            pass

    monkeypatch.setattr("backend.core.db.get_db", lambda **_kwargs: _Connection())
    monkeypatch.setattr(
        "backend.domains.playback.album_projects.compute_album_project_weekly_plays",
        lambda value, *_args, **_kwargs: value.drop(columns=["track_id"]).copy(),
    )

    expected = compute_album_weekly_rankings(frame, 20, pre_agg=frame)
    actual = compute_album_weekly_rankings(frame, 20, pre_agg=_shuffled(frame))

    assert expected[["album_project_id", "rank"]].to_dict("records") == [
        {"album_project_id": 11, "rank": 1},
        {"album_project_id": 22, "rank": 2},
    ]
    pd.testing.assert_frame_equal(expected.reset_index(drop=True), actual.reset_index(drop=True))


def test_power_ranks_are_stable_for_shuffled_equal_scores() -> None:
    tracks = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2026-08-07"),
                "track_id": track_id,
                "track_name": name,
                "artist_name": artist,
                "rank": 1,
                "play_count": 10,
            }
            for track_id, name, artist in ((20, "Beta", "Artist B"), (10, "Alpha", "Artist A"))
        ]
    )
    albums = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2026-08-07"),
                "album_name": album,
                "artist_name": artist,
                "rank": 1,
                "play_count": 10,
            }
            for album, artist in (("Beta", "Artist B"), ("Alpha", "Artist A"))
        ]
    )
    artists = albums[["billboard_week", "artist_name", "rank", "play_count"]].copy()

    cases = (
        (compute_power_scores, tracks, ["track_id"]),
        (compute_album_power_scores, albums, ["artist_name", "album_name"]),
        (compute_artist_power_scores, artists, ["artist_name"]),
    )
    for compute, frame, keys in cases:
        expected = compute(frame, 30).reset_index(drop=True)
        actual = compute(_shuffled(frame), 30).reset_index(drop=True)
        pd.testing.assert_frame_equal(expected, actual)
        assert expected["power_rank"].tolist() == [1, 2]
        assert expected[keys].to_dict("records") == sorted(
            expected[keys].to_dict("records"), key=lambda row: tuple(row[key] for key in keys)
        )

import pandas as pd

from backend.domains.billboard.cross_level_power import (
    attach_cross_level_power_metrics,
    compute_album_track_power_metrics,
    compute_artist_track_power_metrics,
)


def test_album_track_power_uses_project_membership_artist_disambiguation_and_competition_ties():
    albums = pd.DataFrame(
        [
            {"album_name": "Original", "artist_name": "A"},
            {"album_name": "Same", "artist_name": "A"},
            {"album_name": "Same", "artist_name": "B"},
            {"album_name": "No Singles", "artist_name": "C"},
        ]
    )
    membership = pd.DataFrame(
        [
            {"track_id": 1, "album_name": "Original", "artist_name": "A"},
            {"track_id": 1, "album_name": "Original", "artist_name": "A"},
            {"track_id": 2, "album_name": "Original", "artist_name": "A"},
            {"track_id": 3, "album_name": "Same", "artist_name": "A"},
            {"track_id": 4, "album_name": "Same", "artist_name": "B"},
        ]
    )
    scores = pd.DataFrame(
        [
            {"track_id": 1, "power_score": 60},
            {"track_id": 2, "power_score": 40},
            {"track_id": 3, "power_score": 50},
            {"track_id": 4, "power_score": 50},
        ]
    )

    result = compute_album_track_power_metrics(albums, membership, scores).set_index(
        ["album_name", "artist_name"]
    )

    assert result.loc[("Original", "A"), "track_power_sum"] == 100
    assert result.loc[("Original", "A"), "track_power_rank"] == 1
    assert result.loc[("Same", "A"), "track_power_rank"] == 2
    assert result.loc[("Same", "B"), "track_power_rank"] == 2
    assert result.loc[("No Singles", "C"), "track_power_sum"] == 0
    assert pd.isna(result.loc[("No Singles", "C"), "track_power_rank"])


def test_artist_track_power_deduplicates_canonical_featured_credit():
    artists = pd.DataFrame([{"artist_name": "Canonical"}, {"artist_name": "Other"}])
    credits = pd.DataFrame(
        [
            {"artist_name": "Canonical", "track_id": 1},
            {"artist_name": "Canonical", "track_id": 1},
            {"artist_name": "Canonical", "track_id": 2},
            {"artist_name": "Other", "track_id": 1},
        ]
    )
    scores = pd.DataFrame([{"track_id": 1, "power_score": 70}, {"track_id": 2, "power_score": 30}])

    result = compute_artist_track_power_metrics(artists, credits, scores).set_index("artist_name")

    assert result.loc["Canonical", "track_power_sum"] == 100
    assert result.loc["Canonical", "track_power_rank"] == 1
    assert result.loc["Other", "track_power_sum"] == 70
    assert result.loc["Other", "track_power_rank"] == 2


def test_attach_cross_level_power_keeps_zero_contributors_unranked():
    albums = pd.DataFrame(
        [
            {"album_name": "Album", "artist_name": "A", "power_score": 90},
            {"album_name": "Quiet", "artist_name": "B", "power_score": 20},
        ]
    )
    artists = pd.DataFrame(
        [
            {"artist_name": "A", "power_score": 120},
            {"artist_name": "B", "power_score": 30},
        ]
    )
    tracks = pd.DataFrame([{"track_id": 1, "power_score": 40}])
    membership = pd.DataFrame([{"track_id": 1, "album_name": "Album", "artist_name": "A"}])
    artist_summary = pd.DataFrame([{"artist_name": "A", "track_id": 1}])

    album_result, artist_result = attach_cross_level_power_metrics(
        albums, artists, tracks, membership, artist_summary
    )
    album_result = album_result.set_index(["album_name", "artist_name"])
    artist_result = artist_result.set_index("artist_name")

    assert album_result.loc[("Quiet", "B"), "track_power_sum"] == 0
    assert pd.isna(album_result.loc[("Quiet", "B"), "track_power_rank"])
    assert artist_result.loc["B", "track_power_sum"] == 0
    assert pd.isna(artist_result.loc["B", "track_power_rank"])
    assert artist_result.loc["A", "album_power_sum"] == 90
    assert artist_result.loc["A", "album_power_rank"] == 1

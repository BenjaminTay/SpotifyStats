"""Unit coverage for evidence-backed playback-record milestone thresholds."""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_reigns import _fastest_milestone


def _milestone_frame(count: int) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=count, freq="D")
    return pd.DataFrame(
        {
            "entity_id": ["fixture"] * count,
            "name": ["Fixture"] * count,
            "artist": ["Fixture Artist"] * count,
            "ts_date": dates.astype(str),
        }
    )


def test_fastest_milestone_uses_entity_specific_thresholds():
    cases = [("track", 50), ("artist", 250)]

    for entity_type, target in cases:
        result = _fastest_milestone(
            _milestone_frame(target),
            "entity_id",
            "name",
            "artist",
            entity_type,
        ).iloc[0]

        assert result["milestone_target"] == target
        assert result["value"] == target - 1
        assert result["unit"] == f"天達{target}次"


def test_album_milestone_ignores_prerelease_plays_and_starts_at_first_valid_play():
    prerelease = _milestone_frame(25)
    prerelease["ts_date"] = pd.date_range("2026-01-01", periods=25, freq="D").astype(str)
    postrelease = _milestone_frame(100)
    postrelease["ts_date"] = pd.date_range("2026-02-10", periods=100, freq="D").astype(str)
    frame = pd.concat([prerelease, postrelease], ignore_index=True)
    frame["album_release_date"] = "2026-02-01"

    result = _fastest_milestone(
        frame,
        "entity_id",
        "name",
        "artist",
        "album",
    ).iloc[0]

    assert result["milestone_target"] == 100
    assert result["value"] == 99
    assert result["start_date"] == "2026-02-10"
    assert result["end_date"] == "2026-05-20"


def test_album_milestone_excludes_prerelease_count_from_threshold():
    prerelease = _milestone_frame(100)
    prerelease["ts_date"] = pd.date_range("2025-09-01", periods=100, freq="h").astype(str)
    postrelease = _milestone_frame(99)
    postrelease["ts_date"] = pd.date_range("2026-02-10", periods=99, freq="D").astype(str)
    frame = pd.concat([prerelease, postrelease], ignore_index=True)
    frame["album_release_date"] = "2026-02-01"

    assert _fastest_milestone(frame, "entity_id", "name", "artist", "album").empty


def test_album_milestone_excludes_missing_or_partial_release_date():
    frame = _milestone_frame(100)

    assert _fastest_milestone(frame, "entity_id", "name", "artist", "album").empty

    frame["album_release_date"] = "2026-02"
    assert _fastest_milestone(frame, "entity_id", "name", "artist", "album").empty


def test_album_milestone_excludes_conflicting_release_dates():
    frame = _milestone_frame(100)
    frame["album_release_date"] = "2026-01-01"
    frame.loc[50:, "album_release_date"] = "2026-01-02"

    assert _fastest_milestone(frame, "entity_id", "name", "artist", "album").empty


def test_album_milestone_excludes_invalid_full_precision_release_date():
    frame = _milestone_frame(100)
    frame["album_release_date"] = "2026-99-99"

    assert _fastest_milestone(frame, "entity_id", "name", "artist", "album").empty


def test_fastest_milestone_preserves_first_source_metadata():
    frame = _milestone_frame(50)
    frame.loc[0, ["name", "artist", "ts_date"]] = [
        "Original Name",
        "Original Artist",
        "2026-02-20",
    ]

    result = _fastest_milestone(frame, "entity_id", "name", "artist", "track").iloc[0]

    assert result["name"] == "Original Name"
    assert result["artist_name"] == "Original Artist"


def test_artist_milestone_supports_identity_column_for_all_fields():
    frame = _milestone_frame(250).rename(columns={"artist": "artist_name"})

    result = _fastest_milestone(
        frame,
        "artist_name",
        "artist_name",
        "artist_name",
        "artist",
    ).iloc[0]

    assert result["entity_id"] == "Fixture Artist"
    assert result["name"] == "Fixture Artist"
    assert result["artist_name"] == "Fixture Artist"


def test_fastest_milestone_resolves_numeric_entity_metadata_by_entity_id():
    first = _milestone_frame(50).assign(entity_id=160.0, name="First")
    second = _milestone_frame(50).assign(entity_id=193.0, name="Second")
    frame = pd.concat([first, second], ignore_index=True)
    frame.index = range(1000, 1100)

    result = _fastest_milestone(frame, "entity_id", "name", "artist", "track")

    assert set(result["entity_id"]) == {"160.0", "193.0"}
    assert set(result["name"]) == {"First", "Second"}


def test_track_milestone_ignores_album_release_date_column():
    frame = _milestone_frame(50)
    frame["album_release_date"] = "2030-01-01"

    result = _fastest_milestone(frame, "entity_id", "name", "artist", "track").iloc[0]

    assert result["value"] == 49


def test_fastest_milestone_excludes_entities_below_threshold():
    result = _fastest_milestone(
        _milestone_frame(49),
        "entity_id",
        "name",
        "artist",
        "track",
    )

    assert result.empty

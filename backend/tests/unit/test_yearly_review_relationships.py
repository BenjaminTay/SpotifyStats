from __future__ import annotations

from collections import Counter

import pandas as pd

from backend.domains.yearly_review.relationships import build_relationships
from backend.models.yearly_review import (
    YearlyBillboardCoverage,
    YearlyComparisonCoverage,
    YearlyPlayCoverage,
    YearlyReviewCoverage,
    YearlyTasteCoverage,
)


def _coverage(span: int = 365) -> YearlyReviewCoverage:
    return YearlyReviewCoverage(
        status="complete" if span >= 365 else "insufficient",
        play=YearlyPlayCoverage(status="complete", natural_days_span=span),
        billboard=YearlyBillboardCoverage(status="complete", source_status="complete"),
        comparison=YearlyComparisonCoverage(),
        taste=YearlyTasteCoverage(),
    )


def _frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    track_rows = []
    album_rows = []
    artist_rows = []
    play_id = 1
    for month in range(1, 13):
        for day in (1, 12, 23):
            artist_rows.append(
                {
                    "play_id": play_id,
                    "track_id": month,
                    "artist_name": "Long Artist",
                    "album_name": "Long Album",
                    "ms_played": 180_000,
                    "ts_date": f"2025-{month:02d}-{day:02d}",
                    "ts_month": month,
                }
            )
            play_id += 1
    for index in range(12):
        track_rows.append(
            {
                "play_id": play_id,
                "track_id": 9,
                "canonical_track_id": 9,
                "track_name": "Burst",
                "canonical_track_name": "Burst",
                "artist_name": "Burst Artist",
                "album_name": "Burst Album",
                "ms_played": 180_000,
                "ts_date": f"2025-03-{index + 1:02d}",
                "ts_month": 3,
            }
        )
        play_id += 1
    for index in range(24):
        month = 1 + index % 4
        album_rows.append(
            {
                "play_id": play_id,
                "track_id": 100 + index % 8,
                "album_project_id": 77,
                "album_project_name": "Deep Album",
                "album_name": "Deep Album",
                "artist_name": "Album Artist",
                "ms_played": 180_000,
                "ts_date": f"2025-{month:02d}-{1 + index:02d}",
                "ts_month": month,
            }
        )
        play_id += 1
    return pd.DataFrame(track_rows), pd.DataFrame(album_rows), pd.DataFrame(artist_rows)


def _billboard() -> dict:
    return {
        "honors": {
            "year_end_no1_artist": {
                "artist_name": "Long Artist",
                "year_end_rank": 1,
                "year_end_score": 900,
                "weeks_on_chart": 40,
                "weeks_at_no1": 8,
            },
            "album_era_of_the_year": {
                "album_project_id": 77,
                "album_name": "Deep Album",
                "artist_name": "Album Artist",
                "year_end_rank": 1,
                "year_end_score": 800,
                "weeks_on_chart": 30,
                "weeks_at_no1": 4,
            },
        }
    }


def test_relationships_require_two_metrics_and_apply_entity_role_cap() -> None:
    result = build_relationships(2025, _coverage(), _frames(), _billboard())

    assert {story.relationship_type for story in result} >= {
        "mainline_artist",
        "album_era",
        "short_obsession",
        "deep_album",
    }
    assert all(len(story.metrics) >= 2 for story in result)
    counts = Counter(
        f"{story.entity.entity_type}:{story.entity.entity_id or story.entity.name}"
        for story in result
    )
    assert max(counts.values()) <= 2


def test_short_report_does_not_force_relationship_labels() -> None:
    assert build_relationships(2025, _coverage(45), _frames(), _billboard()) == []


def test_new_relationship_and_return_use_personal_history_dates() -> None:
    track, album, artist = _frames()
    new_rows = []
    return_rows = []
    for index in range(12):
        new_rows.append(
            {
                "play_id": 1000 + index,
                "track_id": 500 + index,
                "artist_name": "New Artist",
                "album_name": "New Album",
                "ms_played": 180_000,
                "ts_date": f"2025-02-{1 + index:02d}",
                "ts_month": 2,
            }
        )
        return_rows.append(
            {
                "play_id": 2000 + index,
                "track_id": 700 + index,
                "artist_name": "Return Artist",
                "album_name": "Return Album",
                "ms_played": 180_000,
                "ts_date": f"2025-08-{1 + index:02d}",
                "ts_month": 8,
            }
        )
    annual_artist = pd.concat([artist, pd.DataFrame(new_rows), pd.DataFrame(return_rows)])
    prior_return = pd.DataFrame(
        [
            {
                "play_id": 2999,
                "track_id": 700,
                "artist_name": "Return Artist",
                "album_name": "Old",
                "ms_played": 180_000,
                "ts_date": "2024-01-01",
                "ts_month": 1,
            }
        ]
    )
    history_artist = pd.concat([annual_artist, prior_return], ignore_index=True)
    result = build_relationships(
        2025,
        _coverage(),
        (track, album, annual_artist),
        _billboard(),
        history_frames=(track, album, history_artist),
    )

    types = {story.relationship_type for story in result}
    assert "new_relationship" in types
    assert "return" in types


def test_relationship_history_parses_dates_once_per_entity_frame(monkeypatch) -> None:
    frames = _frames()
    calls = 0
    real_to_datetime = pd.to_datetime

    def counted_to_datetime(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_to_datetime(*args, **kwargs)

    monkeypatch.setattr(pd, "to_datetime", counted_to_datetime)

    build_relationships(
        2025,
        _coverage(),
        frames,
        _billboard(),
        history_frames=frames,
    )

    # Three annual summaries plus three history date-bound aggregations. This
    # guards against restoring per-entity full-history date parsing.
    assert calls <= 6

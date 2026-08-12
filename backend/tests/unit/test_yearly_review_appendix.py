from __future__ import annotations

from backend.domains.yearly_review.appendix import build_appendix
from backend.domains.yearly_review.epilogue import build_epilogue
from backend.models.yearly_review import (
    YearlyEntityRef,
    YearlyHeadline,
    YearlyMonthSummary,
)


def test_appendix_keeps_complete_indexes_without_new_narrative() -> None:
    play = {
        "charts": {
            "track": {"by_plays": [{"rank": 1}], "by_hours": [{"rank": 1}]},
            "album": {"by_plays": [], "by_hours": []},
            "artist": {"by_plays": [], "by_hours": []},
        }
    }
    billboard = {
        "charts": {"track": [{"year_end_rank": 1}], "album": [], "artist": []},
        "record_catalog_counts": {"total": 9},
    }
    months = [YearlyMonthSummary(month=month) for month in range(1, 13)]
    result = build_appendix(
        play,
        billboard,
        months,
        playback_record_counts={"total": 20},
    )

    assert result.play_charts["track_by_plays"] == [{"rank": 1}]
    assert result.billboard_charts["track"] == [{"year_end_rank": 1}]
    assert len(result.monthly_champions) == 12
    assert result.record_catalog_counts == {"total": 20, "billboard_total": 9}


def test_epilogue_selects_three_distinct_conclusions_and_optional_carryovers() -> None:
    artist = YearlyEntityRef(entity_type="artist", name="Artist")
    headlines = [
        YearlyHeadline(
            headline_id=f"headline-{index}",
            title=f"Headline {index}",
            statement="Evidence-backed.",
            evidence_grade="A",
            entity_refs=[artist] if index < 2 else [],
        )
        for index in range(5)
    ]
    result = build_epilogue(
        headlines,
        new_history_tops=[artist],
        next_year_carryovers=[artist],
    )

    assert len(result.conclusions) == 3
    assert all(item.headline_id.startswith("epilogue_") for item in result.conclusions)
    assert not {item.statement for item in result.conclusions} & {
        item.statement for item in headlines
    }
    assert result.new_history_tops == [artist]
    assert result.next_year_carryovers == [artist]

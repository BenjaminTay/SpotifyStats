from __future__ import annotations

from typing import Any

from backend.domains.yearly_review.honors import build_honors
from backend.models.yearly_review import YearlyBillboardCoverage


def _play_rows(entity: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank in range(1, 13):
        row: dict[str, Any] = {
            "rank": rank,
            "plays": 100 - rank,
            "hours": 10,
            "active_months": 6,
            "share_pct": 5,
        }
        if entity == "track":
            row.update(track_id=rank, track_name=f"Track {rank}", identity_key=f"track:{rank}")
        elif entity == "album":
            row.update(
                album_project_id=rank,
                album_name=f"Album {rank}",
                artist_name="Artist",
                identity_key=f"album-project:{rank}",
            )
        else:
            row.update(artist_name=f"Artist {rank}", identity_key=f"artist:Artist {rank}")
        rows.append(row)
    return rows


def _billboard_rows(entity: str, *, shift: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    order = list(range(1, 13))
    if shift:
        order = [11, *range(1, 11), 12]
    for rank, identity in enumerate(order, start=1):
        row: dict[str, Any] = {
            "year_end_rank": rank,
            "year_end_score": 1000 - rank,
            "peak_position": 1,
            "weeks_on_chart": 20,
            "weeks_at_no1": 2,
        }
        if entity == "track":
            row.update(track_id=identity, track_name=f"Track {identity}")
        elif entity == "album":
            row.update(
                album_project_id=identity,
                album_name=f"Album {identity}",
                artist_name="Artist",
                identity_key=f"album-project:{identity}",
            )
        else:
            row.update(artist_name=f"Artist {identity}")
        rows.append(row)
    return rows


def _payload(
    *, complete: bool = True, shift: bool = False
) -> tuple[dict[str, Any], dict[str, Any]]:
    play = {
        "charts": {
            entity: {"by_plays": _play_rows(entity)} for entity in ("track", "album", "artist")
        }
    }
    billboard = {
        "coverage": YearlyBillboardCoverage(
            status="complete" if complete else "observed_range",
            source_status="complete" if complete else "partial_range",
        ),
        "charts": {
            entity: _billboard_rows(entity, shift=shift) for entity in ("track", "album", "artist")
        },
        "honors": {
            "year_end_no1_track": _billboard_rows("track")[0],
            "year_end_no1_album": _billboard_rows("album")[0],
            "year_end_no1_artist": _billboard_rows("artist")[0],
        },
    }
    return play, billboard


def test_equal_dual_rankings_do_not_create_divergence() -> None:
    result = build_honors(*_payload())

    assert result.divergence_stories == []
    assert set(result.play_leaders) == {"track", "album", "artist"}
    assert set(result.billboard_leaders) == {"track", "album", "artist"}


def test_real_rank_gap_creates_explainable_story_with_project_identity() -> None:
    result = build_honors(*_payload(shift=True))

    assert any(story.entity.entity_type == "track" for story in result.divergence_stories)
    album_entities = [item.entity.entity_id for item in result.annual_honors if item.entity]
    assert len(album_entities) == len(
        set((item.honor_id, item.entity.entity_id) for item in result.annual_honors)
    )


def test_incomplete_billboard_downgrades_champion_wording() -> None:
    result = build_honors(*_payload(complete=False))

    assert all("阶段领先" in item.title for item in result.billboard_leaders.values())

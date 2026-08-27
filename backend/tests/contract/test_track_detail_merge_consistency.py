"""Track detail endpoints must consume the same L2/L3 grouping as charts."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


PARAMS = {
    "min_ms": 30_000,
    "music_only": True,
    "merge_enabled": True,
    "dynamic_threshold": False,
    "period": "lifetime",
    "merge_level": 2,
}


def test_recording_group_detail_matches_l2_chart_for_every_member(client) -> None:
    chart_response = client.get(
        "/api/analysis/charts",
        params={**PARAMS, "entity": "track", "metric": "plays", "limit": 5000},
    )
    assert chart_response.status_code == 200
    chart_row = next(row for row in chart_response.json()["rows"] if int(row["track_id"]) == 905)

    for member_id in (905, 906):
        stats_response = client.get(
            f"/api/music/tracks/{member_id}/stats",
            params={**PARAMS, "include_rank_context": False},
        )
        plays_response = client.get(
            f"/api/music/tracks/{member_id}/plays",
            params={**PARAMS, "limit": 200},
        )
        dates_response = client.get(
            f"/api/music/tracks/{member_id}/play-dates",
            params=PARAMS,
        )

        assert stats_response.status_code == 200
        assert plays_response.status_code == 200
        assert dates_response.status_code == 200
        stats = stats_response.json()
        plays = plays_response.json()
        dates = dates_response.json()
        assert stats["entity"]["track_id"] == 905
        assert stats["summary"]["total_plays"] == chart_row["plays"]
        assert plays["total"] == chart_row["plays"]
        assert sum(row["count"] for row in dates) == chart_row["plays"]


def test_composition_group_expands_only_at_l3(client) -> None:
    l2 = client.get(
        "/api/music/tracks/925/stats",
        params={**PARAMS, "merge_level": 2, "include_rank_context": False},
    ).json()
    l3 = client.get(
        "/api/music/tracks/925/stats",
        params={**PARAMS, "merge_level": 3, "include_rank_context": False},
    ).json()
    chart = client.get(
        "/api/analysis/charts",
        params={
            **PARAMS,
            "merge_level": 3,
            "entity": "track",
            "metric": "plays",
            "limit": 5000,
        },
    ).json()
    chart_row = next(row for row in chart["rows"] if int(row["track_id"]) == 920)

    assert l2["entity"]["track_id"] == 925
    assert l3["entity"]["track_id"] == 920
    assert l2["summary"]["total_plays"] < l3["summary"]["total_plays"]
    assert l3["summary"]["total_plays"] == chart_row["plays"]


@pytest.mark.parametrize("suffix", ["stats", "plays", "play-dates"])
def test_track_detail_endpoints_reject_removed_l1_level(client, suffix: str) -> None:
    response = client.get(f"/api/music/tracks/905/{suffix}", params={"merge_level": 1})
    assert response.status_code == 422

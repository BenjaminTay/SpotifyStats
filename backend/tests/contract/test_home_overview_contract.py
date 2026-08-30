from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_home_overview_response_uses_complete_filter_context(client):
    response = client.get(
        "/api/home/overview",
        params={
            "min_ms": 30_000,
            "music_only": "true",
            "merge_enabled": "true",
            "dynamic_threshold": "true",
            "merge_level": 2,
            "include_compilations": "false",
            "bb_top_n": 30,
            "bb_album_top_n": 20,
            "bb_artist_top_n": 20,
            "bb_week_start_dow": 4,
            "bb_week_start_hour": 0,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["schema_version"] == "home_overview_v2"
    assert payload["filter_fingerprint"]
    assert payload["state"] in {"ready", "limited", "empty"}
    assert isinstance(payload["rediscovery_candidates"], list)
    coverage = payload["coverage"]
    assert "source_latest_date" in coverage
    assert "latest_effective_play_date" in coverage
    if payload["state"] != "empty":
        assert payload["recent"]["period"]["end_date"] == coverage["latest_effective_play_date"]
        assert payload["billboard"]["state"] in {"ready", "unavailable"}
        for entity in ("track", "album", "artist"):
            champion = payload["billboard"][entity]
            if champion is not None:
                assert champion["movement"] in {"new", "re", "up", "down", "same"}
        assert payload["yearly_review"]["state"] in {
            "ready",
            "not_generated",
            "unavailable",
        }

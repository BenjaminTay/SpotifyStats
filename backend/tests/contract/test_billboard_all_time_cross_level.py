import pytest

pytestmark = pytest.mark.contract


def test_all_time_contract_exposes_cross_level_power_metrics(client):
    response = client.get(
        "/api/billboard/all-time",
        params={
            "merge_level": 2,
            "dynamic_threshold": "true",
            "include_compilations": "false",
            "bb_top_n": 30,
            "bb_album_top_n": 20,
            "bb_artist_top_n": 20,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["album_power_scores"]
    assert payload["artist_power_scores"]
    assert {"track_power_sum", "track_power_rank"} <= payload["album_power_scores"][0].keys()
    assert {
        "track_power_sum",
        "track_power_rank",
        "album_power_sum",
        "album_power_rank",
    } <= payload["artist_power_scores"][0].keys()


def test_power_and_summary_endpoints_forward_compilation_context(client, monkeypatch):
    import backend.api.billboard.data as api_data

    captured = []

    def fake_power(**kwargs):
        captured.append(("power", kwargs))
        return {"power_scores": [], "album_power_scores": [], "artist_power_scores": []}

    def fake_summaries(**kwargs):
        captured.append(("summaries", kwargs))
        return {
            "track_summary": [],
            "artist_summary": [],
            "album_track_counts": [],
            "artist_track_counts": [],
        }

    monkeypatch.setattr(api_data, "compute_power_scores_staged", fake_power)
    monkeypatch.setattr(api_data, "compute_summaries_staged", fake_summaries)

    assert (
        client.get(
            "/api/billboard/power-scores",
            params={
                "merge_level": 3,
                "merge_enabled": "false",
                "include_compilations": "true",
            },
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/billboard/summaries",
            params={
                "merge_level": 3,
                "merge_enabled": "false",
                "include_compilations": "true",
            },
        ).status_code
        == 200
    )

    assert [name for name, _ in captured] == ["power", "summaries"]
    assert all(kwargs["merge_level"] == 3 for _, kwargs in captured)
    assert all(kwargs["merge_enabled"] is False for _, kwargs in captured)
    assert all(kwargs["include_compilations"] is True for _, kwargs in captured)


def test_records_endpoint_forwards_merge_and_compilation_context(client, monkeypatch):
    import backend.api.billboard.data as api_data

    captured = {}

    def fake_records(**kwargs):
        captured.update(kwargs)
        return {"records": {}}

    monkeypatch.setattr(api_data, "compute_records_staged", fake_records)
    response = client.get(
        "/api/billboard/records",
        params={
            "merge_level": 1,
            "merge_enabled": "false",
            "include_compilations": "true",
        },
    )

    assert response.status_code == 200, response.text
    assert captured["merge_level"] == 1
    assert captured["merge_enabled"] is False
    assert captured["include_compilations"] is True

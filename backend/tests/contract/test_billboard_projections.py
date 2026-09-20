"""Public projections preserve published facts and cannot build or write."""

from __future__ import annotations

import pytest

from backend.api.billboard import projections as p
from backend.domains.billboard import persistent_cache as cache
from backend.services import billboard_snapshot_service as maintenance
from backend.tests.contract.test_public_snapshot_boundary import (
    PUBLIC,
    _sentinels,
    _state,
)
from backend.tests.contract.test_public_snapshot_boundary import (
    isolated as _isolated,
)

isolated = _isolated

pytestmark = pytest.mark.contract
ENDPOINTS = [
    "/api/billboard/records?projection=page",
    "/api/billboard/weekly?projection=page",
    "/api/billboard/all-time?projection=entity",
    "/api/billboard/all-time?projection=number-ones",
]


def test_projection_exact_lkg_and_readonly(isolated, monkeypatch):
    client, db_path, files = isolated
    maintenance.rebuild_default_billboard_snapshots()
    old = {
        name: client.get("/api/billboard/" + name, headers=PUBLIC).json()
        for name in ("data", "records", "weekly", "all-time", "summaries")
    }
    _sentinels(monkeypatch)
    before = _state(db_path, files)
    for entity in p.WEEKLY:
        for week in old["weekly"]["meta"]["all_weeks_desc"]:
            r = client.get(
                "/api/billboard/weekly",
                params={"projection": "page", "entity": entity, "week": week},
                headers=PUBLIC,
            )
            assert r.status_code == 200
            v = r.json()
            assert v["current"] == sorted(
                [x for x in old["weekly"][p.WEEKLY[entity]] if x["billboard_week"] == week],
                key=lambda r: r["rank"],
            )
        r = client.get(
            "/api/billboard/all-time",
            params={"projection": "entity", "entity": entity},
            headers=PUBLIC,
        )
        assert r.status_code == 200
        assert len(r.json()["rows"]) == len(old["all-time"][p.POWER[entity]])
    r = client.get(ENDPOINTS[0], headers=PUBLIC).json()
    assert r["records"] == old["data"]["records"]
    assert "weekly" not in r and "track_summary" not in r and "artist_summary" not in r
    assert r["snapshot"] == old["records"]["snapshot"]
    champions = client.get(ENDPOINTS[3], headers=PUBLIC).json()
    for field in p.WEEKLY.values():
        assert champions[field] == [r for r in old["all-time"][field] if r["rank"] == 1]
    original = cache.build_cache_context

    def stale(family, params):
        return {
            **original(family, params),
            "source_revision": "next",
            "cache_key": "missing-" + family,
        }

    monkeypatch.setattr(cache, "build_cache_context", stale)
    for url in ENDPOINTS:
        r = client.get(url, headers=PUBLIC)
        assert r.status_code == 200, r.text
        assert r.json()["snapshot"]["freshness"] == "last_known_good"
        assert r.json()["snapshot"]["target_revision"] == "next"
        assert client.get(url + "&bb_top_n=31", headers=PUBLIC).status_code == 503
    assert _state(db_path, files) == before


@pytest.mark.parametrize("broken", [False, True])
def test_missing_or_key_error_fails_without_side_effects(isolated, monkeypatch, broken):
    client, db_path, files = isolated
    _sentinels(monkeypatch)
    if broken:

        def fail(*args):
            raise ValueError("revision unavailable")

        monkeypatch.setattr(cache, "build_cache_context", fail)
    before = _state(db_path, files)
    for url in ENDPOINTS:
        assert client.get(url, headers=PUBLIC).status_code == 503
    assert _state(db_path, files) == before


def test_records_mixed_generation_is_unavailable(isolated, monkeypatch):
    client, db_path, files = isolated
    maintenance.rebuild_default_billboard_snapshots()
    original = cache.load_persisted_snapshot

    def mixed(context, **kwargs):
        payload = original(context, **kwargs)
        if context["family"] == "summaries":
            payload["snapshot"]["source_revision"] = "older"
        return payload

    monkeypatch.setattr(cache, "load_persisted_snapshot", mixed)
    _sentinels(monkeypatch)
    before = _state(db_path, files)
    assert client.get(ENDPOINTS[0], headers=PUBLIC).status_code == 503
    assert _state(db_path, files) == before


@pytest.mark.parametrize(
    "path",
    [
        "/api/billboard/weekly?projection=page&entity=invalid",
        "/api/billboard/all-time?projection=entity&entity=invalid",
        "/api/billboard/all-time?projection=invalid",
        "/api/billboard/records?projection=invalid",
        "/api/billboard/weekly?projection=invalid",
    ],
)
def test_projection_parameter_allowlists(isolated, monkeypatch, path):
    client, _, _ = isolated
    _sentinels(monkeypatch)
    assert client.get(path, headers=PUBLIC).status_code == 422

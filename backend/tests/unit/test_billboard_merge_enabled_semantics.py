from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_merge_disabled_never_reads_merge_enabled_preaggregation(monkeypatch):
    from backend.domains.billboard import data_loader

    monkeypatch.setattr(
        data_loader,
        "get_db",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("merge-disabled path must not inspect aggregate state")
        ),
    )

    assert data_loader._try_load_from_agg(30_000, True, 4, 0, merge_enabled=False) == (
        None,
        None,
        None,
    )


def test_load_rank_cache_separates_merge_enabled_variants(monkeypatch):
    from backend.domains.billboard import chart_load_rank

    calls: list[bool] = []

    def fake_uncached(*args):
        merge_enabled = bool(args[-1])
        calls.append(merge_enabled)
        return merge_enabled

    monkeypatch.setattr(chart_load_rank, "_load_and_rank_uncached", fake_uncached)
    chart_load_rank._load_and_rank_cached_by_revision.cache_clear()
    base = (30_000, True, 30, 20, 20, 4, 0, None, None, 2, True, 5, False)
    revision = (1, 1, 1, 1, "ready:ready")

    assert chart_load_rank._load_and_rank_cached_by_revision(*base, False, revision) is False
    assert chart_load_rank._load_and_rank_cached_by_revision(*base, True, revision) is True
    assert chart_load_rank._load_and_rank_cached_by_revision(*base, False, revision) is False
    assert calls == [False, True]


def test_latest_snapshot_key_separates_merge_enabled_variants():
    from backend.domains.billboard.latest_snapshot_cache import snapshot_key

    assert snapshot_key(merge_enabled=False) != snapshot_key(merge_enabled=True)


def test_staged_weekly_forwards_merge_enabled_into_revision_key(monkeypatch):
    from backend.domains.billboard import chart_staged_api

    captured: dict[str, object] = {}

    def fake_call(cached_fn, args):
        captured["cached_fn"] = cached_fn
        captured["args"] = args
        return {"ok": True}

    monkeypatch.setattr(chart_staged_api, "call_with_billboard_revision_cache", fake_call)

    assert chart_staged_api.compute_weekly_data(merge_enabled=False) == {"ok": True}
    assert captured["args"][-1] is False


def test_search_chart_lookup_forwards_complete_nondefault_context(monkeypatch):
    from backend.services import music_search_service

    captured: dict[str, object] = {}

    def fake_compute(**kwargs):
        captured.update(kwargs)
        return {
            "weekly": [],
            "weekly_album": [],
            "weekly_artist": [],
            "power_scores": [],
            "album_power_scores": [],
            "artist_power_scores": [],
        }

    monkeypatch.setattr(music_search_service, "compute_billboard_data", fake_compute)

    music_search_service._build_chart_lookup(
        min_ms=45_000,
        music_only=False,
        bb_top_n=41,
        bb_album_top_n=31,
        bb_artist_top_n=21,
        bb_week_start_dow=2,
        bb_week_start_hour=12,
        year_start=2024,
        year_end=2025,
        merge_level=3,
        dynamic_threshold=False,
        max_merge_gap_minutes=17,
        merge_enabled=False,
        include_compilations=True,
    )

    assert captured == {
        "min_ms": 45_000,
        "music_only": False,
        "bb_top_n": 41,
        "bb_album_top_n": 31,
        "bb_artist_top_n": 21,
        "bb_week_start_dow": 2,
        "bb_week_start_hour": 12,
        "year_start": 2024,
        "year_end": 2025,
        "merge_level": 3,
        "dynamic_threshold": False,
        "max_merge_gap_minutes": 17,
        "merge_enabled": False,
        "include_compilations": True,
    }

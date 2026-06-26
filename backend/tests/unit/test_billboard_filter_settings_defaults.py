from __future__ import annotations

from backend import dependencies


def test_billboard_filters_use_saved_settings_when_query_params_are_omitted(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "_load_filter_settings",
        lambda: {
            "min_ms": 45000,
            "music_only": False,
            "bb_top_n": 15,
            "bb_album_top_n": 10,
            "bb_artist_top_n": 25,
            "bb_week_start_dow": 2,
            "bb_week_start_hour": 8,
        },
        raising=False,
    )

    filters = dependencies.BillboardFilters(
        min_ms=None,
        music_only=None,
        bb_top_n=None,
        bb_album_top_n=None,
        bb_artist_top_n=None,
        bb_week_start_dow=None,
        bb_week_start_hour=None,
    )

    assert filters.min_ms == 45000
    assert filters.music_only is False
    assert filters.bb_top_n == 15
    assert filters.bb_album_top_n == 10
    assert filters.bb_artist_top_n == 25
    assert filters.bb_week_start_dow == 2
    assert filters.bb_week_start_hour == 8


def test_billboard_filters_keep_explicit_query_params_over_saved_settings(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "_load_filter_settings",
        lambda: {
            "min_ms": 45000,
            "music_only": False,
            "bb_top_n": 15,
            "bb_album_top_n": 10,
            "bb_artist_top_n": 25,
            "bb_week_start_dow": 2,
            "bb_week_start_hour": 8,
        },
        raising=False,
    )

    filters = dependencies.BillboardFilters(
        min_ms=30000,
        music_only=True,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
    )

    assert filters.min_ms == 30000
    assert filters.music_only is True
    assert filters.bb_top_n == 30
    assert filters.bb_album_top_n == 20
    assert filters.bb_artist_top_n == 20
    assert filters.bb_week_start_dow == 4
    assert filters.bb_week_start_hour == 0

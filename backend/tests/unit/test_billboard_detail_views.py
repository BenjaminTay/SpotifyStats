import pytest

from backend.domains.billboard import detail_views
from backend.domains.billboard.detail_views import (
    get_album_detail_view,
    get_track_detail_view,
    select_album_detail_view,
    select_artist_detail_view,
    select_track_detail_view,
)


def test_track_summary_view_prefers_published_summary_without_full_build(monkeypatch):
    published = {
        "found": True,
        "track_name": "Song",
        "summary": {"peak_position": 1, "weeks_on_chart": 8},
        "history": [],
        "chart_data": {},
    }
    monkeypatch.setattr(detail_views, "build_track_detail_summary", lambda _args: published)
    monkeypatch.setattr(detail_views, "build_published_detail", lambda _args, **_kwargs: published)
    monkeypatch.setattr(
        detail_views,
        "get_track_history",
        lambda *_args, **_kwargs: pytest.fail("exact published summary should avoid full build"),
    )

    result = get_track_detail_view(
        7,
        30_000,
        True,
        30,
        20,
        20,
        4,
        12,
        None,
        None,
        True,
        5,
        True,
        2,
        False,
        view="summary",
    )

    assert result["summary"] == published["summary"]
    assert result["history"] == []
    assert result["chart_data"] == {}


def test_summary_missing_publication_never_falls_back(monkeypatch):
    from fastapi import HTTPException

    from backend.core.access_surface import snapshot_unavailable

    monkeypatch.setattr(
        detail_views,
        "build_published_detail",
        lambda *_a, **_kw: (_ for _ in ()).throw(snapshot_unavailable("music_detail")),
    )
    monkeypatch.setattr(
        detail_views,
        "get_track_history",
        lambda *_a, **_kw: pytest.fail("full fallback is forbidden"),
    )
    with pytest.raises(HTTPException) as error:
        get_track_detail_view(7, view="summary")
    assert error.value.status_code == 503
    assert error.value.detail["error"] == "snapshot_unavailable"


def test_track_agent_view_keeps_published_weekly_facts(monkeypatch):
    published = {
        "found": True,
        "track_name": "Song",
        "summary": {"peak_position": 1, "weeks_on_chart": 1},
        "history": [{"week": "2026-01-01", "rank": 1}],
        "chart_data": {"x": ["2026-01-01"], "y": [1]},
    }
    monkeypatch.setattr(detail_views, "build_track_detail_summary", lambda _args: published)
    monkeypatch.setattr(detail_views, "build_published_detail", lambda _args, **_kwargs: published)
    monkeypatch.setattr(
        detail_views,
        "get_track_history",
        lambda *_args, **_kwargs: pytest.fail("published agent evidence should avoid full build"),
    )

    result = get_track_detail_view(
        7,
        30_000,
        True,
        30,
        20,
        20,
        4,
        12,
        None,
        None,
        True,
        5,
        True,
        2,
        False,
        view="agent",
    )

    assert result is published


def test_album_project_view_reads_target_publication(monkeypatch):
    project = {
        "album_project_id": 7,
        "play_count": 3,
        "transferred_tracks": [{"canonical_song_name": "Song"}],
    }
    published = {"found": True, "effective_play_count": 3, "album_project": project}
    monkeypatch.setattr(detail_views, "build_published_detail", lambda *_a, **_kw: published)
    for function in (
        "_load_album_project_detail_events",
        "_get_album_project_payload",
        "get_album_chart_detail",
    ):
        monkeypatch.setattr(
            detail_views, function, lambda *_a, **_kw: pytest.fail("legacy computation forbidden")
        )
    assert get_album_detail_view("Album", "Artist", view="project") == published


def test_track_summary_view_keeps_every_scalar_fact_unchanged():
    full = {
        "found": True,
        "chart_status": "charted",
        "effective_play_count": 12,
        "track_id": 7,
        "l1_id": 7,
        "representative_track_id": 70,
        "track_name": "Song",
        "artist_name": "Artist",
        "artist_names": ["Artist", "Guest"],
        "primary_artist_name": "Artist",
        "cover_url": "/cover.jpg",
        "meta": {"duration_ms": 123},
        "summary": {"peak_position": 1},
        "history": [{"week": "2026-01-01", "rank": 1}],
        "chart_data": {"x": ["2026-01-01"], "y": [1]},
    }

    summary = select_track_detail_view(full, "summary")

    for key in full.keys() - {"history", "chart_data"}:
        assert summary[key] == full[key]
    assert summary["history"] == []
    assert summary["chart_data"] == {}
    assert select_track_detail_view(full, "full") is full


def test_album_views_are_lossless_partitions_of_the_full_payload():
    full = {
        "found": True,
        "chart_status": "charted",
        "track_chart_status": "charted",
        "effective_play_count": 20,
        "album_name": "Album",
        "artist_name": "Artist",
        "cover_url": "/album.jpg",
        "meta": {"release_date": "2026-01-01", "release_group": {"versions": [1, 2]}},
        "info": {"total_tracks": 2},
        "chart_summary": {"peak_position": 1},
        "album_project": {"play_count": 20},
        "album_weekly_history": [{"week": "2026-01-01", "rank": 1}],
        "album_no1_by_week": [{"week": "2026-01-01"}],
        "best_singles_overlay": [{"week": "2026-01-01", "rank": 1}],
        "tracks": [{"track_id": 1}, {"track_id": 2}],
    }

    summary = select_album_detail_view(full, "summary")
    overview = select_album_detail_view(full, "overview")
    tracks = select_album_detail_view(full, "tracks")
    project = select_album_detail_view(full, "project")

    assert summary["meta"] == {"release_date": "2026-01-01"}
    assert overview["album_weekly_history"] == full["album_weekly_history"]
    assert overview["album_no1_by_week"] == full["album_no1_by_week"]
    assert overview["best_singles_overlay"] == full["best_singles_overlay"]
    assert tracks["tracks"] == full["tracks"]
    assert project["album_project"] == full["album_project"]
    assert project["meta"] == full["meta"]
    assert select_album_detail_view(full, "full") is full


def test_artist_views_preserve_order_and_pages_recombine_exactly():
    full = {
        "found": True,
        "chart_status": "charted",
        "track_chart_status": "charted",
        "album_chart_status": "charted",
        "effective_play_count": 30,
        "artist_name": "Artist",
        "cover_url": "/artist.jpg",
        "meta": {"genres": ["pop"]},
        "info": {"total_tracks": 5},
        "chart_summary": {"peak_position": 1},
        "artist_weekly_history": [{"week": "2026-01-01"}],
        "artist_no1_by_week": [{"week": "2026-01-01"}],
        "week_no1_albums": [{"week": "2026-01-01"}],
        "best_singles_overlay": [{"track_name": "Song"}],
        "best_albums_overlay": [{"album_name": "Album"}],
        "tracks": [{"track_id": index, "total_chart_plays": 100 - index} for index in range(1, 8)],
        "albums": [{"album_name": "Album"}],
    }

    summary = select_artist_detail_view(full, "summary")
    overview = select_artist_detail_view(full, "overview")
    albums = select_artist_detail_view(full, "albums")
    pages = [
        select_artist_detail_view(full, "tracks", limit=3, offset=offset) for offset in (0, 3, 6)
    ]

    assert summary["tracks"] == []
    assert summary["albums"] == []
    assert overview["artist_weekly_history"] == full["artist_weekly_history"]
    assert overview["best_singles_overlay"] == full["best_singles_overlay"]
    assert overview["best_albums_overlay"] == full["best_albums_overlay"]
    assert albums["albums"] == full["albums"]
    assert [row for page in pages for row in page["tracks"]] == full["tracks"]
    assert all(page["tracks_total"] == len(full["tracks"]) for page in pages)
    assert all(page["tracks_max_chart_plays"] == 99 for page in pages)
    assert select_artist_detail_view(full, "full") is full


def test_album_metadata_policy_invalidates_full_detail_process_cache(monkeypatch):
    from types import SimpleNamespace

    from backend.domains.billboard import detail_views

    monkeypatch.setattr(detail_views, "get_db", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(
        detail_views,
        "get_music_search_revision_state",
        lambda _: SimpleNamespace(
            playback_revision=1, billboard_revision=1, metadata_revision=1, settings_revision=1
        ),
    )
    monkeypatch.setattr(detail_views, "get_identity_revision", lambda _: 1)
    monkeypatch.setattr(detail_views, "get_track_credit_revision", lambda _: 1)
    monkeypatch.setattr(detail_views, "billboard_revision_state", lambda: ())
    calls = []
    monkeypatch.setattr(
        detail_views,
        "get_album_chart_detail",
        lambda *_: (
            calls.append(1)
            or {"meta": {"label": "Old Label" if len(calls) == 1 else "Correct Label"}}
        ),
    )
    detail_views._album_detail_cached.cache_clear()
    try:
        monkeypatch.setattr(detail_views, "ALBUM_DETAIL_META_POLICY_VERSION", "old_rule")
        old_revision = detail_views.detail_revision_state()
        assert (
            detail_views._album_detail_cached(("fixture",), old_revision)["meta"]["label"]
            == "Old Label"
        )
        monkeypatch.setattr(
            detail_views, "ALBUM_DETAIL_META_POLICY_VERSION", "source_precision_rule"
        )
        assert detail_views.detail_revision_state() != old_revision
        assert (
            detail_views._album_detail_cached(("fixture",), detail_views.detail_revision_state())[
                "meta"
            ]["label"]
            == "Correct Label"
        )
        assert len(calls) == 2
    finally:
        detail_views._album_detail_cached.cache_clear()

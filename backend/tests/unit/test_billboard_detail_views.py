from backend.domains.billboard.detail_views import (
    select_album_detail_view,
    select_artist_detail_view,
    select_track_detail_view,
)


def test_track_summary_view_keeps_every_scalar_fact_unchanged():
    full = {
        "found": True,
        "chart_status": "charted",
        "effective_play_count": 12,
        "track_id": 7,
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

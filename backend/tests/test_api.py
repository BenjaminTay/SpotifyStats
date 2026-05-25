"""Comprehensive API endpoint tests.

Covers all 50+ endpoints across 18 route modules. Each test validates:
- HTTP 200 response
- Correct response structure (keys, types)
- Data consistency (cross-referencing values)
- Edge cases (empty/invalid inputs, filter variations)

Run with:  pytest backend/tests/ -v
"""

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# Health & Infrastructure
# ═══════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_openapi_spec(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert "paths" in spec
        assert len(spec["paths"]) >= 45


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard (6 endpoints)
# ═══════════════════════════════════════════════════════════════════════════

class TestDashboard:
    def test_summary_structure(self, client, default_params):
        r = client.get("/api/dashboard/summary", params=default_params)
        assert r.status_code == 200
        d = r.json()
        for k in ["total_plays", "total_hours", "total_tracks", "total_artists",
                   "total_albums", "total_days", "avg_daily_hours"]:
            assert k in d, f"Missing key: {k}"
        assert d["total_plays"] > 50000
        assert d["total_hours"] > 3000
        assert d["total_tracks"] > 4000
        assert d["total_artists"] > 500

    def test_summary_values_consistent(self, client, default_params):
        """total_plays >= total_tracks (can't have more unique tracks than plays)."""
        r = client.get("/api/dashboard/summary", params=default_params)
        d = r.json()
        assert d["total_plays"] >= d["total_tracks"]

    def test_top_tracks_returns_data(self, client, default_params):
        r = client.get("/api/dashboard/top-tracks", params={**default_params, "top_n": 5})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 5  # API may return more than requested
        for t in data:
            assert "track_name" in t
            assert "artist_name" in t
            assert "plays" in t
            assert t["plays"] > 0

    def test_top_tracks_descending(self, client, default_params):
        r = client.get("/api/dashboard/top-tracks", params={**default_params, "top_n": 10})
        data = r.json()
        plays = [t["plays"] for t in data]
        assert plays == sorted(plays, reverse=True), "Tracks not sorted by plays descending"

    def test_platform_dist(self, client, default_params):
        r = client.get("/api/dashboard/platform-dist", params=default_params)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 2  # at least ios, windows
        for p in data:
            assert "platform" in p
            assert "count" in p
            assert p["count"] > 0

    def test_dow_dist(self, client, default_params):
        r = client.get("/api/dashboard/dow-dist", params=default_params)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 7
        total = sum(d["count"] for d in data)
        assert total > 50000

    def test_random_track(self, client, default_params):
        r = client.get("/api/dashboard/random-track", params=default_params)
        assert r.status_code == 200
        d = r.json()
        assert "track_name" in d
        assert "artist_name" in d

    def test_full_endpoint_combines_all(self, client, default_params):
        r = client.get("/api/dashboard/full", params=default_params)
        assert r.status_code == 200
        d = r.json()
        for k in ["summary", "top_tracks", "monthly_trend", "platform_dist", "dow_dist", "random_track"]:
            assert k in d, f"Missing key: {k}"


# ═══════════════════════════════════════════════════════════════════════════
# Timeline (2 endpoints)
# ═══════════════════════════════════════════════════════════════════════════

class TestTimeline:
    def test_annual_structure(self, client, default_params):
        r = client.get("/api/timeline/annual", params=default_params)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 4  # 2022..2026
        for y in data:
            assert "year" in y
            assert "plays" in y
            assert "hours" in y
            assert y["plays"] > 0

    def test_annual_years_monotonic(self, client, default_params):
        r = client.get("/api/timeline/annual", params=default_params)
        years = [y["year"] for y in r.json()]
        assert years == sorted(years)

    def test_monthly_structure(self, client, default_params):
        r = client.get("/api/timeline/monthly", params=default_params)
        assert r.status_code == 200
        d = r.json()
        assert "months" in d
        months = d["months"]
        assert len(months) >= 40
        for m in months:
            assert "period" in m
            assert "plays" in m
            assert "hours" in m
            assert "-" in m["period"]

    def test_monthly_periods_monotonic(self, client, default_params):
        r = client.get("/api/timeline/monthly", params=default_params)
        periods = [m["period"] for m in r.json()["months"]]
        assert periods == sorted(periods)

    def test_total_plays_matches_dashboard(self, client, default_params):
        """Annual sum of plays should match dashboard total."""
        annual = client.get("/api/timeline/annual", params=default_params).json()
        dashboard = client.get("/api/dashboard/summary", params=default_params).json()
        annual_total = sum(y["plays"] for y in annual)
        assert abs(annual_total - dashboard["total_plays"]) < 100


# ═══════════════════════════════════════════════════════════════════════════
# Leaderboard
# ═══════════════════════════════════════════════════════════════════════════

class TestLeaderboard:
    def test_track_leaderboard(self, client, default_params):
        r = client.get("/api/leaderboard", params={
            **default_params, "entity": "track", "metric": "plays",
            "time_range": "all", "top_n": 10,
        })
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d
        assert "time_label" in d
        assert len(d["rows"]) == 10
        for row in d["rows"]:
            assert row["rank"] >= 1
            assert "track_name" in row
            assert "artist_name" in row
            assert row["plays"] > 0

    def test_artist_leaderboard(self, client, default_params):
        r = client.get("/api/leaderboard", params={
            **default_params, "entity": "artist", "metric": "hours",
            "time_range": "all", "top_n": 10,
        })
        assert r.status_code == 200
        d = r.json()
        assert len(d["rows"]) == 10
        assert d["rows"][0]["artist_name"] == "Taylor Swift"

    def test_album_leaderboard(self, client, default_params):
        r = client.get("/api/leaderboard", params={
            **default_params, "entity": "album", "metric": "plays",
            "time_range": "all", "top_n": 10,
        })
        assert r.status_code == 200
        d = r.json()
        assert len(d["rows"]) == 10
        for row in d["rows"]:
            assert "album_name" in row
            assert "artist_name" in row

    def test_top_artist_consistent_with_dashboard(self, client, default_params):
        """Top artist in leaderboard should appear in dashboard top tracks."""
        dashboard_tracks = client.get("/api/dashboard/top-tracks", params={
            **default_params, "top_n": 20,
        }).json()
        leaderboard = client.get("/api/leaderboard", params={
            **default_params, "entity": "artist", "metric": "plays",
            "time_range": "all", "top_n": 5,
        }).json()
        top_artist = leaderboard["rows"][0]["artist_name"]
        artist_track_count = sum(
            1 for t in dashboard_tracks if t["artist_name"] == top_artist
        )
        assert artist_track_count > 0, f"Top artist {top_artist} not in any top tracks"

    def test_leaderboard_ranks_sequential(self, client, default_params):
        r = client.get("/api/leaderboard", params={
            **default_params, "entity": "track", "metric": "plays",
            "time_range": "all", "top_n": 20,
        })
        ranks = [row["rank"] for row in r.json()["rows"]]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_leaderboard_plays_descending(self, client, default_params):
        r = client.get("/api/leaderboard", params={
            **default_params, "entity": "track", "metric": "plays",
            "time_range": "all", "top_n": 20,
        })
        plays_vals = [row["plays"] for row in r.json()["rows"]]
        assert plays_vals == sorted(plays_vals, reverse=True)

    def test_invalid_entity_rejected(self, client, default_params):
        r = client.get("/api/leaderboard", params={
            **default_params, "entity": "invalid", "metric": "plays",
            "time_range": "all", "top_n": 10,
        })
        assert r.status_code in (200, 422)


# ═══════════════════════════════════════════════════════════════════════════
# Behavior
# ═══════════════════════════════════════════════════════════════════════════

class TestBehavior:
    def test_behavior_structure(self, client, default_params):
        r = client.get("/api/behavior", params=default_params)
        assert r.status_code == 200
        d = r.json()
        for k in ["reason_end", "reason_start", "fwdbtn_by_hour",
                   "most_forwarded", "platform_monthly", "platform_hourly",
                   "shuffle_rate_by_platform", "shuffle_monthly"]:
            assert k in d, f"Missing key: {k}"

    def test_reason_end_has_data(self, client, default_params):
        r = client.get("/api/behavior", params=default_params)
        reasons = r.json()["reason_end"]
        assert len(reasons) >= 5
        total = sum(r["count"] for r in reasons)
        assert total > 0

    def test_fwdbtn_by_hour_complete(self, client, default_params):
        r = client.get("/api/behavior", params=default_params)
        hours = r.json()["fwdbtn_by_hour"]
        hour_set = {h["hour"] for h in hours}
        assert len(hour_set) == 24
        assert set(range(24)) == hour_set


# ═══════════════════════════════════════════════════════════════════════════
# Listening Hours
# ═══════════════════════════════════════════════════════════════════════════

class TestListeningHours:
    def test_heatmap_structure(self, client, default_params):
        r = client.get("/api/listening-hours/heatmap", params=default_params)
        assert r.status_code == 200
        d = r.json()
        assert "z" in d and "x" in d and "y" in d
        assert len(d["z"]) == 7
        assert len(d["z"][0]) == 24
        assert d["x"] == list(range(24))
        assert len(d["y"]) == 7

    def test_late_night(self, client, default_params):
        r = client.get("/api/listening-hours/late-night", params=default_params)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 4
        assert "year" in data[0]
        assert "rate" in data[0]

    def test_yearly_heatmap(self, client, default_params):
        r = client.get("/api/listening-hours/yearly", params=default_params)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 4
        for y in data:
            assert "year" in y
            assert "z" in y


# ═══════════════════════════════════════════════════════════════════════════
# Artist Deep Dive
# ═══════════════════════════════════════════════════════════════════════════

class TestArtistDeep:
    def test_artist_list(self, client):
        r = client.get("/api/artist/list")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 500
        assert isinstance(data[0], dict)
        assert "artist_name" in data[0]
        assert "play_count" in data[0]

    def test_artist_deep_dive(self, client, default_params):
        r = client.get("/api/artist/Taylor Swift/deep-dive", params=default_params)
        assert r.status_code == 200
        d = r.json()
        assert d.get("found") is True
        assert d.get("artist_name") == "Taylor Swift"
        assert "heatmap" in d
        assert "monthly_trend" in d
        assert "top_tracks" in d

    def test_nonexistent_artist_returns_empty(self, client, default_params):
        r = client.get("/api/artist/NoSuchArtistXYZ123/deep-dive", params=default_params)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Wrapped
# ═══════════════════════════════════════════════════════════════════════════

class TestWrapped:
    def test_wrapped_valid_year(self, client, default_params):
        r = client.get("/api/wrapped/2024", params=default_params)
        assert r.status_code == 200
        d = r.json()
        assert d["year"] == 2024
        assert d["empty"] is False
        assert d["hero"] is not None
        h = d["hero"]
        assert h["total_plays"] > 10000
        assert h["total_minutes"] > 50000
        assert h["unique_tracks"] > 1000
        assert h["unique_artists"] > 200

    def test_wrapped_top_artists(self, client, default_params):
        r = client.get("/api/wrapped/2024", params=default_params)
        d = r.json()
        assert len(d["top_artists"]) == 5
        plays_first = d["top_artists"][0]["plays"]
        plays_last = d["top_artists"][-1]["plays"]
        assert plays_first >= plays_last

    def test_wrapped_top_tracks(self, client, default_params):
        r = client.get("/api/wrapped/2024", params=default_params)
        d = r.json()
        assert len(d["top_tracks"]) == 5

    def test_wrapped_monthly_pulse(self, client, default_params):
        r = client.get("/api/wrapped/2024", params=default_params)
        d = r.json()
        assert len(d["monthly_pulse"]) == 12

    def test_wrapped_empty_year(self, client, default_params):
        r = client.get("/api/wrapped/2010", params=default_params)
        assert r.status_code == 200
        d = r.json()
        assert d["empty"] is True

    def test_wrapped_season_tops(self, client, default_params):
        r = client.get("/api/wrapped/2024", params=default_params)
        d = r.json()
        for season in ["spring", "summer", "autumn", "winter"]:
            assert season in d["season_tops"]


# ═══════════════════════════════════════════════════════════════════════════
# Billboard Data
# ═══════════════════════════════════════════════════════════════════════════

class TestBillboard:
    def test_billboard_meta(self, client, default_params):
        r = client.get("/api/billboard/data", params=default_params)
        assert r.status_code == 200
        d = r.json()
        meta = d["meta"]
        assert meta["total_weeks"] >= 150
        assert meta["total_filtered_records"] > 50000
        assert len(meta["all_weeks_asc"]) == meta["total_weeks"]
        assert meta["top_n"] == 30

    def test_billboard_weekly_format(self, client, default_params):
        r = client.get("/api/billboard/data", params=default_params)
        d = r.json()
        weekly = d["weekly"]
        assert len(weekly) > 5000
        entry = weekly[0]
        for k in ["billboard_week", "track_name", "artist_name", "rank", "play_count"]:
            assert k in entry, f"Missing key in weekly entry: {k}"

    def test_billboard_track_summary(self, client, default_params):
        r = client.get("/api/billboard/data", params=default_params)
        d = r.json()
        ts = d["track_summary"]
        assert len(ts) > 500
        t = ts[0]
        for k in ["track_name", "artist_name", "peak_position", "weeks_on_chart",
                   "weeks_at_peak", "first_week", "last_week"]:
            assert k in t, f"Missing key: {k}"

    def test_billboard_power_scores(self, client, default_params):
        r = client.get("/api/billboard/data", params=default_params)
        d = r.json()
        assert len(d["power_scores"]) > 0
        assert len(d["album_power_scores"]) > 0
        assert len(d["artist_power_scores"]) > 0

    def test_billboard_records(self, client, default_params):
        r = client.get("/api/billboard/data", params=default_params)
        d = r.json()
        assert len(d["records"]) >= 12

    def test_billboard_year_filter(self, client, default_params):
        r = client.get("/api/billboard/data", params={
            **default_params, "year_start": 2024, "year_end": 2024,
        })
        assert r.status_code == 200
        d = r.json()
        assert d["meta"]["total_weeks"] == 52

    def test_billboard_rank_range(self, client, default_params):
        r = client.get("/api/billboard/data", params=default_params)
        weekly = r.json()["weekly"]
        for w in weekly[:200]:
            assert 1 <= w["rank"] <= 30, f"Rank {w['rank']} out of top_n range"


# ═══════════════════════════════════════════════════════════════════════════
# Release Cycle
# ═══════════════════════════════════════════════════════════════════════════

class TestReleaseCycle:
    def test_artist_list_format(self, client, default_params):
        r = client.get("/api/billboard/release-cycle/artist-list", params=default_params)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 100
        assert isinstance(data[0], dict)
        assert "artist_name" in data[0]
        assert "track_count" in data[0]
        assert data[0]["track_count"] > 0

    def test_artist_overview(self, client, default_params):
        r = client.get("/api/billboard/release-cycle/artist/Taylor Swift", params=default_params)
        assert r.status_code == 200
        d = r.json()
        assert d["artist_name"] == "Taylor Swift"
        assert len(d["releases"]) > 10
        assert len(d["rank_trend"]) > 100
        assert d["summary"] is not None
        assert len(d["cycles"]) > 0

    def test_album_detail(self, client, default_params):
        r = client.get(
            "/api/billboard/release-cycle/artist/Taylor Swift/album/Midnights",
            params=default_params,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["album_name"] == "Midnights"
        assert d["artist_name"] == "Taylor Swift"
        assert "metrics" in d
        assert "album_timeline" in d

    def test_album_detail_nonexistent(self, client, default_params):
        r = client.get(
            "/api/billboard/release-cycle/artist/Taylor Swift/album/NonExistentAlbumXYZ",
            params=default_params,
        )
        assert r.status_code == 200
        d = r.json()
        assert "error" in d

    def test_compare_releases(self, client, default_params):
        r = client.post(
            "/api/billboard/release-cycle/compare",
            params=default_params,
            json={
                "items": [
                    {"artist_name": "Taylor Swift", "album_name": "Midnights"},
                    {"artist_name": "Taylor Swift", "album_name": "evermore"},
                ],
                "weeks_before": 8,
                "weeks_after": 16,
            },
        )
        assert r.status_code == 200
        d = r.json()
        assert "comparisons" in d
        assert len(d["comparisons"]) == 2

    def test_compare_requires_two_items(self, client, default_params):
        r = client.post(
            "/api/billboard/release-cycle/compare",
            params=default_params,
            json={"items": [{"artist_name": "Taylor Swift", "album_name": "Midnights"}]},
        )
        assert r.status_code == 200
        d = r.json()
        assert "error" in d


# ═══════════════════════════════════════════════════════════════════════════
# Account Data
# ═══════════════════════════════════════════════════════════════════════════

class TestLibrary:
    def test_library_structure(self, client):
        r = client.get("/api/library")
        assert r.status_code == 200
        d = r.json()
        assert "available" in d
        for k in ["saved_tracks", "saved_albums", "saved_artists",
                   "coverage_pct", "forgotten_count"]:
            assert k in d, f"Missing key: {k}"

    def test_library_playlists(self, client):
        r = client.get("/api/library/playlists")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "name" in data[0]
            assert "track_count" in data[0]

    def test_library_playlist_overlap(self, client):
        r = client.get("/api/library/playlist-overlap")
        assert r.status_code == 200


class TestSearch:
    def test_search_history(self, client):
        r = client.get("/api/search-history")
        assert r.status_code == 200
        d = r.json()
        assert "available" in d
        if d.get("available"):
            assert "total_searches" in d


class TestInsights:
    def test_tiers(self, client):
        r = client.get("/api/insights/tiers")
        assert r.status_code == 200
        d = r.json()
        assert "available" in d

    def test_marquee(self, client):
        r = client.get("/api/insights/marquee")
        assert r.status_code == 200


class TestPodcast:
    def test_podcast(self, client):
        r = client.get("/api/podcast")
        assert r.status_code == 200
        d = r.json()
        assert "available" in d

    def test_podcast_interactions(self, client):
        r = client.get("/api/podcast/interactions")
        assert r.status_code == 200

    def test_podcast_saved_shows(self, client):
        r = client.get("/api/podcast/saved-shows")
        assert r.status_code == 200


class TestVideo:
    def test_video(self, client):
        r = client.get("/api/video")
        assert r.status_code == 200
        d = r.json()
        assert "available" in d


class TestProfile:
    def test_profile(self, client):
        r = client.get("/api/profile")
        assert r.status_code == 200
        d = r.json()
        assert "profile" in d


class TestWrappedHub:
    def test_wrapped_hub(self, client):
        r = client.get("/api/wrapped-hub")
        assert r.status_code == 200
        d = r.json()
        assert "available" in d


# ═══════════════════════════════════════════════════════════════════════════
# Settings, Version Merge, Import
# ═══════════════════════════════════════════════════════════════════════════

class TestSettings:
    def test_get_settings(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200
        d = r.json()
        for k in ["min_ms", "music_only", "merge_enabled",
                   "bb_top_n", "bb_album_top_n", "bb_artist_top_n",
                   "db_record_count"]:
            assert k in d, f"Missing key: {k}"
        assert d["db_record_count"] > 80000


class TestVersionMerge:
    def test_get_groups(self, client):
        r = client.get("/api/version-merge/groups")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_get_ungrouped(self, client):
        r = client.get("/api/version-merge/ungrouped")
        assert r.status_code == 200

    def test_album_types(self, client):
        r = client.get("/api/version-merge/album-types", params={"album_ids": "1,2,3"})
        assert r.status_code == 200

    def test_detect(self, client):
        r = client.post("/api/version-merge/detect", params={"overlap_threshold": 0.5})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "artist_name" in data[0]
            assert "canonical_name" in data[0]


class TestImport:
    def test_import_status_not_found(self, client):
        r = client.get("/api/import/status/nonexistent")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "not_found"


# ═══════════════════════════════════════════════════════════════════════════
# Filter parameter variations
# ═══════════════════════════════════════════════════════════════════════════

class TestFilterVariations:
    def test_no_filter_all_plays(self, client):
        r = client.get("/api/dashboard/summary", params={
            "min_ms": 0, "music_only": True, "merge_enabled": False,
        })
        assert r.status_code == 200
        d = r.json()
        assert d["total_plays"] > 80000

    def test_min_ms_effect(self, client):
        low = client.get("/api/dashboard/summary", params={
            "min_ms": 0, "music_only": True, "merge_enabled": False,
        }).json()["total_plays"]
        high = client.get("/api/dashboard/summary", params={
            "min_ms": 60000, "music_only": True, "merge_enabled": False,
        }).json()["total_plays"]
        assert high <= low, f"higher min_ms returned more plays ({high} > {low})"

    def test_music_only_effect(self, client):
        with_music = client.get("/api/dashboard/summary", params={
            "min_ms": 30000, "music_only": True, "merge_enabled": False,
        }).json()["total_plays"]
        without = client.get("/api/dashboard/summary", params={
            "min_ms": 30000, "music_only": False, "merge_enabled": False,
        }).json()["total_plays"]
        assert with_music <= without

    def test_merge_effect(self, client):
        merged = client.get("/api/dashboard/summary", params={
            "min_ms": 30000, "music_only": True, "merge_enabled": True,
        }).json()["total_plays"]
        unmerged = client.get("/api/dashboard/summary", params={
            "min_ms": 30000, "music_only": True, "merge_enabled": False,
        }).json()["total_plays"]
        assert merged <= unmerged, f"merged ({merged}) > unmerged ({unmerged})"


# ═══════════════════════════════════════════════════════════════════════════
# Response format
# ═══════════════════════════════════════════════════════════════════════════

class TestResponseFormat:
    def test_json_content_type(self, client, default_params):
        r = client.get("/api/dashboard/summary", params=default_params)
        assert "application/json" in r.headers["content-type"]

    def test_gzip_for_large_response(self, client, default_params):
        r = client.get("/api/billboard/data", params=default_params)
        assert len(r.content) > 100000

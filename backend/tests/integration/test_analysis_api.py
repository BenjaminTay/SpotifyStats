"""Playback analysis API tests."""

import pytest

pytestmark = pytest.mark.integration


class TestAnalysisOverview:
    def test_overview_structure(self, client, default_params):
        r = client.get("/api/analysis/overview", params=default_params)
        assert r.status_code == 200
        data = r.json()

        for key in [
            "summary",
            "monthly_trend",
            "trend_summary",
            "listening_summary",
            "top_tracks",
            "top_artists",
            "top_albums",
            "behavior_summary",
            "module_cards",
        ]:
            assert key in data, f"Missing key: {key}"

        summary = data["summary"]
        assert summary["total_plays"] > 50000
        assert summary["total_hours"] > 3000
        assert summary["total_tracks"] > 4000
        assert summary["total_artists"] > 500

        assert len(data["monthly_trend"]) >= 40
        assert len(data["top_tracks"]) == 5
        assert len(data["top_artists"]) == 5
        assert len(data["top_albums"]) == 5
        assert len(data["module_cards"]) == 5
        for row in data["top_tracks"] + data["top_artists"] + data["top_albums"]:
            assert "cover_url" in row

    def test_overview_changes_with_filter_params(self, client, default_params):
        default = client.get("/api/analysis/overview", params=default_params).json()
        strict = client.get(
            "/api/analysis/overview",
            params={**default_params, "min_ms": 120000},
        ).json()

        assert strict["summary"]["total_plays"] < default["summary"]["total_plays"]
        assert strict["summary"]["total_hours"] <= default["summary"]["total_hours"]

    def test_overview_extreme_filter_returns_empty_shape(self, client, default_params):
        r = client.get(
            "/api/analysis/overview",
            params={**default_params, "min_ms": 999999999},
        )
        assert r.status_code == 200
        data = r.json()

        assert data["summary"]["total_plays"] == 0
        assert data["monthly_trend"] == []
        assert data["top_tracks"] == []
        assert data["top_artists"] == []
        assert data["top_albums"] == []
        assert data["module_cards"] == []

    def test_overview_total_matches_dashboard_summary(self, client, default_params):
        overview = client.get("/api/analysis/overview", params=default_params).json()
        dashboard = client.get("/api/dashboard/summary", params=default_params).json()

        assert overview["summary"]["total_plays"] == dashboard["total_plays"]
        assert abs(overview["summary"]["total_hours"] - dashboard["total_hours"]) < 0.2

    def test_analysis_entity_endpoints_include_cover_urls(self, client, default_params):
        leaderboard = client.get(
            "/api/leaderboard",
            params={**default_params, "entity": "track", "top_n": 5},
        ).json()
        assert "cover_url" in leaderboard["rows"][0]

        monthly = client.get(
            "/api/timeline/monthly",
            params={**default_params, "period": "2024-10"},
        ).json()
        assert monthly["drilldown"]
        assert "cover_url" in monthly["drilldown"][0]

        artists = client.get("/api/artist/list", params=default_params).json()
        assert artists
        assert "cover_url" in artists[0]

        detail = client.get(
            f"/api/artist/{artists[0]['artist_name']}/deep-dive",
            params=default_params,
        ).json()
        assert detail["found"] is True
        assert "cover_url" in detail
        assert "cover_url" in detail["top_tracks"][0]
        assert "cover_url" in detail["album_breakdown"][0]


class TestAnalysisStats:
    def test_stats_lifetime_structure(self, client, default_params):
        r = client.get("/api/analysis/stats", params={**default_params, "period": "lifetime"})
        assert r.status_code == 200
        data = r.json()

        for key in [
            "summary",
            "daily_metrics",
            "hourly_distribution",
            "daily_trend",
            "cumulative_trend",
            "weekday_distribution",
            "month_distribution",
            "year_distribution",
            "behavior_summary",
            "recent_plays",
        ]:
            assert key in data

        assert data["summary"]["total_plays"] > 50000
        assert data["summary"]["unique_tracks"] > 4000
        assert len(data["hourly_distribution"]) == 24
        assert len(data["weekday_distribution"]) == 7
        assert len(data["month_distribution"]) == 12
        assert data["daily_trend"]
        assert data["cumulative_trend"][-1]["cumulative_plays"] == data["summary"]["total_plays"]
        assert data["recent_plays"]
        assert "cover_url" in data["recent_plays"][0]

    def test_stats_custom_empty_range_returns_zero_shape(self, client, default_params):
        r = client.get(
            "/api/analysis/stats",
            params={
                **default_params,
                "period": "custom",
                "start_date": "1900-01-01",
                "end_date": "1900-01-02",
            },
        )
        assert r.status_code == 200
        data = r.json()

        assert data["summary"]["total_plays"] == 0
        assert data["daily_trend"] == []
        assert data["recent_plays"] == []
        assert len(data["hourly_distribution"]) == 24


class TestAnalysisCharts:
    def test_charts_returns_cover_rows_for_all_entities(self, client, default_params):
        for entity in ["track", "album", "artist"]:
            r = client.get(
                "/api/analysis/charts",
                params={**default_params, "entity": entity, "metric": "plays", "limit": 10},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["total"] >= len(data["rows"]) > 0
            assert data["rows"][0]["rank"] == 1
            assert "cover_url" in data["rows"][0]
            assert "first_played" in data["rows"][0]
            assert "last_played" in data["rows"][0]
            assert "share_pct" in data["rows"][0]

    def test_charts_metric_changes_sort_value(self, client, default_params):
        plays = client.get(
            "/api/analysis/charts",
            params={**default_params, "entity": "track", "metric": "plays", "limit": 5},
        ).json()
        hours = client.get(
            "/api/analysis/charts",
            params={**default_params, "entity": "track", "metric": "hours", "limit": 5},
        ).json()

        assert plays["rows"][0]["plays"] >= plays["rows"][1]["plays"]
        assert hours["rows"][0]["hours"] >= hours["rows"][1]["hours"]


class TestMusicStats:
    def test_track_album_artist_stats_structure(self, client, default_params):
        charts = client.get(
            "/api/analysis/charts",
            params={**default_params, "entity": "track", "limit": 1},
        ).json()
        track = charts["rows"][0]

        track_stats = client.get(
            f"/api/music/tracks/{track['track_id']}/stats",
            params=default_params,
        )
        assert track_stats.status_code == 200
        track_data = track_stats.json()
        assert track_data["found"] is True
        assert track_data["summary"]["total_plays"] == track["plays"]
        assert "lifetime" in track_data["ranks"]
        assert len(track_data["hourly_distribution"]) == 24
        assert track_data["recent_plays"]

        album_stats = client.get(
            f"/api/music/albums/{track['album_name']}/stats",
            params={**default_params, "artist": track["artist_name"]},
        )
        assert album_stats.status_code == 200
        album_data = album_stats.json()
        assert album_data["found"] is True
        assert "top250_counts" in album_data
        assert album_data["track_breakdown"]
        assert "cover_url" in album_data["track_breakdown"][0]

        artist_stats = client.get(
            f"/api/music/artists/{track['artist_name']}/stats",
            params=default_params,
        )
        assert artist_stats.status_code == 200
        artist_data = artist_stats.json()
        assert artist_data["found"] is True
        assert "top250_counts" in artist_data
        assert "recent_50_count" in artist_data
        assert artist_data["top_tracks"]
        assert artist_data["top_albums"]

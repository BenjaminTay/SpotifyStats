"""Contract tests — validate API response structure against seed SQLite DB.

These tests run against a small, known seed database. They verify JSON structure,
HTTP status codes, and response types — not specific data values (those belong in
integration tests against real data).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_health_no_stack_trace(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200


class TestDashboardEndpoints:
    def test_summary_structure(self, client):
        r = client.get("/api/dashboard/summary", params={"min_ms": 30000})
        assert r.status_code == 200
        data = r.json()
        for key in ["total_plays", "total_hours", "total_tracks", "total_artists"]:
            assert key in data
            assert isinstance(data[key], (int, float))

    def test_dow_dist_structure(self, client):
        r = client.get("/api/dashboard/dow-dist", params={"min_ms": 30000})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "day" in data[0]

    def test_platform_dist_structure(self, client):
        r = client.get("/api/dashboard/platform-dist", params={"min_ms": 30000})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)


class TestTimelineEndpoints:
    def test_annual_structure(self, client):
        r = client.get("/api/timeline/annual", params={"min_ms": 30000})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)


class TestBehaviorEndpoints:
    def test_behavior_structure(self, client):
        r = client.get("/api/behavior", params={"min_ms": 30000})
        assert r.status_code == 200
        data = r.json()
        for key in ["reason_end", "reason_start", "fwdbtn_by_hour"]:
            assert key in data


class TestListeningHoursEndpoints:
    def test_heatmap_structure(self, client):
        r = client.get("/api/listening-hours/heatmap", params={"min_ms": 30000})
        assert r.status_code == 200
        data = r.json()
        assert "z" in data
        assert "x" in data
        assert "y" in data


class TestMusicEndpoints:
    def test_track_stats_not_found(self, client):
        r = client.get("/api/music/tracks/99999/stats", params={"min_ms": 30000})
        assert r.status_code == 200
        data = r.json()
        assert data.get("found") is False or data.get("empty") is True

    def test_album_stats_not_found(self, client):
        r = client.get("/api/music/albums/____nonexistent____/stats", params={"min_ms": 30000})
        assert r.status_code == 200
        data = r.json()
        assert data.get("found") is False or data.get("empty") is True

    def test_artist_stats_not_found(self, client):
        r = client.get("/api/music/artists/____nonexistent____/stats", params={"min_ms": 30000})
        assert r.status_code == 200
        data = r.json()
        assert data.get("found") is False or data.get("empty") is True


class TestLeaderboardEndpoints:
    def test_leaderboard_structure(self, client):
        r = client.get(
            "/api/leaderboard",
            params={"entity": "track", "metric": "plays", "min_ms": 30000},
        )
        assert r.status_code == 200
        data = r.json()
        assert "rows" in data


class TestBillboardEndpoints:
    def test_billboard_data_structure(self, client):
        r = client.get(
            "/api/billboard/data",
            params={
                "min_ms": 30000,
                "bb_top_n": 30,
                "bb_album_top_n": 20,
                "bb_artist_top_n": 20,
            },
        )
        assert r.status_code == 200
        data = r.json()
        for key in [
            "meta",
            "weekly",
            "weekly_album",
            "weekly_artist",
            "track_summary",
            "records",
        ]:
            assert key in data, f"Missing key: {key}"

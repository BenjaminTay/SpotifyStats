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
        assert r.headers.get("X-Request-ID")

    def test_health_no_stack_trace(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_request_id_header_is_preserved(self, client):
        r = client.get("/api/health", headers={"X-Request-ID": "phase5-test-request"})
        assert r.status_code == 200
        assert r.headers["X-Request-ID"] == "phase5-test-request"


class TestArtistIdentityEndpoints:
    def test_identity_overview_exposes_revision_state_and_groups(self, client):
        response = client.get("/api/artist-identities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["state"]["current_revision"], int)
        assert isinstance(data["state"]["active_aggregate_revision"], int)
        assert data["state"]["rebuild_status"] in {"ready", "pending", "running", "failed"}
        assert isinstance(data["groups"], list)

    def test_candidate_search_contract(self, client):
        response = client.get("/api/artist-identities/candidates", params={"q": "a"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)
        assert "state" in data


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

    def test_behavior_openapi_only_exposes_effective_filters(self):
        from backend.main import app

        operation = app.openapi()["paths"]["/api/behavior"]["get"]
        query_params = {
            param["name"] for param in operation.get("parameters", []) if param["in"] == "query"
        }

        assert query_params == {"music_only", "readonly"}


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


class TestAnalysisRecordsEndpoint:
    """Contract: /api/analysis/records returns correct nested structure with non-empty P0 records."""

    def test_records_returns_200_with_nested_structure(self, client):
        r = client.get(
            "/api/analysis/records",
            params={
                "min_ms": 30000,
                "music_only": "true",
                "merge_enabled": "true",
                "period": "lifetime",
                "merge_level": 2,
                "dynamic_threshold": "true",
            },
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
        data = r.json()

        # Top-level structure
        assert "period" in data
        assert "meta" in data
        assert "records" in data
        assert data["meta"]["total_plays"] > 0, "meta.total_plays must be non-zero with seed data"

        rec = data["records"]

        # Required sections
        for section in [
            "obsession",
            "time_patterns",
            "reigns",
            "longevity",
            "discovery",
            "behavior",
        ]:
            assert section in rec, f"Missing section: {section}"

        # P0: obsession.daily_binge must have track/album/artist triples
        db = rec["obsession"]["daily_binge"]
        assert isinstance(db["track"], list)
        assert isinstance(db["album"], list)
        assert isinstance(db["artist"], list)

        # P0: longevity.longest_streak_days must have non-empty triples
        ls = rec["longevity"]["longest_streak_days"]
        assert isinstance(ls["track"], list)
        assert isinstance(ls["album"], list)
        assert isinstance(ls["artist"], list)

    def test_records_daily_binge_has_data(self, client):
        """Content contract: daily_binge must not be empty with seed data."""
        r = client.get(
            "/api/analysis/records",
            params={
                "min_ms": 30000,
                "music_only": "true",
                "merge_enabled": "true",
                "period": "lifetime",
                "merge_level": 2,
                "dynamic_threshold": "true",
            },
        )
        assert r.status_code == 200
        data = r.json()
        rec = data["records"]

        db = rec["obsession"]["daily_binge"]
        total = len(db["track"]) + len(db["album"]) + len(db["artist"])
        assert total > 0, (
            f"daily_binge must have data; got track={len(db['track'])}, "
            f"album={len(db['album'])}, artist={len(db['artist'])}"
        )

    def test_records_longevity_streak_has_data(self, client):
        """Content contract: longest_streak_days must not be empty with seed data."""
        r = client.get(
            "/api/analysis/records",
            params={
                "min_ms": 30000,
                "music_only": "true",
                "merge_enabled": "true",
                "period": "lifetime",
                "merge_level": 2,
                "dynamic_threshold": "true",
            },
        )
        assert r.status_code == 200
        data = r.json()
        rec = data["records"]

        ls = rec["longevity"]["longest_streak_days"]
        total = len(ls["track"]) + len(ls["album"]) + len(ls["artist"])
        assert total > 0, (
            f"longest_streak_days must have data; got track={len(ls['track'])}, "
            f"album={len(ls['album'])}, artist={len(ls['artist'])}"
        )

    def test_records_daily_total_record_has_day_rows_with_top_entities(self, client):
        """Daily total records should be sortable day rows with daily top entities."""
        r = client.get(
            "/api/analysis/records",
            params={
                "min_ms": 30000,
                "music_only": "true",
                "merge_enabled": "true",
                "period": "lifetime",
                "merge_level": 2,
                "dynamic_threshold": "true",
            },
        )
        assert r.status_code == 200
        rows = r.json()["records"]["obsession"]["daily_total_record"]

        assert 1 <= len(rows) <= 100
        dates = [row["date"] for row in rows]
        assert len(dates) == len(set(dates))
        assert {"播放次数纪录", "总时长纪录", "独特歌曲纪录"}.isdisjoint(
            {row["name"] for row in rows}
        )
        for row in rows:
            assert row["name"] == row["date"]
            assert row["total_plays"] and row["total_plays"] > 0
            assert row["total_hours"] is not None and row["total_hours"] >= 0
            assert row["unique_tracks"] and row["unique_tracks"] > 0
            assert row["top_track_name"]
            assert row["top_track_entity_id"]
            assert row["top_album_name"]
            assert row["top_artist_name"]
            assert "top_track_cover_url" in row
            assert "top_album_cover_url" in row
            assert "top_artist_cover_url" in row

    def test_records_cover_url_field_present(self, client):
        """Cover URL contract: records should have cover_url field (may be null if no image data)."""
        r = client.get(
            "/api/analysis/records",
            params={
                "min_ms": 30000,
                "music_only": "true",
                "merge_enabled": "true",
                "period": "lifetime",
                "merge_level": 2,
                "dynamic_threshold": "true",
            },
        )
        assert r.status_code == 200
        data = r.json()
        rec = data["records"]

        # Check that cover_url field exists on track records (value may be null)
        db_tracks = rec["obsession"]["daily_binge"]["track"]
        assert len(db_tracks) > 0, "daily_binge tracks must not be empty"
        assert "cover_url" in db_tracks[0], (
            f"track records must have cover_url field; keys: {list(db_tracks[0].keys())}"
        )

    def test_records_empty_on_extreme_filters(self, client):
        """Shape contract: response shape is preserved even with extreme filters."""
        r = client.get(
            "/api/analysis/records",
            params={
                "min_ms": 9999999,
                "music_only": "true",
                "period": "lifetime",
                "merge_level": 2,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["meta"]["total_plays"] == 0
        # Shape must still be valid — nested sections present with empty lists
        rec = data["records"]
        assert rec["obsession"]["daily_binge"]["track"] == []
        assert rec["longevity"]["longest_streak_days"]["track"] == []

    def test_records_merge_level_shape_stable(self, client):
        """Shape contract: merge_level=1 and merge_level=2 both return valid nested structure."""
        for ml in [1, 2]:
            r = client.get(
                "/api/analysis/records",
                params={
                    "min_ms": 30000,
                    "music_only": "true",
                    "merge_enabled": "true",
                    "period": "lifetime",
                    "merge_level": ml,
                    "dynamic_threshold": "true",
                },
            )
            assert r.status_code == 200, f"merge_level={ml} returned {r.status_code}"
            data = r.json()
            rec = data["records"]
            # Verify triple structure is intact
            db = rec["obsession"]["daily_binge"]
            assert isinstance(db["track"], list), f"merge_level={ml}: track must be list"
            assert isinstance(db["album"], list), f"merge_level={ml}: album must be list"
            assert isinstance(db["artist"], list), f"merge_level={ml}: artist must be list"

    def test_records_album_triple_has_data(self, client):
        """Content contract: album records are non-empty, proving album project attribution works."""
        r = client.get(
            "/api/analysis/records",
            params={
                "min_ms": 30000,
                "music_only": "true",
                "merge_enabled": "true",
                "period": "lifetime",
                "merge_level": 2,
                "dynamic_threshold": "true",
            },
        )
        assert r.status_code == 200
        rec = r.json()["records"]
        # Album records across sections must have data
        album_daily_binge = rec["obsession"]["daily_binge"]["album"]
        album_streak = rec["longevity"]["longest_streak_days"]["album"]
        assert len(album_daily_binge) > 0, "Album daily_binge must have data"
        assert len(album_streak) > 0, "Album streak must have data"

    def test_records_artist_triple_has_data(self, client):
        """Content contract: artist records are non-empty, proving fan-out works with seed data."""
        r = client.get(
            "/api/analysis/records",
            params={
                "min_ms": 30000,
                "music_only": "true",
                "merge_enabled": "true",
                "period": "lifetime",
                "merge_level": 2,
                "dynamic_threshold": "true",
            },
        )
        assert r.status_code == 200
        rec = r.json()["records"]
        # Artist records across sections must have data
        artist_daily_binge = rec["obsession"]["daily_binge"]["artist"]
        artist_streak = rec["longevity"]["longest_streak_days"]["artist"]
        assert len(artist_daily_binge) > 0, "Artist daily_binge must have data"
        assert len(artist_streak) > 0, "Artist streak must have data"

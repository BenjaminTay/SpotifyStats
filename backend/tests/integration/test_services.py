"""Service layer tests — validate computation logic directly.

These tests call service functions directly (bypassing HTTP) to verify
computation correctness with concrete data assertions.
"""

import pytest

pytestmark = pytest.mark.integration

# ═══════════════════════════════════════════════════════════════════════════
# Play Service
# ═══════════════════════════════════════════════════════════════════════════


class TestPlayService:
    def test_dashboard_summary(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_dashboard_summary

        conn = get_db()
        try:
            result = get_dashboard_summary(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert result["total_plays"] > 50000
            assert result["total_hours"] > 3000
            assert result["total_tracks"] > 4000
            assert result["total_artists"] > 500
            assert result["total_plays"] >= result["total_tracks"]
        finally:
            conn.close()

    def test_dashboard_summary_numeric_types(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_dashboard_summary

        conn = get_db()
        try:
            result = get_dashboard_summary(conn, min_ms=30000, music_only=True, merge_enabled=True)
            for k, v in result.items():
                assert isinstance(v, (int, float)), f"{k} is {type(v)}"
        finally:
            conn.close()

    def test_dashboard_monthly_trend(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_monthly_trend

        conn = get_db()
        try:
            data = get_monthly_trend(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert len(data) > 40
            for m in data:
                assert "period" in m
                assert "plays" in m
                assert "hours" in m
        finally:
            conn.close()

    def test_timeline_annual(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_annual_timeline

        conn = get_db()
        try:
            data = get_annual_timeline(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert len(data) >= 4
            years = [y["year"] for y in data]
            assert years == sorted(years)
            for y in data:
                assert y["plays"] > 0
                assert y["hours"] > 0
                assert y["unique_tracks"] > 0
        finally:
            conn.close()

    def test_leaderboard_tracks(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_leaderboard

        conn = get_db()
        try:
            data = get_leaderboard(
                conn,
                min_ms=30000,
                music_only=True,
                merge_enabled=True,
                entity="track",
                metric="plays",
                top_n=10,
            )
            assert len(data["rows"]) == 10
            for row in data["rows"]:
                assert row["rank"] >= 1
                assert row["plays"] > 0
                assert row["track_name"]
                assert row["artist_name"]
        finally:
            conn.close()

    def test_leaderboard_artists(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_leaderboard

        conn = get_db()
        try:
            data = get_leaderboard(
                conn,
                min_ms=30000,
                music_only=True,
                merge_enabled=True,
                entity="artist",
                metric="hours",
                top_n=10,
            )
            assert len(data["rows"]) == 10
            assert data["rows"][0]["artist_name"] == "Taylor Swift"
        finally:
            conn.close()

    def test_behavior_data(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_behavior_data

        conn = get_db()
        try:
            data = get_behavior_data(conn, music_only=True)
            assert len(data["reason_end"]) >= 5
            assert len(data["reason_start"]) >= 5
            assert len(data["fwdbtn_by_hour"]) == 24
            assert len(data["most_forwarded"]) > 0
            assert len(data["shuffle_rate_by_platform"]) > 0
        finally:
            conn.close()

    def test_wrapped_2024(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_wrapped_data

        conn = get_db()
        try:
            data = get_wrapped_data(
                conn, min_ms=30000, music_only=True, merge_enabled=True, year=2024
            )
            assert data["year"] == 2024
            assert data["empty"] is False
            assert data["hero"] is not None
            assert len(data["top_artists"]) == 5
            assert len(data["top_tracks"]) == 5
            assert len(data["monthly_pulse"]) == 12
        finally:
            conn.close()

    def test_wrapped_empty_year(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_wrapped_data

        conn = get_db()
        try:
            data = get_wrapped_data(
                conn, min_ms=30000, music_only=True, merge_enabled=True, year=2010
            )
            assert data["year"] == 2010
            assert data["empty"] is True
        finally:
            conn.close()

    def test_wrapped_personality(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_wrapped_data

        conn = get_db()
        try:
            data = get_wrapped_data(
                conn, min_ms=30000, music_only=True, merge_enabled=True, year=2024
            )
            p = data["personality"]
            assert "primary" in p
            assert "explorer" in p
            assert "loyalist" in p
            assert "binger" in p
            for key in ["primary", "explorer", "loyalist", "binger"]:
                item = p[key]
                assert "label" in item
                assert "score" in item
                assert isinstance(item["score"], (int, float))
                assert 0 <= item["score"] <= 100
        finally:
            conn.close()

    def test_listening_heatmap(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_listening_heatmap

        conn = get_db()
        try:
            data = get_listening_heatmap(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert len(data["z"]) == 7
            assert len(data["z"][0]) == 24
            assert data["x"] == list(range(24))
            assert len(data["y"]) == 7
        finally:
            conn.close()

    def test_weekly_timeline(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_weekly_timeline

        conn = get_db()
        try:
            data = get_weekly_timeline(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert len(data["weeks"]) >= 150
            assert data["drilldown"] is None
            w = data["weeks"][0]
            assert "label" in w
            assert "plays" in w
            assert "hours" in w
            assert "-W" in w["label"]
        finally:
            conn.close()

    def test_weekly_timeline_drilldown(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_weekly_timeline

        conn = get_db()
        try:
            data = get_weekly_timeline(
                conn, min_ms=30000, music_only=True, merge_enabled=True, week_label="2024-W01"
            )
            drilldown = data["drilldown"]
            assert drilldown is not None
            assert len(drilldown) >= 1
            for t in drilldown:
                assert "track_name" in t
                assert "artist_name" in t
                assert t["plays"] > 0
        finally:
            conn.close()

    def test_weekday_weekend_comparison(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_weekday_weekend_comparison

        conn = get_db()
        try:
            data = get_weekday_weekend_comparison(
                conn, min_ms=30000, music_only=True, merge_enabled=True
            )
            assert len(data["hours"]) == 24
            assert len(data["weekend"]) == 24
            assert len(data["weekday"]) == 24
            assert sum(data["weekend"]) + sum(data["weekday"]) > 50000
        finally:
            conn.close()

    def test_platform_hourly_listening(self):
        from backend.core.db import get_db
        from backend.services.play_service import get_platform_hourly_listening

        conn = get_db()
        try:
            data = get_platform_hourly_listening(
                conn, min_ms=30000, music_only=True, merge_enabled=True
            )
            assert len(data["platform_hourly"]) > 0
            assert len(data["platform_pct"]) > 0
            assert len(data["platform_peaks"]) >= 1
            for p in data["platform_peaks"]:
                assert "platform" in p
                assert "peak_hour" in p
                assert 0 <= p["peak_hour"] <= 23
                assert p["peak_count"] > 0
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Billboard Service
# ═══════════════════════════════════════════════════════════════════════════


class TestBillboardService:
    def test_compute_billboard_data_meta(self, billboard_data):
        meta = billboard_data["meta"]
        assert meta["total_weeks"] >= 150
        assert meta["total_filtered_records"] > 50000
        assert len(meta["all_weeks_asc"]) == meta["total_weeks"]

    def test_compute_billboard_data_weekly(self, billboard_data):
        weekly = billboard_data["weekly"]
        assert len(weekly) > 5000
        entry = weekly[0]
        assert 1 <= entry["rank"] <= 30
        assert isinstance(entry["billboard_week"], str)
        assert isinstance(entry["track_name"], str)

    def test_compute_billboard_data_track_summary(self, billboard_data):
        ts = billboard_data["track_summary"]
        assert len(ts) > 500
        assert ts[0]["peak_position"] >= 1
        assert ts[0]["weeks_on_chart"] >= 1

    def test_compute_billboard_data_records(self, billboard_data):
        records = billboard_data["records"]
        assert len(records) >= 40

        # ── 冠军圣殿 ──
        r = records
        assert len(r["artist_most_no1"]) > 0
        a1 = r["artist_most_no1"][0]
        assert "冠单数" in a1
        assert "冠军专辑数" in a1
        assert "单曲冠军周数" in a1
        assert "专辑冠军周数" in a1

        assert len(r["debut_no1"]) > 0
        assert "track_id" in r["debut_no1"][0]
        assert "weeks_at_no1" in r["debut_no1"][0]
        assert len(r["debut_no1_album"]) > 0
        assert "weeks_at_no1" in r["debut_no1_album"][0]

        assert len(r["return_to_no1"]) > 0
        assert len(r["return_to_no1_album"]) > 0

        assert len(r["self_replacement_no1"]) > 0
        assert len(r["self_replacement_no1_album"]) > 0
        assert "前冠专" in r["self_replacement_no1_album"][0]

        assert len(r["blocker_king"]) > 0
        assert "阻挡数" in r["blocker_king"][0]
        assert "走势评分" in r["blocker_king"][0]
        assert len(r["blocked_tracks_map"]) > 0
        assert len(r["blocker_king_album"]) > 0
        assert "走势评分" in r["blocker_king_album"][0]
        assert len(r["blocked_albums_map"]) > 0

        assert len(r["longest_to_no1"]) > 0
        assert "登顶周数" in r["longest_to_no1"][0]
        assert len(r["fastest_to_no1"]) > 0

        # ── 持久传奇 ──
        for key in [
            "longest_charting",
            "longest_charting_album",
            "longest_streak",
            "longest_streak_album",
            "longest_no_top5",
            "longest_no_top5_album",
            "most_weeks_no2_no_no1",
            "most_weeks_no2_no_no1_album",
            "most_reentries",
            "most_reentries_album",
            "longest_consecutive_same_rank",
            "longest_consecutive_same_rank_album",
        ]:
            assert len(r[key]) > 0, f"{key} should have data"

        assert len(r["longest_artist_span"]) > 0
        assert "跨度天数" in r["longest_artist_span"][0]

        # ── 爆发时刻 ──
        assert "artist_simul" in r
        assert "album_simul" in r
        assert len(r["artist_simul_list"]) > 0
        assert len(r["album_simul_list"]) > 0
        assert "most_top10_simul" in r
        assert len(r["biggest_jump"]) > 0
        assert len(r["biggest_drop"]) > 0
        assert len(r["fastest_exit_after_no1"]) > 0
        assert "strongest_week" in r

        # ── 名人堂 ──
        assert len(r["all_time_greatest"]) > 0
        assert "走势评分" in r["all_time_greatest"][0]
        assert len(r["album_power_ranking"]) > 0
        assert len(r["artist_power_ranking"]) > 0
        assert len(r["year_end_no1"]) > 0
        assert len(r["decade_best"]) > 0
        assert "年代" in r["decade_best"][0]

        # ── 奇趣纪录 ──
        assert len(r["double_debut"]) > 0
        assert len(r["triple_no1"]) > 0

        # ── 每周大盘 ──
        assert len(r["week_total_plays"]) > 0
        wtp = r["week_total_plays"][0]
        assert "total_plays" in wtp
        assert "no1_album" in wtp
        assert "no1_album_artist" in wtp
        assert "closest_no1_vs_no2" in r
        if r["closest_no1_vs_no2"]:
            assert "gap_pct" in r["closest_no1_vs_no2"]
        assert "largest_no1_vs_no2" in r
        if r["largest_no1_vs_no2"]:
            assert "gap_pct" in r["largest_no1_vs_no2"]

        assert len(r["new_entry_ratio"]) > 0
        ner = r["new_entry_ratio"]
        # 验证按活跃度降序排列
        if len(ner) >= 2:
            assert ner[0]["新歌占比"] >= ner[-1]["新歌占比"], (
                "new_entry_ratio should be sorted by 新歌占比 descending"
            )
        assert "大盘播放" in ner[0]

    def test_compute_billboard_data_records_album_fields(self, billboard_data):
        """验证专辑维度记录的关键字段存在"""
        records = billboard_data["records"]

        for key in [
            "longest_charting_album",
            "longest_streak_album",
            "longest_no_top5_album",
            "most_weeks_no2_no_no1_album",
            "most_reentries_album",
            "longest_consecutive_same_rank_album",
        ]:
            data = records[key]
            assert len(data) > 0, f"{key} should have data"
            assert "album_name" in data[0], f"{key} missing album_name"
            assert "artist_name" in data[0], f"{key} missing artist_name"

        # 验证 blocked_tracks_map 结构
        assert isinstance(records["blocked_tracks_map"], dict)
        first_key = next(iter(records["blocked_tracks_map"]))
        assert isinstance(records["blocked_tracks_map"][first_key], list)

        # 验证 blocked_albums_map 结构
        assert isinstance(records["blocked_albums_map"], dict)
        first_alb_key = next(iter(records["blocked_albums_map"]))
        assert isinstance(records["blocked_albums_map"][first_alb_key], list)

    def test_compute_billboard_data_power_scores(self, billboard_data):
        assert len(billboard_data["power_scores"]) > 0
        assert len(billboard_data["album_power_scores"]) > 0
        assert len(billboard_data["artist_power_scores"]) > 0

    def test_year_filter(self, billboard_data):
        from backend.services.billboard_service import compute_billboard_data

        result_2024 = compute_billboard_data(bb_top_n=30, year_start=2024, year_end=2024)
        assert result_2024["meta"]["total_weeks"] < billboard_data["meta"]["total_weeks"]
        assert result_2024["meta"]["total_weeks"] == 52
        assert len(result_2024["weekly"]) < len(billboard_data["weekly"])

    def test_track_history(self):
        from backend.services.billboard_service import get_track_history

        data = get_track_history(
            track_id=157,
            min_ms=30000,
            music_only=True,
            bb_top_n=30,
            bb_album_top_n=20,
            bb_artist_top_n=20,
            bb_week_start_dow=4,
            bb_week_start_hour=0,
            year_start=None,
            year_end=None,
        )
        assert data["found"] is True
        assert data["track_id"] == 157
        assert len(data["history"]) >= 1
        assert data["summary"]["weeks_on_chart"] >= 1
        for h in data["history"]:
            assert (
                h["change"] in ("NEW", "RE", "─")
                or h["change"].startswith("▲")
                or h["change"].startswith("▼")
            )
        assert len(data["chart_data"]["x"]) >= len(data["history"])
        assert len(data["chart_data"]["y"]) >= len(data["history"])

    def test_track_history_not_found(self):
        from backend.services.billboard_service import get_track_history

        data = get_track_history(
            track_id=99999,
            min_ms=30000,
            music_only=True,
            bb_top_n=30,
            bb_album_top_n=20,
            bb_artist_top_n=20,
            bb_week_start_dow=4,
            bb_week_start_hour=0,
            year_start=None,
            year_end=None,
        )
        assert data["found"] is False

    def test_artist_chart_detail(self):
        from backend.services.billboard_service import get_artist_chart_detail

        data = get_artist_chart_detail(
            artist_name="Taylor Swift",
            min_ms=30000,
            music_only=True,
            bb_top_n=30,
            bb_album_top_n=20,
            bb_artist_top_n=20,
            bb_week_start_dow=4,
            bb_week_start_hour=0,
            year_start=None,
            year_end=None,
        )
        assert data["found"] is True
        assert data["artist_name"] == "Taylor Swift"
        assert len(data["tracks"]) > 10
        assert len(data["albums"]) >= 1
        assert "chart_summary" in data
        assert "artist_weekly_history" in data

    def test_album_chart_detail(self):
        from backend.services.billboard_service import get_album_chart_detail

        data = get_album_chart_detail(
            album_name="Midnights",
            artist_name="Taylor Swift",
            min_ms=30000,
            music_only=True,
            bb_top_n=30,
            bb_album_top_n=20,
            bb_artist_top_n=20,
            bb_week_start_dow=4,
            bb_week_start_hour=0,
            year_start=None,
            year_end=None,
        )
        assert data["found"] is True
        assert data["album_name"] == "Midnights"
        assert len(data["tracks"]) >= 1
        assert "chart_summary" in data
        assert "album_weekly_history" in data

    def test_album_chart_detail_without_charting_singles(self):
        from backend.services.billboard_service import get_album_chart_detail

        data = get_album_chart_detail(
            album_name="CONFESSIONS II",
            artist_name="Madonna",
            min_ms=30000,
            music_only=True,
            bb_top_n=30,
            bb_album_top_n=20,
            bb_artist_top_n=20,
            bb_week_start_dow=4,
            bb_week_start_hour=12,
            year_start=None,
            year_end=None,
            dynamic_threshold=True,
            merge_level=2,
        )
        assert data["chart_status"] == "charted"
        assert data["track_chart_status"] == "not_charted"
        history = data["album_weekly_history"]
        assert history
        peak_position = min(int(row["rank"]) for row in history)
        assert data["chart_summary"]["peak_position"] == peak_position
        assert data["chart_summary"]["weeks_on_chart"] == len(history)
        assert data["chart_summary"]["peak_weeks"] == sum(
            int(row["rank"]) == peak_position for row in history
        )
        assert data["chart_summary"]["no1_weeks"] == 0
        assert data["chart_summary"]["power_score"] > 0
        assert data["tracks"] == []

    def test_entity_lists(self):
        from backend.services.billboard_service import get_billboard_entity_lists

        data = get_billboard_entity_lists(
            min_ms=30000,
            music_only=True,
            bb_top_n=30,
            bb_album_top_n=20,
            bb_artist_top_n=20,
            bb_week_start_dow=4,
            bb_week_start_hour=0,
            year_start=None,
            year_end=None,
        )
        assert len(data["tracks"]) > 500
        assert len(data["albums"]) > 200
        assert len(data["artists"]) > 100
        assert "display" in data["tracks"][0]
        assert "track_id" in data["tracks"][0]

    def test_versus_track(self):
        from backend.services.billboard_service import get_versus_track

        data = get_versus_track(
            tid_a=157,
            tid_b=149,
            min_ms=30000,
            music_only=True,
            bb_top_n=30,
            bb_album_top_n=20,
            bb_artist_top_n=20,
            bb_week_start_dow=4,
            bb_week_start_hour=0,
            year_start=None,
            year_end=None,
        )
        assert data["found"] is True
        for key in ["entity_a", "entity_b"]:
            e = data[key]
            assert "name" in e
            assert "rank_history" in e
            assert len(e["rank_history"]) >= 1
            assert "power_score" in e["metrics"]
            assert "peak_position" in e["metrics"]

    def test_versus_album(self):
        from backend.services.billboard_service import get_versus_album

        data = get_versus_album(
            aname_a="Midnights",
            aart_a="Taylor Swift",
            aname_b="folklore",
            aart_b="Taylor Swift",
            min_ms=30000,
            music_only=True,
            bb_top_n=30,
            bb_album_top_n=20,
            bb_artist_top_n=20,
            bb_week_start_dow=4,
            bb_week_start_hour=0,
            year_start=None,
            year_end=None,
        )
        assert data["found"] is True
        assert "num_tracks" in data["entity_a"]["metrics"]
        assert "track_power_sum" in data["entity_a"]["metrics"]

    def test_versus_artist(self):
        from backend.services.billboard_service import get_versus_artist

        data = get_versus_artist(
            sel_a="Taylor Swift",
            sel_b="Olivia Rodrigo",
            min_ms=30000,
            music_only=True,
            bb_top_n=30,
            bb_album_top_n=20,
            bb_artist_top_n=20,
            bb_week_start_dow=4,
            bb_week_start_hour=0,
            year_start=None,
            year_end=None,
        )
        assert data["found"] is True
        assert "num_tracks" in data["entity_a"]["metrics"]
        assert "num_albums" in data["entity_a"]["metrics"]
        assert "album_power_sum" in data["entity_a"]["metrics"]


# ═══════════════════════════════════════════════════════════════════════════
# Release Cycle Service
# ═══════════════════════════════════════════════════════════════════════════


class TestReleaseCycleService:
    @pytest.fixture(scope="class")
    def _df_raw(self):
        from backend.services.billboard_service import load_billboard_raw

        return load_billboard_raw(30000, True, 4, 0)

    def test_load_artist_list(self, _df_raw):
        from backend.services.release_cycle_service import load_artist_list

        data = load_artist_list(_df_raw)
        assert len(data) > 100
        assert isinstance(data[0], dict)
        assert "artist_name" in data[0]
        assert "track_count" in data[0]
        assert data[0]["track_count"] > 0

    def test_load_artist_releases(self):
        from backend.services.release_cycle_service import load_artist_releases

        releases = load_artist_releases("Taylor Swift")
        assert len(releases) > 10
        cols = releases.columns.tolist()
        for c in ["album_name", "release_date", "album_type"]:
            assert c in cols

    def test_compute_artist_summary(self):
        from backend.services.billboard_service import (
            compute_album_weekly_rankings,
            compute_artist_weekly_rankings,
            compute_weekly_rankings,
            load_billboard_raw,
        )
        from backend.services.release_cycle_service import (
            compute_artist_summary,
            load_artist_releases,
        )

        df_raw = load_billboard_raw(30000, True, 4, 0)
        releases = load_artist_releases("Taylor Swift")
        weekly = compute_weekly_rankings(df_raw, 30)
        weekly_artist = compute_artist_weekly_rankings(df_raw, 20)
        weekly_album = compute_album_weekly_rankings(df_raw, 20)

        summary = compute_artist_summary(
            "Taylor Swift",
            releases,
            weekly,
            weekly_artist,
            weekly_album,
        )
        assert summary["total_albums"] > 0
        assert summary["total_singles"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# Genius Service (integration — requires DB)
# ═══════════════════════════════════════════════════════════════════════════


class TestGeniusService:
    def test_get_track_lyrics_cached(self):
        """Fetching the same track twice returns cached=True on second call."""
        from backend.core.db import get_db
        from backend.services.genius_service import _get_client, get_track_lyrics

        # Ensure we have a cached entry for a known track
        client = _get_client()
        if client is None:
            pytest.skip("Genius client not available")

        # Seed cache
        conn = get_db(readonly=False)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO track_lyrics (track_id, genius_song_id, lyrics_text, genius_url) VALUES (?, ?, ?, ?)",
                (
                    9999,
                    12345,
                    "[Verse]\nTest lyrics line 1\nTest lyrics line 2",
                    "https://genius.com/test",
                ),
            )
            conn.commit()
        finally:
            conn.close()

        result1 = get_track_lyrics(9999)
        assert result1["found"] is True
        assert result1["cached"] is True
        assert "[Verse]" in result1["lyrics"]
        assert result1["genius_url"] == "https://genius.com/test"

        # Clean up
        conn = get_db(readonly=False)
        try:
            conn.execute("DELETE FROM track_lyrics WHERE track_id = 9999")
            conn.commit()
        finally:
            conn.close()

    def test_get_track_lyrics_nonexistent_track(self):
        """Non-existent track_id returns found=False."""
        from backend.services.genius_service import get_track_lyrics

        result = get_track_lyrics(-1)
        assert result["found"] is False

    def test_get_track_genius_url_cached(self):
        """URL-only lookup returns genius_url from cache."""
        from backend.core.db import get_db
        from backend.services.genius_service import get_track_genius_url

        # Seed cache
        conn = get_db(readonly=False)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO track_lyrics (track_id, genius_song_id, lyrics_text, genius_url) VALUES (?, ?, ?, ?)",
                (9998, 12346, "lyrics", "https://genius.com/test-url"),
            )
            conn.commit()
        finally:
            conn.close()

        result = get_track_genius_url(9998)
        assert result["found"] is True
        assert result["genius_url"] == "https://genius.com/test-url"

        # Clean up
        conn = get_db(readonly=False)
        try:
            conn.execute("DELETE FROM track_lyrics WHERE track_id = 9998")
            conn.commit()
        finally:
            conn.close()

    def test_get_track_genius_url_nonexistent(self):
        """URL lookup for non-existent track returns found=False."""
        from backend.services.genius_service import get_track_genius_url

        result = get_track_genius_url(-1)
        assert result["found"] is False

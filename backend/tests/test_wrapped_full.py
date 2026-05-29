"""Tests for the full yearly wrapped endpoint."""

import pytest

from backend.core.db import get_db
from backend.models.wrapped import WrappedFullResponse
from backend.services.wrapped_service import get_wrapped_full


@pytest.fixture(scope="module")
def wrapped_2024_full(default_params):
    """Shared full wrapped payload for 2024.

    The full wrapped calculation is intentionally broad and costs about a
    second on real data, so compute it once and let individual tests assert
    their own slice of the response.
    """
    conn = get_db()
    try:
        data = get_wrapped_full(
            conn,
            min_ms=default_params["min_ms"],
            music_only=default_params["music_only"],
            merge_enabled=default_params["merge_enabled"],
            year=2024,
        )
    finally:
        conn.close()

    WrappedFullResponse.model_validate(data)
    return data


@pytest.fixture(scope="module")
def wrapped_1999_full(default_params):
    conn = get_db()
    try:
        data = get_wrapped_full(
            conn,
            min_ms=default_params["min_ms"],
            music_only=default_params["music_only"],
            merge_enabled=default_params["merge_enabled"],
            year=1999,
        )
    finally:
        conn.close()

    WrappedFullResponse.model_validate(data)
    return data


class TestWrappedFull:
    def test_full_valid_year(self, wrapped_2024_full):
        """验证 2024 年完整响应结构正确"""
        d = wrapped_2024_full
        assert d["year"] == 2024
        assert d["empty"] is False

        # Hero - 使用真实数据阈值
        h = d["hero"]
        assert h["total_plays"] > 10000
        assert h["total_minutes"] > 50000
        assert h["unique_tracks"] > 1000
        assert h["unique_artists"] > 200
        assert h["active_days"] > 100
        assert h["avg_minutes_per_day"] > 0

    def test_full_personality(self, wrapped_2024_full):
        """验证 7 维人格 + 主人格判定"""
        d = wrapped_2024_full
        p = d["personality"]
        assert p is not None
        assert "primary" in p
        assert "primary_label" in p
        assert "primary_desc" in p
        dims = p["dimensions"]
        assert len(dims) == 7
        for key in ["explorer", "loyalist", "binger", "night_owl", "collector", "trend_chaser", "globetrotter"]:
            assert key in dims, f"Missing dimension: {key}"
            assert "label" in dims[key]
            assert "score" in dims[key]
            assert "desc" in dims[key]
            assert 0 <= dims[key]["score"] <= 100, f"{key} score out of range: {dims[key]['score']}"

    def test_full_top_lists(self, wrapped_2024_full):
        """验证 Top 榜单结构 + cover_url"""
        d = wrapped_2024_full
        tl = d["top_lists"]
        assert len(tl["artists"]) == 5
        assert len(tl["tracks"]) == 5
        assert len(tl["albums"]) == 5
        # 排名降序
        assert tl["artists"][0]["hours"] >= tl["artists"][-1]["hours"]
        assert tl["tracks"][0]["plays"] >= tl["tracks"][-1]["plays"]
        # cover_url 字段存在
        for artist in tl["artists"]:
            assert "cover_url" in artist
        for track in tl["tracks"]:
            assert "cover_url" in track
        for album in tl["albums"]:
            assert "cover_url" in album

    def test_full_time_story(self, wrapped_2024_full):
        """验证时间故事结构"""
        d = wrapped_2024_full
        ts = d["time_story"]
        assert len(ts["daily_grid"]) == 12  # 12个月
        # 每月最多31天
        for row in ts["daily_grid"]:
            assert len(row) == 31
        assert len(ts["monthly_pulse"]) == 12
        assert [m["month"] for m in ts["monthly_pulse"]] == list(range(1, 13))
        assert len(ts["hourly_dist"]) == 24
        assert [h["hour"] for h in ts["hourly_dist"]] == list(range(24))
        assert "ratio" in ts["late_night"]
        assert 0 <= ts["late_night"]["ratio"] <= 100
        assert len(ts["late_night"]["top_tracks"]) >= 1
        for t in ts["late_night"]["top_tracks"]:
            assert "cover_url" in t

    def test_full_monthly_drilldown(self, wrapped_2024_full):
        """验证月度下钻 12 个月"""
        d = wrapped_2024_full
        md = d["monthly_drilldown"]
        assert len(md) == 12
        assert [m["month"] for m in md] == list(range(1, 13))
        for month_data in md:
            assert "month" in month_data
            assert 1 <= month_data["month"] <= 12
            assert "total_hours" in month_data
            assert "top_tracks" in month_data
            assert "top_artist" in month_data
            for t in month_data["top_tracks"]:
                assert "cover_url" in t

    def test_full_special_moments(self, wrapped_2024_full):
        """验证特殊时刻"""
        d = wrapped_2024_full
        sm = d["special_moments"]
        assert sm["most_active_day"] is not None
        assert sm["most_active_day"]["plays"] > 0
        assert sm["earliest_listen"] is not None
        assert sm["latest_listen"] is not None
        assert "cover_url" in sm["most_active_day"]["top_track"]
        assert "cover_url" in sm["earliest_listen"]["track"]
        assert "cover_url" in sm["latest_listen"]["track"]
        assert sm["longest_streak"] is not None
        assert sm["longest_streak"]["days"] > 0

    def test_full_empty_year(self, wrapped_1999_full):
        """验证空年份返回"""
        d = wrapped_1999_full
        assert d["empty"] is True
        assert d["hero"] is None
        assert d["top_lists"] is None

    def test_full_listening_depth(self, wrapped_2024_full):
        """验证收听深度"""
        d = wrapped_2024_full
        ld = d["listening_depth"]
        assert ld is not None
        assert "deep_listen_ratio" in ld
        assert 0 <= ld["deep_listen_ratio"] <= 100
        if ld["listening_age"] is not None:
            assert ld["listening_age"]["age"] > 0
            assert "description" in ld["listening_age"]

    def test_full_discovery_returns(self, wrapped_2024_full):
        """验证发现与回归"""
        d = wrapped_2024_full
        dr = d["discovery_returns"]
        assert dr is not None
        assert "new_artists" in dr
        assert "returning_tracks" in dr
        assert "longest_love" in dr
        for a in dr["new_artists"]:
            assert "cover_url" in a
        for t in dr["returning_tracks"]:
            assert "cover_url" in t
            assert t["release_year"] <= 2019
        if dr["longest_love"] is not None:
            assert "cover_url" in dr["longest_love"]
            assert dr["longest_love"]["span_days"] >= 0

    def test_full_comparison(self, wrapped_2024_full):
        """验证年度对比"""
        d = wrapped_2024_full
        comp = d["comparison"]
        assert comp is not None
        if comp["last_year"] is not None:
            assert "total_hours_change" in comp["last_year"]
        assert "top_vs_alltime" in comp
        assert set(comp["top_vs_alltime"]) == {"tracks", "artists"}
        for marks in comp["top_vs_alltime"].values():
            for mark in marks:
                assert mark["is_new"] != mark["is_classic"]

    def test_full_genre_panorama(self, wrapped_2024_full):
        """验证流派全景"""
        d = wrapped_2024_full
        gp = d["genre_panorama"]
        assert gp is not None
        assert "top_genres" in gp
        assert "monthly_genres" in gp
        assert len(gp["monthly_genres"]) == 12
        assert [m["month"] for m in gp["monthly_genres"]] == list(range(1, 13))

    def test_full_music_map(self, wrapped_2024_full):
        """验证后端直接输出音乐版图，避免前端重复推断口径"""
        mm = wrapped_2024_full["music_map"]
        assert mm is not None
        assert "regions" in mm
        assert "top_overseas_artists" in mm
        total_share = sum(r["play_share"] for r in mm["regions"])
        assert 99 <= total_share <= 101
        for region in mm["regions"]:
            assert region["region"]
            assert "flag" in region
            assert 0 <= region["play_share"] <= 100
        for artist in mm["top_overseas_artists"]:
            assert "cover_url" in artist

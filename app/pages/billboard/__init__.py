import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import html as _html
import json
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from app.pages.billboard.shared import (
    load_billboard_raw,
    load_track_album_map,
    compute_weekly_rankings,
    compute_album_weekly_rankings,
    compute_artist_weekly_rankings,
    compute_power_scores,
    compute_album_power_scores,
    compute_artist_power_scores,
    compute_records,
    DOW_NAMES,
    DOW_SHORT,
    _try_load_from_agg,
)
from app.pages.billboard.versus import (
    render_track_versus,
    render_album_versus,
    render_artist_versus,
)
from app.pages.billboard.weekly import render as render_weekly
from app.pages.billboard.number_ones import render as render_number_ones
from app.pages.billboard.track_history import render as render_track_history
from app.pages.billboard.artist_chart import render as render_artist_chart
from app.pages.billboard.album_chart import render as render_album_chart
from app.pages.billboard.power_score import render as render_power_score
from app.pages.billboard.all_time_tracks import render as render_all_time_tracks
from app.pages.billboard.all_time_artists import render as render_all_time_artists
from app.pages.billboard.all_time_albums import render as render_all_time_albums
from app.pages.billboard.records import render as render_records


def run():
    """Render the full Billboard page — called from 08_billboard.py entry point."""

    # ── Restore Billboard config from URL (persisted by Settings page) ──────
    _bb_cfg = st.query_params.get("bb_cfg")
    if _bb_cfg:
        try:
            cfg = json.loads(_bb_cfg)
            st.session_state.bb_top_n = cfg.get("tn", 30)
            st.session_state.bb_album_top_n = cfg.get("an", 20)
            st.session_state.bb_artist_top_n = cfg.get("arn", 20)
            st.session_state.bb_week_start_dow = cfg.get("dow", 4)
            st.session_state.bb_week_start_hour = cfg.get("hr", 0)
        except (json.JSONDecodeError, ValueError):
            pass

    # ── Session state defaults ────────────────────────────────────────────
    min_ms = st.session_state.get("min_ms", 30000)
    music_only = st.session_state.get("music_only", True)
    bb_week_start_dow = st.session_state.get("bb_week_start_dow", 4)  # Friday
    bb_week_start_hour = st.session_state.get("bb_week_start_hour", 0)

    # Cross-tab navigation
    if "bb_active_tab" not in st.session_state:
        st.session_state.bb_active_tab = "📋 周榜"
    if "bb_selected_track_id" not in st.session_state:
        st.session_state.bb_selected_track_id = None
    if "bb_selected_artist_name" not in st.session_state:
        st.session_state.bb_selected_artist_name = None
    if "bb_selected_album_name" not in st.session_state:
        st.session_state.bb_selected_album_name = None
    if "bb_selected_week" not in st.session_state:
        st.session_state.bb_selected_week = None
    if "_bb_selected_album_artist" not in st.session_state:
        st.session_state._bb_selected_album_artist = None

    # Widget-internal: radio 控件绑定的 key（与 bb_active_tab 解耦，避免 widget-key 冲突）
    if "_bb_tab_radio" not in st.session_state:
        st.session_state._bb_tab_radio = "📋 周榜"
    if "_bb_pending_tab" not in st.session_state:
        st.session_state._bb_pending_tab = None

    # ── 消费来自 HTML 表格 <a> 链接的 query param 导航 ─────────────────
    _nav_type = st.query_params.get("bb_nav")
    if _nav_type:
        if _nav_type == "track":
            try:
                st.session_state.bb_selected_track_id = int(st.query_params["bb_id"])
            except (ValueError, KeyError):
                pass
        elif _nav_type == "artist":
            st.session_state.bb_selected_artist_name = st.query_params.get("bb_name")
        elif _nav_type == "album":
            st.session_state.bb_selected_album_name = st.query_params.get("bb_name")
            st.session_state._bb_selected_album_artist = st.query_params.get("bb_art")
        elif _nav_type == "week":
            st.session_state.bb_selected_week = st.query_params.get("bb_date")
        # 目标 tab（来自 bb_tab 参数）
        _target_tab = st.query_params.get("bb_tab")
        if _target_tab:
            st.session_state._bb_pending_tab = _target_tab
        # 目标 sub-tab（周榜下的子 Tab）
        _target_subtab = st.query_params.get("bb_subtab")
        if _target_subtab is not None:
            try:
                st.session_state.bb_weekly_subtab = int(_target_subtab)
            except (ValueError, TypeError):
                pass
        st.query_params.clear()
        st.rerun()

    if "bb_top_n" not in st.session_state:
        st.session_state.bb_top_n = 30
    if "bb_weekly_subtab" not in st.session_state:
        st.session_state.bb_weekly_subtab = 0

    # Album & Artist Top N (from settings, with fallback defaults)
    bb_album_top_n = st.session_state.get("bb_album_top_n", 20)
    bb_artist_top_n = st.session_state.get("bb_artist_top_n", 20)

    # Tab 4/5 selectbox keys for programmatic index control
    if "bb_artist_selector_idx" not in st.session_state:
        st.session_state.bb_artist_selector_idx = 0
    if "bb_album_selector_idx" not in st.session_state:
        st.session_state.bb_album_selector_idx = 0


    # ── Load data ─────────────────────────────────────────────────────────
    try:
        df_raw = load_billboard_raw(min_ms, music_only, bb_week_start_dow, bb_week_start_hour)
        album_map = load_track_album_map()
    except Exception as e:
        st.error(f"数据加载失败：{e}")
        st.stop()

    # Detect config changes from Settings page → clear caches to force recomputation
    if "_applied_bb_top_n" not in st.session_state:
        st.session_state._applied_bb_top_n = st.session_state.bb_top_n
    if "_applied_bb_week_dow" not in st.session_state:
        st.session_state._applied_bb_week_dow = bb_week_start_dow
    if "_applied_bb_week_hour" not in st.session_state:
        st.session_state._applied_bb_week_hour = bb_week_start_hour
    if "_applied_bb_album_top_n" not in st.session_state:
        st.session_state._applied_bb_album_top_n = bb_album_top_n
    if "_applied_bb_artist_top_n" not in st.session_state:
        st.session_state._applied_bb_artist_top_n = bb_artist_top_n

    _config_changed = False
    if st.session_state.bb_top_n != st.session_state._applied_bb_top_n:
        st.session_state._applied_bb_top_n = st.session_state.bb_top_n
        _config_changed = True
    if bb_album_top_n != st.session_state._applied_bb_album_top_n:
        st.session_state._applied_bb_album_top_n = bb_album_top_n
        _config_changed = True
    if bb_artist_top_n != st.session_state._applied_bb_artist_top_n:
        st.session_state._applied_bb_artist_top_n = bb_artist_top_n
        _config_changed = True
    if bb_week_start_dow != st.session_state._applied_bb_week_dow:
        st.session_state._applied_bb_week_dow = bb_week_start_dow
        _config_changed = True
    if bb_week_start_hour != st.session_state._applied_bb_week_hour:
        st.session_state._applied_bb_week_hour = bb_week_start_hour
        _config_changed = True
    if _config_changed:
        st.cache_data.clear()
        st.rerun()

    # ── Billboard-specific filters (sidebar) ─────────────────────────────
    # Compute available years from all_weeks (before year filtering)
    raw_years = sorted(df_raw["billboard_week"].apply(lambda x: x.year).unique())

    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;margin-bottom:0.5rem;">'
            '<div style="font-size:2rem;margin-bottom:0.25rem;">📈</div>'
            '<div style="font-size:1.05rem;font-weight:700;color:#2C2416;">Billboard 周榜</div>'
            f'<div style="font-size:0.68rem;color:#8B7355;margin-top:0.15rem;">最短 {min_ms // 1000}s · '
            f'{"仅音乐" if music_only else "含播客"}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.divider()

        st.subheader("榜单数据过滤")

        bb_year_range = st.select_slider(
            "年份范围",
            options=raw_years,
            value=(raw_years[0], raw_years[-1]),
        )

        st.divider()

        # Top N — controlled from Settings page
        st.caption(
            f"单曲 Top {st.session_state.bb_top_n} · "
            f"专辑 Top {bb_album_top_n} · "
            f"艺人 Top {bb_artist_top_n}（在「⚙️ 设置」中调整）"
        )

    # Apply year-range post-load filter (min_ms already handled at SQL level)
    df_raw = df_raw.copy()  # avoid mutating cached DataFrame
    df_raw["_year"] = df_raw["billboard_week"].apply(lambda x: x.year)
    df_filtered = df_raw[
        (df_raw["_year"] >= bb_year_range[0])
        & (df_raw["_year"] <= bb_year_range[1])
    ].copy()

    # Weeks sorted DESC (newest first) for selectors; ASC for LW calculation
    all_weeks_desc = sorted(df_filtered["billboard_week"].unique().tolist(), reverse=True)
    all_weeks_asc = sorted(df_filtered["billboard_week"].unique().tolist())
    all_weeks_str = [f"{w} ({DOW_SHORT[bb_week_start_dow]})" for w in all_weeks_desc]

    st.caption(
        f"统计周期：每{DOW_NAMES[bb_week_start_dow]} {bb_week_start_hour:02d}:00 — "
        f"下{DOW_NAMES[bb_week_start_dow]} {bb_week_start_hour:02d}:00（北京时间）| "
        f"规则：播放次数相同按总收听时长排 | "
        f"共 {len(all_weeks_asc)} 周 · {len(df_filtered):,} 条过滤后记录"
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Compute rankings (try pre-aggregated tables first for speed)
    # ═══════════════════════════════════════════════════════════════════════
    top_n = st.session_state.bb_top_n
    _agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(
        min_ms, music_only, bb_week_start_dow, bb_week_start_hour
    )

    if _agg_tracks is not None:
        # Filter pre-aggregated data to selected year range
        # billboard_week may be str (from agg tables) or date (from raw path)
        _agg_tracks = _agg_tracks[
            pd.to_datetime(_agg_tracks["billboard_week"]).dt.year.between(
                bb_year_range[0], bb_year_range[1]
            )
        ]
        _agg_albums = _agg_albums[
            pd.to_datetime(_agg_albums["billboard_week"]).dt.year.between(
                bb_year_range[0], bb_year_range[1]
            )
        ]
        _agg_artists = _agg_artists[
            pd.to_datetime(_agg_artists["billboard_week"]).dt.year.between(
                bb_year_range[0], bb_year_range[1]
            )
        ]

    weekly = compute_weekly_rankings(df_filtered, top_n, pre_agg=_agg_tracks)
    weekly_album = compute_album_weekly_rankings(df_filtered, bb_album_top_n, pre_agg=_agg_albums)
    weekly_artist = compute_artist_weekly_rankings(df_filtered, bb_artist_top_n, pre_agg=_agg_artists)

    # Patch tracks_count from weekly (singles) chart — pre-aggregated tables lack track-level data
    if _agg_tracks is not None:
        _album_tc = (
            weekly.groupby(["billboard_week", "album_name", "artist_name"])
            .agg(tracks_count=("track_id", "nunique"))
            .reset_index()
        )
        weekly_album = weekly_album.drop(columns=["tracks_count"], errors="ignore").merge(
            _album_tc, on=["billboard_week", "album_name", "artist_name"], how="left"
        )
        weekly_album["tracks_count"] = weekly_album["tracks_count"].fillna(0).astype(int)

        _artist_tc = (
            weekly.groupby(["billboard_week", "artist_name"])
            .agg(tracks_count=("track_id", "nunique"))
            .reset_index()
        )
        weekly_artist = weekly_artist.drop(columns=["tracks_count"], errors="ignore").merge(
            _artist_tc, on=["billboard_week", "artist_name"], how="left"
        )
        weekly_artist["tracks_count"] = weekly_artist["tracks_count"].fillna(0).astype(int)

    # Patch albums_count for weekly_artist: number of albums on album chart that week
    _artist_ac = (
        weekly_album.groupby(["billboard_week", "artist_name"])
        .agg(albums_count=("album_name", "nunique"))
        .reset_index()
    )
    weekly_artist = weekly_artist.merge(
        _artist_ac, on=["billboard_week", "artist_name"], how="left"
    )
    weekly_artist["albums_count"] = weekly_artist["albums_count"].fillna(0).astype(int)

    # Build track-level summary (peak, weeks on chart, etc.)
    track_summary = (
        weekly.groupby(["track_id", "track_name", "artist_name", "album_name"])
        .agg(
            peak_position=("rank", "min"),
            weeks_on_chart=("billboard_week", "nunique"),
            weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
            first_week=("billboard_week", "min"),
            last_week=("billboard_week", "max"),
            total_chart_plays=("play_count", "sum"),
        )
        .reset_index()
    )

    # Total plays per track (all-time, for single-track detail cards)
    track_total_plays = (
        df_filtered.groupby("track_id")
        .agg(total_plays=("ms_played", "count"))
        .reset_index()
    )
    track_summary = track_summary.merge(track_total_plays, on="track_id", how="left")

    # Weeks at #1 per track
    weeks_at_no1 = (
        weekly[weekly["rank"] == 1]
        .groupby("track_id")
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
    )
    track_summary = track_summary.merge(weeks_at_no1, on="track_id", how="left")
    track_summary["weeks_at_no1"] = track_summary["weeks_at_no1"].fillna(0).astype(int)

    # First week at peak position
    first_peak = weekly.merge(
        track_summary[["track_id", "peak_position"]], on="track_id"
    )
    first_peak = first_peak[first_peak["rank"] == first_peak["peak_position"]]
    first_peak = first_peak.groupby("track_id")["billboard_week"].min().reset_index()
    first_peak.columns = ["track_id", "first_peak_week"]
    track_summary = track_summary.merge(first_peak, on="track_id", how="left")

    # Add running peak weeks to weekly (cumulative count of weeks at all-time peak)
    wp = weekly.merge(
        track_summary[["track_id", "peak_position"]], on="track_id", how="left"
    )
    wp = wp.sort_values(["track_id", "billboard_week"])
    wp["at_peak"] = (wp["rank"] == wp["peak_position"]).astype(int)
    wp["running_peak_wks"] = wp.groupby("track_id")["at_peak"].cumsum()
    weekly = wp.drop(columns=["peak_position", "at_peak"])

    # ── Pre-compute artist / album summary DataFrames (used by Tabs 3,5,7,8) ─
    artist_summary = (
        weekly.groupby(["artist_name", "track_id", "track_name", "album_name"])
        .agg(
            peak_position=("rank", "min"),
            weeks_on_chart=("billboard_week", "nunique"),
            weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
            first_week=("billboard_week", "min"),
            last_week=("billboard_week", "max"),
            total_chart_plays=("play_count", "sum"),
        )
        .reset_index()
    )

    artist_track_counts = (
        artist_summary.groupby("artist_name")
        .agg(
            total_tracks=("track_id", "nunique"),
            best_peak=("peak_position", "min"),
            total_weeks=("weeks_on_chart", "sum"),
            avg_weeks=("weeks_on_chart", "mean"),
            top1=("peak_position", lambda x: (x == 1).sum()),
            top5=("peak_position", lambda x: (x <= 5).sum()),
            top10=("peak_position", lambda x: (x <= 10).sum()),
        )
        .reset_index()
        .sort_values("total_tracks", ascending=False)
    )
    artist_track_counts["best_peak_track"] = artist_track_counts["artist_name"].apply(
        lambda a: artist_summary[artist_summary["artist_name"] == a]
        .sort_values("peak_position")
        .iloc[0]["track_name"]
    )

    # Artist weeks at #1 (sum of all tracks' weeks at #1)
    artist_weeks_no1 = (
        track_summary.groupby("artist_name")["weeks_at_no1"]
        .sum()
        .reset_index()
    )
    artist_track_counts = artist_track_counts.merge(artist_weeks_no1, on="artist_name", how="left")

    # Album #1 metrics per artist (from weekly_album)
    album_no1_artist = weekly_album[weekly_album["rank"] == 1].groupby("artist_name").agg(
        num_no1_albums=("album_name", "nunique"),
        album_no1_weeks=("billboard_week", "nunique"),
    ).reset_index()
    artist_track_counts = artist_track_counts.merge(album_no1_artist, on="artist_name", how="left")
    artist_track_counts["num_no1_albums"] = artist_track_counts["num_no1_albums"].fillna(0).astype(int)
    artist_track_counts["album_no1_weeks"] = artist_track_counts["album_no1_weeks"].fillna(0).astype(int)

    # Artist chart #1 weeks (from weekly_artist)
    artist_no1_weeks = weekly_artist[weekly_artist["rank"] == 1].groupby("artist_name").agg(
        artist_chart_no1_weeks=("billboard_week", "nunique"),
    ).reset_index()
    artist_track_counts = artist_track_counts.merge(artist_no1_weeks, on="artist_name", how="left")
    artist_track_counts["artist_chart_no1_weeks"] = artist_track_counts["artist_chart_no1_weeks"].fillna(0).astype(int)

    # Album expanded view (track → all its albums via album_map)
    ts_for_album = track_summary.drop(columns=["album_name"])
    track_albums_expanded = ts_for_album.merge(album_map, on="track_id", how="left")
    track_albums_expanded["album_list"] = track_albums_expanded["album_list"].apply(
        lambda x: x if isinstance(x, list) else []
    )
    track_per_album = track_albums_expanded.explode("album_list")
    track_per_album = track_per_album.dropna(subset=["album_list"])
    track_per_album = track_per_album.rename(columns={"album_list": "album_name"})

    album_track_counts = (
        track_per_album.groupby(["album_name", "artist_name"])
        .agg(
            total_tracks=("track_id", "nunique"),
            best_peak=("peak_position", "min"),
            total_weeks=("weeks_on_chart", "sum"),
            avg_weeks=("weeks_on_chart", "mean"),
            top1=("peak_position", lambda x: (x == 1).sum()),
            top5=("peak_position", lambda x: (x <= 5).sum()),
            top10=("peak_position", lambda x: (x <= 10).sum()),
        )
        .reset_index()
        .sort_values("total_tracks", ascending=False)
    )
    album_track_counts["best_peak_track"] = album_track_counts.apply(
        lambda r: track_per_album[
            (track_per_album["album_name"] == r["album_name"])
            & (track_per_album["artist_name"] == r["artist_name"])
        ]
        .sort_values("peak_position")
        .iloc[0]["track_name"],
        axis=1,
    )

    # Album weeks at #1 (sum of all tracks' weeks at #1 per album)
    # track_per_album already has weeks_at_no1 from track_summary via ts_for_album
    album_weeks_no1 = (
        track_per_album.groupby(["album_name", "artist_name"])["weeks_at_no1"]
        .sum()
        .reset_index()
    )
    album_track_counts = album_track_counts.merge(album_weeks_no1, on=["album_name", "artist_name"], how="left")

    # Album #1 weeks (from weekly_album)
    album_no1 = weekly_album[weekly_album["rank"] == 1].groupby(["album_name", "artist_name"]).agg(
        album_chart_no1_weeks=("billboard_week", "nunique"),
    ).reset_index()
    album_track_counts = album_track_counts.merge(album_no1, on=["album_name", "artist_name"], how="left")
    album_track_counts["album_chart_no1_weeks"] = album_track_counts["album_chart_no1_weeks"].fillna(0).astype(int)

    # ── Compute Records ────────────────────────────────────────────────────
    records = compute_records(weekly, track_summary, top_n, weekly_album, weekly_artist)

    # ── Tabs (radio + CSS styled as tabs for programmatic control) ────────
    TAB_NAMES = [
        "📋 周榜", "👑 每周榜首", "🎵 单曲历史", "🎤 艺人榜单", "💿 专辑榜单",
        "⭐ 走势总榜", "🏆 歌曲总榜", "📊 艺人总榜", "📀 专辑总榜",
        "🏅 榜单记录", "⚔️ 对决",
    ]

    # 消费来自 query param 导航的待处理 tab 切换请求
    _pending = st.session_state.pop("_bb_pending_tab", None)
    if _pending is not None and _pending in TAB_NAMES:
        st.session_state._bb_tab_radio = _pending
    if "_bb_tab_radio" not in st.session_state:
        st.session_state._bb_tab_radio = TAB_NAMES[0]

    st.markdown("""
    <style>
    /* ── Billboard Tab Bar ─────────────────────────────────────────────── */
    div[data-testid="stRadio"]:has(input[value="📋 周榜"]) > div[role="radiogroup"] {
      display: flex !important;
      flex-direction: row !important;
      gap: 0.25rem !important;
      border-bottom: 1.5px solid rgba(184, 134, 11, 0.20) !important;
      margin-bottom: 1.75rem !important;
      padding-bottom: 0 !important;
      overflow-x: auto !important;
      flex-wrap: nowrap !important;
      -webkit-overflow-scrolling: touch;
    }

    div[data-testid="stRadio"]:has(input[value="📋 周榜"]) label {
      padding: 0.6rem 0.9rem !important;
      border-radius: 10px 10px 0 0 !important;
      color: #8B7355 !important;
      font-family: "Palatino", "Book Antiqua", serif !important;
      font-size: 0.82rem !important;
      font-weight: 500 !important;
      border-bottom: 2.5px solid transparent !important;
      margin-bottom: -1.5px !important;
      cursor: pointer !important;
      transition: all 0.2s ease !important;
      white-space: nowrap !important;
      background: transparent !important;
      letter-spacing: 0.01em;
    }

    div[data-testid="stRadio"]:has(input[value="📋 周榜"]) label:hover {
      color: #2C2416 !important;
      background: rgba(184, 134, 11, 0.06) !important;
      border-bottom-color: rgba(184, 134, 11, 0.25) !important;
    }

    div[data-testid="stRadio"]:has(input[value="📋 周榜"]) input[type="radio"] {
      display: none !important;
    }

    div[data-testid="stRadio"]:has(input[value="📋 周榜"]) label:has(input:checked) {
      color: #B8860B !important;
      font-weight: 600 !important;
      border-bottom: 2.5px solid #B8860B !important;
      background: linear-gradient(180deg, rgba(184,134,11,0.04) 0%, rgba(184,134,11,0.01) 100%) !important;
    }

    /* ── Billboard HTML Tables ─────────────────────────────────────────── */
    .bb-table-container {
      border: 1px solid rgba(139, 115, 85, 0.12);
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 1rem;
    }
    .bb-table {
      width: 100%;
      border-collapse: collapse;
      font-family: "Palatino", "Book Antiqua", serif;
      font-size: 0.82rem;
      color: #2C2416;
    }
    .bb-table thead {
      background: #F5EDDA;
      border-bottom: 2px solid rgba(184, 134, 11, 0.25);
    }
    .bb-table th {
      padding: 0.6rem 0.75rem;
      text-align: left;
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #8B7355;
      font-weight: 600;
    }
    .bb-table td {
      padding: 0.5rem 0.75rem;
      border-bottom: 1px solid rgba(139, 115, 85, 0.06);
      background: #FFFFFF;
    }
    .bb-table tbody tr:hover td {
      background: #FDF8EF;
      transition: background 0.15s ease;
    }
    .bb-table a {
      color: #2C2416;
      text-decoration: none;
      border-bottom: 1px dotted rgba(184, 134, 11, 0.45);
      transition: all 0.15s ease;
    }
    .bb-table a:hover {
      color: #B8860B;
      border-bottom-color: #B8860B;
    }
    .bb-table .bb-rank { text-align: center; font-weight: 600; width: 3rem; }
    .bb-table .bb-num { text-align: right; font-variant-numeric: tabular-nums; }
    .bb-table .bb-num-wide { text-align: right; font-variant-numeric: tabular-nums; }
    .bb-table .bb-text { text-align: left; }
    </style>
    """, unsafe_allow_html=True)

    st.radio(
        "导航",
        options=TAB_NAMES,
        key="_bb_tab_radio",
        label_visibility="collapsed",
        horizontal=True,
    )
    # 将 radio 内部值同步到公开的 bb_active_tab
    st.session_state.bb_active_tab = st.session_state._bb_tab_radio


    # ═══════════════════════════════════════════════════════════════════════
    # Tab 1: Weekly Chart
    # ═══════════════════════════════════════════════════════════════════════
    if st.session_state.bb_active_tab == "📋 周榜":
        render_weekly(weekly, weekly_album, weekly_artist, track_summary, all_weeks_desc, all_weeks_asc, all_weeks_str, top_n, bb_album_top_n, bb_artist_top_n)
    # ═══════════════════════════════════════════════════════════════════════
    elif st.session_state.bb_active_tab == "🎵 单曲历史":
        render_track_history(weekly, track_summary, top_n, all_weeks_str, all_weeks_desc)
    # ═══════════════════════════════════════════════════════════════════════
    elif st.session_state.bb_active_tab == "🎤 艺人榜单":
        render_artist_chart(weekly, weekly_artist, weekly_album, artist_track_counts, artist_summary, track_summary, bb_artist_top_n, top_n, bb_album_top_n)
    # ═══════════════════════════════════════════════════════════════════════
    elif st.session_state.bb_active_tab == "⭐ 走势总榜":
        render_power_score(weekly, weekly_album, weekly_artist, top_n, bb_album_top_n, bb_artist_top_n)

    elif st.session_state.bb_active_tab == "🏆 歌曲总榜":
        render_all_time_tracks(track_summary, weekly)
    # ═══════════════════════════════════════════════════════════════════════
    elif st.session_state.bb_active_tab == "💿 专辑榜单":
        render_album_chart(weekly, weekly_album, track_per_album, album_track_counts, bb_album_top_n, top_n)
    # ═══════════════════════════════════════════════════════════════════════
    elif st.session_state.bb_active_tab == "👑 每周榜首":
        render_number_ones(weekly, weekly_album, weekly_artist, track_summary)
    # ═══════════════════════════════════════════════════════════════════════
    elif st.session_state.bb_active_tab == "📊 艺人总榜":
        render_all_time_artists(artist_track_counts)
    # ═══════════════════════════════════════════════════════════════════════
    elif st.session_state.bb_active_tab == "📀 专辑总榜":
        render_all_time_albums(album_track_counts)
    # ═══════════════════════════════════════════════════════════════════════
    elif st.session_state.bb_active_tab == "🏅 榜单记录":
        render_records(records)
    # ═══════════════════════════════════════════════════════════════════════════
    elif st.session_state.bb_active_tab == "⚔️ 对决":
        power_scores = compute_power_scores(weekly, top_n)
        album_power_scores = compute_album_power_scores(weekly_album, bb_album_top_n)
        artist_power_scores = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

        versus_tabs = st.tabs(["🎵 歌曲对决", "💿 专辑对决", "🎤 艺人对决"])

        with versus_tabs[0]:
            render_track_versus(weekly, track_summary, power_scores)

        with versus_tabs[1]:
            render_album_versus(weekly_album, weekly, album_power_scores, power_scores)

        with versus_tabs[2]:
            render_artist_versus(weekly_artist, weekly, weekly_album, artist_power_scores, power_scores, album_power_scores)


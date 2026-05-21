"""Leaderboard: top tracks, artists, albums with time range and metric selectors."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px

from app.db import get_db, load_plays
from app.styles import inject_global_styles, page_header

inject_global_styles()

min_ms = st.session_state.get("min_ms", 30000)
music_only = st.session_state.get("music_only", True)
merge_enabled = st.session_state.get("merge_enabled", True)


@st.cache_data(ttl=3600)
def load_leaderboard_data(_min_ms, _music_only, _merge_enabled):
    conn = get_db()
    df = load_plays(conn, min_ms=_min_ms, music_only=_music_only, merge_enabled=_merge_enabled)
    conn.close()
    return df


def render():
    try:
        df = load_leaderboard_data(min_ms, music_only, merge_enabled)
    except Exception as e:
        st.error(f"加载排行榜数据失败：{e}")
        return

    years = sorted(df["ts_year"].unique().tolist(), reverse=True)
    months = sorted(df["ts_year"].astype(str) + "-" + df["ts_month"].astype(str).str.zfill(2))[::-1]

    page_header("🏆 排行榜", description=f"按不同维度浏览排行 · 最短={min_ms//1000}s")

    # Controls (inline — was sidebar)
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        entity_type = st.radio("排行对象", ["曲目", "艺人", "专辑"])
    with col_c2:
        time_range = st.selectbox("时间范围", ["全部", "今年", "本月", "自定义年份"])
        if time_range == "自定义年份":
            selected_year = st.selectbox("选择年份", years, index=0)
        elif time_range == "本月":
            if months:
                selected_month = st.selectbox("选择月份", months, index=0)
    with col_c3:
        metric = st.radio("排行指标", ["播放次数", "总时长 (小时)"])
        top_n = st.slider("Top N", 5, 100, 20, step=5)

    # ── Filter by time range ────────────────────────────────────────────
    filtered = df.copy()
    time_label = "全部时间"

    if time_range == "今年":
        current_year = pd.Timestamp.now().year
        filtered = filtered[filtered["ts_year"] == current_year]
        time_label = f"{current_year}年"
    elif time_range == "本月":
        if months:
            parts = selected_month.split("-")
            yr, mo = int(parts[0]), int(parts[1])
            filtered = filtered[(filtered["ts_year"] == yr) & (filtered["ts_month"] == mo)]
            time_label = f"{yr}年{mo}月"
    elif time_range == "自定义年份":
        filtered = filtered[filtered["ts_year"] == selected_year]
        time_label = f"{selected_year}年"

    st.caption(f"数据范围：{time_label} | 共 {len(filtered):,} 条播放记录")

    # ── Compute rankings ────────────────────────────────────────────────
    if entity_type == "曲目":
        group_cols = ["track_name", "artist_name", "spotify_track_uri"]
    elif entity_type == "艺人":
        group_cols = ["artist_name"]
    else:
        group_cols = ["album_name", "artist_name"]

    if entity_type == "曲目":
        ranked = (
            filtered.groupby(group_cols)
            .agg(
                plays=("play_id", "count"),
                hours=("ms_played", lambda x: x.sum() / 3_600_000),
            )
            .reset_index()
        )
    elif entity_type == "艺人":
        ranked = (
            filtered.groupby("artist_name")
            .agg(
                plays=("play_id", "count"),
                hours=("ms_played", lambda x: x.sum() / 3_600_000),
                unique_tracks=("track_id", "nunique"),
            )
            .reset_index()
        )
    else:
        ranked = (
            filtered.groupby(["album_name", "artist_name"])
            .agg(
                plays=("play_id", "count"),
                hours=("ms_played", lambda x: x.sum() / 3_600_000),
            )
            .reset_index()
        )

    sort_col = "plays" if metric == "播放次数" else "hours"
    ranked = ranked.sort_values(sort_col, ascending=False).head(top_n).reset_index(drop=True)
    ranked.index = ranked.index + 1
    ranked.index.name = "#"

    # ── Display ─────────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#2C2416;margin-bottom:0.75rem;">📋 排行表格</div>', unsafe_allow_html=True)
        display_cols = [sort_col]
        if entity_type == "曲目":
            display_cols = ["track_name", "artist_name", "plays", "hours"]
            ranked_display = ranked[display_cols].copy()
            ranked_display.columns = ["曲目", "艺人", "播放次数", "时长(小时)"]
        elif entity_type == "艺人":
            display_cols = ["artist_name", "plays", "hours", "unique_tracks"]
            ranked_display = ranked[display_cols].copy()
            ranked_display.columns = ["艺人", "播放次数", "时长(小时)", "独特曲目"]
        else:
            display_cols = ["album_name", "artist_name", "plays", "hours"]
            ranked_display = ranked[display_cols].copy()
            ranked_display.columns = ["专辑", "艺人", "播放次数", "时长(小时)"]

        ranked_display["时长(小时)"] = ranked_display["时长(小时)"].round(1)
        st.dataframe(ranked_display, use_container_width=True)
        st.download_button(
            f"导出 CSV ({entity_type} Top {top_n})",
            ranked_display.to_csv(index=False).encode("utf-8"),
            f"spotify_{entity_type}_top{top_n}.csv",
            "text/csv",
        )

    with col2:
        st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#2C2416;margin-bottom:0.75rem;">📊 图表</div>', unsafe_allow_html=True)
        if entity_type == "曲目":
            y_col = "track_name"
            hover_data = ["artist_name"]
        elif entity_type == "艺人":
            y_col = "artist_name"
            hover_data = None
        else:
            y_col = "album_name"
            hover_data = ["artist_name"]

        fig = px.bar(
            ranked.head(20),
            x=sort_col,
            y=y_col,
            orientation="h",
            hover_data=hover_data,
            labels={sort_col: metric, y_col: ""},
            height=600,
            title=f"Top {top_n} {entity_type} — {metric}",
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

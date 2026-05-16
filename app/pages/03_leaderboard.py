"""Leaderboard: top tracks, artists, albums with time range and metric selectors."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px

from app.db import get_db, base_filters
from app.styles import inject_global_styles, page_header

st.set_page_config(page_title="排行榜", page_icon="🏆", layout="wide")
inject_global_styles()

min_ms = st.session_state.get("min_ms", 30000)
exclude_skipped = st.session_state.get("exclude_skipped", True)
music_only = st.session_state.get("music_only", True)


@st.cache_data(ttl=3600)
def load_leaderboard_data(_min_ms, _exclude_skipped, _music_only):
    conn = get_db()
    _f, _fp = base_filters(min_ms=_min_ms, exclude_skipped=_exclude_skipped, music_only=_music_only)
    _w = f"WHERE {_f}" if _f else ""
    df = pd.read_sql_query(
        f"""SELECT p.*, t.track_name, t.spotify_track_uri, a.artist_name, al.album_name
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN artists a ON t.artist_id = a.artist_id
            LEFT JOIN albums al ON t.album_id = al.album_id
            {_w}""",
        conn,
        params=_fp,
    )
    conn.close()
    return df


df = load_leaderboard_data(min_ms, exclude_skipped, music_only)

years = sorted(df["ts_year"].unique().tolist(), reverse=True)
months = sorted(df["ts_year"].astype(str) + "-" + df["ts_month"].astype(str).str.zfill(2))[::-1]

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        '<div style="font-size:2rem;margin-bottom:0.25rem;">🏆</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#F0F0F5;">排行榜</div>'
        f'<div style="font-size:0.7rem;color:#8888A0;margin-top:0.15rem;">跳过=否，最短={min_ms//1000}s</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.divider()
    entity_type = st.radio("排行对象", ["曲目", "艺人", "专辑"])

    st.divider()
    time_range = st.selectbox("时间范围", ["全部", "今年", "本月", "自定义年份"])
    if time_range == "自定义年份":
        selected_year = st.selectbox("选择年份", years, index=0)
    elif time_range == "本月":
        if months:
            selected_month = st.selectbox("选择月份", months, index=0)

    st.divider()
    metric = st.radio("排行指标", ["播放次数", "总时长 (小时)"])

    top_n = st.slider("Top N", 5, 100, 20, step=5)

page_header(f"🏆 {entity_type}排行榜")

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
            skip_rate=("skipped", "mean"),
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
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#F0F0F5;margin-bottom:0.75rem;">📋 排行表格</div>', unsafe_allow_html=True)
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

with col2:
    st.markdown('<div style="font-size:1.1rem;font-weight:600;color:#F0F0F5;margin-bottom:0.75rem;">📊 图表</div>', unsafe_allow_html=True)
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

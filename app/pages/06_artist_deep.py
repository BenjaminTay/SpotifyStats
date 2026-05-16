"""Per-artist and per-album deep-dive analysis."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.db import get_db, base_filters
from app.styles import inject_global_styles, page_header

st.set_page_config(page_title="艺人深度分析", page_icon="🎸", layout="wide")
inject_global_styles()

min_ms = st.session_state.get("min_ms", 30000)
exclude_skipped = st.session_state.get("exclude_skipped", True)
music_only = st.session_state.get("music_only", True)


@st.cache_data(ttl=3600)
def load_artist_data(_min_ms, _exclude_skipped, _music_only):
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


@st.cache_data(ttl=3600)
def get_artist_list(_min_ms, _exclude_skipped, _music_only):
    conn = get_db()
    _f, _fp = base_filters(min_ms=_min_ms, exclude_skipped=_exclude_skipped, music_only=_music_only)
    _w = f"WHERE {_f}" if _f else ""
    rows = conn.execute(
        f"""SELECT a.artist_id, a.artist_name, COUNT(*) as cnt
            FROM plays p
            JOIN tracks t ON p.track_id = t.track_id
            JOIN artists a ON t.artist_id = a.artist_id
            {_w}
            GROUP BY a.artist_id
            ORDER BY cnt DESC""",
        _fp,
    ).fetchall()
    conn.close()
    return [(r[0], r[1], r[2]) for r in rows]


df = load_artist_data(min_ms, exclude_skipped, music_only)
artist_list = get_artist_list(min_ms, exclude_skipped, music_only)
artist_names = [f"{name} ({cnt}次)" for _, name, cnt in artist_list]

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        '<div style="font-size:2rem;margin-bottom:0.25rem;">🎸</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#F0F0F5;">艺人深度</div>'
        f'<div style="font-size:0.7rem;color:#8888A0;margin-top:0.15rem;">跳过=否，最短={min_ms//1000}s</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    selected_idx = st.selectbox(
        "选择艺人",
        options=range(len(artist_names)),
        format_func=lambda i: artist_names[i],
        index=0,
    )
    selected_artist_id, selected_artist_name, _ = artist_list[selected_idx]

# Filter to selected artist
artist_df = df[df["artist_name"] == selected_artist_name]
total_plays = len(artist_df)
total_hours = artist_df["ms_played"].sum() / 3_600_000
unique_tracks = artist_df["track_id"].nunique()
first_date = artist_df["ts_date"].min()
last_date = artist_df["ts_date"].max()

# ── Stats cards ─────────────────────────────────────────────────────
page_header(f"🎸 {selected_artist_name}", description=f"共 {total_plays:,} 次播放 · {total_hours:,.1f} 小时 · {unique_tracks} 首曲目")

col1, col2, col3, col4 = st.columns(4)
col1.metric("总播放次数", f"{total_plays:,}")
col2.metric("总时长", f"{total_hours:,.1f} 小时")
col3.metric("独特曲目", f"{unique_tracks}")
col4.metric("时间跨度", f"{first_date} → {last_date}")

st.divider()

# ── Monthly activity ────────────────────────────────────────────────
st.subheader("月度活跃度")

monthly = (
    artist_df.groupby(["ts_year", "ts_month"])
    .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
    .reset_index()
)
monthly["label"] = monthly["ts_year"].astype(str) + "-" + monthly["ts_month"].astype(str).str.zfill(2)
monthly = monthly.sort_values(["ts_year", "ts_month"])

fig = px.bar(
    monthly,
    x="label",
    y="hours",
    labels={"label": "月份", "hours": "总时长 (小时)"},
    title=f"{selected_artist_name} — 月度听歌时长",
)
st.plotly_chart(fig, use_container_width=True)

# ── Top tracks ──────────────────────────────────────────────────────
col5, col6 = st.columns([3, 2])

with col5:
    st.subheader("Top 曲目排行榜")

    top_tracks = (
        artist_df.groupby("track_name")
        .agg(
            plays=("play_id", "count"),
            hours=("ms_played", lambda x: x.sum() / 3_600_000),
            skip_rate=("skipped", "mean"),
        )
        .sort_values("plays", ascending=False)
        .head(20)
        .reset_index()
    )
    top_tracks["hours"] = top_tracks["hours"].round(1)
    top_tracks["skip_rate"] = (top_tracks["skip_rate"] * 100).round(1)
    top_tracks.index = top_tracks.index + 1
    top_tracks.index.name = "#"

    st.dataframe(
        top_tracks.rename(columns={"track_name": "曲目", "plays": "次数", "hours": "时长(小时)", "skip_rate": "跳过率(%)"}),
        use_container_width=True,
    )

with col6:
    st.subheader("专辑分布")

    album_stats = (
        artist_df.groupby("album_name")
        .agg(
            plays=("play_id", "count"),
            hours=("ms_played", lambda x: x.sum() / 3_600_000),
        )
        .sort_values("hours", ascending=False)
        .reset_index()
    )
    album_stats["hours"] = album_stats["hours"].round(1)

    fig = px.pie(
        album_stats.head(8),
        names="album_name",
        values="hours",
        title="各专辑时长占比",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Listening pattern heatmap ───────────────────────────────────────
st.subheader("听歌时段分布")

dow_names = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
artist_df["dow_label"] = artist_df["ts_dow"].map(dow_names)

heatmap_data = (
    artist_df.groupby(["dow_label", "ts_hour"])
    .size()
    .reset_index(name="count")
)
pivot = heatmap_data.pivot(index="dow_label", columns="ts_hour", values="count").fillna(0)
# Ensure correct order
dow_order = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
pivot = pivot.reindex([d for d in dow_order if d in pivot.index])

fig = px.imshow(
    pivot,
    labels={"x": "小时", "y": "周几", "color": "播放次数"},
    title=f"{selected_artist_name} — 听歌时段热力图",
    aspect="auto",
    color_continuous_scale="Blues",
)
st.plotly_chart(fig, use_container_width=True)

# ── Album deep dive ─────────────────────────────────────────────────
st.divider()
st.subheader("📀 专辑深入分析")

album_list = sorted(artist_df["album_name"].dropna().unique().tolist())
if album_list:
    selected_album = st.selectbox("选择专辑查看详情", album_list)

    album_df = artist_df[artist_df["album_name"] == selected_album]
    album_plays = len(album_df)
    album_hours = album_df["ms_played"].sum() / 3_600_000
    album_tracks = album_df["track_id"].nunique()

    cols = st.columns(3)
    cols[0].metric("专辑播放次数", f"{album_plays:,}")
    cols[1].metric("专辑总时长", f"{album_hours:,.1f} 小时")
    cols[2].metric("专辑曲目数", album_tracks)

    # Album tracks ranking
    album_track_stats = (
        album_df.groupby("track_name")
        .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
        .sort_values("plays", ascending=False)
        .reset_index()
    )
    album_track_stats["hours"] = album_track_stats["hours"].round(1)

    fig = px.bar(
        album_track_stats,
        x="plays",
        y="track_name",
        orientation="h",
        labels={"track_name": "", "plays": "播放次数"},
        title=f"《{selected_album}》 — 曲目播放排行",
        height=400,
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

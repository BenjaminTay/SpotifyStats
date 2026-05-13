"""Spotify Stats — Streamlit entry point and overview dashboard."""

import os
import sys

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px

from app.db import get_db, init_db, base_filters, query_plays, db_exists
from app.import_data import import_data

st.set_page_config(
    page_title="Spotify Stats",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ──────────────────────────────────────────
if "min_ms" not in st.session_state:
    st.session_state.min_ms = 30000
if "exclude_skipped" not in st.session_state:
    st.session_state.exclude_skipped = True
if "music_only" not in st.session_state:
    st.session_state.music_only = True


# ── Sidebar: global filters ─────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.title("🎵 Spotify Stats")
        st.caption("Extended Streaming History")

        st.divider()

        st.subheader("数据过滤")
        min_sec = st.selectbox(
            "最短播放时长",
            options=[0, 10, 30, 60, 120],
            index=2,  # 30s default
            format_func=lambda x: f"{x} 秒" if x > 0 else "不过滤",
            key="sidebar_min_sec",
        )
        st.session_state.min_ms = min_sec * 1000

        st.session_state.exclude_skipped = st.checkbox(
            "排除已跳过的播放", value=True, key="sidebar_skip"
        )
        st.session_state.music_only = st.checkbox(
            "仅音乐（排除播客/有声书）", value=True, key="sidebar_music"
        )

        st.divider()

        if st.button("🔄 重新导入数据", use_container_width=True):
            with st.spinner("正在重新导入..."):
                import_data()
                st.cache_data.clear()
            st.rerun()

        # Show database status
        if db_exists():
            conn = get_db()
            count = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
            conn.close()
            st.caption(f"数据库：{count:,} 条记录")
        else:
            st.caption("数据库：未导入")


# ── First-run import ────────────────────────────────────────────────
def ensure_data():
    if not db_exists():
        with st.spinner("首次使用，正在导入 Spotify 播放记录..."):
            try:
                result = import_data(
                    progress_callback=lambda msg, pct: st.info(msg) if pct == 0 else None
                )
                st.success(
                    f"导入完成！{result['total_records']:,} 条记录，"
                    f"{result['unique_artists']} 位艺人，{result['unique_tracks']} 首曲目"
                )
                st.cache_data.clear()
                st.rerun()
            except FileNotFoundError as e:
                st.error(f"找不到数据文件：{e}")
                st.stop()
            except Exception as e:
                st.error(f"导入失败：{e}")
                st.stop()


# ── Helper: get filtered data as DataFrame ─────────────────────────
@st.cache_data(ttl=3600)
def load_plays_df(min_ms: int, exclude_skipped: bool, music_only: bool) -> pd.DataFrame:
    conn = get_db()
    filters, fparams = base_filters(
        min_ms=min_ms, exclude_skipped=exclude_skipped, music_only=music_only
    )
    where = f"WHERE {filters}" if filters else ""
    sql = f"""
        SELECT p.*, t.track_name, t.spotify_track_uri,
               a.artist_name, al.album_name
        FROM plays p
        LEFT JOIN tracks t ON p.track_id = t.track_id
        LEFT JOIN artists a ON t.artist_id = a.artist_id
        LEFT JOIN albums al ON t.album_id = al.album_id
        {where}
    """
    df = pd.read_sql_query(sql, conn, params=fparams)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_all_plays_df() -> pd.DataFrame:
    """Unfiltered data for behavior analysis pages."""
    conn = get_db()
    df = pd.read_sql_query(
        """SELECT p.*, t.track_name, t.spotify_track_uri,
                  a.artist_name, al.album_name
           FROM plays p
           LEFT JOIN tracks t ON p.track_id = t.track_id
           LEFT JOIN artists a ON t.artist_id = a.artist_id
           LEFT JOIN albums al ON t.album_id = al.album_id""",
        conn,
    )
    conn.close()
    return df


# ── Main ────────────────────────────────────────────────────────────
render_sidebar()
ensure_data()

st.title("📊 总览仪表盘")

min_ms = st.session_state.min_ms
exclude_skipped = st.session_state.exclude_skipped
music_only = st.session_state.music_only

df = load_plays_df(min_ms, exclude_skipped, music_only)
df_all = load_all_plays_df()

total_plays = len(df)
total_hours = df["ms_played"].sum() / 3_600_000
total_tracks = df["track_id"].nunique()
total_artists = df["artist_name"].dropna().nunique()
total_albums = df["album_name"].dropna().nunique()
total_days = df["ts_date"].nunique()
avg_daily_hours = total_hours / total_days if total_days > 0 else 0

skip_rate_all = df_all["skipped"].sum() / max(len(df_all), 1) * 100

# KPI 卡片
st.subheader("关键指标")
cols = st.columns(6)
cols[0].metric("总播放次数", f"{total_plays:,}")
cols[1].metric("总时长", f"{total_hours:,.0f} 小时")
cols[2].metric("独特曲目", f"{total_tracks:,}")
cols[3].metric("独特艺人", f"{total_artists:,}")
cols[4].metric("日均听歌", f"{avg_daily_hours:.1f} 小时")
cols[5].metric("总跳过率", f"{skip_rate_all:.1f}%")

st.divider()

# 月度趋势
st.subheader("月度播放趋势")
monthly = (
    df.groupby(["ts_year", "ts_month"])
    .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
    .reset_index()
)
monthly["period"] = monthly["ts_year"].astype(str) + "-" + monthly["ts_month"].astype(str).str.zfill(2)

fig_trend = px.line(
    monthly,
    x="period",
    y=["plays", "hours"],
    title="月度播放次数与时长",
    labels={"value": "数值", "period": "月份", "variable": "指标"},
)
st.plotly_chart(fig_trend, use_container_width=True)

# Top 10 + 平台 + 周天
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Top 10 曲目")
    top_tracks = (
        df.groupby(["track_name", "artist_name"])
        .size()
        .sort_values(ascending=False)
        .head(10)
        .reset_index(name="plays")
    )
    fig_top = px.bar(
        top_tracks,
        x="plays",
        y="track_name",
        orientation="h",
        hover_data=["artist_name"],
        labels={"track_name": "", "plays": "播放次数"},
        height=350,
    )
    fig_top.update_yaxes(autorange="reversed")
    st.plotly_chart(fig_top, use_container_width=True)

with col2:
    st.subheader("平台分布")
    platform_counts = df["platform"].value_counts().reset_index()
    platform_counts.columns = ["platform", "count"]
    fig_plat = px.pie(
        platform_counts,
        names="platform",
        values="count",
        height=350,
    )
    st.plotly_chart(fig_plat, use_container_width=True)

with col3:
    st.subheader("一周各天听歌量")
    dow_names = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    dow_counts = (
        df["ts_dow"]
        .value_counts()
        .sort_index()
        .reset_index()
    )
    dow_counts.columns = ["dow", "count"]
    dow_counts["day"] = dow_counts["dow"].map(dow_names)
    fig_dow = px.bar(
        dow_counts,
        x="day",
        y="count",
        labels={"day": "", "count": "播放次数"},
        height=350,
    )
    st.plotly_chart(fig_dow, use_container_width=True)

st.divider()
st.caption("提示：使用左侧边栏调整数据过滤条件、切换分析页面")

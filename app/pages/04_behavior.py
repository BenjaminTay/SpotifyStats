"""Listening behavior analysis: skip rate, fast-forward, platform, incognito, shuffle."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.db import get_db, load_plays
from app.styles import inject_global_styles, page_header

inject_global_styles()

min_ms = st.session_state.get("min_ms", 30000)
music_only = st.session_state.get("music_only", True)


@st.cache_data(ttl=3600)
def load_all_data():
    conn = get_db()
    df = load_plays(conn, filtered=False, music_only=False)
    conn.close()
    return df


df = load_all_data()

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        '<div style="font-size:2rem;margin-bottom:0.25rem;">🔍</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#2C2416;">播放行为</div>'
        '<div style="font-size:0.7rem;color:#8B7355;margin-top:0.15rem;">全量数据（含跳过和短播放）</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    section = st.radio(
        "分析维度",
        ["跳过分析", "快进/快退", "平台使用", "隐身模式", "随机播放"],
    )

# ── Helpers ─────────────────────────────────────────────────────────
dow_names = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
hour_labels = [f"{h}:00" for h in range(24)]

# ── 跳过分析 ──────────────────────────────────────
if section == "跳过分析":
    st.subheader("跳过率分析")

    col1, col2 = st.columns(2)

    with col1:
        # Skip rate by platform
        skip_by_platform = (
            df.groupby("platform")["skipped"].mean().mul(100).sort_values(ascending=False).reset_index()
        )
        skip_by_platform.columns = ["平台", "跳过率(%)"]
        fig = px.bar(
            skip_by_platform,
            x="平台",
            y="跳过率(%)",
            color="平台",
            title="各平台跳过率",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Skip rate by hour
        skip_by_hour = df.groupby("ts_hour")["skipped"].mean().mul(100).reset_index()
        skip_by_hour.columns = ["小时", "跳过率(%)"]
        fig = px.line(
            skip_by_hour,
            x="小时",
            y="跳过率(%)",
            markers=True,
            title="各小时跳过率趋势",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Monthly skip rate trend
    st.subheader("月度跳过率趋势")
    monthly_skip = (
        df.groupby(["ts_year", "ts_month"])
        .agg(total=("play_id", "count"), skip_rate=("skipped", "mean"))
        .reset_index()
    )
    monthly_skip["label"] = (
        monthly_skip["ts_year"].astype(str) + "-" + monthly_skip["ts_month"].astype(str).str.zfill(2)
    )
    monthly_skip["skip_rate"] = monthly_skip["skip_rate"] * 100

    fig = px.line(
        monthly_skip,
        x="label",
        y="skip_rate",
        markers=True,
        labels={"label": "月份", "skip_rate": "跳过率 (%)"},
        title="月度跳过率变化趋势",
    )
    fig.add_hline(
        y=monthly_skip["skip_rate"].mean(),
        line_dash="dash",
        line_color="red",
        annotation_text=f"平均 {monthly_skip['skip_rate'].mean():.1f}%",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Most skipped tracks (played >= 5 times)
    st.subheader("最常被跳过的曲目 (播放≥5次)")
    track_stats = (
        df.groupby(["track_name", "artist_name"])
        .agg(plays=("play_id", "count"), skip_rate=("skipped", "mean"))
        .reset_index()
    )
    track_stats = track_stats[track_stats["plays"] >= 5]
    track_stats["skip_rate"] = track_stats["skip_rate"] * 100
    most_skipped = track_stats.sort_values("skip_rate", ascending=False).head(20)

    fig = px.bar(
        most_skipped,
        x="skip_rate",
        y="track_name",
        orientation="h",
        hover_data=["artist_name", "plays"],
        labels={"skip_rate": "跳过率 (%)", "track_name": ""},
        title="跳过率最高的20首曲目",
        height=500,
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

# ── 快进/快退 ───────────────────────────────────
elif section == "快进/快退":
    st.subheader("播放结束原因分析")

    col1, col2 = st.columns(2)

    with col1:
        reason_counts = df["reason_end"].value_counts().reset_index()
        reason_counts.columns = ["reason", "count"]
        fig = px.pie(
            reason_counts,
            names="reason",
            values="count",
            title="reason_end 分布",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        reason_start_counts = df["reason_start"].value_counts().reset_index()
        reason_start_counts.columns = ["reason", "count"]
        fig = px.pie(
            reason_start_counts,
            names="reason",
            values="count",
            title="reason_start 分布",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Fwdbtn usage by hour
    st.subheader("快进行为时段分布")
    fwd = df[df["reason_end"] == "fwdbtn"]
    if not fwd.empty:
        fwd_by_hour = fwd.groupby("ts_hour").size().reset_index(name="count")
        fig = px.bar(
            fwd_by_hour,
            x="ts_hour",
            y="count",
            labels={"ts_hour": "小时", "count": "快进次数"},
            title="各小时快进次数",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Most forwarded tracks
    st.subheader("最常被快进的曲目")
    fwd_tracks = (
        df[df["reason_end"] == "fwdbtn"]
        .groupby(["track_name", "artist_name"])
        .size()
        .sort_values(ascending=False)
        .head(15)
        .reset_index(name="快进次数")
    )
    if not fwd_tracks.empty:
        fig = px.bar(
            fwd_tracks,
            x="快进次数",
            y="track_name",
            orientation="h",
            hover_data=["artist_name"],
            labels={"track_name": ""},
            height=400,
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

# ── 平台使用 ─────────────────────────────────────
elif section == "平台使用":
    st.subheader("平台使用分析")

    # Platform distribution by month
    platform_monthly = (
        df.groupby(["ts_year", "ts_month", "platform"])
        .size()
        .reset_index(name="count")
    )
    platform_monthly["label"] = (
        platform_monthly["ts_year"].astype(str)
        + "-"
        + platform_monthly["ts_month"].astype(str).str.zfill(2)
    )

    fig = px.area(
        platform_monthly,
        x="label",
        y="count",
        color="platform",
        labels={"label": "月份", "count": "播放次数", "platform": "平台"},
        title="月度平台使用分布",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Platform x Hour heatmap
    st.subheader("平台 × 小时 热力图")
    heatmap_data = df.groupby(["platform", "ts_hour"]).size().reset_index(name="count")
    pivot = heatmap_data.pivot(index="platform", columns="ts_hour", values="count").fillna(0)

    fig = px.imshow(
        pivot,
        labels={"x": "小时", "y": "平台", "color": "播放次数"},
        title="平台使用时段热力图",
        aspect="auto",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── 隐身模式 ─────────────────────────────────────
elif section == "隐身模式":
    st.subheader("隐身模式分析")

    incognito = df[df["incognito_mode"] == 1]
    total_incognito = len(incognito)

    col1, col2 = st.columns(2)
    col1.metric("隐身模式播放次数", f"{total_incognito:,}")
    col2.metric("占总播放比例", f"{total_incognito / max(len(df), 1) * 100:.1f}%")

    if not incognito.empty:
        # Incognito over time
        incog_monthly = (
            incognito.groupby(["ts_year", "ts_month"])
            .size()
            .reset_index(name="count")
        )
        incog_monthly["label"] = (
            incog_monthly["ts_year"].astype(str)
            + "-"
            + incog_monthly["ts_month"].astype(str).str.zfill(2)
        )

        fig = px.bar(
            incog_monthly,
            x="label",
            y="count",
            labels={"label": "月份", "count": "隐身播放次数"},
            title="隐身模式月度使用趋势",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Top artists in incognito
        incog_artists = (
            incognito.groupby("artist_name")
            .size()
            .sort_values(ascending=False)
            .head(10)
            .reset_index(name="count")
        )
        fig = px.bar(
            incog_artists,
            x="count",
            y="artist_name",
            orientation="h",
            labels={"artist_name": "", "count": "播放次数"},
            title="隐身模式下最爱艺人",
            height=300,
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

# ── 随机播放 ─────────────────────────────────────
elif section == "随机播放":
    st.subheader("随机播放分析")

    shuffle_rate = df["shuffle"].mean() * 100

    col1, col2 = st.columns(2)
    col1.metric("随机播放使用率", f"{shuffle_rate:.1f}%")

    # Shuffle rate over time
    shuffle_monthly = (
        df.groupby(["ts_year", "ts_month"])["shuffle"].mean().mul(100).reset_index()
    )
    shuffle_monthly["label"] = (
        shuffle_monthly["ts_year"].astype(str)
        + "-"
        + shuffle_monthly["ts_month"].astype(str).str.zfill(2)
    )
    shuffle_monthly.columns = ["ts_year", "ts_month", "shuffle_rate", "label"]

    fig = px.line(
        shuffle_monthly,
        x="label",
        y="shuffle_rate",
        markers=True,
        labels={"label": "月份", "shuffle_rate": "随机播放率 (%)"},
        title="随机播放使用率趋势",
    )
    col2.plotly_chart(fig, use_container_width=True)

    # Shuffle by platform
    st.subheader("各平台随机播放使用率")
    shuffle_platform = (
        df.groupby("platform")["shuffle"].mean().mul(100).sort_values(ascending=False).reset_index()
    )
    shuffle_platform.columns = ["平台", "随机播放率(%)"]

    fig = px.bar(
        shuffle_platform,
        x="平台",
        y="随机播放率(%)",
        color="平台",
        title="各平台随机播放率",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Shuffle vs Skip correlation
    st.subheader("随机播放与跳过率关系")
    shuffle_skip = df.groupby("shuffle")["skipped"].mean().mul(100).reset_index()
    shuffle_skip["shuffle"] = shuffle_skip["shuffle"].map({0: "非随机", 1: "随机"})
    shuffle_skip.columns = ["模式", "跳过率(%)"]

    fig = px.bar(
        shuffle_skip,
        x="模式",
        y="跳过率(%)",
        color="模式",
        title="随机 vs 非随机播放的跳过率对比",
    )
    st.plotly_chart(fig, use_container_width=True)

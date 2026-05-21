"""Listening behavior analysis: fast-forward, platform, incognito, shuffle."""

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


@st.cache_data(ttl=3600)
def load_all_data():
    conn = get_db()
    df = load_plays(conn, filtered=False, music_only=False)
    conn.close()
    return df


def render():
    df = load_all_data()

    page_header("🔍 行为分析", description="全量数据（含短播放）")

    # Controls (inline — was sidebar)
    section = st.radio(
        "分析维度",
        ["快进/快退", "平台使用", "随机播放"],
        horizontal=True,
    )

    # ── 快进/快退 ───────────────────────────────────
    if section == "快进/快退":
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

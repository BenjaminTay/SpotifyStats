"""Timeline reports: annual / monthly / weekly breakdowns."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from app.db import get_db, load_plays
from app.styles import inject_global_styles, page_header

inject_global_styles()

min_ms = st.session_state.get("min_ms", 30000)
music_only = st.session_state.get("music_only", True)
merge_enabled = st.session_state.get("merge_enabled", True)

@st.cache_data(ttl=3600)
def load_timeline_data(_min_ms, _music_only, _merge_enabled):
    conn = get_db()
    df = load_plays(conn, join_albums=False, min_ms=_min_ms, music_only=_music_only, merge_enabled=_merge_enabled)
    conn.close()
    return df


def render():
    # Controls (inline — was sidebar)
    page_header("📅 时间线", description=f"按时间维度浏览播放历史 · 最短={min_ms//1000}s")
    tab_choice = st.radio("视图", ["年度汇总", "月度详情", "周度详情"], horizontal=True)

    df = load_timeline_data(min_ms, music_only, merge_enabled)

    # ── Annual Summary ──────────────────────────────────────────────────
    if tab_choice == "年度汇总":
        st.subheader("年度播放汇总")

        annual = (
            df.groupby("ts_year")
            .agg(
                plays=("play_id", "count"),
                hours=("ms_played", lambda x: x.sum() / 3_600_000),
                unique_tracks=("track_id", "nunique"),
                unique_artists=("artist_name", "nunique"),
            )
            .reset_index()
        )

        # Top track per year
        def top_track_year(df_sub):
            top = df_sub.groupby(["track_name", "artist_name"]).size().idxmax()
            return f"{top[0]} — {top[1]}"

        top_tracks = df.groupby("ts_year").apply(top_track_year).reset_index(name="top_track")

        annual = annual.merge(top_tracks, on="ts_year", how="left")
        annual = annual.sort_values("ts_year")

        st.dataframe(
            annual,
            column_config={
                "ts_year": st.column_config.NumberColumn("年份", format="%d"),
                "plays": st.column_config.NumberColumn("播放次数", format="%d"),
                "hours": st.column_config.NumberColumn("总时长(小时)", format="%.1f"),
                "unique_tracks": st.column_config.NumberColumn("独特曲目", format="%d"),
                "unique_artists": st.column_config.NumberColumn("独特艺人", format="%d"),
                "top_track": st.column_config.TextColumn("年度Top曲目"),
            },
            use_container_width=True,
            hide_index=True,
        )

        # Year comparison chart
        fig = px.bar(
            annual,
            x="ts_year",
            y="hours",
            color="ts_year",
            labels={"ts_year": "年份", "hours": "总时长 (小时)"},
            title="各年度听歌总时长",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Monthly Detail ──────────────────────────────────────────────────
    elif tab_choice == "月度详情":
        st.subheader("月度播放详情")

        monthly = (
            df.groupby(["ts_year", "ts_month"])
            .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
            .reset_index()
        )
        monthly["label"] = monthly["ts_year"].astype(str) + "-" + monthly["ts_month"].astype(str).str.zfill(2)
        monthly = monthly.sort_values(["ts_year", "ts_month"])

        fig = px.bar(
            monthly,
            x="label",
            y="hours",
            color=monthly["ts_year"].astype(str),
            labels={"x": "月份", "y": "总时长 (小时)", "color": "年份"},
            title="月度听歌时长（按年分色）",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Select a month for detail
        selected_month = st.selectbox(
            "选择月份查看 Top 5 曲目",
            options=monthly["label"].tolist()[::-1],
        )

        if selected_month:
            parts = selected_month.split("-")
            yr, mo = int(parts[0]), int(parts[1])
            month_df = df[(df["ts_year"] == yr) & (df["ts_month"] == mo)]
            top5 = (
                month_df.groupby(["track_name", "artist_name"])
                .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
                .sort_values("plays", ascending=False)
                .head(5)
                .reset_index()
            )
            top5["hours"] = top5["hours"].round(1)

            cols = st.columns(5)
            for i, (_, row) in enumerate(top5.iterrows()):
                cols[i].metric(
                    f"#{i+1} {row['track_name'][:20]}",
                    f"{row['plays']} 次",
                    delta=row["artist_name"][:25],
                )

    # ── Weekly Detail ───────────────────────────────────────────────────
    else:
        st.subheader("周度播放趋势")

        weekly = (
            df.groupby(["ts_year", "ts_week"])
            .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
            .reset_index()
        )
        weekly["label"] = weekly["ts_year"].astype(str) + "-W" + weekly["ts_week"].astype(str).str.zfill(2)

        fig = px.line(
            weekly,
            x="label",
            y="hours",
            labels={"label": "周", "hours": "总时长 (小时)"},
            title="周度听歌时长",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Select a week for detail
        selected_week = st.selectbox(
            "选择周查看 Top 曲目",
            options=weekly["label"].tolist()[::-1],
        )

        if selected_week:
            yr, wk = selected_week.split("-W")
            yr, wk = int(yr), int(wk)
            week_df = df[(df["ts_year"] == yr) & (df["ts_week"] == wk)]
            if not week_df.empty:
                st.write(f"{len(week_df)} 次播放")
                top5 = (
                    week_df.groupby(["track_name", "artist_name"])
                    .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
                    .sort_values("plays", ascending=False)
                    .head(5)
                    .reset_index()
                )
                top5["hours"] = top5["hours"].round(1)

                cols = st.columns(5)
                for i, (_, row) in enumerate(top5.iterrows()):
                    cols[i].metric(
                        f"#{i+1} {row['track_name'][:20]}",
                        f"{row['plays']} 次",
                        delta=row["artist_name"][:25],
                    )

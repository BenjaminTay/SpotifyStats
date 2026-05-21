"""Podcast Zone — listening history, interactions, and saved shows."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json

import streamlit as st
import pandas as pd
import plotly.express as px

from app.db import get_db
from app.styles import inject_global_styles, page_header, kpi_row, PLOTLY_TEMPLATE, COLORS

inject_global_styles()


@st.cache_data(ttl=3600)
def load_podcast_data():
    conn = get_db()

    plays = pd.read_sql_query(
        "SELECT * FROM podcast_plays ORDER BY end_time", conn
    )
    interactions = pd.read_sql_query(
        "SELECT * FROM podcast_interactions", conn
    )
    saved_shows = pd.read_sql_query(
        "SELECT * FROM saved_shows", conn
    )
    top_podcasts = pd.read_sql_query(
        "SELECT * FROM wrapped_top_podcasts", conn
    )

    conn.close()

    has_data = not plays.empty or not saved_shows.empty
    return {
        "has_data": has_data,
        "plays": plays,
        "interactions": interactions,
        "saved_shows": saved_shows,
        "top_podcasts": top_podcasts,
    }


def render():
    data = load_podcast_data()

    if not data["has_data"]:
        st.warning("请先在「设置」页面导入账号数据")
        return

    plays = data["plays"]
    page_header("播客专区", description="播客收听记录、互动与收藏")

    total_hours = plays["ms_played"].sum() / 3600000 if not plays.empty else 0

    kpi_row([
        {"label": "播客播放", "value": f"{len(plays)} 次"},
        {"label": "收听时长", "value": f"{total_hours:.1f} 小时"},
        {"label": "独特节目", "value": str(plays["podcast_name"].nunique() if not plays.empty else 0)},
        {"label": "收藏节目", "value": str(len(data["saved_shows"]))},
    ])

    tab1, tab2 = st.tabs(["收听总览", "互动记录"])

    with tab1:
        if not plays.empty:
            # Show by listening time
            show_hours = (
                plays.groupby("podcast_name")["ms_played"].sum()
                .div(3600000).sort_values(ascending=True).tail(15)
            )
            fig = px.bar(
                x=show_hours.values, y=show_hours.index, orientation="h",
                color_discrete_sequence=[COLORS[0]],
            )
            fig.update_layout(**PLOTLY_TEMPLATE["layout"])
            fig.update_layout(height=350, xaxis={"title": "收听小时"})
            st.plotly_chart(fig, use_container_width=True)

            # Monthly trend (by listening hours)
            plays["play_date_dt"] = pd.to_datetime(plays["play_date"])
            monthly = plays.groupby(plays["play_date_dt"].dt.to_period("M"))["ms_played"].sum().div(3600000).reset_index(name="hours")
            monthly["play_date_dt"] = monthly["play_date_dt"].astype(str)
            fig_line = px.line(
                monthly, x="play_date_dt", y="hours",
                color_discrete_sequence=[COLORS[0]],
            )
            fig_line.update_layout(**PLOTLY_TEMPLATE["layout"])
            fig_line.update_layout(height=250, xaxis={"title": ""}, yaxis={"title": "小时"})
            st.plotly_chart(fig_line, use_container_width=True)

        # Saved shows
        if not data["saved_shows"].empty:
            st.markdown("#### 收藏的节目")
            shows_df = data["saved_shows"][["show_name", "publisher"]].copy()
            shows_df.columns = ["节目名称", "发布者"]
            st.dataframe(shows_df, use_container_width=True, hide_index=True)

    with tab2:
        interactions = data["interactions"]
        if not interactions.empty:
            for _, row in interactions.iterrows():
                itype = row["interaction_type"]
                detail = json.loads(row.get("content_json", "{}")) if row.get("content_json") else {}

                if itype == "comment":
                    st.markdown(
                        f"""<div style="background:var(--bg-card);border-left:3px solid var(--gold);
                        border-radius:8px;padding:0.75rem 1rem;margin-bottom:0.5rem;">
                        <div style="font-size:0.7rem;color:var(--gold);">💬 评论</div>
                        <div style="font-weight:600;">{detail.get('commentText', '')}</div>
                        <div style="font-size:0.75rem;color:var(--text-secondary);">{row['created_at']}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                elif itype == "rating":
                    st.markdown(
                        f"""<div style="background:var(--bg-card);border-left:3px solid var(--gold);
                        border-radius:8px;padding:0.75rem 1rem;margin-bottom:0.5rem;">
                        <div style="font-size:0.7rem;color:var(--gold);">⭐ 评分</div>
                        <div style="font-weight:600;">{detail.get('rating', '')}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                elif itype == "poll":
                    st.markdown(
                        f"""<div style="background:var(--bg-card);border-left:3px solid var(--gold);
                        border-radius:8px;padding:0.75rem 1rem;margin-bottom:0.5rem;">
                        <div style="font-size:0.7rem;color:var(--gold);">📊 投票</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("暂无播客互动记录")

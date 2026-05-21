"""Search Chronicles — search query trends, intents, and trajectories."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.db import get_db
from app.styles import inject_global_styles, page_header, kpi_row, PLOTLY_TEMPLATE, COLORS

inject_global_styles()


@st.cache_data(ttl=3600)
def load_search_data():
    conn = get_db()
    df = pd.read_sql_query(
        "SELECT * FROM search_queries ORDER BY search_time_utc", conn
    )
    # Also load artists/tracks for intent classification
    artists = pd.read_sql_query("SELECT artist_name FROM artists", conn)
    tracks = pd.read_sql_query("SELECT track_name FROM tracks", conn)
    conn.close()

    has_data = not df.empty
    return {"has_data": has_data, "df": df, "artists": artists, "tracks": tracks}


def classify_intent(query, artist_names, track_names):
    q = query.lower()
    q2 = query.strip()
    if q2 in [a.lower() for a in artist_names]:
        return "艺人查找"
    if q2 in [t.lower() for t in track_names]:
        return "歌曲搜索"
    if any(kw in q for kw in ["billboard", "hot 100", "排行", "top", "排行榜", "歌单", "playlist"]):
        return "排行榜/歌单"
    return "未分类"


def render():
    data = load_search_data()

    if not data["has_data"]:
        st.warning("请先在「设置」页面导入账号数据")
        return

    df = data["df"]
    artist_names = data["artists"]["artist_name"].dropna().tolist()
    track_names = data["tracks"]["track_name"].dropna().tolist()

    page_header("搜索编年史", description="Spotify 搜索查询的轨迹与趋势")

    kpi_row([
        {"label": "总搜索次数", "value": f"{len(df):,}"},
        {"label": "独特搜索词", "value": f"{df['query_text'].nunique():,}"},
        {"label": "覆盖天数", "value": f"{df['search_date'].nunique()}"},
    ])

    # ── Tab 1: Trends ────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["搜索趋势", "热门搜索", "搜索意图"])

    with tab1:
        st.markdown("#### 每日搜索量")
        daily = df.groupby("search_date").size().reset_index(name="count")
        daily["search_date"] = pd.to_datetime(daily["search_date"])
        daily = daily.sort_values("search_date")

        fig_line = px.line(daily, x="search_date", y="count",
                           color_discrete_sequence=[COLORS[0]])
        fig_line.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_line.update_layout(height=280)
        st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("#### 搜索时段热力图")
        heatmap_data = df.groupby(["search_dow", "search_hour"]).size().unstack(fill_value=0)
        dow_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        try:
            heatmap_data = heatmap_data.reindex(range(7), fill_value=0)
        except Exception:
            pass
        heatmap_data.index = [dow_labels[i] if i < len(dow_labels) else str(i)
                              for i in range(len(heatmap_data))]

        fig_heat = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=list(heatmap_data.columns),
            y=list(heatmap_data.index),
            colorscale=[[0, "rgba(184,134,11,0.05)"], [1, "rgb(184,134,11)"]],
            hoverongaps=False,
        ))
        fig_heat.update_layout(
            **PLOTLY_TEMPLATE["layout"],
            height=300,
            xaxis={"title": "小时", "dtick": 1},
            yaxis={"title": ""},
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    with tab2:
        st.markdown("#### Top 30 搜索词")
        top_qs = df["query_text"].value_counts().head(30).reset_index()
        top_qs.columns = ["query", "count"]
        top_qs = top_qs.sort_values("count")

        fig_bar = px.bar(top_qs, x="count", y="query", orientation="h",
                         color_discrete_sequence=[COLORS[0]])
        fig_bar.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_bar.update_layout(height=500, yaxis={"dtick": 1})
        st.plotly_chart(fig_bar, use_container_width=True)

    with tab3:
        st.markdown("#### 搜索意图分类")
        df["intent"] = df["query_text"].apply(
            lambda q: classify_intent(q, artist_names, track_names)
        )
        intent_counts = df["intent"].value_counts()

        col_pie, col_list = st.columns([1, 2])
        with col_pie:
            fig_pie = px.pie(
                values=intent_counts.values,
                names=intent_counts.index,
                color_discrete_sequence=COLORS,
            )
            fig_pie.update_layout(**PLOTLY_TEMPLATE["layout"])
            fig_pie.update_layout(height=300)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_list:
            for intent in intent_counts.index:
                st.markdown(f"**{intent}** ({intent_counts[intent]} 次)")
                examples = df[df["intent"] == intent]["query_text"].value_counts().head(5)
                for q, c in examples.items():
                    st.markdown(f"- {q} ({c})")

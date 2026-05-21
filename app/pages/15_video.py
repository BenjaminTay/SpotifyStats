"""Video Analytics — video vs audio playback comparison."""

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
def load_video_data():
    conn = get_db()

    # Video plays (only >= 30s to exclude scroll-by autoplay noise)
    video_df = pd.read_sql_query(
        """SELECT p.*, t.track_name, a.artist_name
           FROM plays p
           LEFT JOIN tracks t ON p.track_id = t.track_id
           LEFT JOIN artists a ON t.artist_id = a.artist_id
           WHERE p.content_type = 'video' AND p.ms_played >= 30000
           ORDER BY p.ts""",
        conn,
    )

    # Audio plays for comparison
    audio_total = conn.execute(
        "SELECT COUNT(*) FROM plays WHERE content_type = 'audio'"
    ).fetchone()[0]

    # Video vs audio top tracks (video only counts >= 30s)
    video_top = pd.DataFrame()
    if not video_df.empty:
        video_top = pd.read_sql_query(
            """SELECT t.track_name, a.artist_name,
                      SUM(CASE WHEN p.content_type='video' AND p.ms_played >= 30000 THEN 1 ELSE 0 END) as video_plays,
                      SUM(CASE WHEN p.content_type='audio' THEN 1 ELSE 0 END) as audio_plays
               FROM plays p
               JOIN tracks t ON p.track_id = t.track_id
               JOIN artists a ON t.artist_id = a.artist_id
               WHERE p.content_type IN ('video', 'audio') AND p.track_id IS NOT NULL
               GROUP BY p.track_id
               HAVING video_plays > 0
               ORDER BY video_plays DESC
               LIMIT 30""",
            conn,
        )

    # Yearly trend (video only counts >= 30s)
    yearly = conn.execute(
        """SELECT ts_year, content_type, COUNT(*) as cnt
           FROM plays
           WHERE content_type != 'video' OR ms_played >= 30000
           GROUP BY ts_year, content_type
           ORDER BY ts_year"""
    ).fetchall()
    yearly_df = pd.DataFrame(yearly, columns=["year", "type", "count"])

    # Platform for video
    video_platform = video_df["platform"].value_counts() if not video_df.empty else pd.Series()

    conn.close()

    has_data = not video_df.empty
    return {
        "has_data": has_data,
        "video_df": video_df,
        "audio_total": audio_total,
        "video_top": video_top,
        "yearly_df": yearly_df,
        "video_platform": video_platform,
    }


def render():
    data = load_video_data()

    if not data["has_data"]:
        st.warning("请先在「设置」页面重新导入数据（需包含视频记录）")
        return

    vd = data["video_df"]
    page_header("视频分析", description="视频播放 vs 音频播放对比 · 仅统计 ≥30s 有效观看")

    video_total_ms = vd["ms_played"].sum()
    video_hours = video_total_ms / 3600000

    # Detect music video vs others
    music_video_count = vd[vd["track_id"].notna()].shape[0]
    other_video_count = len(vd) - music_video_count

    kpi_row([
        {"label": "视频播放", "value": f"{len(vd):,} 次"},
        {"label": "视频时长", "value": f"{video_hours:.1f} 小时"},
        {"label": "音乐视频", "value": f"{music_video_count}"},
        {"label": "音频对比", "value": f"{data['audio_total']:,} 次"},
    ])

    tab1, tab2 = st.tabs(["趋势对比", "视频排行"])

    with tab1:
        # Yearly trend
        ydf = data["yearly_df"]
        if not ydf.empty:
            ydf_pivot = ydf.pivot(index="year", columns="type", values="count").fillna(0)
            if "video" not in ydf_pivot.columns:
                ydf_pivot["video"] = 0
            if "audio" not in ydf_pivot.columns:
                ydf_pivot["audio"] = 0

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=ydf_pivot.index, y=ydf_pivot["audio"],
                name="音频", marker={"color": COLORS[2]},
            ))
            fig.add_trace(go.Bar(
                x=ydf_pivot.index, y=ydf_pivot["video"],
                name="视频", marker={"color": COLORS[0]},
            ))
            fig.update_layout(
                **PLOTLY_TEMPLATE["layout"],
                barmode="group", height=300,
                xaxis={"title": ""}, yaxis={"title": "播放次数"},
            )
            st.plotly_chart(fig, use_container_width=True)

        # Platform distribution
        if not data["video_platform"].empty:
            st.markdown("#### 视频播放平台")
            fig_pie = px.pie(
                values=data["video_platform"].values,
                names=data["video_platform"].index,
                color_discrete_sequence=COLORS,
            )
            fig_pie.update_layout(**PLOTLY_TEMPLATE["layout"])
            fig_pie.update_layout(height=280)
            st.plotly_chart(fig_pie, use_container_width=True)

        # Average ms_played comparison
        avg_video_ms = vd["ms_played"].mean()
        st.metric("视频平均播放时长", f"{avg_video_ms/1000:.1f} 秒")

    with tab2:
        vt = data["video_top"]
        if not vt.empty:
            st.markdown("#### Top 30 音乐视频（视频 vs 音频播放次数）")
            show_vt = vt.head(20).copy()
            show_vt["label"] = show_vt["track_name"] + " - " + show_vt["artist_name"]
            show_vt = show_vt.sort_values("video_plays")

            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=show_vt["label"], x=show_vt["video_plays"],
                name="视频播放", orientation="h",
                marker={"color": COLORS[0]},
            ))
            fig.add_trace(go.Bar(
                y=show_vt["label"], x=show_vt["audio_plays"],
                name="音频播放", orientation="h",
                marker={"color": COLORS[2]},
            ))
            fig.update_layout(
                **PLOTLY_TEMPLATE["layout"],
                barmode="group", height=500,
                xaxis={"title": "次数"},
            )
            st.plotly_chart(fig, use_container_width=True)

        # Recent video plays
        if len(vd) > 0:
            st.markdown("#### 最近视频播放")
            vd["_ts_parsed"] = pd.to_datetime(vd["ts"])
            recent = vd.nlargest(20, "_ts_parsed")[["ts_date", "track_name", "artist_name", "ms_played", "platform"]]
            recent["seconds"] = (recent["ms_played"].astype(float) / 1000).round(1)
            recent = recent[["ts_date", "track_name", "artist_name", "seconds", "platform"]]
            recent.columns = ["日期", "曲目", "艺人", "秒数", "平台"]
            st.dataframe(recent, use_container_width=True, hide_index=True)

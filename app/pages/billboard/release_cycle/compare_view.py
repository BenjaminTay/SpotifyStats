"""发行周期分析 — 对比视图."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from app.styles import PLOTLY_TEMPLATE, COLORS

from app.pages.billboard.release_cycle.shared import (
    compute_release_cycle,
    compute_release_metrics,
)


def render_compare_view(df_raw, weekly_artist, weekly_album):
    """渲染对比视图。"""
    queue = st.session_state.get("rc_compare_queue", [])

    # ── Top Navigation ─────────────────────────────────────────────────
    col_back, col_clear = st.columns([3, 1])
    with col_back:
        if st.button("← 返回艺人总览", key="rc_back_from_compare"):
            st.session_state.rc_view = "artist"
            st.rerun()
    with col_clear:
        if st.button(f"清空队列 ({len(queue)})", key="rc_clear_queue"):
            st.session_state.rc_compare_queue = []
            st.rerun()

    if len(queue) < 2:
        st.warning("对比队列中至少需要 2 张发行。请从艺人总览或专辑下钻页面添加。")
        return

    st.divider()

    # ── Compute cycle data for all items ───────────────────────────────
    all_cycles = []
    all_metrics = []
    for item in queue:
        cycle = compute_release_cycle(
            df_raw, item["artist_name"], item["album_name"], item["release_date"],
            weekly_artist=weekly_artist, weekly_album=weekly_album,
        )
        metrics = compute_release_metrics(cycle, "album")
        all_cycles.append({
            "label": f"{item['album_name']} ({item['release_date'].strftime('%Y')})",
            "artist_name": item["artist_name"],
            "album_name": item["album_name"],
            "cycle": cycle,
            "metrics": metrics,
        })
        all_metrics.append({
            "发行": f"{item['album_name']}",
            "艺人": item["artist_name"],
            "发行日期": item["release_date"].strftime("%Y-%m-%d"),
            "空降排名": f"#{metrics['debut_rank']}" if metrics["debut_rank"] else "—",
            "Peak": f"#{metrics['peak_rank']}" if metrics["peak_rank"] else "—",
            "在榜周数": metrics["weeks_on_chart"],
            "冲击力": f"+{metrics['impact_force']:.0f}%" if metrics["impact_force"] else "—",
            "半衰期": f"{metrics['half_life']}周" if metrics.get("half_life") else ">24周",
        })

    # ── 排名对比曲线 ──────────────────────────────────────────────────
    st.subheader("排名对比（以发行周为 0 点对齐）")

    fig_rank = go.Figure()
    for i, c in enumerate(all_cycles):
        ar = c["cycle"].get("album_ranks", pd.DataFrame())
        if not ar.empty:
            color = COLORS[i % len(COLORS)]
            fig_rank.add_trace(
                go.Scatter(
                    x=ar["week_offset"],
                    y=ar["rank"],
                    mode="lines+markers",
                    name=c["label"],
                    line={"color": color, "width": 2},
                    marker={"size": 5},
                    connectgaps=False,
                    hovertemplate=f"{c['label']}<br>Week %{{x}}: #%{{y}}<extra></extra>",
                )
            )

    fig_rank.add_vline(x=0, line_dash="dot", line_color="rgba(139,115,85,0.4)", line_width=1.5)
    fig_rank.update_layout(
        template=PLOTLY_TEMPLATE,
        xaxis={"title": "距发行周数", "gridcolor": "rgba(139,115,85,0.08)"},
        yaxis={"autorange": "reversed", "title": "排名", "gridcolor": "rgba(139,115,85,0.08)"},
        height=400,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_rank, use_container_width=True)

    # ── 播放量对比曲线 ────────────────────────────────────────────────
    st.subheader("播放量对比")

    fig_plays = go.Figure()
    for i, c in enumerate(all_cycles):
        atl = c["cycle"].get("album_timeline", pd.DataFrame())
        if not atl.empty:
            color = COLORS[i % len(COLORS)]
            fig_plays.add_trace(
                go.Scatter(
                    x=atl["week_offset"],
                    y=atl["play_count"],
                    mode="lines+markers",
                    name=c["label"],
                    line={"color": color, "width": 2},
                    marker={"size": 5},
                    connectgaps=False,
                    hovertemplate=f"{c['label']}<br>Week %{{x}}: %{{y:,}} 次<extra></extra>",
                )
            )

    fig_plays.add_vline(x=0, line_dash="dot", line_color="rgba(139,115,85,0.4)", line_width=1.5)
    fig_plays.update_layout(
        template=PLOTLY_TEMPLATE,
        xaxis={"title": "距发行周数", "gridcolor": "rgba(139,115,85,0.08)"},
        yaxis={"title": "播放次数", "gridcolor": "rgba(139,115,85,0.08)"},
        height=400,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_plays, use_container_width=True)

    # ── 指标对比表 ────────────────────────────────────────────────────
    st.subheader("指标对比")

    metrics_df = pd.DataFrame(all_metrics)
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)

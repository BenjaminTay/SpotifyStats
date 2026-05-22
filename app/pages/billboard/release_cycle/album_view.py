"""发行周期分析 — 专辑下钻视图."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from app.styles import PLOTLY_TEMPLATE, COLORS

from app.pages.billboard.release_cycle.shared import (
    load_artist_releases,
    compute_release_cycle,
    compute_release_metrics,
    detect_catalog_reentries,
    get_advance_singles,
)


def render_album_detail(artist_name, album_name, df_raw, weekly_artist, weekly_album, weekly):
    """渲染专辑下钻视图。"""
    releases = load_artist_releases(artist_name)
    album_releases = releases[releases["album_name"] == album_name]
    if album_releases.empty:
        st.warning(f"未找到专辑「{album_name}」的发行信息。")
        return

    rel = album_releases.iloc[0]
    release_date = rel["release_date"]
    album_type = rel["album_type"]

    # Find advance singles: songs on this album released as singles before album date
    advance_singles = []
    if album_type == "album":
        advance_singles = get_advance_singles(artist_name, album_name)

    # ── Top Navigation ─────────────────────────────────────────────────
    col_back, col_action = st.columns([3, 1])
    with col_back:
        if st.button("← 返回艺人总览", key="rc_back_artist"):
            st.session_state.rc_view = "artist"
            st.session_state.rc_selected_album = None
            st.rerun()
    with col_action:
        if st.button("添加到对比队列", key="rc_add_compare"):
            if "rc_compare_queue" not in st.session_state:
                st.session_state.rc_compare_queue = []
            existing = [q for q in st.session_state.rc_compare_queue if q["album_name"] != album_name]
            existing.append({
                "artist_name": artist_name,
                "album_name": album_name,
                "release_date": release_date,
            })
            if len(existing) > 5:
                existing = existing[-5:]
            st.session_state.rc_compare_queue = existing
            st.success(f"已添加「{album_name}」到对比队列 ({len(existing)}/5)")
            st.rerun()

    st.divider()

    # ── Album Info ─────────────────────────────────────────────────────
    if advance_singles:
        names = [s["single_name"] for s in advance_singles]
        lead_str = f"先行曲: {', '.join(names)}"
    else:
        lead_str = "无先行单曲"
    st.caption(f"{album_type} · {release_date.strftime('%Y-%m-%d')} · {lead_str}")

    # Compute cycle data
    cycle = compute_release_cycle(
        df_raw, artist_name, album_name, release_date,
        weekly_artist=weekly_artist, weekly_album=weekly_album,
    )
    metrics = compute_release_metrics(cycle, album_type)
    catalog = detect_catalog_reentries(df_raw, artist_name, release_date, album_name)

    # ── KPI Cards ──────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        debut_str = f"#{metrics['debut_rank']}" if metrics["debut_rank"] else "未入榜"
        st.metric("空降排名", debut_str)
    with col2:
        peak_str = f"#{metrics['peak_rank']}" if metrics["peak_rank"] else "—"
        weeks_pk = f"登顶需 {metrics['weeks_to_peak']} 周" if metrics.get("weeks_to_peak") is not None else ""
        st.metric("Peak 排名", peak_str, delta=weeks_pk if weeks_pk else None)
    with col3:
        wks_str = f"{metrics['weeks_on_chart']} 周" if metrics["weeks_on_chart"] else "—"
        hl_str = f"半衰 {metrics['half_life']} 周" if metrics.get("half_life") is not None else "半衰 >24周"
        st.metric("在榜周数", wks_str, delta=hl_str)
    with col4:
        impact_str = f"+{metrics['impact_force']:.0f}%" if metrics["impact_force"] else "—"
        st.metric("发行冲击力", impact_str)

    st.divider()

    # ── 发行前后排名/播放量曲线 ──────────────────────────────────────
    st.subheader("发行前后表现")
    fig = _build_cycle_chart(cycle, album_name, advance_singles)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── 两列布局：歌曲入榜矩阵 + 老歌回榜 ───────────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("专辑歌曲入榜矩阵")
        _render_track_matrix(cycle, album_name)

    with col_right:
        st.subheader("老歌回榜")
        if catalog:
            _render_catalog_table(catalog)
        else:
            st.caption("发行未带动老歌回榜")


def _build_cycle_chart(cycle, album_name, advance_singles=None):
    """构建发行周期图（排名 + 播放量）。"""
    if advance_singles is None:
        advance_singles = []

    fig = go.Figure()

    ar = cycle.get("album_ranks", pd.DataFrame())
    if not ar.empty:
        fig.add_trace(
            go.Scatter(
                x=ar["week_offset"],
                y=ar["rank"],
                mode="lines+markers",
                name=f"专辑榜排名 ({album_name})",
                line={"color": "#B8860B", "width": 2.5},
                marker={"size": 6},
                connectgaps=False,
                hovertemplate="Week %{x}: #%{y}<extra></extra>",
            )
        )

    art_r = cycle.get("artist_ranks", pd.DataFrame())
    if not art_r.empty:
        fig.add_trace(
            go.Scatter(
                x=art_r["week_offset"],
                y=art_r["rank"],
                mode="lines+markers",
                name="艺人榜排名",
                line={"color": "#C45C3A", "width": 1.5, "dash": "dash"},
                marker={"size": 4},
                connectgaps=False,
                hovertemplate="Week %{x}: #%{y}<extra></extra>",
            )
        )

    atl = cycle.get("album_timeline", pd.DataFrame())
    if not atl.empty:
        fig.add_trace(
            go.Bar(
                x=atl["week_offset"],
                y=atl["play_count"],
                name="专辑播放次数",
                marker_color="rgba(184, 134, 11, 0.18)",
                yaxis="y2",
                hovertemplate="%{y:,} 次<extra></extra>",
            )
        )

    release_date = cycle["release_date"]
    for s in advance_singles:
        single_date = pd.to_datetime(s["release_date"])
        offset = int(round((single_date - release_date).days / 7.0))
        fig.add_trace(
            go.Scatter(
                x=[offset],
                y=[1],
                mode="markers+text",
                name=f"先行曲: {s['single_name']}",
                text=[s["single_name"][:12]],
                textposition="top center",
                marker={"size": 12, "color": "#D4A84B", "symbol": "diamond"},
                hovertemplate=f"先行曲: {s['single_name']}<br>{single_date.strftime('%Y-%m-%d')}<extra></extra>",
            )
        )

    fig.add_vline(x=0, line_dash="dot", line_color="rgba(139,115,85,0.4)", line_width=1.5)
    fig.add_annotation(
        x=0, y=1, yref="paper",
        text="发行周", showarrow=False,
        font={"color": "#8B7355", "size": 10},
    )

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        xaxis={
            "title": "距发行周数",
            "gridcolor": "rgba(139,115,85,0.08)",
        },
        yaxis={
            "autorange": "reversed",
            "title": "排名",
            "gridcolor": "rgba(139,115,85,0.08)",
        },
        yaxis2={
            "title": "播放次数",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
        height=400,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _render_track_matrix(cycle, album_name):
    """渲染专辑歌曲入榜热力图矩阵。"""
    track_tl = cycle.get("track_timelines", pd.DataFrame())
    if track_tl.empty:
        st.caption("该专辑无歌曲播放记录。")
        return

    top_tracks = (
        track_tl.groupby("track_name")["play_count"]
        .sum()
        .sort_values(ascending=False)
        .head(20)
        .index.tolist()
    )

    matrix_data = track_tl[track_tl["track_name"].isin(top_tracks)]
    if matrix_data.empty:
        st.caption("无歌曲入榜数据。")
        return

    pivot = matrix_data.pivot_table(
        index="track_name",
        columns="week_offset",
        values="play_count",
        fill_value=0,
    )

    track_first_week = (pivot > 0).idxmax(axis=1)
    pivot = pivot.loc[track_first_week.sort_values().index]

    if not pivot.empty and not pivot.columns.empty:
        st.dataframe(pivot, use_container_width=True, height=350)
        st.caption("数字 = 播放次数，0 = 未入榜")
    else:
        st.caption("数据不足以构建矩阵。")


def _render_catalog_table(catalog):
    """渲染老歌回榜表格。"""
    if not catalog:
        return

    rows = []
    for item in catalog:
        rows.append({
            "歌曲": item["track_name"],
            "来源专辑": item["source_album"],
            "回归周": f"+{item['reentry_offset']} 周",
            "在榜周数": f"{item['weeks_in_chart']} 周",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

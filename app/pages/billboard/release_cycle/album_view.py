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
    _resolve_album_group,
    align_to_release,
    format_artist_impact,
    format_artist_impact_help,
    format_market_impact,
    format_market_impact_help,
)

# 先行曲和走势线配色
ADVANCE_SINGLE_COLORS = ["#D4A84B", "#6B9B7A", "#C47A3A", "#6B7B9B", "#9B6B7A"]


def _split_consecutive_segments(df, x_col="week_offset"):
    """将 DataFrame 按连续周拆分为多个片段，非连续周之间断开连线。"""
    if df.empty or len(df) == 0:
        return []
    df = df.sort_values(x_col).reset_index(drop=True)
    segments = []
    start = 0
    for i in range(1, len(df)):
        if df.iloc[i][x_col] - df.iloc[i - 1][x_col] != 1:
            segments.append(df.iloc[start:i])
            start = i
    segments.append(df.iloc[start:])
    return segments


def _get_single_track_ids(artist_name, single_name):
    """获取单曲（在 DB 中作为 album 存储）关联的所有 track_id。"""
    from app.db import get_db

    conn = get_db()
    rows = conn.execute(
        """SELECT DISTINCT ta.track_id
           FROM track_albums ta
           JOIN albums al ON ta.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           WHERE a.artist_name = ? AND al.album_name = ?""",
        [artist_name, single_name],
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _get_chart_ranks_for_tracks(weekly, artist_name, track_ids, release_date,
                                 weeks_before=12, weeks_after=24):
    """获取指定 track 在单曲榜上的排名，对齐到发行日。"""
    if weekly is None or not track_ids:
        return pd.DataFrame()
    ranks = weekly[
        (weekly["artist_name"] == artist_name)
        & (weekly["track_id"].isin(track_ids))
    ][["billboard_week", "track_id", "track_name", "rank"]].copy()
    if ranks.empty:
        return ranks
    ranks = align_to_release(ranks, release_date, weeks_before, weeks_after)
    if ranks.empty:
        return ranks
    # 同一单曲可能有多首歌，取每周最佳排名
    ranks = ranks.groupby("week_offset")["rank"].min().reset_index()
    return ranks.sort_values("week_offset")


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

    # Resolve release group info
    group_albums, canonical, primary_name = _resolve_album_group(artist_name, album_name)
    is_grouped = len(group_albums) > 1

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

    version_tag = ""
    if is_grouped:
        non_primary = [a for a in group_albums if a != canonical]
        if non_primary:
            version_tag = f" · 📀 含 {len(non_primary)} 个子版本"
    st.caption(f"{album_type} · {release_date.strftime('%Y-%m-%d')} · {lead_str}{version_tag}")

    # 版本家族信息
    if is_grouped:
        with st.expander(f"📀 版本家族 ({len(group_albums)} 个版本)", expanded=False):
            st.caption(f"主版本：**{canonical}**")
            for a in group_albums:
                if a != canonical:
                    st.caption(f"  ↳ {a}")

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
        st.metric("艺人收听冲击力", format_artist_impact(metrics["artist_impact"]),
                  help=format_artist_impact_help(metrics.get("artist_impact_detail")))
        st.metric("大盘冲击力", format_market_impact(metrics["market_impact"]),
                  help=format_market_impact_help(metrics.get("market_impact_detail")))

    # ── 先行曲单曲榜排名数据 ────────────────────────────────────────
    advance_single_ranks = []
    advance_single_track_ids = set()
    if advance_singles:
        for s in advance_singles:
            track_ids = _get_single_track_ids(artist_name, s["single_name"])
            advance_single_track_ids.update(track_ids)
            ranks = _get_chart_ranks_for_tracks(
                weekly, artist_name, track_ids, release_date,
            )
            if not ranks.empty:
                advance_single_ranks.append({"name": s["single_name"], "ranks": ranks})

    # ── 最佳走势单曲排名线 ──────────────────────────────────────────
    best_track_ranks = None
    track_tl = cycle.get("track_timelines", pd.DataFrame())
    if not track_tl.empty and weekly is not None:
        track_totals = (
            track_tl.groupby(["track_id", "track_name"])["play_count"]
            .sum()
            .reset_index()
            .sort_values("play_count", ascending=False)
        )
        # 找到第一首不属于先行曲的曲目作为最佳走势单曲
        for _, tr in track_totals.iterrows():
            if tr["track_id"] not in advance_single_track_ids:
                ranks = _get_chart_ranks_for_tracks(
                    weekly, artist_name, [tr["track_id"]], release_date,
                )
                if not ranks.empty:
                    best_track_ranks = {"name": tr["track_name"], "ranks": ranks}
                break

    st.divider()

    # ── 发行前后排名/播放量曲线 ──────────────────────────────────────
    st.subheader("发行前后表现")
    fig = _build_cycle_chart(
        cycle, album_name, advance_singles,
        advance_single_ranks=advance_single_ranks,
        best_track_ranks=best_track_ranks,
    )
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

    # 加曲来源：显示来自子版本（豪华版等）的独有曲目
    if is_grouped:
        _render_bonus_tracks(df_raw, artist_name, group_albums, primary_name)


def _build_cycle_chart(cycle, album_name, advance_singles=None,
                        advance_single_ranks=None, best_track_ranks=None):
    """构建发行周期图（排名 + 播放量）。

    advance_single_ranks: [{"name": str, "ranks": DataFrame(week_offset, rank)}, ...]
    best_track_ranks: {"name": str, "ranks": DataFrame(week_offset, rank)} or None
    """
    if advance_singles is None:
        advance_singles = []
    if advance_single_ranks is None:
        advance_single_ranks = []

    fig = go.Figure()

    # ── 专辑榜排名（仅连续周连线） ──────────────────────────────────
    ar = cycle.get("album_ranks", pd.DataFrame())
    if not ar.empty:
        segments = _split_consecutive_segments(ar)
        for i, seg in enumerate(segments):
            fig.add_trace(
                go.Scatter(
                    x=seg["week_offset"],
                    y=seg["rank"],
                    mode="lines+markers",
                    name=f"专辑榜排名 ({album_name})",
                    legendgroup="album_rank",
                    showlegend=(i == 0),
                    line={"color": "#B8860B", "width": 2.5},
                    marker={"size": 6},
                    hovertemplate="Week %{x}: #%{y}<extra></extra>",
                )
            )

    # ── 艺人榜排名（仅连续周连线） ──────────────────────────────────
    art_r = cycle.get("artist_ranks", pd.DataFrame())
    if not art_r.empty:
        segments = _split_consecutive_segments(art_r)
        for i, seg in enumerate(segments):
            fig.add_trace(
                go.Scatter(
                    x=seg["week_offset"],
                    y=seg["rank"],
                    mode="lines+markers",
                    name="艺人榜排名",
                    legendgroup="artist_rank",
                    showlegend=(i == 0),
                    line={"color": "#C45C3A", "width": 1.5, "dash": "dash"},
                    marker={"size": 4},
                    hovertemplate="Week %{x}: #%{y}<extra></extra>",
                )
            )

    # ── 先行曲单曲榜排名线 ──────────────────────────────────────────
    for i, asr in enumerate(advance_single_ranks):
        ranks = asr["ranks"]
        if ranks.empty:
            continue
        color = ADVANCE_SINGLE_COLORS[i % len(ADVANCE_SINGLE_COLORS)]
        name = asr["name"]
        segments = _split_consecutive_segments(ranks)
        for j, seg in enumerate(segments):
            fig.add_trace(
                go.Scatter(
                    x=seg["week_offset"],
                    y=seg["rank"],
                    mode="lines+markers",
                    name=f"先行曲单曲榜: {name}",
                    legendgroup=f"adv_{i}",
                    showlegend=(j == 0),
                    line={"color": color, "width": 1.8, "dash": "dot"},
                    marker={"size": 5, "symbol": "diamond"},
                    hovertemplate=f"先行曲: {name}<br>Week %{{x}}: #%{{y}}<extra></extra>",
                )
            )

    # ── 最佳走势单曲排名线 ──────────────────────────────────────────
    if best_track_ranks is not None and not best_track_ranks["ranks"].empty:
        ranks = best_track_ranks["ranks"]
        name = best_track_ranks["name"]
        segments = _split_consecutive_segments(ranks)
        for j, seg in enumerate(segments):
            fig.add_trace(
                go.Scatter(
                    x=seg["week_offset"],
                    y=seg["rank"],
                    mode="lines+markers",
                    name=f"最佳单曲榜: {name}",
                    legendgroup="best_track",
                    showlegend=(j == 0),
                    line={"color": "#9B4B3A", "width": 1.8, "dash": "dashdot"},
                    marker={"size": 5, "symbol": "triangle-up"},
                    hovertemplate=f"最佳走势: {name}<br>Week %{{x}}: #%{{y}}<extra></extra>",
                )
            )

    # ── 专辑播放量柱状图 ────────────────────────────────────────────
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

    # ── 先行曲发行时间标记 ──────────────────────────────────────────
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


def _render_bonus_tracks(df_raw, artist_name, group_albums, primary_name):
    """显示来自子版本（豪华版、Acoustic版等）的加曲。

    从非 primary 的组成员中找出独有曲目（不在 primary 版本中的 track_id），
    统计其播放数据并展示。
    """
    non_primary = [a for a in group_albums if a != primary_name]
    if not non_primary:
        return

    from app.db import get_db

    conn = get_db()
    # Primary album tracks
    primary_rows = conn.execute(
        """SELECT DISTINCT ta.track_id
           FROM track_albums ta
           JOIN albums al ON ta.album_id = al.album_id
           WHERE al.album_name = ?""",
        [primary_name],
    ).fetchall()
    primary_tracks = {row[0] for row in primary_rows}

    # Tracks from sub-versions
    placeholders = ",".join("?" for _ in non_primary)
    sub_rows = conn.execute(
        f"""SELECT DISTINCT ta.track_id, al.album_name
            FROM track_albums ta
            JOIN albums al ON ta.album_id = al.album_id
            WHERE al.album_name IN ({placeholders})""",
        non_primary,
    ).fetchall()
    sub_track_ids = {row[0] for row in sub_rows}
    track_source = {row[0]: row[1] for row in sub_rows}
    conn.close()

    # Bonus tracks = tracks in sub versions but not in primary
    bonus_track_ids = sub_track_ids - primary_tracks
    if not bonus_track_ids:
        return

    # Query play stats for bonus tracks
    bonus_data = df_raw[
        (df_raw["artist_name"] == artist_name)
        & (df_raw["track_id"].isin(bonus_track_ids))
    ]
    if bonus_data.empty:
        return

    bonus_stats = (
        bonus_data.groupby(["track_id", "track_name"])
        .agg(
            play_count=("ms_played", "count"),
            first_week=("billboard_week", "min"),
        )
        .reset_index()
    )

    bonus_stats["source_album"] = bonus_stats["track_id"].map(track_source)

    st.divider()
    st.subheader(f"加曲来源（{len(bonus_stats)} 首）")
    st.caption("来自豪华版、Acoustic版等子版本，未出现在主版本中的额外曲目")

    display = bonus_stats.sort_values("play_count", ascending=False).head(30)
    display["首次出现"] = display["first_week"].astype(str)
    display = display.rename(columns={
        "track_name": "歌曲",
        "source_album": "来源专辑",
        "play_count": "总播放次数",
    })
    st.dataframe(
        display[["歌曲", "来源专辑", "总播放次数", "首次出现"]],
        use_container_width=True,
        hide_index=True,
    )


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

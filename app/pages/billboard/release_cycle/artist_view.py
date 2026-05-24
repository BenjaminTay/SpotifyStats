"""发行周期分析 — 艺人总览视图."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from app.styles import PLOTLY_TEMPLATE, COLORS

from app.pages.billboard.release_cycle.shared import (
    load_artist_releases,
    compute_artist_play_timeline,
    compute_release_cycle,
    compute_release_metrics,
    compute_artist_summary,
    fill_summary_from_cycles,
    format_artist_impact,
    format_market_impact,
)


def render_artist_overview(artist_name, df_raw, weekly, weekly_artist, weekly_album):
    """渲染艺人总览视图。"""
    releases = load_artist_releases(artist_name)

    if releases.empty:
        st.warning(f"未找到 {artist_name} 的发行信息（可能缺少 Spotify 元数据）。")
        return

    # ── 预计算共享数据（一次过滤/聚合，所有发行复用） ──────────────
    artist_df = df_raw[df_raw["artist_name"] == artist_name]

    artist_median = None
    if not artist_df.empty:
        dow = artist_df["ts_date_dt"].dt.dayofweek
        week_start = artist_df["ts_date_dt"] - pd.to_timedelta(dow, unit="D")
        agg = artist_df.groupby(week_start).agg(play_count=("ms_played", "count"))
        if not agg.empty:
            artist_median = float(agg["play_count"].median())

    total_daily = df_raw.groupby("ts_date_dt")["ms_played"].count()
    total_daily.name = "play_count"

    # ── 预计算所有发行的 cycle + metrics（一次计算，多处复用） ──────
    all_cycles = {}
    all_metrics = {}
    for _, rel in releases.iterrows():
        key = rel["album_name"]
        cycle = compute_release_cycle(
            df_raw, artist_name, rel["album_name"], rel["release_date"],
            weekly_artist=weekly_artist, weekly_album=weekly_album,
            weeks_before=4, weeks_after=24,
            artist_df=artist_df, artist_median=artist_median, total_daily=total_daily,
        )
        all_cycles[key] = cycle
        all_metrics[key] = compute_release_metrics(cycle, rel["album_type"])

    # ── KPI Cards ──────────────────────────────────────────────────────
    summary = compute_artist_summary(artist_name, releases, weekly, weekly_artist, weekly_album)
    fill_summary_from_cycles(summary, artist_name, releases, all_cycles, df_raw)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("发行总数", f"{summary['total_albums']} 专辑 / {summary['total_singles']} 单曲")
    with col2:
        st.metric("专辑空冠次数", f"{summary['album_debut_no1_count']} 次")
    with col3:
        st.metric("单曲空冠次数", f"{summary['single_debut_no1_count']} 次")
    with col4:
        st.metric("同周双空冠", f"{summary['double_debut_count']} 次")
    with col5:
        st.metric("最大艺人冲击力", format_artist_impact(summary["max_artist_impact"]),
                  delta=summary['max_artist_impact_album'][:20] if summary['max_artist_impact_album'] else None)
        st.metric("最大大盘冲击力", format_market_impact(summary["max_market_impact"]),
                  delta=summary['max_market_impact_album'][:20] if summary['max_market_impact_album'] else None)
    with col6:
        st.metric("回榜歌曲总数", f"{summary['total_catalog_reentries']} 首")

    st.divider()

    # ── 艺人周榜排名趋势图（标记发行事件） ──────────────────────────
    st.subheader(f"{artist_name} · 排名趋势与发行事件")

    artist_timeline = compute_artist_play_timeline(df_raw, artist_name)
    if artist_timeline.empty:
        st.caption("该艺人在当前过滤条件下无播放记录")
        return

    artist_timeline["billboard_week"] = pd.to_datetime(artist_timeline["billboard_week"])
    if weekly_artist is not None:
        art_ranks = weekly_artist[weekly_artist["artist_name"] == artist_name][
            ["billboard_week", "rank"]
        ].copy()
        art_ranks["billboard_week"] = pd.to_datetime(art_ranks["billboard_week"])
        artist_timeline = artist_timeline.merge(art_ranks, on="billboard_week", how="left")
    else:
        artist_timeline["rank"] = None

    # Chart x-axis range: start from first play data, not earliest release
    first_play_week = artist_timeline["billboard_week"].min()
    last_play_week = artist_timeline["billboard_week"].max()

    fig = go.Figure()

    # Play count bars (secondary y-axis)
    fig.add_trace(
        go.Bar(
            x=artist_timeline["billboard_week"],
            y=artist_timeline["play_count"],
            name="周播放次数",
            marker_color="rgba(184, 134, 11, 0.25)",
            yaxis="y2",
            hovertemplate="%{y:,} 次<extra></extra>",
        )
    )

    # Rank line (primary y-axis, reversed)
    charted = artist_timeline[artist_timeline["rank"].notna()]
    if not charted.empty:
        fig.add_trace(
            go.Scatter(
                x=charted["billboard_week"],
                y=charted["rank"],
                mode="lines+markers",
                name="艺人榜排名",
                line={"color": "#B8860B", "width": 2},
                marker={"size": 6, "color": "#B8860B"},
                hovertemplate="#%{y}<extra></extra>",
            )
        )

    # Release markers — only show releases within or near the play data range
    for _, rel in releases.iterrows():
        rel_date = rel["release_date"]
        album_name = rel["album_name"]
        album_type = rel["album_type"]

        # Skip releases far before the first play data
        if rel_date < first_play_week - pd.Timedelta(weeks=4):
            continue

        marker_color = "#C45C3A" if album_type == "album" else "#D4A84B"
        marker_symbol = "star-triangle-down" if album_type == "album" else "diamond"

        fig.add_trace(
            go.Scatter(
                x=[rel_date],
                y=[1],
                mode="markers+text",
                name=f"{album_name} ({album_type})",
                text=[album_name[:15]],
                textposition="top center",
                marker={"size": 12, "color": marker_color, "symbol": marker_symbol},
                hovertemplate=f"{album_name}<br>{rel_date.strftime('%Y-%m-%d')}<br>{album_type}<extra></extra>",
            )
        )

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
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
        xaxis={
            "title": "",
            "gridcolor": "rgba(139,115,85,0.08)",
            "range": [first_play_week, last_play_week],
        },
        height=450,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── 发行卡片流 ─────────────────────────────────────────────────────
    st.subheader("发行列表")

    albums = releases[releases["album_type"] == "album"]
    singles_df = releases[releases["album_type"] == "single"]

    if not albums.empty:
        st.caption(f"专辑 ({len(albums)})")
        cols = st.columns(min(len(albums), 3))
        for i, (_, rel) in enumerate(albums.iterrows()):
            with cols[i % 3]:
                key = rel["album_name"]
                _render_release_card(rel, artist_name, df_raw, weekly_artist, weekly_album,
                                     cycle=all_cycles.get(key), metrics=all_metrics.get(key))

    if not singles_df.empty:
        st.caption(f"单曲 ({len(singles_df)})")
        cols = st.columns(min(len(singles_df), 4))
        for i, (_, rel) in enumerate(singles_df.iterrows()):
            with cols[i % 4]:
                key = rel["album_name"]
                _render_release_card(rel, artist_name, df_raw, weekly_artist, weekly_album,
                                     cycle=all_cycles.get(key), metrics=all_metrics.get(key))

    st.divider()

    # ── 对比入口 ───────────────────────────────────────────────────────
    st.caption("勾选 2-5 张专辑/单曲后可进入对比视图")
    compare_candidates = []
    for _, rel in releases.iterrows():
        key = f"rc_cmp_{rel['spotify_album_id']}"
        if st.checkbox(
            f"{rel['album_name']} ({rel['album_type']}, {rel['release_date'].strftime('%Y-%m-%d')})",
            key=key,
        ):
            compare_candidates.append({
                "artist_name": artist_name,
                "album_name": rel["album_name"],
                "release_date": rel["release_date"],
            })

    if len(compare_candidates) >= 2:
        if st.button("对比选中发行", type="primary", key="rc_compare_btn"):
            st.session_state.rc_compare_queue = compare_candidates
            st.session_state.rc_view = "compare"
            st.rerun()
    elif 1 <= len(compare_candidates) < 2:
        st.caption("至少需要勾选 2 项才能对比")


def _render_release_card(rel, artist_name, df_raw, weekly_artist, weekly_album,
                         cycle=None, metrics=None):
    """渲染单张发行卡片（含被合并子专辑列表）。

    可传入预计算的 cycle 和 metrics 以跳过重复计算。
    """
    import json

    album_name = rel["album_name"]
    release_date = rel["release_date"]
    album_type = rel["album_type"]

    if cycle is None:
        cycle = compute_release_cycle(
            df_raw, artist_name, album_name, release_date,
            weekly_artist=weekly_artist, weekly_album=weekly_album,
            weeks_before=4, weeks_after=24,
        )
    if metrics is None:
        metrics = compute_release_metrics(cycle, album_type)

    peak_str = f"#{metrics['peak_rank']}" if metrics["peak_rank"] else "未入榜"
    debut_str = f"空降 #{metrics['debut_rank']}" if metrics["debut_rank"] else "—"
    impact_str = format_artist_impact(metrics["artist_impact"])
    market_str = format_market_impact(metrics["market_impact"])
    weeks_str = f"{metrics['weeks_on_chart']} 周" if metrics["weeks_on_chart"] else "—"

    # 构建子专辑列表 HTML
    sub_albums_html = ""
    sub_raw = rel.get("sub_albums")
    if pd.notna(sub_raw) and sub_raw:
        try:
            sub_albums = json.loads(sub_raw) if isinstance(sub_raw, str) else sub_raw
        except (json.JSONDecodeError, TypeError):
            sub_albums = []
        if sub_albums:
            items = []
            for sa in sub_albums:
                sa_name = sa.get("album_name", "")
                sa_date = sa.get("release_date", "") or "—"
                sa_type = sa.get("album_type", "")
                type_badge = {"album": "🟤", "single": "🟡"}.get(sa_type, "⚪")
                items.append(
                    f'<span style="color:#8B7355;">└ {type_badge} {sa_name}'
                    f'<span style="color:#AB9B85;font-size:0.62rem;"> · {sa_date}</span></span>'
                )
            sub_albums_html = (
                '<div style="margin-top:0.35rem;padding-top:0.35rem;'
                'border-top:1px dashed rgba(139,115,85,0.12);'
                'color:#8B7355;font-size:0.66rem;line-height:1.5;">'
                + "<br>".join(items) +
                '</div>'
            )

    card_html = f"""
    <div style="
        background: var(--bg-card, #FFFFFF);
        border: 1px solid var(--border, rgba(139,115,85,0.12));
        border-left: 3px solid var(--gold, #B8860B);
        border-radius: var(--radius, 12px);
        padding: 0.85rem 1rem;
        margin-bottom: 0.6rem;
        font-family: var(--font-body, 'Palatino', serif);
        font-size: 0.78rem;
    ">
        <div style="font-weight:700;color:#2C2416;margin-bottom:0.3rem;">{album_name}</div>
        <div style="color:#8B7355;font-size:0.68rem;margin-bottom:0.4rem;">
            {release_date.strftime('%Y-%m-%d')} · {album_type}
        </div>
        <div style="display:flex;gap:1rem;color:#5C3D2E;font-size:0.7rem;">
            <span>Peak: {peak_str}</span><span>{debut_str}</span>
            <span>{weeks_str}</span><span>艺人: {impact_str}</span><span>大盘: {market_str}</span>
        </div>
        {sub_albums_html}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    if st.button("查看详情", key=f"rc_detail_{rel['spotify_album_id']}"):
        st.session_state.rc_view = "album"
        st.session_state.rc_selected_album = album_name
        st.rerun()

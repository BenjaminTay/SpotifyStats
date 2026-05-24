"""Billboard Versus tab — side-by-side comparison of tracks, albums, and artists."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from .shared import _resolve_album_members

VS_COLORS = {"A": "#B8860B", "B": "#C45C3A"}

_VS_TEMPLATE = {
    "layout": {
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#8B7355", "size": 11, "family": "Palatino, Book Antiqua, serif"},
        "xaxis": {"gridcolor": "rgba(139,115,85,0.08)", "linecolor": "rgba(139,115,85,0.15)"},
        "yaxis": {"gridcolor": "rgba(139,115,85,0.08)", "linecolor": "rgba(139,115,85,0.15)"},
        "legend": {"font": {"color": "#8B7355"}},
        "margin": {"l": 10, "r": 10, "t": 40, "b": 10},
        "hoverlabel": {"bgcolor": "#FFFFFF", "font": {"color": "#2C2416"}, "bordercolor": "#D4A84B"},
    }
}

_VS_OVERRIDE_KEYS = ("xaxis", "yaxis", "legend", "title")


def _rank_chart(grp_a, grp_b, label_a, label_b, y_label="排名", invert_y=True):
    """Draw a dual-line rank-over-time chart comparing two entities."""
    fig = go.Figure()
    for grp, label, color in [(grp_a, label_a, VS_COLORS["A"]), (grp_b, label_b, VS_COLORS["B"])]:
        if grp is None or len(grp) == 0:
            continue
        g = grp.sort_values("billboard_week")
        fig.add_trace(go.Scatter(
            x=g["billboard_week"], y=g["rank"],
            name=label, mode="lines+markers",
            line={"color": color, "width": 2.5},
            marker={"size": 5, "color": color},
        ))
    layout = {k: v for k, v in _VS_TEMPLATE["layout"].items() if k not in _VS_OVERRIDE_KEYS}
    fig.update_layout(
        **layout,
        title="",
        yaxis={"title": y_label, "autorange": "reversed" if invert_y else True,
               "gridcolor": "rgba(139,115,85,0.08)"},
        xaxis={"title": "", "gridcolor": "rgba(139,115,85,0.08)"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def _metric_grid(metrics_a, metrics_b, label_a, label_b):
    """Render a 2xN comparison metric table."""
    cols = st.columns(2)
    for col, metrics, label in [(cols[0], metrics_a, label_a), (cols[1], metrics_b, label_b)]:
        with col:
            st.markdown(
                f'<div style="font-size:0.75rem;font-weight:700;color:#2C2416;margin-bottom:0.5rem;">{label}</div>',
                unsafe_allow_html=True,
            )
            for m in metrics:
                st.metric(label=m["label"], value=m["value"])


def _search_picker(label, full_list, key_prefix):
    """Search-to-select pattern: text input to filter, then radio with top results."""
    query = st.text_input(
        f"搜索{label}",
        placeholder=f"输入关键词搜索{label}...",
        key=f"{key_prefix}_search",
        label_visibility="collapsed",
    )

    if query and len(query) >= 1:
        filtered = [(name, val) for name, val in full_list if query.lower() in name.lower()]
    else:
        filtered = full_list[:50]

    if not filtered:
        st.caption("无匹配结果")
        return None

    options = [name for name, _ in filtered[:30]]
    selected_name = st.radio(
        f"选择{label}",
        options=options,
        index=None,
        key=f"{key_prefix}_radio",
        label_visibility="collapsed",
    )

    if selected_name:
        for name, val in filtered[:30]:
            if name == selected_name:
                return val
    return None


def _build_entity_list(df, name_col, value_col, extra_col=None):
    """Build sorted deduplicated list of (display_name, value) tuples from weekly data."""
    if extra_col:
        agg = df.groupby([value_col, name_col, extra_col])["play_count"].sum().reset_index()
        agg = agg.sort_values("play_count", ascending=False)
        result = []
        seen = set()
        for _, r in agg.iterrows():
            key = r[value_col]
            if key in seen:
                continue
            seen.add(key)
            result.append((f"{r[name_col]} — {r[extra_col]}", key))
        return result
    else:
        agg = df.groupby([name_col])["play_count"].sum().reset_index()
        agg = agg.sort_values("play_count", ascending=False)
        return [(r[name_col], r[name_col]) for _, r in agg.iterrows()]


def _ps_rank(power_scores, key_col, key_val, artist_val=None):
    """Look up power score and rank for an entity in a power_scores DataFrame.

    Returns (power_score, rank) or (None, None) if not found.
    """
    if power_scores is None or len(power_scores) == 0:
        return None, None
    ps = power_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    if artist_val is not None:
        mask = (ps.get(key_col) == key_val) & (ps.get("artist_name") == artist_val)
    else:
        mask = ps.get(key_col) == key_val
    match = ps[mask]
    if len(match) == 0:
        return None, None
    idx = match.index[0]
    return int(match.iloc[0]["power_score"]), idx + 1


# ═══════════════════════════════════════════════════════════════════════════
# Track Versus
# ═══════════════════════════════════════════════════════════════════════════

def render_track_versus(weekly, track_summary, power_scores=None):
    st.subheader("🎵 歌曲对决")
    st.caption("选择两首曾入榜的歌曲，对比它们的榜单走势和关键指标")

    track_list = _build_entity_list(weekly, "track_name", "track_id", "artist_name")

    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("歌曲 A")
        tid_a = _search_picker("歌曲 A", track_list, "vs_track")
    with col_b:
        st.caption("歌曲 B")
        tid_b = _search_picker("歌曲 B", track_list, "vs_track_b")

    if tid_a is None or tid_b is None:
        st.info("请在两侧各搜索并选择一首歌曲进行对比")
        return

    grp_a = weekly[weekly["track_id"] == tid_a].sort_values("billboard_week")
    grp_b = weekly[weekly["track_id"] == tid_b].sort_values("billboard_week")

    if len(grp_a) == 0 or len(grp_b) == 0:
        st.warning("其中一首歌在选定的年份范围内没有入榜记录")
        return

    name_a = f"{grp_a['track_name'].iloc[0]} — {grp_a['artist_name'].iloc[0]}"
    name_b = f"{grp_b['track_name'].iloc[0]} — {grp_b['artist_name'].iloc[0]}"

    st.divider()
    _rank_chart(grp_a, grp_b, name_a, name_b)

    def _track_metrics(grp, tid):
        ps_val, ps_rank = _ps_rank(power_scores, "track_id", tid)
        metrics = []
        if ps_val is not None:
            metrics.append({"label": "走势点数", "value": f"{ps_val:,}"})
            metrics.append({"label": "走势总榜排名", "value": f"#{ps_rank}"})
        metrics += [
            {"label": "入榜峰值", "value": f"#{int(grp['rank'].min())}"},
            {"label": "在榜周数", "value": f"{grp['billboard_week'].nunique()} 周"},
            {"label": "冠军周数", "value": f"{int((grp['rank'] == 1).sum())} 周"},
            {"label": "Top 5 周数", "value": f"{int((grp['rank'] <= 5).sum())} 周"},
            {"label": "总上榜播放", "value": f"{int(grp['play_count'].sum()):,}"},
        ]
        return metrics

    _metric_grid(_track_metrics(grp_a, tid_a), _track_metrics(grp_b, tid_b), name_a, name_b)


# ═══════════════════════════════════════════════════════════════════════════
# Album Versus
# ═══════════════════════════════════════════════════════════════════════════

def render_album_versus(weekly_album, weekly, album_power_scores=None, track_power_scores=None):
    st.subheader("💿 专辑对决")
    st.caption("选择两张曾入榜的专辑，对比它们的榜单表现和入榜曲目")

    agg = weekly_album.groupby(["album_name", "artist_name"])["play_count"].sum().reset_index()
    agg = agg.sort_values("play_count", ascending=False)
    album_list = [
        (f"{r['album_name']} — {r['artist_name']}", (r["album_name"], r["artist_name"]))
        for _, r in agg.iterrows()
    ]

    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("专辑 A")
        sel_a = _search_picker("专辑 A", album_list, "vs_album")
    with col_b:
        st.caption("专辑 B")
        sel_b = _search_picker("专辑 B", album_list, "vs_album_b")

    if sel_a is None or sel_b is None:
        st.info("请在两侧各搜索并选择一张专辑进行对比")
        return

    aname_a, aart_a = sel_a
    aname_b, aart_b = sel_b

    grp_a = weekly_album[
        (weekly_album["album_name"] == aname_a) & (weekly_album["artist_name"] == aart_a)
    ].sort_values("billboard_week")
    grp_b = weekly_album[
        (weekly_album["album_name"] == aname_b) & (weekly_album["artist_name"] == aart_b)
    ].sort_values("billboard_week")

    if len(grp_a) == 0 or len(grp_b) == 0:
        st.warning("其中一张专辑在选定的年份范围内没有入榜记录")
        return

    st.divider()
    _rank_chart(grp_a, grp_b, f"{aname_a} — {aart_a}", f"{aname_b} — {aart_b}")

    def _album_metrics(grp, aname, aartist):
        # Album power score and rank
        aps_val, aps_rank = _ps_rank(album_power_scores, "album_name", aname, aartist)

        # Album's track-level stats from weekly（解析 release group 成员）
        member_names, _ = _resolve_album_members(aname, aartist)
        album_tracks = weekly[weekly["album_name"].isin(member_names)]
        num_tracks = album_tracks["track_id"].nunique()
        num_no1_tracks = album_tracks[album_tracks["rank"] == 1]["track_id"].nunique()
        total_no1_weeks = int((album_tracks["rank"] == 1).sum())

        # Sum of track power scores for this album
        album_track_ids = album_tracks["track_id"].unique()
        track_ps_sum = 0
        if track_power_scores is not None and len(track_power_scores) > 0:
            track_ps_sum = int(track_power_scores[
                track_power_scores["track_id"].isin(album_track_ids)
            ]["power_score"].sum())

        metrics = []
        if aps_val is not None:
            metrics.append({"label": "走势点数", "value": f"{aps_val:,}"})
            metrics.append({"label": "走势总榜排名", "value": f"#{aps_rank}"})
        metrics += [
            {"label": "入榜峰值", "value": f"#{int(grp['rank'].min())}"},
            {"label": "在榜周数", "value": f"{grp['billboard_week'].nunique()} 周"},
            {"label": "冠军周数", "value": f"{int((grp['rank'] == 1).sum())} 周"},
            {"label": "入榜曲目数", "value": f"{num_tracks} 首"},
            {"label": "冠单数量", "value": f"{num_no1_tracks} 首"},
            {"label": "单曲冠军周数", "value": f"{total_no1_weeks} 周"},
        ]
        if track_ps_sum > 0:
            metrics.append({"label": "歌曲总走势点数", "value": f"{track_ps_sum:,}"})
        metrics.append({"label": "总播放次数", "value": f"{int(grp['play_count'].sum()):,}"})
        return metrics

    _metric_grid(
        _album_metrics(grp_a, aname_a, aart_a),
        _album_metrics(grp_b, aname_b, aart_b),
        f"{aname_a} — {aart_a}", f"{aname_b} — {aart_b}",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Artist Versus
# ═══════════════════════════════════════════════════════════════════════════

def render_artist_versus(weekly_artist, weekly, weekly_album,
                         artist_power_scores=None, track_power_scores=None,
                         album_power_scores=None):
    st.subheader("🎤 艺人对决")
    st.caption("选择两位曾入榜的艺人，对比榜单统治力和入榜曲目数量")

    artist_list = _build_entity_list(weekly_artist, "artist_name", "artist_name")

    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("艺人 A")
        sel_a = _search_picker("艺人 A", artist_list, "vs_artist")
    with col_b:
        st.caption("艺人 B")
        sel_b = _search_picker("艺人 B", artist_list, "vs_artist_b")

    if sel_a is None or sel_b is None:
        st.info("请在两侧各搜索并选择一位艺人进行对比")
        return

    grp_a = weekly_artist[weekly_artist["artist_name"] == sel_a].sort_values("billboard_week")
    grp_b = weekly_artist[weekly_artist["artist_name"] == sel_b].sort_values("billboard_week")

    if len(grp_a) == 0 or len(grp_b) == 0:
        st.warning("其中一位艺人在选定的年份范围内没有入榜记录")
        return

    st.divider()
    _rank_chart(grp_a, grp_b, sel_a, sel_b)

    def _artist_metrics(grp, artist_name):
        # Artist power score and rank
        aps_val, aps_rank = _ps_rank(artist_power_scores, "artist_name", artist_name)

        # Track-level stats
        artist_tracks = weekly[weekly["artist_name"] == artist_name]
        num_tracks = artist_tracks["track_id"].nunique()
        num_no1_tracks = artist_tracks[artist_tracks["rank"] == 1]["track_id"].nunique()
        total_no1_track_weeks = int((artist_tracks["rank"] == 1).sum())

        # Sum of track power scores for this artist
        artist_track_ids = artist_tracks["track_id"].unique()
        track_ps_sum = 0
        if track_power_scores is not None and len(track_power_scores) > 0:
            track_ps_sum = int(track_power_scores[
                track_power_scores["track_id"].isin(artist_track_ids)
            ]["power_score"].sum())

        # Album-level stats
        artist_albums = weekly_album[weekly_album["artist_name"] == artist_name]
        num_albums = artist_albums["album_name"].dropna().nunique()
        num_no1_albums = artist_albums[artist_albums["rank"] == 1]["album_name"].nunique()
        total_no1_album_weeks = int((artist_albums["rank"] == 1).sum())

        # Sum of album power scores for this artist
        album_ps_sum = 0
        if album_power_scores is not None and len(album_power_scores) > 0:
            album_ps_sum = int(album_power_scores[
                album_power_scores["artist_name"] == artist_name
            ]["power_score"].sum())

        metrics = []
        if aps_val is not None:
            metrics.append({"label": "走势点数", "value": f"{aps_val:,}"})
            metrics.append({"label": "走势总榜排名", "value": f"#{aps_rank}"})
        metrics += [
            {"label": "入榜峰值", "value": f"#{int(grp['rank'].min())}"},
            {"label": "在榜周数", "value": f"{grp['billboard_week'].nunique()} 周"},
            {"label": "冠军周数", "value": f"{int((grp['rank'] == 1).sum())} 周"},
            {"label": "入榜曲目数", "value": f"{num_tracks} 首"},
            {"label": "冠单数量", "value": f"{num_no1_tracks} 首"},
            {"label": "冠军单曲周数", "value": f"{total_no1_track_weeks} 周"},
        ]
        if track_ps_sum > 0:
            metrics.append({"label": "歌曲总走势点数", "value": f"{track_ps_sum:,}"})
        metrics += [
            {"label": "入榜专辑数", "value": f"{num_albums} 张"},
            {"label": "冠专数量", "value": f"{num_no1_albums} 张"},
            {"label": "冠军专辑周数", "value": f"{total_no1_album_weeks} 周"},
        ]
        if album_ps_sum > 0:
            metrics.append({"label": "专辑总走势点数", "value": f"{album_ps_sum:,}"})
        metrics.append({"label": "总播放次数", "value": f"{int(grp['play_count'].sum()):,}"})
        return metrics

    _metric_grid(
        _artist_metrics(grp_a, sel_a),
        _artist_metrics(grp_b, sel_b),
        sel_a, sel_b,
    )

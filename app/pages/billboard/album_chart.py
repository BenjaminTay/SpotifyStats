"""Tab: 专辑榜单 (Album Billboard Summary)."""

import html as _html
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from .shared import _bb_url, _render_bb_table


def render(weekly, weekly_album, track_per_album, album_track_counts, bb_album_top_n):
    # ── Consume cross-tab album navigation ───────────────────────────
    nav_album = st.session_state.get("bb_selected_album_name")
    nav_album_artist = st.session_state.get("_bb_selected_album_artist")
    if nav_album is not None and nav_album_artist is not None:
        st.session_state.bb_selected_album_name = None
        st.session_state._bb_selected_album_artist = None
        st.session_state.bb_album_search = ""
        full_albums = album_track_counts.reset_index(drop=True)
        mask = (full_albums["album_name"] == nav_album) & (full_albums["artist_name"] == nav_album_artist)
        matches = full_albums[mask]
        if not matches.empty:
            st.session_state.bb_album_selector_idx = int(matches.index[0])
        st.rerun()

    # Album search
    album_search = st.text_input(
        "搜索专辑/艺人",
        placeholder="输入专辑名或艺人名筛选...",
        key="bb_album_search",
    )

    if album_search:
        term = album_search.lower()
        mask = (
            album_track_counts["album_name"].str.lower().str.contains(term, na=False)
            | album_track_counts["artist_name"].str.lower().str.contains(term, na=False)
        )
        filtered_albums = album_track_counts[mask].reset_index(drop=True)
    else:
        filtered_albums = album_track_counts.reset_index(drop=True)

    # Album selector
    album_labels = [
        f"{r['album_name']} — {r['artist_name']} ({int(r['total_tracks'])}首入榜)"
        for _, r in filtered_albums.iterrows()
    ]

    if not album_labels:
        if album_search:
            st.warning(f"没有匹配「{album_search}」的专辑")
        else:
            st.warning("暂无数据")
    else:
        selected_album_idx = st.selectbox(
            "选择专辑",
            options=range(len(album_labels)),
            format_func=lambda i: album_labels[i],
            key="bb_album_selector_idx",
        )
        selected_album_row = filtered_albums.iloc[selected_album_idx]
        selected_album = selected_album_row["album_name"]
        selected_album_artist = selected_album_row["artist_name"]

        # ── Album summary cards ───────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("入榜曲数", f"{int(selected_album_row['total_tracks'])} 首")
        col2.metric(
            "最佳 Peak",
            f"#{int(selected_album_row['best_peak'])}",
            delta=selected_album_row["best_peak_track"][:30],
        )
        col3.metric("总上榜周数", f"{int(selected_album_row['total_weeks'])} 周")
        col4.metric("平均在榜", f"{selected_album_row['avg_weeks']:.1f} 周")

        col1b, col2b, col3b, col4b = st.columns(4)
        col1b.metric("#1 曲数", f"{int(selected_album_row['top1'])} 首")
        col2b.metric("Top 5 曲数", f"{int(selected_album_row['top5'])} 首")
        col3b.metric("Top 10 曲数", f"{int(selected_album_row['top10'])} 首")
        col4b.metric("#1周数", f"{int(selected_album_row['weeks_at_no1'])} 周")

        st.divider()

        # ── Secondary sort selector ───────────────────────────────────
        album_tiebreaker = st.radio(
            "Peak 相同时按",
            ["在榜周数", "Peak 周数"],
            horizontal=True,
            key="album_tiebreaker",
        )

        # ── Charting tracks table ─────────────────────────────────────
        alb_tracks = track_per_album[
            (track_per_album["album_name"] == selected_album)
            & (track_per_album["artist_name"] == selected_album_artist)
        ].copy()

        if album_tiebreaker == "在榜周数":
            alb_tracks = alb_tracks.sort_values(
                ["peak_position", "weeks_on_chart", "weeks_at_peak"], ascending=[True, False, False]
            )
        else:
            alb_tracks = alb_tracks.sort_values(
                ["peak_position", "weeks_at_peak", "weeks_on_chart"], ascending=[True, False, False]
            )
        alb_tracks = alb_tracks.reset_index(drop=True)
        alb_tracks.index = alb_tracks.index + 1

        display_alb = alb_tracks[
            ["track_name", "peak_position", "weeks_on_chart", "weeks_at_peak",
             "first_week", "first_peak_week", "last_week", "total_chart_plays"]
        ].copy()
        display_alb["first_peak_week"] = display_alb["first_peak_week"].astype(str)
        display_alb["first_week"] = display_alb["first_week"].astype(str)
        display_alb["last_week"] = display_alb["last_week"].astype(str)
        display_alb.columns = ["曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "首次Peak周", "最近上榜", "总播放"]
        display_alb.index.name = "#"

        st.subheader(f"《{selected_album}》 · 入榜曲目")

        _alb_t_headers = ["#", "曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "首次Peak周", "最近上榜", "总播放"]
        _alb_t_rows = []
        for _i, _r in alb_tracks.iterrows():
            _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
            _alb_t_rows.append([
                str(_r.name),
                (_html.escape(str(_r["track_name"])), _track_url),
                str(_r["peak_position"]),
                str(_r["weeks_on_chart"]),
                str(_r["weeks_at_peak"]),
                (_html.escape(str(_r["first_week"])), _bb_url(bb_nav="week", bb_date=_r['first_week'], bb_tab="📋 周榜")),
                (_html.escape(str(_r["first_peak_week"])), _bb_url(bb_nav="week", bb_date=_r['first_peak_week'], bb_tab="📋 周榜")),
                (_html.escape(str(_r["last_week"])), _bb_url(bb_nav="week", bb_date=_r['last_week'], bb_tab="📋 周榜")),
                f"{_r['total_chart_plays']:,}",
            ])
        _render_bb_table(_alb_t_headers, _alb_t_rows,
            col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 8: "num"})

        # ── Album weekly charting history ───────────────────────────────
        st.divider()
        st.subheader(f"《{selected_album}》· 每周入榜概况")

        alb_track_ids = set(alb_tracks["track_id"].tolist())
        album_weekly = weekly[weekly["track_id"].isin(alb_track_ids)]
        alw_summary = (
            album_weekly.groupby("billboard_week")
            .agg(
                tracks_on_chart=("track_id", "nunique"),
                total_plays=("play_count", "sum"),
            )
            .reset_index()
        )

        # Get #1 track names and IDs per week
        album_no1_grp = (
            album_weekly[album_weekly["rank"] == 1]
            .groupby("billboard_week")
        )
        album_no1 = (
            album_no1_grp["track_name"]
            .apply(lambda x: "、".join(dict.fromkeys(x)))
            .reset_index()
        )
        album_no1.columns = ["billboard_week", "no1_track_names"]
        album_no1_ids = (
            album_no1_grp.agg(no1_track_id=("track_id", "first"), no1_count=("track_id", "nunique"))
            .reset_index()
        )
        album_no1 = album_no1.merge(album_no1_ids, on="billboard_week", how="left")
        alw_summary = alw_summary.merge(album_no1, on="billboard_week", how="left")
        alw_summary["no1_track_names"] = alw_summary["no1_track_names"].fillna("—")
        alw_summary = alw_summary.sort_values("billboard_week", ascending=False)

        if alw_summary.empty:
            st.caption("该专辑在当前过滤条件下无上榜记录")
        else:
            _alw_headers = ["周", "上榜曲数", "当周总播放", "#1 曲目"]
            _alw_rows = []
            for _, _r in alw_summary.iterrows():
                _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜")
                no1_names = str(_r["no1_track_names"])
                if pd.notna(_r.get("no1_count")) and int(_r["no1_count"]) == 1 and pd.notna(_r.get("no1_track_id")):
                    no1_url = _bb_url(bb_nav="track", bb_id=int(_r['no1_track_id']), bb_tab="🎵 单曲历史")
                    _no1_cell = (_html.escape(no1_names), no1_url)
                else:
                    _no1_cell = _html.escape(no1_names)
                _alw_rows.append([
                    (str(_r["billboard_week"]), _week_url),
                    str(_r["tracks_on_chart"]),
                    f"{_r['total_plays']:,}",
                    _no1_cell,
                ])
            _render_bb_table(_alw_headers, _alw_rows,
                col_formats={1: "num", 2: "num"})
        # ── Album Weekly Chart History (专辑周榜) ────────────────────────
        st.divider()
        st.subheader(f"《{selected_album}》· 专辑周榜历史")

        album_wk_history = weekly_album[(weekly_album["album_name"] == selected_album) & (weekly_album["artist_name"] == selected_album_artist)].copy()
        if album_wk_history.empty:
            st.info("该专辑在当前过滤条件下无周榜记录")
        else:
            album_wk_history = album_wk_history.sort_values("billboard_week", ascending=False)
            album_wk_history["total_hours"] = album_wk_history["total_ms"] / 3_600_000

            _alwh_headers = ["周", "排名", "总播放次数", "入榜曲数", "总时长(小时)"]
            _alwh_rows = []
            for _, _r in album_wk_history.iterrows():
                _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜", bb_subtab="1")
                _alwh_rows.append([
                    (_html.escape(str(_r["billboard_week"])), _week_url),
                    str(_r["rank"]),
                    f"{_r['play_count']:,}",
                    str(_r["tracks_count"]),
                    f"{_r['total_hours']:.1f}",
                ])
            _render_bb_table(_alwh_headers, _alwh_rows,
                col_formats={1: "rank", 2: "num", 3: "num", 4: "num"}, height="500px")

            # Rank trend chart
            st.subheader("专辑周榜排名趋势")
            trend_data2 = album_wk_history.sort_values("billboard_week", ascending=True).copy()
            peak_row2 = trend_data2.loc[trend_data2["rank"].idxmin()]
            fig_alb_trend = go.Figure()
            fig_alb_trend.add_trace(
                go.Scatter(
                    x=trend_data2["billboard_week"],
                    y=trend_data2["rank"],
                    mode="lines+markers",
                    name="排名",
                    line={"color": "#B8860B", "width": 2},
                    marker={"size": 6, "color": "#B8860B"},
                )
            )
            fig_alb_trend.add_trace(
                go.Scatter(
                    x=[peak_row2["billboard_week"]],
                    y=[peak_row2["rank"]],
                    mode="markers+text",
                    name=f"Peak #{int(peak_row2['rank'])}",
                    text=[f"#{int(peak_row2['rank'])}"],
                    textposition="top center",
                    marker={"size": 14, "color": "#C45C3A", "symbol": "star"},
                )
            )
            fig_alb_trend.update_layout(
                yaxis={"autorange": "reversed", "title": "排名", "gridcolor": "rgba(139,115,85,0.08)"},
                xaxis={"title": "", "gridcolor": "rgba(139,115,85,0.08)"},
                height=400,
                hovermode="x unified",
                showlegend=False,
            )
            st.plotly_chart(fig_alb_trend, use_container_width=True)

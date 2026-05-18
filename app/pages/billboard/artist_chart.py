"""Tab: 艺人榜单 (Artist Billboard Summary)."""

import html as _html
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from .shared import _bb_url, _render_bb_table


def render(weekly, weekly_artist, artist_track_counts, artist_summary, track_summary, bb_artist_top_n):
    # ── Consume cross-tab artist navigation ──────────────────────────
    nav_artist = st.session_state.get("bb_selected_artist_name")
    if nav_artist is not None:
        st.session_state.bb_selected_artist_name = None
        st.session_state.bb_artist_search = ""
        all_names = artist_track_counts["artist_name"].tolist()
        if nav_artist in all_names:
            st.session_state.bb_artist_selector_idx = all_names.index(nav_artist)
        st.rerun()

    # Artist search
    artist_search = st.text_input(
        "搜索艺人",
        placeholder="输入艺人名筛选...",
        key="bb_artist_search",
    )

    if artist_search:
        term = artist_search.lower()
        mask = artist_track_counts["artist_name"].str.lower().str.contains(term, na=False)
        filtered_artists = artist_track_counts[mask].reset_index(drop=True)
    else:
        filtered_artists = artist_track_counts.reset_index(drop=True)

    # Artist selector
    artist_labels = [
        f"{r['artist_name']} ({int(r['total_tracks'])}首入榜)"
        for _, r in filtered_artists.iterrows()
    ]
    artist_names = filtered_artists["artist_name"].tolist()

    if not artist_labels:
        if artist_search:
            st.warning(f"没有匹配「{artist_search}」的艺人")
        else:
            st.warning("暂无数据")
    else:
        selected_artist_idx = st.selectbox(
            "选择艺人",
            options=range(len(artist_labels)),
            format_func=lambda i: artist_labels[i],
            key="bb_artist_selector_idx",
        )
        selected_artist = artist_names[selected_artist_idx]

        # ── Artist summary cards ──────────────────────────────────────
        art_row = artist_track_counts[artist_track_counts["artist_name"] == selected_artist].iloc[0]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("入榜曲数", f"{int(art_row['total_tracks'])} 首")
        col2.metric("最佳 Peak", f"#{int(art_row['best_peak'])}", delta=art_row["best_peak_track"][:30])
        col3.metric("总上榜周数", f"{int(art_row['total_weeks'])} 周")
        col4.metric("平均在榜", f"{art_row['avg_weeks']:.1f} 周")

        col1b, col2b, col3b, col4b = st.columns(4)
        col1b.metric("#1 曲数", f"{int(art_row['top1'])} 首")
        col2b.metric("Top 5 曲数", f"{int(art_row['top5'])} 首")
        col3b.metric("Top 10 曲数", f"{int(art_row['top10'])} 首")
        col4b.metric("#1周数", f"{int(art_row['weeks_at_no1'])} 周")

        st.divider()

        # ── Secondary sort selector ───────────────────────────────────
        peak_tiebreaker = st.radio(
            "Peak 相同时按",
            ["在榜周数", "Peak 周数"],
            horizontal=True,
            key="artist_tiebreaker",
        )

        # ── Charting tracks table ─────────────────────────────────────
        art_tracks = artist_summary[artist_summary["artist_name"] == selected_artist].copy()
        # Merge weeks_at_no1 and first_peak_week from track_summary
        art_tracks = art_tracks.merge(
            track_summary[["track_id", "weeks_at_no1", "first_peak_week"]],
            on="track_id", how="left"
        )
        art_tracks["weeks_at_no1"] = art_tracks["weeks_at_no1"].fillna(0).astype(int)
        art_tracks["first_peak_week"] = art_tracks["first_peak_week"].astype(str)
        # Three-level sort: Peak → chosen tiebreaker → the other
        if peak_tiebreaker == "在榜周数":
            art_tracks = art_tracks.sort_values(
                ["peak_position", "weeks_on_chart", "weeks_at_peak"], ascending=[True, False, False]
            )
        else:
            art_tracks = art_tracks.sort_values(
                ["peak_position", "weeks_at_peak", "weeks_on_chart"], ascending=[True, False, False]
            )
        art_tracks = art_tracks.reset_index(drop=True)
        art_tracks.index = art_tracks.index + 1

        display_art = art_tracks[
            ["track_name", "peak_position", "weeks_on_chart", "weeks_at_peak",
             "first_week", "first_peak_week", "last_week", "total_chart_plays"]
        ].copy()
        display_art["first_week"] = display_art["first_week"].astype(str)
        display_art["last_week"] = display_art["last_week"].astype(str)
        display_art.columns = ["曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "首次Peak周", "最近上榜", "总播放"]
        display_art.index.name = "#"

        st.subheader(f"{selected_artist} · 入榜曲目")

        _art_headers = ["#", "曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "首次Peak周", "最近上榜", "总播放"]
        _art_rows = []
        for _, r in art_tracks.iterrows():
            track_url = _bb_url(bb_nav="track", bb_id=r['track_id'], bb_tab="🎵 单曲历史")
            _art_rows.append([
                str(r.name),
                (_html.escape(str(r["track_name"])), track_url),
                str(r["peak_position"]),
                str(r["weeks_on_chart"]),
                str(r["weeks_at_peak"]),
                (_html.escape(str(r["first_week"])), _bb_url(bb_nav="week", bb_date=r['first_week'], bb_tab="📋 周榜")),
                (_html.escape(str(r["first_peak_week"])), _bb_url(bb_nav="week", bb_date=r['first_peak_week'], bb_tab="📋 周榜")),
                (_html.escape(str(r["last_week"])), _bb_url(bb_nav="week", bb_date=r['last_week'], bb_tab="📋 周榜")),
                f"{r['total_chart_plays']:,}",
            ])
        _render_bb_table(_art_headers, _art_rows,
            col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 8: "num"})

        # ── Artist weekly charting history ──────────────────────────────
        st.divider()
        st.subheader(f"{selected_artist} · 每周入榜概况")

        artist_weekly = weekly[weekly["artist_name"] == selected_artist]
        aw_summary = (
            artist_weekly.groupby("billboard_week")
            .agg(
                tracks_on_chart=("track_id", "nunique"),
                total_plays=("play_count", "sum"),
            )
            .reset_index()
        )

        # Get #1 track names and IDs per week
        artist_no1_grp = (
            artist_weekly[artist_weekly["rank"] == 1]
            .groupby("billboard_week")
        )
        artist_no1 = (
            artist_no1_grp["track_name"]
            .apply(lambda x: "、".join(dict.fromkeys(x)))
            .reset_index()
        )
        artist_no1.columns = ["billboard_week", "no1_track_names"]
        artist_no1_ids = (
            artist_no1_grp.agg(no1_track_id=("track_id", "first"), no1_count=("track_id", "nunique"))
            .reset_index()
        )
        artist_no1 = artist_no1.merge(artist_no1_ids, on="billboard_week", how="left")
        aw_summary = aw_summary.merge(artist_no1, on="billboard_week", how="left")
        aw_summary["no1_track_names"] = aw_summary["no1_track_names"].fillna("—")
        aw_summary = aw_summary.sort_values("billboard_week", ascending=False)

        if aw_summary.empty:
            st.caption("该艺人在当前过滤条件下无上榜记录")
        else:
            _aw_headers = ["周", "上榜曲数", "当周总播放", "#1 曲目"]
            _aw_rows = []
            for _, r in aw_summary.iterrows():
                week_url = _bb_url(bb_nav="week", bb_date=r['billboard_week'], bb_tab="📋 周榜")
                no1_names = str(r["no1_track_names"])
                if pd.notna(r.get("no1_count")) and int(r["no1_count"]) == 1 and pd.notna(r.get("no1_track_id")):
                    no1_url = _bb_url(bb_nav="track", bb_id=int(r['no1_track_id']), bb_tab="🎵 单曲历史")
                    _no1_cell = (_html.escape(no1_names), no1_url)
                else:
                    _no1_cell = _html.escape(no1_names)
                _aw_rows.append([
                    (str(r["billboard_week"]), week_url),
                    str(r["tracks_on_chart"]),
                    f"{r['total_plays']:,}",
                    _no1_cell,
                ])
            _render_bb_table(_aw_headers, _aw_rows,
                col_formats={1: "num", 2: "num"})
        # ── Artist Weekly Chart History (艺人周榜) ────────────────────────
        st.divider()
        st.subheader(f"{selected_artist} · 艺人周榜历史")

        artist_wk_history = weekly_artist[weekly_artist["artist_name"] == selected_artist].copy()
        if artist_wk_history.empty:
            st.info("该艺人在当前过滤条件下无周榜记录")
        else:
            artist_wk_history = artist_wk_history.sort_values("billboard_week", ascending=False)
            artist_wk_history["total_hours"] = artist_wk_history["total_ms"] / 3_600_000

            _awh_headers = ["周", "排名", "总播放次数", "入榜曲数", "总时长(小时)"]
            _awh_rows = []
            for _, _r in artist_wk_history.iterrows():
                _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜", bb_subtab="2")
                _awh_rows.append([
                    (_html.escape(str(_r["billboard_week"])), _week_url),
                    str(_r["rank"]),
                    f"{_r['play_count']:,}",
                    str(_r["tracks_count"]),
                    f"{_r['total_hours']:.1f}",
                ])
            _render_bb_table(_awh_headers, _awh_rows,
                col_formats={1: "rank", 2: "num", 3: "num", 4: "num"}, height="500px")

            # Rank trend chart
            st.subheader("艺人周榜排名趋势")
            trend_data = artist_wk_history.sort_values("billboard_week", ascending=True).copy()
            peak_row = trend_data.loc[trend_data["rank"].idxmin()]
            fig_art_trend = go.Figure()
            fig_art_trend.add_trace(
                go.Scatter(
                    x=trend_data["billboard_week"],
                    y=trend_data["rank"],
                    mode="lines+markers",
                    name="排名",
                    line={"color": "#B8860B", "width": 2},
                    marker={"size": 6, "color": "#B8860B"},
                )
            )
            fig_art_trend.add_trace(
                go.Scatter(
                    x=[peak_row["billboard_week"]],
                    y=[peak_row["rank"]],
                    mode="markers+text",
                    name=f"Peak #{int(peak_row['rank'])}",
                    text=[f"#{int(peak_row['rank'])}"],
                    textposition="top center",
                    marker={"size": 14, "color": "#C45C3A", "symbol": "star"},
                )
            )
            fig_art_trend.update_layout(
                yaxis={"autorange": "reversed", "title": "排名", "gridcolor": "rgba(139,115,85,0.08)"},
                xaxis={"title": "", "gridcolor": "rgba(139,115,85,0.08)"},
                height=400,
                hovermode="x unified",
                showlegend=False,
            )
            st.plotly_chart(fig_art_trend, use_container_width=True)

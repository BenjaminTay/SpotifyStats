"""Tab: 艺人榜单 (Artist Billboard Summary)."""

import html as _html
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from .shared import _bb_url, _render_bb_table, compute_power_scores, compute_album_power_scores


def render(weekly, weekly_artist, weekly_album, artist_track_counts, artist_summary, track_summary, bb_artist_top_n, top_n, bb_album_top_n):
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

        art_row = artist_track_counts[artist_track_counts["artist_name"] == selected_artist].iloc[0]

        # ── Pre-compute power scores for delta text ────────────────────
        track_power = compute_power_scores(weekly, top_n)
        artist_track_power = track_power[track_power["artist_name"] == selected_artist]

        album_power = compute_album_power_scores(weekly_album, bb_album_top_n)
        artist_albums_all = weekly_album[weekly_album["artist_name"] == selected_artist]
        artist_album_power = album_power[album_power["artist_name"] == selected_artist]

        # ═════════════════════════════════════════════════════════════════
        # 组1: 艺人榜成绩（从 weekly_artist 计算）
        # ═════════════════════════════════════════════════════════════════
        artist_chart_data = weekly_artist[weekly_artist["artist_name"] == selected_artist]
        if not artist_chart_data.empty:
            art_chart_peak = int(artist_chart_data["rank"].min())
            art_chart_weeks = int(artist_chart_data["billboard_week"].nunique())
            art_chart_first_week = artist_chart_data["billboard_week"].min()
            art_chart_first_peak = artist_chart_data.loc[
                artist_chart_data["rank"] == art_chart_peak, "billboard_week"
            ].min()
            art_chart_no1 = int((artist_chart_data["rank"] == 1).sum())

            st.subheader("艺人榜成绩")
            car1, car2, car3, car4, car5 = st.columns(5)
            car1.metric("艺人最高排名", f"#{art_chart_peak}")
            car2.metric("进榜周数", f"{art_chart_weeks} 周")
            car3.metric("首次入榜", str(art_chart_first_week))
            car4.metric("首次Peak周", str(art_chart_first_peak))
            car5.metric("艺人 #1 周数", f"{art_chart_no1} 周")
        else:
            st.caption("该艺人暂无艺人榜记录")

        st.divider()

        # ═════════════════════════════════════════════════════════════════
        # 组2: 单曲成绩
        # ═════════════════════════════════════════════════════════════════
        # Best peak delta: highest Power Score track at that peak
        best_peak_val = int(art_row["best_peak"])
        at_peak_tracks = artist_track_power[artist_track_power["peak_position"] == best_peak_val]
        if not at_peak_tracks.empty:
            best_peak_delta = at_peak_tracks.iloc[0]["track_name"][:30]
        else:
            best_peak_delta = art_row["best_peak_track"][:30]

        st.subheader("单曲成绩")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("入榜曲数", f"{int(art_row['total_tracks'])} 首")
        col2.metric("最佳单曲Peak", f"#{best_peak_val}", delta=best_peak_delta)
        col3.metric("总上榜周数", f"{int(art_row['total_weeks'])} 周")
        col4.metric("平均在榜", f"{art_row['avg_weeks']:.1f} 周")

        col1b, col2b, col3b, col4b = st.columns(4)
        col1b.metric("#1 曲数", f"{int(art_row['top1'])} 首")
        col2b.metric("Top 5 曲数", f"{int(art_row['top5'])} 首")
        col3b.metric("Top 10 曲数", f"{int(art_row['top10'])} 首")
        col4b.metric("单曲 #1 周数", f"{int(art_row['weeks_at_no1'])} 周")

        st.divider()

        # ═════════════════════════════════════════════════════════════════
        # 组3: 专辑成绩
        # ═════════════════════════════════════════════════════════════════
        if not artist_albums_all.empty:
            alb_best_peak = int(artist_albums_all["rank"].min())
            # Best album peak delta: highest Power Score album at that peak
            at_peak_albums = artist_album_power[artist_album_power["peak_position"] == alb_best_peak]
            if not at_peak_albums.empty:
                alb_best_delta = at_peak_albums.iloc[0]["album_name"][:25]
            else:
                alb_best_delta = artist_albums_all.loc[artist_albums_all["rank"].idxmin(), "album_name"][:25]
        else:
            alb_best_peak = None
            alb_best_delta = ""

        st.subheader("专辑成绩")
        cal1, cal2, cal3, cal4 = st.columns(4)
        cal1.metric("#1 专辑数", f"{int(art_row.get('num_no1_albums', 0))} 张")
        cal2.metric("专辑 #1 周数", f"{int(art_row.get('album_no1_weeks', 0))} 周")
        cal3.metric("上榜专辑数", f"{artist_albums_all['album_name'].nunique() if not artist_albums_all.empty else 0} 张")
        cal4.metric(
            "专辑最佳Peak",
            f"#{alb_best_peak}" if alb_best_peak is not None else "—",
            delta=alb_best_delta if alb_best_delta else None,
        )

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
        art_tracks = art_tracks.merge(
            track_summary[["track_id", "weeks_at_no1", "first_peak_week"]],
            on="track_id", how="left"
        )
        art_tracks["weeks_at_no1"] = art_tracks["weeks_at_no1"].fillna(0).astype(int)
        art_tracks["first_peak_week"] = art_tracks["first_peak_week"].astype(str)
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

        # ── Merged: 每周入榜概况 + 艺人周榜历史 ───────────────────────────
        st.divider()
        st.subheader(f"{selected_artist} · 周榜历史")

        artist_weekly = weekly[weekly["artist_name"] == selected_artist]
        # #1 track info per week
        artist_no1_grp = artist_weekly[artist_weekly["rank"] == 1].groupby("billboard_week")
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

        # #1 album info per week
        week_no1_albums = weekly_album[weekly_album["rank"] == 1][
            ["billboard_week", "album_name", "artist_name"]
        ].copy()
        week_no1_albums = week_no1_albums.rename(
            columns={"album_name": "no1_album_name", "artist_name": "no1_album_artist"}
        )

        # Merge artist chart data with #1 track/album info
        artist_wk_history = weekly_artist[weekly_artist["artist_name"] == selected_artist].copy()
        if not artist_wk_history.empty:
            merged = artist_wk_history.merge(artist_no1, on="billboard_week", how="left")
            merged["no1_track_names"] = merged["no1_track_names"].fillna("—")
            merged = merged.merge(week_no1_albums, on="billboard_week", how="left")
            merged = merged.sort_values("billboard_week", ascending=False)

            _m_headers = ["周", "艺人排名", "总播放", "入榜曲数", "入榜专辑数", "#1 曲目", "#1 专辑"]
            _m_rows = []
            for _, _r in merged.iterrows():
                _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜", bb_subtab="2")
                no1_names = str(_r["no1_track_names"])
                if pd.notna(_r.get("no1_count")) and int(_r["no1_count"]) == 1 and pd.notna(_r.get("no1_track_id")):
                    no1_url = _bb_url(bb_nav="track", bb_id=int(_r['no1_track_id']), bb_tab="🎵 单曲历史")
                    _no1_cell = (_html.escape(no1_names), no1_url)
                else:
                    _no1_cell = _html.escape(no1_names)
                # #1 album: show name only if this artist owns it
                _no1_album = "—"
                if pd.notna(_r.get("no1_album_artist")) and str(_r["no1_album_artist"]) == selected_artist:
                    _no1_album = _html.escape(str(_r["no1_album_name"]))
                _m_rows.append([
                    (_html.escape(str(_r["billboard_week"])), _week_url),
                    str(_r["rank"]),
                    f"{_r['play_count']:,}",
                    str(_r["tracks_count"]),
                    str(_r.get("albums_count", 0)),
                    _no1_cell,
                    _no1_album,
                ])
            _render_bb_table(_m_headers, _m_rows,
                col_formats={1: "rank", 2: "num", 3: "num", 4: "num"}, height="500px")
        else:
            st.caption("该艺人在当前过滤条件下无周榜记录")

        # ── Rank trend chart with artist chart rank overlay ────────────
        if not artist_wk_history.empty:
            st.divider()
            st.subheader("艺人周榜排名趋势")

            trend_data = artist_wk_history.sort_values("billboard_week", ascending=True).copy()
            trend_data["billboard_week"] = pd.to_datetime(trend_data["billboard_week"])
            all_weeks = pd.date_range(trend_data["billboard_week"].min(), trend_data["billboard_week"].max(), freq="7D")
            trend_data = pd.DataFrame({"billboard_week": all_weeks}).merge(trend_data, on="billboard_week", how="left")
            peak_row = trend_data.loc[trend_data["rank"].idxmin()]
            fig_art_trend = go.Figure()
            fig_art_trend.add_trace(
                go.Scatter(
                    x=trend_data["billboard_week"],
                    y=trend_data["rank"],
                    mode="lines+markers",
                    name="艺人榜排名",
                    line={"color": "#B8860B", "width": 2},
                    marker={"size": 6, "color": "#B8860B"},
                    connectgaps=False,
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

            # Overlay: best singles chart rank per week
            artist_singles_rank = (
                artist_weekly.groupby("billboard_week")["rank"]
                .min()
                .reset_index()
                .sort_values("billboard_week")
            )
            if not artist_singles_rank.empty:
                artist_singles_rank["billboard_week"] = pd.to_datetime(artist_singles_rank["billboard_week"])
                all_sw = pd.date_range(artist_singles_rank["billboard_week"].min(), artist_singles_rank["billboard_week"].max(), freq="7D")
                artist_singles_rank = pd.DataFrame({"billboard_week": all_sw}).merge(artist_singles_rank, on="billboard_week", how="left")
                fig_art_trend.add_trace(
                    go.Scatter(
                        x=artist_singles_rank["billboard_week"],
                        y=artist_singles_rank["rank"],
                        mode="lines+markers",
                        name="最佳单曲排名",
                        line={"color": "#2E8B57", "width": 1.5, "dash": "dot"},
                        marker={"size": 5, "color": "#2E8B57", "symbol": "triangle-up"},
                        connectgaps=False,
                        hovertemplate="最佳单曲 #%{y}<extra></extra>",
                    )
                )

            fig_art_trend.update_layout(
                yaxis={"autorange": "reversed", "title": "排名", "gridcolor": "rgba(139,115,85,0.08)"},
                xaxis={"title": "", "gridcolor": "rgba(139,115,85,0.08)"},
                height=400,
                hovermode="x unified",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_art_trend, use_container_width=True)

        # ── Album chart performance table ──────────────────────────────
        if not artist_albums_all.empty:
            st.divider()
            st.subheader(f"{selected_artist} · 专辑榜表现")

            artist_album_summary = (
                artist_albums_all.groupby("album_name")
                .agg(
                    peak=("rank", "min"),
                    no1_weeks=("rank", lambda x: (x == 1).sum()),
                    weeks=("billboard_week", "nunique"),
                    first_week=("billboard_week", "min"),
                )
                .reset_index()
                .sort_values(["peak", "no1_weeks", "weeks"], ascending=[True, False, False])
            )
            artist_album_summary.index = artist_album_summary.index + 1

            _aa_headers = ["#", "专辑", "Peak", "#1 周数", "上榜周数", "首次入榜"]
            _aa_rows = []
            for _, _r in artist_album_summary.iterrows():
                album_url = _bb_url(bb_nav="album", bb_name=str(_r["album_name"]), bb_art=selected_artist, bb_tab="💿 专辑榜单")
                _aa_rows.append([
                    str(_r.name),
                    (_html.escape(str(_r["album_name"])), album_url),
                    str(int(_r["peak"])),
                    str(int(_r["no1_weeks"])),
                    str(int(_r["weeks"])),
                    str(_r["first_week"]),
                ])
            _render_bb_table(_aa_headers, _aa_rows,
                col_formats={0: "rank", 2: "num", 3: "num", 4: "num"})

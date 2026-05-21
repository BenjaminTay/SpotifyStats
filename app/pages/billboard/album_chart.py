"""Tab: 专辑榜单 (Album Billboard Summary)."""

import html as _html
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from .shared import _bb_url, _render_bb_table, compute_power_scores, compute_album_power_scores


def render(weekly, weekly_album, track_per_album, album_track_counts, bb_album_top_n, top_n):
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

        # Pre-compute power scores for delta text
        track_power = compute_power_scores(weekly, top_n)
        album_track_ids = set(
            track_per_album[
                (track_per_album["album_name"] == selected_album)
                & (track_per_album["artist_name"] == selected_album_artist)
            ]["track_id"].tolist()
        )
        track_power = track_power.sort_values("power_score", ascending=False).reset_index(drop=True)
        track_power["power_rank"] = track_power.index + 1
        album_track_power = track_power[track_power["track_id"].isin(album_track_ids)]

        # Album power score & rank
        album_power_all = compute_album_power_scores(weekly_album, bb_album_top_n)
        album_power_all = album_power_all.reset_index(drop=True)
        album_power_all.index = album_power_all.index + 1
        ap_row = album_power_all[
            (album_power_all["album_name"] == selected_album)
            & (album_power_all["artist_name"] == selected_album_artist)
        ]
        album_power_score = int(ap_row.iloc[0]["power_score"]) if not ap_row.empty else 0
        album_power_rank = str(int(ap_row.iloc[0].name)) if not ap_row.empty else "—"

        # ── Pre-compute shared data ────────────────────────────────────
        album_chart_data = weekly_album[
            (weekly_album["album_name"] == selected_album)
            & (weekly_album["artist_name"] == selected_album_artist)
        ]

        # Album week history
        album_wk_history = weekly_album[
            (weekly_album["album_name"] == selected_album)
            & (weekly_album["artist_name"] == selected_album_artist)
        ].copy()

        # Charting tracks
        alb_tracks = track_per_album[
            (track_per_album["album_name"] == selected_album)
            & (track_per_album["artist_name"] == selected_album_artist)
        ].copy()

        # Merge power scores into album tracks
        alb_tracks = alb_tracks.merge(
            album_track_power[["track_id", "power_score", "power_rank"]],
            on="track_id", how="left"
        )
        alb_tracks["power_score"] = alb_tracks["power_score"].fillna(0).astype(int)
        alb_tracks["power_rank"] = alb_tracks["power_rank"].fillna(0).astype(int)

        # Singles weekly for this album
        alb_track_ids = set(alb_tracks["track_id"].tolist())
        album_weekly = weekly[weekly["track_id"].isin(alb_track_ids)]

        # ── Sub-tabs ──────────────────────────────────────────────────
        tab1, tab2 = st.tabs(["💿 专辑榜成绩", "🎵 单曲成绩"])

        # ═══════════════════════════════════════════════════════════════
        # Tab 1: 专辑榜成绩
        # ═══════════════════════════════════════════════════════════════
        with tab1:
            if not album_chart_data.empty:
                alb_peak = int(album_chart_data["rank"].min())
                alb_weeks = int(album_chart_data["billboard_week"].nunique())
                alb_first_week = album_chart_data["billboard_week"].min()
                alb_first_peak = album_chart_data.loc[
                    album_chart_data["rank"] == alb_peak, "billboard_week"
                ].min()
                alb_no1 = int((album_chart_data["rank"] == 1).sum())

                st.subheader("专辑榜成绩")
                ca1, ca2, ca3, ca4 = st.columns(4)
                ca1.metric("专辑最高排名", f"#{alb_peak}")
                ca2.metric("进榜周数", f"{alb_weeks} 周")
                ca3.metric("首次入榜", str(alb_first_week))
                ca4.metric("首次Peak周", str(alb_first_peak))

                ca5, ca6, ca7 = st.columns(3)
                ca5.metric("专辑 #1 周数", f"{alb_no1} 周")
                ca6.metric("走势点数", f"{album_power_score:,}")
                ca7.metric("走势排名", f"#{album_power_rank}")
            else:
                st.caption("该专辑暂无专辑榜记录")

            st.divider()

            # ── 周榜历史 ──────────────────────────────────────────────
            st.subheader(f"《{selected_album}》· 周榜历史")

            # Build singles-side summary (#1 track info per week)
            album_no1_grp = album_weekly[album_weekly["rank"] == 1].groupby("billboard_week")
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

            if not album_wk_history.empty:
                merged = album_wk_history.merge(album_no1, on="billboard_week", how="left")
                merged["no1_track_names"] = merged["no1_track_names"].fillna("—")

                # Compute rank changes (ascending order for correct prev_week comparison)
                merged = merged.sort_values("billboard_week", ascending=True)
                merged["prev_rank"] = merged["rank"].shift(1)
                merged["prev_week"] = merged["billboard_week"].shift(1)
                changes = []
                for _, _r in merged.iterrows():
                    p = _r["prev_rank"]
                    pw = _r["prev_week"]
                    cw = _r["billboard_week"]
                    cur = _r["rank"]
                    if pd.isna(p):
                        changes.append("NEW")
                    elif pd.notna(pw) and (cw - pw).days > 8:
                        changes.append("RE")
                    else:
                        diff = int(p) - int(cur)
                        if diff > 0:
                            changes.append(f"▲{diff}")
                        elif diff < 0:
                            changes.append(f"▼{abs(diff)}")
                        else:
                            changes.append("─")
                merged["Change"] = changes
                # Display oldest-first
                merged = merged.sort_values("billboard_week", ascending=True)

                _m_headers = ["周", "专辑排名", "升降", "总播放", "入榜曲数", "#1 曲目"]
                _m_rows = []
                for _, _r in merged.iterrows():
                    _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜", bb_subtab="1")
                    no1_names = str(_r["no1_track_names"])
                    if pd.notna(_r.get("no1_count")) and int(_r["no1_count"]) == 1 and pd.notna(_r.get("no1_track_id")):
                        no1_url = _bb_url(bb_nav="track", bb_id=int(_r['no1_track_id']), bb_tab="🎵 单曲历史")
                        _no1_cell = (_html.escape(no1_names), no1_url)
                    else:
                        _no1_cell = _html.escape(no1_names)
                    _m_rows.append([
                        (_html.escape(str(_r["billboard_week"])), _week_url),
                        str(_r["rank"]),
                        _html.escape(str(_r["Change"])),
                        f"{_r['play_count']:,}",
                        str(_r["tracks_count"]),
                        _no1_cell,
                    ])
                _render_bb_table(_m_headers, _m_rows,
                    col_formats={1: "rank", 3: "num", 4: "num"}, height="500px")
            else:
                st.caption("该专辑在当前过滤条件下无周榜记录")

            # ── Rank trend chart ───────────────────────────────────────
            if not album_wk_history.empty:
                st.divider()
                st.subheader("专辑周榜排名趋势")

                trend_data2 = album_wk_history.sort_values("billboard_week", ascending=True).copy()
                trend_data2["billboard_week"] = pd.to_datetime(trend_data2["billboard_week"])
                all_weeks2 = pd.date_range(trend_data2["billboard_week"].min(), trend_data2["billboard_week"].max(), freq="7D")
                trend_data2 = pd.DataFrame({"billboard_week": all_weeks2}).merge(trend_data2, on="billboard_week", how="left")
                peak_row2 = trend_data2.loc[trend_data2["rank"].idxmin()]
                fig_alb_trend = go.Figure()
                fig_alb_trend.add_trace(
                    go.Scatter(
                        x=trend_data2["billboard_week"],
                        y=trend_data2["rank"],
                        mode="lines+markers",
                        name="专辑排名",
                        line={"color": "#B8860B", "width": 2},
                        marker={"size": 6, "color": "#B8860B"},
                        connectgaps=False,
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

                # Overlay: best singles chart rank per week for this album
                album_singles_rank = (
                    album_weekly.groupby("billboard_week")["rank"]
                    .min()
                    .reset_index()
                    .sort_values("billboard_week")
                )
                if not album_singles_rank.empty:
                    album_singles_rank["billboard_week"] = pd.to_datetime(album_singles_rank["billboard_week"])
                    all_aw = pd.date_range(album_singles_rank["billboard_week"].min(), album_singles_rank["billboard_week"].max(), freq="7D")
                    album_singles_rank = pd.DataFrame({"billboard_week": all_aw}).merge(album_singles_rank, on="billboard_week", how="left")
                    fig_alb_trend.add_trace(
                        go.Scatter(
                            x=album_singles_rank["billboard_week"],
                            y=album_singles_rank["rank"],
                            mode="lines+markers",
                            name="最佳单曲排名",
                            line={"color": "#2E8B57", "width": 1.5, "dash": "dot"},
                            marker={"size": 5, "color": "#2E8B57", "symbol": "triangle-up"},
                            connectgaps=False,
                            hovertemplate="最佳单曲 #%{y}<extra></extra>",
                        )
                    )

                fig_alb_trend.update_layout(
                    yaxis={"autorange": "reversed", "title": "排名", "gridcolor": "rgba(139,115,85,0.08)"},
                    xaxis={"title": "", "gridcolor": "rgba(139,115,85,0.08)"},
                    height=400,
                    hovermode="x unified",
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_alb_trend, use_container_width=True)

        # ═══════════════════════════════════════════════════════════════
        # Tab 2: 单曲成绩
        # ═══════════════════════════════════════════════════════════════
        with tab2:
            # Best peak delta: highest Power Score track at that peak
            best_peak_val = int(selected_album_row["best_peak"])
            at_peak_tracks = album_track_power[album_track_power["peak_position"] == best_peak_val]
            if not at_peak_tracks.empty:
                best_peak_delta = at_peak_tracks.iloc[0]["track_name"][:30]
            else:
                best_peak_delta = selected_album_row["best_peak_track"][:30]

            # Total power score for all tracks in this album
            total_track_power = int(album_track_power["power_score"].sum())

            st.subheader("单曲成绩")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("入榜曲数", f"{int(selected_album_row['total_tracks'])} 首")
            col2.metric(
                "最佳单曲Peak",
                f"#{best_peak_val}",
                delta=best_peak_delta,
            )
            col3.metric("总上榜周数", f"{int(selected_album_row['total_weeks'])} 周")
            col4.metric("平均在榜", f"{selected_album_row['avg_weeks']:.1f} 周")

            col1b, col2b, col3b, col4b = st.columns(4)
            col1b.metric("#1 曲数", f"{int(selected_album_row['top1'])} 首")
            col2b.metric("Top 5 曲数", f"{int(selected_album_row['top5'])} 首")
            col3b.metric("Top 10 曲数", f"{int(selected_album_row['top10'])} 首")
            col4b.metric("单曲 #1 周数", f"{int(selected_album_row['weeks_at_no1'])} 周")

            col1c, col2c, col3c, col4c = st.columns(4)
            col1c.metric("单曲走势总点数", f"{total_track_power:,}")

            st.divider()

            # ── Secondary sort selector ───────────────────────────────────
            album_tiebreaker = st.radio(
                "Peak 相同时按",
                ["在榜周数", "Peak 周数"],
                horizontal=True,
                key="album_tiebreaker",
            )

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

            st.subheader(f"《{selected_album}》· 入榜曲目")

            _alb_t_headers = ["#", "曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "首次Peak周", "最近上榜", "总播放", "走势点数", "走势排名"]
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
                    f"{_r['power_score']:,}",
                    str(int(_r["power_rank"])) if _r["power_rank"] > 0 else "—",
                ])
            _render_bb_table(_alb_t_headers, _alb_t_rows,
                col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 8: "num", 9: "num", 10: "num"})

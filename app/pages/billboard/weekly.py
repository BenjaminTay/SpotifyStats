"""Tab: 周榜 (Weekly Chart) — 3 sub-tabs: 单曲榜/专辑榜/艺人榜."""

import html as _html
from datetime import date
import streamlit as st
import pandas as pd

from .shared import _bb_url, _render_bb_table


def render(weekly, weekly_album, weekly_artist, track_summary,
           all_weeks_desc, all_weeks_asc, all_weeks_str,
           top_n, bb_album_top_n, bb_artist_top_n):
    # ── Consume cross-tab week navigation ─────────────────────────────
    nav_week = st.session_state.get("bb_selected_week")
    if nav_week is not None:
        st.session_state.bb_selected_week = None
        try:
            target_week = date.fromisoformat(nav_week)
            if target_week in all_weeks_desc:
                st.session_state.bb_week_selector = all_weeks_desc.index(target_week)
        except (ValueError, TypeError):
            pass

    # Week selector with prev/next buttons
    if "bb_week_selector" not in st.session_state:
        st.session_state.bb_week_selector = 0
    max_week_idx = len(all_weeks_desc) - 1
    if st.session_state.bb_week_selector > max_week_idx:
        st.session_state.bb_week_selector = max_week_idx
    cur_idx = st.session_state.bb_week_selector
    c1, c2, c3 = st.columns([1, 8, 1])
    with c1:
        if st.button("◀ 上一周", use_container_width=True, disabled=cur_idx >= max_week_idx):
            st.session_state.bb_week_selector = min(cur_idx + 1, max_week_idx)
            st.rerun()
    with c3:
        if st.button("下一周 ▶", use_container_width=True, disabled=cur_idx <= 0):
            st.session_state.bb_week_selector = max(cur_idx - 1, 0)
            st.rerun()
    with c2:
        selected_week_idx = st.selectbox(
            "选择周",
            options=range(len(all_weeks_desc)),
            format_func=lambda i: all_weeks_str[i],
            key="bb_week_selector",
            label_visibility="collapsed",
        )
    selected_week = all_weeks_desc[selected_week_idx]

    # Clamp sub-tab index
    subtab_idx = max(0, min(st.session_state.bb_weekly_subtab, 2))
    st.session_state.bb_weekly_subtab = subtab_idx

    WEEKLY_SUBTABS = ["🎵 单曲榜", "💿 专辑榜", "🎤 艺人榜"]
    wtabs = st.tabs(WEEKLY_SUBTABS)

    # ═════════════════════════════════════════════════════════════════════
    # Sub-tab 0: Track Weekly Chart (单曲榜)
    # ═════════════════════════════════════════════════════════════════════
    with wtabs[0]:
        week_df = weekly[weekly["billboard_week"] == selected_week].copy()
        week_df = week_df.sort_values("rank")

        if week_df.empty:
            st.warning(f"本周无数据（{selected_week}）")
        else:
            n_tracks = len(week_df)
            st.subheader(f"{selected_week} 单曲榜 · Top {n_tracks}")

            total_week_plays = int(week_df["play_count"].sum())
            st.metric("本周入榜歌曲总播放次数", f"{total_week_plays:,}")

            # ── Top 10 Highlight Cards ────────────────────────────────────
            top10 = week_df.head(10)
            medals = {0: "🥇", 1: "🥈", 2: "🥉"}
            card_rows = [st.columns(5), st.columns(5)]
            for i, (_, row) in enumerate(top10.iterrows()):
                r = i // 5
                c = i % 5
                medal = medals.get(i, "")
                track_short = row["track_name"][:25] if len(row["track_name"]) > 25 else row["track_name"]
                artist_short = row["artist_name"][:20] if len(row["artist_name"]) > 20 else row["artist_name"]
                with card_rows[r][c]:
                    st.metric(
                        f"{medal} #{row['rank']} {track_short}",
                        f"{row['play_count']} 次",
                        delta=artist_short,
                    )

            st.divider()

            # ── LW rank computation ───────────────────────────────────────
            sw_idx = all_weeks_asc.index(selected_week)
            prev_week = all_weeks_asc[sw_idx - 1] if sw_idx > 0 else None

            if prev_week is not None:
                prev_ranks = weekly[weekly["billboard_week"] == prev_week][
                    ["track_id", "rank"]
                ].set_index("track_id")["rank"]

                earlier_weeks = set(all_weeks_asc[:sw_idx])
                earlier_tracks = set(
                    weekly[weekly["billboard_week"].isin(earlier_weeks)]["track_id"].unique()
                )
            else:
                prev_ranks = pd.Series(dtype=int)
                earlier_tracks = set()

            # Build LW display
            lw_values = []
            for _, row in week_df.iterrows():
                tid = row["track_id"]
                if prev_week is None:
                    lw_values.append("NEW")
                elif tid in prev_ranks.index:
                    prev_r = prev_ranks[tid]
                    change = prev_r - row["rank"]
                    if change > 0:
                        lw_values.append(f"▲{change}")
                    elif change < 0:
                        lw_values.append(f"▼{abs(change)}")
                    else:
                        lw_values.append("─")
                elif tid in earlier_tracks:
                    lw_values.append("RE")
                else:
                    lw_values.append("NEW")

            week_df["LW"] = lw_values

            # ── Compute running Peak / Wks / Pk Wks as of selected_week ──
            running_w = weekly[weekly["billboard_week"] <= selected_week]
            cur_ids = week_df["track_id"].unique()
            track_running = (
                running_w[running_w["track_id"].isin(cur_ids)]
                .groupby("track_id")
                .agg(
                    running_peak=("rank", "min"),
                    running_wks=("billboard_week", "nunique"),
                )
                .reset_index()
            )
            # running_peak_wks: weeks at the running peak (not all-time peak)
            rwp = running_w[running_w["track_id"].isin(cur_ids)].merge(
                track_running[["track_id", "running_peak"]], on="track_id"
            )
            rwp["at_peak"] = (rwp["rank"] == rwp["running_peak"]).astype(int)
            rpk = rwp.groupby("track_id")["at_peak"].sum().reset_index()
            rpk.columns = ["track_id", "running_pk_wks"]
            track_running = track_running.merge(rpk, on="track_id")
            week_df = week_df.merge(track_running, on="track_id", how="left")

            # ── Hot 100 Table ─────────────────────────────────────────────
            headers = ["#", "曲目", "艺人", "播放次数", "LW", "Peak", "Wks", "Pk Wks"]
            rows = []
            for _, r in week_df.iterrows():
                track_url = _bb_url(bb_nav="track", bb_id=r['track_id'], bb_tab="🎵 单曲历史")
                artist_url = _bb_url(bb_nav="artist", bb_name=str(r['artist_name']), bb_tab="🎤 艺人榜单")
                rows.append([
                    str(r["rank"]),
                    (_html.escape(str(r["track_name"])), track_url),
                    (_html.escape(str(r["artist_name"])), artist_url),
                    f"{r['play_count']:,}",
                    str(r.get("LW", "-")),
                    str(int(r["running_peak"])),
                    str(int(r["running_wks"])),
                    str(int(r["running_pk_wks"])),
                ])
            _render_bb_table(headers, rows,
                col_formats={0: "rank", 3: "num", 4: "num", 5: "num", 6: "num", 7: "num"})

            if n_tracks < top_n:
                st.caption(f"本周仅 {n_tracks} 首曲目上榜（不足 Top {top_n}）")

    # ═════════════════════════════════════════════════════════════════════
    # Sub-tab 1: Album Weekly Chart (专辑榜)
    # ═════════════════════════════════════════════════════════════════════
    with wtabs[1]:
        album_week_df = weekly_album[weekly_album["billboard_week"] == selected_week].copy()
        album_week_df = album_week_df.sort_values("rank")

        if album_week_df.empty:
            st.warning(f"本周无专辑数据（{selected_week}）")
        else:
            n_albums = len(album_week_df)
            st.subheader(f"{selected_week} 专辑周榜 · Top {n_albums}")

            total_album_plays = int(album_week_df["play_count"].sum())
            st.metric("上榜专辑总播放次数", f"{total_album_plays:,}")

            # ── Top 3 KPI highlight cards ────────────────────────────────
            top3 = album_week_df.head(3)
            medals = {0: "🥇", 1: "🥈", 2: "🥉"}
            kpi_cols = st.columns(3)
            for i, (_, row) in enumerate(top3.iterrows()):
                medal = medals.get(i, "")
                album_short = str(row["album_name"])[:30] if len(str(row["album_name"])) > 30 else str(row["album_name"])
                artist_short = str(row["artist_name"])[:20]
                with kpi_cols[i]:
                    st.metric(
                        f"{medal} #{row['rank']} {album_short}",
                        f"{row['play_count']} 次",
                        delta=artist_short,
                    )

            st.divider()

            # ── LW rank computation ───────────────────────────────────────
            sw_idx = all_weeks_asc.index(selected_week)
            prev_week = all_weeks_asc[sw_idx - 1] if sw_idx > 0 else None

            # Composite key for album matching: album_name|||artist_name
            album_week_df["_key"] = album_week_df["album_name"].astype(str) + "|||" + album_week_df["artist_name"].fillna("").astype(str)

            if prev_week is not None:
                prev_alb = weekly_album[weekly_album["billboard_week"] == prev_week].copy()
                prev_alb["_key"] = prev_alb["album_name"].astype(str) + "|||" + prev_alb["artist_name"].fillna("").astype(str)
                prev_album_ranks = dict(zip(prev_alb["_key"], prev_alb["rank"]))
                earlier_album_weeks = set(all_weeks_asc[:sw_idx])
                earlier_albums = set(
                    weekly_album[weekly_album["billboard_week"].isin(earlier_album_weeks)]
                    .apply(lambda r: str(r["album_name"]) + "|||" + str(r.get("artist_name", "") or ""), axis=1)
                    .unique()
                )
            else:
                prev_album_ranks = {}
                earlier_albums = set()

            lw_album_values = []
            for _, row in album_week_df.iterrows():
                key = row["_key"]
                if prev_week is None:
                    lw_album_values.append("NEW")
                elif key in prev_album_ranks:
                    prev_r = prev_album_ranks[key]
                    change = prev_r - row["rank"]
                    if change > 0:
                        lw_album_values.append(f"▲{change}")
                    elif change < 0:
                        lw_album_values.append(f"▼{abs(change)}")
                    else:
                        lw_album_values.append("─")
                elif key in earlier_albums:
                    lw_album_values.append("RE")
                else:
                    lw_album_values.append("NEW")
            album_week_df["LW"] = lw_album_values

            # ── Compute running Peak/Wks for albums as of selected_week ──
            running_alb = weekly_album[weekly_album["billboard_week"] <= selected_week]
            album_running = (
                running_alb.groupby(["album_name", "artist_name"])
                .agg(
                    running_peak=("rank", "min"),
                    running_wks=("billboard_week", "nunique"),
                )
                .reset_index()
            )
            album_week_df = album_week_df.merge(
                album_running, on=["album_name", "artist_name"], how="left"
            )

            # running_peak_wks: weeks at the running peak
            rwp_alb = running_alb.merge(
                album_running[["album_name", "artist_name", "running_peak"]],
                on=["album_name", "artist_name"]
            )
            rwp_alb["at_peak"] = (rwp_alb["rank"] == rwp_alb["running_peak"]).astype(int)
            rpk_alb = rwp_alb.groupby(["album_name", "artist_name"])["at_peak"].sum().reset_index()
            rpk_alb.columns = ["album_name", "artist_name", "running_pk_wks"]
            album_week_df = album_week_df.merge(rpk_alb, on=["album_name", "artist_name"], how="left")

            # ── Table ─────────────────────────────────────────────────────
            headers = ["#", "专辑", "艺人", "总播放次数", "LW", "Peak", "Wks", "Pk Wks"]
            rows = []
            for _, r in album_week_df.iterrows():
                album_url = _bb_url(bb_nav="album", bb_name=str(r["album_name"]),
                                    bb_art=str(r.get("artist_name", "")), bb_tab="💿 专辑榜单")
                artist_url = _bb_url(bb_nav="artist", bb_name=str(r["artist_name"]), bb_tab="🎤 艺人榜单")
                rows.append([
                    str(r["rank"]),
                    (_html.escape(str(r["album_name"])), album_url),
                    (_html.escape(str(r["artist_name"])), artist_url),
                    f"{r['play_count']:,}",
                    str(r.get("LW", "-")),
                    str(int(r.get("running_peak", 0)) or "-"),
                    str(int(r.get("running_wks", 0)) or "-"),
                    str(int(r.get("running_pk_wks", 0)) or "-"),
                ])
            _render_bb_table(headers, rows,
                col_formats={0: "rank", 3: "num", 4: "num", 5: "num", 6: "num", 7: "num"})

            if n_albums < bb_album_top_n:
                st.caption(f"本周仅 {n_albums} 张专辑上榜（不足 Top {bb_album_top_n}）")

    # ═════════════════════════════════════════════════════════════════════
    # Sub-tab 2: Artist Weekly Chart (艺人榜)
    # ═════════════════════════════════════════════════════════════════════
    with wtabs[2]:
        artist_week_df = weekly_artist[weekly_artist["billboard_week"] == selected_week].copy()
        artist_week_df = artist_week_df.sort_values("rank")

        if artist_week_df.empty:
            st.warning(f"本周无艺人数据（{selected_week}）")
        else:
            n_artists = len(artist_week_df)
            st.subheader(f"{selected_week} 艺人周榜 · Top {n_artists}")

            total_artist_plays = int(artist_week_df["play_count"].sum())
            st.metric("上榜艺人总播放次数", f"{total_artist_plays:,}")

            # ── Top 3 KPI highlight cards ────────────────────────────────
            top3 = artist_week_df.head(3)
            medals = {0: "🥇", 1: "🥈", 2: "🥉"}
            kpi_cols = st.columns(3)
            for i, (_, row) in enumerate(top3.iterrows()):
                medal = medals.get(i, "")
                artist_short = str(row["artist_name"])[:25]
                with kpi_cols[i]:
                    st.metric(
                        f"{medal} #{row['rank']} {artist_short}",
                        f"{row['play_count']} 次",
                        delta=f"{row['tracks_count']} 首曲目",
                    )

            st.divider()

            # ── LW rank computation ───────────────────────────────────────
            sw_idx = all_weeks_asc.index(selected_week)
            prev_week = all_weeks_asc[sw_idx - 1] if sw_idx > 0 else None

            if prev_week is not None:
                prev_art = weekly_artist[weekly_artist["billboard_week"] == prev_week]
                prev_artist_ranks = dict(zip(prev_art["artist_name"], prev_art["rank"]))
                earlier_artist_weeks = set(all_weeks_asc[:sw_idx])
                earlier_artists = set(
                    weekly_artist[weekly_artist["billboard_week"].isin(earlier_artist_weeks)]["artist_name"].unique()
                )
            else:
                prev_artist_ranks = {}
                earlier_artists = set()

            lw_artist_values = []
            for _, row in artist_week_df.iterrows():
                aname = row["artist_name"]
                if prev_week is None:
                    lw_artist_values.append("NEW")
                elif aname in prev_artist_ranks:
                    prev_r = prev_artist_ranks[aname]
                    change = prev_r - row["rank"]
                    if change > 0:
                        lw_artist_values.append(f"▲{change}")
                    elif change < 0:
                        lw_artist_values.append(f"▼{abs(change)}")
                    else:
                        lw_artist_values.append("─")
                elif aname in earlier_artists:
                    lw_artist_values.append("RE")
                else:
                    lw_artist_values.append("NEW")
            artist_week_df["LW"] = lw_artist_values

            # ── Compute running Peak/Wks for artists as of selected_week ──
            running_art = weekly_artist[weekly_artist["billboard_week"] <= selected_week]
            artist_running = (
                running_art.groupby("artist_name")
                .agg(
                    running_peak=("rank", "min"),
                    running_wks=("billboard_week", "nunique"),
                )
                .reset_index()
            )
            artist_week_df = artist_week_df.merge(
                artist_running, on="artist_name", how="left"
            )

            # running_peak_wks: weeks at the running peak
            rwp_art = running_art.merge(
                artist_running[["artist_name", "running_peak"]],
                on="artist_name"
            )
            rwp_art["at_peak"] = (rwp_art["rank"] == rwp_art["running_peak"]).astype(int)
            rpk_art = rwp_art.groupby("artist_name")["at_peak"].sum().reset_index()
            rpk_art.columns = ["artist_name", "running_pk_wks"]
            artist_week_df = artist_week_df.merge(rpk_art, on="artist_name", how="left")

            # ── Table ─────────────────────────────────────────────────────
            headers = ["#", "艺人", "总播放次数", "LW", "Peak", "Wks", "Pk Wks"]
            rows = []
            for _, r in artist_week_df.iterrows():
                artist_url = _bb_url(bb_nav="artist", bb_name=str(r["artist_name"]), bb_tab="🎤 艺人榜单")
                rows.append([
                    str(r["rank"]),
                    (_html.escape(str(r["artist_name"])), artist_url),
                    f"{r['play_count']:,}",
                    str(r.get("LW", "-")),
                    str(int(r.get("running_peak", 0)) or "-"),
                    str(int(r.get("running_wks", 0)) or "-"),
                    str(int(r.get("running_pk_wks", 0)) or "-"),
                ])
            _render_bb_table(headers, rows,
                col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 5: "num", 6: "num"})

            if n_artists < bb_artist_top_n:
                st.caption(f"本周仅 {n_artists} 位艺人上榜（不足 Top {bb_artist_top_n}）")

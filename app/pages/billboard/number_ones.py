"""Tab: 每周榜首 (Number Ones History) — 3 sub-tabs: 单曲榜/专辑榜/艺人榜."""

import html as _html
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from .shared import _bb_url, _render_bb_table


def _longest_streak(hist, week_col="billboard_week"):
    weeks = sorted(hist[week_col].unique())
    if len(weeks) < 2:
        return len(weeks)
    max_s = 1
    cur_s = 1
    for i in range(1, len(weeks)):
        if (weeks[i] - weeks[i - 1]).days == 7:
            cur_s += 1
            max_s = max(max_s, cur_s)
        else:
            cur_s = 1
    return max_s


def render(weekly, weekly_album, weekly_artist, track_summary):
    # Extract #1 songs, newest first
    number_ones = weekly[weekly["rank"] == 1].copy()
    number_ones = number_ones.sort_values("billboard_week", ascending=False)

    # Count total #1 weeks per track
    weeks_at_one = (
        number_ones.groupby(["track_id", "track_name", "artist_name"])
        .agg(
            weeks_at_no1=("billboard_week", "nunique"),
            total_no1_plays=("play_count", "sum"),
        )
        .reset_index()
        .sort_values("weeks_at_no1", ascending=False)
    )

    longest_streak = 0
    longest_streak_track = ""
    longest_streak_artist = ""
    for _, row in weeks_at_one.iterrows():
        hist = number_ones[number_ones["track_id"] == row["track_id"]]
        s = _longest_streak(hist)
        if s > longest_streak:
            longest_streak = s
            longest_streak_track = row["track_name"]
            longest_streak_artist = row["artist_name"]

    # ── Pre-compute album #1 data ───────────────────────────────────────
    number_one_albums = weekly_album[weekly_album["rank"] == 1].copy()
    number_one_albums = number_one_albums.sort_values(["album_name", "artist_name", "billboard_week"])
    number_one_albums["album_pk_wks"] = number_one_albums.groupby(["album_name", "artist_name"]).cumcount() + 1

    album_weeks_at_one = (
        weekly_album[weekly_album["rank"] == 1]
        .groupby(["album_name", "artist_name"])
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
        .sort_values("weeks_at_no1", ascending=False)
    )

    # Album longest #1 streak
    album_longest_streak = 0
    album_longest_streak_name = ""
    album_longest_streak_artist = ""
    for _, row in album_weeks_at_one.iterrows():
        hist = number_one_albums[
            (number_one_albums["album_name"] == row["album_name"])
            & (number_one_albums["artist_name"] == row["artist_name"])
        ]
        s = _longest_streak(hist)
        if s > album_longest_streak:
            album_longest_streak = s
            album_longest_streak_name = row["album_name"]
            album_longest_streak_artist = row["artist_name"]

    # ── Pre-compute artist #1 data ──────────────────────────────────────
    number_one_artists = weekly_artist[weekly_artist["rank"] == 1].copy()
    number_one_artists = number_one_artists.sort_values(["artist_name", "billboard_week"])
    number_one_artists["artist_pk_wks"] = number_one_artists.groupby("artist_name").cumcount() + 1

    artist_weeks_at_one = (
        weekly_artist[weekly_artist["rank"] == 1]
        .groupby("artist_name")
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
        .sort_values("weeks_at_no1", ascending=False)
    )

    # Artist longest #1 streak
    artist_longest_streak = 0
    artist_longest_streak_name = ""
    for _, row in artist_weeks_at_one.iterrows():
        hist = number_one_artists[number_one_artists["artist_name"] == row["artist_name"]]
        s = _longest_streak(hist)
        if s > artist_longest_streak:
            artist_longest_streak = s
            artist_longest_streak_name = row["artist_name"]

    # ── Pre-compute debut data (for 单曲榜 and 专辑榜) ──────────────────
    first_appear = (
        weekly.sort_values("billboard_week")
        .groupby("track_id")
        .first()
        .reset_index()
    )
    debut_no1 = first_appear[first_appear["rank"] == 1][
        ["track_id", "track_name", "artist_name", "billboard_week"]
    ].copy()
    debut_no1 = debut_no1.merge(
        track_summary[["track_id", "weeks_on_chart", "weeks_at_no1"]],
        on="track_id",
        how="left",
    )
    debut_no1 = debut_no1.sort_values("billboard_week", ascending=False)
    debut_no1["billboard_week"] = debut_no1["billboard_week"].astype(str)

    album_first_appear = (
        weekly_album.sort_values("billboard_week")
        .groupby(["album_name", "artist_name"])
        .first()
        .reset_index()
    )
    album_debut_no1 = album_first_appear[album_first_appear["rank"] == 1][
        ["album_name", "artist_name", "billboard_week"]
    ].copy()
    album_chart_info = (
        weekly_album.groupby(["album_name", "artist_name"])
        .agg(weeks_on_chart=("billboard_week", "nunique"), weeks_at_no1=("rank", lambda x: (x == 1).sum()))
        .reset_index()
    )
    album_debut_no1 = album_debut_no1.merge(album_chart_info, on=["album_name", "artist_name"], how="left")
    album_debut_no1 = album_debut_no1.sort_values("billboard_week", ascending=False)
    album_debut_no1["billboard_week"] = album_debut_no1["billboard_week"].astype(str)

    # ═════════════════════════════════════════════════════════════════════
    # Three sub-tabs
    # ═════════════════════════════════════════════════════════════════════
    no1_tabs = st.tabs(["单曲榜", "专辑榜", "艺人榜"])

    # ─────────────────────────────────────────────────────────────────────
    # Sub-tab 0: 单曲榜
    # ─────────────────────────────────────────────────────────────────────
    with no1_tabs[0]:
        # ── Summary Cards ────────────────────────────────────────────────
        col1, col2, col3 = st.columns(3)
        col1.metric("总冠单曲目数", f"{len(weeks_at_one)} 首")
        col2.metric(
            "最多冠单周数",
            f"{int(weeks_at_one.iloc[0]['weeks_at_no1'])} 周",
            delta=weeks_at_one.iloc[0]["track_name"][:30],
        )
        col3.metric(
            "最长连冠纪录",
            f"{longest_streak} 周",
            delta=f"{longest_streak_track[:20]} — {longest_streak_artist[:20]}" if longest_streak > 0 else None,
        )

        st.divider()

        # ── Weekly #1 Table ──────────────────────────────────────────────
        st.subheader("每周冠单")

        _no1_headers = ["周", "冠单曲目", "艺人", "播放次数", "Pk Wks"]
        _no1_rows = []
        for _, _r in number_ones.iterrows():
            _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
            _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜")
            _no1_rows.append([
                (_html.escape(str(_r["billboard_week"])), _week_url),
                (_html.escape(str(_r["track_name"])), _track_url),
                (_html.escape(str(_r["artist_name"])), _artist_url),
                f"{_r['play_count']:,}",
                str(_r["running_peak_wks"]),
            ])
        _render_bb_table(_no1_headers, _no1_rows,
            col_formats={3: "num", 4: "num"}, height="600px")

        st.divider()
        st.subheader("冠单周数排行")

        ws_data = weeks_at_one.head(20).merge(
            track_summary[["track_id", "weeks_at_peak", "first_peak_week"]],
            on="track_id", how="left"
        )
        ws_data["first_peak_week"] = ws_data["first_peak_week"].astype(str)
        ws_data = ws_data.reset_index(drop=True)
        ws_data.index = ws_data.index + 1

        _ws_headers = ["#", "曲目", "艺人", "Pk Wks", "首次Peak周", "总播放"]
        _ws_rows = []
        for _i, _r in ws_data.iterrows():
            _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
            _ws_rows.append([
                str(_r.name),
                (_html.escape(str(_r["track_name"])), _track_url),
                (_html.escape(str(_r["artist_name"])), _artist_url),
                str(_r["weeks_at_peak"]),
                (_html.escape(str(_r["first_peak_week"])), _bb_url(bb_nav="week", bb_date=_r['first_peak_week'], bb_tab="📋 周榜")),
                f"{_r['total_no1_plays']:,}",
            ])
        _render_bb_table(_ws_headers, _ws_rows,
            col_formats={0: "rank", 3: "num", 5: "num"}, height="600px")

        # ── Chart ────────────────────────────────────────────────────────
        st.divider()
        st.subheader("单曲冠军周数 Top 15")

        chart_data = weeks_at_one.head(15).sort_values("weeks_at_no1", ascending=True)

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=chart_data["weeks_at_no1"],
                y=chart_data["track_name"],
                orientation="h",
                marker=dict(
                    color=chart_data["weeks_at_no1"],
                    colorscale="YlOrRd",
                    showscale=True,
                    colorbar=dict(title="冠单周数"),
                ),
                text=chart_data["weeks_at_no1"].apply(lambda x: f"{x} 周"),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>%{customdata}<br>冠单周数: %{x} 周<extra></extra>",
                customdata=chart_data["artist_name"],
            )
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

        # ── Annual unique #1 songs ───────────────────────────────────────
        st.divider()
        st.subheader("每年独特冠单统计")

        number_ones["year"] = pd.to_datetime(number_ones["billboard_week"]).dt.year
        annual_no1 = (
            number_ones.groupby("year")
            .agg(
                unique_no1=("track_id", "nunique"),
                songs=("track_name", lambda x: "、".join(dict.fromkeys(x))),
            )
            .reset_index()
            .sort_values("year", ascending=False)
        )

        display_annual = annual_no1.copy()
        display_annual.columns = ["年份", "独特冠单数", "冠单曲目"]
        display_annual = display_annual.set_index("年份")

        st.dataframe(
            display_annual,
            column_config={
                "独特冠单数": st.column_config.NumberColumn("独特冠单数", format="%d"),
                "冠单曲目": st.column_config.TextColumn("冠单曲目", width="large"),
            },
            use_container_width=True,
        )

        # ── Debut at #1 (空冠歌曲) ────────────────────────────────────────
        st.divider()
        st.subheader("空冠歌曲（首次上榜即 #1）")

        if debut_no1.empty:
            st.info("暂无空冠歌曲")
        else:
            st.metric("空冠歌曲数", f"{len(debut_no1)} 首")
            _db_headers = ["曲目", "艺人", "首次上榜周", "在榜周数", "冠单周数"]
            _db_rows = []
            for _, _r in debut_no1.iterrows():
                _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
                _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
                _week_url = _bb_url(bb_nav="week", bb_date=str(_r['billboard_week']), bb_tab="📋 周榜")
                _db_rows.append([
                    (_html.escape(str(_r["track_name"])), _track_url),
                    (_html.escape(str(_r["artist_name"])), _artist_url),
                    (_html.escape(str(_r["billboard_week"])), _week_url),
                    str(_r["weeks_on_chart"]),
                    str(_r["weeks_at_no1"]),
                ])
            _render_bb_table(_db_headers, _db_rows,
                col_formats={3: "num", 4: "num"})

    # ─────────────────────────────────────────────────────────────────────
    # Sub-tab 1: 专辑榜
    # ─────────────────────────────────────────────────────────────────────
    with no1_tabs[1]:
        # ── Summary Cards ────────────────────────────────────────────────
        total_no1_albums = album_weeks_at_one["album_name"].nunique()
        if not album_weeks_at_one.empty:
            col_a1, col_a2, col_a3 = st.columns(3)
            col_a1.metric("总冠军专辑数", f"{total_no1_albums} 张")
            col_a2.metric(
                "最多冠军周数",
                f"{int(album_weeks_at_one.iloc[0]['weeks_at_no1'])} 周",
                delta=album_weeks_at_one.iloc[0]["album_name"][:30],
            )
            col_a3.metric(
                "最长连冠纪录",
                f"{album_longest_streak} 周",
                delta=f"{album_longest_streak_name[:20]} — {album_longest_streak_artist[:20]}" if album_longest_streak > 0 else None,
            )
        else:
            st.metric("总冠军专辑数", "0 张")

        st.divider()

        # ── Weekly #1 Album Table ────────────────────────────────────────
        st.subheader("每周冠军专辑")

        _no1_album_headers = ["周", "冠军专辑", "艺人", "总播放次数", "入榜曲数", "Pk Wks"]
        _no1_album_rows = []
        for _, _r in number_one_albums.sort_values("billboard_week", ascending=False).iterrows():
            _album_url = _bb_url(bb_nav="album", bb_name=str(_r['album_name']), bb_art=str(_r['artist_name']), bb_tab="💿 专辑榜单")
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
            _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜")
            _no1_album_rows.append([
                (_html.escape(str(_r["billboard_week"])), _week_url),
                (_html.escape(str(_r["album_name"])), _album_url),
                (_html.escape(str(_r["artist_name"])), _artist_url),
                f"{_r['play_count']:,}",
                str(_r["tracks_count"]),
                str(_r["album_pk_wks"]),
            ])
        _render_bb_table(_no1_album_headers, _no1_album_rows,
            col_formats={3: "num", 4: "num", 5: "num"}, height="600px")

        # ── Album #1 Weeks Ranking Table ────────────────────────────────
        st.divider()
        st.subheader("冠军周数排行")

        album_weeks_rank = album_weeks_at_one.head(20).reset_index(drop=True)
        album_weeks_rank.index = album_weeks_rank.index + 1

        _aw_headers = ["#", "专辑", "艺人", "冠军周数"]
        _aw_rows = []
        for _i, _r in album_weeks_rank.iterrows():
            _album_url = _bb_url(bb_nav="album", bb_name=str(_r['album_name']), bb_art=str(_r['artist_name']), bb_tab="💿 专辑榜单")
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
            _aw_rows.append([
                str(_r.name),
                (_html.escape(str(_r["album_name"])), _album_url),
                (_html.escape(str(_r["artist_name"])), _artist_url),
                str(_r["weeks_at_no1"]),
            ])
        _render_bb_table(_aw_headers, _aw_rows,
            col_formats={0: "rank", 3: "num"}, height="600px")

        # ── Album #1 Weeks Chart ────────────────────────────────────────
        st.divider()
        st.subheader("专辑冠军周数 Top 15")

        if not album_weeks_at_one.empty:
            album_no1_chart = album_weeks_at_one.head(15).sort_values("weeks_at_no1", ascending=True)
            fig_album_no1 = go.Figure()
            fig_album_no1.add_trace(
                go.Bar(
                    x=album_no1_chart["weeks_at_no1"],
                    y=album_no1_chart["album_name"],
                    orientation="h",
                    marker=dict(
                        color=album_no1_chart["weeks_at_no1"],
                        colorscale="YlOrRd",
                        showscale=True,
                        colorbar=dict(title="冠军周数"),
                    ),
                    text=album_no1_chart["weeks_at_no1"].apply(lambda x: f"{x} 周"),
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>%{customdata}<br>冠军周数: %{x} 周<extra></extra>",
                    customdata=album_no1_chart["artist_name"],
                )
            )
            fig_album_no1.update_layout(height=500)
            st.plotly_chart(fig_album_no1, use_container_width=True)
        else:
            st.info("暂无专辑冠军数据")

        # ── Debut at #1 Albums (空冠专辑) ────────────────────────────────
        st.divider()
        st.subheader("空冠专辑（首次上榜即 #1）")

        if album_debut_no1.empty:
            st.info("暂无空冠专辑")
        else:
            st.metric("空冠专辑数", f"{len(album_debut_no1)} 张")
            _da_headers = ["专辑", "艺人", "首次上榜周", "在榜周数", "冠军周数"]
            _da_rows = []
            for _, _r in album_debut_no1.iterrows():
                _album_url = _bb_url(bb_nav="album", bb_name=str(_r['album_name']), bb_art=str(_r['artist_name']), bb_tab="💿 专辑榜单")
                _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
                _week_url = _bb_url(bb_nav="week", bb_date=str(_r['billboard_week']), bb_tab="📋 周榜")
                _da_rows.append([
                    (_html.escape(str(_r["album_name"])), _album_url),
                    (_html.escape(str(_r["artist_name"])), _artist_url),
                    (_html.escape(str(_r["billboard_week"])), _week_url),
                    str(_r["weeks_on_chart"]),
                    str(_r["weeks_at_no1"]),
                ])
            _render_bb_table(_da_headers, _da_rows,
                col_formats={3: "num", 4: "num"})

    # ─────────────────────────────────────────────────────────────────────
    # Sub-tab 2: 艺人榜
    # ─────────────────────────────────────────────────────────────────────
    with no1_tabs[2]:
        # ── Summary Cards ────────────────────────────────────────────────
        total_no1_artists = artist_weeks_at_one["artist_name"].nunique()
        if not artist_weeks_at_one.empty:
            col_ar1, col_ar2, col_ar3 = st.columns(3)
            col_ar1.metric("总冠军艺人", f"{total_no1_artists} 位")
            col_ar2.metric(
                "最多冠军周数",
                f"{int(artist_weeks_at_one.iloc[0]['weeks_at_no1'])} 周",
                delta=artist_weeks_at_one.iloc[0]["artist_name"][:25],
            )
            col_ar3.metric(
                "最长连冠纪录",
                f"{artist_longest_streak} 周",
                delta=artist_longest_streak_name[:25] if artist_longest_streak > 0 else None,
            )
        else:
            st.metric("总冠军艺人", "0 位")

        st.divider()

        # ── Weekly #1 Artist Table ───────────────────────────────────────
        st.subheader("每周冠军艺人")

        _no1_artist_headers = ["周", "冠军艺人", "总播放次数", "入榜曲数", "入榜专辑数", "Pk Wks"]
        _no1_artist_rows = []
        for _, _r in number_one_artists.sort_values("billboard_week", ascending=False).iterrows():
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
            _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜")
            _no1_artist_rows.append([
                (_html.escape(str(_r["billboard_week"])), _week_url),
                (_html.escape(str(_r["artist_name"])), _artist_url),
                f"{_r['play_count']:,}",
                str(_r["tracks_count"]),
                str(_r.get("albums_count", 0)),
                str(_r["artist_pk_wks"]),
            ])
        _render_bb_table(_no1_artist_headers, _no1_artist_rows,
            col_formats={2: "num", 3: "num", 4: "num", 5: "num"}, height="600px")

        # ── Artist #1 Weeks Ranking Table ───────────────────────────────
        st.divider()
        st.subheader("冠军周数排行")

        artist_weeks_rank = artist_weeks_at_one.head(20).reset_index(drop=True)
        artist_weeks_rank.index = artist_weeks_rank.index + 1

        _arw_headers = ["#", "艺人", "冠军周数"]
        _arw_rows = []
        for _i, _r in artist_weeks_rank.iterrows():
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
            _arw_rows.append([
                str(_r.name),
                (_html.escape(str(_r["artist_name"])), _artist_url),
                str(_r["weeks_at_no1"]),
            ])
        _render_bb_table(_arw_headers, _arw_rows,
            col_formats={0: "rank", 2: "num"}, height="600px")

        # ── Artist #1 Weeks Chart ───────────────────────────────────────
        st.divider()
        st.subheader("艺人冠军周数 Top 15")

        if not artist_weeks_at_one.empty:
            artist_no1_chart = artist_weeks_at_one.head(15).sort_values("weeks_at_no1", ascending=True)
            fig_artist_no1 = go.Figure()
            fig_artist_no1.add_trace(
                go.Bar(
                    x=artist_no1_chart["weeks_at_no1"],
                    y=artist_no1_chart["artist_name"],
                    orientation="h",
                    marker=dict(
                        color=artist_no1_chart["weeks_at_no1"],
                        colorscale="YlOrRd",
                        showscale=True,
                        colorbar=dict(title="冠军周数"),
                    ),
                    text=artist_no1_chart["weeks_at_no1"].apply(lambda x: f"{x} 周"),
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>冠军周数: %{x} 周<extra></extra>",
                )
            )
            fig_artist_no1.update_layout(height=500)
            st.plotly_chart(fig_artist_no1, use_container_width=True)
        else:
            st.info("暂无艺人冠军数据")

"""Tab: 歌曲总榜 (All-Time Tracks Ranking)."""

import html as _html
import streamlit as st

from .shared import _bb_url, _render_bb_table


def render(track_summary, weekly):
    view_mode = st.radio(
        "排行方式",
        ["在榜周数排行", "Peak 排行"],
        horizontal=True,
    )

    if view_mode == "在榜周数排行":
        st.subheader("在榜周数排行")
        ranked = track_summary.sort_values(
            "weeks_on_chart", ascending=False
        ).reset_index(drop=True)
        ranked.index = ranked.index + 1

        _t6_headers = ["#", "曲目", "艺人", "Wks", "Peak", "Pk Wks", "首次入榜"]
        _t6_rows = []
        for _i, _r in ranked.iterrows():
            _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
            _t6_rows.append([
                str(_r.name),
                (_html.escape(str(_r["track_name"])), _track_url),
                (_html.escape(str(_r["artist_name"])), _artist_url),
                str(_r["weeks_on_chart"]),
                str(_r["peak_position"]),
                str(_r["weeks_at_peak"]),
                (_html.escape(str(_r["first_week"])), _bb_url(bb_nav="week", bb_date=_r['first_week'], bb_tab="📋 周榜")),
            ])
        _render_bb_table(_t6_headers, _t6_rows,
            col_formats={0: "rank", 3: "num", 4: "num", 5: "num"})

    else:
        # Peak ranking with selectable secondary sort
        peak_tie = st.radio(
            "Peak 相同时按",
            ["在榜周数", "Peak 周数"],
            horizontal=True,
            key="songs_peak_tiebreaker",
        )

        st.subheader(f"Peak 排行（Peak 相同按{peak_tie}）")
        if peak_tie == "在榜周数":
            ranked = track_summary.sort_values(
                ["peak_position", "weeks_on_chart", "weeks_at_peak"],
                ascending=[True, False, False],
            ).reset_index(drop=True)
        else:
            ranked = track_summary.sort_values(
                ["peak_position", "weeks_at_peak", "weeks_on_chart"],
                ascending=[True, False, False],
            ).reset_index(drop=True)
        ranked.index = ranked.index + 1

        _t6_headers = ["#", "曲目", "艺人", "Peak", "Wks", "Pk Wks", "首次入榜"]
        _t6_rows = []
        for _i, _r in ranked.iterrows():
            _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
            _t6_rows.append([
                str(_r.name),
                (_html.escape(str(_r["track_name"])), _track_url),
                (_html.escape(str(_r["artist_name"])), _artist_url),
                str(_r["peak_position"]),
                str(_r["weeks_on_chart"]),
                str(_r["weeks_at_peak"]),
                (_html.escape(str(_r["first_week"])), _bb_url(bb_nav="week", bb_date=_r['first_week'], bb_tab="📋 周榜")),
            ])
        _render_bb_table(_t6_headers, _t6_rows,
            col_formats={0: "rank", 3: "num", 4: "num", 5: "num"})

    # ── Song-weekly top plays ───────────────────────────────────────────
    st.divider()
    st.subheader("歌曲周播放次数 Top 100")

    song_weekly_top = (
        weekly.sort_values("play_count", ascending=False)
        .head(100)
        .reset_index(drop=True)
    )
    song_weekly_top.index = song_weekly_top.index + 1
    song_weekly_top["billboard_week"] = song_weekly_top["billboard_week"].astype(str)
    song_weekly_top["rank_display"] = song_weekly_top["rank"].apply(lambda x: f"#{x}")

    _swt_headers = ["#", "曲目", "艺人", "榜单周", "播放次数", "当周 Peak"]
    _swt_rows = []
    for _i, _r in song_weekly_top.iterrows():
        _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
        _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
        _swt_rows.append([
            str(_r.name),
            (_html.escape(str(_r["track_name"])), _track_url),
            (_html.escape(str(_r["artist_name"])), _artist_url),
            (_html.escape(str(_r["billboard_week"])), _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜")),
            f"{_r['play_count']:,}",
            str(_r["rank_display"]),
        ])
    _render_bb_table(_swt_headers, _swt_rows,
        col_formats={0: "rank", 3: "num", 4: "num"})

"""Tab: 专辑总榜 (Album Overall Ranking)."""

import html as _html
import streamlit as st
import plotly.express as px

from .shared import _bb_url, _render_bb_table


def render(album_track_counts):
    st.subheader("专辑总榜")

    album_rank_metric = st.radio(
        "排行指标",
        ["入榜曲数", "总上榜周数", "#1 曲数", "Top 5 曲数", "Top 10 曲数", "#1周数", "专辑#1周数"],
        horizontal=True,
        key="album_overall_metric",
    )

    album_metric_map = {
        "入榜曲数": "total_tracks",
        "总上榜周数": "total_weeks",
        "#1 曲数": "top1",
        "Top 5 曲数": "top5",
        "Top 10 曲数": "top10",
        "#1周数": "weeks_at_no1",
        "专辑#1周数": "album_chart_no1_weeks",
    }
    album_sort_col = album_metric_map[album_rank_metric]

    ranked_alb = album_track_counts.sort_values(album_sort_col, ascending=False).head(100).reset_index(drop=True)
    ranked_alb.index = ranked_alb.index + 1

    _alb_overall_headers = ["#", "专辑", "艺人", "入榜曲数", "#1 曲数", "#1周数", "专辑#1周数", "Top5", "Top10", "总周数"]
    _alb_overall_rows = []
    for _i, (_, _r) in enumerate(ranked_alb.iterrows()):
        _alb_url = _bb_url(bb_nav="album", bb_name=str(_r['album_name']), bb_art=str(_r['artist_name']), bb_tab="💿 专辑榜单")
        _alb_overall_rows.append([
            str(_r.name),
            (_html.escape(str(_r["album_name"])), _alb_url),
            _html.escape(str(_r["artist_name"])),
            f"{int(_r['total_tracks']):,}",
            f"{int(_r['top1']):,}",
            f"{int(_r['weeks_at_no1']):,}",
            f"{int(_r['album_chart_no1_weeks']):,}",
            f"{int(_r['top5']):,}",
            f"{int(_r['top10']):,}",
            f"{int(_r['total_weeks']):,}",
        ])
    _render_bb_table(_alb_overall_headers, _alb_overall_rows,
                     col_formats={0: "rank", 3: "num", 4: "num", 5: "num", 6: "num", 7: "num", 8: "num", 9: "num"},
                     height="600px")

    chart_alb = ranked_alb.head(20).sort_values(album_sort_col, ascending=True)
    fig2 = px.bar(
        chart_alb,
        x=album_sort_col,
        y="album_name",
        orientation="h",
        labels={album_sort_col: album_rank_metric, "album_name": ""},
        height=600,
        title=f"专辑 {album_rank_metric} Top 20",
    )
    fig2.update_yaxes(autorange="reversed")
    st.plotly_chart(fig2, use_container_width=True)

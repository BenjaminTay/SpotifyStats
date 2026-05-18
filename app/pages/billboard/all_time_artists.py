"""Tab: 艺人总榜 (Artist Overall Ranking)."""

import html as _html
import streamlit as st
import plotly.express as px

from .shared import _bb_url, _render_bb_table


def render(artist_track_counts):
    st.subheader("艺人总榜")

    artist_rank_metric = st.radio(
        "排行指标",
        ["入榜曲数", "总上榜周数", "#1 曲数", "Top 5 曲数", "Top 10 曲数", "#1周数"],
        horizontal=True,
        key="artist_overall_metric",
    )

    metric_map = {
        "入榜曲数": "total_tracks",
        "总上榜周数": "total_weeks",
        "#1 曲数": "top1",
        "Top 5 曲数": "top5",
        "Top 10 曲数": "top10",
        "#1周数": "weeks_at_no1",
        "#1 专辑数": "num_no1_albums",
        "专辑#1周数": "album_no1_weeks",
        "艺人榜#1周数": "artist_chart_no1_weeks",
    }
    sort_col = metric_map[artist_rank_metric]

    ranked_art = artist_track_counts.sort_values(sort_col, ascending=False).head(100).reset_index(drop=True)
    ranked_art.index = ranked_art.index + 1

    _art_overall_names = ranked_art["artist_name"].tolist()
    _art_overall_headers = ["#", "艺人", "入榜曲数", "#1 曲数", "#1周数", "#1 专辑数", "专辑#1周数", "艺人榜#1周数", "Top5", "Top10", "总周数"]
    _art_rows = []
    for _i, (_, _r) in enumerate(ranked_art.iterrows()):
        _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
        _art_rows.append([
            str(_r.name),
            (_html.escape(str(_r["artist_name"])), _artist_url),
            f"{int(_r['total_tracks']):,}",
            f"{int(_r['top1']):,}",
            f"{int(_r['weeks_at_no1']):,}",
            f"{int(_r['num_no1_albums']):,}",
            f"{int(_r['album_no1_weeks']):,}",
            f"{int(_r['artist_chart_no1_weeks']):,}",
            f"{int(_r['top5']):,}",
            f"{int(_r['top10']):,}",
            f"{int(_r['total_weeks']):,}",
        ])
    _render_bb_table(_art_overall_headers, _art_rows,
                     col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 5: "num", 6: "num", 7: "num", 8: "num", 9: "num", 10: "num"},
                     height="600px")

    # Chart
    chart_art = ranked_art.head(20).sort_values(sort_col, ascending=True)
    fig = px.bar(
        chart_art,
        x=sort_col,
        y="artist_name",
        orientation="h",
        labels={sort_col: artist_rank_metric, "artist_name": ""},
        height=600,
        title=f"艺人 {artist_rank_metric} Top 20",
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

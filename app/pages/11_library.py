"""Music Library — saved tracks/albums/artists vs actual listening."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.db import get_db
from app.styles import inject_global_styles, page_header, kpi_row, PLOTLY_TEMPLATE, COLORS

inject_global_styles()


@st.cache_data(ttl=3600)
def load_library_data():
    conn = get_db()

    saved_tracks = pd.read_sql_query("SELECT * FROM saved_tracks", conn)
    saved_albums = pd.read_sql_query("SELECT * FROM saved_albums", conn)
    saved_artists = pd.read_sql_query("SELECT * FROM saved_artists", conn)
    playlists = pd.read_sql_query("SELECT * FROM playlists", conn)
    playlist_tracks = pd.read_sql_query("SELECT * FROM playlist_tracks", conn)
    banned = pd.read_sql_query("SELECT * FROM banned_items", conn)

    has_data = not saved_tracks.empty or not playlists.empty

    # Cross-reference: saved tracks vs actual plays via URI matching
    coverage_pct = 0
    saved_with_plays = pd.DataFrame()
    forgotten = pd.DataFrame()
    artist_comparison = pd.DataFrame()

    if not saved_tracks.empty:
        # Extract track IDs from URIs
        saved_tracks["track_id_part"] = saved_tracks["track_uri"].apply(
            lambda u: u.replace("spotify:track:", "") if isinstance(u, str) else ""
        )
        track_ids = saved_tracks["track_id_part"].tolist()
        placeholders = ",".join("?" * len(track_ids))
        matched = pd.read_sql_query(
            f"""SELECT REPLACE(t.spotify_track_uri, 'spotify:track:', '') as tid,
                       COUNT(p.play_id) as play_count, MAX(p.ts_date) as last_played
                FROM tracks t
                LEFT JOIN plays p ON t.track_id = p.track_id
                WHERE REPLACE(t.spotify_track_uri, 'spotify:track:', '') IN ({placeholders})
                GROUP BY tid""",
            conn, params=track_ids,
        )
        if not matched.empty:
            saved_with_plays = saved_tracks.merge(
                matched, left_on="track_id_part", right_on="tid", how="left"
            )
            saved_with_plays["play_count"] = saved_with_plays["play_count"].fillna(0).astype(int)
            coverage_pct = (saved_with_plays["play_count"] > 0).mean() * 100

            # Forgotten treasures: saved but not played, or not played in 6 months
            six_months_ago = pd.Timestamp.now() - pd.Timedelta(days=180)
            forgotten = saved_with_plays[
                (saved_with_plays["play_count"] == 0) |
                (pd.to_datetime(saved_with_plays["last_played"]) < six_months_ago)
            ]

        # Artist comparison: saved artist track count vs actual plays
        if not saved_tracks.empty:
            artist_comp_raw = conn.execute(
                """SELECT sa.artist_name,
                          COUNT(st.track_uri) as saved_count
                   FROM saved_artists sa
                   LEFT JOIN saved_tracks st ON st.artist_name = sa.artist_name
                   GROUP BY sa.artist_name"""
            ).fetchall()
            artist_comparison = pd.DataFrame(
                artist_comp_raw, columns=["artist_name", "saved_count"]
            )
            # Get actual play counts
            for i, row in artist_comparison.iterrows():
                a_plays = conn.execute(
                    """SELECT COUNT(DISTINCT p.play_id)
                       FROM plays p
                       JOIN tracks t ON p.track_id = t.track_id
                       JOIN artists a ON t.artist_id = a.artist_id
                       WHERE a.artist_name = ?""",
                    (row["artist_name"],),
                ).fetchone()[0]
                artist_comparison.at[i, "play_count"] = a_plays
            artist_comparison["play_count"] = artist_comparison["play_count"].fillna(0).astype(int)

    conn.close()

    return {
        "has_data": has_data,
        "saved_tracks": saved_tracks,
        "saved_albums": saved_albums,
        "saved_artists": saved_artists,
        "playlists": playlists,
        "playlist_tracks": playlist_tracks,
        "banned": banned,
        "coverage_pct": coverage_pct,
        "forgotten": forgotten,
        "artist_comparison": artist_comparison,
    }


def render():
    data = load_library_data()

    if not data["has_data"]:
        st.warning("请先在「设置」页面导入账号数据")
        return

    page_header("音乐库", description="收藏、歌单与实际播放的交叉分析")

    kpi_row([
        {"label": "已收藏曲目", "value": str(len(data["saved_tracks"]))},
        {"label": "已收藏专辑", "value": str(len(data["saved_albums"]))},
        {"label": "已关注艺人", "value": str(len(data["saved_artists"]))},
        {"label": "歌单数", "value": str(len(data["playlists"]))},
    ])

    tab1, tab2, tab3 = st.tabs(["收藏总览", "歌单分析", "遗忘宝藏"])

    with tab1:
        st.markdown(f"#### 覆盖率：{data['coverage_pct']:.1f}% 收藏曲目有播放记录")

        # Artist comparison
        ac = data["artist_comparison"]
        if not ac.empty:
            top_artists = ac.nlargest(15, "saved_count")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=top_artists["artist_name"], x=top_artists["saved_count"],
                name="收藏曲目数", orientation="h",
                marker={"color": COLORS[0]},
            ))
            fig.add_trace(go.Bar(
                y=top_artists["artist_name"], x=top_artists["play_count"],
                name="实际播放次数", orientation="h",
                marker={"color": COLORS[2]},
            ))
            fig.update_layout(
                **PLOTLY_TEMPLATE["layout"],
                barmode="group", height=400,
                xaxis={"title": "数量"},
            )
            st.plotly_chart(fig, use_container_width=True)

        # Playlist size distribution
        if not data["playlists"].empty:
            st.markdown("#### 歌单大小分布")
            fig_hist = px.histogram(
                data["playlists"], x="track_count", nbins=15,
                color_discrete_sequence=[COLORS[1]],
            )
            fig_hist.update_layout(**PLOTLY_TEMPLATE["layout"])
            fig_hist.update_layout(height=250, xaxis={"title": "曲目数"})
            st.plotly_chart(fig_hist, use_container_width=True)

    with tab2:
        if not data["playlists"].empty:
            st.markdown("#### 所有歌单")
            pl_df = data["playlists"][["playlist_name", "track_count", "last_modified_date", "follower_count"]]
            pl_df.columns = ["歌单名", "曲目数", "最后修改", "关注者"]
            pl_df = pl_df.sort_values("曲目数", ascending=False)
            st.dataframe(pl_df, use_container_width=True, hide_index=True)

            # ── Playlist drill-down ─────────────────────────────────
            st.divider()
            st.markdown("#### 查看歌单内容")

            pl_names = data["playlists"]["playlist_name"].tolist()
            pl_ids = data["playlists"]["playlist_id"].tolist()
            selected_pl_name = st.selectbox("选择歌单", pl_names, key="pl_drilldown")

            selected_pl_id = pl_ids[pl_names.index(selected_pl_name)]
            pl_tracks = data["playlist_tracks"][
                data["playlist_tracks"]["playlist_id"] == selected_pl_id
            ]
            if not pl_tracks.empty:
                pl_tracks_display = pl_tracks[
                    ["track_name", "artist_name", "album_name", "added_date"]
                ].copy()
                pl_tracks_display.columns = ["曲目", "艺人", "专辑", "添加日期"]
                pl_tracks_display = pl_tracks_display.reset_index(drop=True)
                pl_tracks_display.index = pl_tracks_display.index + 1
                st.dataframe(
                    pl_tracks_display,
                    use_container_width=True,
                    height=400,
                )
                st.caption(f"共 {len(pl_tracks_display)} 首曲目")
            else:
                st.caption("此歌单暂无曲目数据")

            # Playlist overlap matrix (top 10 by size)
            st.divider()
            top_pl = data["playlists"].nlargest(10, "track_count")
            if len(top_pl) > 1:
                st.markdown("#### Top 10 歌单重叠矩阵")
                top_pl_ids = top_pl["playlist_id"].tolist()
                names = top_pl["playlist_name"].tolist()

                pt = data["playlist_tracks"]
                matrix = [[0] * len(top_pl_ids) for _ in range(len(top_pl_ids))]
                for i, pid1 in enumerate(top_pl_ids):
                    uris1 = set(pt[pt["playlist_id"] == pid1]["track_uri"])
                    for j, pid2 in enumerate(top_pl_ids):
                        uris2 = set(pt[pt["playlist_id"] == pid2]["track_uri"])
                        matrix[i][j] = len(uris1 & uris2)

                fig_heat = go.Figure(data=go.Heatmap(
                    z=matrix,
                    x=[n[:8] for n in names],
                    y=[n[:8] for n in names],
                    colorscale=[[0, "rgba(184,134,11,0.05)"], [1, "rgb(184,134,11)"]],
                ))
                fig_heat.update_layout(**PLOTLY_TEMPLATE["layout"])
                fig_heat.update_layout(height=400)
                st.plotly_chart(fig_heat, use_container_width=True)

    with tab3:
        forgotten = data["forgotten"]
        if not forgotten.empty:
            n = min(30, len(forgotten))
            st.markdown(f"#### 遗忘宝藏（收藏但未播放或超 6 个月未听）：{len(forgotten)} 首")
            show_df = forgotten[["track_name", "artist_name", "album_name", "play_count"]].head(n)
            show_df["last_played"] = forgotten["last_played"].head(n).values
            show_df.columns = ["曲目", "艺人", "专辑", "播放次数", "最后播放"]
            st.dataframe(show_df, use_container_width=True, hide_index=True)
        else:
            st.success("所有收藏曲目都有播放记录！")

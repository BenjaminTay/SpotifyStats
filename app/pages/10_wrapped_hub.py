"""Wrapped 2025 — Official Spotify year-in-review summary."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.db import get_db
from app.styles import inject_global_styles, page_header, kpi_row, PLOTLY_TEMPLATE, COLORS

inject_global_styles()


def _resolve_uri_name(conn, uri: str, uri_type: str) -> str:
    """Resolve a Spotify URI to a human-readable name using dimension tables."""
    if not uri:
        return "Unknown"
    extracted_id = uri.split(":")[-1] if ":" in uri else uri

    if uri_type == "artist":
        # Try spotify_artist_meta (from Spotify API)
        row = conn.execute(
            "SELECT artist_name FROM spotify_artist_meta WHERE spotify_artist_id = ?",
            (extracted_id,),
        ).fetchone()
        if row:
            return row[0]
        # Try saved_artists (from account data)
        row = conn.execute(
            "SELECT artist_name FROM saved_artists WHERE artist_uri = ?",
            (uri,),
        ).fetchone()
        if row:
            return row[0]
    elif uri_type == "track":
        # Try tracks table on spotify_track_uri
        row = conn.execute(
            "SELECT track_name FROM tracks WHERE spotify_track_uri = ?",
            (uri,),
        ).fetchone()
        if row:
            return row[0]
        # Try saved_tracks
        row = conn.execute(
            "SELECT track_name FROM saved_tracks WHERE track_uri = ?",
            (uri,),
        ).fetchone()
        if row:
            return row[0]
    elif uri_type == "album":
        # Try spotify_album_meta (from Spotify API)
        row = conn.execute(
            "SELECT album_name FROM spotify_album_meta WHERE spotify_album_id = ?",
            (extracted_id,),
        ).fetchone()
        if row:
            return row[0]
        # Try saved_albums
        row = conn.execute(
            "SELECT album_name FROM saved_albums WHERE album_uri = ?",
            (uri,),
        ).fetchone()
        if row:
            return row[0]

    return extracted_id[:16] if extracted_id else "Unknown"


@st.cache_data(ttl=3600)
def load_official_wrapped_data():
    conn = get_db()

    top_artists = pd.read_sql_query(
        "SELECT * FROM wrapped_top_artists ORDER BY rank", conn
    )
    top_tracks = pd.read_sql_query(
        "SELECT * FROM wrapped_top_tracks ORDER BY rank", conn
    )
    top_albums = pd.read_sql_query(
        "SELECT * FROM wrapped_top_albums ORDER BY rank", conn
    )
    artist_race = pd.read_sql_query(
        "SELECT * FROM wrapped_artist_race", conn
    )
    clubs = pd.read_sql_query(
        "SELECT * FROM wrapped_clubs", conn
    )
    party = pd.read_sql_query(
        "SELECT * FROM wrapped_party", conn
    )
    la_row = conn.execute(
        "SELECT * FROM wrapped_listening_age"
    ).fetchone()
    listening_age = dict(la_row) if la_row else None
    archive_reports = pd.read_sql_query(
        "SELECT * FROM wrapped_archive_reports", conn
    )
    top_genres = pd.read_sql_query(
        "SELECT * FROM wrapped_top_genres ORDER BY rank", conn
    )
    top_podcasts = pd.read_sql_query(
        "SELECT * FROM wrapped_top_podcasts ORDER BY rank", conn
    )

    # Resolve display names from URIs
    if not top_artists.empty:
        top_artists["display_name"] = top_artists["artist_uri"].apply(
            lambda u: _resolve_uri_name(conn, u, "artist")
        )
    if not top_tracks.empty:
        top_tracks["display_name"] = top_tracks["track_uri"].apply(
            lambda u: _resolve_uri_name(conn, u, "track")
        )
    if not top_albums.empty:
        top_albums["display_name"] = top_albums["album_uri"].apply(
            lambda u: _resolve_uri_name(conn, u, "album")
        )
    if not artist_race.empty:
        artist_race["display_name"] = artist_race["artist_uri"].apply(
            lambda u: _resolve_uri_name(conn, u, "artist")
        )

    conn.close()

    has_data = not top_artists.empty or not top_tracks.empty
    return {
        "has_data": has_data,
        "top_artists": top_artists,
        "top_tracks": top_tracks,
        "top_albums": top_albums,
        "artist_race": artist_race,
        "clubs": clubs,
        "party": party,
        "listening_age": listening_age,
        "archive_reports": archive_reports,
        "top_genres": top_genres,
        "top_podcasts": top_podcasts,
    }


def _get_party_metric(party_df, key, default=0):
    row = party_df[party_df["metric"] == key]
    if row.empty:
        return default
    return row.iloc[0]["value"]


def render():
    data = load_official_wrapped_data()

    if not data["has_data"]:
        st.warning("请先在「设置」页面导入账号数据")
        return

    page_header("Wrapped 2025", description="Spotify 官方年度回顾")

    party = data["party"]

    # ── Section 1: Hero KPIs ──────────────────────────────────────────────
    total_min = _get_party_metric(party, "totalNumListeningMinutes", 0)
    total_hours = total_min / 60
    num_artists = int(_get_party_metric(party, "numUniqueArtists", 0))
    num_tracks = int(_get_party_metric(party, "numUniqueTracks", 0))
    streak_days = int(_get_party_metric(party, "streakNumListeningDays", 0))

    kpi_row([
        {"label": "总收听时长", "value": f"{total_hours:,.0f} 小时"},
        {"label": "独特艺人", "value": f"{num_artists}"},
        {"label": "独特曲目", "value": f"{num_tracks}"},
        {"label": "连续收听天数", "value": f"{streak_days} 天"},
    ])

    # Club info
    clubs = data["clubs"]
    if not clubs.empty:
        club_name = clubs.iloc[0]["club_name"]
        club_pct = clubs.iloc[0]["percent_in_club"] * 100
        club_role = clubs.iloc[0]["role"]
        st.markdown(
            f"""<div style="background:linear-gradient(135deg,var(--bg-header),var(--bg-card));
            border:1px solid var(--border-gold);border-radius:var(--radius);padding:1.25rem;
            margin:1rem 0;text-align:center;">
            <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--text-secondary);">你的俱乐部</div>
            <div style="font-size:1.5rem;font-weight:700;color:var(--gold);margin:0.25rem 0;">{club_name}</div>
            <div style="font-size:0.85rem;color:var(--text-primary);">角色：{club_role} · 前 {club_pct:.1f}% 听众</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Section 2: Top Artist Race ────────────────────────────────────────
    st.markdown("### 艺人竞速")
    st.caption("全年 5 位顶尖艺人的月度排名变化（1月–11月）")

    race = data["artist_race"]
    if not race.empty:
        months_order = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
                        "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER"]
        race["month_num"] = race["month"].apply(
            lambda m: months_order.index(m) if m in months_order else 0
        )

        fig = go.Figure()
        # Rank 1 is best — reverse Y so 1 is at top
        uri_names = race.groupby("artist_uri")["display_name"].first().to_dict()
        for i, (uri, name) in enumerate(uri_names.items()):
            if not isinstance(name, str) or not name:
                name = f"Artist {i+1}"
            adf = race[race["artist_uri"] == uri].sort_values("month_num")
            fig.add_trace(go.Scatter(
                x=adf["month_num"], y=adf["rank"],
                mode="lines+markers", name=name,
                line={"color": COLORS[i % len(COLORS)], "width": 2.5},
                marker={"size": 6},
            ))

        fig.update_layout(
            **PLOTLY_TEMPLATE["layout"],
            height=350,
        )
        fig.update_xaxes(tickvals=list(range(11)), ticktext=[m[:3] for m in months_order],
                         gridcolor="rgba(139,115,85,0.08)")
        fig.update_yaxes(autorange="reversed", tickvals=[1, 2, 3, 4, 5],
                         gridcolor="rgba(139,115,85,0.08)", title="排名")
        st.plotly_chart(fig, use_container_width=True)

    # ── Section 3: Party Personality ──────────────────────────────────────
    st.markdown("### 收听性格")

    col_a, col_b = st.columns(2)

    with col_a:
        happy = _get_party_metric(party, "percentHappyTracks", 0)
        love = _get_party_metric(party, "percentLoveTracks", 0)
        party_pct = _get_party_metric(party, "percentPartyTracks", 0)
        night = _get_party_metric(party, "percentListenedNight", 0)
        explicit = _get_party_metric(party, "percentListenedExplicit", 0)

        radar = go.Figure()
        radar.add_trace(go.Scatterpolar(
            r=[happy, love, party_pct, night, explicit],
            theta=["Happy", "Love", "Party", "夜间", "Explicit"],
            fill="toself",
            fillcolor="rgba(184,134,11,0.15)",
            line={"color": COLORS[0], "width": 2},
            name="你的收听",
        ))
        radar.update_layout(
            polar={
                "radialaxis": {"visible": True, "color": "#8B7355"},
                "angularaxis": {"color": "#8B7355"},
                "bgcolor": "rgba(0,0,0,0)",
            },
            paper_bgcolor="rgba(0,0,0,0)",
            height=320,
            margin={"l": 10, "r": 10, "t": 30, "b": 10},
        )
        st.plotly_chart(radar, use_container_width=True)

    with col_b:
        kpi_row([
            {"label": "多语言评分", "value": f"{_get_party_metric(party, 'multilinguistRankingScore', 0):.1f}"},
            {"label": "混乱度", "value": f"{_get_party_metric(party, 'absoluteChaosRankingScore', 0):.0f}"},
        ])
        kpi_row([
            {"label": "平均曲目热度", "value": f"{_get_party_metric(party, 'avgTrackPopularityScore', 0):.1f}"},
            {"label": "分享次数", "value": f"{_get_party_metric(party, 'numSharesAllContent', 0):.0f}"},
        ])
        kpi_row([
            {"label": "收听天数", "value": f"{int(_get_party_metric(party, 'totalNumListeningDays', 0))}"},
            {"label": "发现新艺人", "value": f"{int(_get_party_metric(party, 'numArtistsDiscovered', 0))}"},
        ])

    # ── Section 4: Listening Age ──────────────────────────────────────────
    la = data["listening_age"]
    if la:
        st.markdown("### 收听年龄")
        st.markdown(
            f"""<div style="text-align:center;margin:1rem 0;">
            <div style="font-size:3rem;font-weight:700;color:var(--gold);font-family:Georgia,serif;">{la['listening_age']} 年</div>
            <div style="color:var(--text-secondary);">音乐品味跨度 · {la['window_start_year']} 至今 · {la['decade_phase']} phase</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Section 5: Archive Reports ────────────────────────────────────────
    reports = data["archive_reports"]
    if not reports.empty:
        st.markdown("### 特别日子")

        REASON_LABELS = {
            "BIGGEST_TOP_GENRE_DAY": "年度最大流派日",
            "BIGGEST_TOP_ARTIST_DAY": "年度最大艺人日",
            "BIGGEST_PODCAST_LISTENING_DAY": "年度播客日",
            "MOST_ENERGETIC_DAY": "最嗨的一天",
            "BIGGEST_MUSIC_LISTENING_DAY": "听歌最多的一天",
        }

        cols = st.columns(len(reports))
        for i, (_, r) in enumerate(reports.iterrows()):
            with cols[i]:
                reason_label = REASON_LABELS.get(r["reason"], r["reason"])
                st.markdown(
                    f"""<div style="background:var(--bg-card);border:1px solid var(--border);
                    border-radius:8px;padding:1rem;height:100%;">
                    <div style="font-size:0.65rem;text-transform:uppercase;color:var(--gold);margin-bottom:0.4rem;">
                    {reason_label}</div>
                    <div style="font-weight:700;color:var(--text-primary);margin-bottom:0.25rem;">
                    {r['title']}</div>
                    <div style="font-size:0.8rem;color:var(--text-secondary);">
                    {r['description'][:120]}...</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

    # ── Section 6: Official Top Charts ────────────────────────────────────
    st.markdown("### 官方排行榜")

    col_t, col_a2, col_al = st.columns(3)

    with col_t:
        st.markdown("**Top 5 歌曲**")
        tracks = data["top_tracks"]
        if not tracks.empty:
            for _, t in tracks.iterrows():
                name = t.get("display_name") or t["track_uri"].replace("spotify:track:", "")[:20]
                rank = int(t.get("rank", 0))
                st.markdown(
                    f"""<div style="display:flex;justify-content:space-between;padding:0.3rem 0;
                    border-bottom:1px solid rgba(139,115,85,0.06);">
                    <span style="font-size:0.85rem;"><strong>#{rank}</strong> {name}</span>
                    <span style="font-size:0.8rem;color:var(--text-secondary);">{t['play_count']} 次</span>
                    </div>""",
                    unsafe_allow_html=True,
                )

    with col_a2:
        st.markdown("**Top 5 艺人**")
        artists = data["top_artists"]
        if not artists.empty:
            for _, a in artists.iterrows():
                name = a.get("display_name") or a["artist_uri"].replace("spotify:artist:", "")[:20]
                rank = int(a.get("rank", 0))
                st.markdown(
                    f"""<div style="padding:0.3rem 0;
                    border-bottom:1px solid rgba(139,115,85,0.06);">
                    <span style="font-size:0.85rem;"><strong>#{rank}</strong> {name}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )

    with col_al:
        st.markdown("**Top 5 专辑**")
        albums = data["top_albums"]
        if not albums.empty:
            for _, a in albums.iterrows():
                name = a.get("display_name") or a["album_uri"].replace("spotify:album:", "")[:20]
                rank = int(a.get("rank", 0))
                st.markdown(
                    f"""<div style="padding:0.3rem 0;
                    border-bottom:1px solid rgba(139,115,85,0.06);">
                    <span style="font-size:0.85rem;"><strong>#{rank}</strong> {name}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )

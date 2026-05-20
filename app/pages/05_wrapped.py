"""Spotify Wrapped-style annual report with card-based storytelling."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.db import get_db, load_plays
from app.styles import inject_global_styles

inject_global_styles()

min_ms = st.session_state.get("min_ms", 30000)
music_only = st.session_state.get("music_only", True)
merge_enabled = st.session_state.get("merge_enabled", True)

# Vinyl Archive warm palette
GOLD = "#B8860B"
WARM_DARK = "#3C1F0A"
CARD_BG = "#FFFFFF"
TEXT_PRIMARY = "#2C2416"
TEXT_SECONDARY = "#8B7355"


@st.cache_data(ttl=3600)
def load_wrapped_data(_min_ms, _music_only, _merge_enabled):
    conn = get_db()
    df = load_plays(conn, min_ms=_min_ms, music_only=_music_only, merge_enabled=_merge_enabled)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_all_wrapped():
    conn = get_db()
    df = load_plays(conn, join_albums=False, filtered=False, music_only=False)
    conn.close()
    return df


df = load_wrapped_data(min_ms, music_only, merge_enabled)
df_all = load_all_wrapped()

years = sorted(df["ts_year"].unique().tolist(), reverse=True)

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        '<div style="font-size:2rem;margin-bottom:0.25rem;">🎁</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#2C2416;">Wrapped</div>'
        f'<div style="font-size:0.7rem;color:#8B7355;margin-top:0.15rem;">最短={min_ms//1000}s</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    selected_year = st.selectbox("选择年份", years, index=0)

# Filter to selected year
year_df = df[df["ts_year"] == selected_year]
year_all = df_all[df_all["ts_year"] == selected_year]

if year_df.empty:
    st.warning(f"{selected_year} 年没有符合条件的播放记录")
    st.stop()

# ── Compute stats for the year ──────────────────────────────────────
total_minutes = year_df["ms_played"].sum() / 60_000
total_plays = len(year_df)
total_tracks = year_df["track_id"].nunique()
total_artists = year_df["artist_name"].dropna().nunique()
total_days = year_df["ts_date"].nunique()

top_artists = (
    year_df.groupby("artist_name")
    .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
    .sort_values("hours", ascending=False)
    .head(5)
    .reset_index()
)

top_tracks = (
    year_df.groupby(["track_name", "artist_name"])
    .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
    .sort_values("plays", ascending=False)
    .head(5)
    .reset_index()
)

top_albums = (
    year_df.groupby(["album_name", "artist_name"])
    .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
    .sort_values("hours", ascending=False)
    .head(1)
    .reset_index()
)

# Peak hour
peak_hour = year_df["ts_hour"].value_counts().index[0]

# Platform story
platform_hours = (
    year_df.groupby("platform")["ms_played"].sum() / 3_600_000
).sort_values(ascending=False)

# First and last track
sorted_dates = year_df.sort_values("ts_date")
first_track = sorted_dates.iloc[0]
last_track = sorted_dates.iloc[-1]

# Jan #1 vs Dec #1
jan_df = year_df[year_df["ts_month"] == 1]
dec_df = year_df[year_df["ts_month"] == 12]
jan_top = jan_df.groupby("track_name").size().sort_values(ascending=False).index[0] if not jan_df.empty else "N/A"
dec_top = dec_df.groupby("track_name").size().sort_values(ascending=False).index[0] if not dec_df.empty else "N/A"

# ── Personality ─────────────────────────────────────────────────────
unique_ratio = total_tracks / max(total_plays, 1) * 100
top_artist_share = top_artists.iloc[0]["plays"] / max(total_plays, 1) * 100 if len(top_artists) > 0 else 0
avg_hours_per_day = total_minutes / 60 / max(total_days, 1)
skip_rate = year_all["skipped"].mean() * 100

# Scores
explorer_score = min(unique_ratio / 40 * 100, 100)
loyalist_score = min(top_artist_share / 20 * 100, 100)
binger_score = min(avg_hours_per_day / 4 * 100, 100)
skipper_score = min(skip_rate / 50 * 100, 100)

scores = {
    "Explorer 探索者": (explorer_score, "广泛涉猎不同曲目，保持音乐品味多样化"),
    "Loyalist 专一者": (loyalist_score, "对喜爱的艺人从一而终，深入了解他们的作品"),
    "Binger 狂听者": (binger_score, "音乐是日常必需品，每天大量时间沉浸在旋律中"),
    "Skipper 跳过者": (skipper_score, "宁缺毋滥，快速筛选只为找到最对味的歌"),
}
personality_label, (personality_score, personality_desc) = max(scores.items(), key=lambda x: x[1][0])

# ── CSS Styling ─────────────────────────────────────────────────────
st.markdown(
    f"""
<style>
.wrapped-hero {{
    background: linear-gradient(135deg, {WARM_DARK} 0%, {GOLD} 100%);
    border-radius: 20px;
    padding: 40px;
    text-align: center;
    color: white;
    margin-bottom: 24px;
}}
.wrapped-hero h1 {{
    font-size: 3em;
    margin: 0;
    font-weight: 900;
}}
.wrapped-hero .big-number {{
    font-size: 5em;
    font-weight: 900;
    line-height: 1;
}}
.wrapped-card {{
    background: #FFFFFF;
    border: 1px solid rgba(139,115,85,0.12);
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 16px;
    border-left: 4px solid {GOLD};
    box-shadow: 0 1px 3px rgba(139,69,19,0.06);
}}
.wrapped-card h3 {{
    color: {GOLD};
    margin-top: 0;
    font-family: Georgia, serif;
}}
.rank-number {{
    font-size: 2.5em;
    font-weight: 900;
    color: {GOLD};
    font-family: Georgia, serif;
}}
.artist-name {{
    font-size: 1.5em;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.track-name {{
    font-size: 1.2em;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}
</style>
""",
    unsafe_allow_html=True,
)

# ── Hero Card ───────────────────────────────────────────────────────
st.markdown(
    f"""
<div class="wrapped-hero">
    <p style="font-size:1.2em; opacity:0.8; margin:0;">YOUR {selected_year} IN MUSIC</p>
    <h1>你的音乐年度总结 🎵</h1>
    <div style="margin: 30px 0;">
        <span class="big-number">{total_minutes:,.0f}</span><br>
        <span style="font-size:1.5em;">分钟</span>
    </div>
    <p style="font-size:1.1em;">
        共播放 <b>{total_plays:,}</b> 次 | <b>{total_tracks:,}</b> 首曲目 | <b>{total_artists:,}</b> 位艺人
    </p>
    <p style="opacity:0.7;">{total_days} 天有音乐相伴</p>
</div>
""",
    unsafe_allow_html=True,
)

# ── Row 1: Top Artists + Top Tracks ─────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    artists_html = "".join(
        f"""<div style="display:flex; align-items:center; gap:16px; margin-bottom:16px;">
            <span class="rank-number">#{i+1}</span>
            <div>
                <span class="artist-name">{row['artist_name']}</span><br>
                <span style="color:#8B7355;">{row['plays']:,} 次 · {row['hours']:.1f} 小时</span>
            </div>
        </div>"""
        for i, (_, row) in enumerate(top_artists.iterrows())
    )
    st.markdown(
        f'<div class="wrapped-card"><h3>🎤 Top 5 艺人</h3>{artists_html}</div>',
        unsafe_allow_html=True,
    )

with col2:
    tracks_html = "".join(
        f"""<div style="display:flex; align-items:center; gap:16px; margin-bottom:16px;">
            <span class="rank-number">#{i+1}</span>
            <div>
                <span class="track-name">{row['track_name']}</span><br>
                <span style="color:#8B7355;">{row['artist_name']} · {row['plays']:,} 次 · {row['hours']:.1f} 小时</span>
            </div>
        </div>"""
        for i, (_, row) in enumerate(top_tracks.iterrows())
    )
    st.markdown(
        f'<div class="wrapped-card"><h3>🎵 Top 5 曲目</h3>{tracks_html}</div>',
        unsafe_allow_html=True,
    )

# ── Row 2: Top Album + Personality ──────────────────────────────────
col3, col4 = st.columns(2)

with col3:
    if not top_albums.empty:
        album = top_albums.iloc[0]
        album_html = f"""<div style="text-align:center; padding:20px 0;">
            <span class="artist-name">{album['album_name']}</span><br>
            <span style="color:#8B7355;">{album['artist_name']}</span><br>
            <span style="font-size:1.5em; font-weight:700; color:{GOLD};">{album['hours']:.1f} 小时</span>
        </div>"""
    else:
        album_html = ""
    st.markdown(
        f'<div class="wrapped-card"><h3>💿 年度最佳专辑</h3>{album_html}</div>',
        unsafe_allow_html=True,
    )

with col4:
    # Build progress bars as HTML
    progress_bars = ""
    for label, (score_val, _) in scores.items():
        pct = min(score_val / 100, 1.0)
        progress_bars += f"""<p style="color:#8B7355; margin:8px 0 4px; font-size:0.8em;">{label}: {score_val:.0f}%</p>
        <div style="background:rgba(139,115,85,0.15); border-radius:4px; height:6px; margin-bottom:8px;">
            <div style="background:{GOLD}; width:{pct*100:.0f}%; height:100%; border-radius:4px;"></div>
        </div>"""

    st.markdown(
        f"""<div class="wrapped-card">
        <h3>🎭 你的听歌人格</h3>
        <div style="text-align:center; padding:20px 0;">
            <span style="font-size:2em; font-weight:900; color:{GOLD};">{personality_label}</span><br>
            <p style="color:#8B7355; margin-top:12px;">{personality_desc}</p>
        </div>
        {progress_bars}
        </div>""",
        unsafe_allow_html=True,
    )

# ── Row 3: Time Machine + Platform Story ────────────────────────────
col5, col6 = st.columns(2)

with col5:
    st.markdown(
        f"""<div class="wrapped-card">
        <h3>⏰ 时间机器</h3>
        <div style="text-align:center;">
            <p style="color:#8B7355;">一月最爱</p>
            <span class="track-name">{jan_top}</span>
            <hr style="border-color:#D4A84B;">
            <p style="color:#8B7355;">十二月最爱</p>
            <span class="track-name">{dec_top}</span>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

with col6:
    platforms_html = "".join(
        f"""<div style="display:flex; justify-content:space-between; margin-bottom:8px;">
            <span>{p.upper()}</span>
            <span style="color:{GOLD}; font-weight:700;">{h:.1f} 小时</span>
        </div>"""
        for p, h in platform_hours.items()
    )
    st.markdown(
        f'<div class="wrapped-card"><h3>📱 平台故事</h3>{platforms_html}</div>',
        unsafe_allow_html=True,
    )

# ── Row 4: Peak Hour + Monthly Pulse ────────────────────────────────
col7, col8 = st.columns(2)

with col7:
    st.markdown(
        f"""<div class="wrapped-card">
        <h3>🌙 高峰时段</h3>
        <div style="text-align:center; padding:30px 0;">
            <p style="color:#8B7355;">你最常听歌的时间是</p>
            <span style="font-size:3em; font-weight:900; color:{GOLD};">{peak_hour}:00</span>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

with col8:
    monthly = (
        year_df.groupby("ts_month")
        .agg(hours=("ms_played", lambda x: x.sum() / 3_600_000))
        .reset_index()
    )
    monthly["ts_month"] = monthly["ts_month"].astype(int)

    fig = px.bar(
        monthly,
        x="ts_month",
        y="hours",
        labels={"ts_month": "月份", "hours": "小时"},
    )
    fig.update_traces(marker_color=GOLD)
    fig.update_layout(
        height=220,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#8B7355",
    )
    fig.update_xaxes(tickvals=list(range(1, 13)))

    with st.container(border=True):
        st.markdown('<h3 style="color:#B8860B; margin-top:0;">📊 月度脉搏</h3>', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── Footer ──────────────────────────────────────────────────────────
st.divider()
st.caption(f"🎧 数据来源：Spotify Extended Streaming History | {first_track['ts_date']} — {last_track['ts_date']}")

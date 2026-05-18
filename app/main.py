"""Spotify Stats — Streamlit entry point and overview dashboard."""

import os
import sys

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.db import get_db, init_db, ensure_schema, base_filters, load_plays, db_exists
from app.import_data import import_data
from app.styles import inject_global_styles, page_header, kpi_row, filter_badge

st.set_page_config(
    page_title="Spotify Stats",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_styles()

# ── Plotly warm template (Vinyl Archive) ─────────────────────────────
PLOTLY_TEMPLATE = {
    "layout": {
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#8B7355", "size": 11, "family": "Palatino, Book Antiqua, serif"},
        "xaxis": {"gridcolor": "rgba(139,115,85,0.08)", "linecolor": "rgba(139,115,85,0.15)"},
        "yaxis": {"gridcolor": "rgba(139,115,85,0.08)", "linecolor": "rgba(139,115,85,0.15)"},
        "legend": {"font": {"color": "#8B7355"}},
        "title": {"font": {"color": "#2C2416", "size": 14, "family": "Georgia, serif"}},
        "margin": {"l": 10, "r": 10, "t": 40, "b": 10},
        "hoverlabel": {"bgcolor": "#FFFFFF", "font": {"color": "#2C2416"}, "bordercolor": "#D4A84B"},
    }
}

COLORS = ["#B8860B", "#C45C3A", "#7D8C4E", "#D4845A", "#D4A84B", "#5C3D2E", "#C4956A", "#8B6914"]


# ── Session state defaults ──────────────────────────────────────────
if "min_ms" not in st.session_state:
    st.session_state.min_ms = 30000
if "exclude_skipped" not in st.session_state:
    st.session_state.exclude_skipped = True
if "music_only" not in st.session_state:
    st.session_state.music_only = True


# ── Sidebar ──────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center;margin-bottom:0.5rem;">
                <div style="font-size:2.5rem;margin-bottom:0.25rem;">🎵</div>
                <div style="font-size:1.05rem;font-weight:700;color:#2C2416;">Spotify Stats</div>
                <div style="font-size:0.7rem;color:#8B7355;margin-top:0.1rem;">Extended Streaming History</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # Filter summary
        st.markdown(
            '<div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:#8B7355;margin-bottom:0.4rem;">当前过滤</div>',
            unsafe_allow_html=True,
        )
        min_s = st.session_state.min_ms // 1000
        st.markdown(
            f"""
            <div style="display:flex;flex-wrap:wrap;gap:0.3rem;margin-bottom:0.75rem;">
                <span class="sidebar-badge">⏱ {min_s}s</span>
                <span class="sidebar-badge">{'🚫 跳过' if st.session_state.exclude_skipped else '✅ 跳过'}</span>
                <span class="sidebar-badge">{'🎶 音乐' if st.session_state.music_only else '📻 全部'}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        bb_n = st.session_state.get("bb_top_n", 30)
        bb_album_n = st.session_state.get("bb_album_top_n", 20)
        bb_artist_n = st.session_state.get("bb_artist_top_n", 20)
        st.markdown(
            f"""
            <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:#8B7355;margin-bottom:0.4rem;">Billboard</div>
            <div style="display:flex;flex-wrap:wrap;gap:0.3rem;margin-bottom:0.75rem;">
                <span class="sidebar-badge">🎵 单曲 Top {bb_n}</span>
                <span class="sidebar-badge">💿 专辑 Top {bb_album_n}</span>
                <span class="sidebar-badge">🎤 艺人 Top {bb_artist_n}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # Database status
        if db_exists():
            conn = get_db()
            count = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
            conn.close()
            st.markdown(
                f"""
                <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:#8B7355;margin-bottom:0.4rem;">数据库</div>
                <div style="font-size:0.8rem;color:#B8860B;font-weight:600;">● {count:,} 条记录</div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-size:0.8rem;color:#C45C3A;font-weight:600;">● 未导入</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div style="margin-top:1rem;font-size:0.7rem;color:#8B7355;">💡 前往「⚙️ 设置」调整参数</div>',
            unsafe_allow_html=True,
        )

        # Sidebar badge CSS
        st.markdown(
            """
            <style>
            .sidebar-badge {
                display:inline-block;
                background:var(--bg-card);
                border:1px solid var(--border-gold);
                border-radius:16px;
                padding:0.15rem 0.6rem;
                font-size:0.68rem;
                color:#8B7355;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )


# ── First-run import ────────────────────────────────────────────────
def ensure_data():
    if not db_exists():
        with st.spinner("首次使用，正在导入 Spotify 播放记录..."):
            try:
                result = import_data(
                    progress_callback=lambda msg, pct: st.info(msg) if pct == 0 else None,
                    agg_min_ms=st.session_state.get("min_ms", 30000),
                    agg_exclude_skipped=st.session_state.get("exclude_skipped", True),
                    agg_music_only=st.session_state.get("music_only", True),
                    agg_week_start_dow=st.session_state.get("bb_week_start_dow", 4),
                    agg_week_start_hour=st.session_state.get("bb_week_start_hour", 0),
                )
                st.success(
                    f"导入完成！{result['total_records']:,} 条记录，"
                    f"{result['unique_artists']} 位艺人，{result['unique_tracks']} 首曲目"
                )
                st.cache_data.clear()
                st.rerun()
            except FileNotFoundError as e:
                st.error(f"找不到数据文件：{e}")
                st.stop()
            except Exception as e:
                st.error(f"导入失败：{e}")
                st.stop()
    else:
        ensure_schema()


# ── Helper: get filtered data as DataFrame ─────────────────────────
@st.cache_data(ttl=3600)
def load_plays_df(min_ms: int, exclude_skipped: bool, music_only: bool) -> pd.DataFrame:
    conn = get_db()
    df = load_plays(conn, min_ms=min_ms, exclude_skipped=exclude_skipped, music_only=music_only)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_all_plays_df() -> pd.DataFrame:
    """Unfiltered data for behavior analysis pages."""
    conn = get_db()
    df = load_plays(conn, min_ms=0, exclude_skipped=False, music_only=False)
    conn.close()
    return df


# ── Dashboard ───────────────────────────────────────────────────────
def dashboard():
    render_sidebar()
    ensure_data()

    min_ms = st.session_state.min_ms
    exclude_skipped = st.session_state.exclude_skipped
    music_only = st.session_state.music_only

    df = load_plays_df(min_ms, exclude_skipped, music_only)
    df_all = load_all_plays_df()

    total_plays = len(df)
    total_hours = df["ms_played"].sum() / 3_600_000
    total_tracks = df["track_id"].nunique()
    total_artists = df["artist_name"].dropna().nunique()
    total_albums = df["album_name"].dropna().nunique()
    total_days = df["ts_date"].nunique()
    avg_daily_hours = total_hours / total_days if total_days > 0 else 0
    skip_rate_all = df_all["skipped"].sum() / max(len(df_all), 1) * 100

    page_header("📊 总览仪表盘", description="全局播放数据概览")

    # ── KPI Cards ───────────────────────────────────────────────────────
    kpi_metrics = [
        {"label": "总播放次数", "value": f"{total_plays:,}"},
        {"label": "总时长", "value": f"{total_hours:,.0f} 小时"},
        {"label": "独特曲目", "value": f"{total_tracks:,}"},
        {"label": "独特艺人", "value": f"{total_artists:,}"},
        {"label": "日均听歌", "value": f"{avg_daily_hours:.1f} 小时"},
        {"label": "总跳过率", "value": f"{skip_rate_all:.1f}%"},
    ]
    kpi_row(kpi_metrics)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Monthly trend ──────────────────────────────────────────────────
    st.subheader("月度播放趋势")
    monthly = (
        df.groupby(["ts_year", "ts_month"])
        .agg(plays=("play_id", "count"), hours=("ms_played", lambda x: x.sum() / 3_600_000))
        .reset_index()
    )
    monthly["period"] = monthly["ts_year"].astype(str) + "-" + monthly["ts_month"].astype(str).str.zfill(2)
    monthly = monthly.sort_values("period")

    fig_trend = go.Figure()
    fig_trend.add_trace(
        go.Scatter(
            x=monthly["period"],
            y=monthly["plays"],
            name="播放次数",
            mode="lines+markers",
            line={"color": "#B8860B", "width": 2.5},
            marker={"size": 5, "color": "#B8860B"},
            fill="tozeroy",
            fillcolor="rgba(184,134,11,0.08)",
        )
    )
    fig_trend.add_trace(
        go.Scatter(
            x=monthly["period"],
            y=monthly["hours"],
            name="时长 (小时)",
            mode="lines+markers",
            line={"color": "#C45C3A", "width": 2.5},
            marker={"size": 5, "color": "#C45C3A"},
            yaxis="y2",
        )
    )
    fig_trend.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#8B7355", "size": 11},
        hovermode="x unified",
        hoverlabel={"bgcolor": "#FFFFFF", "font": {"color": "#2C2416"}, "bordercolor": "#D4A84B"},
        xaxis={"gridcolor": "rgba(139,115,85,0.08)"},
        yaxis={"title": "播放次数", "gridcolor": "rgba(139,115,85,0.08)"},
        yaxis2={"title": "小时", "overlaying": "y", "side": "right", "gridcolor": "rgba(139,115,85,0.04)"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "font": {"color": "#8B7355"}},
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    st.plotly_chart(fig_trend, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Three-column grid: Top 10 / Platform / DOW ──────────────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Top 10 曲目")
        top_tracks = (
            df.groupby(["track_name", "artist_name"])
            .size()
            .sort_values(ascending=False)
            .head(10)
            .reset_index(name="plays")
        )
        fig_top = px.bar(
            top_tracks,
            x="plays",
            y="track_name",
            orientation="h",
            hover_data=["artist_name"],
            labels={"track_name": "", "plays": "播放次数"},
            height=350,
            color_discrete_sequence=[COLORS[0]],
        )
        fig_top.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_top.update_yaxes(autorange="reversed")
        fig_top.update_traces(marker={"color": COLORS[0]})
        st.plotly_chart(fig_top, use_container_width=True)

    with col2:
        st.subheader("平台分布")
        platform_counts = df["platform"].value_counts().reset_index()
        platform_counts.columns = ["platform", "count"]
        fig_plat = px.pie(
            platform_counts,
            names="platform",
            values="count",
            height=350,
            color_discrete_sequence=COLORS,
        )
        fig_plat.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_plat.update_traces(textinfo="label+percent", textfont={"color": "#2C2416"})
        st.plotly_chart(fig_plat, use_container_width=True)

    with col3:
        st.subheader("一周各天听歌量")
        dow_names = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
        dow_counts = df["ts_dow"].value_counts().sort_index().reset_index()
        dow_counts.columns = ["dow", "count"]
        dow_counts["day"] = dow_counts["dow"].map(dow_names)

        fig_dow = px.bar(
            dow_counts,
            x="day",
            y="count",
            labels={"day": "", "count": "播放次数"},
            height=350,
            color_discrete_sequence=[COLORS[2]],
        )
        fig_dow.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_dow.update_traces(marker={"color": COLORS[2]})
        st.plotly_chart(fig_dow, use_container_width=True)

    # ── 回忆推荐 ────────────────────────────────────────────────────────
    if not df.empty:
        st.divider()
        st.subheader("🎲 回忆推荐")
        conn_rec = get_db()
        _f, _fp = base_filters(min_ms=min_ms, exclude_skipped=exclude_skipped, music_only=music_only)
        _w = f"WHERE {_f}" if _f else ""
        random_track = conn_rec.execute(
            f"""SELECT p.track_id, t.track_name, a.artist_name, al.album_name,
                       MAX(p.ts_date) as last_played, COUNT(*) as total_plays
                FROM plays p
                LEFT JOIN tracks t ON p.track_id = t.track_id
                LEFT JOIN artists a ON t.artist_id = a.artist_id
                LEFT JOIN albums al ON t.album_id = al.album_id
                {_w}
                GROUP BY p.track_id
                ORDER BY RANDOM() LIMIT 1""",
            _fp,
        ).fetchone()
        conn_rec.close()

        if random_track:
            album_name = random_track["album_name"]
            album_line = f"<div style=\"font-size:0.8rem;color:#8B7355;\">收录于《{album_name or '未知专辑'}》</div>" if album_name else ""
            st.markdown(
                f"""<div style="background:var(--bg-card);border-left:3px solid var(--gold);padding:1rem 1.25rem;border-radius:0 8px 8px 0;">
                <div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--gold);margin-bottom:0.4rem;">随机推荐一首你听过的歌</div>
                <div style="font-size:1.15rem;font-weight:700;color:#2C2416;">{random_track['track_name']}</div>
                <div style="font-size:0.85rem;color:#8B7355;">{random_track['artist_name']}</div>
                {album_line}
                <div style="font-size:0.7rem;color:#A0937D;margin-top:0.5rem;">最近播放: {random_track['last_played']} · 播放 {random_track['total_plays']} 次</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.divider()
    st.caption("提示：使用左侧边栏调整数据过滤条件、切换分析页面")


# ── Navigation ──────────────────────────────────────────────────────
pg = st.navigation(
    [
        st.Page(dashboard, title="总览仪表盘", icon="📊", default=True),
        st.Page("pages/02_timeline.py", title="时间线", icon="⏱"),
        st.Page("pages/03_leaderboard.py", title="排行榜", icon="🏆"),
        st.Page("pages/04_behavior.py", title="行为分析", icon="🔍"),
        st.Page("pages/05_wrapped.py", title="年度总结", icon="🎁"),
        st.Page("pages/06_artist_deep.py", title="艺人深潜", icon="🎤"),
        st.Page("pages/07_listening_hours.py", title="听歌时段", icon="🕐"),
        st.Page("pages/08_billboard.py", title="Billboard 周榜", icon="📈"),
        st.Page("pages/09_settings.py", title="设置", icon="⚙️"),
    ]
)
pg.run()

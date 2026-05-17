"""Billboard Hot 100 style weekly chart with configurable tracking week boundary."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import html as _html
from urllib.parse import quote as _url_quote
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from app.db import get_db, base_filters
from app.styles import inject_global_styles

st.set_page_config(page_title="Billboard 周榜", page_icon="📈", layout="wide")
inject_global_styles()


# ═══════════════════════════════════════════════════════════════════════════
# HTML Table Renderer (Vinyl Archive styled, with clickable <a> links)
# ═══════════════════════════════════════════════════════════════════════════
def _render_bb_table(headers, rows, link_cols=None, col_formats=None, height=None):
    """Render a Vinyl Archive styled HTML table with optional hyperlink columns.

    Args:
        headers: list of column header strings
        rows: list of lists. Each cell can be a plain string, or a (text, url) tuple for a hyperlink.
        link_cols: dict mapping column index -> static URL string, applied to ALL rows.
                   Only used when cells are plain strings (not tuples).
        col_formats: dict mapping column index -> CSS class suffix ('rank', 'num', 'text')
        height: optional max-height CSS value (e.g. "400px")
    """
    if link_cols is None:
        link_cols = {}
    if col_formats is None:
        col_formats = {}

    style = f' style="max-height:{height};overflow-y:auto;"' if height else ""
    html = f'<div class="bb-table-container"{style}><table class="bb-table"><thead><tr>'

    for i, h in enumerate(headers):
        fmt = col_formats.get(i, "text")
        html += f'<th class="bb-{fmt}">{_html.escape(str(h))}</th>'
    html += "</tr></thead><tbody>"

    for row in rows:
        html += "<tr>"
        for i, cell in enumerate(row):
            fmt = col_formats.get(i, "text")
            if isinstance(cell, tuple):
                text, url = cell
                html += f'<td class="bb-{fmt}"><a href="{url}" target="_self">{text}</a></td>'
            else:
                url = link_cols.get(i)
                if url:
                    html += f'<td class="bb-{fmt}"><a href="{url}" target="_self">{cell}</a></td>'
                else:
                    html += f'<td class="bb-{fmt}">{cell}</td>'
        html += "</tr>"
    html += "</tbody></table></div>"

    st.markdown(html, unsafe_allow_html=True)


def _bb_url(**params):
    """Build a properly URL-encoded query string for Billboard navigation."""
    return "?" + "&".join(f"{k}={_url_quote(str(v), safe='')}" for k, v in params.items())


def _render_record_table(df, link_col_map=None, drop_cols=None, col_formats=None, height=None):
    """Render a records DataFrame as an HTML table with per-row navigation links.

    Args:
        df: DataFrame to display
        link_col_map: dict {column_name: "track"|"artist"|"album"|"week"}
        drop_cols: list of column names to hide from display (but still use for URL building)
        col_formats: dict {column_index: css_class}
        height: optional max-height
    """
    if link_col_map is None:
        link_col_map = {}
    if drop_cols is None:
        drop_cols = []
    if col_formats is None:
        col_formats = {}

    display_cols = [c for c in df.columns if c not in drop_cols]
    headers = [str(c) for c in display_cols]
    rows = []

    for _, r in df.iterrows():
        row = []
        for ci, col in enumerate(display_cols):
            val = r[col]
            if pd.isna(val):
                cell = "-"
            elif isinstance(val, (float,)):
                cell = f"{int(val):,}" if val == int(val) else f"{val:.1f}"
            else:
                cell = _html.escape(str(val))

            lt = link_col_map.get(col)
            if lt == "track":
                url = _bb_url(bb_nav="track", bb_id=int(r['track_id']), bb_tab="🎵 单曲历史")
                cell = (cell, url)
            elif lt == "artist":
                url = _bb_url(bb_nav="artist", bb_name=str(r[col]), bb_tab="🎤 艺人榜单")
                cell = (cell, url)
            elif lt == "album":
                art = str(r.get("artist_name", "")) if "artist_name" in r.index else ""
                url = _bb_url(bb_nav="album", bb_name=str(r[col]), bb_art=art, bb_tab="💿 专辑榜单")
                cell = (cell, url)
            elif lt == "week":
                url = _bb_url(bb_nav="week", bb_date=str(r[col]), bb_tab="📋 周榜")
                cell = (cell, url)
            row.append(cell)
        rows.append(row)

    _render_bb_table(headers, rows, col_formats=col_formats, height=height)


# ── Session state defaults ────────────────────────────────────────────
min_ms = st.session_state.get("min_ms", 30000)
exclude_skipped = st.session_state.get("exclude_skipped", True)
music_only = st.session_state.get("music_only", True)
bb_week_start_dow = st.session_state.get("bb_week_start_dow", 4)  # Friday
bb_week_start_hour = st.session_state.get("bb_week_start_hour", 0)

# Cross-tab navigation
if "bb_active_tab" not in st.session_state:
    st.session_state.bb_active_tab = "📋 周榜"
if "bb_selected_track_id" not in st.session_state:
    st.session_state.bb_selected_track_id = None
if "bb_selected_artist_name" not in st.session_state:
    st.session_state.bb_selected_artist_name = None
if "bb_selected_album_name" not in st.session_state:
    st.session_state.bb_selected_album_name = None
if "bb_selected_week" not in st.session_state:
    st.session_state.bb_selected_week = None
if "_bb_selected_album_artist" not in st.session_state:
    st.session_state._bb_selected_album_artist = None

# Widget-internal: radio 控件绑定的 key（与 bb_active_tab 解耦，避免 widget-key 冲突）
if "_bb_tab_radio" not in st.session_state:
    st.session_state._bb_tab_radio = "📋 周榜"
if "_bb_pending_tab" not in st.session_state:
    st.session_state._bb_pending_tab = None

# ── 消费来自 HTML 表格 <a> 链接的 query param 导航 ─────────────────
_nav_type = st.query_params.get("bb_nav")
if _nav_type:
    if _nav_type == "track":
        try:
            st.session_state.bb_selected_track_id = int(st.query_params["bb_id"])
        except (ValueError, KeyError):
            pass
    elif _nav_type == "artist":
        st.session_state.bb_selected_artist_name = st.query_params.get("bb_name")
    elif _nav_type == "album":
        st.session_state.bb_selected_album_name = st.query_params.get("bb_name")
        st.session_state._bb_selected_album_artist = st.query_params.get("bb_art")
    elif _nav_type == "week":
        st.session_state.bb_selected_week = st.query_params.get("bb_date")
    # 目标 tab（来自 bb_tab 参数）
    _target_tab = st.query_params.get("bb_tab")
    if _target_tab:
        st.session_state._bb_pending_tab = _target_tab
    # 目标 sub-tab（周榜下的子 Tab）
    _target_subtab = st.query_params.get("bb_subtab")
    if _target_subtab is not None:
        try:
            st.session_state.bb_weekly_subtab = int(_target_subtab)
        except (ValueError, TypeError):
            pass
    st.query_params.clear()
    st.rerun()

if "bb_top_n" not in st.session_state:
    st.session_state.bb_top_n = 30
if "bb_weekly_subtab" not in st.session_state:
    st.session_state.bb_weekly_subtab = 0

# Album & Artist Top N (from settings, with fallback defaults)
bb_album_top_n = st.session_state.get("bb_album_top_n", 20)
bb_artist_top_n = st.session_state.get("bb_artist_top_n", 20)

# Tab 4/5 selectbox keys for programmatic index control
if "bb_artist_selector_idx" not in st.session_state:
    st.session_state.bb_artist_selector_idx = 0
if "bb_album_selector_idx" not in st.session_state:
    st.session_state.bb_album_selector_idx = 0

# Weekday labels
DOW_NAMES = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
DOW_SHORT = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


# ═══════════════════════════════════════════════════════════════════════
# Data loading (cached)
# ═══════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_billboard_raw(min_ms, exclude_skipped, music_only, week_start_dow, week_start_hour):
    """Load filtered plays and compute billboard_week with configurable boundary."""
    conn = get_db()
    _f, _fp = base_filters(
        min_ms=min_ms, exclude_skipped=exclude_skipped, music_only=music_only
    )
    _w = f"WHERE {_f}" if _f else ""
    df = pd.read_sql_query(
        f"""SELECT p.ts_date, p.ts_dow, p.ts_hour, p.ms_played, p.skipped, p.track_id,
                   t.track_name, a.artist_name, al.album_name
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN artists a ON t.artist_id = a.artist_id
            LEFT JOIN albums al ON t.album_id = al.album_id
            {_w}""",
        conn,
        params=_fp,
    )
    conn.close()

    # Billboard week: configurable boundary
    df["days_back"] = (df["ts_dow"] - week_start_dow) % 7
    mask_before = (df["ts_dow"] == week_start_dow) & (df["ts_hour"] < week_start_hour)
    df.loc[mask_before, "days_back"] = 7
    df["ts_date_dt"] = pd.to_datetime(df["ts_date"])
    df["billboard_week"] = (
        df["ts_date_dt"] - pd.to_timedelta(df["days_back"], unit="D")
    ).dt.date

    return df


@st.cache_data(ttl=3600)
def load_track_album_map():
    """Get all album names for each track_id (including track_albums junction)."""
    conn = get_db()
    rows = conn.execute(
        """SELECT t.track_id, al.album_name
           FROM tracks t
           JOIN albums al ON t.album_id = al.album_id
           UNION
           SELECT ta.track_id, al.album_name
           FROM track_albums ta
           JOIN albums al ON ta.album_id = al.album_id"""
    ).fetchall()
    conn.close()

    data = {}
    for tid, album in rows:
        data.setdefault(tid, []).append(album)

    # Build DataFrame: track_id → list of album names
    records = []
    for tid, albums in data.items():
        records.append({"track_id": tid, "album_list": sorted(set(albums))})
    return pd.DataFrame(records)


def compute_weekly_rankings(_df, top_n):
    """Aggregate per-week rankings with tiebreaker (play_count > total_ms)."""
    df = _df.copy()
    weekly = (
        df.groupby(["billboard_week", "track_id", "track_name", "artist_name", "album_name"])
        .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )

    # Tiebreaker: sort by play_count DESC, then total_ms DESC
    weekly = weekly.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    weekly["rank"] = weekly.groupby("billboard_week").cumcount() + 1
    weekly = weekly[weekly["rank"] <= top_n]

    return weekly


def compute_album_weekly_rankings(_df, top_n):
    """Aggregate per-week album rankings from ALL plays (not just charting tracks).

    Ranks albums by total play_count of all their songs during each week.
    Tiebreaker: total_ms (descending).
    """
    df = _df.copy()
    df = df.dropna(subset=["album_name"])
    weekly_album = (
        df.groupby(["billboard_week", "album_name", "artist_name"])
        .agg(
            play_count=("ms_played", "count"),
            total_ms=("ms_played", "sum"),
            tracks_count=("track_id", "nunique"),
        )
        .reset_index()
    )
    weekly_album = weekly_album.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    weekly_album["rank"] = weekly_album.groupby("billboard_week").cumcount() + 1
    weekly_album = weekly_album[weekly_album["rank"] <= top_n]
    return weekly_album


def compute_artist_weekly_rankings(_df, top_n):
    """Aggregate per-week artist rankings from ALL plays (not just charting tracks).

    Ranks artists by total play_count of all their songs during each week.
    Tiebreaker: total_ms (descending).
    """
    df = _df.copy()
    df = df.dropna(subset=["artist_name"])
    weekly_artist = (
        df.groupby(["billboard_week", "artist_name"])
        .agg(
            play_count=("ms_played", "count"),
            total_ms=("ms_played", "sum"),
            tracks_count=("track_id", "nunique"),
        )
        .reset_index()
    )
    weekly_artist = weekly_artist.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    weekly_artist["rank"] = weekly_artist.groupby("billboard_week").cumcount() + 1
    weekly_artist = weekly_artist[weekly_artist["rank"] <= top_n]
    return weekly_artist


def compute_power_scores(weekly, N):
    """Compute Power Score for each track — composite ranking metric.

    Power Score = Σ(weekly_base_points × play_intensity_weight)
                  + peak_bonus + top5_bonus + top10_bonus

    Base points are normalized to rank/N so scores are comparable
    regardless of chart size N.
    """
    tier1_count = int(N * 0.1)
    tier2_count = int(N * 0.2)

    # Week median plays (competition baseline)
    week_medians = weekly.groupby("billboard_week")["play_count"].median().to_dict()

    scores = []
    for (track_id, track_name, artist_name), group in weekly.groupby(
        ["track_id", "track_name", "artist_name"]
    ):
        peak = group["rank"].min()
        weeks_total = group["billboard_week"].nunique()
        weeks_top5 = int((group["rank"] <= 5).sum())
        weeks_top10 = int((group["rank"] <= 10).sum())
        weeks_at_no1 = int((group["rank"] == 1).sum())

        total = 0.0
        for _, row in group.iterrows():
            rank = row["rank"]
            plays = row["play_count"]
            median = week_medians.get(row["billboard_week"], 1)

            # 1. Base points (normalized by rank/N)
            r_norm = rank / N if N > 0 else 0
            if rank == 1:
                base = 200
            elif r_norm <= 0.1:
                base = int(200 * (0.75 - 2.5 * r_norm))
            elif r_norm <= 0.2:
                rank_in_tier = rank - tier1_count
                base = max(1, int(85 * (0.85 ** rank_in_tier)))
            else:
                start_val = int(85 * 0.85 ** (tier2_count - tier1_count))
                base = max(1, int(start_val * (1 - (r_norm - 0.2) / 0.8)))

            # 2. Play intensity weight: log₂ ratio to week median
            if median > 0 and plays > 0:
                weight = 1 + min(3.0, max(0.0, np.log2(plays / median)))
            else:
                weight = 1.0

            total += base * weight

        # 3. Bonuses
        peak_bonus = {1: 100, 2: 50, 3: 30}.get(peak, 0)
        top5_bonus = weeks_top5 * 20
        top10_bonus = weeks_top10 * 5

        power_score = round(total + peak_bonus + top5_bonus + top10_bonus)

        scores.append(
            {
                "track_id": track_id,
                "track_name": track_name,
                "artist_name": artist_name,
                "power_score": power_score,
                "peak_position": peak,
                "weeks_on_chart": weeks_total,
                "weeks_top5": weeks_top5,
                "weeks_top10": weeks_top10,
                "weeks_at_no1": weeks_at_no1,
            }
        )

    return pd.DataFrame(scores).sort_values("power_score", ascending=False).reset_index(drop=True)



def compute_album_power_scores(weekly_album, N):
    """Compute Power Score for each album — composite ranking metric."""
    tier1_count = int(N * 0.1)
    tier2_count = int(N * 0.2)

    week_medians = weekly_album.groupby("billboard_week")["play_count"].median().to_dict()

    scores = []
    for (album_name, artist_name), group in weekly_album.groupby(["album_name", "artist_name"]):
        peak = group["rank"].min()
        weeks_total = group["billboard_week"].nunique()
        weeks_top1 = int((group["rank"] == 1).sum())

        total = 0.0
        for _, row in group.iterrows():
            rank = row["rank"]
            plays = row["play_count"]
            median = week_medians.get(row["billboard_week"], 1)

            r_norm = rank / N if N > 0 else 0
            if rank == 1:
                base = 200
            elif r_norm <= 0.1:
                base = int(200 * (0.75 - 2.5 * r_norm))
            elif r_norm <= 0.2:
                rank_in_tier = rank - tier1_count
                base = max(1, int(85 * (0.85 ** rank_in_tier)))
            else:
                start_val = int(85 * 0.85 ** (tier2_count - tier1_count))
                base = max(1, int(start_val * (1 - (r_norm - 0.2) / 0.8)))

            if median > 0 and plays > 0:
                weight = 1 + min(3.0, max(0.0, np.log2(plays / median)))
            else:
                weight = 1.0

            total += base * weight

        peak_bonus = {1: 100, 2: 50, 3: 30}.get(peak, 0)
        top1_bonus = weeks_top1 * 20

        power_score = round(total + peak_bonus + top1_bonus)

        scores.append({
            "album_name": album_name,
            "artist_name": artist_name,
            "power_score": power_score,
            "peak_position": peak,
            "weeks_on_chart": weeks_total,
            "weeks_top1": weeks_top1,
        })

    return pd.DataFrame(scores).sort_values("power_score", ascending=False).reset_index(drop=True)


def compute_artist_power_scores(weekly_artist, N):
    """Compute Power Score for each artist — composite ranking metric."""
    tier1_count = int(N * 0.1)
    tier2_count = int(N * 0.2)

    week_medians = weekly_artist.groupby("billboard_week")["play_count"].median().to_dict()

    scores = []
    for artist_name, group in weekly_artist.groupby("artist_name"):
        peak = group["rank"].min()
        weeks_total = group["billboard_week"].nunique()
        weeks_top1 = int((group["rank"] == 1).sum())

        total = 0.0
        for _, row in group.iterrows():
            rank = row["rank"]
            plays = row["play_count"]
            median = week_medians.get(row["billboard_week"], 1)

            r_norm = rank / N if N > 0 else 0
            if rank == 1:
                base = 200
            elif r_norm <= 0.1:
                base = int(200 * (0.75 - 2.5 * r_norm))
            elif r_norm <= 0.2:
                rank_in_tier = rank - tier1_count
                base = max(1, int(85 * (0.85 ** rank_in_tier)))
            else:
                start_val = int(85 * 0.85 ** (tier2_count - tier1_count))
                base = max(1, int(start_val * (1 - (r_norm - 0.2) / 0.8)))

            if median > 0 and plays > 0:
                weight = 1 + min(3.0, max(0.0, np.log2(plays / median)))
            else:
                weight = 1.0

            total += base * weight

        peak_bonus = {1: 100, 2: 50, 3: 30}.get(peak, 0)
        top1_bonus = weeks_top1 * 20

        power_score = round(total + peak_bonus + top1_bonus)

        scores.append({
            "artist_name": artist_name,
            "power_score": power_score,
            "peak_position": peak,
            "weeks_on_chart": weeks_total,
            "weeks_top1": weeks_top1,
        })

    return pd.DataFrame(scores).sort_values("power_score", ascending=False).reset_index(drop=True)


def compute_records(weekly, track_summary, top_n):
    """Compute all-time Billboard records from weekly rankings.

    Returns a dict of record DataFrames and highlight values for the 榜单记录 tab.
    """
    records = {}

    # ── 1. Most simultaneous chart entries by artist (full chart) ──────
    artist_weekly = (
        weekly.groupby(["billboard_week", "artist_name"])
        .size()
        .reset_index(name="track_count")
    )
    if not artist_weekly.empty:
        best_full = artist_weekly.sort_values("track_count", ascending=False).iloc[0]
        records["artist_simul"] = {
            "artist": best_full["artist_name"],
            "week": best_full["billboard_week"],
            "count": int(best_full["track_count"]),
        }
        records["artist_simul_list"] = artist_weekly.sort_values(
            "track_count", ascending=False
        ).head(15)

    # ── 3. Most #1 songs by artist ─────────────────────────────────────
    no1_tracks = (
        weekly[weekly["rank"] == 1][["track_id", "artist_name"]]
        .drop_duplicates()
    )
    artist_no1 = (
        no1_tracks.groupby("artist_name")
        .size()
        .sort_values(ascending=False)
        .reset_index(name="冠单数")
    )
    records["artist_most_no1"] = artist_no1.head(15)

    # ── 4. Return to #1 ────────────────────────────────────────────────
    no1_weeks = (
        weekly[weekly["rank"] == 1][
            ["track_id", "track_name", "artist_name", "billboard_week"]
        ]
        .drop_duplicates()
        .sort_values(["track_id", "billboard_week"])
    )
    returns = []
    for tid, grp in no1_weeks.groupby("track_id"):
        if len(grp) >= 2:
            wks = grp["billboard_week"].tolist()
            for i in range(1, len(wks)):
                gap = (wks[i] - wks[i - 1]).days
                if gap > 8:  # More than one week apart → returned to #1
                    returns.append(
                        {
                            "track_id": tid,
                            "track_name": grp.iloc[i]["track_name"],
                            "artist_name": grp.iloc[i]["artist_name"],
                            "首次冠单": wks[i - 1],
                            "回冠日期": wks[i],
                            "间隔周数": gap // 7,
                        }
                    )
    records["return_to_no1"] = (
        pd.DataFrame(returns).sort_values("间隔周数", ascending=False)
        if returns
        else pd.DataFrame()
    )

    # ── 5. Debut at #1 ─────────────────────────────────────────────────
    debut = track_summary[
        (track_summary["peak_position"] == 1)
        & (track_summary["first_week"] == track_summary["first_peak_week"])
    ].copy()
    records["debut_no1"] = debut.sort_values("first_week")[
        ["track_id", "track_name", "artist_name", "first_week", "weeks_on_chart"]
    ]

    # ── 6. Longest charting songs ──────────────────────────────────────
    records["longest_charting"] = track_summary.sort_values(
        "weeks_on_chart", ascending=False
    ).head(20)[
        ["track_id", "track_name", "artist_name", "weeks_on_chart", "peak_position", "weeks_at_no1"]
    ]

    # ── 7. Longest charting without Top 10 ─────────────────────────────
    no_top10 = track_summary[track_summary["peak_position"] > 10].sort_values(
        "weeks_on_chart", ascending=False
    ).head(20)[
        ["track_id", "track_name", "artist_name", "weeks_on_chart", "peak_position"]
    ]
    records["longest_no_top10"] = no_top10

    # ── 8. Longest consecutive streak ─────────────────────────────────
    streaks = []
    for tid, grp in weekly.sort_values(["track_id", "billboard_week"]).groupby(
        "track_id"
    ):
        wks = grp["billboard_week"].tolist()
        max_run = 1
        cur_run = 1
        run_start = wks[0]
        run_end = wks[0]
        best_start = wks[0]
        best_end = wks[0]

        for i in range(1, len(wks)):
            if (wks[i] - wks[i - 1]).days <= 8:
                cur_run += 1
                run_end = wks[i]
            else:
                if cur_run > max_run:
                    max_run = cur_run
                    best_start = run_start
                    best_end = run_end
                cur_run = 1
                run_start = wks[i]
                run_end = wks[i]

        if cur_run > max_run:
            max_run = cur_run
            best_start = run_start
            best_end = run_end

        streaks.append(
            {
                "track_id": tid,
                "track_name": grp.iloc[0]["track_name"],
                "artist_name": grp.iloc[0]["artist_name"],
                "连续周数": max_run,
                "起始周": best_start,
                "结束周": best_end,
            }
        )
    records["longest_streak"] = (
        pd.DataFrame(streaks)
        .sort_values("连续周数", ascending=False)
        .head(20)
    )

    # ── 9. Biggest Jump / Drop ─────────────────────────────────────────
    changes = []
    for tid, grp in weekly.sort_values(["track_id", "billboard_week"]).groupby(
        "track_id"
    ):
        grp = grp.sort_values("billboard_week")
        rows = grp.to_dict("records")
        for i in range(1, len(rows)):
            prev, curr = rows[i - 1], rows[i]
            if (curr["billboard_week"] - prev["billboard_week"]).days <= 8:
                change = prev["rank"] - curr["rank"]  # positive = rise
                changes.append(
                    {
                        "track_id": tid,
                        "track_name": curr["track_name"],
                        "artist_name": curr["artist_name"],
                        "日期": curr["billboard_week"],
                        "上周排名": prev["rank"],
                        "本周排名": curr["rank"],
                        "变化": change,
                    }
                )
    if changes:
        ch_df = pd.DataFrame(changes)
        records["biggest_jump"] = ch_df.nlargest(15, "变化")
        records["biggest_drop"] = ch_df.nsmallest(15, "变化")
    else:
        records["biggest_jump"] = pd.DataFrame()
        records["biggest_drop"] = pd.DataFrame()

    # ── 10. Same album most simultaneous entries ───────────────────────
    album_weekly = (
        weekly.groupby(["billboard_week", "artist_name", "album_name"])
        .size()
        .reset_index(name="track_count")
    )
    if not album_weekly.empty:
        best_alb = album_weekly.sort_values("track_count", ascending=False).iloc[0]
        records["album_simul"] = {
            "album": best_alb["album_name"],
            "artist": best_alb["artist_name"],
            "week": best_alb["billboard_week"],
            "count": int(best_alb["track_count"]),
        }
        records["album_simul_list"] = album_weekly.sort_values(
            "track_count", ascending=False
        ).head(15)

    # ── 11. All-Time Greatest (Power Score) ──────────────────────────────
    power_df = compute_power_scores(weekly, top_n)
    records["all_time_greatest"] = power_df.head(20)[
        ["track_id", "track_name", "artist_name", "peak_position", "weeks_on_chart", "weeks_at_no1", "power_score"]
    ].rename(columns={"power_score": "综合评分"})

    # ── 12. Year-End #1 (per-year Power Score) ──────────────────────────
    wy = weekly.copy()
    wy["year"] = pd.to_datetime(wy["billboard_week"]).dt.year
    ye_results = []
    for year, year_df in wy.groupby("year"):
        year_power = compute_power_scores(year_df, top_n)
        if not year_power.empty:
            top = year_power.iloc[0]
            ye_results.append({
                "year": int(year),
                "track_id": top["track_id"],
                "track_name": top["track_name"],
                "artist_name": top["artist_name"],
                "peak": top["peak_position"],
                "weeks_on_chart": top["weeks_on_chart"],
            })
    records["year_end_no1"] = pd.DataFrame(ye_results).sort_values("year", ascending=False) if ye_results else pd.DataFrame()

    return records


# ── Load data ─────────────────────────────────────────────────────────
df_raw = load_billboard_raw(min_ms, exclude_skipped, music_only, bb_week_start_dow, bb_week_start_hour)
album_map = load_track_album_map()

# Detect config changes from Settings page → clear caches to force recomputation
if "_applied_bb_top_n" not in st.session_state:
    st.session_state._applied_bb_top_n = st.session_state.bb_top_n
if "_applied_bb_week_dow" not in st.session_state:
    st.session_state._applied_bb_week_dow = bb_week_start_dow
if "_applied_bb_week_hour" not in st.session_state:
    st.session_state._applied_bb_week_hour = bb_week_start_hour
if "_applied_bb_album_top_n" not in st.session_state:
    st.session_state._applied_bb_album_top_n = bb_album_top_n
if "_applied_bb_artist_top_n" not in st.session_state:
    st.session_state._applied_bb_artist_top_n = bb_artist_top_n

_config_changed = False
if st.session_state.bb_top_n != st.session_state._applied_bb_top_n:
    st.session_state._applied_bb_top_n = st.session_state.bb_top_n
    _config_changed = True
if bb_album_top_n != st.session_state._applied_bb_album_top_n:
    st.session_state._applied_bb_album_top_n = bb_album_top_n
    _config_changed = True
if bb_artist_top_n != st.session_state._applied_bb_artist_top_n:
    st.session_state._applied_bb_artist_top_n = bb_artist_top_n
    _config_changed = True
if bb_week_start_dow != st.session_state._applied_bb_week_dow:
    st.session_state._applied_bb_week_dow = bb_week_start_dow
    _config_changed = True
if bb_week_start_hour != st.session_state._applied_bb_week_hour:
    st.session_state._applied_bb_week_hour = bb_week_start_hour
    _config_changed = True
if _config_changed:
    st.cache_data.clear()
    st.rerun()

# ── Billboard-specific filters (sidebar) ─────────────────────────────
# Compute available years from all_weeks (before year filtering)
raw_years = sorted(df_raw["billboard_week"].apply(lambda x: x.year).unique())

with st.sidebar:
    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        '<div style="font-size:2rem;margin-bottom:0.25rem;">📈</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#2C2416;">Billboard 周榜</div>'
        f'<div style="font-size:0.68rem;color:#8B7355;margin-top:0.15rem;">最短 {min_ms // 1000}s · '
        f'跳过={"排除" if exclude_skipped else "包含"} · {"仅音乐" if music_only else "含播客"}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    st.subheader("榜单数据过滤")

    bb_year_range = st.select_slider(
        "年份范围",
        options=raw_years,
        value=(raw_years[0], raw_years[-1]),
    )

    st.divider()

    # Top N — controlled from Settings page
    st.caption(
        f"单曲 Top {st.session_state.bb_top_n} · "
        f"专辑 Top {bb_album_top_n} · "
        f"艺人 Top {bb_artist_top_n}（在「⚙️ 设置」中调整）"
    )

# Apply year-range post-load filter (min_ms/exclude_skipped already handled at SQL level)
df_raw = df_raw.copy()  # avoid mutating cached DataFrame
df_raw["_year"] = df_raw["billboard_week"].apply(lambda x: x.year)
df_filtered = df_raw[
    (df_raw["_year"] >= bb_year_range[0])
    & (df_raw["_year"] <= bb_year_range[1])
].copy()

# Weeks sorted DESC (newest first) for selectors; ASC for LW calculation
all_weeks_desc = sorted(df_filtered["billboard_week"].unique().tolist(), reverse=True)
all_weeks_asc = sorted(df_filtered["billboard_week"].unique().tolist())
all_weeks_str = [f"{w} ({DOW_SHORT[bb_week_start_dow]})" for w in all_weeks_desc]

st.caption(
    f"统计周期：每{DOW_NAMES[bb_week_start_dow]} {bb_week_start_hour:02d}:00 — "
    f"下{DOW_NAMES[bb_week_start_dow]} {bb_week_start_hour:02d}:00（北京时间）| "
    f"规则：播放次数相同按总收听时长排 | "
    f"共 {len(all_weeks_asc)} 周 · {len(df_filtered):,} 条过滤后记录"
)

# ═══════════════════════════════════════════════════════════════════════
# Compute rankings
# ═══════════════════════════════════════════════════════════════════════
top_n = st.session_state.bb_top_n
weekly = compute_weekly_rankings(df_filtered, top_n)
weekly_album = compute_album_weekly_rankings(df_filtered, bb_album_top_n)
weekly_artist = compute_artist_weekly_rankings(df_filtered, bb_artist_top_n)

# Build track-level summary (peak, weeks on chart, etc.)
track_summary = (
    weekly.groupby(["track_id", "track_name", "artist_name", "album_name"])
    .agg(
        peak_position=("rank", "min"),
        weeks_on_chart=("billboard_week", "nunique"),
        weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
        first_week=("billboard_week", "min"),
        last_week=("billboard_week", "max"),
        total_chart_plays=("play_count", "sum"),
    )
    .reset_index()
)

# Total plays per track (all-time, for single-track detail cards)
track_total_plays = (
    df_filtered.groupby("track_id")
    .agg(total_plays=("ms_played", "count"))
    .reset_index()
)
track_summary = track_summary.merge(track_total_plays, on="track_id", how="left")

# Weeks at #1 per track
weeks_at_no1 = (
    weekly[weekly["rank"] == 1]
    .groupby("track_id")
    .agg(weeks_at_no1=("billboard_week", "nunique"))
    .reset_index()
)
track_summary = track_summary.merge(weeks_at_no1, on="track_id", how="left")
track_summary["weeks_at_no1"] = track_summary["weeks_at_no1"].fillna(0).astype(int)

# First week at peak position
first_peak = weekly.merge(
    track_summary[["track_id", "peak_position"]], on="track_id"
)
first_peak = first_peak[first_peak["rank"] == first_peak["peak_position"]]
first_peak = first_peak.groupby("track_id")["billboard_week"].min().reset_index()
first_peak.columns = ["track_id", "first_peak_week"]
track_summary = track_summary.merge(first_peak, on="track_id", how="left")

# Add running peak weeks to weekly (cumulative count of weeks at all-time peak)
wp = weekly.merge(
    track_summary[["track_id", "peak_position"]], on="track_id", how="left"
)
wp = wp.sort_values(["track_id", "billboard_week"])
wp["at_peak"] = (wp["rank"] == wp["peak_position"]).astype(int)
wp["running_peak_wks"] = wp.groupby("track_id")["at_peak"].cumsum()
weekly = wp.drop(columns=["peak_position", "at_peak"])

# ── Pre-compute artist / album summary DataFrames (used by Tabs 3,5,7,8) ─
artist_summary = (
    weekly.groupby(["artist_name", "track_id", "track_name", "album_name"])
    .agg(
        peak_position=("rank", "min"),
        weeks_on_chart=("billboard_week", "nunique"),
        weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
        first_week=("billboard_week", "min"),
        last_week=("billboard_week", "max"),
        total_chart_plays=("play_count", "sum"),
    )
    .reset_index()
)

artist_track_counts = (
    artist_summary.groupby("artist_name")
    .agg(
        total_tracks=("track_id", "nunique"),
        best_peak=("peak_position", "min"),
        total_weeks=("weeks_on_chart", "sum"),
        avg_weeks=("weeks_on_chart", "mean"),
        top1=("peak_position", lambda x: (x == 1).sum()),
        top5=("peak_position", lambda x: (x <= 5).sum()),
        top10=("peak_position", lambda x: (x <= 10).sum()),
    )
    .reset_index()
    .sort_values("total_tracks", ascending=False)
)
artist_track_counts["best_peak_track"] = artist_track_counts["artist_name"].apply(
    lambda a: artist_summary[artist_summary["artist_name"] == a]
    .sort_values("peak_position")
    .iloc[0]["track_name"]
)

# Artist weeks at #1 (sum of all tracks' weeks at #1)
artist_weeks_no1 = (
    track_summary.groupby("artist_name")["weeks_at_no1"]
    .sum()
    .reset_index()
)
artist_track_counts = artist_track_counts.merge(artist_weeks_no1, on="artist_name", how="left")

# Album #1 metrics per artist (from weekly_album)
album_no1_artist = weekly_album[weekly_album["rank"] == 1].groupby("artist_name").agg(
    num_no1_albums=("album_name", "nunique"),
    album_no1_weeks=("billboard_week", "nunique"),
).reset_index()
artist_track_counts = artist_track_counts.merge(album_no1_artist, on="artist_name", how="left")
artist_track_counts["num_no1_albums"] = artist_track_counts["num_no1_albums"].fillna(0).astype(int)
artist_track_counts["album_no1_weeks"] = artist_track_counts["album_no1_weeks"].fillna(0).astype(int)

# Artist chart #1 weeks (from weekly_artist)
artist_no1_weeks = weekly_artist[weekly_artist["rank"] == 1].groupby("artist_name").agg(
    artist_chart_no1_weeks=("billboard_week", "nunique"),
).reset_index()
artist_track_counts = artist_track_counts.merge(artist_no1_weeks, on="artist_name", how="left")
artist_track_counts["artist_chart_no1_weeks"] = artist_track_counts["artist_chart_no1_weeks"].fillna(0).astype(int)

# Album expanded view (track → all its albums via album_map)
ts_for_album = track_summary.drop(columns=["album_name"])
track_albums_expanded = ts_for_album.merge(album_map, on="track_id", how="left")
track_albums_expanded["album_list"] = track_albums_expanded["album_list"].apply(
    lambda x: x if isinstance(x, list) else []
)
track_per_album = track_albums_expanded.explode("album_list")
track_per_album = track_per_album.dropna(subset=["album_list"])
track_per_album = track_per_album.rename(columns={"album_list": "album_name"})

album_track_counts = (
    track_per_album.groupby(["album_name", "artist_name"])
    .agg(
        total_tracks=("track_id", "nunique"),
        best_peak=("peak_position", "min"),
        total_weeks=("weeks_on_chart", "sum"),
        avg_weeks=("weeks_on_chart", "mean"),
        top1=("peak_position", lambda x: (x == 1).sum()),
        top5=("peak_position", lambda x: (x <= 5).sum()),
        top10=("peak_position", lambda x: (x <= 10).sum()),
    )
    .reset_index()
    .sort_values("total_tracks", ascending=False)
)
album_track_counts["best_peak_track"] = album_track_counts.apply(
    lambda r: track_per_album[
        (track_per_album["album_name"] == r["album_name"])
        & (track_per_album["artist_name"] == r["artist_name"])
    ]
    .sort_values("peak_position")
    .iloc[0]["track_name"],
    axis=1,
)

# Album weeks at #1 (sum of all tracks' weeks at #1 per album)
# track_per_album already has weeks_at_no1 from track_summary via ts_for_album
album_weeks_no1 = (
    track_per_album.groupby(["album_name", "artist_name"])["weeks_at_no1"]
    .sum()
    .reset_index()
)
album_track_counts = album_track_counts.merge(album_weeks_no1, on=["album_name", "artist_name"], how="left")

# Album #1 weeks (from weekly_album)
album_no1 = weekly_album[weekly_album["rank"] == 1].groupby(["album_name", "artist_name"]).agg(
    album_chart_no1_weeks=("billboard_week", "nunique"),
).reset_index()
album_track_counts = album_track_counts.merge(album_no1, on=["album_name", "artist_name"], how="left")
album_track_counts["album_chart_no1_weeks"] = album_track_counts["album_chart_no1_weeks"].fillna(0).astype(int)

# ── Compute Records ────────────────────────────────────────────────────
records = compute_records(weekly, track_summary, top_n)

# ── Tabs (radio + CSS styled as tabs for programmatic control) ────────
TAB_NAMES = [
    "📋 周榜", "👑 每周榜首", "🎵 单曲历史", "🎤 艺人榜单", "💿 专辑榜单",
    "⭐ 走势总榜", "🏆 歌曲总榜", "📊 艺人总榜", "📀 专辑总榜",
    "🏅 榜单记录",
]

# 消费来自 query param 导航的待处理 tab 切换请求
_pending = st.session_state.pop("_bb_pending_tab", None)
if _pending is not None and _pending in TAB_NAMES:
    st.session_state._bb_tab_radio = _pending
if "_bb_tab_radio" not in st.session_state:
    st.session_state._bb_tab_radio = TAB_NAMES[0]

st.markdown("""
<style>
/* ── Billboard Tab Bar ─────────────────────────────────────────────── */
div[data-testid="stRadio"]:has(input[value="📋 周榜"]) > div[role="radiogroup"] {
  display: flex !important;
  flex-direction: row !important;
  gap: 0.25rem !important;
  border-bottom: 1.5px solid rgba(184, 134, 11, 0.20) !important;
  margin-bottom: 1.75rem !important;
  padding-bottom: 0 !important;
  overflow-x: auto !important;
  flex-wrap: nowrap !important;
  -webkit-overflow-scrolling: touch;
}

div[data-testid="stRadio"]:has(input[value="📋 周榜"]) label {
  padding: 0.6rem 0.9rem !important;
  border-radius: 10px 10px 0 0 !important;
  color: #8B7355 !important;
  font-family: "Palatino", "Book Antiqua", serif !important;
  font-size: 0.82rem !important;
  font-weight: 500 !important;
  border-bottom: 2.5px solid transparent !important;
  margin-bottom: -1.5px !important;
  cursor: pointer !important;
  transition: all 0.2s ease !important;
  white-space: nowrap !important;
  background: transparent !important;
  letter-spacing: 0.01em;
}

div[data-testid="stRadio"]:has(input[value="📋 周榜"]) label:hover {
  color: #2C2416 !important;
  background: rgba(184, 134, 11, 0.06) !important;
  border-bottom-color: rgba(184, 134, 11, 0.25) !important;
}

div[data-testid="stRadio"]:has(input[value="📋 周榜"]) input[type="radio"] {
  display: none !important;
}

div[data-testid="stRadio"]:has(input[value="📋 周榜"]) label:has(input:checked) {
  color: #B8860B !important;
  font-weight: 600 !important;
  border-bottom: 2.5px solid #B8860B !important;
  background: linear-gradient(180deg, rgba(184,134,11,0.04) 0%, rgba(184,134,11,0.01) 100%) !important;
}

/* ── Billboard HTML Tables ─────────────────────────────────────────── */
.bb-table-container {
  border: 1px solid rgba(139, 115, 85, 0.12);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 1rem;
}
.bb-table {
  width: 100%;
  border-collapse: collapse;
  font-family: "Palatino", "Book Antiqua", serif;
  font-size: 0.82rem;
  color: #2C2416;
}
.bb-table thead {
  background: #F5EDDA;
  border-bottom: 2px solid rgba(184, 134, 11, 0.25);
}
.bb-table th {
  padding: 0.6rem 0.75rem;
  text-align: left;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #8B7355;
  font-weight: 600;
}
.bb-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid rgba(139, 115, 85, 0.06);
  background: #FFFFFF;
}
.bb-table tbody tr:hover td {
  background: #FDF8EF;
  transition: background 0.15s ease;
}
.bb-table a {
  color: #2C2416;
  text-decoration: none;
  border-bottom: 1px dotted rgba(184, 134, 11, 0.45);
  transition: all 0.15s ease;
}
.bb-table a:hover {
  color: #B8860B;
  border-bottom-color: #B8860B;
}
.bb-table .bb-rank { text-align: center; font-weight: 600; width: 3rem; }
.bb-table .bb-num { text-align: right; font-variant-numeric: tabular-nums; }
.bb-table .bb-num-wide { text-align: right; font-variant-numeric: tabular-nums; }
.bb-table .bb-text { text-align: left; }
</style>
""", unsafe_allow_html=True)

st.radio(
    "导航",
    options=TAB_NAMES,
    key="_bb_tab_radio",
    label_visibility="collapsed",
    horizontal=True,
)
# 将 radio 内部值同步到公开的 bb_active_tab
st.session_state.bb_active_tab = st.session_state._bb_tab_radio


# ═══════════════════════════════════════════════════════════════════════
# Tab 1: Weekly Chart
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.bb_active_tab == "📋 周榜":
    # ── Consume cross-tab week navigation ─────────────────────────────
    nav_week = st.session_state.get("bb_selected_week")
    if nav_week is not None:
        st.session_state.bb_selected_week = None
        from datetime import date
        try:
            target_week = date.fromisoformat(nav_week)
            if target_week in all_weeks_desc:
                st.session_state.bb_week_selector = all_weeks_desc.index(target_week)
        except (ValueError, TypeError):
            pass

    # Week selector — newest first, remembers last selection
    if "bb_week_selector" not in st.session_state:
        st.session_state.bb_week_selector = 0
    max_week_idx = len(all_weeks_desc) - 1
    if st.session_state.bb_week_selector > max_week_idx:
        st.session_state.bb_week_selector = max_week_idx

    selected_week_idx = st.selectbox(
        "选择周",
        options=range(len(all_weeks_desc)),
        format_func=lambda i: all_weeks_str[i],
        key="bb_week_selector",
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

            # Merge peak and weeks from track_summary
            week_df = week_df.merge(
                track_summary[["track_id", "peak_position", "weeks_on_chart"]],
                on="track_id",
                how="left",
            )

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
                    str(r["peak_position"]),
                    str(r["weeks_on_chart"]),
                    str(r["running_peak_wks"]),
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
            total_album_tracks = int(album_week_df["tracks_count"].sum())
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.metric("上榜专辑总播放次数", f"{total_album_plays:,}")
            with col_a2:
                st.metric("上榜专辑涉及曲目数", f"{total_album_tracks:,}")

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

            # ── Compute Peak/Wks for albums from all-time weekly_album ──
            album_alltime = (
                weekly_album.groupby(["album_name", "artist_name"])
                .agg(
                    peak_position=("rank", "min"),
                    weeks_on_chart=("billboard_week", "nunique"),
                )
                .reset_index()
            )
            album_week_df = album_week_df.merge(
                album_alltime, on=["album_name", "artist_name"], how="left"
            )

            # Total hours
            album_week_df["total_hours"] = (album_week_df["total_ms"] / 3_600_000).round(1)

            # ── Table ─────────────────────────────────────────────────────
            headers = ["#", "专辑", "艺人", "总播放次数", "入榜曲数", "总时长(小时)", "LW", "Peak", "Wks"]
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
                    str(r["tracks_count"]),
                    f"{r['total_hours']:.1f}",
                    str(r.get("LW", "-")),
                    str(int(r.get("peak_position", 0)) or "-"),
                    str(int(r.get("weeks_on_chart", 0)) or "-"),
                ])
            _render_bb_table(headers, rows,
                col_formats={0: "rank", 3: "num", 4: "num", 5: "num", 6: "num", 7: "num", 8: "num"})

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
            total_artist_tracks = int(artist_week_df["tracks_count"].sum())
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                st.metric("上榜艺人总播放次数", f"{total_artist_plays:,}")
            with col_a2:
                st.metric("上榜艺人涉及曲目数", f"{total_artist_tracks:,}")

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

            # ── Compute Peak/Wks for artists from all-time weekly_artist ──
            artist_alltime = (
                weekly_artist.groupby("artist_name")
                .agg(
                    peak_position=("rank", "min"),
                    weeks_on_chart=("billboard_week", "nunique"),
                )
                .reset_index()
            )
            artist_week_df = artist_week_df.merge(
                artist_alltime, on="artist_name", how="left"
            )

            # Total hours
            artist_week_df["total_hours"] = (artist_week_df["total_ms"] / 3_600_000).round(1)

            # ── Table ─────────────────────────────────────────────────────
            headers = ["#", "艺人", "总播放次数", "入榜曲数", "总时长(小时)", "LW", "Peak", "Wks"]
            rows = []
            for _, r in artist_week_df.iterrows():
                artist_url = _bb_url(bb_nav="artist", bb_name=str(r["artist_name"]), bb_tab="🎤 艺人榜单")
                rows.append([
                    str(r["rank"]),
                    (_html.escape(str(r["artist_name"])), artist_url),
                    f"{r['play_count']:,}",
                    str(r["tracks_count"]),
                    f"{r['total_hours']:.1f}",
                    str(r.get("LW", "-")),
                    str(int(r.get("peak_position", 0)) or "-"),
                    str(int(r.get("weeks_on_chart", 0)) or "-"),
                ])
            _render_bb_table(headers, rows,
                col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 5: "num", 6: "num", 7: "num"})

            if n_artists < bb_artist_top_n:
                st.caption(f"本周仅 {n_artists} 位艺人上榜（不足 Top {bb_artist_top_n}）")


# ═══════════════════════════════════════════════════════════════════════
# Tab 3: Track Chart History
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.bb_active_tab == "🎵 单曲历史":
    # Build track options sorted by peak DESC, weeks DESC
    track_options = track_summary.sort_values(
        ["peak_position", "weeks_on_chart"], ascending=[True, False]
    )

    # ── Search box ────────────────────────────────────────────────────
    search_term = st.text_input(
        "搜索曲目/艺人/专辑",
        placeholder="输入关键词筛选...",
        key="bb_track_search",
    )

    if search_term:
        term = search_term.lower()
        mask = (
            track_options["track_name"].str.lower().str.contains(term, na=False)
            | track_options["artist_name"].str.lower().str.contains(term, na=False)
            | track_options["album_name"].str.lower().str.contains(term, na=False)
        )
        filtered_options = track_options[mask].reset_index(drop=True)
    else:
        filtered_options = track_options.reset_index(drop=True)

    if filtered_options.empty:
        st.warning(f"没有匹配「{search_term}」的曲目")
    else:
        # Determine default index from session_state cross-tab nav
        default_idx = 0
        if st.session_state.bb_selected_track_id is not None:
            sel_id = st.session_state.bb_selected_track_id
            matches = filtered_options[filtered_options["track_id"] == sel_id]
            if not matches.empty:
                default_idx = int(matches.index[0])
                st.session_state.bb_selected_track_id = None
            else:
                # Track hidden by search filter — clear search and retry
                st.session_state.bb_track_search = ""
                st.rerun()

        track_labels = [
            f"{t['track_name']} — {t['artist_name']}  (Peak #{t['peak_position']}, {t['weeks_on_chart']}wks)"
            for _, t in filtered_options.iterrows()
        ]
        track_ids = filtered_options["track_id"].tolist()

        selected_track_idx = st.selectbox(
            "选择曲目",
            options=range(len(track_labels)),
            format_func=lambda i: track_labels[i],
            index=min(default_idx, len(track_labels) - 1),
        )
        selected_tid = track_ids[selected_track_idx]

        # Track history data
        track_hist = weekly[weekly["track_id"] == selected_tid].sort_values("billboard_week")
        ts_row = track_summary[track_summary["track_id"] == selected_tid].iloc[0]

        # ── Summary Cards ─────────────────────────────────────────────
        col1, col2, col3 = st.columns(3)
        peak_str = f"#{ts_row['peak_position']}"
        if ts_row["weeks_at_peak"] > 1:
            peak_str += f" ({ts_row['weeks_at_peak']}wks)"
        col1.metric("最高排名", peak_str)
        col2.metric("进榜周数", f"{ts_row['weeks_on_chart']} 周")
        col3.metric("首次入榜", str(ts_row["first_week"]))

        col4, col5, col6 = st.columns(3)
        first_peak_str = str(ts_row["first_peak_week"]) if pd.notna(ts_row["first_peak_week"]) else "—"
        col4.metric("首次 Peak 周", first_peak_str)
        col5.metric("总上榜播放", f"{int(ts_row['total_chart_plays']):,}")
        col6.metric("总播放次数", f"{int(ts_row['total_plays']):,}")

        st.divider()

        # ── History Table ─────────────────────────────────────────────
        st.subheader("榜单历史")

        track_hist_display = track_hist.copy()
        track_hist_display["prev_rank"] = track_hist_display["rank"].shift(1)
        changes = []
        for _, r in track_hist_display.iterrows():
            p = r["prev_rank"]
            cur = r["rank"]
            if pd.isna(p):
                changes.append("NEW")
            else:
                diff = int(p) - int(cur)
                if diff > 0:
                    changes.append(f"▲{diff}")
                elif diff < 0:
                    changes.append(f"▼{abs(diff)}")
                else:
                    changes.append("─")
        track_hist_display["Change"] = changes

        display_hist = track_hist_display[["billboard_week", "rank", "play_count", "Change"]].copy()
        display_hist.columns = ["周", "排名", "播放次数", "升降"]

        _th_headers = ["周", "排名", "播放次数", "升降"]
        _th_rows = []
        for _, _r in display_hist.iterrows():
            _th_rows.append([
                (_html.escape(str(_r["周"])), _bb_url(bb_nav="week", bb_date=_r['周'], bb_tab="📋 周榜")),
                str(_r["排名"]),
                f"{int(_r['播放次数']):,}",
                _html.escape(str(_r["升降"])),
            ])
        _render_bb_table(_th_headers, _th_rows, col_formats={1: "num", 2: "num"})

        # ── Rank Trend Chart (gapped) ─────────────────────────────────
        st.subheader("排名趋势")

        chart_data = track_hist[["billboard_week", "rank", "play_count"]].copy()
        chart_data["week_num"] = pd.to_datetime(chart_data["billboard_week"])

        x_vals = []
        y_vals = []
        texts = []
        for i, (_, row) in enumerate(chart_data.iterrows()):
            if i > 0:
                gap_days = (row["week_num"] - chart_data.iloc[i - 1]["week_num"]).days
                if gap_days > 9:
                    x_vals.append(None)
                    y_vals.append(None)
                    texts.append(None)
            x_vals.append(row["week_num"])
            y_vals.append(row["rank"])
            texts.append(f"#{row['rank']} · {row['play_count']}次")

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines+markers",
                name=filtered_options.iloc[selected_track_idx]["track_name"],
                line=dict(color="#B8860B", width=2),
                marker=dict(size=7, color="#B8860B"),
                text=texts,
                hovertemplate="%{text}<extra></extra>",
                connectgaps=False,
            )
        )

        fig.add_hline(
            y=top_n,
            line_dash="dash",
            line_color="gray",
            annotation_text=f"榜单边界 (Top {top_n})",
        )

        fig.add_hline(
            y=ts_row["peak_position"],
            line_dash="dot",
            line_color="#B8860B",
            annotation_text=f"Peak #{ts_row['peak_position']}",
        )

        fig.update_yaxes(autorange="reversed", title="排名", range=[top_n + 1, 1])
        fig.update_xaxes(title="周")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# Tab 4: Artist Billboard Summary
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.bb_active_tab == "🎤 艺人榜单":
    # ── Consume cross-tab artist navigation ──────────────────────────
    nav_artist = st.session_state.get("bb_selected_artist_name")
    if nav_artist is not None:
        st.session_state.bb_selected_artist_name = None
        st.session_state.bb_artist_search = ""
        all_names = artist_track_counts["artist_name"].tolist()
        if nav_artist in all_names:
            st.session_state.bb_artist_selector_idx = all_names.index(nav_artist)
        st.rerun()

    # Artist search
    artist_search = st.text_input(
        "搜索艺人",
        placeholder="输入艺人名筛选...",
        key="bb_artist_search",
    )

    if artist_search:
        term = artist_search.lower()
        mask = artist_track_counts["artist_name"].str.lower().str.contains(term, na=False)
        filtered_artists = artist_track_counts[mask].reset_index(drop=True)
    else:
        filtered_artists = artist_track_counts.reset_index(drop=True)

    # Artist selector
    artist_labels = [
        f"{r['artist_name']} ({int(r['total_tracks'])}首入榜)"
        for _, r in filtered_artists.iterrows()
    ]
    artist_names = filtered_artists["artist_name"].tolist()

    if not artist_labels:
        if artist_search:
            st.warning(f"没有匹配「{artist_search}」的艺人")
        else:
            st.warning("暂无数据")
    else:
        selected_artist_idx = st.selectbox(
            "选择艺人",
            options=range(len(artist_labels)),
            format_func=lambda i: artist_labels[i],
            key="bb_artist_selector_idx",
        )
        selected_artist = artist_names[selected_artist_idx]

        # ── Artist summary cards ──────────────────────────────────────
        art_row = artist_track_counts[artist_track_counts["artist_name"] == selected_artist].iloc[0]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("入榜曲数", f"{int(art_row['total_tracks'])} 首")
        col2.metric("最佳 Peak", f"#{int(art_row['best_peak'])}", delta=art_row["best_peak_track"][:30])
        col3.metric("总上榜周数", f"{int(art_row['total_weeks'])} 周")
        col4.metric("平均在榜", f"{art_row['avg_weeks']:.1f} 周")

        col1b, col2b, col3b, col4b = st.columns(4)
        col1b.metric("#1 曲数", f"{int(art_row['top1'])} 首")
        col2b.metric("Top 5 曲数", f"{int(art_row['top5'])} 首")
        col3b.metric("Top 10 曲数", f"{int(art_row['top10'])} 首")
        col4b.metric("#1周数", f"{int(art_row['weeks_at_no1'])} 周")

        st.divider()

        # ── Secondary sort selector ───────────────────────────────────
        peak_tiebreaker = st.radio(
            "Peak 相同时按",
            ["在榜周数", "Peak 周数"],
            horizontal=True,
            key="artist_tiebreaker",
        )

        # ── Charting tracks table ─────────────────────────────────────
        art_tracks = artist_summary[artist_summary["artist_name"] == selected_artist].copy()
        # Merge weeks_at_no1 and first_peak_week from track_summary
        art_tracks = art_tracks.merge(
            track_summary[["track_id", "weeks_at_no1", "first_peak_week"]],
            on="track_id", how="left"
        )
        art_tracks["weeks_at_no1"] = art_tracks["weeks_at_no1"].fillna(0).astype(int)
        art_tracks["first_peak_week"] = art_tracks["first_peak_week"].astype(str)
        # Three-level sort: Peak → chosen tiebreaker → the other
        if peak_tiebreaker == "在榜周数":
            art_tracks = art_tracks.sort_values(
                ["peak_position", "weeks_on_chart", "weeks_at_peak"], ascending=[True, False, False]
            )
        else:
            art_tracks = art_tracks.sort_values(
                ["peak_position", "weeks_at_peak", "weeks_on_chart"], ascending=[True, False, False]
            )
        art_tracks = art_tracks.reset_index(drop=True)
        art_tracks.index = art_tracks.index + 1

        display_art = art_tracks[
            ["track_name", "peak_position", "weeks_on_chart", "weeks_at_peak",
             "first_week", "first_peak_week", "last_week", "total_chart_plays"]
        ].copy()
        display_art["first_week"] = display_art["first_week"].astype(str)
        display_art["last_week"] = display_art["last_week"].astype(str)
        display_art.columns = ["曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "首次Peak周", "最近上榜", "总播放"]
        display_art.index.name = "#"

        st.subheader(f"{selected_artist} · 入榜曲目")

        _art_headers = ["#", "曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "首次Peak周", "最近上榜", "总播放"]
        _art_rows = []
        for _, r in art_tracks.iterrows():
            track_url = _bb_url(bb_nav="track", bb_id=r['track_id'], bb_tab="🎵 单曲历史")
            _art_rows.append([
                str(r.name),
                (_html.escape(str(r["track_name"])), track_url),
                str(r["peak_position"]),
                str(r["weeks_on_chart"]),
                str(r["weeks_at_peak"]),
                (_html.escape(str(r["first_week"])), _bb_url(bb_nav="week", bb_date=r['first_week'], bb_tab="📋 周榜")),
                (_html.escape(str(r["first_peak_week"])), _bb_url(bb_nav="week", bb_date=r['first_peak_week'], bb_tab="📋 周榜")),
                (_html.escape(str(r["last_week"])), _bb_url(bb_nav="week", bb_date=r['last_week'], bb_tab="📋 周榜")),
                f"{r['total_chart_plays']:,}",
            ])
        _render_bb_table(_art_headers, _art_rows,
            col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 8: "num"})

        # ── Artist weekly charting history ──────────────────────────────
        st.divider()
        st.subheader(f"{selected_artist} · 每周入榜概况")

        artist_weekly = weekly[weekly["artist_name"] == selected_artist]
        aw_summary = (
            artist_weekly.groupby("billboard_week")
            .agg(
                tracks_on_chart=("track_id", "nunique"),
                total_plays=("play_count", "sum"),
            )
            .reset_index()
        )

        # Get #1 track names and IDs per week
        artist_no1_grp = (
            artist_weekly[artist_weekly["rank"] == 1]
            .groupby("billboard_week")
        )
        artist_no1 = (
            artist_no1_grp["track_name"]
            .apply(lambda x: "、".join(dict.fromkeys(x)))
            .reset_index()
        )
        artist_no1.columns = ["billboard_week", "no1_track_names"]
        artist_no1_ids = (
            artist_no1_grp.agg(no1_track_id=("track_id", "first"), no1_count=("track_id", "nunique"))
            .reset_index()
        )
        artist_no1 = artist_no1.merge(artist_no1_ids, on="billboard_week", how="left")
        aw_summary = aw_summary.merge(artist_no1, on="billboard_week", how="left")
        aw_summary["no1_track_names"] = aw_summary["no1_track_names"].fillna("—")
        aw_summary = aw_summary.sort_values("billboard_week", ascending=False)

        if aw_summary.empty:
            st.caption("该艺人在当前过滤条件下无上榜记录")
        else:
            _aw_headers = ["周", "上榜曲数", "当周总播放", "#1 曲目"]
            _aw_rows = []
            for _, r in aw_summary.iterrows():
                week_url = _bb_url(bb_nav="week", bb_date=r['billboard_week'], bb_tab="📋 周榜")
                no1_names = str(r["no1_track_names"])
                if pd.notna(r.get("no1_count")) and int(r["no1_count"]) == 1 and pd.notna(r.get("no1_track_id")):
                    no1_url = _bb_url(bb_nav="track", bb_id=int(r['no1_track_id']), bb_tab="🎵 单曲历史")
                    _no1_cell = (_html.escape(no1_names), no1_url)
                else:
                    _no1_cell = _html.escape(no1_names)
                _aw_rows.append([
                    (str(r["billboard_week"]), week_url),
                    str(r["tracks_on_chart"]),
                    f"{r['total_plays']:,}",
                    _no1_cell,
                ])
            _render_bb_table(_aw_headers, _aw_rows,
                col_formats={1: "num", 2: "num"})
        # ── Artist Weekly Chart History (艺人周榜) ────────────────────────
        st.divider()
        st.subheader(f"{selected_artist} · 艺人周榜历史")

        artist_wk_history = weekly_artist[weekly_artist["artist_name"] == selected_artist].copy()
        if artist_wk_history.empty:
            st.info("该艺人在当前过滤条件下无周榜记录")
        else:
            artist_wk_history = artist_wk_history.sort_values("billboard_week", ascending=False)
            artist_wk_history["total_hours"] = artist_wk_history["total_ms"] / 3_600_000

            _awh_headers = ["周", "排名", "总播放次数", "入榜曲数", "总时长(小时)"]
            _awh_rows = []
            for _, _r in artist_wk_history.iterrows():
                _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜", bb_subtab="2")
                _awh_rows.append([
                    (_html.escape(str(_r["billboard_week"])), _week_url),
                    str(_r["rank"]),
                    f"{_r['play_count']:,}",
                    str(_r["tracks_count"]),
                    f"{_r['total_hours']:.1f}",
                ])
            _render_bb_table(_awh_headers, _awh_rows,
                col_formats={1: "rank", 2: "num", 3: "num", 4: "num"}, height="500px")

            # Rank trend chart
            st.subheader("艺人周榜排名趋势")
            trend_data = artist_wk_history.sort_values("billboard_week", ascending=True).copy()
            peak_row = trend_data.loc[trend_data["rank"].idxmin()]
            fig_art_trend = go.Figure()
            fig_art_trend.add_trace(
                go.Scatter(
                    x=trend_data["billboard_week"],
                    y=trend_data["rank"],
                    mode="lines+markers",
                    name="排名",
                    line={"color": "#B8860B", "width": 2},
                    marker={"size": 6, "color": "#B8860B"},
                )
            )
            fig_art_trend.add_trace(
                go.Scatter(
                    x=[peak_row["billboard_week"]],
                    y=[peak_row["rank"]],
                    mode="markers+text",
                    name=f"Peak #{int(peak_row['rank'])}",
                    text=[f"#{int(peak_row['rank'])}"],
                    textposition="top center",
                    marker={"size": 14, "color": "#C45C3A", "symbol": "star"},
                )
            )
            fig_art_trend.update_layout(
                yaxis={"autorange": "reversed", "title": "排名", "gridcolor": "rgba(139,115,85,0.08)"},
                xaxis={"title": "", "gridcolor": "rgba(139,115,85,0.08)"},
                height=400,
                hovermode="x unified",
                showlegend=False,
            )
            st.plotly_chart(fig_art_trend, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# Tab: Power Score Ranking (走势总榜)
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.bb_active_tab == "⭐ 走势总榜":
    st.subheader("⭐ 走势总榜")
    st.caption(
        "综合衡量最高排名、在榜周数、竞争强度（播放量相对当周大盘）、"
        "稳定性及冠军奖励的复合评分"
    )

    # Compute all three power score DataFrames
    power_df = compute_power_scores(weekly, top_n)
    album_power_df = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_df = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    ptabs = st.tabs(["🎵 歌曲走势", "💿 专辑走势", "🎤 艺人走势"])

    # ═════════════════════════════════════════════════════════════════════
    # Sub-tab 0: Track Power Scores
    # ═════════════════════════════════════════════════════════════════════
    with ptabs[0]:
        if power_df.empty:
            st.info("暂无足够数据计算歌曲走势评分")
        else:
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            with col_p1:
                st.metric("上榜歌曲数", f"{len(power_df):,}")
            with col_p2:
                top10_avg = power_df.head(10)["power_score"].mean()
                st.metric("Top 10 平均分", f"{top10_avg:,.0f}")
            with col_p3:
                st.metric("最高 Power Score", f"{power_df.iloc[0]['power_score']:,}")
            with col_p4:
                no1_count = int((power_df["peak_position"] == 1).sum())
                st.metric("冠单数量", f"{no1_count}")

            st.divider()

            _ps_headers = ["#", "曲目", "艺人", "Power", "Peak", "Wks", "Top5", "#1 Wks"]
            _ps_rows = []
            for _i, _r in power_df.iterrows():
                _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
                _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
                _ps_rows.append([
                    str(_i + 1),
                    (_html.escape(str(_r["track_name"])), _track_url),
                    (_html.escape(str(_r["artist_name"])), _artist_url),
                    f"{_r['power_score']:,.0f}",
                    str(_r["peak_position"]),
                    str(_r["weeks_on_chart"]),
                    str(_r["weeks_top5"]),
                    str(_r["weeks_at_no1"]),
                ])
            _render_bb_table(_ps_headers, _ps_rows,
                col_formats={0: "rank", 3: "num", 4: "num", 5: "num", 6: "num", 7: "num"})

            st.divider()

            with st.expander("📐 Power Score 计算方式"):
                st.markdown(f"""
                **核心公式**：

                **1. 周基础分**（归一化到 rank ÷ Top N，保证调整 Top N 后分数可比）：
                - #1 = 200 分
                - Top 10%（排名 ≤ {int(top_n * 0.1)}）：200 × (0.75 − 2.5 × rank/N)，约 150 → 85 分
                - 10%−20%（排名 ≤ {int(top_n * 0.2)}）：85 × 0.85^(排名−{int(top_n * 0.1)})，约 72 → 40 分
                - 20%−100%：线性衰减至 1 分

                **2. 播放量加权**：，范围 1−4
                - 播放量 = 中位数 → ×1.0；2× 中位数 → ×2.0；8×+ 中位数 → ×4.0（上限）

                **3. 奖励**：Peak #1 +100 · #2 +50 · #3 +30 | 每在前五一周 +20 | 每在前十一周 +5

                **总分 {top_n} 首歌曲**，已从高到低排序
                """)

            st.subheader("Top 20 Power Score")
            top20 = power_df.head(20).iloc[::-1]
            fig_ps = px.bar(
                top20,
                x="power_score",
                y="track_name",
                orientation="h",
                hover_data=["artist_name", "peak_position", "weeks_on_chart"],
                labels={
                    "power_score": "Power Score",
                    "track_name": "",
                    "artist_name": "艺人",
                },
                height=600,
            )
            fig_ps.update_yaxes(autorange="reversed")
            fig_ps.update_traces(
                marker_color=top20["power_score"].apply(
                    lambda x: f"rgba(184,134,11,{max(0.3, min(1, x / top20['power_score'].max()))})"
                )
            )
            st.plotly_chart(fig_ps, use_container_width=True)

    # ═════════════════════════════════════════════════════════════════════
    # Sub-tab 1: Album Power Scores
    # ═════════════════════════════════════════════════════════════════════
    with ptabs[1]:
        if album_power_df.empty:
            st.info("暂无足够数据计算专辑走势评分")
        else:
            col_a1, col_a2, col_a3, col_a4 = st.columns(4)
            with col_a1:
                st.metric("上榜专辑数", f"{len(album_power_df):,}")
            with col_a2:
                a_top10_avg = album_power_df.head(10)["power_score"].mean()
                st.metric("Top 10 平均分", f"{a_top10_avg:,.0f}")
            with col_a3:
                st.metric("最高 Power Score", f"{album_power_df.iloc[0]['power_score']:,}")
            with col_a4:
                a_no1_count = int((album_power_df["peak_position"] == 1).sum())
                st.metric("冠军专辑数", f"{a_no1_count}")

            st.divider()

            _aps_headers = ["#", "专辑", "艺人", "Power", "Peak", "Wks", "#1 Wks"]
            _aps_rows = []
            for _i, _r in album_power_df.iterrows():
                _album_url = _bb_url(bb_nav="album", bb_name=str(_r['album_name']), bb_art=str(_r['artist_name']), bb_tab="💿 专辑榜单")
                _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
                _aps_rows.append([
                    str(_i + 1),
                    (_html.escape(str(_r["album_name"])), _album_url),
                    (_html.escape(str(_r["artist_name"])), _artist_url),
                    f"{_r['power_score']:,.0f}",
                    str(_r["peak_position"]),
                    str(_r["weeks_on_chart"]),
                    str(_r["weeks_top1"]),
                ])
            _render_bb_table(_aps_headers, _aps_rows,
                col_formats={0: "rank", 3: "num", 4: "num", 5: "num", 6: "num"})

            st.divider()

            st.subheader("Top 20 专辑 Power Score")
            top20_alb = album_power_df.head(20).iloc[::-1]
            fig_aps = px.bar(
                top20_alb,
                x="power_score",
                y="album_name",
                orientation="h",
                hover_data=["artist_name", "peak_position", "weeks_on_chart"],
                labels={"power_score": "Power Score", "album_name": "", "artist_name": "艺人"},
                height=600,
            )
            fig_aps.update_yaxes(autorange="reversed")
            fig_aps.update_traces(
                marker_color=top20_alb["power_score"].apply(
                    lambda x: f"rgba(184,134,11,{max(0.3, min(1, x / top20_alb['power_score'].max()))})"
                )
            )
            st.plotly_chart(fig_aps, use_container_width=True)

    # ═════════════════════════════════════════════════════════════════════
    # Sub-tab 2: Artist Power Scores
    # ═════════════════════════════════════════════════════════════════════
    with ptabs[2]:
        if artist_power_df.empty:
            st.info("暂无足够数据计算艺人走势评分")
        else:
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            with col_r1:
                st.metric("上榜艺人总数", f"{len(artist_power_df):,}")
            with col_r2:
                r_top10_avg = artist_power_df.head(10)["power_score"].mean()
                st.metric("Top 10 平均分", f"{r_top10_avg:,.0f}")
            with col_r3:
                st.metric("最高 Power Score", f"{artist_power_df.iloc[0]['power_score']:,}")
            with col_r4:
                r_no1_count = int((artist_power_df["peak_position"] == 1).sum())
                st.metric("冠军艺人人数", f"{r_no1_count}")

            st.divider()

            _rps_headers = ["#", "艺人", "Power", "Peak", "Wks", "#1 Wks"]
            _rps_rows = []
            for _i, _r in artist_power_df.iterrows():
                _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
                _rps_rows.append([
                    str(_i + 1),
                    (_html.escape(str(_r["artist_name"])), _artist_url),
                    f"{_r['power_score']:,.0f}",
                    str(_r["peak_position"]),
                    str(_r["weeks_on_chart"]),
                    str(_r["weeks_top1"]),
                ])
            _render_bb_table(_rps_headers, _rps_rows,
                col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 5: "num"})

            st.divider()

            st.subheader("Top 20 艺人 Power Score")
            top20_art = artist_power_df.head(20).iloc[::-1]
            fig_rps = px.bar(
                top20_art,
                x="power_score",
                y="artist_name",
                orientation="h",
                hover_data=["peak_position", "weeks_on_chart"],
                labels={"power_score": "Power Score", "artist_name": ""},
                height=600,
            )
            fig_rps.update_yaxes(autorange="reversed")
            fig_rps.update_traces(
                marker_color=top20_art["power_score"].apply(
                    lambda x: f"rgba(184,134,11,{max(0.3, min(1, x / top20_art['power_score'].max()))})"
                )
            )
            st.plotly_chart(fig_rps, use_container_width=True)


if st.session_state.bb_active_tab == "🏆 歌曲总榜":
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


# ═══════════════════════════════════════════════════════════════════════
# Tab 5: Album Billboard Summary
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.bb_active_tab == "💿 专辑榜单":
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

        # ── Album summary cards ───────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("入榜曲数", f"{int(selected_album_row['total_tracks'])} 首")
        col2.metric(
            "最佳 Peak",
            f"#{int(selected_album_row['best_peak'])}",
            delta=selected_album_row["best_peak_track"][:30],
        )
        col3.metric("总上榜周数", f"{int(selected_album_row['total_weeks'])} 周")
        col4.metric("平均在榜", f"{selected_album_row['avg_weeks']:.1f} 周")

        col1b, col2b, col3b, col4b = st.columns(4)
        col1b.metric("#1 曲数", f"{int(selected_album_row['top1'])} 首")
        col2b.metric("Top 5 曲数", f"{int(selected_album_row['top5'])} 首")
        col3b.metric("Top 10 曲数", f"{int(selected_album_row['top10'])} 首")
        col4b.metric("#1周数", f"{int(selected_album_row['weeks_at_no1'])} 周")

        st.divider()

        # ── Secondary sort selector ───────────────────────────────────
        album_tiebreaker = st.radio(
            "Peak 相同时按",
            ["在榜周数", "Peak 周数"],
            horizontal=True,
            key="album_tiebreaker",
        )

        # ── Charting tracks table ─────────────────────────────────────
        alb_tracks = track_per_album[
            (track_per_album["album_name"] == selected_album)
            & (track_per_album["artist_name"] == selected_album_artist)
        ].copy()

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

        display_alb = alb_tracks[
            ["track_name", "peak_position", "weeks_on_chart", "weeks_at_peak",
             "first_week", "first_peak_week", "last_week", "total_chart_plays"]
        ].copy()
        display_alb["first_peak_week"] = display_alb["first_peak_week"].astype(str)
        display_alb["first_week"] = display_alb["first_week"].astype(str)
        display_alb["last_week"] = display_alb["last_week"].astype(str)
        display_alb.columns = ["曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "首次Peak周", "最近上榜", "总播放"]
        display_alb.index.name = "#"

        st.subheader(f"《{selected_album}》 · 入榜曲目")

        _alb_t_headers = ["#", "曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "首次Peak周", "最近上榜", "总播放"]
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
            ])
        _render_bb_table(_alb_t_headers, _alb_t_rows,
            col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 8: "num"})

        # ── Album weekly charting history ───────────────────────────────
        st.divider()
        st.subheader(f"《{selected_album}》· 每周入榜概况")

        alb_track_ids = set(alb_tracks["track_id"].tolist())
        album_weekly = weekly[weekly["track_id"].isin(alb_track_ids)]
        alw_summary = (
            album_weekly.groupby("billboard_week")
            .agg(
                tracks_on_chart=("track_id", "nunique"),
                total_plays=("play_count", "sum"),
            )
            .reset_index()
        )

        # Get #1 track names and IDs per week
        album_no1_grp = (
            album_weekly[album_weekly["rank"] == 1]
            .groupby("billboard_week")
        )
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
        alw_summary = alw_summary.merge(album_no1, on="billboard_week", how="left")
        alw_summary["no1_track_names"] = alw_summary["no1_track_names"].fillna("—")
        alw_summary = alw_summary.sort_values("billboard_week", ascending=False)

        if alw_summary.empty:
            st.caption("该专辑在当前过滤条件下无上榜记录")
        else:
            _alw_headers = ["周", "上榜曲数", "当周总播放", "#1 曲目"]
            _alw_rows = []
            for _, _r in alw_summary.iterrows():
                _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜")
                no1_names = str(_r["no1_track_names"])
                if pd.notna(_r.get("no1_count")) and int(_r["no1_count"]) == 1 and pd.notna(_r.get("no1_track_id")):
                    no1_url = _bb_url(bb_nav="track", bb_id=int(_r['no1_track_id']), bb_tab="🎵 单曲历史")
                    _no1_cell = (_html.escape(no1_names), no1_url)
                else:
                    _no1_cell = _html.escape(no1_names)
                _alw_rows.append([
                    (str(_r["billboard_week"]), _week_url),
                    str(_r["tracks_on_chart"]),
                    f"{_r['total_plays']:,}",
                    _no1_cell,
                ])
            _render_bb_table(_alw_headers, _alw_rows,
                col_formats={1: "num", 2: "num"})
        # ── Album Weekly Chart History (专辑周榜) ────────────────────────
        st.divider()
        st.subheader(f"《{selected_album}》· 专辑周榜历史")

        album_wk_history = weekly_album[(weekly_album["album_name"] == selected_album) & (weekly_album["artist_name"] == selected_album_artist)].copy()
        if album_wk_history.empty:
            st.info("该专辑在当前过滤条件下无周榜记录")
        else:
            album_wk_history = album_wk_history.sort_values("billboard_week", ascending=False)
            album_wk_history["total_hours"] = album_wk_history["total_ms"] / 3_600_000

            _alwh_headers = ["周", "排名", "总播放次数", "入榜曲数", "总时长(小时)"]
            _alwh_rows = []
            for _, _r in album_wk_history.iterrows():
                _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜", bb_subtab="1")
                _alwh_rows.append([
                    (_html.escape(str(_r["billboard_week"])), _week_url),
                    str(_r["rank"]),
                    f"{_r['play_count']:,}",
                    str(_r["tracks_count"]),
                    f"{_r['total_hours']:.1f}",
                ])
            _render_bb_table(_alwh_headers, _alwh_rows,
                col_formats={1: "rank", 2: "num", 3: "num", 4: "num"}, height="500px")

            # Rank trend chart
            st.subheader("专辑周榜排名趋势")
            trend_data2 = album_wk_history.sort_values("billboard_week", ascending=True).copy()
            peak_row2 = trend_data2.loc[trend_data2["rank"].idxmin()]
            fig_alb_trend = go.Figure()
            fig_alb_trend.add_trace(
                go.Scatter(
                    x=trend_data2["billboard_week"],
                    y=trend_data2["rank"],
                    mode="lines+markers",
                    name="排名",
                    line={"color": "#B8860B", "width": 2},
                    marker={"size": 6, "color": "#B8860B"},
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
            fig_alb_trend.update_layout(
                yaxis={"autorange": "reversed", "title": "排名", "gridcolor": "rgba(139,115,85,0.08)"},
                xaxis={"title": "", "gridcolor": "rgba(139,115,85,0.08)"},
                height=400,
                hovermode="x unified",
                showlegend=False,
            )
            st.plotly_chart(fig_alb_trend, use_container_width=True)




# ═══════════════════════════════════════════════════════════════════════
# Tab 2: Number Ones History
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.bb_active_tab == "👑 每周榜首":
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

    # Compute longest consecutive #1 streak
    def _longest_streak(track_hist):
        weeks = sorted(track_hist["billboard_week"].unique())
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

    # ── Summary Cards ─────────────────────────────────────────────────
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

    # ── Weekly #1 Table ────────────────────────────────────────────────
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

    # ── Weekly #1 Album Table ──────────────────────────────────────────
    st.divider()
    st.subheader("每周冠军专辑")

    number_one_albums = weekly_album[weekly_album["rank"] == 1].copy()
    number_one_albums = number_one_albums.sort_values("billboard_week", ascending=False)
    # Compute running peak wks for albums
    number_one_albums = number_one_albums.sort_values(["album_name", "artist_name", "billboard_week"])
    number_one_albums["album_pk_wks"] = number_one_albums.groupby(["album_name", "artist_name"]).cumcount() + 1

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

    # ── Weekly #1 Artist Table ─────────────────────────────────────────
    st.divider()
    st.subheader("每周冠军艺人")

    number_one_artists = weekly_artist[weekly_artist["rank"] == 1].copy()
    number_one_artists = number_one_artists.sort_values(["artist_name", "billboard_week"])
    number_one_artists["artist_pk_wks"] = number_one_artists.groupby("artist_name").cumcount() + 1

    _no1_artist_headers = ["周", "冠军艺人", "总播放次数", "入榜曲数", "Pk Wks"]
    _no1_artist_rows = []
    for _, _r in number_one_artists.sort_values("billboard_week", ascending=False).iterrows():
        _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
        _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜")
        _no1_artist_rows.append([
            (_html.escape(str(_r["billboard_week"])), _week_url),
            (_html.escape(str(_r["artist_name"])), _artist_url),
            f"{_r['play_count']:,}",
            str(_r["tracks_count"]),
            str(_r["artist_pk_wks"]),
        ])
    _render_bb_table(_no1_artist_headers, _no1_artist_rows,
        col_formats={2: "num", 3: "num", 4: "num"}, height="600px")

    st.divider()
    st.subheader("冠单周数排行")

    # Merge Pk Wks and first peak week from track_summary
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

    # ── Chart ─────────────────────────────────────────────────────────
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

    # ── Album #1 Weeks Chart ──────────────────────────────────────────
    st.divider()
    st.subheader("专辑冠军周数 Top 15")

    album_weeks_at_one = (
        weekly_album[weekly_album["rank"] == 1]
        .groupby(["album_name", "artist_name"])
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
        .sort_values("weeks_at_no1", ascending=False)
    )
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

    # ── Artist #1 Weeks Chart ─────────────────────────────────────────
    st.divider()
    st.subheader("艺人冠军周数 Top 15")

    artist_weeks_at_one = (
        weekly_artist[weekly_artist["rank"] == 1]
        .groupby("artist_name")
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
        .sort_values("weeks_at_no1", ascending=False)
    )
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

    # ── Annual unique #1 songs ────────────────────────────────────────
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

    # ── Debut at #1 (空冠歌曲) ─────────────────────────────────────────
    st.divider()
    st.subheader("空冠歌曲（首次上榜即 #1）")

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
    debut_no1.columns = ["track_id", "曲目", "艺人", "首次上榜周", "在榜周数", "冠单周数"]

    if debut_no1.empty:
        st.info("暂无空冠歌曲")
    else:
        st.metric("空冠歌曲数", f"{len(debut_no1)} 首")
        _db_headers = ["曲目", "艺人", "首次上榜周", "在榜周数", "冠单周数"]
        _db_rows = []
        for _, _r in debut_no1.iterrows():
            _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['艺人']), bb_tab="🎤 艺人榜单")
            _week_url = _bb_url(bb_nav="week", bb_date=str(_r['首次上榜周']), bb_tab="📋 周榜")
            _db_rows.append([
                (_html.escape(str(_r["曲目"])), _track_url),
                (_html.escape(str(_r["艺人"])), _artist_url),
                (_html.escape(str(_r["首次上榜周"])), _week_url),
                str(_r["在榜周数"]),
                str(_r["冠单周数"]),
            ])
        _render_bb_table(_db_headers, _db_rows,
            col_formats={3: "num", 4: "num"})

    # ── Debut at #1 Albums (空冠专辑) ─────────────────────────────────
    st.divider()
    st.subheader("空冠专辑（首次上榜即 #1）")

    album_first_appear = (
        weekly_album.sort_values("billboard_week")
        .groupby(["album_name", "artist_name"])
        .first()
        .reset_index()
    )
    album_debut_no1 = album_first_appear[album_first_appear["rank"] == 1][
        ["album_name", "artist_name", "billboard_week"]
    ].copy()
    # Merge weeks on chart and #1 weeks from weekly_album
    album_chart_info = (
        weekly_album.groupby(["album_name", "artist_name"])
        .agg(weeks_on_chart=("billboard_week", "nunique"), weeks_at_no1=("rank", lambda x: (x == 1).sum()))
        .reset_index()
    )
    album_debut_no1 = album_debut_no1.merge(album_chart_info, on=["album_name", "artist_name"], how="left")
    album_debut_no1 = album_debut_no1.sort_values("billboard_week", ascending=False)
    album_debut_no1["billboard_week"] = album_debut_no1["billboard_week"].astype(str)

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

    # ── Double Debut #1 (双空冠) ──────────────────────────────────────
    st.divider()
    st.subheader("双空冠（同周歌曲+专辑同时空冠）")

    if not debut_no1.empty and not album_debut_no1.empty:
        track_debut = debut_no1[["曲目", "艺人", "首次上榜周"]].copy()
        track_debut.columns = ["debut_track", "debut_artist", "debut_week"]
        album_d = album_debut_no1[["album_name", "artist_name", "billboard_week"]].copy()
        album_d.columns = ["debut_album", "debut_artist", "debut_week"]
        double_debut = track_debut.merge(album_d, on=["debut_artist", "debut_week"], how="inner")
        double_debut = double_debut.sort_values("debut_week", ascending=False)

        if double_debut.empty:
            st.info("暂无同时实现歌曲和专辑双空冠的艺人")
        else:
            st.metric("双空冠次数", f"{len(double_debut)} 次")
            _dd_headers = ["周", "艺人", "空冠歌曲", "空冠专辑"]
            _dd_rows = []
            for _, _r in double_debut.iterrows():
                _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['debut_artist']), bb_tab="🎤 艺人榜单")
                _week_url = _bb_url(bb_nav="week", bb_date=str(_r['debut_week']), bb_tab="📋 周榜")
                _dd_rows.append([
                    (_html.escape(str(_r["debut_week"])), _week_url),
                    (_html.escape(str(_r["debut_artist"])), _artist_url),
                    _html.escape(str(_r["debut_track"])),
                    _html.escape(str(_r["debut_album"])),
                ])
            _render_bb_table(_dd_headers, _dd_rows)
    else:
        st.info("暂无同时实现歌曲和专辑双空冠的艺人")

    # ── Weekly total plays ranking (榜单大盘) ────────────────────────────
    st.divider()
    st.subheader("周总播放次数排名（大盘）")

    week_total_plays = (
        weekly.groupby("billboard_week")
        .agg(
            total_plays=("play_count", "sum"),
            tracks_count=("track_id", "nunique"),
        )
        .reset_index()
    )
    # Find #1 song for each week
    week_no1 = weekly[weekly["rank"] == 1][
        ["billboard_week", "track_id", "track_name", "artist_name", "play_count"]
    ].copy()
    week_no1.columns = ["billboard_week", "no1_track_id", "no1_track", "no1_track_artist", "no1_track_plays"]
    week_total_plays = week_total_plays.merge(week_no1, on="billboard_week", how="left")
    # Find #1 album for each week
    week_album_no1 = weekly_album[weekly_album["rank"] == 1][
        ["billboard_week", "album_name", "artist_name", "play_count"]
    ].copy()
    week_album_no1.columns = ["billboard_week", "no1_album", "no1_album_artist", "no1_album_plays"]
    week_total_plays = week_total_plays.merge(week_album_no1, on="billboard_week", how="left")
    # Find #1 artist for each week
    week_artist_no1 = weekly_artist[weekly_artist["rank"] == 1][
        ["billboard_week", "artist_name", "play_count"]
    ].copy()
    week_artist_no1.columns = ["billboard_week", "no1_chart_artist", "no1_chart_artist_plays"]
    week_total_plays = week_total_plays.merge(week_artist_no1, on="billboard_week", how="left")
    week_total_plays = week_total_plays.sort_values("total_plays", ascending=False)
    week_total_plays.index = week_total_plays.index + 1
    week_total_plays["billboard_week"] = week_total_plays["billboard_week"].astype(str)

    _wtp_headers = ["#", "周", "总播放次数", "#1 曲目", "#1 曲目播放次数", "#1 专辑", "#1 专辑播放次数", "#1 艺人", "#1 艺人播放次数"]
    _wtp_rows = []
    for _i, _r in week_total_plays.iterrows():
        _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜")
        # Track #1 cell
        if pd.notna(_r["no1_track_id"]):
            _no1_track_url = _bb_url(bb_nav="track", bb_id=int(_r['no1_track_id']), bb_tab="🎵 单曲历史")
            _no1_track_cell = (_html.escape(str(_r["no1_track"])), _no1_track_url)
        else:
            _no1_track_cell = "—"
        # Album #1 cell
        if pd.notna(_r.get("no1_album")):
            _no1_album_url = _bb_url(bb_nav="album", bb_name=str(_r['no1_album']), bb_art=str(_r.get('no1_album_artist', '')), bb_tab="💿 专辑榜单")
            _no1_album_cell = (_html.escape(str(_r["no1_album"])), _no1_album_url)
        else:
            _no1_album_cell = "—"
        # Artist #1 cell
        if pd.notna(_r.get("no1_chart_artist")):
            _no1_artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['no1_chart_artist']), bb_tab="🎤 艺人榜单")
            _no1_artist_cell = (_html.escape(str(_r["no1_chart_artist"])), _no1_artist_url)
        else:
            _no1_artist_cell = "—"
        _wtp_rows.append([
            str(_r.name),
            (_html.escape(str(_r["billboard_week"])), _week_url),
            f"{_r['total_plays']:,}",
            _no1_track_cell,
            f"{_r['no1_track_plays']:,.0f}" if pd.notna(_r.get("no1_track_plays")) else "—",
            _no1_album_cell,
            f"{_r['no1_album_plays']:,.0f}" if pd.notna(_r.get("no1_album_plays")) else "—",
            _no1_artist_cell,
            f"{_r['no1_chart_artist_plays']:,.0f}" if pd.notna(_r.get("no1_chart_artist_plays")) else "—",
        ])
    _render_bb_table(_wtp_headers, _wtp_rows,
        col_formats={0: "rank", 2: "num", 4: "num", 6: "num", 8: "num"}, height="500px")


# ═══════════════════════════════════════════════════════════════════════
# Tab 7: Artist Overall Ranking
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.bb_active_tab == "📊 艺人总榜":
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


# ═══════════════════════════════════════════════════════════════════════
# Tab 8: Album Overall Ranking
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.bb_active_tab == "📀 专辑总榜":
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


# ═══════════════════════════════════════════════════════════════════════
# Tab 10: Billboard Records & Milestones
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.bb_active_tab == "🏅 榜单记录":
    st.subheader("🏅 榜单历史记录")

    # ── Highlight Cards ─────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.75rem;text-transform:uppercase;letter-spacing:0.1em;color:#8B7355;margin-bottom:0.5rem;">'
        '里程碑纪录</div>',
        unsafe_allow_html=True,
    )

    highlight_cards = []

    # Card 1: Artist domination record (full chart)
    if "artist_simul" in records:
        dom_best = records["artist_simul"]
        highlight_cards.append({
            "emoji": "👑",
            "value": f"全榜 {dom_best['count']} 首",
            "label": "艺人霸榜纪录",
            "detail": f"{dom_best['artist']} · {dom_best['week']}",
        })

    # Card 2: Longest charting
    if "longest_charting" in records and len(records["longest_charting"]) > 0:
        lc = records["longest_charting"].iloc[0]
        highlight_cards.append({
            "emoji": "⏳",
            "value": f"{int(lc['weeks_on_chart'])} 周",
            "label": "最長在榜歌曲",
            "detail": f"{lc['track_name']} — {lc['artist_name']}",
        })

    # Card 3: Biggest jump
    if "biggest_jump" in records and len(records["biggest_jump"]) > 0:
        bj = records["biggest_jump"].iloc[0]
        highlight_cards.append({
            "emoji": "🚀",
            "value": f"#{int(bj['上周排名'])} → #{int(bj['本周排名'])}",
            "label": "最大排名跃升",
            "detail": f"{bj['track_name']} — {bj['artist_name']}",
        })

    # Card 4: Most #1s artist
    if "artist_most_no1" in records and len(records["artist_most_no1"]) > 0:
        an1 = records["artist_most_no1"].iloc[0]
        highlight_cards.append({
            "emoji": "🏆",
            "value": f"{int(an1['冠单数'])} 首冠单",
            "label": "最多冠单艺人",
            "detail": an1["artist_name"],
        })

    if highlight_cards:
        cols = st.columns(len(highlight_cards))
        for i, card in enumerate(highlight_cards):
            with cols[i]:
                st.markdown(
                    f"""
                    <div style="background:#FFFFFF;border-left:3px solid #B8860B;border-radius:12px;
                                padding:1rem 1.2rem;box-shadow:0 1px 3px rgba(139,69,19,0.08);">
                        <div style="font-size:1.6rem;margin-bottom:0.3rem;">{card['emoji']}</div>
                        <div style="font-size:1.2rem;font-weight:700;color:#B8860B;font-family:Georgia,serif;">
                            {card['value']}</div>
                        <div style="font-size:0.7rem;color:#8B7355;text-transform:uppercase;letter-spacing:0.06em;
                                    margin-top:0.2rem;">{card['label']}</div>
                        <div style="font-size:0.78rem;color:#2C2416;margin-top:0.3rem;line-height:1.3;">
                            {card['detail']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Section 1: 霸榜记录 (Domination) ─────────────────────────────────
    st.subheader("👑 艺人霸榜记录")
    st.caption("单周同一艺人在全榜占据的席位数纪录")

    if "artist_simul" in records:
        rec = records["artist_simul"]
        st.markdown(
            f"**最高纪录：{rec['artist']}** 在 {rec['week']} 周 "
            f"同时有 **{rec['count']}** 首歌曲在榜"
        )
    if "artist_simul_list" in records and len(records["artist_simul_list"]) > 0:
        _render_record_table(records["artist_simul_list"], link_col_map={"billboard_week": "week", "artist_name": "artist"})
    else:
        st.info("暂无数据")

    st.divider()

    # ── Section 2: 冠单记录 ──────────────────────────────────────────────
    st.subheader("👑 冠单里程碑")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**最多冠单艺人**")
        if "artist_most_no1" in records and len(records["artist_most_no1"]) > 0:
            _render_record_table(records["artist_most_no1"], link_col_map={"artist_name": "artist"})
        else:
            st.info("暂无数据")

    with col_b:
        st.markdown("**空降冠军歌曲**")
        if "debut_no1" in records and len(records["debut_no1"]) > 0:
            _render_record_table(records["debut_no1"], link_col_map={"track_name": "track", "artist_name": "artist", "first_week": "week"}, drop_cols=["track_id"])
            st.caption(f"共 {len(records['debut_no1'])} 首歌曲首周即登顶")
        else:
            st.info("暂无空降冠军歌曲")

    st.markdown("**回冠歌曲（跌出 #1 后再度登顶）**")
    if "return_to_no1" in records and len(records["return_to_no1"]) > 0:
        _render_record_table(records["return_to_no1"], link_col_map={"track_name": "track", "artist_name": "artist", "首次冠单": "week", "回冠日期": "week"}, drop_cols=["track_id"])
        st.caption(f"共 {len(records['return_to_no1'])} 次回冠记录")
    else:
        st.info("暂无回冠记录")

    st.divider()

    # ── Section 3: 在榜耐力 ──────────────────────────────────────────────
    st.subheader("⏳ 在榜耐力记录")

    long_tabs = st.tabs(["最長在榜 Top 20", "未进 Top 10 遗珠", "最长连续在榜"])
    with long_tabs[0]:
        if "longest_charting" in records and len(records["longest_charting"]) > 0:
            _render_record_table(records["longest_charting"], link_col_map={"track_name": "track", "artist_name": "artist"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")
    with long_tabs[1]:
        if "longest_no_top10" in records and len(records["longest_no_top10"]) > 0:
            _render_record_table(records["longest_no_top10"], link_col_map={"track_name": "track", "artist_name": "artist"}, drop_cols=["track_id"])
            st.caption("这些歌曲虽从未进入前 10，但长期保持在榜——真正的 '慢热型' 选手")
        else:
            st.info("暂无数据")
    with long_tabs[2]:
        if "longest_streak" in records and len(records["longest_streak"]) > 0:
            _render_record_table(records["longest_streak"], link_col_map={"track_name": "track", "artist_name": "artist", "起始周": "week", "结束周": "week"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")

    st.divider()

    # ── Section 4: 排名跃升 ──────────────────────────────────────────────
    st.subheader("📈 排名跃升记录")

    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("**单周最大跃升 Top 15**")
        if "biggest_jump" in records and len(records["biggest_jump"]) > 0:
            _bj_df = records["biggest_jump"].rename(columns={"变化": "上升位数"})
            _render_record_table(_bj_df, link_col_map={"track_name": "track", "artist_name": "artist", "日期": "week"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")

    with col_d:
        st.markdown("**单周最大跌幅 Top 15**")
        if "biggest_drop" in records and len(records["biggest_drop"]) > 0:
            _bd_df = records["biggest_drop"].rename(columns={"变化": "下跌位数"})
            _render_record_table(_bd_df, link_col_map={"track_name": "track", "artist_name": "artist", "日期": "week"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")

    st.divider()

    # ── Section 5: 专辑霸榜 ──────────────────────────────────────────────
    st.subheader("💿 专辑霸榜记录")
    st.caption("同一专辑在单周最多歌曲同时入榜")

    if "album_simul" in records:
        rec = records["album_simul"]
        st.markdown(
            f"**最高纪录：《{rec['album']}》** — {rec['artist']}，"
            f"{rec['week']} 周同时有 **{rec['count']}** 首歌曲在榜"
        )
    if "album_simul_list" in records and len(records["album_simul_list"]) > 0:
        _render_record_table(records["album_simul_list"], link_col_map={"billboard_week": "week", "album_name": "album", "artist_name": "artist"})

    st.divider()

    # ── Section 6: 历史总榜 ──────────────────────────────────────────────
    st.subheader("📜 历史总榜")

    alltime_tabs = st.tabs(["All-Time Greatest Top 20", "年度代表歌曲"])
    with alltime_tabs[0]:
        if "all_time_greatest" in records and len(records["all_time_greatest"]) > 0:
            st.caption("基于 Power Score 综合评分：Σ(每周归一化排名得分 × 播放强度权重) + Peak/冠单奖励")
            _render_record_table(records["all_time_greatest"], link_col_map={"track_name": "track", "artist_name": "artist"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")
    with alltime_tabs[1]:
        if "year_end_no1" in records and len(records["year_end_no1"]) > 0:
            st.caption("各年度 Power Score 最高的年度代表歌曲")
            _render_record_table(records["year_end_no1"], link_col_map={"track_name": "track", "artist_name": "artist"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")


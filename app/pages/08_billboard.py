"""Billboard Hot 100 style weekly chart with configurable tracking week boundary."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from app.db import get_db, base_filters
from app.styles import inject_global_styles

st.set_page_config(page_title="Billboard 周榜", page_icon="📈", layout="wide")
inject_global_styles()

# ── Session state defaults ────────────────────────────────────────────
min_ms = st.session_state.get("min_ms", 30000)
exclude_skipped = st.session_state.get("exclude_skipped", True)
music_only = st.session_state.get("music_only", True)
bb_week_start_dow = st.session_state.get("bb_week_start_dow", 4)  # Friday
bb_week_start_hour = st.session_state.get("bb_week_start_hour", 12)

# Cross-tab track selection
if "bb_selected_track_id" not in st.session_state:
    st.session_state.bb_selected_track_id = None

if "bb_top_n" not in st.session_state:
    st.session_state.bb_top_n = 50

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

_config_changed = False
if st.session_state.bb_top_n != st.session_state._applied_bb_top_n:
    st.session_state._applied_bb_top_n = st.session_state.bb_top_n
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
        '<div style="font-size:1.05rem;font-weight:700;color:#F0F0F5;">Billboard 周榜</div>'
        f'<div style="font-size:0.68rem;color:#8888A0;margin-top:0.15rem;">最短 {min_ms // 1000}s · '
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
    st.caption(f"上榜数量：Top {st.session_state.bb_top_n}（在「⚙️ 设置」中调整）")

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
artist_track_counts["weeks_at_no1"] = artist_track_counts["weeks_at_no1"].fillna(0).astype(int)

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
album_track_counts["weeks_at_no1"] = album_track_counts["weeks_at_no1"].fillna(0).astype(int)

# ── Tabs ──────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab_power, tab6, tab7, tab8 = st.tabs([
    "📋 周榜", "👑 冠单历史", "🎵 单曲历史", "🎤 艺人榜单", "💿 专辑榜单",
    "⭐ 歌曲走势总榜", "🏆 歌曲总榜", "📊 艺人总榜", "📀 专辑总榜",
])


# ═══════════════════════════════════════════════════════════════════════
# Tab 1: Weekly Chart
# ═══════════════════════════════════════════════════════════════════════
with tab1:
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

    week_df = weekly[weekly["billboard_week"] == selected_week].copy()
    week_df = week_df.sort_values("rank")

    if week_df.empty:
        st.warning(f"本周无数据（{selected_week}）")
    else:
        n_tracks = len(week_df)
        st.subheader(f"{selected_week} 周榜 · Top {n_tracks}")

        total_week_plays = int(week_df["play_count"].sum())
        st.metric("本周入榜歌曲总播放次数", f"{total_week_plays:,}")

        # ── Top 10 Highlight Cards ────────────────────────────────────
        top10 = week_df.head(10)
        medals = {0: "🥇", 1: "🥈", 2: "🥉"}
        rows = [st.columns(5), st.columns(5)]
        for i, (_, row) in enumerate(top10.iterrows()):
            r = i // 5
            c = i % 5
            medal = medals.get(i, "")
            track_short = row["track_name"][:25] if len(row["track_name"]) > 25 else row["track_name"]
            artist_short = row["artist_name"][:20] if len(row["artist_name"]) > 20 else row["artist_name"]
            with rows[r][c]:
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
                lw_values.append("—")
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

        # running_peak_wks is already in week_df (inherited from weekly)

        # ── Hot 100 Table ─────────────────────────────────────────────
        display_df = week_df[["rank", "track_name", "artist_name", "play_count", "LW", "peak_position", "weeks_on_chart", "running_peak_wks"]].copy()
        display_df.columns = ["#", "曲目", "艺人", "播放次数", "LW", "Peak", "Wks", "Pk Wks"]
        display_df = display_df.set_index("#")

        st.dataframe(
            display_df,
            column_config={
                "曲目": st.column_config.TextColumn("曲目", width="medium"),
                "艺人": st.column_config.TextColumn("艺人", width="medium"),
                "播放次数": st.column_config.NumberColumn("播放次数", format="%d"),
                "LW": st.column_config.TextColumn("LW", width="small"),
                "Peak": st.column_config.NumberColumn("Peak", format="%d"),
                "Wks": st.column_config.NumberColumn("Wks", format="%d"),
                "Pk Wks": st.column_config.NumberColumn("Pk Wks", format="%d"),
            },
            use_container_width=True,
        )

        if n_tracks < top_n:
            st.caption(f"本周仅 {n_tracks} 首曲目上榜（不足 Top {top_n}）")


# ═══════════════════════════════════════════════════════════════════════
# Tab 3: Track Chart History
# ═══════════════════════════════════════════════════════════════════════
with tab3:
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
            # Reset after use
            st.session_state.bb_selected_track_id = None

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
        display_hist = display_hist.set_index("周")

        st.dataframe(
            display_hist,
            column_config={
                "排名": st.column_config.NumberColumn("排名", format="%d"),
                "播放次数": st.column_config.NumberColumn("播放次数", format="%d"),
                "升降": st.column_config.TextColumn("升降", width="small"),
            },
            use_container_width=True,
        )

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
                line=dict(color="#1DB954", width=2),
                marker=dict(size=7, color="#1DB954"),
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
            line_color="#1DB954",
            annotation_text=f"Peak #{ts_row['peak_position']}",
        )

        fig.update_yaxes(autorange="reversed", title="排名", range=[top_n + 1, 1])
        fig.update_xaxes(title="周")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# Tab 4: Artist Billboard Summary
# ═══════════════════════════════════════════════════════════════════════
with tab4:
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
            index=0,
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
        col4b.metric("冠军周数", f"{int(art_row['weeks_at_no1'])} 周")

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
        if peak_tiebreaker == "在榜周数":
            art_tracks = art_tracks.sort_values(
                ["peak_position", "weeks_on_chart"], ascending=[True, False]
            )
        else:
            art_tracks = art_tracks.sort_values(
                ["peak_position", "weeks_at_peak"], ascending=[True, False]
            )
        art_tracks = art_tracks.reset_index(drop=True)
        art_tracks.index = art_tracks.index + 1

        display_art = art_tracks[
            ["track_name", "peak_position", "weeks_on_chart", "weeks_at_peak",
             "first_week", "last_week", "total_chart_plays"]
        ].copy()
        display_art["first_week"] = display_art["first_week"].astype(str)
        display_art["last_week"] = display_art["last_week"].astype(str)
        display_art.columns = ["曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "最近上榜", "总播放"]
        display_art.index.name = "#"

        st.subheader(f"{selected_artist} · 入榜曲目")

        st.dataframe(
            display_art,
            column_config={
                "曲目": st.column_config.TextColumn("曲目", width="large"),
                "Peak": st.column_config.NumberColumn("Peak", format="%d"),
                "Wks": st.column_config.NumberColumn("Wks", format="%d"),
                "Pk Wks": st.column_config.NumberColumn("Pk Wks", format="%d"),
                "首次入榜": st.column_config.TextColumn("首次入榜"),
                "最近上榜": st.column_config.TextColumn("最近上榜"),
                "总播放": st.column_config.NumberColumn("总播放", format="%d"),
            },
            use_container_width=True,
        )

        # ── Peak comparison chart (≥3 tracks) ─────────────────────────
        if len(art_tracks) >= 3:
            st.subheader("Peak 排名对比")

            chart_df = art_tracks.sort_values("peak_position", ascending=False)

            color_col = "weeks_on_chart" if peak_tiebreaker == "在榜周数" else "weeks_at_peak"
            color_title = "Wks" if peak_tiebreaker == "在榜周数" else "Pk Wks"

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=chart_df["peak_position"],
                    y=chart_df["track_name"],
                    orientation="h",
                    marker=dict(
                        color=chart_df[color_col],
                        colorscale="YlGnBu",
                        showscale=True,
                        colorbar=dict(title=color_title),
                    ),
                    text=chart_df["peak_position"].apply(lambda x: f"#{x}"),
                    textposition="outside",
                    hovertemplate="%{y}<br>Peak #%{x}<br>%{marker.color:.0f} {color_title}<extra></extra>".replace("{color_title}", color_title),
                )
            )
            fig.update_xaxes(
                autorange="reversed",
                title="Peak 排名 (#1 最佳)",
                range=[chart_df["peak_position"].max() + 5, 0],
            )
            fig.update_layout(height=max(300, len(art_tracks) * 25))
            st.plotly_chart(fig, use_container_width=True)

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

        # Get #1 track names per week
        artist_no1 = (
            artist_weekly[artist_weekly["rank"] == 1]
            .groupby("billboard_week")["track_name"]
            .apply(lambda x: "、".join(dict.fromkeys(x)))
            .reset_index()
        )
        artist_no1.columns = ["billboard_week", "no1_track_names"]
        aw_summary = aw_summary.merge(artist_no1, on="billboard_week", how="left")
        aw_summary["no1_track_names"] = aw_summary["no1_track_names"].fillna("—")
        aw_summary = aw_summary.sort_values("billboard_week", ascending=False)

        if aw_summary.empty:
            st.caption("该艺人在当前过滤条件下无上榜记录")
        else:
            display_aw = aw_summary.copy()
            display_aw["billboard_week"] = display_aw["billboard_week"].astype(str)
            display_aw.columns = ["周", "上榜曲数", "当周总播放", "#1 曲目"]
            display_aw = display_aw.set_index("周")

            st.dataframe(
                display_aw,
                column_config={
                    "上榜曲数": st.column_config.NumberColumn("上榜曲数", format="%d"),
                    "当周总播放": st.column_config.NumberColumn("当周总播放", format="%d"),
                    "#1 曲目": st.column_config.TextColumn("#1 曲目", width="medium"),
                },
                use_container_width=True,
                height=400,
            )


# ═══════════════════════════════════════════════════════════════════════
# Tab: Power Score Ranking (歌曲走势总榜)
# ═══════════════════════════════════════════════════════════════════════
with tab_power:
    st.subheader("⭐ 歌曲走势总榜")
    st.caption(
        "综合衡量最高排名、在榜周数、竞争强度（播放量相对当周大盘）、"
        "前五/前十稳定性及冠单奖励的复合评分"
    )

    power_df = compute_power_scores(weekly, top_n)

    if power_df.empty:
        st.info("暂无足够数据计算走势评分")
    else:
        # ── Summary cards ─────────────────────────────────────────────────
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

        # ── Leaderboard table ────────────────────────────────────────────
        display_ps = power_df[
            [
                "track_name", "artist_name", "power_score", "peak_position",
                "weeks_on_chart", "weeks_top5", "weeks_at_no1",
            ]
        ].copy()
        display_ps.index = display_ps.index + 1
        display_ps.index.name = "#"
        display_ps.columns = [
            "曲目", "艺人", "Power", "Peak", "Wks", "Top5", "#1 Wks",
        ]

        select_event_ps = st.dataframe(
            display_ps,
            column_config={
                "曲目": st.column_config.TextColumn("曲目", width="medium"),
                "艺人": st.column_config.TextColumn("艺人", width="medium"),
                "Power": st.column_config.NumberColumn("Power", format="%,d"),
                "Peak": st.column_config.NumberColumn("Peak", format="%d"),
                "Wks": st.column_config.NumberColumn("Wks", format="%d"),
                "Top5": st.column_config.NumberColumn("Top5", format="%d"),
                "#1 Wks": st.column_config.NumberColumn("#1 Wks", format="%d"),
            },
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
        )

        # Handle row selection → navigate to Tab 2 (单曲历史)
        if select_event_ps.selection.rows:
            row_idx = select_event_ps.selection.rows[0]
            selected_track = power_df.iloc[row_idx]
            st.session_state.bb_selected_track_id = int(selected_track["track_id"])
            st.success(
                f"已选择 **{selected_track['track_name']}** — {selected_track['artist_name']}"
                f" ｜ Power {selected_track['power_score']:,} · "
                f"Peak #{selected_track['peak_position']} · "
                f"{selected_track['weeks_on_chart']}wks\n\n"
                f"👉 切换到「🎵 单曲历史」Tab 查看榜单详情"
            )

        st.divider()

        # ── Scoring formula explainer ─────────────────────────────────────
        with st.expander("📐 Power Score 计算方式"):
            st.markdown(f"""
            **核心公式**：`Power Score = Σ(每周得分) + 冠单奖励 + 稳定性加成`

            **1. 周基础分**（归一化到 rank ÷ Top N，保证调整 Top N 后分数可比）：
            - #1 = 200 分
            - Top 10%（排名 ≤ {int(top_n * 0.1)}）：200 × (0.75 − 2.5 × rank/N)，约 150 → 85 分
            - 10%−20%（排名 ≤ {int(top_n * 0.2)}）：85 × 0.85^(排名−{int(top_n * 0.1)})，约 72 → 40 分
            - 20%−100%：线性衰减至 1 分

            **2. 播放量加权**：`1 + log₂(当周播放次数 ÷ 当周大盘中位数)`，范围 1−4
            - 播放量 = 中位数 → ×1.0；2× 中位数 → ×2.0；8×+ 中位数 → ×4.0（上限）
            - 意义：真正大热的周，排名含金量更高

            **3. 奖励**：Peak #1 +100 · #2 +50 · #3 +30 | 每在前五一周 +20 | 每在前十一周 +5

            **总分 {top_n} 首歌曲**，已从高到低排序
            """)

        # ── Top 20 horizontal bar chart ───────────────────────────────────
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
                lambda x: f"rgba(29,185,84,{max(0.3, min(1, x / top20['power_score'].max()))})"
            )
        )
        st.plotly_chart(fig_ps, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════
# Tab 6: All-Songs Ranking (歌曲总榜)
# ═══════════════════════════════════════════════════════════════════════
with tab6:
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
        ranked.index.name = "#"

        display_cols = ranked[
            ["track_name", "artist_name", "weeks_on_chart", "peak_position", "weeks_at_peak", "first_week"]
        ].copy()
        display_cols["first_week"] = display_cols["first_week"].astype(str)
        display_cols.columns = ["曲目", "艺人", "Wks", "Peak", "Pk Wks", "首次入榜"]

        select_event = st.dataframe(
            display_cols,
            column_config={
                "曲目": st.column_config.TextColumn("曲目", width="medium"),
                "艺人": st.column_config.TextColumn("艺人", width="medium"),
                "Wks": st.column_config.NumberColumn("Wks", format="%d"),
                "Peak": st.column_config.NumberColumn("Peak", format="%d"),
                "Pk Wks": st.column_config.NumberColumn("Pk Wks", format="%d"),
                "首次入榜": st.column_config.TextColumn("首次入榜"),
            },
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
        )

    else:
        # Peak ranking with selectable secondary sort
        peak_tie = st.radio(
            "Peak 相同时按",
            ["在榜周数", "Peak 周数"],
            horizontal=True,
            key="songs_peak_tiebreaker",
        )

        st.subheader(f"Peak 排行（Peak 相同按{peak_tie}）")
        ranked = track_summary.sort_values(
            ["peak_position", "weeks_on_chart" if peak_tie == "在榜周数" else "weeks_at_peak"],
            ascending=[True, False],
        ).reset_index(drop=True)
        ranked.index = ranked.index + 1
        ranked.index.name = "#"

        display_cols = ranked[
            ["track_name", "artist_name", "peak_position", "weeks_on_chart", "weeks_at_peak", "first_week"]
        ].copy()
        display_cols["first_week"] = display_cols["first_week"].astype(str)
        display_cols.columns = ["曲目", "艺人", "Peak", "Wks", "Pk Wks", "首次入榜"]

        select_event = st.dataframe(
            display_cols,
            column_config={
                "曲目": st.column_config.TextColumn("曲目", width="medium"),
                "艺人": st.column_config.TextColumn("艺人", width="medium"),
                "Peak": st.column_config.NumberColumn("Peak", format="%d"),
                "Wks": st.column_config.NumberColumn("Wks", format="%d"),
                "Pk Wks": st.column_config.NumberColumn("Pk Wks", format="%d"),
                "首次入榜": st.column_config.TextColumn("首次入榜"),
            },
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
        )

    # Handle row selection → navigate to Tab 2
    if select_event.selection.rows:
        row_idx = select_event.selection.rows[0]
        selected_track = ranked.iloc[row_idx]
        st.session_state.bb_selected_track_id = int(selected_track["track_id"])
        st.success(
            f"已选择 **{selected_track['track_name']}** — {selected_track['artist_name']}"
            f" ｜ Peak #{selected_track['peak_position']} · {selected_track['weeks_on_chart']}wks\n\n"
            f"👉 切换到「🎵 单曲历史」Tab 查看榜单详情"
        )

    # ── Song-weekly top plays ───────────────────────────────────────────
    st.divider()
    st.subheader("歌曲周播放次数 Top 100")

    song_weekly_top = (
        weekly.sort_values("play_count", ascending=False)
        .head(100)
        .reset_index(drop=True)
    )
    song_weekly_top.index = song_weekly_top.index + 1
    song_weekly_top.index.name = "#"
    song_weekly_top["billboard_week"] = song_weekly_top["billboard_week"].astype(str)
    song_weekly_top["rank_display"] = song_weekly_top["rank"].apply(lambda x: f"#{x}")

    display_swt = song_weekly_top[
        ["track_name", "artist_name", "billboard_week", "play_count", "rank_display"]
    ].copy()
    display_swt.columns = ["曲目", "艺人", "榜单周", "播放次数", "当周 Peak"]

    st.dataframe(
        display_swt,
        column_config={
            "曲目": st.column_config.TextColumn("曲目", width="medium"),
            "艺人": st.column_config.TextColumn("艺人", width="medium"),
            "榜单周": st.column_config.TextColumn("榜单周"),
            "播放次数": st.column_config.NumberColumn("播放次数", format="%d"),
            "当周 Peak": st.column_config.TextColumn("当周 Peak", width="small"),
        },
        use_container_width=True,
        height=500,
    )


# ═══════════════════════════════════════════════════════════════════════
# Tab 5: Album Billboard Summary
# ═══════════════════════════════════════════════════════════════════════
with tab5:
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
            index=0,
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
        col4b.metric("冠军周数", f"{int(selected_album_row['weeks_at_no1'])} 周")

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
                ["peak_position", "weeks_on_chart"], ascending=[True, False]
            )
        else:
            alb_tracks = alb_tracks.sort_values(
                ["peak_position", "weeks_at_peak"], ascending=[True, False]
            )
        alb_tracks = alb_tracks.reset_index(drop=True)
        alb_tracks.index = alb_tracks.index + 1

        display_alb = alb_tracks[
            ["track_name", "peak_position", "weeks_on_chart", "weeks_at_peak",
             "first_week", "last_week", "total_chart_plays"]
        ].copy()
        display_alb["first_week"] = display_alb["first_week"].astype(str)
        display_alb["last_week"] = display_alb["last_week"].astype(str)
        display_alb.columns = ["曲目", "Peak", "Wks", "Pk Wks", "首次入榜", "最近上榜", "总播放"]
        display_alb.index.name = "#"

        st.subheader(f"《{selected_album}》 · 入榜曲目")

        select_evt_alb = st.dataframe(
            display_alb,
            column_config={
                "曲目": st.column_config.TextColumn("曲目", width="large"),
                "Peak": st.column_config.NumberColumn("Peak", format="%d"),
                "Wks": st.column_config.NumberColumn("Wks", format="%d"),
                "Pk Wks": st.column_config.NumberColumn("Pk Wks", format="%d"),
                "首次入榜": st.column_config.TextColumn("首次入榜"),
                "最近上榜": st.column_config.TextColumn("最近上榜"),
                "总播放": st.column_config.NumberColumn("总播放", format="%d"),
            },
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
        )

        # Handle row selection → navigate to Tab 2
        if select_evt_alb.selection.rows:
            row_idx = select_evt_alb.selection.rows[0]
            selected_track = alb_tracks.iloc[row_idx]
            st.session_state.bb_selected_track_id = int(selected_track["track_id"])
            st.success(
                f"已选择 **{selected_track['track_name']}**"
                f" ｜ Peak #{selected_track['peak_position']} · {selected_track['weeks_on_chart']}wks\n\n"
                f"👉 切换到「🎵 单曲历史」Tab 查看榜单详情"
            )

        # ── Peak comparison chart (≥3 tracks) ─────────────────────────
        if len(alb_tracks) >= 3:
            st.subheader("Peak 排名对比")

            chart_df = alb_tracks.sort_values("peak_position", ascending=False)

            color_col = "weeks_on_chart" if album_tiebreaker == "在榜周数" else "weeks_at_peak"
            color_title = "Wks" if album_tiebreaker == "在榜周数" else "Pk Wks"

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=chart_df["peak_position"],
                    y=chart_df["track_name"],
                    orientation="h",
                    marker=dict(
                        color=chart_df[color_col],
                        colorscale="YlGnBu",
                        showscale=True,
                        colorbar=dict(title=color_title),
                    ),
                    text=chart_df["peak_position"].apply(lambda x: f"#{x}"),
                    textposition="outside",
                    hovertemplate="%{y}<br>Peak #%{x}<br>%{marker.color:.0f} " + color_title + "<extra></extra>",
                )
            )
            fig.update_xaxes(
                autorange="reversed",
                title="Peak 排名 (#1 最佳)",
                range=[chart_df["peak_position"].max() + 5, 0],
            )
            fig.update_layout(height=max(300, len(alb_tracks) * 25))
            st.plotly_chart(fig, use_container_width=True)

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

        # Get #1 track names per week
        album_no1 = (
            album_weekly[album_weekly["rank"] == 1]
            .groupby("billboard_week")["track_name"]
            .apply(lambda x: "、".join(dict.fromkeys(x)))
            .reset_index()
        )
        album_no1.columns = ["billboard_week", "no1_track_names"]
        alw_summary = alw_summary.merge(album_no1, on="billboard_week", how="left")
        alw_summary["no1_track_names"] = alw_summary["no1_track_names"].fillna("—")
        alw_summary = alw_summary.sort_values("billboard_week", ascending=False)

        if alw_summary.empty:
            st.caption("该专辑在当前过滤条件下无上榜记录")
        else:
            display_alw = alw_summary.copy()
            display_alw["billboard_week"] = display_alw["billboard_week"].astype(str)
            display_alw.columns = ["周", "上榜曲数", "当周总播放", "#1 曲目"]
            display_alw = display_alw.set_index("周")

            st.dataframe(
                display_alw,
                column_config={
                    "上榜曲数": st.column_config.NumberColumn("上榜曲数", format="%d"),
                    "当周总播放": st.column_config.NumberColumn("当周总播放", format="%d"),
                    "#1 曲目": st.column_config.TextColumn("#1 曲目", width="medium"),
                },
                use_container_width=True,
                height=400,
            )


# ═══════════════════════════════════════════════════════════════════════
# Tab 2: Number Ones History
# ═══════════════════════════════════════════════════════════════════════
with tab2:
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

    # ── Two-column layout ─────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("每周冠单")

        display = number_ones[["billboard_week", "track_name", "artist_name", "play_count"]].copy()
        display.columns = ["周", "冠单曲目", "艺人", "播放次数"]
        display = display.set_index("周")

        st.dataframe(
            display,
            column_config={
                "冠单曲目": st.column_config.TextColumn("冠单曲目", width="large"),
                "艺人": st.column_config.TextColumn("艺人", width="medium"),
                "播放次数": st.column_config.NumberColumn("播放次数", format="%d"),
            },
            use_container_width=True,
            height=600,
        )

    with col_right:
        st.subheader("冠单周数排行")

        ws_display = weeks_at_one.head(20).reset_index(drop=True)
        ws_display.index = ws_display.index + 1
        ws_display.index.name = "#"

        st.dataframe(
            ws_display[["track_name", "artist_name", "weeks_at_no1", "total_no1_plays"]],
            column_config={
                "track_name": st.column_config.TextColumn("曲目", width="medium"),
                "artist_name": st.column_config.TextColumn("艺人", width="medium"),
                "weeks_at_no1": st.column_config.NumberColumn("冠单周数", format="%d"),
                "total_no1_plays": st.column_config.NumberColumn("总播放", format="%d"),
            },
            use_container_width=True,
            height=600,
        )

    # ── Chart ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("冠单周数 Top 15")

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
        st.dataframe(
            debut_no1[["曲目", "艺人", "首次上榜周", "在榜周数", "冠单周数"]],
            column_config={
                "曲目": st.column_config.TextColumn("曲目", width="medium"),
                "艺人": st.column_config.TextColumn("艺人", width="medium"),
                "首次上榜周": st.column_config.TextColumn("首次上榜周"),
                "在榜周数": st.column_config.NumberColumn("在榜周数", format="%d"),
                "冠单周数": st.column_config.NumberColumn("冠单周数", format="%d"),
            },
            use_container_width=True,
        )

    # ── Weekly total plays ranking (榜单大盘) ────────────────────────────
    st.divider()
    st.subheader("榜单周总播放次数排名（大盘）")

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
        ["billboard_week", "track_name", "artist_name", "play_count"]
    ].copy()
    week_no1.columns = ["billboard_week", "no1_track", "no1_artist", "no1_plays"]
    week_total_plays = week_total_plays.merge(week_no1, on="billboard_week", how="left")
    week_total_plays = week_total_plays.sort_values("total_plays", ascending=False)
    week_total_plays = week_total_plays.reset_index(drop=True)
    week_total_plays.index = week_total_plays.index + 1
    week_total_plays.index.name = "#"
    week_total_plays["billboard_week"] = week_total_plays["billboard_week"].astype(str)

    display_wtp = week_total_plays[
        ["billboard_week", "total_plays", "no1_track", "no1_artist", "no1_plays"]
    ].copy()
    display_wtp.columns = ["周", "总播放次数", "#1 曲目", "#1 艺人", "#1 播放次数"]

    st.dataframe(
        display_wtp,
        column_config={
            "周": st.column_config.TextColumn("周"),
            "总播放次数": st.column_config.NumberColumn("总播放次数", format="%d"),
            "#1 曲目": st.column_config.TextColumn("#1 曲目", width="medium"),
            "#1 艺人": st.column_config.TextColumn("#1 艺人", width="medium"),
            "#1 播放次数": st.column_config.NumberColumn("#1 播放次数", format="%d"),
        },
        use_container_width=True,
        height=500,
    )


# ═══════════════════════════════════════════════════════════════════════
# Tab 7: Artist Overall Ranking
# ═══════════════════════════════════════════════════════════════════════
with tab7:
    st.subheader("艺人总榜")

    artist_rank_metric = st.radio(
        "排行指标",
        ["入榜曲数", "总上榜周数", "#1 曲数", "Top 5 曲数", "Top 10 曲数"],
        horizontal=True,
        key="artist_overall_metric",
    )

    metric_map = {
        "入榜曲数": "total_tracks",
        "总上榜周数": "total_weeks",
        "#1 曲数": "top1",
        "Top 5 曲数": "top5",
        "Top 10 曲数": "top10",
    }
    sort_col = metric_map[artist_rank_metric]

    ranked_art = artist_track_counts.sort_values(sort_col, ascending=False).head(100).reset_index(drop=True)
    ranked_art.index = ranked_art.index + 1
    ranked_art.index.name = "#"

    display = ranked_art[["artist_name", "total_tracks", "top1", "top5", "top10", "total_weeks"]].copy()
    display.columns = ["艺人", "入榜曲数", "#1", "Top5", "Top10", "总周数"]

    st.dataframe(
        display,
        column_config={
            "艺人": st.column_config.TextColumn("艺人", width="medium"),
            "入榜曲数": st.column_config.NumberColumn("入榜曲数", format="%d"),
            "#1": st.column_config.NumberColumn("#1", format="%d"),
            "Top5": st.column_config.NumberColumn("Top5", format="%d"),
            "Top10": st.column_config.NumberColumn("Top10", format="%d"),
            "总周数": st.column_config.NumberColumn("总周数", format="%d"),
        },
        use_container_width=True,
        height=600,
    )

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
with tab8:
    st.subheader("专辑总榜")

    album_rank_metric = st.radio(
        "排行指标",
        ["入榜曲数", "总上榜周数", "#1 曲数", "Top 5 曲数", "Top 10 曲数"],
        horizontal=True,
        key="album_overall_metric",
    )

    album_metric_map = {
        "入榜曲数": "total_tracks",
        "总上榜周数": "total_weeks",
        "#1 曲数": "top1",
        "Top 5 曲数": "top5",
        "Top 10 曲数": "top10",
    }
    album_sort_col = album_metric_map[album_rank_metric]

    ranked_alb = album_track_counts.sort_values(album_sort_col, ascending=False).head(100).reset_index(drop=True)
    ranked_alb.index = ranked_alb.index + 1
    ranked_alb.index.name = "#"

    display_alb = ranked_alb[["album_name", "artist_name", "total_tracks", "top1", "top5", "top10", "total_weeks"]].copy()
    display_alb.columns = ["专辑", "艺人", "入榜曲数", "#1", "Top5", "Top10", "总周数"]

    st.dataframe(
        display_alb,
        column_config={
            "专辑": st.column_config.TextColumn("专辑", width="medium"),
            "艺人": st.column_config.TextColumn("艺人", width="medium"),
            "入榜曲数": st.column_config.NumberColumn("入榜曲数", format="%d"),
            "#1": st.column_config.NumberColumn("#1", format="%d"),
            "Top5": st.column_config.NumberColumn("Top5", format="%d"),
            "Top10": st.column_config.NumberColumn("Top10", format="%d"),
            "总周数": st.column_config.NumberColumn("总周数", format="%d"),
        },
        use_container_width=True,
        height=600,
    )

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

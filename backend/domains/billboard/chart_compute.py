"""Core Billboard computation pipeline."""

import math
from functools import lru_cache

import numpy as np
import pandas as pd

from backend.core.cache import singleflight
from backend.core.db import (
    enrich_track_artist_names,
    fan_out_weekly_for_artists,
)
from backend.core.json_helpers import df_to_json as _df_to_json
from backend.domains.billboard.data_loader import (
    DOW_NAMES,
    DOW_SHORT,
    _load_album_metadata,
    _try_load_from_agg,
    load_billboard_raw,
    load_billboard_raw_for_artists,
    load_track_album_map,
)
from backend.domains.billboard.version_merge import (
    _apply_album_release_groups,
    _normalize_album_column,
)

# ── Power Score 参数 ────────────────────────────────────────────────────
# 榜单统治力评分 = Σ(每周基础分 × 竞争权重) + peak_bonus + 周数奖励 + 持续性加成 + 空降加成
#
# 基础分: 指数衰减曲线，与 top_n 无关
#   base = max(1, round(_RANK1_BASE × _BASE_DECAY^(rank-1)))
#   示例: #1=200, #2=174, #3=151, #5=117, #10=59, #20=15, #30=4
#
# 竞争权重 = comp_factor × indiv_factor
#   comp_factor = clamp(√(week_total_plays / global_baseline), 0.7, 1.5)  — 周竞争强度
#     — sqrt 压缩极端值，冷热周自然收敛，夹率从 48%→17%
#   indiv_factor（冠军）: 1 + clamp(0.5 × log2(plays / runner_up), 0, 1.0)
#     — 用"与亚军差距"度量统治力
#   indiv_factor（非冠军）: 1 + clamp(0.4 × log2(plays / week_median), 0, 0.8)
#     — 度量高于当周平均水平的程度，4×中位数即达上限 1.8×
# 持续性加成 = sqrt(weeks_on_chart) × LONGEVITY_FACTOR，奖励长期在榜的稳定表现

_RANK1_BASE = 200  # 第 1 名基础分
_BASE_DECAY = 0.87  # 基础分指数衰减因子（每降 1 名 ×0.87）
_PEAK_BONUS = {1: 200, 2: 100, 3: 50}  # 最高排名一次性奖励
_TOP5_BONUS = 30  # 每周 Top 5 奖励（仅单曲）
_TOP10_BONUS = 10  # 每周 Top 10 奖励（仅单曲）
_TOP1_BONUS = 40  # 每周 #1 奖励（专辑/艺人）
_LONGEVITY_FACTOR = 45  # 持续性加成系数
_DEBUT_NO1_BONUS = 50  # 空降 #1 奖励（首周即登顶）
_COMP_RANGE = (0.7, 1.5)  # 竞争因子 clamp 范围
_INDIV_RANGE = (0.0, 0.8)  # 个人统治因子 clamp 范围（非冠军，不含基准 1.0）
_INDIV_GAP_RANGE = (0.0, 1.0)  # 冠军统治因子 clamp 范围（gap-to-runner-up，不含基准 1.0）


def compute_weekly_rankings(_df, top_n, pre_agg=None):
    """Aggregate per-week rankings with tiebreaker (play_count > total_ms).

    If pre_agg DataFrame is provided (from agg_weekly_tracks), skips the
    expensive groupby step and directly ranks the pre-aggregated data.
    """
    if pre_agg is not None and not pre_agg.empty:
        weekly = pre_agg.copy()
        # pre_agg already has: billboard_week, track_id, track_name,
        # artist_name, album_name, play_count, total_ms
    else:
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


def compute_album_weekly_rankings(_df, top_n, pre_agg=None):
    """Aggregate per-week album rankings from ALL plays (not just charting tracks).

    If pre_agg DataFrame is provided (from agg_weekly_albums), skips the
    expensive groupby step.

    Release groups are applied to merge different album versions (deluxe,
    acoustic, etc.) into canonical names before ranking.
    """
    if pre_agg is not None and not pre_agg.empty:
        weekly_album = pre_agg.copy()
        # pre_agg already has: billboard_week, album_id, album_name,
        # artist_name, play_count, total_ms
        # Estimate tracks_count from the album-tracks relationship
        weekly_album["tracks_count"] = 0
    else:
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

    # 应用发行版本合并：将组内成员的 album_name 替换为 canonical_name 并重新聚合
    weekly_album = _apply_album_release_groups(weekly_album)

    weekly_album = weekly_album.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )
    # 排除 single 类型 + 排除专辑发行前的周数
    album_meta = _load_album_metadata()
    weekly_album = weekly_album.merge(
        album_meta["type"], on=["album_name", "artist_name"], how="left"
    )
    weekly_album = weekly_album[weekly_album["album_type"] != "single"]
    weekly_album = weekly_album.merge(
        album_meta["release_date"], on=["album_name", "artist_name"], how="left"
    )
    if not weekly_album.empty:
        weekly_album["_bb_week"] = pd.to_datetime(weekly_album["billboard_week"])
        weekly_album["_rel_date"] = pd.to_datetime(weekly_album["release_date"], errors="coerce")
        weekly_album = weekly_album[
            weekly_album["_rel_date"].isna()
            | (weekly_album["_bb_week"] + pd.Timedelta(days=6) >= weekly_album["_rel_date"])
        ].drop(columns=["_bb_week", "_rel_date"])

    weekly_album["rank"] = weekly_album.groupby("billboard_week").cumcount() + 1
    weekly_album = weekly_album[weekly_album["rank"] <= top_n]
    return weekly_album


def compute_artist_weekly_rankings(_df, top_n, pre_agg=None):
    """Aggregate per-week artist rankings from ALL plays (not just charting tracks).

    If pre_agg DataFrame is provided (from agg_weekly_artists), skips the
    expensive groupby step.
    """
    if pre_agg is not None and not pre_agg.empty:
        weekly_artist = pre_agg.copy()
        # pre_agg already has: billboard_week, artist_id, artist_name,
        # play_count, total_ms
        weekly_artist["tracks_count"] = 0
    else:
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


def compute_power_scores(weekly, top_n):
    """Compute Power Score for each track — composite ranking metric.

    Power Score = Σ(weekly_base_points × competition_weight)
                  + peak_bonus + top5_bonus + top10_bonus
                  + longevity_bonus + debut_bonus

    competition_weight = comp_factor × indiv_factor
      comp_factor = clamp(week_median / global_baseline, _COMP_RANGE)
        — rewards performing in competitive weeks
      indiv_factor = 1.0 + clamp(0.5 × log2(plays / week_median), _INDIV_RANGE)
        — rewards dominating peers within the week

    Base points are normalized to rank/top_n so scores are comparable
    regardless of chart size top_n.
    """
    week_medians = weekly.groupby("billboard_week")["play_count"].median().to_dict()
    week_totals = weekly.groupby("billboard_week")["play_count"].sum().to_dict()
    week_total_values = list(week_totals.values())
    global_baseline = float(np.median(week_total_values)) if week_total_values else 1.0
    comp_lo, comp_hi = _COMP_RANGE
    indiv_lo, indiv_hi = _INDIV_RANGE
    gap_lo, gap_hi = _INDIV_GAP_RANGE

    # Precompute #1 and #2 plays per week for gap-to-runner-up
    _r2 = weekly[weekly["rank"] == 2][["billboard_week", "play_count"]]
    week_r2 = dict(zip(_r2["billboard_week"], _r2["play_count"]))

    has_artist_names = "artist_names" in weekly.columns

    scores = []
    for (track_id, track_name, artist_name), group in weekly.groupby(
        ["track_id", "track_name", "artist_name"]
    ):
        peak = group["rank"].min()
        weeks_total = group["billboard_week"].nunique()
        weeks_top5 = int((group["rank"] <= 5).sum())
        weeks_top10 = int((group["rank"] <= 10).sum())
        weeks_at_no1 = int((group["rank"] == 1).sum())

        # Debut #1: first charting week was rank 1
        first_week_idx = group["billboard_week"].idxmin()
        debut_rank = group.loc[first_week_idx, "rank"]
        is_debut_no1 = 1 if debut_rank == 1 else 0

        total = 0.0
        for _, row in group.iterrows():
            rank = row["rank"]
            plays = row["play_count"]
            median = week_medians.get(row["billboard_week"], 1)
            week_total = week_totals.get(row["billboard_week"], 1)

            # 1. Base points — exponential decay, independent of top_n
            base = max(1, round(_RANK1_BASE * _BASE_DECAY ** (rank - 1)))

            # 2. Competition weight
            #    comp_factor: 市场大盘越热 → 竞争越激烈 → 排名含金量越高
            #    indiv_factor: #1 uses gap-to-runner-up, others use median ratio
            if week_total > 0 and plays > 0 and global_baseline > 0:
                comp_factor = max(comp_lo, min(comp_hi, math.sqrt(week_total / global_baseline)))
                if rank == 1:
                    runner_up = week_r2.get(row["billboard_week"], 0)
                    if runner_up > 0:
                        gap_ratio = plays / runner_up
                        indiv_factor = 1.0 + max(gap_lo, min(gap_hi, 0.5 * np.log2(gap_ratio)))
                    else:
                        indiv_factor = 1.0 + gap_hi  # solo #1, max bonus
                else:
                    indiv_factor = 1.0 + max(indiv_lo, min(indiv_hi, 0.4 * np.log2(plays / median)))
                weight = comp_factor * indiv_factor
            else:
                weight = 1.0

            total += base * weight

        # 3. Bonuses
        peak_bonus = _PEAK_BONUS.get(peak, 0)
        top5_bonus = weeks_top5 * _TOP5_BONUS
        top10_bonus = weeks_top10 * _TOP10_BONUS
        longevity_bonus = math.sqrt(weeks_total) * _LONGEVITY_FACTOR
        debut_bonus = is_debut_no1 * _DEBUT_NO1_BONUS

        power_score = round(
            total + peak_bonus + top5_bonus + top10_bonus + longevity_bonus + debut_bonus
        )

        entry = {
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
        if has_artist_names:
            names_val = group.iloc[0].get("artist_names")
            if isinstance(names_val, list):
                entry["artist_names"] = names_val
        scores.append(entry)

    df = pd.DataFrame(scores).sort_values("power_score", ascending=False).reset_index(drop=True)
    df["power_rank"] = df.index + 1
    return df


def compute_album_power_scores(weekly_album, top_n):
    """Compute Power Score for each album — composite ranking metric.

    Power Score = Σ(weekly_base_points × competition_weight)
                  + peak_bonus + top1_bonus + longevity_bonus + debut_bonus
    """
    week_medians = weekly_album.groupby("billboard_week")["play_count"].median().to_dict()
    week_totals = weekly_album.groupby("billboard_week")["play_count"].sum().to_dict()
    week_total_values = list(week_totals.values())
    global_baseline = float(np.median(week_total_values)) if week_total_values else 1.0
    comp_lo, comp_hi = _COMP_RANGE
    indiv_lo, indiv_hi = _INDIV_RANGE
    gap_lo, gap_hi = _INDIV_GAP_RANGE

    _r2 = weekly_album[weekly_album["rank"] == 2][["billboard_week", "play_count"]]
    week_r2 = dict(zip(_r2["billboard_week"], _r2["play_count"]))

    scores = []
    for (album_name, artist_name), group in weekly_album.groupby(["album_name", "artist_name"]):
        peak = group["rank"].min()
        weeks_total = group["billboard_week"].nunique()
        weeks_top1 = int((group["rank"] == 1).sum())
        weeks_top5 = int((group["rank"] <= 5).sum())
        weeks_top10 = int((group["rank"] <= 10).sum())

        first_week_idx = group["billboard_week"].idxmin()
        debut_rank = group.loc[first_week_idx, "rank"]
        is_debut_no1 = 1 if debut_rank == 1 else 0

        total = 0.0
        for _, row in group.iterrows():
            rank = row["rank"]
            plays = row["play_count"]
            median = week_medians.get(row["billboard_week"], 1)
            week_total = week_totals.get(row["billboard_week"], 1)

            base = max(1, round(_RANK1_BASE * _BASE_DECAY ** (rank - 1)))

            if week_total > 0 and plays > 0 and global_baseline > 0:
                comp_factor = max(comp_lo, min(comp_hi, math.sqrt(week_total / global_baseline)))
                if rank == 1:
                    runner_up = week_r2.get(row["billboard_week"], 0)
                    if runner_up > 0:
                        gap_ratio = plays / runner_up
                        indiv_factor = 1.0 + max(gap_lo, min(gap_hi, 0.5 * np.log2(gap_ratio)))
                    else:
                        indiv_factor = 1.0 + gap_hi
                else:
                    indiv_factor = 1.0 + max(indiv_lo, min(indiv_hi, 0.4 * np.log2(plays / median)))
                weight = comp_factor * indiv_factor
            else:
                weight = 1.0

            total += base * weight

        peak_bonus = _PEAK_BONUS.get(peak, 0)
        top1_bonus = weeks_top1 * _TOP1_BONUS
        longevity_bonus = math.sqrt(weeks_total) * _LONGEVITY_FACTOR
        debut_bonus = is_debut_no1 * _DEBUT_NO1_BONUS

        power_score = round(total + peak_bonus + top1_bonus + longevity_bonus + debut_bonus)

        scores.append(
            {
                "album_name": album_name,
                "artist_name": artist_name,
                "power_score": power_score,
                "peak_position": peak,
                "weeks_on_chart": weeks_total,
                "weeks_top1": weeks_top1,
                "weeks_top5": weeks_top5,
                "weeks_top10": weeks_top10,
            }
        )

    df = pd.DataFrame(scores).sort_values("power_score", ascending=False).reset_index(drop=True)
    df["power_rank"] = df.index + 1
    return df


def compute_artist_power_scores(weekly_artist, top_n):
    """Compute Power Score for each artist — composite ranking metric.

    Power Score = Σ(weekly_base_points × competition_weight)
                  + peak_bonus + top1_bonus + longevity_bonus + debut_bonus
    """

    week_medians = weekly_artist.groupby("billboard_week")["play_count"].median().to_dict()
    week_totals = weekly_artist.groupby("billboard_week")["play_count"].sum().to_dict()
    week_total_values = list(week_totals.values())
    global_baseline = float(np.median(week_total_values)) if week_total_values else 1.0
    comp_lo, comp_hi = _COMP_RANGE
    indiv_lo, indiv_hi = _INDIV_RANGE
    gap_lo, gap_hi = _INDIV_GAP_RANGE

    _r2 = weekly_artist[weekly_artist["rank"] == 2][["billboard_week", "play_count"]]
    week_r2 = dict(zip(_r2["billboard_week"], _r2["play_count"]))

    scores = []
    for artist_name, group in weekly_artist.groupby("artist_name"):
        peak = group["rank"].min()
        weeks_total = group["billboard_week"].nunique()
        weeks_top1 = int((group["rank"] == 1).sum())
        weeks_top5 = int((group["rank"] <= 5).sum())
        weeks_top10 = int((group["rank"] <= 10).sum())

        first_week_idx = group["billboard_week"].idxmin()
        debut_rank = group.loc[first_week_idx, "rank"]
        is_debut_no1 = 1 if debut_rank == 1 else 0

        total = 0.0
        for _, row in group.iterrows():
            rank = row["rank"]
            plays = row["play_count"]
            median = week_medians.get(row["billboard_week"], 1)
            week_total = week_totals.get(row["billboard_week"], 1)

            base = max(1, round(_RANK1_BASE * _BASE_DECAY ** (rank - 1)))

            if week_total > 0 and plays > 0 and global_baseline > 0:
                comp_factor = max(comp_lo, min(comp_hi, math.sqrt(week_total / global_baseline)))
                if rank == 1:
                    runner_up = week_r2.get(row["billboard_week"], 0)
                    if runner_up > 0:
                        gap_ratio = plays / runner_up
                        indiv_factor = 1.0 + max(gap_lo, min(gap_hi, 0.5 * np.log2(gap_ratio)))
                    else:
                        indiv_factor = 1.0 + gap_hi
                else:
                    indiv_factor = 1.0 + max(indiv_lo, min(indiv_hi, 0.4 * np.log2(plays / median)))
                weight = comp_factor * indiv_factor
            else:
                weight = 1.0

            total += base * weight

        peak_bonus = _PEAK_BONUS.get(peak, 0)
        top1_bonus = weeks_top1 * _TOP1_BONUS
        longevity_bonus = math.sqrt(weeks_total) * _LONGEVITY_FACTOR
        debut_bonus = is_debut_no1 * _DEBUT_NO1_BONUS

        power_score = round(total + peak_bonus + top1_bonus + longevity_bonus + debut_bonus)

        scores.append(
            {
                "artist_name": artist_name,
                "power_score": power_score,
                "peak_position": peak,
                "weeks_on_chart": weeks_total,
                "weeks_top1": weeks_top1,
                "weeks_top5": weeks_top5,
                "weeks_top10": weeks_top10,
            }
        )

    df = pd.DataFrame(scores).sort_values("power_score", ascending=False).reset_index(drop=True)
    df["power_rank"] = df.index + 1
    return df


def _add_running_metrics(df, group_cols):
    """Add running_peak, running_wks, running_peak_wks columns.

    All three metrics are computed up to and including the current week,
    not as all-time aggregates. When the peak improves (e.g. 2→1), the
    peak-weeks count resets to only include weeks at the new peak.
    """
    df = df.sort_values(group_cols + ["billboard_week"])
    df["running_peak"] = df.groupby(group_cols)["rank"].cummin()
    df["running_wks"] = df.groupby(group_cols).cumcount() + 1

    def _running_peak_wks(group, key):
        ranks = group["rank"].values
        rp = np.minimum.accumulate(ranks)
        rank_counts = {}
        result = np.zeros(len(ranks), dtype=int)
        for i, r in enumerate(ranks):
            rank_counts[r] = rank_counts.get(r, 0) + 1
            result[i] = rank_counts[rp[i]]
        group = group.copy()
        key = key if isinstance(key, tuple) else (key,)
        for col, val in zip(group_cols, key):
            group[col] = val
        group["running_peak_wks"] = result
        return group

    groups = [_running_peak_wks(group, key) for key, group in df.groupby(group_cols, sort=False)]
    return pd.concat(groups, ignore_index=True) if groups else df


@singleflight
@lru_cache(maxsize=8)
def _compute_billboard_data_cached(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute all Billboard data in one call.

    Returns a dict with all DataFrames converted to JSON-safe lists of dicts.
    This single function replaces the 15+ DataFrame computation pipeline
    previously done in Streamlit's billboard/__init__.py:run().

    Parameters
    ----------
    min_ms : int
        Minimum play duration in milliseconds.
    music_only : bool
        Exclude podcasts/audiobooks.
    bb_top_n : int
        Number of tracks per week in the singles chart.
    bb_album_top_n : int
        Number of albums per week in the albums chart.
    bb_artist_top_n : int
        Number of artists per week in the artists chart.
    bb_week_start_dow : int
        Day of week (0=Mon, 6=Sun) that starts a Billboard week.
    bb_week_start_hour : int
        Hour (0-23) that starts a Billboard week.
    year_start : int or None
        Filter to this year and later (inclusive).
    year_end : int or None
        Filter to this year and earlier (inclusive).

    Returns
    -------
    dict with keys:
        meta, weekly, weekly_album, weekly_artist,
        track_summary, artist_summary, artist_track_counts,
        album_track_counts, track_per_album,
        records, power_scores, album_power_scores, artist_power_scores
    """
    # ── Load raw data ──────────────────────────────────────────────────
    df_raw = load_billboard_raw(min_ms, music_only, bb_week_start_dow, bb_week_start_hour)
    album_map = load_track_album_map()

    # ── Year filter ────────────────────────────────────────────────────
    df_raw = df_raw.copy()
    df_raw["_year"] = df_raw["billboard_week"].apply(lambda x: x.year)
    if year_start is not None:
        df_raw = df_raw[df_raw["_year"] >= year_start]
    if year_end is not None:
        df_raw = df_raw[df_raw["_year"] <= year_end]
    df_filtered = df_raw.copy()

    # All weeks
    all_weeks_asc = sorted(df_filtered["billboard_week"].unique().tolist())
    all_weeks_desc = sorted(all_weeks_asc, reverse=True)

    # ── Try pre-aggregated tables ──────────────────────────────────────
    _agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(
        min_ms, music_only, bb_week_start_dow, bb_week_start_hour
    )

    if _agg_tracks is not None:
        _agg_tracks = _agg_tracks[
            pd.to_datetime(_agg_tracks["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_albums = _agg_albums[
            pd.to_datetime(_agg_albums["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_artists = _agg_artists[
            pd.to_datetime(_agg_artists["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]

    # ── Compute rankings ───────────────────────────────────────────────
    weekly = compute_weekly_rankings(df_filtered, bb_top_n, pre_agg=_agg_tracks)
    weekly_album = compute_album_weekly_rankings(df_filtered, bb_album_top_n, pre_agg=_agg_albums)

    if _agg_artists is not None:
        weekly_artist = compute_artist_weekly_rankings(
            df_filtered, bb_artist_top_n, pre_agg=_agg_artists
        )
    else:
        df_artists = load_billboard_raw_for_artists(
            min_ms, music_only, bb_week_start_dow, bb_week_start_hour
        )
        df_artists = df_artists.copy()
        df_artists["_year"] = df_artists["billboard_week"].apply(lambda x: x.year)
        if year_start is not None:
            df_artists = df_artists[df_artists["_year"] >= year_start]
        if year_end is not None:
            df_artists = df_artists[df_artists["_year"] <= year_end]
        weekly_artist = compute_artist_weekly_rankings(df_artists, bb_artist_top_n)

    # ── Patch tracks_count from weekly when using pre-agg ──────────────
    if _agg_tracks is not None:
        _album_tc = (
            weekly.groupby(["billboard_week", "album_name", "artist_name"])
            .agg(tracks_count=("track_id", "nunique"))
            .reset_index()
        )
        _album_tc = _normalize_album_column(
            _album_tc, dedup_cols=["billboard_week", "album_name", "artist_name"]
        )
        _album_tc = (
            _album_tc.groupby(["billboard_week", "album_name", "artist_name"])
            .agg(tracks_count=("tracks_count", "sum"))
            .reset_index()
        )
        weekly_album = weekly_album.drop(columns=["tracks_count"], errors="ignore").merge(
            _album_tc, on=["billboard_week", "album_name", "artist_name"], how="left"
        )
        weekly_album["tracks_count"] = weekly_album["tracks_count"].fillna(0).astype(int)

        _artist_tc = (
            weekly.groupby(["billboard_week", "artist_name"])
            .agg(tracks_count=("track_id", "nunique"))
            .reset_index()
        )
        weekly_artist = weekly_artist.drop(columns=["tracks_count"], errors="ignore").merge(
            _artist_tc, on=["billboard_week", "artist_name"], how="left"
        )
        weekly_artist["tracks_count"] = weekly_artist["tracks_count"].fillna(0).astype(int)

    # Albums count per artist from album chart
    _artist_ac = (
        weekly_album.groupby(["billboard_week", "artist_name"])
        .agg(albums_count=("album_name", "nunique"))
        .reset_index()
    )
    weekly_artist = weekly_artist.merge(
        _artist_ac, on=["billboard_week", "artist_name"], how="left"
    )
    weekly_artist["albums_count"] = weekly_artist["albums_count"].fillna(0).astype(int)

    # ── Track summary ──────────────────────────────────────────────────
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

    # Total plays per track (all-time)
    track_total_plays = (
        df_filtered.groupby("track_id").agg(total_plays=("ms_played", "count")).reset_index()
    )
    track_summary = track_summary.merge(track_total_plays, on="track_id", how="left")

    # Weeks at #1
    weeks_at_no1 = (
        weekly[weekly["rank"] == 1]
        .groupby("track_id")
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
    )
    track_summary = track_summary.merge(weeks_at_no1, on="track_id", how="left")
    track_summary["weeks_at_no1"] = track_summary["weeks_at_no1"].fillna(0).astype(int)

    # First week at peak position
    first_peak = weekly.merge(track_summary[["track_id", "peak_position"]], on="track_id")
    first_peak = first_peak[first_peak["rank"] == first_peak["peak_position"]]
    first_peak = first_peak.groupby("track_id")["billboard_week"].min().reset_index()
    first_peak.columns = ["track_id", "first_peak_week"]
    track_summary = track_summary.merge(first_peak, on="track_id", how="left")

    # is_debut_no1: debuted at #1 (first_week == first_peak_week AND peak_position == 1)
    track_summary["is_debut_no1"] = (track_summary["peak_position"] == 1) & (
        track_summary["first_week"] == track_summary["first_peak_week"]
    )

    weekly = _add_running_metrics(weekly, ["track_id"])
    weekly_album = _add_running_metrics(weekly_album, ["artist_name", "album_name"])
    weekly_artist = _add_running_metrics(weekly_artist, ["artist_name"])

    # ── Artist summary ─────────────────────────────────────────────────
    weekly_fanned = fan_out_weekly_for_artists(weekly)
    artist_summary = (
        weekly_fanned.groupby(["artist_name", "track_id", "track_name", "album_name"])
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

    # ── Artist track counts ────────────────────────────────────────────
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
        lambda a: (
            artist_summary[artist_summary["artist_name"] == a]
            .sort_values("peak_position")
            .iloc[0]["track_name"]
        )
    )

    # Artist weeks at #1 (sum of all tracks' weeks at #1)
    artist_weeks_no1 = track_summary.groupby("artist_name")["weeks_at_no1"].sum().reset_index()
    artist_track_counts = artist_track_counts.merge(artist_weeks_no1, on="artist_name", how="left")

    # Album #1 metrics per artist
    album_no1_artist = (
        weekly_album[weekly_album["rank"] == 1]
        .groupby("artist_name")
        .agg(
            num_no1_albums=("album_name", "nunique"),
            album_no1_weeks=("billboard_week", "nunique"),
        )
        .reset_index()
    )
    artist_track_counts = artist_track_counts.merge(album_no1_artist, on="artist_name", how="left")
    artist_track_counts["num_no1_albums"] = (
        artist_track_counts["num_no1_albums"].fillna(0).astype(int)
    )
    artist_track_counts["album_no1_weeks"] = (
        artist_track_counts["album_no1_weeks"].fillna(0).astype(int)
    )

    # Artist chart #1 weeks
    artist_no1_weeks = (
        weekly_artist[weekly_artist["rank"] == 1]
        .groupby("artist_name")
        .agg(
            artist_chart_no1_weeks=("billboard_week", "nunique"),
        )
        .reset_index()
    )
    artist_track_counts = artist_track_counts.merge(artist_no1_weeks, on="artist_name", how="left")
    artist_track_counts["artist_chart_no1_weeks"] = (
        artist_track_counts["artist_chart_no1_weeks"].fillna(0).astype(int)
    )

    # ── Album expanded view (track → all its albums via album_map) ─────
    ts_for_album = track_summary.drop(columns=["album_name"])
    track_albums_expanded = ts_for_album.merge(album_map, on="track_id", how="left")
    track_albums_expanded["album_list"] = track_albums_expanded["album_list"].apply(
        lambda x: x if isinstance(x, list) else []
    )
    track_per_album = track_albums_expanded.explode("album_list")
    track_per_album = track_per_album.dropna(subset=["album_list"])
    track_per_album = track_per_album.rename(columns={"album_list": "album_name"})

    # Normalize album names via release groups
    track_per_album = _normalize_album_column(
        track_per_album,
        dedup_cols=["track_id", "album_name", "artist_name"],
    )

    # ── Album track counts ─────────────────────────────────────────────
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
        lambda r: (
            track_per_album[
                (track_per_album["album_name"] == r["album_name"])
                & (track_per_album["artist_name"] == r["artist_name"])
            ]
            .sort_values("peak_position")
            .iloc[0]["track_name"]
        ),
        axis=1,
    )

    # Album weeks at #1
    album_weeks_no1 = (
        track_per_album.groupby(["album_name", "artist_name"])["weeks_at_no1"].sum().reset_index()
    )
    album_track_counts = album_track_counts.merge(
        album_weeks_no1, on=["album_name", "artist_name"], how="left"
    )

    # Album #1 weeks (from weekly_album)
    album_no1 = (
        weekly_album[weekly_album["rank"] == 1]
        .groupby(["album_name", "artist_name"])
        .agg(
            album_chart_no1_weeks=("billboard_week", "nunique"),
        )
        .reset_index()
    )
    album_track_counts = album_track_counts.merge(
        album_no1, on=["album_name", "artist_name"], how="left"
    )
    album_track_counts["album_chart_no1_weeks"] = (
        album_track_counts["album_chart_no1_weeks"].fillna(0).astype(int)
    )

    # ── Enrich track artist_name with featured artists ────────────────────
    weekly = enrich_track_artist_names(weekly)
    track_summary = enrich_track_artist_names(track_summary)

    # ── Power scores (compute before records to avoid double work) ──────
    power_scores = compute_power_scores(weekly, bb_top_n)
    album_power_scores = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_scores = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    # ── Records ────────────────────────────────────────────────────────
    from backend.domains.billboard.records import (  # noqa: E402
        _add_cover_urls,
        _serialize_records,
        compute_records,
    )

    records = compute_records(
        weekly,
        track_summary,
        bb_top_n,
        weekly_album,
        weekly_artist,
        track_power_scores=power_scores,
        album_power_scores=album_power_scores,
        artist_power_scores=artist_power_scores,
    )

    # ── Enrich with cover URLs ───────────────────────────────────────
    weekly, weekly_album, weekly_artist = _add_cover_urls(weekly, weekly_album, weekly_artist)

    # ── Convert to JSON-safe format ────────────────────────────────────
    date_cols_week = ["billboard_week", "first_week", "last_week", "first_peak_week"]

    result = {
        "meta": {
            "total_weeks": len(all_weeks_asc),
            "total_filtered_records": int(len(df_filtered)),
            "all_weeks_asc": [w.isoformat() for w in all_weeks_asc],
            "all_weeks_desc": [w.isoformat() for w in all_weeks_desc],
            "dow_name": DOW_NAMES[bb_week_start_dow],
            "dow_short": DOW_SHORT[bb_week_start_dow],
            "top_n": bb_top_n,
            "album_top_n": bb_album_top_n,
            "artist_top_n": bb_artist_top_n,
            "week_start_dow": bb_week_start_dow,
            "week_start_hour": bb_week_start_hour,
        },
        "weekly": _df_to_json(weekly, date_cols_week),
        "weekly_album": _df_to_json(weekly_album, ["billboard_week"]),
        "weekly_artist": _df_to_json(weekly_artist, ["billboard_week"]),
        "track_summary": _df_to_json(track_summary, date_cols_week),
        "artist_summary": _df_to_json(artist_summary, date_cols_week),
        "artist_track_counts": _df_to_json(artist_track_counts),
        "album_track_counts": _df_to_json(album_track_counts),
        "track_per_album": _df_to_json(track_per_album, date_cols_week),
        "records": _serialize_records(records),
        "power_scores": _df_to_json(power_scores),
        "album_power_scores": _df_to_json(album_power_scores),
        "artist_power_scores": _df_to_json(artist_power_scores),
    }

    return result


def compute_billboard_data(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute all Billboard data with normalized cache keys."""
    return _compute_billboard_data_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


compute_billboard_data.cache_clear = _compute_billboard_data_cached.cache_clear  # type: ignore[attr-defined]
compute_billboard_data.cache_info = _compute_billboard_data_cached.cache_info  # type: ignore[attr-defined]


# ═══════════════════════════════════════════════════════════════════════════
# Staged computation functions — independent @lru_cache per data slice
# ═══════════════════════════════════════════════════════════════════════════


def _load_and_rank(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Shared helper: load raw data, apply filters, compute weekly rankings.

    NOT cached (returns mutable DataFrames), but inner data loading functions
    (load_billboard_raw, _try_load_from_agg) are independently cached.

    Returns (weekly, weekly_album, weekly_artist, all_weeks_asc, all_weeks_desc, df_filtered).
    """
    df_raw = load_billboard_raw(min_ms, music_only, bb_week_start_dow, bb_week_start_hour)

    df_raw = df_raw.copy()
    df_raw["_year"] = df_raw["billboard_week"].apply(lambda x: x.year)
    if year_start is not None:
        df_raw = df_raw[df_raw["_year"] >= year_start]
    if year_end is not None:
        df_raw = df_raw[df_raw["_year"] <= year_end]
    df_filtered = df_raw.copy()

    all_weeks_asc = sorted(df_filtered["billboard_week"].unique().tolist())
    all_weeks_desc = sorted(all_weeks_asc, reverse=True)

    _agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(
        min_ms, music_only, bb_week_start_dow, bb_week_start_hour
    )

    if _agg_tracks is not None:
        _agg_tracks = _agg_tracks[
            pd.to_datetime(_agg_tracks["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_albums = _agg_albums[
            pd.to_datetime(_agg_albums["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_artists = _agg_artists[
            pd.to_datetime(_agg_artists["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]

    weekly = compute_weekly_rankings(df_filtered, bb_top_n, pre_agg=_agg_tracks)
    weekly_album = compute_album_weekly_rankings(df_filtered, bb_album_top_n, pre_agg=_agg_albums)

    if _agg_artists is not None:
        weekly_artist = compute_artist_weekly_rankings(
            df_filtered, bb_artist_top_n, pre_agg=_agg_artists
        )
    else:
        df_artists = load_billboard_raw_for_artists(
            min_ms, music_only, bb_week_start_dow, bb_week_start_hour
        )
        df_artists = df_artists.copy()
        df_artists["_year"] = df_artists["billboard_week"].apply(lambda x: x.year)
        if year_start is not None:
            df_artists = df_artists[df_artists["_year"] >= year_start]
        if year_end is not None:
            df_artists = df_artists[df_artists["_year"] <= year_end]
        weekly_artist = compute_artist_weekly_rankings(df_artists, bb_artist_top_n)

    # Patch tracks_count from weekly when using pre-agg
    if _agg_tracks is not None:
        _album_tc = (
            weekly.groupby(["billboard_week", "album_name", "artist_name"])
            .agg(tracks_count=("track_id", "nunique"))
            .reset_index()
        )
        _album_tc = _normalize_album_column(
            _album_tc, dedup_cols=["billboard_week", "album_name", "artist_name"]
        )
        _album_tc = (
            _album_tc.groupby(["billboard_week", "album_name", "artist_name"])
            .agg(tracks_count=("tracks_count", "sum"))
            .reset_index()
        )
        weekly_album = weekly_album.drop(columns=["tracks_count"], errors="ignore").merge(
            _album_tc, on=["billboard_week", "album_name", "artist_name"], how="left"
        )
        weekly_album["tracks_count"] = weekly_album["tracks_count"].fillna(0).astype(int)

        _artist_tc = (
            weekly.groupby(["billboard_week", "artist_name"])
            .agg(tracks_count=("track_id", "nunique"))
            .reset_index()
        )
        weekly_artist = weekly_artist.drop(columns=["tracks_count"], errors="ignore").merge(
            _artist_tc, on=["billboard_week", "artist_name"], how="left"
        )
        weekly_artist["tracks_count"] = weekly_artist["tracks_count"].fillna(0).astype(int)

    # Albums count per artist from album chart
    _artist_ac = (
        weekly_album.groupby(["billboard_week", "artist_name"])
        .agg(albums_count=("album_name", "nunique"))
        .reset_index()
    )
    weekly_artist = weekly_artist.merge(
        _artist_ac, on=["billboard_week", "artist_name"], how="left"
    )
    weekly_artist["albums_count"] = weekly_artist["albums_count"].fillna(0).astype(int)

    # Running metrics
    weekly = _add_running_metrics(weekly, ["track_id"])
    weekly_album = _add_running_metrics(weekly_album, ["artist_name", "album_name"])
    weekly_artist = _add_running_metrics(weekly_artist, ["artist_name"])

    return weekly, weekly_album, weekly_artist, all_weeks_asc, all_weeks_desc, df_filtered


@lru_cache(maxsize=4)
def _compute_weekly_data_cached(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute weekly rankings + meta. Returns JSON-safe dict."""
    weekly, weekly_album, weekly_artist, all_weeks_asc, all_weeks_desc, df_filtered = (
        _load_and_rank(
            min_ms,
            music_only,
            bb_top_n,
            bb_album_top_n,
            bb_artist_top_n,
            bb_week_start_dow,
            bb_week_start_hour,
            year_start,
            year_end,
        )
    )

    from backend.domains.billboard.records import _add_cover_urls  # noqa: E402

    weekly, weekly_album, weekly_artist = _add_cover_urls(weekly, weekly_album, weekly_artist)
    weekly = enrich_track_artist_names(weekly)

    date_cols_week = ["billboard_week"]
    return {
        "meta": {
            "total_weeks": len(all_weeks_asc),
            "total_filtered_records": int(len(df_filtered)),
            "all_weeks_asc": [w.isoformat() for w in all_weeks_asc],
            "all_weeks_desc": [w.isoformat() for w in all_weeks_desc],
            "dow_name": DOW_NAMES[bb_week_start_dow],
            "dow_short": DOW_SHORT[bb_week_start_dow],
            "top_n": bb_top_n,
            "album_top_n": bb_album_top_n,
            "artist_top_n": bb_artist_top_n,
            "week_start_dow": bb_week_start_dow,
            "week_start_hour": bb_week_start_hour,
        },
        "weekly": _df_to_json(weekly, date_cols_week),
        "weekly_album": _df_to_json(weekly_album, date_cols_week),
        "weekly_artist": _df_to_json(weekly_artist, date_cols_week),
    }


@lru_cache(maxsize=4)
def _compute_power_scores_cached(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute power scores for tracks, albums, and artists. Returns JSON-safe dict."""
    weekly, weekly_album, weekly_artist, *_ = _load_and_rank(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )

    weekly = enrich_track_artist_names(weekly)

    power_scores = compute_power_scores(weekly, bb_top_n)
    album_power_scores = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_scores = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    return {
        "power_scores": _df_to_json(power_scores),
        "album_power_scores": _df_to_json(album_power_scores),
        "artist_power_scores": _df_to_json(artist_power_scores),
    }


@lru_cache(maxsize=4)
def _compute_summaries_cached(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute track/artist/album summaries. Returns JSON-safe dict."""
    weekly, weekly_album, weekly_artist, *_all_weeks, df_filtered = _load_and_rank(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )

    album_map = load_track_album_map()
    date_cols_week = ["billboard_week", "first_week", "last_week", "first_peak_week"]

    # Track summary
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

    track_total_plays = (
        df_filtered.groupby("track_id").agg(total_plays=("ms_played", "count")).reset_index()
    )
    track_summary = track_summary.merge(track_total_plays, on="track_id", how="left")

    weeks_at_no1_df = (
        weekly[weekly["rank"] == 1]
        .groupby("track_id")
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
    )
    track_summary = track_summary.merge(weeks_at_no1_df, on="track_id", how="left")
    track_summary["weeks_at_no1"] = track_summary["weeks_at_no1"].fillna(0).astype(int)

    first_peak = weekly.merge(track_summary[["track_id", "peak_position"]], on="track_id")
    first_peak = first_peak[first_peak["rank"] == first_peak["peak_position"]]
    first_peak = first_peak.groupby("track_id")["billboard_week"].min().reset_index()
    first_peak.columns = ["track_id", "first_peak_week"]
    track_summary = track_summary.merge(first_peak, on="track_id", how="left")
    track_summary["is_debut_no1"] = (track_summary["peak_position"] == 1) & (
        track_summary["first_week"] == track_summary["first_peak_week"]
    )

    # Artist summary
    weekly_fanned = fan_out_weekly_for_artists(weekly)
    artist_summary = (
        weekly_fanned.groupby(["artist_name", "track_id", "track_name", "album_name"])
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

    # Artist track counts
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
        lambda a: (
            artist_summary[artist_summary["artist_name"] == a]
            .sort_values("peak_position")
            .iloc[0]["track_name"]
        )
    )
    artist_weeks_no1 = track_summary.groupby("artist_name")["weeks_at_no1"].sum().reset_index()
    artist_track_counts = artist_track_counts.merge(artist_weeks_no1, on="artist_name", how="left")

    album_no1_artist = (
        weekly_album[weekly_album["rank"] == 1]
        .groupby("artist_name")
        .agg(
            num_no1_albums=("album_name", "nunique"), album_no1_weeks=("billboard_week", "nunique")
        )
        .reset_index()
    )
    artist_track_counts = artist_track_counts.merge(album_no1_artist, on="artist_name", how="left")
    artist_track_counts["num_no1_albums"] = (
        artist_track_counts["num_no1_albums"].fillna(0).astype(int)
    )
    artist_track_counts["album_no1_weeks"] = (
        artist_track_counts["album_no1_weeks"].fillna(0).astype(int)
    )

    artist_no1_weeks = (
        weekly_artist[weekly_artist["rank"] == 1]
        .groupby("artist_name")
        .agg(artist_chart_no1_weeks=("billboard_week", "nunique"))
        .reset_index()
    )
    artist_track_counts = artist_track_counts.merge(artist_no1_weeks, on="artist_name", how="left")
    artist_track_counts["artist_chart_no1_weeks"] = (
        artist_track_counts["artist_chart_no1_weeks"].fillna(0).astype(int)
    )

    # Album track counts
    ts_for_album = track_summary.drop(columns=["album_name"])
    track_albums_expanded = ts_for_album.merge(album_map, on="track_id", how="left")
    track_albums_expanded["album_list"] = track_albums_expanded["album_list"].apply(
        lambda x: x if isinstance(x, list) else []
    )
    track_per_album = track_albums_expanded.explode("album_list")
    track_per_album = track_per_album.dropna(subset=["album_list"])
    track_per_album = track_per_album.rename(columns={"album_list": "album_name"})
    track_per_album = _normalize_album_column(
        track_per_album, dedup_cols=["track_id", "album_name", "artist_name"]
    )

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
        lambda r: (
            track_per_album[
                (track_per_album["album_name"] == r["album_name"])
                & (track_per_album["artist_name"] == r["artist_name"])
            ]
            .sort_values("peak_position")
            .iloc[0]["track_name"]
        ),
        axis=1,
    )

    album_weeks_no1 = (
        track_per_album.groupby(["album_name", "artist_name"])["weeks_at_no1"].sum().reset_index()
    )
    album_track_counts = album_track_counts.merge(
        album_weeks_no1, on=["album_name", "artist_name"], how="left"
    )

    album_no1 = (
        weekly_album[weekly_album["rank"] == 1]
        .groupby(["album_name", "artist_name"])
        .agg(album_chart_no1_weeks=("billboard_week", "nunique"))
        .reset_index()
    )
    album_track_counts = album_track_counts.merge(
        album_no1, on=["album_name", "artist_name"], how="left"
    )
    album_track_counts["album_chart_no1_weeks"] = (
        album_track_counts["album_chart_no1_weeks"].fillna(0).astype(int)
    )

    track_summary = enrich_track_artist_names(track_summary)

    return {
        "track_summary": _df_to_json(track_summary, date_cols_week),
        "artist_summary": _df_to_json(artist_summary, date_cols_week),
        "album_track_counts": _df_to_json(album_track_counts),
        "artist_track_counts": _df_to_json(artist_track_counts),
    }


@lru_cache(maxsize=4)
def _compute_records_cached(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute Billboard records. Returns JSON-safe dict."""
    weekly, weekly_album, weekly_artist, *_all_weeks, df_filtered = _load_and_rank(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )

    # Compute track_summary inline (needed by records)
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
    track_total_plays = (
        df_filtered.groupby("track_id").agg(total_plays=("ms_played", "count")).reset_index()
    )
    track_summary = track_summary.merge(track_total_plays, on="track_id", how="left")
    weeks_at_no1_df = (
        weekly[weekly["rank"] == 1]
        .groupby("track_id")
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
    )
    track_summary = track_summary.merge(weeks_at_no1_df, on="track_id", how="left")
    track_summary["weeks_at_no1"] = track_summary["weeks_at_no1"].fillna(0).astype(int)
    first_peak = weekly.merge(track_summary[["track_id", "peak_position"]], on="track_id")
    first_peak = first_peak[first_peak["rank"] == first_peak["peak_position"]]
    first_peak = first_peak.groupby("track_id")["billboard_week"].min().reset_index()
    first_peak.columns = ["track_id", "first_peak_week"]
    track_summary = track_summary.merge(first_peak, on="track_id", how="left")

    # Compute power_scores inline
    power_scores = compute_power_scores(weekly, bb_top_n)
    album_power_scores = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_scores = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    weekly = enrich_track_artist_names(weekly)
    track_summary = enrich_track_artist_names(track_summary)

    from backend.domains.billboard.records import _serialize_records, compute_records  # noqa: E402

    records = compute_records(
        weekly,
        track_summary,
        bb_top_n,
        weekly_album=weekly_album,
        weekly_artist=weekly_artist,
        track_power_scores=power_scores,
        album_power_scores=album_power_scores,
        artist_power_scores=artist_power_scores,
    )

    return {"records": _serialize_records(records)}


# Public wrappers with normalized cache keys


def compute_weekly_data(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute weekly rankings + meta only (no summaries, no records)."""
    return _compute_weekly_data_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


def compute_power_scores_staged(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute power scores only (track, album, artist)."""
    return _compute_power_scores_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


def compute_summaries_staged(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute summaries only (track_summary, artist_summary, album/artist track counts)."""
    return _compute_summaries_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


def compute_records_staged(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute records only."""
    return _compute_records_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


compute_weekly_data.cache_clear = _compute_weekly_data_cached.cache_clear  # type: ignore[attr-defined]
compute_power_scores_staged.cache_clear = _compute_power_scores_cached.cache_clear  # type: ignore[attr-defined]
compute_summaries_staged.cache_clear = _compute_summaries_cached.cache_clear  # type: ignore[attr-defined]
compute_records_staged.cache_clear = _compute_records_cached.cache_clear  # type: ignore[attr-defined]

# ── Cache registration ─────────────────────────────────────────────────
from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("billboard", "full_data", _compute_billboard_data_cached)
register_lru("billboard", "weekly", _compute_weekly_data_cached)
register_lru("billboard", "power_scores", _compute_power_scores_cached)
register_lru("billboard", "summaries", _compute_summaries_cached)
register_lru("billboard", "records", _compute_records_cached)

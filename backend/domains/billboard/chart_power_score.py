"""Power score computation for tracks, albums, and artists."""

import math

import numpy as np

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


def _base_score(rank):
    return max(1, round(_RANK1_BASE * (_BASE_DECAY ** (rank - 1))))


def _competition_factor(week_total_plays, global_baseline):
    ratio = week_total_plays / global_baseline if global_baseline else 1.0
    return max(_COMP_RANGE[0], min(_COMP_RANGE[1], math.sqrt(ratio)))


def _indiv_factor_no1(plays, runner_up_plays):
    if not runner_up_plays or runner_up_plays <= 0:
        return 1.0 + _INDIV_GAP_RANGE[1]
    ratio = plays / runner_up_plays
    bonus = 0.5 * math.log2(ratio) if ratio > 0 else 0
    return 1.0 + max(_INDIV_GAP_RANGE[0], min(_INDIV_GAP_RANGE[1], bonus))


def _indiv_factor_non_no1(plays, week_median):
    if not week_median or week_median <= 0:
        return 1.0
    ratio = plays / week_median
    bonus = 0.4 * math.log2(ratio) if ratio > 0 else 0
    return 1.0 + max(_INDIV_RANGE[0], min(_INDIV_RANGE[1], bonus))


def compute_power_scores(weekly, top_n):
    """Compute comprehensive power scores for all tracks."""
    w = weekly.copy()

    week_stats = (
        w.groupby("billboard_week")
        .agg(week_total=("play_count", "sum"), week_median=("play_count", "median"))
        .reset_index()
    )
    global_baseline = week_stats["week_total"].median() if not week_stats.empty else 1

    runner_up_map = w[w["rank"] == 2].set_index("billboard_week")["play_count"].to_dict()

    w = w.merge(week_stats, on="billboard_week", how="left")
    w["_base"] = w["rank"].apply(_base_score)
    w["_comp"] = w.apply(lambda r: _competition_factor(r["week_total"], global_baseline), axis=1)
    w["_indiv"] = w.apply(
        lambda r: (
            _indiv_factor_no1(r["play_count"], runner_up_map.get(r["billboard_week"]))
            if r["rank"] == 1
            else _indiv_factor_non_no1(r["play_count"], r["week_median"])
        ),
        axis=1,
    )
    w["_weekly"] = w["_base"] * w["_comp"] * w["_indiv"]

    weekly_scores = (
        w.groupby("track_id")
        .agg(
            raw_score=("_weekly", "sum"),
            weeks_on_chart=("billboard_week", "nunique"),
            peak_position=("rank", "min"),
            weeks_top5=("rank", lambda x: (x <= 5).sum()),
            weeks_top10=("rank", lambda x: (x <= 10).sum()),
            weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
            is_debut_no1=("rank", lambda x: (x.iloc[0] == 1) if len(x) > 0 else False),
        )
        .reset_index()
    )

    weekly_scores["longevity_bonus"] = (
        np.sqrt(weekly_scores["weeks_on_chart"].clip(lower=1)) * _LONGEVITY_FACTOR
    )
    weekly_scores["peak_bonus"] = weekly_scores["peak_position"].map(
        lambda p: _PEAK_BONUS.get(p, 0)
    )
    weekly_scores["debut_bonus"] = weekly_scores["is_debut_no1"].astype(int) * _DEBUT_NO1_BONUS
    weekly_scores["power_score"] = (
        (
            weekly_scores["raw_score"]
            + weekly_scores["longevity_bonus"]
            + weekly_scores["peak_bonus"]
            + weekly_scores["debut_bonus"]
        )
        .round()
        .astype(int)
    )

    dims = w[["track_id", "track_name", "artist_name"]].drop_duplicates(subset=["track_id"])
    result = weekly_scores.merge(dims, on="track_id", how="left")
    result = result.sort_values("power_score", ascending=False).reset_index(drop=True)
    result["power_rank"] = range(1, len(result) + 1)

    return result[
        [
            "track_id",
            "track_name",
            "artist_name",
            "power_score",
            "power_rank",
            "peak_position",
            "weeks_on_chart",
            "weeks_top5",
            "weeks_top10",
            "weeks_at_peak",
        ]
    ]


def compute_album_power_scores(weekly_album, top_n):
    """Compute power scores for albums (no Top 5/10 bonuses, uses #1 bonus)."""
    wa = weekly_album.copy()

    week_stats = (
        wa.groupby("billboard_week")
        .agg(week_total=("play_count", "sum"), week_median=("play_count", "median"))
        .reset_index()
    )
    global_baseline = week_stats["week_total"].median() if not week_stats.empty else 1

    runner_up_map = wa[wa["rank"] == 2].set_index("billboard_week")["play_count"].to_dict()

    wa = wa.merge(week_stats, on="billboard_week", how="left")
    wa["_base"] = wa["rank"].apply(_base_score)
    wa["_comp"] = wa.apply(lambda r: _competition_factor(r["week_total"], global_baseline), axis=1)
    wa["_indiv"] = wa.apply(
        lambda r: (
            _indiv_factor_no1(r["play_count"], runner_up_map.get(r["billboard_week"]))
            if r["rank"] == 1
            else _indiv_factor_non_no1(r["play_count"], r["week_median"])
        ),
        axis=1,
    )
    wa["_weekly"] = wa["_base"] * wa["_comp"] * wa["_indiv"]

    weekly_scores = (
        wa.groupby(["album_name", "artist_name"])
        .agg(
            raw_score=("_weekly", "sum"),
            weeks_on_chart=("billboard_week", "nunique"),
            peak_position=("rank", "min"),
            weeks_top5=("rank", lambda x: (x <= 5).sum()),
            weeks_top10=("rank", lambda x: (x <= 10).sum()),
            weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
        )
        .reset_index()
    )

    weekly_scores["longevity_bonus"] = (
        np.sqrt(weekly_scores["weeks_on_chart"].clip(lower=1)) * _LONGEVITY_FACTOR
    )
    weekly_scores["peak_bonus"] = weekly_scores["peak_position"].map(
        lambda p: _PEAK_BONUS.get(p, 0)
    )
    # Album #1 weekly bonus
    no1_weeks = (
        wa[wa["rank"] == 1]
        .groupby(["album_name", "artist_name"])
        .size()
        .reset_index(name="no1_weeks")
    )
    weekly_scores = weekly_scores.merge(no1_weeks, on=["album_name", "artist_name"], how="left")
    weekly_scores["no1_weeks"] = weekly_scores["no1_weeks"].fillna(0).astype(int)
    weekly_scores["no1_bonus"] = weekly_scores["no1_weeks"] * _TOP1_BONUS
    weekly_scores["power_score"] = (
        (
            weekly_scores["raw_score"]
            + weekly_scores["longevity_bonus"]
            + weekly_scores["peak_bonus"]
            + weekly_scores["no1_bonus"]
        )
        .round()
        .astype(int)
    )

    result = weekly_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    result["power_rank"] = range(1, len(result) + 1)
    return result[
        [
            "album_name",
            "artist_name",
            "power_score",
            "power_rank",
            "peak_position",
            "weeks_on_chart",
            "weeks_top5",
            "weeks_top10",
            "weeks_at_peak",
        ]
    ]


def compute_artist_power_scores(weekly_artist, top_n):
    """Compute power scores for artists."""
    war = weekly_artist.copy()

    week_stats = (
        war.groupby("billboard_week")
        .agg(week_total=("play_count", "sum"), week_median=("play_count", "median"))
        .reset_index()
    )
    global_baseline = week_stats["week_total"].median() if not week_stats.empty else 1

    runner_up_map = war[war["rank"] == 2].set_index("billboard_week")["play_count"].to_dict()

    war = war.merge(week_stats, on="billboard_week", how="left")
    war["_base"] = war["rank"].apply(_base_score)
    war["_comp"] = war.apply(
        lambda r: _competition_factor(r["week_total"], global_baseline), axis=1
    )
    war["_indiv"] = war.apply(
        lambda r: (
            _indiv_factor_no1(r["play_count"], runner_up_map.get(r["billboard_week"]))
            if r["rank"] == 1
            else _indiv_factor_non_no1(r["play_count"], r["week_median"])
        ),
        axis=1,
    )
    war["_weekly"] = war["_base"] * war["_comp"] * war["_indiv"]

    weekly_scores = (
        war.groupby("artist_name")
        .agg(
            raw_score=("_weekly", "sum"),
            weeks_on_chart=("billboard_week", "nunique"),
            peak_position=("rank", "min"),
            weeks_top5=("rank", lambda x: (x <= 5).sum()),
            weeks_top10=("rank", lambda x: (x <= 10).sum()),
            weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
        )
        .reset_index()
    )

    weekly_scores["longevity_bonus"] = (
        np.sqrt(weekly_scores["weeks_on_chart"].clip(lower=1)) * _LONGEVITY_FACTOR
    )
    weekly_scores["peak_bonus"] = weekly_scores["peak_position"].map(
        lambda p: _PEAK_BONUS.get(p, 0)
    )
    no1_weeks = war[war["rank"] == 1].groupby("artist_name").size().reset_index(name="no1_weeks")
    weekly_scores = weekly_scores.merge(no1_weeks, on="artist_name", how="left")
    weekly_scores["no1_weeks"] = weekly_scores["no1_weeks"].fillna(0).astype(int)
    weekly_scores["no1_bonus"] = weekly_scores["no1_weeks"] * _TOP1_BONUS
    weekly_scores["power_score"] = (
        (
            weekly_scores["raw_score"]
            + weekly_scores["longevity_bonus"]
            + weekly_scores["peak_bonus"]
            + weekly_scores["no1_bonus"]
        )
        .round()
        .astype(int)
    )

    result = weekly_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    result["power_rank"] = range(1, len(result) + 1)
    return result[
        [
            "artist_name",
            "power_score",
            "power_rank",
            "peak_position",
            "weeks_on_chart",
            "weeks_top5",
            "weeks_top10",
            "weeks_at_peak",
        ]
    ]

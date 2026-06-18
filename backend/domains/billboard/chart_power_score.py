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


def _score_ranked_rows(df):
    scored = df.copy()

    week_stats = (
        scored.groupby("billboard_week")
        .agg(week_total=("play_count", "sum"), week_median=("play_count", "median"))
        .reset_index()
    )
    global_baseline = week_stats["week_total"].median() if not week_stats.empty else 1
    runner_up_map = scored[scored["rank"] == 2].set_index("billboard_week")["play_count"].to_dict()

    scored = scored.merge(week_stats, on="billboard_week", how="left")

    ranks = scored["rank"].astype(float).to_numpy()
    plays = scored["play_count"].astype(float).to_numpy()
    week_total = scored["week_total"].astype(float).to_numpy()
    week_median = scored["week_median"].astype(float).to_numpy()
    runner_up = scored["billboard_week"].map(runner_up_map).astype(float).to_numpy()

    scored["_base"] = np.maximum(1, np.rint(_RANK1_BASE * np.power(_BASE_DECAY, ranks - 1)))

    if global_baseline:
        scored["_comp"] = np.clip(np.sqrt(week_total / global_baseline), *_COMP_RANGE)
    else:
        scored["_comp"] = 1.0

    indiv = np.ones(len(scored))
    is_no1 = ranks == 1
    valid_runner = is_no1 & np.isfinite(runner_up) & (runner_up > 0) & (plays > 0)
    indiv[is_no1] = 1.0 + _INDIV_GAP_RANGE[1]
    if valid_runner.any():
        no1_bonus = 0.5 * np.log2(plays[valid_runner] / runner_up[valid_runner])
        indiv[valid_runner] = 1.0 + np.clip(no1_bonus, *_INDIV_GAP_RANGE)

    valid_median = (~is_no1) & np.isfinite(week_median) & (week_median > 0) & (plays > 0)
    if valid_median.any():
        non_no1_bonus = 0.4 * np.log2(plays[valid_median] / week_median[valid_median])
        indiv[valid_median] = 1.0 + np.clip(non_no1_bonus, *_INDIV_RANGE)

    scored["_indiv"] = indiv
    scored["_weekly"] = scored["_base"] * scored["_comp"] * scored["_indiv"]
    scored["_top5"] = (scored["rank"] <= 5).astype(int)
    scored["_top10"] = (scored["rank"] <= 10).astype(int)
    scored["_is_no1"] = is_no1.astype(int)
    return scored


def _normalize_group_cols(group_cols):
    return [group_cols] if isinstance(group_cols, str) else list(group_cols)


def _aggregate_scored_rows(scored, group_cols):
    keys = _normalize_group_cols(group_cols)
    scored = scored.copy()
    scored["_at_peak"] = scored["rank"].eq(scored.groupby(keys)["rank"].transform("min"))
    return (
        scored.groupby(keys, sort=False)
        .agg(
            raw_score=("_weekly", "sum"),
            weeks_on_chart=("billboard_week", "nunique"),
            peak_position=("rank", "min"),
            weeks_top5=("_top5", "sum"),
            weeks_top10=("_top10", "sum"),
            weeks_at_peak=("_at_peak", "sum"),
        )
        .reset_index()
    )


def compute_power_scores(weekly, top_n):
    """Compute comprehensive power scores for all tracks."""
    w = _score_ranked_rows(weekly)
    weekly_scores = _aggregate_scored_rows(w, "track_id")
    first_rank = w.groupby("track_id", sort=False)["rank"].first().reset_index(name="_first_rank")
    weekly_scores = weekly_scores.merge(first_rank, on="track_id", how="left")

    weekly_scores["longevity_bonus"] = (
        np.sqrt(weekly_scores["weeks_on_chart"].clip(lower=1)) * _LONGEVITY_FACTOR
    )
    weekly_scores["peak_bonus"] = weekly_scores["peak_position"].map(_PEAK_BONUS).fillna(0)
    weekly_scores["debut_bonus"] = weekly_scores["_first_rank"].eq(1).astype(int) * _DEBUT_NO1_BONUS
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
    wa = _score_ranked_rows(weekly_album)
    group_cols = ["album_name", "artist_name"]
    weekly_scores = _aggregate_scored_rows(wa, group_cols)

    weekly_scores["longevity_bonus"] = (
        np.sqrt(weekly_scores["weeks_on_chart"].clip(lower=1)) * _LONGEVITY_FACTOR
    )
    weekly_scores["peak_bonus"] = weekly_scores["peak_position"].map(_PEAK_BONUS).fillna(0)
    # Album #1 weekly bonus
    no1_weeks = wa.groupby(group_cols, sort=False)["_is_no1"].sum().reset_index(name="no1_weeks")
    weekly_scores = weekly_scores.merge(no1_weeks, on=group_cols, how="left")
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
    war = _score_ranked_rows(weekly_artist)
    weekly_scores = _aggregate_scored_rows(war, "artist_name")

    weekly_scores["longevity_bonus"] = (
        np.sqrt(weekly_scores["weeks_on_chart"].clip(lower=1)) * _LONGEVITY_FACTOR
    )
    weekly_scores["peak_bonus"] = weekly_scores["peak_position"].map(_PEAK_BONUS).fillna(0)
    no1_weeks = (
        war.groupby("artist_name", sort=False)["_is_no1"].sum().reset_index(name="no1_weeks")
    )
    weekly_scores = weekly_scores.merge(no1_weeks, on="artist_name", how="left")
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

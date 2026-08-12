"""Deterministic listening-habit facts with explicit comparison baselines."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from backend.models.yearly_review import (
    YearlyHeadline,
    YearlyHighlightCandidate,
    YearlyListeningLifeChapter,
    YearlyMetric,
    YearlyReviewCoverage,
)


def _metric(key: str, label: str, value: int | float, unit: str | None = None) -> YearlyMetric:
    return YearlyMetric(key=key, label=label, value=value, unit=unit)


def _headline(
    headline_id: str,
    title: str,
    statement: str,
    metrics: Sequence[YearlyMetric],
    *source_refs: str,
) -> YearlyHeadline:
    return YearlyHeadline(
        headline_id=headline_id,
        title=title,
        statement=statement,
        evidence_grade="B",
        primary_metric=metrics[0] if metrics else None,
        source_refs=list(source_refs),
    )


def _hour_totals(stats: Mapping[str, Any]) -> dict[int, int]:
    return {
        int(row["hour"]): int(row.get("plays", 0)) for row in stats.get("hourly_distribution", [])
    }


def _weekday_totals(stats: Mapping[str, Any]) -> list[int]:
    return [int(row.get("plays", 0)) for row in stats.get("weekday_distribution", [])]


def _calendar_day_counts(
    coverage: YearlyReviewCoverage,
    event_frame: pd.DataFrame | None,
) -> tuple[int, int]:
    start = coverage.play.observed_start
    end = coverage.play.observed_end
    if (not start or not end) and event_frame is not None and not event_frame.empty:
        dates = pd.to_datetime(event_frame.get("ts_date"), errors="coerce").dropna()
        if not dates.empty:
            start = dates.min().date().isoformat()
            end = dates.max().date().isoformat()
    if not start or not end:
        return 0, 0
    days = pd.date_range(start=start, end=end, freq="D")
    weekday_days = int((days.dayofweek < 5).sum())
    return weekday_days, int(len(days) - weekday_days)


def _record_metric(
    candidates: Sequence[YearlyHighlightCandidate],
    pattern: str,
) -> tuple[YearlyHighlightCandidate, YearlyMetric] | None:
    for candidate in candidates:
        if pattern in candidate.record_key and candidate.eligible and candidate.primary_metric:
            return candidate, candidate.primary_metric
    return None


def build_listening_life(
    stats: Mapping[str, Any],
    coverage: YearlyReviewCoverage,
    *,
    baseline_stats: Mapping[str, Any] | None = None,
    play_rankings: Mapping[str, Any] | None = None,
    event_frame: pd.DataFrame | None = None,
    history_frame: pd.DataFrame | None = None,
    record_candidates: Sequence[YearlyHighlightCandidate] = (),
) -> YearlyListeningLifeChapter:
    summary = dict(stats.get("summary", {}))
    total_plays = int(summary.get("total_plays", 0))
    if total_plays <= 0:
        return YearlyListeningLifeChapter()

    metrics: list[YearlyMetric] = []
    observations: list[YearlyHeadline] = []
    hours = _hour_totals(stats)
    peak_hour = max(hours, key=lambda hour: (hours[hour], -hour)) if hours else 0
    peak_plays = hours.get(peak_hour, 0)
    average_hour = total_plays / 24
    peak_metrics = [
        _metric("peak_hour_plays", "高峰小时播放", peak_plays, "次"),
        _metric("average_hour_plays", "每小时平均播放", round(average_hour, 1), "次"),
    ]
    metrics.extend(peak_metrics)
    observations.append(
        _headline(
            "primary_listening_hour",
            "主要收听时段",
            f"{peak_hour:02d}:00–{(peak_hour + 1) % 24:02d}:00 是播放最集中的一小时，共记录 {peak_plays:,} 次有效播放。",
            peak_metrics,
            "stats.hourly_distribution",
        )
    )

    weekday = _weekday_totals(stats)
    if len(weekday) == 7:
        weekday_days, weekend_days = _calendar_day_counts(coverage, event_frame)
        weekday_daily = sum(weekday[:5]) / weekday_days if weekday_days else 0.0
        weekend_daily = sum(weekday[5:]) / weekend_days if weekend_days else 0.0
        ratio = round(weekend_daily / weekday_daily, 2) if weekday_daily else 0.0
        weekend_metrics = [
            _metric("weekday_daily_plays", "工作日平均播放", round(weekday_daily, 1), "次/日"),
            _metric("weekend_daily_plays", "周末平均播放", round(weekend_daily, 1), "次/日"),
            _metric("weekend_weekday_ratio", "周末/工作日", ratio, "倍"),
        ]
        metrics.extend(weekend_metrics)
        comparison = "高于" if ratio > 1.05 else "低于" if ratio < 0.95 else "接近"
        observations.append(
            _headline(
                "weekday_weekend_pattern",
                "工作日与周末",
                f"按每个自然日归一后，周末日均播放{comparison}工作日，比例为 {ratio:.2f} 倍。",
                weekend_metrics,
                "stats.weekday_distribution",
            )
        )

    late_night_plays = sum(hours.get(hour, 0) for hour in range(0, 6))
    late_night_pct = round(late_night_plays / total_plays * 100, 1)
    baseline_late_pct = None
    if baseline_stats:
        baseline_hours = _hour_totals(baseline_stats)
        baseline_total = int(dict(baseline_stats.get("summary", {})).get("total_plays", 0))
        if baseline_total:
            baseline_late_pct = round(
                sum(baseline_hours.get(hour, 0) for hour in range(0, 6)) / baseline_total * 100,
                1,
            )
    late_metrics = [
        YearlyMetric(
            key="late_night_share_pct",
            label="深夜播放占比",
            value=late_night_pct,
            unit="%",
            comparison_value=baseline_late_pct,
            comparison_label="可比基线" if baseline_late_pct is not None else None,
        ),
        _metric("late_night_plays", "深夜播放", late_night_plays, "次"),
    ]
    metrics.extend(late_metrics)
    statement = f"00:00–06:00 共 {late_night_plays:,} 次有效播放，占全年 {late_night_pct:.1f}%。"
    if baseline_late_pct is not None:
        statement += f" 可比基线为 {baseline_late_pct:.1f}%。"
    observations.append(
        _headline(
            "late_night_listening",
            "深夜收听",
            statement,
            late_metrics,
            "stats.hourly_distribution",
        )
    )

    charts = dict((play_rankings or {}).get("charts", {}))
    top_artist_rows = dict(charts.get("artist", {})).get("by_plays", [])
    if top_artist_rows:
        top = top_artist_rows[0]
        concentration = round(float(top.get("share_pct", 0)), 1)
        concentration_metrics = [
            _metric("top_artist_share_pct", "头部艺人份额", concentration, "%"),
            _metric("top_artist_plays", "头部艺人播放", int(top.get("plays", 0)), "次"),
        ]
        metrics.extend(concentration_metrics)
        observations.append(
            _headline(
                "artist_concentration",
                "艺人集中度",
                f"播放量最高艺人贡献全年 {concentration:.1f}% 的有效播放，共 {int(top.get('plays', 0)):,} 次。",
                concentration_metrics,
                "play_rankings.artist.by_plays.0",
            )
        )

    if event_frame is not None and not event_frame.empty:
        unique_tracks = int(event_frame["track_id"].nunique()) if "track_id" in event_frame else 0
        replay_rate = round(max(total_plays - unique_tracks, 0) / total_plays * 100, 1)
        replay_metrics = [
            _metric("replay_rate_pct", "复听事件占比", replay_rate, "%"),
            _metric("unique_tracks", "独立曲目", unique_tracks, "首"),
        ]
        metrics.extend(replay_metrics)
        observations.append(
            _headline(
                "replay_pattern",
                "复听与曲目宽度",
                f"在 {total_plays:,} 次播放中覆盖 {unique_tracks:,} 首曲目，其余 {replay_rate:.1f}% 为同年内重复播放事件。",
                replay_metrics,
                "event_frame.track_id",
            )
        )

        if history_frame is not None and not history_frame.empty and "track_id" in history_frame:
            annual_ids = set(event_frame["track_id"].dropna().astype(int))
            prior_dates = pd.to_datetime(history_frame["ts_date"], errors="coerce")
            annual_start = pd.to_datetime(event_frame["ts_date"], errors="coerce").min()
            prior_ids = set(
                history_frame.loc[prior_dates < annual_start, "track_id"].dropna().astype(int)
            )
            discovered = len(annual_ids - prior_ids)
            discovery_rate = round(discovered / max(len(annual_ids), 1) * 100, 1)
            discovery_metrics = [
                _metric("new_tracks", "首次发现曲目", discovered, "首"),
                _metric("new_track_rate_pct", "新曲目占比", discovery_rate, "%"),
            ]
            metrics.extend(discovery_metrics)
            observations.append(
                _headline(
                    "discovery_pattern",
                    "发现率",
                    f"全年听到的不同曲目中，有 {discovered:,} 首此前从未出现在个人历史，占 {discovery_rate:.1f}%。",
                    discovery_metrics,
                    "event_frame.track_id",
                    "history_frame.track_id",
                )
            )

    streak = _record_metric(record_candidates, "longevity.user_active_streak")
    if streak:
        candidate, streak_metric = streak
        observations.append(
            _headline(
                "active_listening_streak",
                "活跃连续期",
                f"年度播放记录中的最长活跃连续期为 {streak_metric.value}{streak_metric.unit or ''}。",
                [streak_metric],
                *candidate.source_refs,
            )
        )
        metrics.append(streak_metric)

    behavior = dict(stats.get("behavior_summary", {}))
    platform = str(behavior.get("primary_platform") or "")
    platform_rate = float(behavior.get("primary_platform_rate", 0))
    if platform and platform != "unknown" and platform_rate >= 60:
        platform_metrics = [
            _metric("primary_platform_rate", "主要平台占比", round(platform_rate, 1), "%"),
            _metric("total_plays", "有效播放", total_plays, "次"),
        ]
        observations.append(
            _headline(
                "primary_platform",
                "主要播放平台",
                f"{platform} 承载全年 {platform_rate:.1f}% 的有效播放。",
                platform_metrics,
                "stats.behavior_summary",
            )
        )
        metrics.extend(platform_metrics)

    # A longest-gap claim is intentionally absent unless import coverage can
    # independently prove completeness; this builder never infers it from silence.
    _ = coverage.play.import_coverage_status
    return YearlyListeningLifeChapter(metrics=metrics, observations=observations)

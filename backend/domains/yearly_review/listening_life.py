"""Deterministic listening-habit facts with explicit comparison baselines."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from backend.domains.yearly_review.entity_links import entity_ref_from_row
from backend.models.yearly_review import (
    YearlyEntityRef,
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
    entity_refs: Sequence[YearlyEntityRef] = (),
) -> YearlyHeadline:
    return YearlyHeadline(
        headline_id=headline_id,
        title=title,
        statement=statement,
        evidence_grade="B",
        primary_metric=metrics[0] if metrics else None,
        entity_refs=list(entity_refs),
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
    track_frame: pd.DataFrame | None = None,
    history_track_frame: pd.DataFrame | None = None,
    record_candidates: Sequence[YearlyHighlightCandidate] = (),
) -> YearlyListeningLifeChapter:
    summary = dict(stats.get("summary", {}))
    total_plays = int(summary.get("total_plays", 0))
    if total_plays <= 0:
        return YearlyListeningLifeChapter()

    complete = coverage.status == "complete"
    period = "全年" if complete else "今年截至目前"
    comparison_copy = "去年" if complete else "去年同期"
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
            f"{peak_hour:02d}–{(peak_hour + 1) % 24:02d} 点最常听歌，一共播放了 {peak_plays:,} 次。",
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
        comparison = "更多" if ratio > 1.05 else "更少" if ratio < 0.95 else "差不多"
        observations.append(
            _headline(
                "weekday_weekend_pattern",
                "工作日与周末",
                f"周末每天平均播放 {weekend_daily:.1f} 次，工作日为 {weekday_daily:.1f} 次，周末{comparison}。",
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
            comparison_label=comparison_copy if baseline_late_pct is not None else None,
        ),
        _metric("late_night_plays", "深夜播放", late_night_plays, "次"),
    ]
    metrics.extend(late_metrics)
    statement = f"凌晨 0–6 点一共播放 {late_night_plays:,} 次，占{period}的 {late_night_pct:.1f}%。"
    if baseline_late_pct is not None:
        direction = (
            "更多"
            if late_night_pct > baseline_late_pct
            else "更少"
            if late_night_pct < baseline_late_pct
            else "一样多"
        )
        statement += f" 比{comparison_copy}{direction}。"
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
        artist_plays = int(top.get("plays", 0))
        concentration = round(artist_plays / max(total_plays, 1) * 100, 1)
        concentration_metrics = [
            _metric("top_artist_share_pct", "含该艺人的播放占比", concentration, "%"),
            _metric("top_artist_plays", "包含该艺人的播放", artist_plays, "次"),
        ]
        metrics.extend(concentration_metrics)
        observations.append(
            _headline(
                "artist_concentration",
                "最常听的艺人",
                f"{period}有 {concentration:.1f}% 的播放包含 {top.get('artist_name')}，"
                f"一共 {artist_plays:,} 次。",
                concentration_metrics,
                "play_rankings.artist.by_plays.0",
                entity_refs=[ref] if (ref := entity_ref_from_row(top, "artist")) else [],
            )
        )

    annual_track_frame = (
        track_frame if track_frame is not None and not track_frame.empty else event_frame
    )
    full_track_frame = (
        history_track_frame
        if history_track_frame is not None and not history_track_frame.empty
        else history_frame
    )
    if annual_track_frame is not None and not annual_track_frame.empty:
        track_identity = (
            "canonical_track_id"
            if "canonical_track_id" in annual_track_frame.columns
            else "track_id"
        )
        unique_tracks = int(annual_track_frame[track_identity].nunique())
        replay_rate = round(max(total_plays - unique_tracks, 0) / total_plays * 100, 1)
        replay_metrics = [
            _metric("replay_rate_pct", "再次播放", replay_rate, "%"),
            _metric("unique_tracks", "听过曲目", unique_tracks, "首"),
        ]
        metrics.extend(replay_metrics)
        observations.append(
            _headline(
                "replay_pattern",
                "熟悉的歌，还是新鲜感",
                f"{period}听过 {unique_tracks:,} 首歌，其中 {replay_rate:.1f}% 的播放是在重听今年已经听过的歌。",
                replay_metrics,
                f"track_frame.{track_identity}",
            )
        )

        if full_track_frame is not None and not full_track_frame.empty:
            history_identity = (
                "canonical_track_id"
                if "canonical_track_id" in full_track_frame.columns
                else "track_id"
            )
            annual_ids = set(annual_track_frame[track_identity].dropna().astype(str))
            prior_dates = pd.to_datetime(full_track_frame["ts_date"], errors="coerce")
            annual_start = pd.to_datetime(annual_track_frame["ts_date"], errors="coerce").min()
            prior_ids = set(
                full_track_frame.loc[prior_dates < annual_start, history_identity]
                .dropna()
                .astype(str)
            )
            discovered = len(annual_ids - prior_ids)
            discovery_rate = round(discovered / max(len(annual_ids), 1) * 100, 1)
            discovery_metrics = [
                _metric("new_tracks", "第一次听到", discovered, "首"),
                _metric("new_track_rate_pct", "新歌占比", discovery_rate, "%"),
            ]
            metrics.extend(discovery_metrics)
            observations.append(
                _headline(
                    "discovery_pattern",
                    "今年认识的新歌",
                    f"{period}第一次听到 {discovered:,} 首歌，占所有不同曲目的 {discovery_rate:.1f}%。",
                    discovery_metrics,
                    f"track_frame.{track_identity}",
                    f"history_track_frame.{history_identity}",
                )
            )

    streak = _record_metric(record_candidates, "longevity.user_active_streak")
    if streak:
        candidate, streak_metric = streak
        streak_value = float(streak_metric.value)
        public_streak_metric = streak_metric.model_copy(
            update={
                "label": "最长连续活跃",
                "value": int(streak_value) if streak_value.is_integer() else round(streak_value, 1),
                "unit": "天",
            }
        )
        observations.append(
            _headline(
                "active_listening_streak",
                "活跃连续期",
                f"连续 {public_streak_metric.value} 天都有听歌记录，是{period}最长的一段。",
                [public_streak_metric],
                *candidate.source_refs,
            )
        )
        metrics.append(public_streak_metric)

    behavior = dict(stats.get("behavior_summary", {}))
    platform = str(behavior.get("primary_platform") or "")
    platform_name = {
        "ios": "iOS",
        "android": "Android",
        "desktop": "电脑",
        "web_player": "网页播放器",
    }.get(platform.casefold(), platform)
    platform_rate = float(behavior.get("primary_platform_rate", 0))
    if platform and platform != "unknown" and platform_rate >= 60:
        platform_metrics = [
            _metric("primary_platform_rate", "主要平台占比", round(platform_rate, 1), "%"),
            _metric("total_plays", "播放次数", total_plays, "次"),
        ]
        observations.append(
            _headline(
                "primary_platform",
                "主要播放平台",
                f"{period}有 {platform_rate:.1f}% 的音乐是在 {platform_name} 上播放的。",
                platform_metrics,
                "stats.behavior_summary",
            )
        )
        metrics.extend(platform_metrics)

    # A longest-gap claim is intentionally absent unless import coverage can
    # independently prove completeness; this builder never infers it from silence.
    _ = coverage.play.import_coverage_status
    return YearlyListeningLifeChapter(metrics=metrics, observations=observations)

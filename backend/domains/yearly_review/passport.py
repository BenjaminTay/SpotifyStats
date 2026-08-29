"""Report passport and deterministic annual headline selection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.models.yearly_review import (
    YearlyEntityRef,
    YearlyHeadline,
    YearlyMetric,
    YearlyReportPassport,
    YearlyReviewCoverage,
)


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _change(current: Any, baseline: Any) -> float | None:
    current_value = _number(current)
    baseline_value = _number(baseline)
    if current_value is None or baseline_value is None or baseline_value == 0:
        return None
    return round((current_value - baseline_value) / baseline_value * 100, 1)


def _comparison_label(coverage: YearlyReviewCoverage) -> str:
    return "比去年" if coverage.comparison.mode == "full_year" else "比去年同期"


def _comparison_window_kwargs(coverage: YearlyReviewCoverage) -> dict[str, str | None]:
    comparison = coverage.comparison
    return {
        "observed_start": comparison.current_start,
        "observed_end": comparison.current_end,
        "comparison_start": comparison.baseline_start or comparison.aligned_start,
        "comparison_end": comparison.baseline_end or comparison.aligned_end,
    }


def _leader_ref(row: Mapping[str, Any] | None, entity_type: str) -> YearlyEntityRef | None:
    if not row:
        return None
    if entity_type == "track" and row.get("track_name"):
        return YearlyEntityRef(
            entity_type="track",
            entity_id=row.get("track_id"),
            name=str(row["track_name"]),
            artist_name=str(row.get("artist_name")) if row.get("artist_name") else None,
            cover_url=row.get("cover_url"),
            deep_link=row.get("deep_link"),
        )
    if entity_type == "album" and row.get("album_name"):
        return YearlyEntityRef(
            entity_type="album",
            entity_id=row.get("album_project_id"),
            name=str(row["album_name"]),
            artist_name=str(row.get("artist_name")) if row.get("artist_name") else None,
            cover_url=row.get("cover_url"),
            deep_link=row.get("deep_link"),
        )
    if entity_type == "artist" and row.get("artist_name"):
        return YearlyEntityRef(
            entity_type="artist",
            entity_id=row.get("artist_id"),
            name=str(row["artist_name"]),
            cover_url=row.get("cover_url"),
            deep_link=row.get("deep_link"),
        )
    return None


def build_passport_and_headlines(
    year: int,
    coverage: YearlyReviewCoverage,
    stats: Mapping[str, Any],
    *,
    baseline_stats: Mapping[str, Any] | None = None,
    comparison_current_stats: Mapping[str, Any] | None = None,
    play_rankings: Mapping[str, Any] | None = None,
    comparison_current_entity_counts: Mapping[str, int] | None = None,
    baseline_entity_counts: Mapping[str, int] | None = None,
) -> tuple[YearlyReportPassport, list[YearlyHeadline]]:
    """Build the report scope card and at most three evidence-backed headlines."""
    summary = dict(stats.get("summary", {}))
    comparison_current_summary = dict((comparison_current_stats or stats).get("summary", {}))
    baseline_summary = dict((baseline_stats or {}).get("summary", {}))
    comparable = (
        coverage.comparison.comparable
        and bool(baseline_stats)
        and bool(comparison_current_stats or stats)
    )
    rankings_authoritative = bool(play_rankings) and (play_rankings or {}).get("empty") is not True
    charts = dict((play_rankings or {}).get("charts", {}))
    entity_specs = {
        "unique_tracks": ("track", "年度播放曲目", "首"),
        "unique_albums": ("album", "年度播放专辑", "张"),
        "unique_artists": ("artist", "年度播放艺人", "位"),
    }
    current_values = dict(summary)
    comparison_current_values: dict[str, Any] = dict(comparison_current_summary)
    baseline_values: dict[str, Any] = dict(baseline_summary)
    for key, (entity, _, _) in entity_specs.items():
        available = dict(charts.get(entity, {})).get("available_count")
        if rankings_authoritative and available is not None:
            current_values[key] = int(available)
        if (
            comparison_current_entity_counts is not None
            and entity in comparison_current_entity_counts
        ):
            comparison_current_values[key] = int(comparison_current_entity_counts[entity])
        if baseline_entity_counts is not None and entity in baseline_entity_counts:
            baseline_values[key] = int(baseline_entity_counts[entity])
        else:
            baseline_values.pop(key, None)
    definitions = (
        ("total_plays", "年度播放", "次"),
        ("total_hours", "年度时长", "小时"),
        ("active_days", "年度活跃天数", "天"),
        *((key, label, unit) for key, (_, label, unit) in entity_specs.items()),
    )
    metrics = [
        YearlyMetric(
            key=key,
            label=label,
            value=current_values.get(key, 0),
            unit=unit,
            comparison_current_value=(
                comparison_current_values.get(key)
                if comparable and key in comparison_current_values
                else None
            ),
            comparison_value=(
                baseline_values.get(key) if comparable and key in baseline_values else None
            ),
            comparison_label=(_comparison_label(coverage) if comparable else None),
            **(_comparison_window_kwargs(coverage) if comparable else {}),
        )
        for key, label, unit in definitions
    ]
    label = {
        "complete": f"{year} 完整年度",
        "year_to_date": f"{year} 截至 {coverage.play.observed_end}",
        "observed_range": f"{year} 观察区间",
        "insufficient": f"{year} 数据不足",
        "empty": f"{year} 暂无数据",
    }[coverage.status]
    passport = YearlyReportPassport(
        year=year,
        label=label,
        observed_start=coverage.play.observed_start,
        observed_end=coverage.play.observed_end,
        status=coverage.status,
        metrics=metrics,
    )

    candidates: list[tuple[int, str, YearlyHeadline]] = []
    hours_change = _change(
        comparison_current_summary.get("total_hours"), baseline_summary.get("total_hours")
    )
    if comparable and hours_change is not None:
        current_hours = float(comparison_current_summary.get("total_hours") or 0)
        baseline_hours = float(baseline_summary.get("total_hours") or 0)
        absolute_change = round(abs(current_hours - baseline_hours), 1)
        direction = "多" if hours_change >= 0 else "少"
        comparison_copy = _comparison_label(coverage)
        candidates.append(
            (
                100 + int(abs(hours_change)),
                "comparison",
                YearlyHeadline(
                    headline_id="listening_time_change",
                    title="这一年的播放时长",
                    statement=(
                        f"{comparison_copy}{direction}听了 {absolute_change:.1f} 小时"
                        f"（{hours_change:+.1f}%）。"
                    ),
                    evidence_grade="B",
                    primary_metric=YearlyMetric(
                        key="total_hours_change_pct",
                        label="播放时长变化",
                        value=hours_change,
                        unit="%",
                        comparison_current_value=current_hours,
                        comparison_value=_number(baseline_summary.get("total_hours")),
                        comparison_label=comparison_copy,
                        **_comparison_window_kwargs(coverage),
                    ),
                    source_refs=["stats.summary.total_hours", "coverage.comparison"],
                ),
            )
        )

    artist_rows = dict(charts.get("artist", {})).get("by_plays", [])
    if artist_rows:
        leader = artist_rows[0]
        ref = _leader_ref(leader, "artist")
        candidates.append(
            (
                90,
                "leader",
                YearlyHeadline(
                    headline_id="most_played_artist",
                    title="年度收听主角",
                    statement=(
                        f"{leader['artist_name']} 以 {int(leader.get('plays', 0)):,} 次播放"
                        f"成为{'全年' if coverage.status == 'complete' else '今年截至目前'}听得最多的艺人。"
                    ),
                    evidence_grade="A",
                    primary_metric=YearlyMetric(
                        key="plays",
                        label="播放次数",
                        value=int(leader.get("plays", 0)),
                        unit="次",
                    ),
                    entity_refs=[ref] if ref else [],
                    source_refs=["play_rankings.artist.by_plays.0"],
                ),
            )
        )

    months = [row for row in stats.get("monthly_distribution", []) if row.get("plays", 0) > 0]
    if months:
        peak = max(months, key=lambda row: (float(row.get("hours", 0)), int(row["month"])))
        candidates.append(
            (
                80,
                "time",
                YearlyHeadline(
                    headline_id="peak_listening_month",
                    title="听歌最多的月份",
                    statement=(
                        f"{int(peak['month'])} 月听了 {float(peak.get('hours', 0)):.1f} 小时，"
                        f"是{'全年' if coverage.status == 'complete' else '今年截至目前'}最高峰。"
                    ),
                    evidence_grade="A",
                    primary_metric=YearlyMetric(
                        key="monthly_hours",
                        label="月收听时长",
                        value=round(float(peak.get("hours", 0)), 2),
                        unit="小时",
                    ),
                    source_refs=[f"stats.monthly_distribution.{int(peak['month'])}"],
                ),
            )
        )

    selected: list[YearlyHeadline] = []
    seen_themes: set[str] = set()
    for _, theme, headline in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if theme in seen_themes:
            continue
        selected.append(headline)
        seen_themes.add(theme)
        if len(selected) == 3:
            break
    return passport, selected

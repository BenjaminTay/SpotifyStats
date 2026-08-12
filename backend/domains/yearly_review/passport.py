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
    play_rankings: Mapping[str, Any] | None = None,
) -> tuple[YearlyReportPassport, list[YearlyHeadline]]:
    """Build the report scope card and at most three evidence-backed headlines."""
    summary = dict(stats.get("summary", {}))
    baseline_summary = dict((baseline_stats or {}).get("summary", {}))
    comparable = coverage.comparison.comparable and bool(baseline_stats)
    definitions = (
        ("total_plays", "有效播放", "次"),
        ("total_hours", "有效时长", "小时"),
        ("active_days", "活跃天数", "天"),
        ("unique_tracks", "曲目数", "首"),
        ("unique_albums", "专辑数", "张"),
        ("unique_artists", "艺人数", "位"),
    )
    metrics = [
        YearlyMetric(
            key=key,
            label=label,
            value=summary.get(key, 0),
            unit=unit,
            comparison_value=(
                baseline_summary.get(key) if comparable and key in baseline_summary else None
            ),
            comparison_label=(f"{coverage.comparison.baseline_year} 同期" if comparable else None),
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
    hours_change = _change(summary.get("total_hours"), baseline_summary.get("total_hours"))
    if comparable and hours_change is not None:
        direction = "增加" if hours_change >= 0 else "减少"
        candidates.append(
            (
                100 + int(abs(hours_change)),
                "comparison",
                YearlyHeadline(
                    headline_id="listening_time_change",
                    title="这一年的收听总量",
                    statement=f"有效收听时长较可比基线{direction} {abs(hours_change):.1f}%。",
                    evidence_grade="B",
                    primary_metric=YearlyMetric(
                        key="total_hours_change_pct",
                        label="有效时长变化",
                        value=hours_change,
                        unit="%",
                        comparison_value=_number(baseline_summary.get("total_hours")),
                        comparison_label=f"{coverage.comparison.baseline_year} 同期小时数",
                    ),
                    source_refs=["stats.summary.total_hours", "coverage.comparison"],
                ),
            )
        )

    charts = dict((play_rankings or {}).get("charts", {}))
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
                        f"{leader['artist_name']} 以 {int(leader.get('plays', 0)):,} 次有效播放成为年度播放量最高艺人。"
                    ),
                    evidence_grade="A",
                    primary_metric=YearlyMetric(
                        key="plays",
                        label="有效播放",
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
                    title="收听高峰月",
                    statement=f"{int(peak['month'])} 月以 {float(peak.get('hours', 0)):.1f} 小时成为全年收听时长最高月份。",
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

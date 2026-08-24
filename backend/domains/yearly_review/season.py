"""Single monthly fact table, annual stages, and deterministic turning points."""

from __future__ import annotations

import math
from calendar import monthrange
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd

from backend.domains.yearly_review.honors import entity_ref
from backend.domains.yearly_review.policies import (
    SEASON_LEADER_CHANGE_CAP,
    SEASON_MAX_STAGES,
    SEASON_MAX_TURNING_POINTS,
    SEASON_MIN_STAGE_MONTHS,
    SEASON_MIN_STAGES,
    SEASON_MIN_TURNING_POINTS,
    SEASON_STAGE_POLICY_VERSION,
)
from backend.domains.yearly_review.record_presenters import present_record_candidate
from backend.models.yearly_review import (
    YearlyEntityRef,
    YearlyHighlightCandidate,
    YearlyMetric,
    YearlyMonthSummary,
    YearlySeasonChapter,
    YearlySeasonStage,
    YearlyTurningPoint,
)


@dataclass
class _EventCandidate:
    month: int
    event_type: str
    title: str
    statement: str
    score: float
    refs: list[YearlyEntityRef]
    metrics: list[YearlyMetric]
    date: str | None = None


def _month_column(frame: pd.DataFrame) -> pd.Series:
    if "ts_month" in frame.columns:
        return pd.to_numeric(frame["ts_month"], errors="coerce")
    return pd.to_datetime(frame["ts_date"], errors="coerce").dt.month


def _monthly_leaders(
    entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None,
) -> dict[int, dict[str, YearlyEntityRef]]:
    result: dict[int, dict[str, YearlyEntityRef]] = defaultdict(dict)
    if entity_frames is None:
        return result
    specs = (
        (
            "track",
            entity_frames[0],
            "canonical_track_id",
            "canonical_track_name",
            "track_id",
            "track_name",
        ),
        (
            "album",
            entity_frames[1],
            "album_project_id",
            "album_project_name",
            "album_project_id",
            "album_name",
        ),
        ("artist", entity_frames[2], "artist_name", "artist_name", "artist_id", "artist_name"),
    )
    for entity_type, source, id_column, name_column, fallback_id, fallback_name in specs:
        if source.empty:
            continue
        frame = source.copy()
        frame["_month"] = _month_column(frame)
        id_col = id_column if id_column in frame.columns else fallback_id
        name_col = name_column if name_column in frame.columns else fallback_name
        if id_col not in frame.columns or name_col not in frame.columns:
            continue
        group_columns = list(dict.fromkeys(["_month", id_col, name_col]))
        if entity_type != "artist" and "artist_name" in frame.columns:
            group_columns.append("artist_name")
        grouped = (
            frame.dropna(subset=["_month", id_col, name_col])
            .groupby(group_columns, dropna=False)
            .agg(plays=("play_id", "count"), hours=("ms_played", lambda s: s.sum() / 3_600_000))
            .reset_index()
            .sort_values(
                ["_month", "plays", "hours", name_col], ascending=[True, False, False, True]
            )
        )
        for month, rows in grouped.groupby("_month", sort=True):
            row = rows.iloc[0]
            payload: dict[str, Any]
            if entity_type == "track":
                payload = {
                    "track_id": row[id_col],
                    "track_name": row[name_col],
                    "artist_name": row.get("artist_name"),
                }
            elif entity_type == "album":
                payload = {
                    "album_project_id": row[id_col],
                    "album_name": row[name_col],
                    "artist_name": row.get("artist_name"),
                }
            else:
                payload = {"artist_id": None, "artist_name": row[name_col]}
            ref = entity_ref(payload, entity_type)
            if ref:
                result[int(cast(Any, month))][f"play_{entity_type}"] = ref
    return result


def _change_pct(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _daily_hours_between(stats: Mapping[str, Any], start: str, end: str) -> float:
    total = 0.0
    for row in stats.get("daily_trend", []):
        date = str(row.get("date") or "")[:10]
        if start <= date <= end:
            total += float(row.get("hours", 0))
    return round(total, 2)


def build_monthly_fact_table(
    stats: Mapping[str, Any],
    *,
    entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None = None,
    billboard_monthly_leaders: Mapping[int, Mapping[str, YearlyEntityRef]] | None = None,
    baseline_monthly: Sequence[Mapping[str, Any]] | None = None,
    complete: bool = True,
    observed_end: str | None = None,
) -> list[YearlyMonthSummary]:
    monthly_rows = {int(row["month"]): row for row in stats.get("monthly_distribution", [])}
    baseline_rows = {int(row["month"]): row for row in baseline_monthly or []}
    leaders = _monthly_leaders(entity_frames)
    for month, month_leaders in (billboard_monthly_leaders or {}).items():
        leaders[int(month)].update(month_leaders)

    months: list[YearlyMonthSummary] = []
    previous_hours = 0.0
    report_year = int(stats.get("year", 0) or 0)
    observed_end_date = pd.to_datetime(observed_end, errors="coerce")
    for month in range(1, 13):
        row = monthly_rows.get(month, {})
        hours = round(float(row.get("hours", 0)), 2)
        comparisons: list[YearlyMetric] = []
        month_change = _change_pct(hours, previous_hours)
        comparison_key = "hours_vs_previous_month_pct"
        comparison_label = "上月小时数"
        observed_start = None
        metric_observed_end = None
        comparison_start = None
        comparison_end = None
        is_partial_current_month = (
            not complete
            and report_year > 0
            and pd.notna(observed_end_date)
            and int(observed_end_date.year) == report_year
            and int(observed_end_date.month) == month
            and int(observed_end_date.day) < monthrange(report_year, month)[1]
            and month > 1
        )
        comparison_value = previous_hours
        if is_partial_current_month:
            prior_month = month - 1
            aligned_day = min(
                int(observed_end_date.day),
                monthrange(report_year, prior_month)[1],
            )
            observed_start = f"{report_year:04d}-{month:02d}-01"
            metric_observed_end = f"{report_year:04d}-{month:02d}-{aligned_day:02d}"
            comparison_start = f"{report_year:04d}-{prior_month:02d}-01"
            comparison_end = f"{report_year:04d}-{prior_month:02d}-{aligned_day:02d}"
            aligned_hours = _daily_hours_between(stats, observed_start, metric_observed_end)
            comparison_value = _daily_hours_between(stats, comparison_start, comparison_end)
            month_change = _change_pct(aligned_hours, comparison_value)
            comparison_key = "hours_vs_previous_period_pct"
            comparison_label = "上月同期小时数"
        if month_change is not None:
            comparisons.append(
                YearlyMetric(
                    key=comparison_key,
                    label=(
                        "较上月同期收听时长变化" if is_partial_current_month else "较上月时长变化"
                    ),
                    value=month_change,
                    unit="%",
                    comparison_value=comparison_value,
                    comparison_label=comparison_label,
                    observed_start=observed_start,
                    observed_end=metric_observed_end,
                    comparison_start=comparison_start,
                    comparison_end=comparison_end,
                )
            )
        baseline = baseline_rows.get(month)
        if baseline:
            baseline_hours = float(baseline.get("hours", 0))
            current_hours = hours
            prior_year_key = "hours_vs_prior_year_month_pct"
            prior_year_label = "较上年同月时长变化"
            prior_observed_start = None
            prior_observed_end = None
            prior_comparison_start = None
            prior_comparison_end = None
            if is_partial_current_month:
                current_hours = _daily_hours_between(stats, observed_start, metric_observed_end)
                prior_year_key = "hours_vs_prior_year_period_pct"
                prior_year_label = "较上年同期收听时长变化"
                prior_observed_start = observed_start
                prior_observed_end = metric_observed_end
                prior_comparison_start = f"{report_year - 1:04d}-{month:02d}-01"
                prior_comparison_end = (
                    f"{report_year - 1:04d}-{month:02d}-{int(observed_end_date.day):02d}"
                )
            year_change = _change_pct(current_hours, baseline_hours)
            if year_change is not None:
                comparisons.append(
                    YearlyMetric(
                        key=prior_year_key,
                        label=prior_year_label,
                        value=year_change,
                        unit="%",
                        comparison_value=baseline_hours,
                        comparison_label=(
                            "上年同期小时数" if is_partial_current_month else "上年同月小时数"
                        ),
                        observed_start=prior_observed_start,
                        observed_end=prior_observed_end,
                        comparison_start=prior_comparison_start,
                        comparison_end=prior_comparison_end,
                    )
                )
        months.append(
            YearlyMonthSummary(
                month=month,
                plays=int(row.get("plays", 0)),
                hours=hours,
                active_days=int(row.get("active_days", 0)),
                leaders=dict(leaders.get(month, {})),
                comparisons=comparisons,
            )
        )
        previous_hours = hours
    return months


def _stable_runs(
    months: Sequence[YearlyMonthSummary],
) -> list[tuple[int, int, str, YearlyEntityRef]]:
    champions: list[tuple[int, str, YearlyEntityRef]] = []
    for month in months:
        ref = month.leaders.get("play_artist")
        if ref and month.plays > 0:
            champions.append((month.month, ref.name.casefold(), ref))
    if len(champions) < 6:
        return []

    keys = [item[1] for item in champions]
    for index in range(1, len(keys) - 1):
        if keys[index - 1] == keys[index + 1] != keys[index]:
            keys[index] = keys[index - 1]
    runs: list[list[Any]] = []
    for (month_number, _, ref), key in zip(champions, keys):
        if runs and runs[-1][2] == key and month_number == runs[-1][1] + 1:
            runs[-1][1] = month_number
        else:
            runs.append([month_number, month_number, key, ref])

    while len(runs) > SEASON_MAX_STAGES:
        index = min(range(len(runs)), key=lambda i: (runs[i][1] - runs[i][0] + 1, i))
        if index == 0:
            runs[1][0] = runs[0][0]
            runs.pop(0)
        else:
            runs[index - 1][1] = runs[index][1]
            runs.pop(index)
    if not (SEASON_MIN_STAGES <= len(runs) <= SEASON_MAX_STAGES):
        return []
    if any(end - start + 1 < SEASON_MIN_STAGE_MONTHS for start, end, _, _ in runs):
        return []
    resolved = []
    for start, end, _, _ in runs:
        segment = [item for item in champions if start <= item[0] <= end]
        counts: dict[str, tuple[int, YearlyEntityRef]] = {}
        for _, key, ref in segment:
            count, _ = counts.get(key, (0, ref))
            counts[key] = (count + 1, ref)
        key, (_, ref) = max(counts.items(), key=lambda item: (item[1][0], item[0]))
        if counts[key][0] / max(end - start + 1, 1) <= 0.5:
            return []
        resolved.append((int(start), int(end), key, ref))
    return resolved


def _timeline_eligible(candidate: YearlyHighlightCandidate) -> bool:
    key = candidate.record_key.casefold()
    return any(
        token in key
        for token in (
            "daily_total_record",
            "daily_total_plays",
            "daily_total_hours",
            "late_night_peak_day",
            "new_year_eve",
            "discovery_day",
            "comeback",
            "return_to_no1",
            "playback_milestones",
            "triple_no1",
            "biggest_jump",
            "biggest_drop",
            "consecutive_marathon",
        )
    )


def _semantically_valid_timeline_candidate(candidate: YearlyHighlightCandidate) -> bool:
    """Keep editorial diversity from changing the truth of a fact."""
    key = candidate.record_key.casefold()
    semantics = candidate.semantics
    superlative_tokens = (
        "daily_binge",
        "daily_total_plays",
        "daily_total_hours",
        "consecutive_marathon",
        "daily_champion",
        "longest_streak",
        "discovery_day",
        "late_night_peak_day",
        "weekday_preference",
        "biggest_jump",
        "biggest_drop",
        "skip_storm",
    )
    has_explicit_rank = candidate.raw_values.get("rank") is not None
    if any(token in key for token in superlative_tokens) and has_explicit_rank:
        if semantics.rank != 1 or not semantics.is_top:
            return False
    if "discovery.discovery_day" in key and has_explicit_rank:
        if semantics.scope != "lifetime_first_seen":
            return False
    if "behavior.playback_milestones" in key and candidate.raw_values.get("scope"):
        if semantics.scope != "lifetime":
            return False
    return True


def _record_month(candidate: YearlyHighlightCandidate) -> tuple[int | None, str | None]:
    raw = candidate.raw_values
    if isinstance(raw.get("month"), (int, float)):
        month = int(raw["month"])
        return (month if 1 <= month <= 12 else None), None
    for key in ("date", "start_date", "billboard_week", "first_week"):
        value = raw.get(key)
        if not value:
            continue
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.notna(parsed):
            return int(parsed.month), str(value)[:10]
    return None, None


def _candidate_events(
    months: Sequence[YearlyMonthSummary],
    record_candidates: Sequence[YearlyHighlightCandidate],
    *,
    complete: bool,
) -> list[_EventCandidate]:
    events: list[_EventCandidate] = []
    active = [month for month in months if month.plays > 0]
    if active:
        peak = max(active, key=lambda month: (month.hours, month.plays, -month.month))
        events.append(
            _EventCandidate(
                month=peak.month,
                event_type="listening_peak",
                title="听歌最多的月份",
                statement=(
                    f"{peak.month} 月听了 {peak.hours:.1f} 小时，"
                    f"是{'全年' if complete else '今年截至目前'}最高峰。"
                ),
                score=100 + peak.hours,
                refs=list(peak.leaders.values())[:2],
                metrics=[
                    YearlyMetric(
                        key="monthly_hours", label="月收听时长", value=peak.hours, unit="小时"
                    )
                ],
            )
        )

    leader_changes = 0
    for index, month in enumerate(months[1:], start=1):
        previous = months[index - 1]
        current_ref = month.leaders.get("play_artist")
        previous_ref = previous.leaders.get("play_artist")
        next_ref = months[index + 1].leaders.get("play_artist") if index + 1 < len(months) else None
        if (
            current_ref
            and previous_ref
            and current_ref.name.casefold() != previous_ref.name.casefold()
            and next_ref
            and next_ref.name.casefold() == current_ref.name.casefold()
            and leader_changes < SEASON_LEADER_CHANGE_CAP
        ):
            events.append(
                _EventCandidate(
                    month=month.month,
                    event_type="leader_change",
                    title="艺人榜首易主",
                    statement=f"{current_ref.name} 从 {month.month} 月起连续至少两个月成为播放冠军艺人。",
                    score=90 - leader_changes,
                    refs=[current_ref, previous_ref],
                    metrics=[
                        YearlyMetric(
                            key="sustained_months",
                            label="连续领先",
                            value=2,
                            unit="个月以上",
                        )
                    ],
                )
            )
            leader_changes += 1

    for candidate in record_candidates:
        if not candidate.eligible or candidate.coverage_status == "unavailable":
            continue
        if not _timeline_eligible(candidate):
            continue
        if not _semantically_valid_timeline_candidate(candidate):
            continue
        record_month, date = _record_month(candidate)
        if record_month is None:
            continue
        presented = present_record_candidate(candidate)
        if presented is None:
            continue
        family = candidate.source_family
        event_type = (
            "return"
            if "comeback" in candidate.record_key or "return" in candidate.record_key
            else "discovery_peak"
            if family == "discovery"
            else "obsession_peak"
            if family == "obsession"
            else "sustained_record"
            if family in {"longevity", "reigns", "endurance", "championship"}
            else "listening_pattern"
            if family in {"behavior", "time_patterns", "market", "movement"}
            else "record_moment"
        )
        metric = candidate.primary_metric
        events.append(
            _EventCandidate(
                month=record_month,
                event_type=event_type,
                title=presented.title,
                statement=presented.statement,
                score=70
                + (
                    math.log1p(abs(float(metric.value)))
                    if metric and isinstance(metric.value, (int, float))
                    else 0
                ),
                refs=list(candidate.entity_refs),
                metrics=[metric] if metric else [],
                date=date,
            )
        )

    for month in active:
        change_metric = next(
            (
                metric
                for metric in month.comparisons
                if metric.key in {"hours_vs_previous_month_pct", "hours_vs_previous_period_pct"}
            ),
            None,
        )
        if change_metric is None:
            continue
        change = float(change_metric.value)
        aligned_copy = change_metric.key == "hours_vs_previous_period_pct"
        cutoff = (
            pd.to_datetime(change_metric.observed_end, errors="coerce")
            if change_metric.observed_end
            else None
        )
        events.append(
            _EventCandidate(
                month=month.month,
                event_type="monthly_shift",
                title="这个月的听歌节奏变了",
                statement=(
                    (
                        f"截至 {month.month} 月{int(cutoff.day)}日，{month.month} 月比上月同期"
                        if aligned_copy and cutoff is not None and pd.notna(cutoff)
                        else f"{month.month} 月比上月"
                    )
                    + f"{'多' if change >= 0 else '少'}听了 "
                    f"{abs(change):.1f}%。"
                ),
                score=50 + abs(change),
                refs=list(month.leaders.values())[:1],
                metrics=[
                    YearlyMetric(
                        key=change_metric.key,
                        label=change_metric.label,
                        value=round(change, 1),
                        unit="%",
                        comparison_value=change_metric.comparison_value,
                        comparison_label=change_metric.comparison_label,
                        observed_start=change_metric.observed_start,
                        observed_end=change_metric.observed_end,
                        comparison_start=change_metric.comparison_start,
                        comparison_end=change_metric.comparison_end,
                    )
                ],
            )
        )
    return events


def _select_events(candidates: Sequence[_EventCandidate]) -> list[_EventCandidate]:
    type_caps = {
        "listening_peak": 1,
        "leader_change": SEASON_LEADER_CHANGE_CAP,
        "discovery_peak": 2,
        "return": 2,
        "obsession_peak": 2,
        "sustained_record": 2,
        "listening_pattern": 2,
        "record_moment": 1,
        "monthly_shift": 3,
    }
    selected: list[_EventCandidate] = []
    selected_months: set[int] = set()
    type_counts: dict[str, int] = defaultdict(int)
    ordered = sorted(candidates, key=lambda item: (-item.score, item.month, item.event_type))
    for candidate in ordered:
        if candidate.month in selected_months:
            continue
        if type_counts[candidate.event_type] >= type_caps.get(candidate.event_type, 2):
            continue
        selected.append(candidate)
        selected_months.add(candidate.month)
        type_counts[candidate.event_type] += 1
        if len(selected) == SEASON_MAX_TURNING_POINTS:
            break
    if len(selected) < SEASON_MIN_TURNING_POINTS:
        return sorted(selected, key=lambda item: item.month)
    return sorted(selected, key=lambda item: item.month)


def build_season(
    year: int,
    stats: Mapping[str, Any],
    *,
    entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None = None,
    billboard_monthly_leaders: Mapping[int, Mapping[str, YearlyEntityRef]] | None = None,
    baseline_monthly: Sequence[Mapping[str, Any]] | None = None,
    record_candidates: Sequence[YearlyHighlightCandidate] = (),
    complete: bool = True,
    observed_end: str | None = None,
) -> YearlySeasonChapter:
    months = build_monthly_fact_table(
        stats,
        entity_frames=entity_frames,
        billboard_monthly_leaders=billboard_monthly_leaders,
        baseline_monthly=baseline_monthly,
        complete=complete,
        observed_end=observed_end,
    )
    stable_runs = _stable_runs(months)
    stage_status = "available" if stable_runs else "no_stable_phase"
    stage_note = None
    stage_rows = stable_runs
    if sum(month.plays > 0 for month in months) < 6:
        stage_status = "insufficient"
        stage_note = None
    stages: list[YearlySeasonStage] = []
    for index, (start, end, _, ref) in enumerate(stage_rows, start=1):
        stage_id = f"stage-{index}"
        stage_months = end - start + 1
        champion_months = sum(
            1
            for month in months
            if start <= month.month <= end
            and month.leaders.get("play_artist")
            and month.leaders["play_artist"].name.casefold() == ref.name.casefold()
        )
        stages.append(
            YearlySeasonStage(
                stage_id=stage_id,
                label=f"{ref.name} 主导期",
                start_month=start,
                end_month=end,
                entity_refs=[ref],
                evidence=[
                    YearlyMetric(
                        key="stage_months",
                        label="阶段长度",
                        value=stage_months,
                        unit="个月",
                    ),
                    YearlyMetric(
                        key="champion_months",
                        label="阶段内月冠军",
                        value=champion_months,
                        unit="个月",
                    ),
                    YearlyMetric(
                        key="champion_month_share_pct",
                        label="阶段月冠军占比",
                        value=round(champion_months / stage_months * 100, 1),
                        unit="%",
                    ),
                ],
            )
        )
        for month in months:
            if start <= month.month <= end:
                month.stage_id = stage_id

    selected_events = _select_events(
        _candidate_events(months, record_candidates, complete=complete)
    )
    turning_points: list[YearlyTurningPoint] = []
    for index, event in enumerate(selected_events, start=1):
        event_id = f"{year}-{event.month:02d}-{event.event_type}-{index}"
        turning_points.append(
            YearlyTurningPoint(
                point_id=event_id,
                month=event.month,
                date=event.date,
                event_type=event.event_type,
                title=event.title,
                statement=event.statement,
                evidence_grade="A" if event.event_type != "monthly_shift" else "B",
                entity_refs=event.refs[:4],
                metrics=event.metrics[:4],
            )
        )
        months[event.month - 1].event_ids.append(event_id)
    return YearlySeasonChapter(
        policy_version=SEASON_STAGE_POLICY_VERSION,
        stage_status=stage_status,
        stage_note=stage_note,
        stages=stages,
        turning_points=turning_points,
        months=months,
    )

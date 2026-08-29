"""Shared-load deterministic orchestrator for Yearly Review V2."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable, TypeVar, cast

import pandas as pd

from backend.core.db import load_plays
from backend.domains.yearly_review.appendix import build_appendix
from backend.domains.yearly_review.billboard_adapter import build_billboard_source
from backend.domains.yearly_review.comparison_window import (
    aligned_comparison_frames,
    filter_date_range,
)
from backend.domains.yearly_review.coverage import (
    build_billboard_coverage,
    build_comparison_coverage,
    build_play_coverage,
    build_taste_coverage,
    build_yearly_review_coverage,
)
from backend.domains.yearly_review.entity_links import enrich_entity_ref_covers
from backend.domains.yearly_review.epilogue import build_epilogue
from backend.domains.yearly_review.honors import build_honors
from backend.domains.yearly_review.listening_life import build_listening_life
from backend.domains.yearly_review.methodology import build_methodology
from backend.domains.yearly_review.passport import build_passport_and_headlines
from backend.domains.yearly_review.play_rankings import (
    build_play_ranking_counts,
    build_play_rankings,
)
from backend.domains.yearly_review.playback_records_adapter import (
    build_playback_record_candidates,
)
from backend.domains.yearly_review.records import select_yearly_records
from backend.domains.yearly_review.relationships import build_relationships
from backend.domains.yearly_review.season import build_season
from backend.domains.yearly_review.stats_adapter import (
    build_yearly_comparison_stats,
    build_yearly_stats,
)
from backend.domains.yearly_review.taste_migration import (
    build_taste_drivers,
    build_taste_migration,
    resolve_taste_comparison,
    taste_comparison_frames,
)
from backend.models.yearly_review import (
    YearlyAppendix,
    YearlyBillboardCoverage,
    YearlyEpilogue,
    YearlyHighlightCandidate,
    YearlyHonorsChapter,
    YearlyListeningLifeChapter,
    YearlyRecordsChapter,
    YearlyRelationshipStory,
    YearlyReviewFilterContext,
    YearlyReviewResponse,
    YearlySeasonChapter,
    YearlyTasteMigrationChapter,
)
from backend.services.analysis_records_service import _build_entity_frames

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True)
class YearlyReviewBuildArtifact:
    report: YearlyReviewResponse
    record_catalog: list[dict[str, Any]]


def _year_frame(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if "ts_year" in frame.columns:
        years = pd.to_numeric(frame["ts_year"], errors="coerce")
        return frame[years == year].copy()
    dates = pd.to_datetime(frame["ts_date"], errors="coerce")
    return frame[dates.dt.year == year].copy()


def _safe_section(
    name: str,
    builder: Callable[[], T],
    fallback: Callable[[], T],
    limitations: list[str],
) -> T:
    try:
        return builder()
    except Exception as exc:
        logger.exception("Yearly Review V2 section failed: %s", name)
        limitations.append(f"section_unavailable:{name}:{type(exc).__name__}")
        return fallback()


def _empty_billboard(year: int) -> dict[str, Any]:
    return {
        "year": year,
        "semantics_version": None,
        "coverage": YearlyBillboardCoverage(status="empty", source_status="empty"),
        "meta": {},
        "charts": {"track": [], "album": [], "artist": []},
        "honors": {},
        "record_catalog_counts": {"total": 0, "eligible": 0},
        "record_candidates": [],
    }


def _empty_play_rankings(year: int) -> dict[str, Any]:
    return {
        "year": year,
        "empty": True,
        "charts": {
            entity: {"available_count": 0, "by_plays": [], "by_hours": []}
            for entity in ("track", "album", "artist")
        },
    }


def _history_top_refs(
    candidates: list[YearlyHighlightCandidate],
) -> list[Any]:
    refs = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        if not (
            candidate.raw_values.get("is_personal_best")
            or candidate.raw_values.get("all_time_rank") == 1
        ):
            continue
        for ref in candidate.entity_refs:
            key = (ref.entity_type, str(ref.entity_id or ref.name).casefold())
            if key not in seen:
                refs.append(ref)
                seen.add(key)
    return refs[:6]


def _carryover_refs(season: YearlySeasonChapter) -> list[Any]:
    active = [month for month in season.months if month.plays > 0]
    if len(active) < 2:
        return []
    recent = active[-2:]
    by_identity: dict[tuple[str, str], tuple[int, Any]] = {}
    for month in recent:
        for ref in month.leaders.values():
            key = (ref.entity_type, str(ref.entity_id or ref.name).casefold())
            count, _ = by_identity.get(key, (0, ref))
            by_identity[key] = (count + 1, ref)
    ordered = sorted(by_identity.values(), key=lambda item: (-item[0], item[1].name))
    return [ref for count, ref in ordered if count >= 2][:6]


def _metric_value(metrics: list[Any], key: str) -> int | float | None:
    for metric in metrics:
        if metric.key == key and isinstance(metric.value, (int, float)):
            return metric.value
    return None


def _validate_cross_chapter_semantics(
    passport: Any,
    listening_life: YearlyListeningLifeChapter,
) -> None:
    if passport is None:
        return
    passport_tracks = _metric_value(passport.metrics, "unique_tracks")
    listening_tracks = _metric_value(listening_life.metrics, "unique_tracks")
    if (
        passport_tracks is not None
        and listening_tracks is not None
        and int(passport_tracks) != int(listening_tracks)
    ):
        raise ValueError(
            "yearly_unique_track_identity_mismatch:"
            f"passport={int(passport_tracks)}:listening_life={int(listening_tracks)}"
        )

    total_plays = _metric_value(passport.metrics, "total_plays")
    artist_plays = _metric_value(listening_life.metrics, "top_artist_plays")
    artist_share = _metric_value(listening_life.metrics, "top_artist_share_pct")
    if total_plays and artist_plays is not None and artist_share is not None:
        expected_share = round(float(artist_plays) / float(total_plays) * 100, 1)
        if abs(float(artist_share) - expected_share) > 0.05:
            raise ValueError(
                "yearly_artist_share_denominator_mismatch:"
                f"expected={expected_share}:actual={float(artist_share)}"
            )


def build_yearly_review_artifact(
    conn: sqlite3.Connection,
    year: int,
    context: YearlyReviewFilterContext,
    *,
    event_frame: pd.DataFrame | None = None,
) -> YearlyReviewBuildArtifact:
    """Build one report while sharing the play and entity frames across chapters."""
    limitations: list[str] = []
    if event_frame is None:
        event_frame = load_plays(
            conn,
            min_ms=context.min_ms,
            music_only=context.music_only,
            merge_enabled=context.merge_enabled,
            dynamic_threshold=context.dynamic_threshold,
            max_merge_gap_minutes=context.max_merge_gap_minutes,
        )
    annual_events = _year_frame(event_frame, year)
    baseline_year_events = _year_frame(event_frame, year - 1)

    entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
    if annual_events.empty:
        entity_frames = (pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    else:
        entity_frames = _safe_section(
            "entity_frames",
            lambda: _build_entity_frames(
                event_frame,
                conn,
                context.merge_level,
                context.include_compilations,
                min_ms=context.min_ms,
                music_only=context.music_only,
                merge_enabled=context.merge_enabled,
                dynamic_threshold=context.dynamic_threshold,
                max_merge_gap_minutes=context.max_merge_gap_minutes,
            ),
            lambda: (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
            limitations,
        )
    annual_entity_frames = (
        _year_frame(entity_frames[0], year),
        _year_frame(entity_frames[1], year),
        _year_frame(entity_frames[2], year),
    )

    # Stats and play coverage are the report spine; failure here should surface.
    stats = build_yearly_stats(conn, year, context, event_frame=event_frame)
    play_coverage = build_play_coverage(annual_events, year=year)
    baseline_coverage = (
        build_play_coverage(baseline_year_events, year=year - 1)
        if not baseline_year_events.empty
        else None
    )
    comparison_coverage = build_comparison_coverage(
        report_year=year,
        current=play_coverage,
        baseline=baseline_coverage,
    )
    aligned = None
    if (
        comparison_coverage.comparable
        and comparison_coverage.current_start
        and comparison_coverage.current_end
        and comparison_coverage.baseline_start
        and comparison_coverage.baseline_end
    ):
        aligned = aligned_comparison_frames(
            event_frame,
            report_year=year,
            observed_start=comparison_coverage.current_start,
            observed_end=comparison_coverage.current_end,
            baseline_start=comparison_coverage.baseline_start,
            baseline_end=comparison_coverage.baseline_end,
        )
    baseline_events = aligned.baseline if aligned is not None else baseline_year_events.iloc[0:0]
    baseline_stats = (
        build_yearly_comparison_stats(year - 1, event_frame=baseline_events)
        if not baseline_events.empty
        else None
    )
    comparison_current_events = aligned.current if aligned is not None else annual_events.iloc[0:0]
    comparison_current_stats = (
        stats
        if aligned is not None and comparison_current_events.equals(annual_events)
        else build_yearly_comparison_stats(year, event_frame=comparison_current_events)
        if not comparison_current_events.empty
        else None
    )

    if annual_events.empty:
        play_rankings = _empty_play_rankings(year)
        billboard = _empty_billboard(year)
    else:
        play_rankings = _safe_section(
            "play_rankings",
            lambda: build_play_rankings(
                conn,
                year,
                context,
                event_frame=event_frame,
                entity_frames=entity_frames,
            ),
            lambda: _empty_play_rankings(year),
            limitations,
        )
        billboard = _safe_section(
            "billboard",
            lambda: build_billboard_source(conn, year, context),
            lambda: _empty_billboard(year),
            limitations,
        )
    taste_coverage = build_taste_coverage(
        stats.get("taste_profile"),
        release_era=stats.get("release_era_profile"),
    )
    coverage = build_yearly_review_coverage(
        play=play_coverage,
        billboard=(
            billboard["coverage"]
            if isinstance(billboard.get("coverage"), YearlyBillboardCoverage)
            else build_billboard_coverage(billboard.get("meta"))
        ),
        comparison=comparison_coverage,
        taste=taste_coverage,
    )

    comparison_current_entity_counts: Mapping[str, int] | None = None
    baseline_entity_counts: Mapping[str, int] | None = None
    if aligned is not None and not baseline_events.empty:
        comparison_current_entity_frames = tuple(
            filter_date_range(frame, aligned.current_start, aligned.current_end)
            for frame in entity_frames
        )
        baseline_entity_frames = tuple(
            filter_date_range(frame, aligned.baseline_start, aligned.baseline_end)
            for frame in entity_frames
        )
        comparison_current_entity_counts = cast(
            Mapping[str, int],
            _safe_section(
                "comparison_current_entity_counts",
                lambda: build_play_ranking_counts(
                    conn,
                    context,
                    event_frame=aligned.current,
                    entity_frames=cast(
                        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
                        comparison_current_entity_frames,
                    ),
                ),
                dict,
                limitations,
            ),
        )
        baseline_entity_counts = cast(
            Mapping[str, int],
            _safe_section(
                "baseline_entity_counts",
                lambda: build_play_ranking_counts(
                    conn,
                    context,
                    event_frame=baseline_events,
                    entity_frames=cast(
                        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
                        baseline_entity_frames,
                    ),
                ),
                dict,
                limitations,
            ),
        )
    passport, headlines = build_passport_and_headlines(
        year,
        coverage,
        stats,
        baseline_stats=baseline_stats,
        comparison_current_stats=comparison_current_stats,
        play_rankings=play_rankings,
        comparison_current_entity_counts=comparison_current_entity_counts,
        baseline_entity_counts=baseline_entity_counts,
    )
    playback_records: dict[str, Any] = (
        {"catalog_counts": {"total": 0, "eligible": 0}, "candidates": []}
        if annual_events.empty
        else _safe_section(
            "playback_records",
            lambda: build_playback_record_candidates(
                conn,
                year,
                context,
                event_frame=annual_events,
                entity_frames=annual_entity_frames,
                history_event_frame=event_frame,
                history_entity_frames=entity_frames,
            ),
            lambda: {"catalog_counts": {"total": 0, "eligible": 0}, "candidates": []},
            limitations,
        )
    )
    billboard_candidates = cast(
        list[YearlyHighlightCandidate], list(billboard.get("record_candidates", []))
    )
    playback_candidates = cast(
        list[YearlyHighlightCandidate], list(playback_records.get("candidates", []))
    )
    all_candidates = [*playback_candidates, *billboard_candidates]
    enrich_entity_ref_covers(conn, all_candidates)

    honors = _safe_section(
        "honors",
        lambda: build_honors(play_rankings, billboard),
        YearlyHonorsChapter,
        limitations,
    )
    season = _safe_section(
        "season",
        lambda: build_season(
            year,
            stats,
            entity_frames=annual_entity_frames,
            baseline_monthly=(baseline_stats or {}).get("monthly_distribution"),
            record_candidates=all_candidates,
            complete=coverage.status == "complete",
            observed_end=coverage.play.observed_end,
        ),
        YearlySeasonChapter,
        limitations,
    )
    relationships: list[YearlyRelationshipStory] = _safe_section(
        "relationships",
        lambda: build_relationships(
            year,
            coverage,
            annual_entity_frames,
            billboard,
            divergence_stories=honors.divergence_stories,
            history_frames=entity_frames,
        ),
        list,
        limitations,
    )
    listening_life = _safe_section(
        "listening_life",
        lambda: build_listening_life(
            stats,
            coverage,
            baseline_stats=baseline_stats,
            comparison_current_stats=comparison_current_stats,
            play_rankings=play_rankings,
            event_frame=annual_events,
            history_frame=event_frame,
            track_frame=annual_entity_frames[0],
            history_track_frame=entity_frames[0],
            record_candidates=all_candidates,
        ),
        YearlyListeningLifeChapter,
        limitations,
    )
    _validate_cross_chapter_semantics(passport, listening_life)
    selected_records = _safe_section(
        "records",
        lambda: select_yearly_records(
            year,
            [playback_candidates, billboard_candidates],
            catalog_counts={
                **{
                    f"playback_{key}": int(value)
                    for key, value in playback_records.get("catalog_counts", {}).items()
                },
                **{
                    f"billboard_{key}": int(value)
                    for key, value in billboard.get("record_catalog_counts", {}).items()
                },
            },
        ),
        YearlyRecordsChapter,
        limitations,
    )
    timeline_statements = {point.statement for point in season.turning_points}
    selected_records.featured = [
        record
        for record in selected_records.featured
        if record.statement not in timeline_statements
    ][:8]
    selected_records.catalog_counts["featured_total"] = len(selected_records.featured)
    taste_comparison = resolve_taste_comparison(stats, coverage)
    taste_from_events, taste_to_events = taste_comparison_frames(annual_events, taste_comparison)
    taste_migration = _safe_section(
        "taste_migration",
        lambda: build_taste_migration(
            stats,
            coverage,
            drivers=build_taste_drivers(
                conn,
                taste_from_events,
                taste_to_events,
            ),
            comparison=taste_comparison,
        ),
        YearlyTasteMigrationChapter,
        limitations,
    )
    appendix = _safe_section(
        "appendix",
        lambda: build_appendix(
            play_rankings,
            billboard,
            season.months,
            playback_record_counts=playback_records.get("catalog_counts"),
        ),
        YearlyAppendix,
        limitations,
    )
    epilogue = _safe_section(
        "epilogue",
        lambda: build_epilogue(
            [*headlines, *listening_life.observations, *taste_migration.observations],
            new_history_tops=_history_top_refs(all_candidates),
            next_year_carryovers=_carryover_refs(season),
        ),
        YearlyEpilogue,
        limitations,
    )

    report = YearlyReviewResponse(
        year=year,
        status=coverage.status,
        filter_context=context,
        coverage=coverage,
        passport=passport,
        headlines=headlines,
        honors=honors,
        season=season,
        relationships=relationships,
        listening_life=listening_life,
        records=selected_records,
        taste_migration=taste_migration,
        epilogue=epilogue,
        appendix=appendix,
        methodology=build_methodology(
            coverage,
            taste_comparison,
            billboard_record_semantics=billboard.get("record_semantics"),
            internal_diagnostics=limitations,
        ),
    )
    enrich_entity_ref_covers(conn, report)
    catalog = [record.model_dump(mode="json") for record in selected_records.featured]
    return YearlyReviewBuildArtifact(report=report, record_catalog=catalog)

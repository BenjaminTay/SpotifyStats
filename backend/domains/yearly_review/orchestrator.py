"""Shared-load deterministic orchestrator for Yearly Review V2."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, TypeVar, cast

import pandas as pd

from backend.core.db import load_plays
from backend.domains.yearly_review.appendix import build_appendix
from backend.domains.yearly_review.billboard_adapter import build_billboard_source
from backend.domains.yearly_review.coverage import (
    build_billboard_coverage,
    build_comparison_coverage,
    build_play_coverage,
    build_taste_coverage,
    build_yearly_review_coverage,
)
from backend.domains.yearly_review.epilogue import build_epilogue
from backend.domains.yearly_review.honors import build_honors
from backend.domains.yearly_review.listening_life import build_listening_life
from backend.domains.yearly_review.passport import build_passport_and_headlines
from backend.domains.yearly_review.play_rankings import build_play_rankings
from backend.domains.yearly_review.playback_records_adapter import (
    build_playback_record_candidates,
)
from backend.domains.yearly_review.records import (
    record_candidate_to_featured,
    select_yearly_records,
)
from backend.domains.yearly_review.relationships import build_relationships
from backend.domains.yearly_review.season import build_season
from backend.domains.yearly_review.stats_adapter import build_yearly_stats
from backend.domains.yearly_review.taste_migration import (
    build_taste_drivers,
    build_taste_migration,
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
    baseline_events = _year_frame(event_frame, year - 1)

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
    baseline_stats = (
        build_yearly_stats(conn, year - 1, context, event_frame=event_frame)
        if not baseline_events.empty
        else None
    )
    play_coverage = build_play_coverage(annual_events, year=year)
    baseline_coverage = (
        build_play_coverage(baseline_events, year=year - 1) if not baseline_events.empty else None
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
        comparison=build_comparison_coverage(
            report_year=year,
            current=play_coverage,
            baseline=baseline_coverage,
        ),
        taste=taste_coverage,
    )

    passport, headlines = build_passport_and_headlines(
        year,
        coverage,
        stats,
        baseline_stats=baseline_stats,
        play_rankings=play_rankings,
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
            play_rankings=play_rankings,
            event_frame=annual_events,
            history_frame=event_frame,
            record_candidates=all_candidates,
        ),
        YearlyListeningLifeChapter,
        limitations,
    )
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
    taste_migration = _safe_section(
        "taste_migration",
        lambda: build_taste_migration(
            stats,
            coverage,
            drivers=build_taste_drivers(
                conn,
                annual_events[pd.to_numeric(annual_events.get("ts_month"), errors="coerce") <= 6]
                if not annual_events.empty
                else annual_events,
                annual_events[pd.to_numeric(annual_events.get("ts_month"), errors="coerce") >= 7]
                if not annual_events.empty
                else annual_events,
            ),
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
            new_history_tops=[
                story.entity
                for story in relationships
                if story.relationship_type == "new_relationship"
            ],
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
        methodology={
            "notes": [
                "single_shared_effective_play_frame",
                "single_shared_entity_frame_set",
            ],
            "limitations": limitations,
        },
    )
    catalog = [
        record_candidate_to_featured(candidate).model_dump(mode="json")
        for candidate in all_candidates
        if candidate.eligible
    ]
    return YearlyReviewBuildArtifact(report=report, record_catalog=catalog)

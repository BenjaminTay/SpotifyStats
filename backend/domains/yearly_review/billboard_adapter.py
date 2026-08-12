"""Personal Billboard Year-End adapter for Yearly Review V2."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from backend.domains.billboard.chart_staged_api import compute_records_staged
from backend.domains.billboard.chart_year_end_api import compute_year_end_staged
from backend.domains.yearly_review.coverage import build_billboard_coverage
from backend.domains.yearly_review.entity_links import ensure_row_deep_link
from backend.domains.yearly_review.playback_records_adapter import normalize_record_catalog
from backend.models.yearly_review import YearlyReviewFilterContext

BILLBOARD_RECORD_FAMILY_PREFIXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "championship",
        (
            "artist_most_no1",
            "debut_no1",
            "fastest_to_no1",
            "longest_to_no1",
            "return_to_no1",
            "triple_no1",
            "year_end_no1",
        ),
    ),
    (
        "longevity",
        ("longest_artist_span", "longest_charting", "longest_streak", "most_reentries"),
    ),
    (
        "endurance",
        ("longest_consecutive_same_rank", "longest_no_top5", "most_weeks_no2_no_no1"),
    ),
    (
        "movement",
        ("biggest_drop", "biggest_jump", "fastest_exit_after_no1", "new_entry_ratio"),
    ),
    (
        "hall_of_fame",
        ("album_power_ranking", "all_time_greatest", "artist_power_ranking", "decade_best"),
    ),
    (
        "self_replacement_blocker",
        ("blocked_", "blocker_king", "self_replacement_no1"),
    ),
    (
        "market",
        ("album_simul_list", "artist_simul_list", "week_total_plays"),
    ),
)


def _group_billboard_records(records: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record_key, value in records.items():
        family = "quirky"
        for candidate_family, prefixes in BILLBOARD_RECORD_FAMILY_PREFIXES:
            if any(str(record_key).startswith(prefix) for prefix in prefixes):
                family = candidate_family
                break
        grouped.setdefault(family, {})[str(record_key)] = value
    return grouped


def _album_project_lookup(conn: sqlite3.Connection) -> dict[tuple[str, str], int]:
    try:
        rows = conn.execute(
            """SELECT ap.project_id, ap.canonical_name, ar.artist_name
               FROM album_projects ap
               LEFT JOIN artists ar ON ar.artist_id = ap.artist_id
               WHERE ap.include_in_charts = 1"""
        ).fetchall()
    except sqlite3.Error:
        return {}
    candidates: dict[tuple[str, str], set[int]] = defaultdict(set)
    for row in rows:
        key = (str(row[1]).casefold(), str(row[2] or "").casefold())
        candidates[key].add(int(row[0]))
    return {
        key: next(iter(project_ids))
        for key, project_ids in candidates.items()
        if len(project_ids) == 1
    }


def _align_album_rows(
    rows: list[dict[str, Any]],
    lookup: Mapping[tuple[str, str], int],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        key = (
            str(item.get("album_name") or "").casefold(),
            str(item.get("artist_name") or "").casefold(),
        )
        project_id = item.get("album_project_id") or lookup.get(key)
        item["album_project_id"] = int(project_id) if project_id is not None else None
        item["identity_key"] = (
            f"album-project:{project_id}"
            if project_id is not None
            else f"album:{key[1]}\u241f{key[0]}"
        )
        result.append(item)
    return result


def build_billboard_source(
    conn: sqlite3.Connection,
    year: int,
    context: YearlyReviewFilterContext,
    *,
    year_end_payload: Mapping[str, Any] | None = None,
    records_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Adapt the existing Year-End chart without changing its scoring semantics."""
    if year_end_payload is None:
        year_end_payload = compute_year_end_staged(
            min_ms=context.min_ms,
            music_only=context.music_only,
            bb_top_n=context.bb_top_n,
            bb_album_top_n=context.bb_album_top_n,
            bb_artist_top_n=context.bb_artist_top_n,
            bb_week_start_dow=context.bb_week_start_dow,
            bb_week_start_hour=context.bb_week_start_hour,
            year=year,
            merge_level=context.merge_level,
            dynamic_threshold=context.dynamic_threshold,
            max_merge_gap_minutes=context.max_merge_gap_minutes,
            include_compilations=context.include_compilations,
            year_end_top_n=50,
            year_end_album_top_n=30,
            year_end_artist_top_n=30,
        )
    if records_payload is None:
        records_payload = compute_records_staged(
            min_ms=context.min_ms,
            music_only=context.music_only,
            bb_top_n=context.bb_top_n,
            bb_album_top_n=context.bb_album_top_n,
            bb_artist_top_n=context.bb_artist_top_n,
            bb_week_start_dow=context.bb_week_start_dow,
            bb_week_start_hour=context.bb_week_start_hour,
            year_start=year,
            year_end=year,
            merge_level=context.merge_level,
            dynamic_threshold=context.dynamic_threshold,
            max_merge_gap_minutes=context.max_merge_gap_minutes,
        )

    meta = dict(year_end_payload.get("meta", {}))
    albums = _align_album_rows(
        [dict(row) for row in year_end_payload.get("albums", [])],
        _album_project_lookup(conn),
    )
    record_candidates, record_counts = normalize_record_catalog(
        _group_billboard_records(records_payload.get("records", {})),
        source="billboard_records",
        fallback_base="/billboard/records",
    )
    return {
        "year": year,
        "semantics_version": meta.get("semantics_version"),
        "coverage": build_billboard_coverage(meta),
        "meta": meta,
        "charts": {
            "track": [
                ensure_row_deep_link(row, "track") for row in year_end_payload.get("tracks", [])
            ],
            "album": [ensure_row_deep_link(row, "album") for row in albums],
            "artist": [
                ensure_row_deep_link(row, "artist") for row in year_end_payload.get("artists", [])
            ],
        },
        "honors": dict(year_end_payload.get("honors", {})),
        "record_semantics": {
            "annual_range": [year, year],
            "include_compilations_requested": context.include_compilations,
            "include_compilations_supported": False,
            "aligned_with_requested_context": not context.include_compilations,
            "limitation": (
                None
                if not context.include_compilations
                else "billboard_records_source_does_not_accept_include_compilations"
            ),
        },
        "record_catalog_counts": {
            "total": len(record_candidates),
            "eligible": sum(candidate.eligible for candidate in record_candidates),
            **record_counts,
        },
        "record_candidates": record_candidates,
    }

"""Fast first-pass candidates for the versioned music-search API.

Published candidate documents remain queryable while the next generation or
its exact statistical context is pending, building, or failed.  This service
never invokes the legacy lifetime/Billboard search path.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import replace
from typing import Any, Literal, cast

from backend.core.config import MUSIC_SEARCH_CANDIDATE_LKG
from backend.domains.ai_agent.entity_resolver import EntityType, resolve_entities
from backend.domains.music_search.contracts import make_music_search_entity_key
from backend.domains.music_search.deny_overlay import denied_music_search_entity_keys
from backend.domains.music_search.index import (
    get_music_search_candidate_maintenance_state,
    get_music_search_index_state,
    music_search_source_revision,
)
from backend.domains.music_search.normalization import analyze_search_query, normalize_search_text
from backend.domains.music_search.repository import search_music_index
from backend.domains.music_search.timing import MusicSearchTiming, measure_search_phase
from backend.models.music_search import (
    MusicSearchCandidateFreshness,
    MusicSearchCandidateResponse,
    MusicSearchCandidateResult,
    MusicSearchKindTotals,
    MusicSearchMatchField,
    MusicSearchMatchQuality,
    MusicSearchSnapshotStatus,
    MusicSearchStatisticsFreshness,
)
from backend.services.music_search_service import _convert

MusicSearchEligibility = Literal["current", "any_local"]

_ALL_KINDS: tuple[EntityType, ...] = ("track", "album", "artist")


def _selected_kinds(kinds: Iterable[str] | None) -> tuple[EntityType, ...]:
    if kinds is None:
        return _ALL_KINDS
    selected = tuple(cast(EntityType, kind) for kind in kinds if kind in _ALL_KINDS)
    return selected or _ALL_KINDS


def _match_metadata(
    candidate: dict[str, Any],
    normalized_query: str,
) -> tuple[MusicSearchMatchField, MusicSearchMatchQuality]:
    fields: tuple[tuple[MusicSearchMatchField, str], ...] = (
        ("label", str(candidate.get("name") or "")),
        ("artist", str(candidate.get("artist_name") or "")),
        ("album", str(candidate.get("album_name") or "")),
    )
    fallback: tuple[MusicSearchMatchField, MusicSearchMatchQuality] = (
        "label",
        "substring",
    )
    for quality in ("exact", "prefix", "token", "substring"):
        for field, value in fields:
            normalized_value = normalize_search_text(value)
            if not normalized_value:
                continue
            if quality == "exact" and normalized_value == normalized_query:
                return field, quality
            if quality == "prefix" and normalized_value.startswith(normalized_query):
                return field, quality
            if quality == "token":
                terms = normalized_query.split()
                if terms and all(term in normalized_value.split() for term in terms):
                    return field, quality
            if quality == "substring" and normalized_query in normalized_value:
                return field, quality
    return fallback


def _candidate_result(
    kind: EntityType,
    candidate: dict[str, Any],
    normalized_query: str,
) -> MusicSearchCandidateResult | None:
    legacy = _convert(kind, candidate)
    if legacy is None:
        return None
    if kind == "track":
        entity_id = candidate.get("track_id")
    elif kind == "album":
        entity_id = candidate.get("album_id")
    else:
        entity_id = candidate.get("artist_id")
    if entity_id is None:
        return None
    match_field, match_quality = _match_metadata(candidate, normalized_query)
    return MusicSearchCandidateResult(
        entity_key=make_music_search_entity_key(kind, int(entity_id)),
        kind=kind,
        label=legacy.label,
        subtitle=legacy.subtitle if kind != "artist" else None,
        href=legacy.href,
        track_id=legacy.track_id,
        artist_id=legacy.artist_id,
        album_name=legacy.album_name,
        artist_name=legacy.artist_name,
        cover_url=legacy.cover_url,
        match_field=match_field,
        match_quality=match_quality,
    )


def _empty_response(
    *,
    query: str,
    normalized_query: str,
    kind: EntityType | None,
    page: int,
    page_size: int,
    snapshot_status: MusicSearchSnapshotStatus,
    filter_fingerprint: str | None = None,
    candidate_status: Literal["ready", "degraded", "unavailable"] = "unavailable",
    candidate_freshness: MusicSearchCandidateFreshness = "unavailable",
    candidate_index_version: str | None = None,
    served_filter_fingerprint: str | None = None,
    target_filter_fingerprint: str | None = None,
) -> MusicSearchCandidateResponse:
    return MusicSearchCandidateResponse(
        query=query,
        normalized_query=normalized_query,
        snapshot_status=snapshot_status,
        candidate_status=candidate_status,
        candidate_freshness=candidate_freshness,
        statistics_status=snapshot_status,
        statistics_freshness=("current" if snapshot_status == "ready" else "unavailable"),
        filter_fingerprint=filter_fingerprint,
        served_filter_fingerprint=served_filter_fingerprint,
        target_filter_fingerprint=target_filter_fingerprint,
        candidate_index_version=candidate_index_version,
        kind=kind,
        page=page,
        page_size=page_size,
        total=0,
        total_by_kind=MusicSearchKindTotals(),
    )


def _published_candidate_freshness(
    conn: sqlite3.Connection,
) -> tuple[MusicSearchCandidateFreshness, str | None]:
    serving = get_music_search_index_state(conn)
    maintenance = get_music_search_candidate_maintenance_state(conn)
    active_source = str(serving.get("source_revision") or "")
    active_version = str(serving.get("candidate_index_version") or "")
    target_source = str(maintenance.get("target_source_revision") or "")
    target_version = str(maintenance.get("target_candidate_index_version") or "")
    current_source = music_search_source_revision(conn)
    target_matches_active = (not target_source or target_source == active_source) and (
        not target_version or target_version == active_version
    )
    is_current = (
        bool(active_source)
        and active_source == current_source
        and target_matches_active
        and str(maintenance.get("maintenance_status") or "missing") == "ready"
    )
    return ("current" if is_current else "last_known_good"), active_version or None


def search_music_candidates(
    conn: sqlite3.Connection,
    *,
    query: str,
    kinds: Iterable[str] | None = None,
    page: int = 1,
    page_size: int = 5,
    eligibility: MusicSearchEligibility = "current",
    filter_fingerprint: str | None = None,
    snapshot_status: MusicSearchSnapshotStatus = "unavailable",
    merge_level: int = 2,
    snapshot_key: str | None = None,
    statistics_freshness: MusicSearchStatisticsFreshness = "unavailable",
    served_filter_fingerprint: str | None = None,
    timing: MusicSearchTiming | None = None,
    allow_fallback: bool = True,
    require_snapshot_membership: bool = False,
    include_target_fingerprint: bool = True,
) -> MusicSearchCandidateResponse:
    """Return lightweight candidates without loading statistical frames.

    Exact snapshot membership is used when available. Otherwise the published
    local-catalog generation remains searchable and statistics are explicitly
    marked unavailable/stale instead of suppressing candidates.
    """

    with measure_search_phase(timing, "normalize"):
        analysis = analyze_search_query(query)
    selected = _selected_kinds(kinds)
    selected_kind = selected[0] if len(selected) == 1 else None
    if not analysis.eligible:
        return _empty_response(
            query=query,
            normalized_query=analysis.normalized_query,
            kind=selected_kind,
            page=page,
            page_size=page_size,
            snapshot_status=("unavailable" if eligibility == "any_local" else snapshot_status),
            filter_fingerprint=filter_fingerprint,
            target_filter_fingerprint=(filter_fingerprint if include_target_fingerprint else None),
        )

    serving_snapshot_key = snapshot_key if eligibility == "current" and snapshot_key else None
    if require_snapshot_membership and eligibility == "current" and serving_snapshot_key is None:
        return _empty_response(
            query=query,
            normalized_query=analysis.normalized_query,
            kind=selected_kind,
            page=page,
            page_size=page_size,
            snapshot_status=snapshot_status,
            filter_fingerprint=filter_fingerprint,
            target_filter_fingerprint=None,
        )
    effective_snapshot_status: MusicSearchSnapshotStatus = (
        "unavailable"
        if eligibility == "any_local"
        else (
            snapshot_status
            if snapshot_status != "ready" or serving_snapshot_key is not None
            else "unavailable"
        )
    )

    with measure_search_phase(timing, "candidate_query"):
        indexed = search_music_index(
            conn,
            query=analysis.normalized_query,
            kind=selected_kind,
            page=page,
            page_size=page_size,
            merge_level=merge_level,
            snapshot_key=serving_snapshot_key,
        )
    if indexed.status in {"ready", "degraded"}:
        candidate_freshness, active_index_version = _published_candidate_freshness(conn)
        if not MUSIC_SEARCH_CANDIDATE_LKG and candidate_freshness != "current":
            indexed = replace(indexed, status="missing")
    if indexed.status in {"ready", "degraded"}:
        candidate_freshness, active_index_version = _published_candidate_freshness(conn)
        totals = indexed.total_by_kind
        response = MusicSearchCandidateResponse(
            query=query,
            normalized_query=analysis.normalized_query,
            snapshot_status=effective_snapshot_status,
            candidate_status=indexed.status,
            candidate_freshness=candidate_freshness,
            statistics_status=effective_snapshot_status,
            statistics_freshness=(
                statistics_freshness if serving_snapshot_key is not None else "unavailable"
            ),
            filter_fingerprint=filter_fingerprint,
            served_filter_fingerprint=(served_filter_fingerprint if serving_snapshot_key else None),
            target_filter_fingerprint=(filter_fingerprint if include_target_fingerprint else None),
            candidate_index_version=indexed.candidate_index_version or active_index_version,
            kind=selected_kind,
            page=page,
            page_size=page_size,
            total=totals.track + totals.album + totals.artist,
            total_by_kind=totals,
            tracks=indexed.tracks,
            albums=indexed.albums,
            artists=indexed.artists,
        )
        with measure_search_phase(timing, "serialize"):
            response.model_dump(mode="json")
        return response

    # First-start fallback is deliberately private and bounded. Public-readonly
    # callers need a separately proven public-safe resolver before this layer
    # can be enabled for them.
    if not allow_fallback:
        return _empty_response(
            query=query,
            normalized_query=analysis.normalized_query,
            kind=selected_kind,
            page=page,
            page_size=page_size,
            snapshot_status="unavailable",
            filter_fingerprint=filter_fingerprint,
            target_filter_fingerprint=(filter_fingerprint if include_target_fingerprint else None),
        )

    resolver_limit = min(max(page * page_size, 1), 10)
    grouped: dict[EntityType, list[MusicSearchCandidateResult]] = {
        "track": [],
        "album": [],
        "artist": [],
    }
    with measure_search_phase(timing, "candidate_fallback"):
        for entity_kind in selected:
            resolved = resolve_entities(
                conn,
                query=analysis.normalized_query,
                entity_type=entity_kind,
                limit=resolver_limit,
            )
            converted = [
                item
                for candidate in resolved.get("candidates", [])
                if (
                    item := _candidate_result(
                        entity_kind,
                        candidate,
                        analysis.normalized_query,
                    )
                )
                is not None
            ]
            denied = denied_music_search_entity_keys(
                conn,
                (item.entity_key for item in converted),
            )
            converted = [item for item in converted if item.entity_key not in denied]
            offset = (page - 1) * page_size if selected_kind else 0
            grouped[entity_kind] = converted[offset : offset + page_size]

    totals = MusicSearchKindTotals(
        track=len(grouped["track"]),
        album=len(grouped["album"]),
        artist=len(grouped["artist"]),
    )
    response = MusicSearchCandidateResponse(
        query=query,
        normalized_query=analysis.normalized_query,
        snapshot_status=effective_snapshot_status,
        candidate_status="degraded",
        candidate_freshness="fallback",
        statistics_status=effective_snapshot_status,
        statistics_freshness="unavailable",
        filter_fingerprint=filter_fingerprint,
        target_filter_fingerprint=(filter_fingerprint if include_target_fingerprint else None),
        kind=selected_kind,
        page=page,
        page_size=page_size,
        total=totals.track + totals.album + totals.artist,
        total_by_kind=totals,
        tracks=grouped["track"],
        albums=grouped["album"],
        artists=grouped["artist"],
    )
    with measure_search_phase(timing, "serialize"):
        response.model_dump(mode="json")
    return response

"""Fast first-pass candidates for the versioned music-search API.

M1 deliberately keeps this service independent from filtered lifetime frames
and Billboard computation.  Exact consumer eligibility is joined from the
derived snapshot in M3; until that snapshot exists, ``current`` requests fail
closed with an explicit availability state.  Private metadata-governance
callers may opt into ``any_local`` candidates.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any, Literal, cast

from backend.domains.ai_agent.entity_resolver import EntityType, resolve_entities
from backend.domains.music_search.contracts import make_music_search_entity_key
from backend.domains.music_search.normalization import analyze_search_query, normalize_search_text
from backend.domains.music_search.repository import search_music_index
from backend.domains.music_search.timing import MusicSearchTiming, measure_search_phase
from backend.models.music_search import (
    MusicSearchCandidateResponse,
    MusicSearchCandidateResult,
    MusicSearchKindTotals,
    MusicSearchMatchField,
    MusicSearchMatchQuality,
    MusicSearchSnapshotStatus,
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
) -> MusicSearchCandidateResponse:
    return MusicSearchCandidateResponse(
        query=query,
        normalized_query=normalized_query,
        snapshot_status=snapshot_status,
        filter_fingerprint=filter_fingerprint,
        kind=kind,
        page=page,
        page_size=page_size,
        total=0,
        total_by_kind=MusicSearchKindTotals(),
    )


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
    timing: MusicSearchTiming | None = None,
) -> MusicSearchCandidateResponse:
    """Return lightweight candidates without loading statistical frames.

    ``current`` is intentionally fail-closed until an exact ready snapshot is
    supplied by M3.  That prevents a fast raw entity match from pretending to
    have the same existence semantics as the detail pages.
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
            snapshot_status="ready" if eligibility == "any_local" else snapshot_status,
            filter_fingerprint=filter_fingerprint,
        )
    if eligibility == "current" and (snapshot_status != "ready" or snapshot_key is None):
        return _empty_response(
            query=query,
            normalized_query=analysis.normalized_query,
            kind=selected_kind,
            page=page,
            page_size=page_size,
            snapshot_status=(snapshot_status if snapshot_status != "ready" else "unavailable"),
            filter_fingerprint=filter_fingerprint,
        )

    with measure_search_phase(timing, "candidate_query"):
        indexed = search_music_index(
            conn,
            query=analysis.normalized_query,
            kind=selected_kind,
            page=page,
            page_size=page_size,
            merge_level=merge_level,
            snapshot_key=snapshot_key if eligibility == "current" else None,
        )
    if indexed.status in {"ready", "degraded"}:
        totals = indexed.total_by_kind
        response = MusicSearchCandidateResponse(
            query=query,
            normalized_query=analysis.normalized_query,
            snapshot_status="ready",
            filter_fingerprint=filter_fingerprint,
            candidate_index_version=indexed.candidate_index_version,
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

    # The bounded resolver remains available only for private metadata
    # governance.  ``current`` must not bypass the exact derived snapshot if
    # the search index is unavailable, because doing so would silently weaken
    # the detail-page existence contract.
    if eligibility == "current":
        return _empty_response(
            query=query,
            normalized_query=analysis.normalized_query,
            kind=selected_kind,
            page=page,
            page_size=page_size,
            snapshot_status="unavailable",
            filter_fingerprint=filter_fingerprint,
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
        snapshot_status="ready",
        filter_fingerprint=filter_fingerprint,
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

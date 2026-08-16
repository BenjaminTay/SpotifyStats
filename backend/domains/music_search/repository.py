"""Read-only candidate queries against the active search-index generation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Literal, cast

from backend.domains.music_search.index import get_music_search_index_state
from backend.domains.music_search.normalization import normalize_search_text
from backend.models.music_search import (
    MusicSearchCandidateResult,
    MusicSearchKind,
    MusicSearchKindTotals,
    MusicSearchMatchField,
    MusicSearchMatchQuality,
)


@dataclass(frozen=True)
class MusicSearchRepositoryResult:
    status: Literal["ready", "degraded", "missing", "failed"]
    generation_id: str | None
    total_by_kind: MusicSearchKindTotals
    tracks: list[MusicSearchCandidateResult]
    albums: list[MusicSearchCandidateResult]
    artists: list[MusicSearchCandidateResult]


def _candidate_kind(kind: str) -> MusicSearchKind:
    return cast(MusicSearchKind, "album" if kind == "album_project" else kind)


def _allowed_document_kinds(kind: MusicSearchKind | None, merge_level: int) -> tuple[str, ...]:
    album_kind = "album" if merge_level <= 1 else "album_project"
    if kind == "album":
        return (album_kind,)
    if kind in {"track", "artist"}:
        return (kind,)
    return ("track", album_kind, "artist")


def _fts_expression(query: str) -> str | None:
    tokens = [token for token in query.split() if token]
    if not tokens or any(len(token) < 3 for token in tokens):
        return None
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def _like_prefix(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _ranked_match_cte(
    *,
    normalized_query: str,
    document_kinds: tuple[str, ...],
    use_fts: bool,
    snapshot_key: str | None,
) -> tuple[str, dict[str, Any]]:
    """Build the bounded SQL match/rank source shared by totals and pages.

    The previous repository materialised every FTS hit plus the complete
    eligible entity-key set in Python before sorting and slicing.  Keeping the
    deterministic rank inside SQLite makes response work proportional to the
    requested page while an exact snapshot join preserves consumer eligibility.
    """

    tokens = [token for token in normalized_query.split() if token]
    params: dict[str, Any] = {
        "query": normalized_query,
        "prefix": _like_prefix(normalized_query),
    }
    kind_names: list[str] = []
    for index, value in enumerate(document_kinds):
        name = f"kind_{index}"
        params[name] = value
        kind_names.append(f":{name}")
    exact_token_conditions: list[str] = []
    fallback_token_conditions: list[str] = []
    for index, token in enumerate(tokens):
        name = f"token_{index}"
        params[name] = token
        exact_token_conditions.append(
            f"instr(' ' || d.search_text || ' ', ' ' || :{name} || ' ') > 0"
        )
        fallback_token_conditions.append(f"instr(d.search_text, :{name}) > 0")
    token_match = " AND ".join(exact_token_conditions) or "0"

    joins: list[str] = []
    if snapshot_key is not None:
        params["snapshot_key"] = snapshot_key
        joins.append(
            "JOIN music_search_entity_context c "
            "ON c.snapshot_key=:snapshot_key AND c.entity_key=d.entity_key"
        )

    fts_expression = _fts_expression(normalized_query) if use_fts else None
    if fts_expression is not None:
        params["fts_expression"] = fts_expression
        source = """FROM music_search_documents_fts
            JOIN music_search_documents d
              ON d.generation_id=music_search_documents_fts.generation_id
             AND d.entity_key=music_search_documents_fts.entity_key
             AND d.merge_level=music_search_documents_fts.merge_level"""
        joins.append("WHERE music_search_documents_fts MATCH :fts_expression")
    else:
        source = "FROM music_search_documents d"
        if len(normalized_query) >= 3:
            joins.append("WHERE " + (" AND ".join(fallback_token_conditions) or "0"))
        else:
            joins.append(
                "WHERE (d.normalized_label=:query OR d.normalized_label LIKE :prefix ESCAPE '\\' "
                "OR d.normalized_secondary=:query OR d.normalized_secondary LIKE :prefix ESCAPE '\\' "
                "OR d.normalized_alias=:query OR d.normalized_alias LIKE :prefix ESCAPE '\\')"
            )

    first_where = next(index for index, value in enumerate(joins) if value.startswith("WHERE "))
    predicate = joins.pop(first_where)[6:]
    join_sql = "\n            ".join(joins)
    rank_expression = f"""CASE
                WHEN d.normalized_label=:query THEN 0
                WHEN d.normalized_label LIKE :prefix ESCAPE '\\' THEN 1
                WHEN {token_match} THEN CASE
                    WHEN d.normalized_secondary=:query
                      OR d.normalized_secondary LIKE :prefix ESCAPE '\\'
                      OR d.normalized_alias=:query
                      OR d.normalized_alias LIKE :prefix ESCAPE '\\' THEN 3
                    ELSE 2 END
                WHEN instr(d.normalized_label, :query) > 0
                  OR instr(d.normalized_secondary, :query) > 0
                  OR instr(d.normalized_alias, :query) > 0 THEN 4
                ELSE 5 END"""
    cte = f"""WITH matched AS (
            SELECT d.*,
                   CASE WHEN d.kind='album_project' THEN 'album' ELSE d.kind END AS result_kind,
                   {rank_expression} AS match_rank
            {source}
            {join_sql}
            WHERE ({predicate})
              AND d.generation_id=:generation_id
              AND d.kind IN ({", ".join(kind_names)})
              AND (d.kind!='track' OR d.merge_level=:merge_level)
        )"""
    return cte, params


def _query_ranked_rows(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    normalized_query: str,
    document_kinds: tuple[str, ...],
    merge_level: int,
    kind: MusicSearchKind | None,
    page: int,
    page_size: int,
    use_fts: bool,
    snapshot_key: str | None,
) -> tuple[MusicSearchKindTotals, list[dict[str, Any]]]:
    cte, params = _ranked_match_cte(
        normalized_query=normalized_query,
        document_kinds=document_kinds,
        use_fts=use_fts,
        snapshot_key=snapshot_key,
    )
    params.update({"generation_id": generation_id, "merge_level": merge_level})
    order_by = "match_rank, popularity_tiebreaker DESC, normalized_label, entity_key"
    totals_by_kind: dict[str, int]
    if kind is not None:
        page_params = {
            **params,
            "result_kind": kind,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        rows = conn.execute(
            f"""{cte}
                SELECT matched.*, COUNT(*) OVER () AS result_total FROM matched
                WHERE match_rank < 5 AND result_kind=:result_kind
                ORDER BY {order_by} LIMIT :limit OFFSET :offset""",
            page_params,
        ).fetchall()
        if rows:
            totals_by_kind = {kind: int(rows[0]["result_total"])}
        else:
            # An out-of-range page still needs the exact total.  Normal UI
            # pages take the single-query window path above; only the empty
            # edge case pays for a bounded count replay.
            total = conn.execute(
                f"""{cte}
                    SELECT COUNT(*) FROM matched
                    WHERE match_rank < 5 AND result_kind=:result_kind""",
                page_params,
            ).fetchone()[0]
            totals_by_kind = {kind: int(total)}
    else:
        page_params = {**params, "limit": page_size}
        rows = conn.execute(
            f"""{cte}, ranked AS (
                    SELECT matched.*,
                           ROW_NUMBER() OVER (
                               PARTITION BY result_kind ORDER BY {order_by}
                           ) AS result_number,
                           COUNT(*) OVER (PARTITION BY result_kind) AS result_total
                    FROM matched WHERE match_rank < 5
                )
                SELECT * FROM ranked WHERE result_number <= :limit
                ORDER BY CASE result_kind WHEN 'track' THEN 0 WHEN 'album' THEN 1 ELSE 2 END,
                         {order_by}""",
            page_params,
        ).fetchall()
        totals_by_kind = {str(row["result_kind"]): int(row["result_total"]) for row in rows}
    totals = MusicSearchKindTotals(
        track=totals_by_kind.get("track", 0),
        album=totals_by_kind.get("album", 0),
        artist=totals_by_kind.get("artist", 0),
    )
    return totals, [dict(row) for row in rows]


def _match_rank(
    row: dict[str, Any], normalized_query: str
) -> tuple[int, MusicSearchMatchField, MusicSearchMatchQuality] | None:
    label = str(row["normalized_label"])
    secondary = str(row["normalized_secondary"])
    alias = str(row["normalized_alias"])
    search_text = str(row["search_text"])
    if label == normalized_query:
        return 0, "label", "exact"
    if label.startswith(normalized_query):
        return 1, "label", "prefix"
    tokens = [token for token in normalized_query.split() if token]
    search_tokens = search_text.split()
    if tokens and all(token in search_tokens for token in tokens):
        if normalized_query == secondary:
            field: MusicSearchMatchField = "artist" if row["kind"] != "artist" else "label"
            return 3, field, "exact"
        if secondary.startswith(normalized_query):
            field = "artist" if row["kind"] != "artist" else "label"
            return 3, field, "prefix"
        if normalized_query == alias or alias.startswith(normalized_query):
            return 3, "alias", "exact" if alias == normalized_query else "prefix"
        if all(token in label.split() for token in tokens):
            return 2, "label", "token"
        return 2, "label", "token"
    for field, value in (("label", label), ("artist", secondary), ("alias", alias)):
        if normalized_query in value:
            return 4, cast(MusicSearchMatchField, field), "substring"
    return None


def _to_candidate(
    row: dict[str, Any],
    *,
    match_field: MusicSearchMatchField,
    match_quality: MusicSearchMatchQuality,
) -> MusicSearchCandidateResult:
    return MusicSearchCandidateResult(
        entity_key=str(row["entity_key"]),
        kind=_candidate_kind(str(row["kind"])),
        label=str(row["label"]),
        subtitle=str(row["secondary"]) if row["secondary"] else None,
        href=str(row["href"]),
        track_id=int(row["track_id"]) if row["track_id"] is not None else None,
        artist_id=int(row["artist_id"]) if row["artist_id"] is not None else None,
        album_name=str(row["album_name"]) if row["album_name"] else None,
        artist_name=str(row["artist_name"]) if row["artist_name"] else None,
        cover_url=str(row["cover_url"]) if row["cover_url"] else None,
        match_field=match_field,
        match_quality=match_quality,
    )


def search_music_index(
    conn: sqlite3.Connection,
    *,
    query: str,
    kind: MusicSearchKind | None,
    page: int,
    page_size: int,
    merge_level: int,
    snapshot_key: str | None = None,
) -> MusicSearchRepositoryResult:
    state = get_music_search_index_state(conn)
    generation_id = state.get("active_generation_id")
    state_status = str(state.get("status") or "missing")
    if not generation_id or state_status not in {"ready", "degraded"}:
        return MusicSearchRepositoryResult(
            status="failed" if state_status == "failed" else "missing",
            generation_id=None,
            total_by_kind=MusicSearchKindTotals(),
            tracks=[],
            albums=[],
            artists=[],
        )
    normalized_query = normalize_search_text(query)
    document_kinds = _allowed_document_kinds(kind, merge_level)
    try:
        totals, rows = _query_ranked_rows(
            conn,
            generation_id=str(generation_id),
            normalized_query=normalized_query,
            document_kinds=document_kinds,
            merge_level=merge_level,
            kind=kind,
            page=page,
            page_size=page_size,
            use_fts=state_status == "ready",
            snapshot_key=snapshot_key,
        )
    except sqlite3.OperationalError:
        if state_status != "ready":
            raise
        totals, rows = _query_ranked_rows(
            conn,
            generation_id=str(generation_id),
            normalized_query=normalized_query,
            document_kinds=document_kinds,
            merge_level=merge_level,
            kind=kind,
            page=page,
            page_size=page_size,
            use_fts=False,
            snapshot_key=snapshot_key,
        )
    grouped: dict[MusicSearchKind, list[MusicSearchCandidateResult]] = {
        "track": [],
        "album": [],
        "artist": [],
    }
    for row in rows:
        match = _match_rank(row, normalized_query)
        if match is None:
            continue
        _, match_field, match_quality = match
        candidate = _to_candidate(
            row,
            match_field=match_field,
            match_quality=match_quality,
        )
        grouped[candidate.kind].append(candidate)
    return MusicSearchRepositoryResult(
        status=cast(Literal["ready", "degraded"], state_status),
        generation_id=str(generation_id),
        total_by_kind=totals,
        tracks=grouped["track"],
        albums=grouped["album"],
        artists=grouped["artist"],
    )

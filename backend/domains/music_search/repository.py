"""Read-only candidate queries against the active search-index generation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Literal, cast

from backend.domains.music_search.index import get_music_search_index_state
from backend.domains.music_search.normalization import (
    QueryScriptCategory,
    classify_query_script,
    expand_chinese_search_variants,
    normalize_search_text,
)
from backend.models.music_search import (
    MusicSearchCandidateResult,
    MusicSearchKind,
    MusicSearchKindTotals,
    MusicSearchMatchField,
    MusicSearchMatchQuality,
    MusicSearchMatchType,
)


@dataclass(frozen=True)
class MusicSearchRepositoryResult:
    status: Literal["ready", "degraded", "missing", "failed"]
    generation_id: str | None
    candidate_index_version: str | None
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


def _query_variants(query: str) -> tuple[tuple[str, MusicSearchMatchType], ...]:
    normalized = normalize_search_text(query)
    candidates: list[tuple[str, MusicSearchMatchType]] = [(normalized, "original")]
    expanded = expand_chinese_search_variants(normalized)
    if expanded:
        candidates.extend(((expanded[0], "simplified"), (expanded[1], "traditional")))
    result: list[tuple[str, MusicSearchMatchType]] = []
    seen: set[str] = set()
    for value, match_type in candidates:
        normalized_value = normalize_search_text(value)
        if normalized_value and normalized_value not in seen:
            seen.add(normalized_value)
            result.append((normalized_value, match_type))
    return tuple(result)


def _like_prefix(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _ranked_match_cte(
    *,
    query_variants: tuple[tuple[str, MusicSearchMatchType], ...],
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

    normalized_query = query_variants[0][0]
    params: dict[str, Any] = {}
    kind_names: list[str] = []
    for index, value in enumerate(document_kinds):
        name = f"kind_{index}"
        params[name] = value
        kind_names.append(f":{name}")
    rank_expressions: list[str] = []
    fallback_variant_conditions: list[str] = []
    fts_expressions: list[str] = []
    for variant_index, (variant, _match_type) in enumerate(query_variants):
        query_name = f"query_{variant_index}"
        prefix_name = f"prefix_{variant_index}"
        params[query_name] = variant
        params[prefix_name] = _like_prefix(variant)
        token_conditions: list[str] = []
        fallback_tokens: list[str] = []
        for token_index, token in enumerate(token for token in variant.split() if token):
            token_name = f"token_{variant_index}_{token_index}"
            params[token_name] = token
            token_conditions.append(
                f"instr(' ' || d.search_text || ' ', ' ' || :{token_name} || ' ') > 0"
            )
            fallback_tokens.append(f"instr(d.search_text, :{token_name}) > 0")
        token_match = " AND ".join(token_conditions) or "0"
        base = variant_index * 10
        rank_expressions.append(
            f"""CASE
                WHEN d.normalized_label=:{query_name} THEN {base}
                WHEN d.normalized_label LIKE :{prefix_name} ESCAPE '\\' THEN {base + 1}
                WHEN {token_match} THEN CASE
                    WHEN d.normalized_secondary=:{query_name}
                      OR d.normalized_secondary LIKE :{prefix_name} ESCAPE '\\'
                      OR d.normalized_alias=:{query_name}
                      OR d.normalized_alias LIKE :{prefix_name} ESCAPE '\\'
                    THEN {base + 3} ELSE {base + 2} END
                WHEN instr(d.normalized_label, :{query_name}) > 0
                  OR instr(d.normalized_secondary, :{query_name}) > 0
                  OR instr(d.normalized_alias, :{query_name}) > 0 THEN {base + 4}
                ELSE {base + 9} END"""
        )
        fallback_variant_conditions.append(" AND ".join(fallback_tokens) or "0")
        expression = _fts_expression(variant)
        if expression is not None:
            fts_expressions.append(f"({expression})")

    joins: list[str] = []
    if snapshot_key is not None:
        params["snapshot_key"] = snapshot_key
        joins.append(
            "JOIN music_search_entity_context c "
            "ON c.snapshot_key=:snapshot_key AND c.entity_key=d.entity_key"
        )

    if use_fts and len(fts_expressions) == len(query_variants):
        params["fts_expression"] = " OR ".join(fts_expressions)
        source = """FROM music_search_documents_fts
            JOIN music_search_documents d
              ON d.generation_id=music_search_documents_fts.generation_id
             AND d.entity_key=music_search_documents_fts.entity_key
             AND d.merge_level=music_search_documents_fts.merge_level"""
        joins.append("WHERE music_search_documents_fts MATCH :fts_expression")
    else:
        source = "FROM music_search_documents d"
        if len(normalized_query) >= 3:
            joins.append("WHERE (" + " OR ".join(fallback_variant_conditions) + ")")
        elif classify_query_script(normalized_query) is QueryScriptCategory.CJK:
            ngram_names = []
            for index, (variant, _match_type) in enumerate(query_variants):
                name = f"ngram_{index}"
                params[name] = variant
                ngram_names.append(f":{name}")
            joins.append(
                """WHERE EXISTS (
                    SELECT 1 FROM music_search_document_ngrams n
                    WHERE n.generation_id=d.generation_id
                      AND n.entity_key=d.entity_key
                      AND n.merge_level=d.merge_level
                      AND n.ngram IN ("""
                + ", ".join(ngram_names)
                + "))"
            )
        else:
            prefix_conditions = []
            for index, _variant in enumerate(query_variants):
                prefix_conditions.append(
                    f"""(d.normalized_label=:query_{index}
                         OR d.normalized_label LIKE :prefix_{index} ESCAPE '\\'
                         OR d.normalized_secondary=:query_{index}
                         OR d.normalized_secondary LIKE :prefix_{index} ESCAPE '\\'
                         OR d.normalized_alias=:query_{index}
                         OR d.normalized_alias LIKE :prefix_{index} ESCAPE '\\')"""
                )
            joins.append("WHERE (" + " OR ".join(prefix_conditions) + ")")

    first_where = next(index for index, value in enumerate(joins) if value.startswith("WHERE "))
    predicate = joins.pop(first_where)[6:]
    join_sql = "\n            ".join(joins)
    rank_expression = (
        rank_expressions[0]
        if len(rank_expressions) == 1
        else "MIN(" + ", ".join(rank_expressions) + ")"
    )
    maximum_rank = (len(query_variants) - 1) * 10 + 5
    params["maximum_rank"] = maximum_rank
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
    query_variants: tuple[tuple[str, MusicSearchMatchType], ...],
    document_kinds: tuple[str, ...],
    merge_level: int,
    kind: MusicSearchKind | None,
    page: int,
    page_size: int,
    use_fts: bool,
    snapshot_key: str | None,
) -> tuple[MusicSearchKindTotals, list[dict[str, Any]]]:
    cte, params = _ranked_match_cte(
        query_variants=query_variants,
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
                WHERE match_rank < :maximum_rank AND result_kind=:result_kind
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
                    WHERE match_rank < :maximum_rank AND result_kind=:result_kind""",
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
                    FROM matched WHERE match_rank < :maximum_rank
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
    row: dict[str, Any], query_variants: tuple[tuple[str, MusicSearchMatchType], ...]
) -> tuple[int, MusicSearchMatchField, MusicSearchMatchQuality, MusicSearchMatchType] | None:
    label = str(row["normalized_label"])
    secondary = str(row["normalized_secondary"])
    alias = str(row["normalized_alias"])
    search_text = str(row["search_text"])
    search_tokens = search_text.split()
    for variant_index, (normalized_query, match_type) in enumerate(query_variants):
        base = variant_index * 10
        if label == normalized_query:
            return base, "label", "exact", match_type
        if label.startswith(normalized_query):
            return base + 1, "label", "prefix", match_type
        tokens = [token for token in normalized_query.split() if token]
        if tokens and all(token in search_tokens for token in tokens):
            if normalized_query == secondary:
                field: MusicSearchMatchField = "artist" if row["kind"] != "artist" else "label"
                return base + 3, field, "exact", match_type
            if secondary.startswith(normalized_query):
                field = "artist" if row["kind"] != "artist" else "label"
                return base + 3, field, "prefix", match_type
            if normalized_query == alias or alias.startswith(normalized_query):
                quality: MusicSearchMatchQuality = (
                    "exact" if alias == normalized_query else "prefix"
                )
                return base + 3, "alias", quality, match_type
            return base + 2, "label", "token", match_type
        for field, value in (("label", label), ("artist", secondary), ("alias", alias)):
            if normalized_query in value:
                return base + 4, cast(MusicSearchMatchField, field), "substring", match_type
    return None


def _to_candidate(
    row: dict[str, Any],
    *,
    match_field: MusicSearchMatchField,
    match_quality: MusicSearchMatchQuality,
    match_type: MusicSearchMatchType = "original",
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
        match_type=match_type,
    )


def _bounded_levenshtein(left: str, right: str, maximum: int) -> int | None:
    if abs(len(left) - len(right)) > maximum:
        return None
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        row_minimum = left_index
        for right_index, right_character in enumerate(right, start=1):
            value = min(
                current[-1] + 1,
                previous[right_index] + 1,
                previous[right_index - 1] + (left_character != right_character),
            )
            current.append(value)
            row_minimum = min(row_minimum, value)
        if row_minimum > maximum:
            return None
        previous = current
    distance = previous[-1]
    return distance if distance <= maximum else None


def _fuzzy_match(
    row: dict[str, Any], normalized_query: str
) -> tuple[int, MusicSearchMatchField] | None:
    compact_length = len(normalized_query.replace(" ", ""))
    maximum = 1 if compact_length <= 5 else 2 if compact_length <= 12 else 3
    values: list[tuple[MusicSearchMatchField, str]] = []
    for field, raw in (
        ("label", row["normalized_label"]),
        ("artist", row["normalized_secondary"]),
        ("alias", row["normalized_alias"]),
    ):
        normalized = str(raw or "")
        if not normalized:
            continue
        values.append((cast(MusicSearchMatchField, field), normalized))
        values.extend(
            (cast(MusicSearchMatchField, field), token)
            for token in normalized.replace("·", " ").split()
            if token
        )
    matches = [
        (distance, field)
        for field, value in values
        if (distance := _bounded_levenshtein(normalized_query, value, maximum)) is not None
    ]
    return min(matches, default=None, key=lambda item: (item[0], item[1]))


def _query_fuzzy_rows(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    normalized_query: str,
    document_kinds: tuple[str, ...],
    merge_level: int,
    snapshot_key: str | None,
    pool_size: int = 50,
) -> list[dict[str, Any]]:
    compact = normalized_query.replace(" ", "")
    if len(compact) < 4:
        return []
    trigrams = tuple(dict.fromkeys(compact[index : index + 3] for index in range(len(compact) - 2)))
    if not trigrams:
        return []
    params: dict[str, Any] = {
        "generation_id": generation_id,
        "merge_level": merge_level,
        "fts_expression": " OR ".join(f'"{value}"' for value in trigrams),
        "pool_size": pool_size,
    }
    kind_names = []
    for index, value in enumerate(document_kinds):
        name = f"fuzzy_kind_{index}"
        params[name] = value
        kind_names.append(f":{name}")
    context_join = ""
    if snapshot_key is not None:
        params["snapshot_key"] = snapshot_key
        context_join = (
            "JOIN music_search_entity_context c "
            "ON c.snapshot_key=:snapshot_key AND c.entity_key=d.entity_key"
        )
    rows = conn.execute(
        f"""SELECT d.*, bm25(music_search_documents_fts) AS fuzzy_recall_rank
            FROM music_search_documents_fts
            JOIN music_search_documents d
              ON d.generation_id=music_search_documents_fts.generation_id
             AND d.entity_key=music_search_documents_fts.entity_key
             AND d.merge_level=music_search_documents_fts.merge_level
            {context_join}
            WHERE music_search_documents_fts MATCH :fts_expression
              AND d.generation_id=:generation_id
              AND d.kind IN ({", ".join(kind_names)})
              AND (d.kind!='track' OR d.merge_level=:merge_level)
            ORDER BY fuzzy_recall_rank, d.normalized_label, d.entity_key
            LIMIT :pool_size""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


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
            candidate_index_version=None,
            total_by_kind=MusicSearchKindTotals(),
            tracks=[],
            albums=[],
            artists=[],
        )
    query_variants = _query_variants(query)
    normalized_query = query_variants[0][0]
    document_kinds = _allowed_document_kinds(kind, merge_level)
    try:
        totals, rows = _query_ranked_rows(
            conn,
            generation_id=str(generation_id),
            query_variants=query_variants,
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
            query_variants=query_variants,
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
        match = _match_rank(row, query_variants)
        if match is None:
            continue
        _, match_field, match_quality, match_type = match
        candidate = _to_candidate(
            row,
            match_field=match_field,
            match_quality=match_quality,
            match_type=match_type,
        )
        grouped[candidate.kind].append(candidate)

    if totals.track + totals.album + totals.artist == 0 and state_status == "ready":
        fuzzy_rows = _query_fuzzy_rows(
            conn,
            generation_id=str(generation_id),
            normalized_query=normalized_query,
            document_kinds=document_kinds,
            merge_level=merge_level,
            snapshot_key=snapshot_key,
        )
        fuzzy_by_kind: dict[MusicSearchKind, list[tuple[int, dict[str, Any]]]] = {
            "track": [],
            "album": [],
            "artist": [],
        }
        seen_keys: set[str] = set()
        for row in fuzzy_rows:
            entity_key = str(row["entity_key"])
            if entity_key in seen_keys:
                continue
            fuzzy_match = _fuzzy_match(row, normalized_query)
            if fuzzy_match is None:
                continue
            seen_keys.add(entity_key)
            distance, match_field = fuzzy_match
            fuzzy_by_kind[_candidate_kind(str(row["kind"]))].append((distance, row))
            row["fuzzy_match_field"] = match_field
        fuzzy_totals: dict[str, int] = {}
        for result_kind, values in fuzzy_by_kind.items():
            values.sort(
                key=lambda item: (
                    item[0],
                    str(item[1]["normalized_label"]),
                    str(item[1]["entity_key"]),
                )
            )
            fuzzy_totals[result_kind] = len(values)
            offset = (page - 1) * page_size if kind is not None else 0
            for _distance, row in values[offset : offset + page_size]:
                grouped[result_kind].append(
                    _to_candidate(
                        row,
                        match_field=cast(MusicSearchMatchField, row["fuzzy_match_field"]),
                        match_quality="fuzzy",
                        match_type="fuzzy",
                    )
                )
        totals = MusicSearchKindTotals(
            track=fuzzy_totals.get("track", 0),
            album=fuzzy_totals.get("album", 0),
            artist=fuzzy_totals.get("artist", 0),
        )
    return MusicSearchRepositoryResult(
        status=cast(Literal["ready", "degraded"], state_status),
        generation_id=str(generation_id),
        candidate_index_version=str(state.get("candidate_index_version") or "") or None,
        total_by_kind=totals,
        tracks=grouped["track"],
        albums=grouped["album"],
        artists=grouped["artist"],
    )

"""Canonical-track album attribution and artwork presentation.

This module deliberately separates four identities which legacy consumers
used to infer from ``tracks.album_id``:

* the L2 canonical recording;
* its default Album Project owner;
* the concrete release displayed beside the track; and
* the concrete release supplying the artwork.

Resolvers are read-only and batch-oriented.  They never rebuild Album
Projects from a request path and never rewrite playback/source facts.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import date
from typing import Any, cast

from backend.domains.metadata.album_detail_meta import _select_candidate
from backend.domains.music_search.normalization import normalize_search_text
from backend.domains.playback.album_projects import SOURCE_BUCKET_ORDER
from backend.domains.playback.album_type import classify_album
from backend.domains.playback.track_groups import load_track_group_keys

TRACK_PRESENTATION_POLICY_VERSION = "track_presentation_l2_v1"


@dataclass(frozen=True)
class TrackPresentation:
    canonical_track_id: int
    album_project_id: int | None
    album_project_name: str | None
    display_album_id: int | None
    display_album_name: str | None
    membership_role: str | None
    cover_album_id: int | None
    cover_url: str | None
    cover_source: str
    resolution_status: str

    def payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _ProjectCandidate:
    project_id: int
    canonical_name: str
    primary_album_id: int | None
    primary_album_name: str | None
    release_date: str | None
    scope: str
    project_type: str
    include_in_charts: bool
    is_manual: bool
    membership_role: str
    source_album_id: int | None
    source_album_name: str | None
    source_bucket: str
    is_exclusive: bool
    inferred: bool
    source_release_date: str | None = None


@dataclass(frozen=True)
class _AlbumCandidate:
    album_id: int
    album_name: str | None
    album_type: str | None
    release_date: str | None
    evidence_rank: int
    has_cover: bool


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _placeholders(values: Iterable[object]) -> str:
    return ",".join("?" for _ in values)


def _date_key(value: str | None) -> tuple[int, str]:
    if not value:
        return (1, date.max.isoformat())
    return (0, str(value))


def _spotify_track_id(value: object) -> str:
    result = str(value or "").strip()
    return result.removeprefix("spotify:track:")


def _project_rank(candidate: _ProjectCandidate) -> tuple[Any, ...]:
    bucket_rank = SOURCE_BUCKET_ORDER.get(candidate.source_bucket, 99)
    standard_original = (
        candidate.membership_role == "standard" and candidate.source_bucket == "original_album"
    )
    deluxe_only = candidate.membership_role == "deluxe" or candidate.source_bucket == "deluxe"
    membership_rank = 0 if standard_original else 1 if deluxe_only else 2
    project_rank = 8 if candidate.project_type == "compilation_exclusive" else 0
    scope_rank = 0 if candidate.scope == "release" else 1
    chart_rank = 0 if candidate.include_in_charts else 1
    evidence_rank = 1 if candidate.inferred else 0
    return (
        0 if candidate.is_manual else 1,
        project_rank,
        scope_rank,
        membership_rank,
        bucket_rank,
        chart_rank,
        evidence_rank,
        _date_key(candidate.release_date),
        _date_key(candidate.source_release_date),
        candidate.source_album_id or 0,
        candidate.project_id,
    )


def _canonical_members(
    conn: sqlite3.Connection,
    requested_ids: list[int],
    merge_level: int,
) -> tuple[dict[int, int], dict[int, set[int]]]:
    request_to_canonical = {track_id: track_id for track_id in requested_ids}
    canonical_members = {track_id: {track_id} for track_id in requested_ids}
    if merge_level <= 1 or not all(
        _table_exists(conn, table) for table in ("track_groups", "track_group_members")
    ):
        return request_to_canonical, canonical_members

    keys = load_track_group_keys(conn, merge_level)
    if keys.empty or not {"track_id", "track_agg_id"}.issubset(keys.columns):
        return request_to_canonical, canonical_members

    track_to_canonical: dict[int, int] = {}
    for row in keys[["track_id", "track_agg_id"]].dropna().itertuples(index=False):
        track_to_canonical[int(cast(Any, row.track_id))] = int(cast(Any, row.track_agg_id))

    for requested in requested_ids:
        canonical = track_to_canonical.get(requested, requested)
        request_to_canonical[requested] = canonical
        canonical_members.setdefault(canonical, set()).add(requested)
        canonical_members[canonical].add(canonical)
    target_canonicals = set(request_to_canonical.values())
    for member, canonical in track_to_canonical.items():
        if canonical in target_canonicals:
            canonical_members.setdefault(canonical, set()).add(member)
    return request_to_canonical, canonical_members


def _source_tracks_by_canonical(
    conn: sqlite3.Connection,
    canonical_members: dict[int, set[int]],
) -> dict[int, set[int]]:
    out: dict[int, set[int]] = {canonical: set() for canonical in canonical_members}
    l1_to_canonical = {
        l1_id: canonical for canonical, members in canonical_members.items() for l1_id in members
    }
    l1_ids = sorted(l1_to_canonical)
    if not l1_ids:
        return out
    placeholders = _placeholders(l1_ids)

    if _table_exists(conn, "track_l1_source_links"):
        rows = conn.execute(
            f"""SELECT DISTINCT l1_id, track_id
                  FROM track_l1_source_links
                 WHERE l1_id IN ({placeholders})""",
            l1_ids,
        ).fetchall()
        for row in rows:
            canonical = l1_to_canonical.get(int(row["l1_id"]))
            if canonical is not None:
                out[canonical].add(int(row["track_id"]))

    if _table_exists(conn, "track_l1_identities"):
        rows = conn.execute(
            f"""SELECT l1_id, representative_track_id
                  FROM track_l1_identities
                 WHERE l1_id IN ({placeholders})
                   AND representative_track_id IS NOT NULL""",
            l1_ids,
        ).fetchall()
        for row in rows:
            canonical = l1_to_canonical.get(int(row["l1_id"]))
            if canonical is not None:
                out[canonical].add(int(row["representative_track_id"]))

    # Legacy/fallback identities generally equal their source Track id.
    for canonical, members in canonical_members.items():
        if not out[canonical]:
            out[canonical].update(members)
    return out


def _load_project_candidates(
    conn: sqlite3.Connection,
    source_tracks: dict[int, set[int]],
    merge_level: int,
) -> dict[int, list[_ProjectCandidate]]:
    out: dict[int, list[_ProjectCandidate]] = {canonical: [] for canonical in source_tracks}
    if not _table_exists(conn, "album_project_tracks"):
        return out
    source_to_canonicals: dict[int, set[int]] = {}
    for canonical, member_track_ids in source_tracks.items():
        for track_id in member_track_ids:
            source_to_canonicals.setdefault(track_id, set()).add(canonical)
    source_track_ids = sorted(source_to_canonicals)
    if not source_track_ids:
        return out
    rows = conn.execute(
        f"""SELECT apt.track_id, ap.project_id, ap.canonical_name,
                      ap.primary_album_id, primary_album.album_name AS primary_album_name,
                      ap.release_date, ap.scope, ap.project_type,
                      ap.include_in_charts, ap.is_manual, apt.membership_role,
                      apt.source_album_id, source_album.album_name AS source_album_name,
                      COALESCE(apa.source_bucket, 'other') AS source_bucket,
                      apt.is_exclusive, apt.inferred
                 FROM album_project_tracks apt
                 JOIN album_projects ap ON ap.project_id=apt.project_id
                 LEFT JOIN albums primary_album
                   ON primary_album.album_id=ap.primary_album_id
                 LEFT JOIN albums source_album
                   ON source_album.album_id=apt.source_album_id
                 LEFT JOIN album_project_albums apa
                   ON apa.project_id=apt.project_id
                  AND apa.album_id=COALESCE(apt.source_album_id, ap.primary_album_id)
                WHERE apt.track_id IN ({_placeholders(source_track_ids)})
                  AND apt.min_merge_level<=?""",
        (*source_track_ids, merge_level),
    ).fetchall()
    seen: set[tuple[int, int, int | None, str]] = set()
    for row in rows:
        candidate = _ProjectCandidate(
            project_id=int(row["project_id"]),
            canonical_name=str(row["canonical_name"]),
            primary_album_id=(
                int(row["primary_album_id"]) if row["primary_album_id"] is not None else None
            ),
            primary_album_name=row["primary_album_name"],
            release_date=row["release_date"],
            scope=str(row["scope"]),
            project_type=str(row["project_type"]),
            include_in_charts=bool(row["include_in_charts"]),
            is_manual=bool(row["is_manual"]),
            membership_role=str(row["membership_role"] or "member"),
            source_album_id=(
                int(row["source_album_id"]) if row["source_album_id"] is not None else None
            ),
            source_album_name=row["source_album_name"],
            source_bucket=str(row["source_bucket"] or "other"),
            is_exclusive=bool(row["is_exclusive"]),
            inferred=bool(row["inferred"]),
        )
        for canonical in source_to_canonicals.get(int(row["track_id"]), ()):
            key = (
                canonical,
                candidate.project_id,
                candidate.source_album_id,
                candidate.membership_role,
            )
            if key not in seen:
                out[canonical].append(candidate)
                seen.add(key)
    return out


def _external_ids_by_canonical(
    conn: sqlite3.Connection,
    canonical_members: dict[int, set[int]],
) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {canonical: set() for canonical in canonical_members}
    if not _table_exists(conn, "track_l1_external_ids"):
        return out
    l1_to_canonical = {
        l1_id: canonical for canonical, members in canonical_members.items() for l1_id in members
    }
    l1_ids = sorted(l1_to_canonical)
    if not l1_ids:
        return out
    rows = conn.execute(
        f"""SELECT l1_id, external_track_id
              FROM track_l1_external_ids
             WHERE provider='spotify'
               AND l1_id IN ({_placeholders(l1_ids)})""",
        l1_ids,
    ).fetchall()
    for row in rows:
        canonical = l1_to_canonical.get(int(row["l1_id"]))
        external_id = _spotify_track_id(row["external_track_id"])
        if canonical is not None and external_id:
            out[canonical].add(external_id)
    return out


def _primary_album_catalog_ids(
    conn: sqlite3.Connection,
    project_candidates: dict[int, list[_ProjectCandidate]],
) -> dict[int, set[str]]:
    album_ids = {
        candidate.primary_album_id
        for rows in project_candidates.values()
        for candidate in rows
        if candidate.primary_album_id is not None
    }
    out: dict[int, set[str]] = {album_id: set() for album_id in album_ids}
    if not album_ids:
        return out
    representative: dict[int, _ProjectCandidate] = {}
    for project_rows in project_candidates.values():
        for candidate in project_rows:
            if candidate.primary_album_id is not None:
                representative.setdefault(candidate.primary_album_id, candidate)
    candidate_rows: dict[int, list[dict[str, Any]]] = {album_id: [] for album_id in representative}
    ids = sorted(representative)
    if _table_exists(conn, "album_spotify_links") and _table_exists(conn, "spotify_album_meta"):
        link_rows = conn.execute(
            f"""SELECT asl.album_id, sam.spotify_album_id, sam.album_name,
                       sam.album_type, sam.release_date, sam.track_list,
                       asl.confidence, asl.play_count, 0 AS source_rank
                  FROM album_spotify_links asl
                  JOIN spotify_album_meta sam
                    ON sam.spotify_album_id=asl.spotify_album_id
                 WHERE asl.album_id IN ({_placeholders(ids)})""",
            ids,
        ).fetchall()
        for row in link_rows:
            candidate_rows[int(row["album_id"])].append(dict(row))
    missing = [album_id for album_id, rows in candidate_rows.items() if not rows]
    if missing and _table_exists(conn, "spotify_track_meta"):
        album_track_selects = [
            f"SELECT track_id, album_id FROM tracks WHERE album_id IN ({_placeholders(missing)})"
        ]
        params: list[int] = list(missing)
        if _table_exists(conn, "track_albums"):
            album_track_selects.append(
                f"SELECT track_id, album_id FROM track_albums WHERE album_id IN ({_placeholders(missing)})"
            )
            params.extend(missing)
        fallback_rows = conn.execute(
            f"""WITH album_tracks AS ({" UNION ".join(album_track_selects)})
                  SELECT at.album_id, sam.spotify_album_id, sam.album_name,
                         sam.album_type, sam.release_date, sam.track_list,
                         0.0 AS confidence, 0 AS play_count, 0 AS source_rank
                    FROM album_tracks at
                    JOIN tracks t ON t.track_id=at.track_id
                    JOIN spotify_track_meta stm
                      ON stm.spotify_track_id=t.spotify_track_id
                    JOIN spotify_album_meta sam
                      ON sam.spotify_album_id=stm.spotify_album_id
                   GROUP BY at.album_id, sam.spotify_album_id""",
            params,
        ).fetchall()
        for row in fallback_rows:
            candidate_rows[int(row["album_id"])].append(dict(row))
    for album_id, project in representative.items():
        provider = _select_candidate(
            candidate_rows.get(album_id, []),
            album_name=project.primary_album_name or project.canonical_name,
            project_date=project.release_date,
            project_type=project.project_type,
        )
        if not provider or not provider.get("spotify_album_id"):
            continue
        expected_name = normalize_search_text(project.primary_album_name or project.canonical_name)
        if normalize_search_text(str(provider.get("album_name") or "")) != expected_name:
            continue
        try:
            values = json.loads(str(provider.get("track_list") or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(values, list):
            out[album_id].update(_spotify_track_id(value) for value in values if value)
    return out


def _isrc_map_for_spotify_ids(conn: sqlite3.Connection, spotify_ids: set[str]) -> dict[str, str]:
    if not spotify_ids or not _table_exists(conn, "spotify_track_meta"):
        return {}
    values = sorted(
        {
            variant
            for spotify_id in spotify_ids
            for variant in (spotify_id, f"spotify:track:{spotify_id}")
        }
    )
    rows = conn.execute(
        f"""SELECT spotify_track_id, isrc FROM spotify_track_meta
             WHERE spotify_track_id IN ({_placeholders(values)})
               AND isrc IS NOT NULL AND isrc!=''""",
        values,
    ).fetchall()
    return {
        _spotify_track_id(row[0]): str(row[1]).strip().upper() for row in rows if row[0] and row[1]
    }


def _correct_catalog_memberships(
    conn: sqlite3.Connection,
    candidates: dict[int, list[_ProjectCandidate]],
    canonical_members: dict[int, set[int]],
) -> dict[int, list[_ProjectCandidate]]:
    """Promote observation-only deluxe membership when the primary catalog proves inclusion."""
    external_ids = _external_ids_by_canonical(conn, canonical_members)
    catalog_ids = _primary_album_catalog_ids(conn, candidates)
    isrc_map = _isrc_map_for_spotify_ids(
        conn,
        {
            spotify_id
            for values in (*external_ids.values(), *catalog_ids.values())
            for spotify_id in values
        },
    )
    corrected: dict[int, list[_ProjectCandidate]] = {}
    for canonical, rows in candidates.items():
        ids = external_ids.get(canonical, set())
        identity_isrcs = {isrc_map[value] for value in ids if value in isrc_map}
        corrected[canonical] = []
        for candidate in rows:
            catalog = (
                catalog_ids.get(candidate.primary_album_id, set())
                if candidate.primary_album_id is not None
                else set()
            )
            catalog_isrcs = {isrc_map[value] for value in catalog if value in isrc_map}
            contained = bool(ids.intersection(catalog)) or bool(
                identity_isrcs.intersection(catalog_isrcs)
            )
            if contained and (
                candidate.membership_role != "standard"
                or candidate.source_bucket != "original_album"
            ):
                candidate = replace(
                    candidate,
                    membership_role="standard",
                    source_album_id=candidate.primary_album_id,
                    source_album_name=candidate.primary_album_name,
                    source_bucket="original_album",
                    inferred=False,
                )
            corrected[canonical].append(candidate)
    return corrected


def _album_associations(
    conn: sqlite3.Connection,
    source_tracks: dict[int, set[int]],
) -> tuple[dict[int, dict[int, int]], set[int]]:
    """Return canonical -> album -> strongest evidence rank."""
    out: dict[int, dict[int, int]] = {canonical: {} for canonical in source_tracks}
    source_to_canonicals: dict[int, set[int]] = {}
    for canonical, member_track_ids in source_tracks.items():
        for track_id in member_track_ids:
            source_to_canonicals.setdefault(track_id, set()).add(canonical)
    source_track_ids = sorted(source_to_canonicals)
    if not source_track_ids:
        return out, set()
    placeholders = _placeholders(source_track_ids)
    selects: list[str] = []
    params: list[int] = []
    if "source_album_id" in _table_columns(conn, "plays"):
        selects.append(
            f"""SELECT p.track_id, p.source_album_id AS album_id, 0 AS evidence_rank
                  FROM plays p WHERE p.track_id IN ({placeholders})
                   AND p.source_album_id IS NOT NULL"""
        )
        params.extend(source_track_ids)
    if _table_exists(conn, "track_albums"):
        selects.append(
            f"""SELECT ta.track_id, ta.album_id, 1 AS evidence_rank
                  FROM track_albums ta WHERE ta.track_id IN ({placeholders})"""
        )
        params.extend(source_track_ids)
    selects.append(
        f"""SELECT t.track_id, t.album_id, 2 AS evidence_rank
              FROM tracks t WHERE t.track_id IN ({placeholders})
               AND t.album_id IS NOT NULL"""
    )
    params.extend(source_track_ids)
    rows = conn.execute(
        f"SELECT track_id, album_id, evidence_rank FROM ({' UNION ALL '.join(selects)})",
        params,
    ).fetchall()
    album_ids: set[int] = set()
    for row in rows:
        track_id = int(row["track_id"])
        album_id = int(row["album_id"])
        album_ids.add(album_id)
        for canonical in source_to_canonicals.get(track_id, ()):
            current = out[canonical].get(album_id, 99)
            out[canonical][album_id] = min(current, int(row["evidence_rank"]))
    return out, album_ids


def _load_album_candidates(
    conn: sqlite3.Connection,
    associations: dict[int, dict[int, int]],
    extra_album_ids: set[int],
) -> dict[int, _AlbumCandidate]:
    album_ids = set(extra_album_ids)
    for rows in associations.values():
        album_ids.update(rows)
    if not album_ids:
        return {}
    ids = sorted(album_ids)
    album_columns = _table_columns(conn, "albums")
    album_type_expr = "album_type" if "album_type" in album_columns else "NULL AS album_type"
    release_date_expr = (
        "release_date" if "release_date" in album_columns else "NULL AS release_date"
    )
    image_path_expr = "image_path" if "image_path" in album_columns else "NULL AS image_path"
    image_url_expr = "image_url" if "image_url" in album_columns else "NULL AS image_url"
    albums = {
        int(row["album_id"]): dict(row)
        for row in conn.execute(
            f"""SELECT album_id, album_name, {album_type_expr}, {release_date_expr},
                       {image_path_expr}, {image_url_expr}
                  FROM albums WHERE album_id IN ({_placeholders(ids)})""",
            ids,
        ).fetchall()
    }
    link_rows: dict[int, list[dict[str, Any]]] = {album_id: [] for album_id in ids}
    if _table_exists(conn, "album_spotify_links") and _table_exists(conn, "spotify_album_meta"):
        for row in conn.execute(
            f"""SELECT asl.album_id, sam.album_name, sam.album_type,
                       sam.release_date, sam.image_url, sam.total_tracks,
                       asl.confidence, asl.play_count, asl.track_count
                  FROM album_spotify_links asl
                  JOIN spotify_album_meta sam
                    ON sam.spotify_album_id=asl.spotify_album_id
                 WHERE asl.album_id IN ({_placeholders(ids)})""",
            ids,
        ).fetchall():
            link_rows.setdefault(int(row["album_id"]), []).append(dict(row))

        missing = [album_id for album_id in ids if not link_rows.get(album_id)]
        if missing and _table_exists(conn, "spotify_track_meta"):
            fallback_rows = conn.execute(
                f"""WITH album_tracks AS (
                         SELECT track_id, album_id FROM tracks
                          WHERE album_id IN ({_placeholders(missing)})
                         UNION
                         SELECT track_id, album_id FROM track_albums
                          WHERE album_id IN ({_placeholders(missing)})
                       )
                       SELECT at.album_id, sam.album_name, sam.album_type,
                              sam.release_date, sam.image_url, sam.total_tracks,
                              0.0 AS confidence, 0 AS play_count, 0 AS track_count
                         FROM album_tracks at
                         JOIN tracks t ON t.track_id=at.track_id
                         JOIN spotify_track_meta stm
                           ON stm.spotify_track_id=t.spotify_track_id
                         JOIN spotify_album_meta sam
                           ON sam.spotify_album_id=stm.spotify_album_id
                        GROUP BY at.album_id, sam.spotify_album_id""",
                (*missing, *missing),
            ).fetchall()
            for row in fallback_rows:
                link_rows.setdefault(int(row["album_id"]), []).append(dict(row))

    evidence_by_album: dict[int, int] = {}
    for rows in associations.values():
        for album_id, rank in rows.items():
            evidence_by_album[album_id] = min(evidence_by_album.get(album_id, 99), rank)

    result: dict[int, _AlbumCandidate] = {}
    for album_id in ids:
        row = albums.get(album_id)
        if row is None:
            continue
        local_name = str(row.get("album_name") or "")
        links = link_rows.get(album_id, [])
        exact_links = [
            link
            for link in links
            if str(link["album_name"] or "").casefold() == local_name.casefold()
        ]
        ranked_links = sorted(
            exact_links or links,
            key=lambda link: (
                0 if str(link["album_name"] or "").casefold() == local_name.casefold() else 1,
                -float(link["confidence"] or 0),
                -int(link["track_count"] or 0),
                -int(link["play_count"] or 0),
                str(link["release_date"] or "9999-12-31"),
            ),
        )
        provider = ranked_links[0] if ranked_links else None
        provider_type = str(row.get("album_type") or "").lower() or None
        total_tracks = None
        if provider is not None and provider["album_type"]:
            provider_type = str(provider["album_type"]).lower()
            total_tracks = provider["total_tracks"]
        album_type = classify_album(provider_type, total_tracks=total_tracks)
        release_date = row.get("release_date")
        if not release_date and provider is not None:
            release_date = provider["release_date"]
        has_cover = bool(row.get("image_path") or row.get("image_url")) or any(
            bool(link["image_url"]) for link in links
        )
        result[album_id] = _AlbumCandidate(
            album_id=album_id,
            album_name=local_name or None,
            album_type=album_type,
            release_date=release_date,
            evidence_rank=evidence_by_album.get(album_id, 9),
            has_cover=has_cover,
        )
    return result


def _display_album_id(owner: _ProjectCandidate | None) -> int | None:
    if owner is None:
        return None
    if owner.membership_role == "standard" and owner.source_bucket == "original_album":
        return owner.primary_album_id or owner.source_album_id
    if owner.membership_role == "deluxe" or owner.source_bucket == "deluxe":
        return owner.source_album_id or owner.primary_album_id
    return owner.source_album_id or owner.primary_album_id


def _fallback_display_album(
    candidate_ids: dict[int, int],
    albums: dict[int, _AlbumCandidate],
) -> int | None:
    candidates = [albums[album_id] for album_id in candidate_ids if album_id in albums]
    if not candidates:
        return None
    type_rank = {"lp": 0, "ep": 1, "single": 3, "compilation": 4}
    candidates.sort(
        key=lambda album: (
            type_rank.get(album.album_type or "", 2),
            album.evidence_rank,
            _date_key(album.release_date),
            album.album_id,
        )
    )
    return candidates[0].album_id


def _cover_album(
    candidate_ids: dict[int, int],
    albums: dict[int, _AlbumCandidate],
    *,
    display_album_id: int | None,
    primary_album_id: int | None,
) -> tuple[int | None, str]:
    candidates = [albums[album_id] for album_id in candidate_ids if album_id in albums]
    singles = [album for album in candidates if album.album_type == "single"]
    if singles:
        singles.sort(
            key=lambda album: (
                album.evidence_rank,
                _date_key(album.release_date),
                album.album_id,
            )
        )
        return singles[0].album_id, "single"
    for album_id, source in (
        (display_album_id, "display_album"),
        (primary_album_id, "owner_album"),
    ):
        if album_id is not None and albums.get(album_id):
            return album_id, source
    available = list(candidates)
    if available:
        available.sort(
            key=lambda album: (
                album.evidence_rank,
                _date_key(album.release_date),
                album.album_id,
            )
        )
        return available[0].album_id, "fallback"
    return None, "none"


def resolve_track_presentations(
    conn: sqlite3.Connection,
    track_ids: Iterable[int],
    *,
    merge_level: int = 2,
) -> dict[int, TrackPresentation]:
    """Resolve owner, display release and artwork for canonical track entities."""
    requested = sorted({int(value) for value in track_ids if value is not None})
    if not requested:
        return {}
    request_to_canonical, canonical_members = _canonical_members(conn, requested, merge_level)
    source_tracks = _source_tracks_by_canonical(conn, canonical_members)
    project_candidates = _load_project_candidates(conn, source_tracks, merge_level)
    project_candidates = _correct_catalog_memberships(conn, project_candidates, canonical_members)
    associations, associated_album_ids = _album_associations(conn, source_tracks)
    extra_album_ids: set[int] = set(associated_album_ids)
    for canonical, candidates in project_candidates.items():
        for candidate in candidates:
            if candidate.primary_album_id is not None:
                extra_album_ids.add(candidate.primary_album_id)
            if candidate.source_album_id is not None:
                extra_album_ids.add(candidate.source_album_id)
    albums = _load_album_candidates(conn, associations, extra_album_ids)
    owners: dict[int, _ProjectCandidate | None] = {}
    for canonical, candidates in project_candidates.items():
        enriched = [
            replace(
                candidate,
                source_release_date=(
                    albums[candidate.source_album_id].release_date
                    if candidate.source_album_id in albums
                    else None
                ),
            )
            for candidate in candidates
        ]
        owners[canonical] = min(enriched, key=_project_rank) if enriched else None

    canonical_results: dict[int, TrackPresentation] = {}
    for canonical in set(request_to_canonical.values()):
        owner = owners.get(canonical)
        display_album_id = _display_album_id(owner)
        status = "resolved" if owner is not None else "fallback"
        if display_album_id is None:
            display_album_id = _fallback_display_album(associations.get(canonical, {}), albums)
        if display_album_id is None:
            status = "unresolved"
        primary_album_id = owner.primary_album_id if owner is not None else None
        cover_album_id, cover_source = _cover_album(
            associations.get(canonical, {}),
            albums,
            display_album_id=display_album_id,
            primary_album_id=primary_album_id,
        )
        display = albums.get(display_album_id) if display_album_id is not None else None
        fallback_role = (
            display.album_type
            if display is not None and display.album_type in {"single", "ep", "compilation"}
            else None
        )
        canonical_results[canonical] = TrackPresentation(
            canonical_track_id=canonical,
            album_project_id=owner.project_id if owner is not None else None,
            album_project_name=owner.canonical_name if owner is not None else None,
            display_album_id=display_album_id,
            display_album_name=(
                display.album_name
                if display is not None
                else owner.source_album_name or owner.primary_album_name
                if owner is not None
                else None
            ),
            membership_role=owner.membership_role if owner is not None else fallback_role,
            cover_album_id=cover_album_id,
            cover_url=(
                f"/covers/albums/{cover_album_id}.jpg" if cover_album_id is not None else None
            ),
            cover_source=cover_source,
            resolution_status=status,
        )
    return {
        requested_id: canonical_results[canonical]
        for requested_id, canonical in request_to_canonical.items()
        if canonical in canonical_results
    }


def resolve_track_presentation(
    conn: sqlite3.Connection,
    track_id: int,
    *,
    merge_level: int = 2,
) -> TrackPresentation:
    result = resolve_track_presentations(conn, [track_id], merge_level=merge_level)
    return result[int(track_id)]

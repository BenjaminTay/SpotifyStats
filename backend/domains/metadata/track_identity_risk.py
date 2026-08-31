"""Read-only audit and dry-run planning for risky L1 Spotify ownership.

L1 is the provider ownership layer, not the L2 musical-version layer.  This
module therefore never decides whether two recordings are the same song.  It
only detects cases where one application ``track_id`` owns Spotify entities
that have strong evidence of being different provider recordings.

The production database is never mutated here.  ``simulate_split_plan`` copies
the connection into memory and invokes the existing audited split primitive on
that copy so callers can prove that a generated plan is executable first.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from typing import Any

from backend.domains.metadata.artist_identity import get_artist_identity_map
from backend.domains.metadata.track_identity import (
    bump_track_identity_revision,
    external_ids_for_l1,
    get_track_identity_revision,
    refresh_play_source_links,
    validate_track_identity_invariants,
)

AUDIT_SCHEMA_VERSION = "l1_external_identity_risk_v2"
DEFAULT_DURATION_TOLERANCE_MS = 2_000
STRONG_DURATION_CONFLICT_MS = 10_000

_VERSION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("video", re.compile(r"\b(?:official\s+)?(?:music\s+)?video\b", re.I)),
    ("instrumental", re.compile(r"\b(?:instrumental|karaoke)\b|伴奏|純音樂|纯音乐", re.I)),
    ("acoustic", re.compile(r"\bacoustic\b|不插電|不插电", re.I)),
    ("live", re.compile(r"\blive\b|現場(?:版|錄音)?|现场(?:版|录音)?", re.I)),
    ("remix", re.compile(r"\b(?:re)?mix\b|混音", re.I)),
    ("demo", re.compile(r"\bdemo\b|試聽版|试听版", re.I)),
    ("rerecord", re.compile(r"taylor(?:'|’)?s\s+version|重錄(?:版)?|重录(?:版)?", re.I)),
    ("remaster", re.compile(r"\b(?:\d{4}\s+)?remaster(?:ed)?\b|重新灌錄|重新灌录", re.I)),
    ("radio_edit", re.compile(r"\bradio\s+(?:edit|version)\b", re.I)),
    ("orchestral", re.compile(r"\borchestral\b|管弦樂版|管弦乐版", re.I)),
    ("piano", re.compile(r"\bpiano\s+version\b|鋼琴版|钢琴版", re.I)),
    ("voice_memo", re.compile(r"\bvoice\s+memo\b", re.I)),
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _normalized_title(value: object) -> str:
    rendered = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in rendered if character.isalnum())


def _version_tags(*values: object) -> list[str]:
    rendered = " ".join(str(value or "") for value in values)
    return [name for name, pattern in _VERSION_PATTERNS if pattern.search(rendered)]


def _plan_token(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def _play_columns(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    columns = _columns(conn, "plays")
    spotify = "spotify_track_id_at_play" if "spotify_track_id_at_play" in columns else None
    content = "content_type" if "content_type" in columns else None
    return spotify, content


def _canonical_artist_id(artist_map: dict[int, Any], artist_id: Any) -> int | None:
    if artist_id is None:
        return None
    value = int(artist_id)
    resolution = artist_map.get(value)
    return int(resolution.canonical_artist_id) if resolution is not None else value


def _content_types_for_external_id(
    conn: sqlite3.Connection,
    external_track_id: str,
    spotify_column: str | None,
    content_column: str | None,
) -> list[str]:
    if not spotify_column or not content_column:
        return []
    return [
        str(row[0]).strip().lower()
        for row in conn.execute(
            f"""SELECT DISTINCT {content_column} FROM plays
                  WHERE {spotify_column}=? AND {content_column} IS NOT NULL
                    AND TRIM({content_column})!=''
                  ORDER BY {content_column}""",
            (external_track_id,),
        ).fetchall()
    ]


def _shared_isrc_target_l1_ids(
    conn: sqlite3.Connection,
    *,
    source_l1_id: int,
    source_canonical_artist_id: int | None,
    item: dict[str, Any],
    artist_map: dict[int, Any],
    spotify_column: str | None,
    content_column: str | None,
) -> list[int]:
    """Resolve an existing owner through provider evidence, not one projection row."""

    if not item["isrc"] or item["duration_ms"] is None:
        return []
    rows = conn.execute(
        """SELECT DISTINCT external.l1_id, tracks.artist_id,
                          meta.external_track_id, meta.track_name, meta.duration_ms,
                          albums.album_name
             FROM track_l1_external_ids external
             JOIN track_l1_identities identity ON identity.l1_id=external.l1_id
             JOIN tracks ON tracks.track_id=identity.representative_track_id
             JOIN (
                 SELECT spotify_track_id AS external_track_id, track_name,
                        duration_ms, isrc, spotify_album_id
                   FROM spotify_track_meta
             ) meta ON meta.external_track_id=external.external_track_id
             LEFT JOIN spotify_album_meta albums
               ON albums.spotify_album_id=meta.spotify_album_id
            WHERE external.provider='spotify'
              AND identity.identity_status='active'
              AND external.l1_id!=?
              AND UPPER(TRIM(meta.isrc))=?
            ORDER BY external.l1_id, meta.external_track_id""",
        (int(source_l1_id), str(item["isrc"])),
    ).fetchall()
    eligible: set[int] = set()
    item_tags = set(item["version_tags"])
    for target_l1_id, artist_id, token, track_name, duration_ms, album_name in rows:
        if _canonical_artist_id(artist_map, artist_id) != source_canonical_artist_id:
            continue
        if (
            duration_ms is None
            or abs(int(duration_ms) - int(item["duration_ms"])) > DEFAULT_DURATION_TOLERANCE_MS
        ):
            continue
        content_types = _content_types_for_external_id(
            conn, str(token), spotify_column, content_column
        )
        target_tags = set(_version_tags(track_name, album_name, *content_types))
        if "video" in content_types:
            target_tags.add("video")
        if target_tags != item_tags:
            continue
        eligible.add(int(target_l1_id))
    return sorted(eligible)


def _creation_target_track_ids(
    conn: sqlite3.Connection,
    *,
    source_l1_id: int,
    source_canonical_artist_id: int | None,
    item: dict[str, Any],
    artist_map: dict[int, Any],
    spotify_column: str | None,
) -> list[int]:
    """Find an existing Track that can safely receive a missing compatibility L1.

    L1 remains ``tracks.track_id``.  This deliberately refuses to create a
    synthetic provider identity when the provider id cannot be tied to one
    distinct existing Track.
    """

    track_ids = {int(value) for value in item["projection_track_ids"]}
    if spotify_column:
        track_ids.update(
            int(row[0])
            for row in conn.execute(
                f"""SELECT DISTINCT track_id FROM plays
                      WHERE {spotify_column}=? AND track_id IS NOT NULL""",
                (str(item["spotify_track_id"]),),
            ).fetchall()
        )
    eligible: list[int] = []
    for track_id in sorted(track_ids):
        if track_id == int(source_l1_id):
            continue
        row = conn.execute(
            "SELECT track_name, artist_id FROM tracks WHERE track_id=?", (track_id,)
        ).fetchone()
        if row is None:
            continue
        if _canonical_artist_id(artist_map, row[1]) != source_canonical_artist_id:
            continue
        if _normalized_title(row[0]) != item["normalized_title"]:
            continue
        identity = conn.execute(
            "SELECT identity_status FROM track_l1_identities WHERE l1_id=?", (track_id,)
        ).fetchone()
        if identity is not None and str(identity[0]) == "active":
            continue
        if conn.execute(
            "SELECT 1 FROM spotify_track_owners WHERE track_id=? LIMIT 1", (track_id,)
        ).fetchone():
            continue
        if conn.execute(
            "SELECT 1 FROM track_l1_external_ids WHERE l1_id=? LIMIT 1", (track_id,)
        ).fetchone():
            continue
        eligible.append(track_id)
    return eligible


def _external_items(conn: sqlite3.Connection, l1_id: int) -> list[dict[str, Any]]:
    spotify_column, content_column = _play_columns(conn)
    metadata_available = _table_exists(conn, "spotify_track_meta")
    album_metadata_available = _table_exists(conn, "spotify_album_meta")
    artist_map = get_artist_identity_map(conn)
    source_artist_row = conn.execute(
        """SELECT tracks.artist_id
             FROM track_l1_identities identity
             JOIN tracks ON tracks.track_id=identity.representative_track_id
            WHERE identity.l1_id=?""",
        (int(l1_id),),
    ).fetchone()
    source_artist_id = (
        int(source_artist_row[0]) if source_artist_row and source_artist_row[0] else None
    )
    source_canonical_artist_id = _canonical_artist_id(artist_map, source_artist_id)
    rows = conn.execute(
        """SELECT external.external_track_id, external.is_primary,
                  external.evidence_type
             FROM track_l1_external_ids external
            WHERE external.provider='spotify' AND external.l1_id=?
            ORDER BY external.is_primary DESC, external.external_track_id""",
        (int(l1_id),),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for external_track_id, is_primary, evidence_type in rows:
        token = str(external_track_id)
        meta = (
            conn.execute(
                """SELECT track_name, duration_ms, explicit, isrc, spotify_album_id
                     FROM spotify_track_meta WHERE spotify_track_id=?""",
                (token,),
            ).fetchone()
            if metadata_available
            else None
        )
        projections = conn.execute(
            """SELECT t.track_id, t.track_name, t.artist_id,
                      COALESCE(a.artist_name, '')
                 FROM tracks t LEFT JOIN artists a ON a.artist_id=t.artist_id
                WHERE t.spotify_track_id=? ORDER BY t.track_id""",
            (token,),
        ).fetchall()
        canonical_artists = sorted(
            {
                value
                for row in projections
                if (value := _canonical_artist_id(artist_map, row[2])) is not None
            }
        )
        # Historical migration aliases often have provider metadata and plays
        # but no independent local Track projection.  They are still attached
        # to this L1 owner, whose representative artist is known.  Treat that
        # owner artist as inherited evidence so same-ISRC reissues can be kept;
        # do not turn the absence of a duplicate projection into 800+ false
        # review items.
        if not canonical_artists and source_canonical_artist_id is not None:
            canonical_artists = [source_canonical_artist_id]
        album = None
        if meta is not None and meta[4] and album_metadata_available:
            album = conn.execute(
                """SELECT album_name, album_type, release_date
                     FROM spotify_album_meta WHERE spotify_album_id=?""",
                (str(meta[4]),),
            ).fetchone()
        play_count = 0
        content_types: list[str] = []
        if spotify_column:
            play_count = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM plays WHERE {spotify_column}=?", (token,)
                ).fetchone()[0]
            )
            content_types = _content_types_for_external_id(
                conn, token, spotify_column, content_column
            )
        track_name = (
            str(meta[0])
            if meta is not None and meta[0]
            else (str(projections[0][1]) if projections else "")
        )
        album_name = str(album[0]) if album is not None and album[0] else ""
        tags = _version_tags(track_name, album_name, *content_types)
        if "video" in content_types and "video" not in tags:
            tags.append("video")
        item = {
            "spotify_track_id": token,
            "is_primary": bool(is_primary),
            "evidence_type": str(evidence_type),
            "track_name": track_name,
            "normalized_title": _normalized_title(track_name),
            "duration_ms": int(meta[1]) if meta is not None and meta[1] is not None else None,
            "explicit": bool(meta[2]) if meta is not None and meta[2] is not None else None,
            "isrc": str(meta[3]).strip().upper() if meta is not None and meta[3] else None,
            "spotify_album_id": str(meta[4]) if meta is not None and meta[4] else None,
            "album_name": album_name or None,
            "album_type": str(album[1]) if album is not None and album[1] else None,
            "release_date": str(album[2]) if album is not None and album[2] else None,
            "projection_track_ids": [int(row[0]) for row in projections],
            "projection_artist_ids": [int(row[2]) for row in projections if row[2] is not None],
            "canonical_artist_ids": canonical_artists,
            "play_count": play_count,
            "content_types": content_types,
            "version_tags": sorted(tags),
        }
        direct_target_l1_ids: set[int] = set()
        for projection in projections:
            target_l1_id = int(projection[0])
            if target_l1_id == int(l1_id):
                continue
            target_row = conn.execute(
                """SELECT tracks.artist_id, tracks.track_name
                     FROM track_l1_identities identity
                     JOIN tracks ON tracks.track_id=identity.representative_track_id
                    WHERE identity.l1_id=? AND identity.identity_status='active'""",
                (target_l1_id,),
            ).fetchone()
            if target_row is None:
                continue
            if _canonical_artist_id(artist_map, target_row[0]) != source_canonical_artist_id:
                continue
            if _normalized_title(target_row[1]) != item["normalized_title"]:
                continue
            direct_target_l1_ids.add(target_l1_id)
        eligible_target_l1_ids = sorted(direct_target_l1_ids)
        target_resolution = "direct_projection" if eligible_target_l1_ids else None
        if len(eligible_target_l1_ids) != 1 and metadata_available:
            shared_isrc_targets = _shared_isrc_target_l1_ids(
                conn,
                source_l1_id=l1_id,
                source_canonical_artist_id=source_canonical_artist_id,
                item=item,
                artist_map=artist_map,
                spotify_column=spotify_column,
                content_column=content_column,
            )
            if len(shared_isrc_targets) == 1:
                eligible_target_l1_ids = shared_isrc_targets
                target_resolution = "shared_isrc_duration_semantics"
            elif shared_isrc_targets:
                eligible_target_l1_ids = shared_isrc_targets
                target_resolution = "ambiguous_shared_isrc"
        item["eligible_target_l1_ids"] = eligible_target_l1_ids
        item["target_resolution"] = target_resolution
        item["creation_target_track_ids"] = _creation_target_track_ids(
            conn,
            source_l1_id=l1_id,
            source_canonical_artist_id=source_canonical_artist_id,
            item=item,
            artist_map=artist_map,
            spotify_column=spotify_column,
        )
        result.append(item)
    return result


def _reference_item(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Prefer a played base/audio item so a variant is not accidentally retained."""

    return max(
        items,
        key=lambda item: (
            not bool(item["version_tags"]),
            "video" not in item["content_types"],
            int(item["play_count"]),
            bool(item["is_primary"]),
            bool(item["isrc"]),
            item["duration_ms"] is not None,
            item["spotify_track_id"],
        ),
    )


def _compare_items(
    reference: dict[str, Any], candidate: dict[str, Any]
) -> tuple[str, list[str], list[str]]:
    """Return recommendation, evidence and blockers for one external id."""

    evidence: list[str] = []
    blockers: list[str] = []
    reference_artists = set(reference["canonical_artist_ids"])
    candidate_artists = set(candidate["canonical_artist_ids"])
    same_artist = bool(
        reference_artists and candidate_artists and reference_artists == candidate_artists
    )
    if reference_artists and candidate_artists and reference_artists != candidate_artists:
        evidence.append("canonical_artist_conflict")

    reference_isrc = reference["isrc"]
    candidate_isrc = candidate["isrc"]
    if reference_isrc and candidate_isrc:
        evidence.append("same_isrc" if reference_isrc == candidate_isrc else "different_isrc")

    duration_delta = None
    if reference["duration_ms"] is not None and candidate["duration_ms"] is not None:
        duration_delta = abs(int(reference["duration_ms"]) - int(candidate["duration_ms"]))
        if duration_delta <= DEFAULT_DURATION_TOLERANCE_MS:
            evidence.append("duration_close")
        elif duration_delta >= STRONG_DURATION_CONFLICT_MS:
            evidence.append("duration_conflict")
        else:
            evidence.append("duration_uncertain")

    same_title = bool(
        reference["normalized_title"]
        and reference["normalized_title"] == candidate["normalized_title"]
    )
    evidence.append("same_normalized_title" if same_title else "different_normalized_title")
    reference_tags = set(reference["version_tags"])
    candidate_tags = set(candidate["version_tags"])
    if reference_tags != candidate_tags:
        evidence.append("semantic_version_conflict")
    if reference["explicit"] is not None and candidate["explicit"] is not None:
        if reference["explicit"] != candidate["explicit"]:
            evidence.append("explicit_flag_conflict")

    reference_media = set(reference["content_types"])
    candidate_media = set(candidate["content_types"])
    media_conflict = bool(
        reference_media and candidate_media and reference_media != candidate_media
    )
    if media_conflict and "video" in reference_media | candidate_media:
        evidence.append("audio_video_conflict")

    strong_different_song = (
        not same_title
        and reference_isrc
        and candidate_isrc
        and reference_isrc != candidate_isrc
        and duration_delta is not None
        and duration_delta >= STRONG_DURATION_CONFLICT_MS
    )
    strong_version_split = (
        reference_tags != candidate_tags
        and bool(reference_tags or candidate_tags)
        and (
            (reference_isrc and candidate_isrc and reference_isrc != candidate_isrc)
            or (duration_delta is not None and duration_delta >= STRONG_DURATION_CONFLICT_MS)
        )
    )
    strong_artist_split = bool(reference_artists and candidate_artists) and not same_artist
    target_l1_ids = candidate["eligible_target_l1_ids"]
    creation_target_track_ids = candidate["creation_target_track_ids"]
    has_unique_target = len(target_l1_ids) == 1 or (
        not target_l1_ids and len(creation_target_track_ids) == 1
    )
    if not reference["track_name"] or not candidate["track_name"]:
        blockers.append("missing_track_name")
    if not has_unique_target:
        if not candidate["projection_track_ids"] and not creation_target_track_ids:
            blockers.append("missing_local_track_projection")
        blockers.append("missing_unique_existing_target_l1")
        if strong_artist_split or strong_different_song or strong_version_split:
            blockers.append("provider_identity_requires_distinct_track_owner")
    if not blockers and (strong_artist_split or strong_different_song or strong_version_split):
        return "split", sorted(set(evidence)), blockers

    safe_keep = (
        same_artist
        and same_title
        and reference_isrc
        and reference_isrc == candidate_isrc
        and duration_delta is not None
        and duration_delta <= DEFAULT_DURATION_TOLERANCE_MS
        and reference_tags == candidate_tags
        and not media_conflict
    )
    if safe_keep:
        return "keep", sorted(set(evidence)), blockers
    return "review", sorted(set(evidence)), blockers


def _shadow_identity_plan(
    conn: sqlite3.Connection, *, protected_l1_ids: set[int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Plan retirement of compatibility identities already projected elsewhere."""

    play_columns = _columns(conn, "plays")
    candidates: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    rows = conn.execute(
        """SELECT l1_id, COALESCE(fallback_track_id, representative_track_id)
             FROM track_l1_identities
            WHERE identity_status='active'
            ORDER BY l1_id"""
    ).fetchall()
    for l1_id_raw, track_id_raw in rows:
        l1_id = int(l1_id_raw)
        if track_id_raw is None or l1_id in protected_l1_ids:
            continue
        track_id = int(track_id_raw)
        if conn.execute(
            "SELECT 1 FROM track_l1_external_ids WHERE l1_id=? LIMIT 1", (l1_id,)
        ).fetchone():
            continue
        if conn.execute(
            "SELECT 1 FROM spotify_track_owners WHERE track_id=? LIMIT 1", (l1_id,)
        ).fetchone():
            continue
        raw_play_count = 0
        if "track_id" in play_columns:
            raw_play_count = int(
                conn.execute("SELECT COUNT(*) FROM plays WHERE track_id=?", (track_id,)).fetchone()[
                    0
                ]
            )
        linked_play_count = int(
            conn.execute(
                """SELECT COALESCE(SUM(observed_plays), 0)
                     FROM track_l1_source_links
                    WHERE l1_id=? AND evidence_type='play_at_time'""",
                (l1_id,),
            ).fetchone()[0]
        )
        if raw_play_count or linked_play_count:
            continue
        target_l1_ids = sorted(
            {
                int(row[0])
                for row in conn.execute(
                    """SELECT DISTINCT links.l1_id
                         FROM track_l1_source_links links
                         JOIN track_l1_identities target ON target.l1_id=links.l1_id
                        WHERE links.track_id=?
                          AND links.evidence_type='track_projection'
                          AND links.l1_id!=?
                          AND target.identity_status='active'
                          AND EXISTS (
                              SELECT 1 FROM spotify_track_owners target_owner
                               WHERE target_owner.track_id=links.l1_id
                          )
                        ORDER BY links.l1_id""",
                    (track_id, l1_id),
                ).fetchall()
            }
        )
        if not target_l1_ids:
            continue
        blockers: list[str] = []
        if len(target_l1_ids) != 1:
            blockers.append("ambiguous_projection_owner")
        blockers.extend(_shadow_governance_blockers(conn, l1_id))
        item = {
            "l1_id": l1_id,
            "track_id": track_id,
            "target_l1_ids": target_l1_ids,
            "recommendation": "supersede" if not blockers else "review",
            "blockers": blockers,
        }
        candidates.append(item)
        if not blockers:
            operations.append(
                {
                    "operation": "supersede_shadow_identity",
                    "source_l1_id": l1_id,
                    "target_l1_id": target_l1_ids[0],
                    "reason": "automatic L1 shadow cleanup: zero play/external evidence and projected to active owner",
                    "preconditions": {
                        "track_id": track_id,
                        "raw_play_count": 0,
                        "external_id_count": 0,
                    },
                }
            )
    return candidates, operations


def _shadow_governance_blockers(conn: sqlite3.Connection, l1_id: int) -> list[str]:
    """Return only live governance references; historical rows remain auditable."""

    blockers: list[str] = []
    if _table_exists(conn, "track_group_l1_members") and _table_exists(conn, "track_groups"):
        active_group = conn.execute(
            """SELECT 1
                 FROM track_group_l1_members members
                 JOIN track_groups groups ON groups.group_id=members.group_id
                WHERE members.l1_id=? AND groups.group_status='active'
                LIMIT 1""",
            (int(l1_id),),
        ).fetchone()
        if active_group:
            blockers.append("active_group_reference")
    if _table_exists(conn, "track_group_candidates"):
        unresolved_candidate = conn.execute(
            """SELECT 1 FROM track_group_candidates
                WHERE (original_l1_id=? OR candidate_l1_id=?)
                  AND status IN ('pending', 'accepted')
                LIMIT 1""",
            (int(l1_id), int(l1_id)),
        ).fetchone()
        if unresolved_candidate:
            blockers.append("unresolved_group_candidate_reference")
    return blockers


def build_l1_external_identity_risk_plan(
    conn: sqlite3.Connection, *, include_keep: bool = True
) -> dict[str, Any]:
    """Build a deterministic and strictly read-only L1 ownership plan."""

    required = {
        "tracks",
        "artists",
        "plays",
        "track_l1_identities",
        "track_l1_external_ids",
        "track_l1_source_links",
        "spotify_track_owners",
        "track_identity_state",
    }
    missing = sorted(table for table in required if not _table_exists(conn, table))
    if missing:
        return {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "status": "blocked",
            "missing_tables": missing,
            "owners": [],
            "operations": [],
        }

    before_changes = conn.total_changes
    l1_ids = [
        int(row[0])
        for row in conn.execute(
            """SELECT external.l1_id
                 FROM track_l1_external_ids external
                 JOIN track_l1_identities identity ON identity.l1_id=external.l1_id
                WHERE external.provider='spotify' AND identity.identity_status='active'
                GROUP BY external.l1_id HAVING COUNT(*)>1
                ORDER BY external.l1_id"""
        ).fetchall()
    ]
    owners: list[dict[str, Any]] = []
    all_owners: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    for l1_id in l1_ids:
        items = _external_items(conn, l1_id)
        reference = _reference_item(items)
        item_results: list[dict[str, Any]] = []
        for item in items:
            recommendation: str
            evidence: list[str]
            blockers: list[str]
            if item["spotify_track_id"] == reference["spotify_track_id"]:
                recommendation, evidence, blockers = "keep", ["reference_external_id"], []
            else:
                recommendation, evidence, blockers = _compare_items(reference, item)
            item_result = {
                **item,
                "recommendation": recommendation,
                "evidence": evidence,
                "blockers": blockers,
            }
            item_results.append(item_result)
            if recommendation == "split":
                existing_targets = item["eligible_target_l1_ids"]
                creation_targets = item["creation_target_track_ids"]
                operation_name = (
                    "reassign_external_identity"
                    if len(existing_targets) == 1
                    else "create_provider_l1_and_reassign"
                )
                target_l1_id = int(existing_targets[0] if existing_targets else creation_targets[0])
                operations.append(
                    {
                        "operation": operation_name,
                        "source_l1_id": l1_id,
                        "target_l1_id": target_l1_id,
                        "provider": "spotify",
                        "external_track_id": item["spotify_track_id"],
                        "reason": "automatic L1 ownership correction: " + ",".join(evidence),
                        "preconditions": {
                            "reference_external_track_id": reference["spotify_track_id"],
                            "local_projection_track_ids": item["projection_track_ids"],
                            "target_resolution": item["target_resolution"]
                            or "existing_track_without_active_l1",
                        },
                    }
                )
        recommendations = Counter(item["recommendation"] for item in item_results)
        owner_recommendation = (
            "split"
            if recommendations["split"]
            else ("review" if recommendations["review"] else "keep")
        )
        owner_result = {
            "l1_id": l1_id,
            "recommendation": owner_recommendation,
            "reference_external_track_id": reference["spotify_track_id"],
            "external_ids": item_results,
        }
        all_owners.append(owner_result)
        if include_keep or owner_recommendation != "keep":
            owners.append(owner_result)

    protected_l1_ids = {int(item["target_l1_id"]) for item in operations}
    shadow_identities, shadow_operations = _shadow_identity_plan(
        conn, protected_l1_ids=protected_l1_ids
    )
    operations.extend(shadow_operations)

    summary = {
        "multi_spotify_id_l1_count": len(l1_ids),
        "reported_l1_count": len(owners),
        "keep_l1_count": sum(item["recommendation"] == "keep" for item in all_owners),
        "split_l1_count": sum(item["recommendation"] == "split" for item in all_owners),
        "review_l1_count": sum(item["recommendation"] == "review" for item in all_owners),
        "auto_split_operation_count": sum(
            item["operation"] != "supersede_shadow_identity" for item in operations
        ),
        "existing_target_split_operation_count": sum(
            item["operation"] == "reassign_external_identity" for item in operations
        ),
        "created_target_split_operation_count": sum(
            item["operation"] == "create_provider_l1_and_reassign" for item in operations
        ),
        "shadow_identity_candidate_count": len(shadow_identities),
        "auto_supersede_operation_count": len(shadow_operations),
        "blocked_shadow_identity_count": sum(
            item["recommendation"] == "review" for item in shadow_identities
        ),
        "multiple_isrc_l1_count": sum(
            len({item["isrc"] for item in owner["external_ids"] if item["isrc"]}) > 1
            for owner in all_owners
        ),
        "duration_conflict_l1_count": sum(
            any("duration_conflict" in item["evidence"] for item in owner["external_ids"])
            for owner in all_owners
        ),
        "version_conflict_l1_count": sum(
            any("semantic_version_conflict" in item["evidence"] for item in owner["external_ids"])
            for owner in all_owners
        ),
        "video_conflict_l1_count": sum(
            any("audio_video_conflict" in item["evidence"] for item in owner["external_ids"])
            for owner in all_owners
        ),
    }
    token_payload = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "track_identity_revision": get_track_identity_revision(conn),
        "owners": [
            {
                "l1_id": owner["l1_id"],
                "reference": owner["reference_external_track_id"],
                "external_ids": [
                    (item["spotify_track_id"], item["recommendation"])
                    for item in owner["external_ids"]
                ],
            }
            for owner in all_owners
        ],
        "operations": operations,
        "shadow_identities": shadow_identities,
    }
    result = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "track_identity_revision": token_payload["track_identity_revision"],
        "status": "ready",
        "summary": summary,
        "owners": owners,
        "shadow_identities": shadow_identities,
        "operations": operations,
        "confirmation_token": _plan_token(token_payload),
    }
    if conn.total_changes != before_changes:
        raise RuntimeError("L1 external identity audit unexpectedly mutated the database")
    return result


class L1IdentitySplitPlanError(RuntimeError):
    """The confirmed plan drifted or would weaken identity invariants."""


def _health_counts(health: object) -> dict[str, int]:
    return {
        key: int(value)
        for key, value in vars(health).items()
        if isinstance(value, int) and not isinstance(value, bool)
    }


def _set_primary_external(conn: sqlite3.Connection, l1_id: int) -> None:
    row = conn.execute(
        """SELECT external_track_id FROM track_l1_external_ids
            WHERE l1_id=? AND provider='spotify'
            ORDER BY is_primary DESC, external_track_id LIMIT 1""",
        (int(l1_id),),
    ).fetchone()
    conn.execute(
        """UPDATE track_l1_external_ids SET is_primary=0
            WHERE l1_id=? AND provider='spotify'""",
        (int(l1_id),),
    )
    if row is not None:
        conn.execute(
            """UPDATE track_l1_external_ids SET is_primary=1
                WHERE l1_id=? AND provider='spotify' AND external_track_id=?""",
            (int(l1_id), str(row[0])),
        )


def _reassign_external_identity(conn: sqlite3.Connection, operation: dict[str, Any]) -> None:
    source = int(operation["source_l1_id"])
    target = int(operation["target_l1_id"])
    token = str(operation["external_track_id"])
    if source == target:
        raise L1IdentitySplitPlanError("source and target L1 must be different")
    active = conn.execute(
        """SELECT COUNT(*) FROM track_l1_identities
            WHERE l1_id IN (?, ?) AND identity_status='active'""",
        (source, target),
    ).fetchone()[0]
    if int(active) != 2:
        raise L1IdentitySplitPlanError(
            f"source/target identity is not active for Spotify id {token}"
        )
    owner = conn.execute(
        """SELECT external.l1_id, owners.track_id
             FROM track_l1_external_ids external
             JOIN spotify_track_owners owners
               ON owners.spotify_track_id=external.external_track_id
            WHERE external.provider='spotify' AND external.external_track_id=?""",
        (token,),
    ).fetchone()
    if owner is None or int(owner[0]) != source or int(owner[1]) != source:
        raise L1IdentitySplitPlanError(f"Spotify ownership drifted for {token}")
    before_payload = {
        str(source): external_ids_for_l1(conn, source, provider="spotify"),
        str(target): external_ids_for_l1(conn, target, provider="spotify"),
    }
    conn.execute(
        """UPDATE spotify_track_owners
              SET track_id=?, evidence_type='manual_override', updated_at=datetime('now')
            WHERE spotify_track_id=?""",
        (target, token),
    )
    conn.execute(
        """UPDATE track_l1_external_ids
              SET l1_id=?, is_primary=0, evidence_type='manual_confirmed',
                  updated_at=datetime('now')
            WHERE provider='spotify' AND external_track_id=?""",
        (target, token),
    )
    for track_id in operation["preconditions"]["local_projection_track_ids"]:
        conn.execute(
            """DELETE FROM track_l1_source_links
                WHERE l1_id=? AND track_id=? AND evidence_type='track_projection'""",
            (source, int(track_id)),
        )
        conn.execute(
            """INSERT OR IGNORE INTO track_l1_source_links(
                   l1_id, track_id, evidence_type, observed_plays
               ) VALUES (?, ?, 'track_projection', 0)""",
            (target, int(track_id)),
        )
    _set_primary_external(conn, source)
    _set_primary_external(conn, target)
    if _table_exists(conn, "track_identity_events"):
        conn.execute(
            """INSERT INTO track_identity_events(
                   action, survivor_l1_id, affected_l1_ids,
                   before_json, after_json, reason
               ) VALUES ('split', ?, ?, ?, ?, ?)""",
            (
                source,
                json.dumps([target]),
                json.dumps(before_payload, ensure_ascii=False, sort_keys=True),
                json.dumps(
                    {
                        str(source): external_ids_for_l1(conn, source, provider="spotify"),
                        str(target): external_ids_for_l1(conn, target, provider="spotify"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                str(operation["reason"]),
            ),
        )


def _ensure_provider_target_identity(conn: sqlite3.Connection, operation: dict[str, Any]) -> None:
    target = int(operation["target_l1_id"])
    if conn.execute("SELECT 1 FROM tracks WHERE track_id=?", (target,)).fetchone() is None:
        raise L1IdentitySplitPlanError(f"target track {target} no longer exists")
    row = conn.execute(
        "SELECT identity_status FROM track_l1_identities WHERE l1_id=?", (target,)
    ).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO track_l1_identities(
                   l1_id, provider, external_track_id, fallback_track_id,
                   identity_status, representative_track_id
               ) VALUES (?, 'local', NULL, ?, 'active', ?)""",
            (target, target, target),
        )
    elif str(row[0]) == "superseded":
        conn.execute(
            """UPDATE track_l1_identities
                  SET provider='local', external_track_id=NULL,
                      fallback_track_id=?, identity_status='active',
                      representative_track_id=?, updated_at=datetime('now')
                WHERE l1_id=?""",
            (target, target, target),
        )
    else:
        raise L1IdentitySplitPlanError(
            f"target track {target} unexpectedly gained an active L1 identity"
        )


def _supersede_shadow_identity(conn: sqlite3.Connection, operation: dict[str, Any]) -> None:
    source = int(operation["source_l1_id"])
    target = int(operation["target_l1_id"])
    track_id = int(operation["preconditions"]["track_id"])
    source_row = conn.execute(
        """SELECT identity_status, COALESCE(fallback_track_id, representative_track_id)
             FROM track_l1_identities WHERE l1_id=?""",
        (source,),
    ).fetchone()
    if source_row is None or str(source_row[0]) != "active" or int(source_row[1]) != track_id:
        raise L1IdentitySplitPlanError(f"shadow identity {source} drifted")
    if (
        conn.execute(
            "SELECT 1 FROM track_l1_external_ids WHERE l1_id=? LIMIT 1", (source,)
        ).fetchone()
        or conn.execute(
            "SELECT 1 FROM spotify_track_owners WHERE track_id=? LIMIT 1", (source,)
        ).fetchone()
    ):
        raise L1IdentitySplitPlanError(f"shadow identity {source} gained provider evidence")
    governance_blockers = _shadow_governance_blockers(conn, source)
    if governance_blockers:
        raise L1IdentitySplitPlanError(
            f"shadow identity {source} gained live governance references: "
            + ",".join(governance_blockers)
        )
    if int(conn.execute("SELECT COUNT(*) FROM plays WHERE track_id=?", (track_id,)).fetchone()[0]):
        raise L1IdentitySplitPlanError(f"shadow identity {source} gained play evidence")
    target_link = conn.execute(
        """SELECT 1 FROM track_l1_source_links links
             JOIN track_l1_identities identity ON identity.l1_id=links.l1_id
            WHERE links.l1_id=? AND links.track_id=?
              AND links.evidence_type='track_projection'
              AND identity.identity_status='active'""",
        (target, track_id),
    ).fetchone()
    if target_link is None:
        raise L1IdentitySplitPlanError(f"shadow target {target} drifted")
    before_payload = {
        "shadow_l1_id": source,
        "track_id": track_id,
        "projection_owner_l1_id": target,
    }
    conn.execute("DELETE FROM track_l1_source_links WHERE l1_id=?", (source,))
    conn.execute(
        """UPDATE track_l1_identities
              SET identity_status='superseded', updated_at=datetime('now')
            WHERE l1_id=?""",
        (source,),
    )
    if _table_exists(conn, "track_identity_events"):
        conn.execute(
            """INSERT INTO track_identity_events(
                   action, survivor_l1_id, affected_l1_ids,
                   before_json, after_json, reason
               ) VALUES ('merge', ?, ?, ?, ?, ?)""",
            (
                target,
                json.dumps([source]),
                json.dumps(before_payload, ensure_ascii=False, sort_keys=True),
                json.dumps(
                    {**before_payload, "identity_status": "superseded"},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                str(operation["reason"]),
            ),
        )


def _table_digest(conn: sqlite3.Connection, table: str) -> str:
    digest = hashlib.sha256()
    columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
    if not columns:
        return digest.hexdigest()
    select_columns = ", ".join(f'"{column}"' for column in columns)
    for row in conn.execute(f'SELECT {select_columns} FROM "{table}" ORDER BY rowid'):
        digest.update(
            json.dumps(tuple(row), ensure_ascii=False, default=str, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _raw_fact_hashes(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        table: _table_digest(conn, table)
        for table in ("plays", "tracks", "track_artists")
        if _table_exists(conn, table)
    }


def apply_split_plan(
    conn: sqlite3.Connection,
    confirmation_token: str,
    *,
    bump_revision: bool = True,
) -> dict[str, Any]:
    """Apply one confirmed plan transactionally to the supplied connection.

    This function intentionally does not commit.  Production callers must first
    run ``simulate_split_plan`` and own the surrounding backup/rebuild workflow.
    """

    if not conn.in_transaction:
        raise L1IdentitySplitPlanError(
            "caller must begin a transaction before applying an L1 split plan"
        )
    plan = build_l1_external_identity_risk_plan(conn)
    if plan.get("status") != "ready" or confirmation_token != plan["confirmation_token"]:
        raise L1IdentitySplitPlanError("L1 split plan confirmation token is stale or invalid")
    before_health = _health_counts(validate_track_identity_invariants(conn))
    before_raw_facts = _raw_fact_hashes(conn)
    conn.execute("SAVEPOINT l1_identity_split_batch")
    try:
        ownership_operations = [
            operation
            for operation in plan["operations"]
            if operation["operation"] != "supersede_shadow_identity"
        ]
        for operation in ownership_operations:
            if operation["operation"] == "create_provider_l1_and_reassign":
                _ensure_provider_target_identity(conn, operation)
            elif operation["operation"] != "reassign_external_identity":
                raise L1IdentitySplitPlanError(
                    f"unsupported L1 operation: {operation['operation']}"
                )
            _reassign_external_identity(conn, operation)
        if ownership_operations:
            refresh_play_source_links(conn, bump_revision=False)
        for operation in plan["operations"]:
            if operation["operation"] == "supersede_shadow_identity":
                _supersede_shadow_identity(conn, operation)
        if plan["operations"] and bump_revision:
            bump_track_identity_revision(conn)
        after_health = _health_counts(validate_track_identity_invariants(conn))
        after_raw_facts = _raw_fact_hashes(conn)
        weakened = {
            key: (before_health.get(key, 0), value)
            for key, value in after_health.items()
            if value > before_health.get(key, 0)
        }
        if before_raw_facts != after_raw_facts or weakened:
            raise L1IdentitySplitPlanError(
                f"L1 split validation failed: raw_facts_preserved={before_raw_facts == after_raw_facts}, "
                f"weakened={weakened}"
            )
        conn.execute("RELEASE SAVEPOINT l1_identity_split_batch")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT l1_identity_split_batch")
        conn.execute("RELEASE SAVEPOINT l1_identity_split_batch")
        raise
    return {
        "status": "applied_uncommitted",
        "operation_count": len(plan["operations"]),
        "semantic_changed": bool(plan["operations"]),
        "revision_bumped": bool(plan["operations"] and bump_revision),
        "affected_source_l1_ids": sorted(
            {int(item["source_l1_id"]) for item in plan["operations"]}
        ),
        "affected_target_l1_ids": sorted(
            {int(item["target_l1_id"]) for item in plan["operations"]}
        ),
        "created_target_l1_ids": sorted(
            int(item["target_l1_id"])
            for item in plan["operations"]
            if item["operation"] == "create_provider_l1_and_reassign"
        ),
        "superseded_shadow_l1_ids": sorted(
            int(item["source_l1_id"])
            for item in plan["operations"]
            if item["operation"] == "supersede_shadow_identity"
        ),
        "raw_plays_preserved": True,
        "raw_fact_hashes": after_raw_facts,
        "identity_health": after_health,
    }


def simulate_split_plan(conn: sqlite3.Connection, confirmation_token: str) -> dict[str, Any]:
    """Execute the current auto-split operations on an in-memory copy only."""

    plan = build_l1_external_identity_risk_plan(conn)
    if plan.get("status") != "ready" or confirmation_token != plan["confirmation_token"]:
        raise ValueError("L1 split plan confirmation token is stale or invalid")
    clone = sqlite3.connect(":memory:")
    clone.row_factory = sqlite3.Row
    try:
        conn.backup(clone)
        before_health = _health_counts(validate_track_identity_invariants(clone))
        before_plays = clone.execute(
            "SELECT COUNT(*), COALESCE(SUM(ms_played), 0) FROM plays"
        ).fetchone()
        clone.execute("BEGIN")
        result = apply_split_plan(clone, confirmation_token)
        health = validate_track_identity_invariants(clone)
        after_plays = clone.execute(
            "SELECT COUNT(*), COALESCE(SUM(ms_played), 0) FROM plays"
        ).fetchone()
        after_health = _health_counts(health)
        weakened = {
            key: (before_health.get(key, 0), value)
            for key, value in after_health.items()
            if value > before_health.get(key, 0)
        }
        clone.rollback()
        return {
            "status": "pass"
            if not weakened and tuple(before_plays) == tuple(after_plays)
            else "fail",
            "simulated_operation_count": int(result["operation_count"]),
            "simulated_target_l1_ids": result["affected_target_l1_ids"],
            "raw_plays_preserved": tuple(before_plays) == tuple(after_plays),
            "preexisting_identity_health": before_health,
            "identity_health": after_health,
            "health_regressions": weakened,
        }
    finally:
        clone.close()

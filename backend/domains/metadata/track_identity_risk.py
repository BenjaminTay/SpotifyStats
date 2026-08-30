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

AUDIT_SCHEMA_VERSION = "l1_external_identity_risk_v1"
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
    source_canonical_artist_id = (
        int(artist_map[source_artist_id].canonical_artist_id)
        if source_artist_id is not None and source_artist_id in artist_map
        else source_artist_id
    )
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
                int(artist_map[int(row[2])].canonical_artist_id)
                if row[2] is not None and int(row[2]) in artist_map
                else int(row[2])
                for row in projections
                if row[2] is not None
            }
        )
        eligible_target_l1_ids: list[int] = []
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
            if target_row is None or target_row[0] is None:
                continue
            target_artist_id = int(target_row[0])
            target_canonical_artist_id = (
                int(artist_map[target_artist_id].canonical_artist_id)
                if target_artist_id in artist_map
                else target_artist_id
            )
            # Never repair one provider collision by assigning it to a local
            # identity whose canonical artist disagrees with the current owner.
            # Such rows are metadata corruption evidence and remain review-only.
            if target_canonical_artist_id != source_canonical_artist_id:
                continue
            if _normalized_title(target_row[1]) != _normalized_title(
                str(meta[0]) if meta is not None and meta[0] else projection[1]
            ):
                continue
            eligible_target_l1_ids.append(target_l1_id)
        eligible_target_l1_ids = sorted(set(eligible_target_l1_ids))
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
            if content_column:
                content_types = [
                    str(row[0]).strip().lower()
                    for row in conn.execute(
                        f"""SELECT DISTINCT {content_column} FROM plays
                              WHERE {spotify_column}=? AND {content_column} IS NOT NULL
                                AND TRIM({content_column})!=''
                              ORDER BY {content_column}""",
                        (token,),
                    ).fetchall()
                ]
        track_name = (
            str(meta[0])
            if meta is not None and meta[0]
            else (str(projections[0][1]) if projections else "")
        )
        album_name = str(album[0]) if album is not None and album[0] else ""
        tags = _version_tags(track_name, album_name, *content_types)
        if "video" in content_types and "video" not in tags:
            tags.append("video")
        result.append(
            {
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
                "eligible_target_l1_ids": eligible_target_l1_ids,
                "projection_artist_ids": [int(row[2]) for row in projections if row[2] is not None],
                "canonical_artist_ids": canonical_artists,
                "play_count": play_count,
                "content_types": content_types,
                "version_tags": sorted(tags),
            }
        )
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

    target_l1_ids = candidate["eligible_target_l1_ids"]
    if not candidate["projection_track_ids"]:
        blockers.append("missing_local_track_projection")
    elif len(target_l1_ids) != 1:
        blockers.append("missing_unique_existing_target_l1")
    if not reference["track_name"] or not candidate["track_name"]:
        blockers.append("missing_track_name")

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
                operations.append(
                    {
                        "operation": "reassign_external_identity",
                        "source_l1_id": l1_id,
                        "target_l1_id": int(item["eligible_target_l1_ids"][0]),
                        "provider": "spotify",
                        "external_track_id": item["spotify_track_id"],
                        "reason": "automatic L1 ownership correction: " + ",".join(evidence),
                        "preconditions": {
                            "reference_external_track_id": reference["spotify_track_id"],
                            "local_projection_track_ids": item["projection_track_ids"],
                        },
                    }
                )
        recommendations = Counter(item["recommendation"] for item in item_results)
        owner_recommendation = (
            "split"
            if recommendations["split"]
            else ("review" if recommendations["review"] else "keep")
        )
        if include_keep or owner_recommendation != "keep":
            owners.append(
                {
                    "l1_id": l1_id,
                    "recommendation": owner_recommendation,
                    "reference_external_track_id": reference["spotify_track_id"],
                    "external_ids": item_results,
                }
            )

    summary = {
        "multi_spotify_id_l1_count": len(l1_ids),
        "reported_l1_count": len(owners),
        "keep_l1_count": sum(item["recommendation"] == "keep" for item in owners),
        "split_l1_count": sum(item["recommendation"] == "split" for item in owners),
        "review_l1_count": sum(item["recommendation"] == "review" for item in owners),
        "auto_split_operation_count": len(operations),
        "multiple_isrc_l1_count": sum(
            len({item["isrc"] for item in owner["external_ids"] if item["isrc"]}) > 1
            for owner in owners
        ),
        "duration_conflict_l1_count": sum(
            any("duration_conflict" in item["evidence"] for item in owner["external_ids"])
            for owner in owners
        ),
        "version_conflict_l1_count": sum(
            any("semantic_version_conflict" in item["evidence"] for item in owner["external_ids"])
            for owner in owners
        ),
        "video_conflict_l1_count": sum(
            any("audio_video_conflict" in item["evidence"] for item in owner["external_ids"])
            for owner in owners
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
            for owner in owners
        ],
        "operations": operations,
    }
    result = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "track_identity_revision": token_payload["track_identity_revision"],
        "status": "ready",
        "summary": summary,
        "owners": owners,
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


def apply_split_plan(conn: sqlite3.Connection, confirmation_token: str) -> dict[str, Any]:
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
    before_plays = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(ms_played), 0) FROM plays"
    ).fetchone()
    conn.execute("SAVEPOINT l1_identity_split_batch")
    try:
        for operation in plan["operations"]:
            _reassign_external_identity(conn, operation)
        refresh_play_source_links(conn, bump_revision=False)
        if plan["operations"]:
            bump_track_identity_revision(conn)
        after_health = _health_counts(validate_track_identity_invariants(conn))
        after_plays = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(ms_played), 0) FROM plays"
        ).fetchone()
        weakened = {
            key: (before_health.get(key, 0), value)
            for key, value in after_health.items()
            if value > before_health.get(key, 0)
        }
        if tuple(before_plays) != tuple(after_plays) or weakened:
            raise L1IdentitySplitPlanError(
                f"L1 split validation failed: plays_preserved={tuple(before_plays) == tuple(after_plays)}, "
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
        "affected_source_l1_ids": sorted(
            {int(item["source_l1_id"]) for item in plan["operations"]}
        ),
        "affected_target_l1_ids": sorted(
            {int(item["target_l1_id"]) for item in plan["operations"]}
        ),
        "raw_plays_preserved": True,
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
        before_plays = clone.execute(
            "SELECT COUNT(*), COALESCE(SUM(ms_played), 0) FROM plays"
        ).fetchone()
        clone.execute("BEGIN")
        result = apply_split_plan(clone, confirmation_token)
        health = validate_track_identity_invariants(clone)
        after_plays = clone.execute(
            "SELECT COUNT(*), COALESCE(SUM(ms_played), 0) FROM plays"
        ).fetchone()
        clone.rollback()
        return {
            "status": "pass"
            if health.healthy and tuple(before_plays) == tuple(after_plays)
            else "fail",
            "simulated_operation_count": int(result["operation_count"]),
            "simulated_target_l1_ids": result["affected_target_l1_ids"],
            "raw_plays_preserved": tuple(before_plays) == tuple(after_plays),
            "identity_health": {
                key: value for key, value in vars(health).items() if isinstance(value, int)
            },
        }
    finally:
        clone.close()

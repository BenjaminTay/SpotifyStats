"""Spotify Track artist credits as provider evidence, separate from effective credits."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from typing import Any


class InvalidSpotifyCreditsError(ValueError):
    """A Track response cannot replace the last known good artist array."""


def evidence_schema_available(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='spotify_track_credit_sets'"
        ).fetchone()
        is not None
    )


def _ordered_credits(
    track: dict[str, Any], requested_id: str | None = None
) -> list[dict[str, str]]:
    track_id = track.get("id")
    if not isinstance(track_id, str) or not track_id.strip():
        raise InvalidSpotifyCreditsError("track_id_missing")
    if requested_id is not None and track_id != requested_id:
        raise InvalidSpotifyCreditsError("track_id_mismatch")
    artists = track.get("artists")
    if not isinstance(artists, list) or not artists:
        raise InvalidSpotifyCreditsError("artists_missing_or_empty")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in artists:
        if not isinstance(item, dict):
            raise InvalidSpotifyCreditsError("artist_not_object")
        artist_id, name = item.get("id"), item.get("name")
        if not isinstance(artist_id, str) or not artist_id.strip():
            raise InvalidSpotifyCreditsError("artist_id_missing")
        if not isinstance(name, str) or not name.strip():
            raise InvalidSpotifyCreditsError("artist_name_missing")
        if artist_id in seen:
            raise InvalidSpotifyCreditsError("artist_id_duplicate")
        seen.add(artist_id)
        result.append({"spotify_artist_id": artist_id, "credited_name": name})
    return result


def _json(credits: list[dict[str, str]]) -> str:
    return json.dumps(credits, ensure_ascii=False, separators=(",", ":"))


def save_track_credit_evidence(
    conn: sqlite3.Connection,
    track: dict[str, Any],
    *,
    requested_id: str | None = None,
    source_run_id: str | None = None,
) -> str:
    """Save a validated ordered array inside the caller's transaction.

    Returns observed, changed, or unchanged. The caller commits only after the
    associated Track metadata succeeds.
    """
    credits = _ordered_credits(track, requested_id)
    track_id = str(track["id"])
    rendered = _json(credits)
    signature = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    observed_at = datetime.now(timezone.utc).isoformat()
    old = conn.execute(
        "SELECT credit_signature FROM spotify_track_credit_sets WHERE spotify_track_id=?",
        (track_id,),
    ).fetchone()
    if old is not None and str(old[0]) == signature:
        conn.execute(
            """UPDATE spotify_track_credit_sets
               SET fetched_at=?, source_run_id=?, updated_at=CURRENT_TIMESTAMP
               WHERE spotify_track_id=?""",
            (observed_at, source_run_id, track_id),
        )
        return "unchanged"

    before = None
    if old is not None:
        previous = conn.execute(
            """SELECT spotify_artist_id, credited_name
               FROM spotify_track_artist_credits WHERE spotify_track_id=?
               ORDER BY credit_order""",
            (track_id,),
        ).fetchall()
        before = _json(
            [{"spotify_artist_id": str(row[0]), "credited_name": str(row[1])} for row in previous]
        )
    conn.execute(
        """INSERT INTO spotify_track_credit_sets(
               spotify_track_id, artist_count, credit_signature, fetched_at, source_run_id)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(spotify_track_id) DO UPDATE SET
               artist_count=excluded.artist_count,
               credit_signature=excluded.credit_signature,
               fetched_at=excluded.fetched_at,
               source_run_id=excluded.source_run_id,
               updated_at=CURRENT_TIMESTAMP""",
        (track_id, len(credits), signature, observed_at, source_run_id),
    )
    conn.execute("DELETE FROM spotify_track_artist_credits WHERE spotify_track_id=?", (track_id,))
    conn.executemany(
        """INSERT INTO spotify_track_artist_credits(
               spotify_track_id, spotify_artist_id, credited_name, credit_order, observed_at)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (track_id, item["spotify_artist_id"], item["credited_name"], index, observed_at)
            for index, item in enumerate(credits)
        ],
    )
    state = "observed" if old is None else "changed"
    conn.execute(
        """INSERT INTO spotify_track_credit_events(
               spotify_track_id, event_type, before_json, after_json, source_run_id, observed_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (track_id, state, before, rendered, source_run_id, observed_at),
    )
    return state


_CANDIDATES_SQL = """SELECT spotify_track_id_at_play AS spotify_track_id FROM plays
                     WHERE spotify_track_id_at_play IS NOT NULL AND spotify_track_id_at_play!=''
                     UNION
                     SELECT spotify_track_id FROM tracks
                     WHERE spotify_track_id IS NOT NULL AND spotify_track_id!=''"""


def select_missing_credit_evidence(conn: sqlite3.Connection, limit: int = 5000) -> list[str]:
    if not evidence_schema_available(conn):
        return []
    rows = conn.execute(
        f"""SELECT candidate.spotify_track_id FROM ({_CANDIDATES_SQL}) candidate
            LEFT JOIN spotify_track_credit_sets evidence
              ON evidence.spotify_track_id=candidate.spotify_track_id
            WHERE evidence.spotify_track_id IS NULL
            ORDER BY candidate.spotify_track_id LIMIT ?""",
        (limit,),
    ).fetchall()
    return [str(row[0]) for row in rows]


def credit_evidence_coverage(conn: sqlite3.Connection) -> dict[str, int | str]:
    if not evidence_schema_available(conn):
        return {"status": "unavailable", "eligible": 0, "stored": 0, "missing": 0}
    row = conn.execute(
        f"""SELECT COUNT(*) AS eligible,
                   SUM(CASE WHEN evidence.spotify_track_id IS NOT NULL THEN 1 ELSE 0 END) AS stored
            FROM ({_CANDIDATES_SQL}) candidate
            LEFT JOIN spotify_track_credit_sets evidence
              ON evidence.spotify_track_id=candidate.spotify_track_id"""
    ).fetchone()
    eligible, stored = int(row[0] or 0), int(row[1] or 0)
    return {
        "status": "ready" if stored == eligible else "missing",
        "eligible": eligible,
        "stored": stored,
        "missing": eligible - stored,
    }


def _name_key(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value).casefold() if char.isalnum()
    )


def audit_track_credit_evidence(conn: sqlite3.Connection, *, limit: int | None = None) -> dict:
    """Read-only owner and artist identity comparison, with one status per Spotify ID."""
    from backend.domains.metadata.artist_identity import get_artist_identity_map
    from backend.domains.metadata.track_credits import get_effective_track_credits

    if not evidence_schema_available(conn):
        return {"status": "unavailable", "eligible": 0, "counts": {}, "rows": []}
    query = f"SELECT spotify_track_id FROM ({_CANDIDATES_SQL}) ORDER BY spotify_track_id"
    params: tuple[int, ...] = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)
    ids = [str(row[0]) for row in conn.execute(query, params)]
    if not ids:
        return {"status": "ready", "eligible": 0, "counts": {}, "rows": []}

    owners = (
        {
            str(row[0]): int(row[1])
            for row in conn.execute("SELECT spotify_track_id, track_id FROM spotify_track_owners")
        }
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='spotify_track_owners'"
        ).fetchone()
        else {}
    )
    owner_ids = {owners[spotify_id] for spotify_id in ids if spotify_id in owners}
    effective: dict[int, list[dict]] = {}
    for row in get_effective_track_credits(conn, owner_ids) if owner_ids else []:
        effective.setdefault(int(row["track_id"]), []).append(row)
    owner_play_impact = {
        int(row[0]): (int(row[1]), int(row[2] or 0))
        for row in conn.execute(
            """SELECT track_id, COUNT(*), SUM(ms_played) FROM plays
               WHERE track_id IS NOT NULL GROUP BY track_id"""
        )
    }
    identity = get_artist_identity_map(conn)
    external: dict[str, set[int]] = {}
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='artist_identity_external_ids'"
    ).fetchone():
        for row in conn.execute(
            """SELECT external_id, artist_id FROM artist_identity_external_ids
               WHERE provider='spotify'"""
        ):
            external.setdefault(str(row[0]), set()).add(int(row[1]))
    local_names = {
        int(row[0]): str(row[1])
        for row in conn.execute("SELECT artist_id, artist_name FROM artists")
    }
    names_by_key: dict[str, set[int]] = {}
    for artist_id, name in local_names.items():
        names_by_key.setdefault(_name_key(name), set()).add(artist_id)

    output: list[dict] = []
    counts: Counter[str] = Counter()
    artist_counts: Counter[str] = Counter()
    for spotify_id in ids:
        owner_id = owners.get(spotify_id)
        evidence_rows = conn.execute(
            """SELECT spotify_artist_id, credited_name, credit_order
               FROM spotify_track_artist_credits WHERE spotify_track_id=?
               ORDER BY credit_order""",
            (spotify_id,),
        ).fetchall()
        provider = [
            {
                "spotify_artist_id": str(row[0]),
                "credited_name": str(row[1]),
                "credit_order": int(row[2]),
            }
            for row in evidence_rows
        ]
        local = effective.get(owner_id, []) if owner_id is not None else []
        resolved: set[int] = set()
        unresolved: list[str] = []
        conflicts: list[str] = []
        link_candidates: dict[str, list[int]] = {}
        for item in provider:
            artist_counts["provider_entries"] += 1
            spotify_artist_id = str(item["spotify_artist_id"])
            matches = external.get(spotify_artist_id, set())
            canonical = {
                identity[value].canonical_artist_id if value in identity else value
                for value in matches
            }
            if len(canonical) > 1:
                conflicts.append(spotify_artist_id)
                artist_counts["conflicting_entries"] += 1
            elif canonical:
                resolved.update(canonical)
                artist_counts["resolved_entries"] += 1
            else:
                unresolved.append(spotify_artist_id)
                artist_counts["unresolved_entries"] += 1
                candidates = names_by_key.get(_name_key(str(item["credited_name"])), set())
                if candidates:
                    link_candidates[spotify_artist_id] = sorted(candidates)
        local_set = {int(row["artist_id"]) for row in local}
        if owner_id is None:
            state = "owner_conflict"
        elif not provider:
            state = "provider_incomplete"
        elif conflicts:
            state = "artist_identity_conflict"
        elif unresolved:
            state = "unresolved_provider_artist"
        elif resolved == local_set:
            state = "exact_member_match"
        elif resolved - local_set and local_set - resolved:
            state = "bidirectional_difference"
        elif resolved - local_set:
            state = "provider_additions"
        else:
            state = "local_only_members"
        member_difference_known = (
            owner_id is not None and bool(provider) and not (unresolved or conflicts)
        )
        counts[state] += 1
        output.append(
            {
                "spotify_track_id": spotify_id,
                "owner_track_id": owner_id,
                "owner_raw_play_rows": owner_play_impact.get(owner_id, (0, 0))[0],
                "owner_raw_ms_played": owner_play_impact.get(owner_id, (0, 0))[1],
                "status": state,
                "provider_credits": provider,
                "effective_credits": [
                    {
                        "artist_id": int(row["artist_id"]),
                        "artist_name": str(row["artist_name"]),
                        "role": str(row["role"]),
                    }
                    for row in local
                ],
                "provider_only_artist_ids": (
                    sorted(resolved - local_set) if member_difference_known else None
                ),
                "local_only_artist_ids": (
                    sorted(local_set - resolved) if member_difference_known else None
                ),
                "unresolved_spotify_artist_ids": unresolved,
                "conflicting_spotify_artist_ids": conflicts,
                "link_candidates": link_candidates,
            }
        )
    affected = {
        row["owner_track_id"]
        for row in output
        if row["owner_track_id"] is not None and row["status"] != "exact_member_match"
    }
    schema_version = (
        conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        else None
    )
    revision_row = (
        conn.execute("SELECT current_revision FROM track_credit_state WHERE state_id=1").fetchone()
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_credit_state'"
        ).fetchone()
        else None
    )
    return {
        "status": "ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": schema_version,
        "track_credit_revision": int(revision_row[0]) if revision_row else None,
        "eligible": len(ids),
        "counts": dict(sorted(counts.items())),
        "artist_counts": dict(sorted(artist_counts.items())),
        "affected_owner_count": len(affected),
        "affected_raw_play_rows": sum(
            owner_play_impact.get(owner, (0, 0))[0] for owner in affected
        ),
        "affected_raw_ms_played": sum(
            owner_play_impact.get(owner, (0, 0))[1] for owner in affected
        ),
        "rows": output,
    }

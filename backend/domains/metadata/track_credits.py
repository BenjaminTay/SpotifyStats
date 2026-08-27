"""Auditable effective track-credit resolution.

Raw ``tracks`` / ``track_artists`` / ``plays`` rows are immutable facts.  This
module overlays active manual decisions, then resolves every credited artist
through the global artist-identity map and de-duplicates one canonical artist
per track.  Artist fan-out consumers should use this module instead of reading
``track_artists`` directly.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from typing import Any

import pandas as pd

from backend.domains.metadata.artist_identity import get_artist_identity_map

VALID_ACTIONS = frozenset({"add", "remove", "set_role"})
VALID_ROLES = frozenset({"primary", "featured"})


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def get_track_credit_revision(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "track_credit_state"):
        return 0
    row = conn.execute(
        "SELECT current_revision FROM track_credit_state WHERE state_id=1"
    ).fetchone()
    return int(row[0]) if row else 0


def get_track_credit_state(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "track_credit_state"):
        return {
            "current_revision": 0,
            "active_aggregate_revision": 0,
            "rebuild_status": "ready",
            "last_error": None,
        }
    row = conn.execute(
        """SELECT current_revision, active_aggregate_revision, rebuild_status,
                  last_error, updated_at
           FROM track_credit_state WHERE state_id=1"""
    ).fetchone()
    return dict(row) if row else {}


def _where_track_ids(track_ids: Iterable[int] | None, alias: str) -> tuple[str, list[int]]:
    values = sorted({int(value) for value in track_ids or []})
    if not values:
        return "", []
    placeholders = ",".join("?" for _ in values)
    return f" WHERE {alias}.track_id IN ({placeholders})", values


def _raw_credit_map(
    conn: sqlite3.Connection, track_ids: Iterable[int] | None = None
) -> dict[tuple[int, int], dict[str, Any]]:
    where, params = _where_track_ids(track_ids, "t")
    if not _table_exists(conn, "track_artists"):
        rows = conn.execute(
            f"""SELECT t.track_id, t.artist_id, 'primary' AS role
                FROM tracks t {where} ORDER BY t.track_id, t.artist_id""",
            params,
        ).fetchall()
        return {
            (int(row["track_id"]), int(row["artist_id"])): {
                "track_id": int(row["track_id"]),
                "artist_id": int(row["artist_id"]),
                "role": "primary",
                "source": "raw",
                "override_id": None,
            }
            for row in rows
        }
    track_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(tracks)").fetchall()}
    if "artist_id" not in track_columns:
        rows = conn.execute(
            f"""SELECT t.track_id, ta.artist_id,
                       COALESCE(NULLIF(ta.role, ''), 'primary') AS role
                FROM tracks t
                JOIN track_artists ta ON ta.track_id=t.track_id
                {where}
                ORDER BY t.track_id,
                         CASE COALESCE(ta.role, 'primary') WHEN 'primary' THEN 0 ELSE 1 END,
                         ta.artist_id""",
            params,
        ).fetchall()
        return {
            (int(row["track_id"]), int(row["artist_id"])): {
                "track_id": int(row["track_id"]),
                "artist_id": int(row["artist_id"]),
                "role": str(row["role"]),
                "source": "raw",
                "override_id": None,
            }
            for row in rows
        }
    rows = conn.execute(
        f"""SELECT t.track_id, COALESCE(ta.artist_id, t.artist_id) AS artist_id,
                   COALESCE(NULLIF(ta.role, ''), 'primary') AS role
            FROM tracks t
            LEFT JOIN track_artists ta ON ta.track_id=t.track_id
            {where}
            ORDER BY t.track_id,
                     CASE COALESCE(ta.role, 'primary') WHEN 'primary' THEN 0 ELSE 1 END,
                     COALESCE(ta.artist_id, t.artist_id)""",
        params,
    ).fetchall()
    return {
        (int(row["track_id"]), int(row["artist_id"])): {
            "track_id": int(row["track_id"]),
            "artist_id": int(row["artist_id"]),
            "role": str(row["role"]),
            "source": "raw",
            "override_id": None,
        }
        for row in rows
    }


def _active_overrides(
    conn: sqlite3.Connection, track_ids: Iterable[int] | None = None
) -> list[dict[str, Any]]:
    if not _table_exists(conn, "track_credit_overrides"):
        return []
    where, params = _where_track_ids(track_ids, "o")
    conjunction = " AND" if where else " WHERE"
    rows = conn.execute(
        f"""SELECT override_id, track_id, artist_id, action, role,
                   evidence_type, evidence_source, reason, actor, revision,
                   created_at
            FROM track_credit_overrides o
            {where}{conjunction} o.active=1
            ORDER BY o.track_id, o.artist_id, o.override_id""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _apply_override(
    credit_map: dict[tuple[int, int], dict[str, Any]], override: dict[str, Any]
) -> None:
    key = (int(override["track_id"]), int(override["artist_id"]))
    action = str(override["action"])
    if action == "remove":
        credit_map.pop(key, None)
        return
    role = str(override.get("role") or "featured")
    previous = credit_map.get(key)
    credit_map[key] = {
        "track_id": key[0],
        "artist_id": key[1],
        "role": role,
        "source": "manual" if previous is None else "raw+manual",
        "override_id": override.get("override_id"),
        "action": action,
        "reason": override.get("reason"),
        "evidence_type": override.get("evidence_type"),
        "evidence_source": override.get("evidence_source"),
        "created_at": override.get("created_at"),
    }


def _effective_raw_map(
    conn: sqlite3.Connection,
    track_ids: Iterable[int] | None = None,
    proposed: dict[str, Any] | None = None,
) -> dict[tuple[int, int], dict[str, Any]]:
    credit_map = _raw_credit_map(conn, track_ids)
    for override in _active_overrides(conn, track_ids):
        _apply_override(credit_map, override)
    if proposed:
        _apply_override(credit_map, proposed)
    return credit_map


def get_effective_track_credits(
    conn: sqlite3.Connection,
    track_ids: Iterable[int] | None = None,
    *,
    proposed: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return canonical effective credits, one row per track and identity."""
    raw_rows = _effective_raw_map(conn, track_ids, proposed)
    identity = get_artist_identity_map(conn)
    artists = {
        int(row[0]): str(row[1])
        for row in conn.execute("SELECT artist_id, artist_name FROM artists").fetchall()
    }
    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    for row in raw_rows.values():
        raw_artist_id = int(row["artist_id"])
        resolved = identity.get(raw_artist_id)
        canonical_id = resolved.canonical_artist_id if resolved else raw_artist_id
        display_name = resolved.display_name if resolved else artists.get(raw_artist_id, "")
        key = (int(row["track_id"]), canonical_id)
        current = grouped.get(key)
        role = str(row["role"])
        if current is None:
            grouped[key] = {
                **row,
                "raw_artist_ids": [raw_artist_id],
                "artist_id": canonical_id,
                "artist_name": display_name,
            }
            continue
        if raw_artist_id not in current["raw_artist_ids"]:
            current["raw_artist_ids"].append(raw_artist_id)
        if role == "primary":
            current["role"] = "primary"
        if row["source"] != current["source"]:
            current["source"] = "raw+manual"
    return sorted(
        grouped.values(),
        key=lambda row: (
            int(row["track_id"]),
            0 if row["role"] == "primary" else 1,
            int(row["artist_id"]),
        ),
    )


def get_effective_track_credit_frame(
    conn: sqlite3.Connection, track_ids: Iterable[int] | None = None
) -> pd.DataFrame:
    rows = get_effective_track_credits(conn, track_ids)
    return pd.DataFrame(
        [
            {
                "track_id": row["track_id"],
                "artist_id": row["artist_id"],
                "raw_artist_id": row["raw_artist_ids"][0],
                "artist_name": row["artist_name"],
                "role": row["role"],
                "credit_source": row["source"],
            }
            for row in rows
        ],
        columns=[
            "track_id",
            "artist_id",
            "raw_artist_id",
            "artist_name",
            "role",
            "credit_source",
        ],
    )


def canonical_artist_names_for_effective_tracks(
    conn: sqlite3.Connection, track_ids: Iterable[int] | None = None
) -> dict[int, list[str]]:
    grouped: dict[int, list[str]] = {}
    for row in get_effective_track_credits(conn, track_ids):
        grouped.setdefault(int(row["track_id"]), []).append(str(row["artist_name"]))
    return grouped


def _track_exists(conn: sqlite3.Connection, track_id: int) -> dict[str, Any]:
    row = conn.execute(
        """SELECT t.track_id, t.track_name, t.spotify_track_id, t.album_id,
                  al.album_name, t.artist_id AS raw_primary_artist_id,
                  a.artist_name AS raw_primary_artist_name
           FROM tracks t
           JOIN artists a ON a.artist_id=t.artist_id
           LEFT JOIN albums al ON al.album_id=t.album_id
           WHERE t.track_id=?""",
        (track_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown track_id: {track_id}")
    return dict(row)


def _artist_exists(conn: sqlite3.Connection, artist_id: int) -> dict[str, Any]:
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(artists)").fetchall()}
    optional = [
        column if column in columns else f"NULL AS {column}"
        for column in ("spotify_artist_id", "image_url", "image_path")
    ]
    row = conn.execute(
        f"""SELECT artist_id, artist_name, {", ".join(optional)}
            FROM artists WHERE artist_id=?""",
        (artist_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown artist_id: {artist_id}")
    return dict(row)


def list_track_credit_detail(conn: sqlite3.Connection, track_id: int) -> dict[str, Any]:
    track = _track_exists(conn, track_id)
    identity = get_artist_identity_map(conn)
    raw = []
    for row in _raw_credit_map(conn, [track_id]).values():
        artist = _artist_exists(conn, int(row["artist_id"]))
        resolved = identity.get(int(row["artist_id"]))
        raw.append(
            {
                **row,
                "artist_name": artist["artist_name"],
                "canonical_artist_id": resolved.canonical_artist_id
                if resolved
                else artist["artist_id"],
                "canonical_display_name": resolved.display_name
                if resolved
                else artist["artist_name"],
            }
        )
    overrides = _active_overrides(conn, [track_id])
    return {
        "track": track,
        "state": get_track_credit_state(conn),
        "raw_credits": raw,
        "manual_overrides": overrides,
        "effective_credits": get_effective_track_credits(conn, [track_id]),
    }


def search_track_credit_tracks(
    conn: sqlite3.Connection, query: str, limit: int = 20
) -> list[dict[str, Any]]:
    pattern = f"%{query.strip()}%"
    exact_track_id = int(query.strip()) if query.strip().isdigit() else -1
    rows = conn.execute(
        """SELECT t.track_id, t.track_name, t.spotify_track_id,
                  a.artist_name, al.album_name, COUNT(p.play_id) AS play_count,
                  MIN(p.ts_date) AS first_play_date, MAX(p.ts_date) AS last_play_date
           FROM tracks t
           JOIN artists a ON a.artist_id=t.artist_id
           LEFT JOIN albums al ON al.album_id=t.album_id
           LEFT JOIN plays p ON p.track_id=t.track_id
           WHERE t.track_name LIKE ? COLLATE NOCASE
              OR a.artist_name LIKE ? COLLATE NOCASE
              OR COALESCE(al.album_name, '') LIKE ? COLLATE NOCASE
              OR COALESCE(t.spotify_track_id, '')=?
              OR t.track_id=?
           GROUP BY t.track_id
           ORDER BY (t.track_id = ?) DESC, (COUNT(p.play_id) > 0) DESC,
                    COUNT(p.play_id) DESC, t.track_name, t.track_id
           LIMIT ?""",
        (
            pattern,
            pattern,
            pattern,
            query.strip(),
            exact_track_id,
            exact_track_id,
            limit,
        ),
    ).fetchall()
    names = canonical_artist_names_for_effective_tracks(
        conn, [int(row["track_id"]) for row in rows]
    )
    return [
        {**dict(row), "effective_artist_names": names.get(int(row["track_id"]), [])} for row in rows
    ]


def search_track_credit_artist_candidates(
    conn: sqlite3.Connection, query: str, limit: int = 20
) -> list[dict[str, Any]]:
    from backend.domains.metadata.artist_identity import search_artist_identity_candidates

    return search_artist_identity_candidates(conn, query, limit)


def preview_track_credit_override(
    conn: sqlite3.Connection,
    *,
    track_id: int,
    artist_id: int,
    action: str,
    role: str | None,
) -> dict[str, Any]:
    track = _track_exists(conn, track_id)
    artist = _artist_exists(conn, artist_id)
    if action not in VALID_ACTIONS:
        raise ValueError(f"unsupported credit action: {action}")
    if action != "remove" and role not in VALID_ROLES:
        raise ValueError("role must be primary or featured")
    before = get_effective_track_credits(conn, [track_id])
    proposed = {
        "track_id": track_id,
        "artist_id": artist_id,
        "action": action,
        "role": role,
        "source": "manual",
    }
    after = get_effective_track_credits(conn, [track_id], proposed=proposed)
    before_raw = _effective_raw_map(conn, [track_id])
    exists_before_raw = (track_id, artist_id) in before_raw
    if action == "add" and exists_before_raw:
        raise ValueError("artist is already an effective credit; use set_role when needed")
    if action in {"remove", "set_role"} and not exists_before_raw:
        raise ValueError("artist is not an effective credit on this track")
    before_ids = {int(row["artist_id"]) for row in before}
    after_ids = {int(row["artist_id"]) for row in after}
    identity = get_artist_identity_map(conn)
    proposed_canonical = identity.get(artist_id)
    canonical_id = proposed_canonical.canonical_artist_id if proposed_canonical else artist_id
    duplicate_identity = action == "add" and canonical_id in before_ids
    no_change = [(row["artist_id"], row["role"]) for row in before] == [
        (row["artist_id"], row["role"]) for row in after
    ]
    play = conn.execute(
        """SELECT COUNT(*) AS raw_play_count,
                  SUM(CASE WHEN ms_played >= 30000 THEN 1 ELSE 0 END) AS baseline_effective_plays,
                  COALESCE(SUM(ms_played), 0) AS total_ms,
                  COUNT(DISTINCT ts_date) AS active_days
           FROM plays WHERE track_id=?""",
        (track_id,),
    ).fetchone()
    album_count = conn.execute(
        """SELECT COUNT(DISTINCT album_id) FROM (
               SELECT album_id FROM tracks WHERE track_id=? AND album_id IS NOT NULL
               UNION SELECT album_id FROM track_albums WHERE track_id=?
           )""",
        (track_id, track_id),
    ).fetchone()[0]
    affected_artist_ids = sorted(before_ids | after_ids)
    return {
        "track": track,
        "artist": artist,
        "before": before,
        "after": after,
        "duplicate_canonical_identity": duplicate_identity,
        "no_change": no_change,
        "blocked": duplicate_identity or no_change,
        "impact": {
            **dict(play),
            "affected_track_count": 1,
            "affected_artist_count": len(affected_artist_ids),
            "affected_album_count": int(album_count),
            "affected_artist_ids": affected_artist_ids,
            "artist_fanout_delta": len(after_ids) - len(before_ids),
            "single_track_play_delta": 0,
        },
        "affected_scopes": [
            "播放统计",
            "Billboard 艺人榜与对决",
            "音乐搜索与详情",
            "播放记录与合作曲",
            "账号、Wrapped、社区与 AI 报告",
        ],
    }


def _active_override_snapshot(
    conn: sqlite3.Connection, track_id: int, artist_id: int
) -> dict[str, Any]:
    if not _table_exists(conn, "track_credit_overrides"):
        return {}
    row = conn.execute(
        """SELECT override_id, track_id, artist_id, action, role, evidence_type,
                  evidence_source, reason, actor, revision, created_at
           FROM track_credit_overrides
           WHERE track_id=? AND artist_id=? AND active=1""",
        (track_id, artist_id),
    ).fetchone()
    return dict(row) if row else {}


def _next_revision(conn: sqlite3.Connection, expected_revision: int) -> int:
    current = get_track_credit_revision(conn)
    if current != expected_revision:
        raise ValueError(
            f"track credit revision conflict: expected {expected_revision}, current {current}"
        )
    revision = current + 1
    conn.execute(
        """UPDATE track_credit_state
           SET current_revision=?, rebuild_status='pending', last_error=NULL,
               updated_at=datetime('now') WHERE state_id=1""",
        (revision,),
    )
    return revision


def _idempotent_result(conn: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT event_id, track_id, artist_id, revision
           FROM track_credit_events WHERE idempotency_key=?""",
        (key,),
    ).fetchone()
    return dict(row) if row else None


def apply_track_credit_override(
    conn: sqlite3.Connection,
    *,
    track_id: int,
    artist_id: int,
    action: str,
    role: str | None,
    evidence_type: str,
    evidence_source: str | None,
    reason: str,
    expected_revision: int,
    idempotency_key: str,
    actor: str = "local-user",
    confirm_duplicate_identity: bool = False,
) -> dict[str, Any]:
    existing_event = _idempotent_result(conn, idempotency_key)
    if existing_event:
        return existing_event
    preview = preview_track_credit_override(
        conn, track_id=track_id, artist_id=artist_id, action=action, role=role
    )
    if preview["duplicate_canonical_identity"] and not confirm_duplicate_identity:
        raise ValueError("track credit conflicts with an existing canonical artist identity")
    if preview["no_change"]:
        raise ValueError("track credit override would not change effective credits")
    before = _active_override_snapshot(conn, track_id, artist_id)
    revision = _next_revision(conn, expected_revision)
    previous_id = before.get("override_id")
    if previous_id:
        conn.execute(
            """UPDATE track_credit_overrides
               SET active=0, deactivated_at=datetime('now') WHERE override_id=?""",
            (previous_id,),
        )
    cursor = conn.execute(
        """INSERT INTO track_credit_overrides(
               track_id, artist_id, action, role, evidence_type, evidence_source,
               reason, actor, revision, supersedes_override_id
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            track_id,
            artist_id,
            action,
            role,
            evidence_type,
            evidence_source,
            reason,
            actor,
            revision,
            previous_id,
        ),
    )
    after = _active_override_snapshot(conn, track_id, artist_id)
    event = conn.execute(
        """INSERT INTO track_credit_events(
               track_id, artist_id, action, before_json, after_json, actor,
               reason, revision, idempotency_key
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            track_id,
            artist_id,
            "create" if not before else "update",
            json.dumps(before, ensure_ascii=False, sort_keys=True),
            json.dumps(after, ensure_ascii=False, sort_keys=True),
            actor,
            reason,
            revision,
            idempotency_key,
        ),
    )
    conn.commit()
    return {
        "event_id": int(event.lastrowid),
        "override_id": int(cursor.lastrowid),
        "track_id": track_id,
        "artist_id": artist_id,
        "revision": revision,
    }


def list_track_credit_events(
    conn: sqlite3.Connection, *, track_id: int | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    if not _table_exists(conn, "track_credit_events"):
        return []
    where = "WHERE e.track_id=?" if track_id is not None else ""
    params: tuple[Any, ...] = (track_id, limit) if track_id is not None else (limit,)
    rows = conn.execute(
        f"""SELECT e.*, t.track_name, a.artist_name
            FROM track_credit_events e
            JOIN tracks t ON t.track_id=e.track_id
            JOIN artists a ON a.artist_id=e.artist_id
            {where}
            ORDER BY e.event_id DESC LIMIT ?""",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def list_active_track_credit_overrides(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return the compact, currently-effective manual layer for Settings.

    The append-only event log remains internal; this projection only exposes the
    active rule and the event that can safely undo it.
    """
    if not _table_exists(conn, "track_credit_overrides"):
        return []
    rows = conn.execute(
        """SELECT o.override_id, o.track_id, t.track_name, t.spotify_track_id,
                  o.artist_id, a.artist_name, o.action, o.role, o.revision,
                  o.created_at,
                  (SELECT e.event_id
                     FROM track_credit_events e
                    WHERE e.track_id=o.track_id AND e.artist_id=o.artist_id
                      AND e.revision=o.revision
                    ORDER BY e.event_id DESC LIMIT 1) AS event_id
             FROM track_credit_overrides o
             JOIN tracks t ON t.track_id=o.track_id
             JOIN artists a ON a.artist_id=o.artist_id
            WHERE o.active=1
            ORDER BY o.revision DESC, o.override_id DESC"""
    ).fetchall()
    identity = get_artist_identity_map(conn)
    result = []
    for row in rows:
        item = dict(row)
        resolved = identity.get(int(item["artist_id"]))
        item["canonical_artist_id"] = (
            resolved.canonical_artist_id if resolved else int(item["artist_id"])
        )
        item["canonical_display_name"] = (
            resolved.display_name if resolved else str(item["artist_name"])
        )
        result.append(item)
    return result


def undo_track_credit_event(
    conn: sqlite3.Connection,
    *,
    event_id: int,
    expected_revision: int,
    idempotency_key: str,
    reason: str,
    actor: str = "local-user",
) -> dict[str, Any]:
    existing_event = _idempotent_result(conn, idempotency_key)
    if existing_event:
        return existing_event
    event = conn.execute(
        "SELECT * FROM track_credit_events WHERE event_id=?", (event_id,)
    ).fetchone()
    if event is None:
        raise ValueError(f"unknown track credit event: {event_id}")
    if event["action"] == "undo":
        raise ValueError("cannot undo an undo event")
    if conn.execute(
        "SELECT 1 FROM track_credit_events WHERE undo_of_event_id=?", (event_id,)
    ).fetchone():
        raise ValueError("track credit event has already been undone")
    track_id = int(event["track_id"])
    artist_id = int(event["artist_id"])
    current = _active_override_snapshot(conn, track_id, artist_id)
    revision = _next_revision(conn, expected_revision)
    if current:
        conn.execute(
            """UPDATE track_credit_overrides
               SET active=0, deactivated_at=datetime('now') WHERE override_id=?""",
            (current["override_id"],),
        )
    previous = json.loads(event["before_json"] or "{}")
    restored: dict[str, Any] = {}
    override_id = None
    if previous:
        cursor = conn.execute(
            """INSERT INTO track_credit_overrides(
                   track_id, artist_id, action, role, evidence_type, evidence_source,
                   reason, actor, revision, supersedes_override_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                track_id,
                artist_id,
                previous["action"],
                previous.get("role"),
                previous.get("evidence_type") or "undo_restore",
                previous.get("evidence_source"),
                reason,
                actor,
                revision,
                current.get("override_id"),
            ),
        )
        override_id = int(cursor.lastrowid)
        restored = _active_override_snapshot(conn, track_id, artist_id)
    undo_event = conn.execute(
        """INSERT INTO track_credit_events(
               track_id, artist_id, action, before_json, after_json, actor,
               reason, revision, idempotency_key, undo_of_event_id
           ) VALUES (?, ?, 'undo', ?, ?, ?, ?, ?, ?, ?)""",
        (
            track_id,
            artist_id,
            json.dumps(current, ensure_ascii=False, sort_keys=True),
            json.dumps(restored, ensure_ascii=False, sort_keys=True),
            actor,
            reason,
            revision,
            idempotency_key,
            event_id,
        ),
    )
    conn.commit()
    return {
        "event_id": int(undo_event.lastrowid),
        "override_id": override_id,
        "track_id": track_id,
        "artist_id": artist_id,
        "revision": revision,
    }

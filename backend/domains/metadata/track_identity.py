"""Spotify provider aliases owned by the existing application ``track_id``.

The public/statistical identity remains ``tracks.track_id``. A track may own
several Spotify ids, but a Spotify id has exactly one owner. Historical L1
tables remain only as a compatibility projection where ``l1_id == track_id``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

TRACK_IDENTITY_POLICY_VERSION = "spotify_owner_track_v1"
_SPOTIFY_TRACK_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{22}$")


class TrackIdentityConflictError(ValueError):
    """A provider id would be assigned to a second canonical owner."""


@dataclass(frozen=True)
class TrackIdentityHealth:
    duplicate_spotify_identity_count: int
    unresolved_play_identity_count: int
    source_link_orphan_count: int
    representative_missing_count: int
    external_owner_orphan_count: int = 0
    active_group_noncanonical_member_count: int = 0
    active_group_too_small_count: int = 0
    active_group_invalid_primary_count: int = 0
    pending_candidate_noncanonical_reference_count: int = 0

    @property
    def healthy(self) -> bool:
        return not any(
            (
                self.duplicate_spotify_identity_count,
                self.unresolved_play_identity_count,
                self.source_link_orphan_count,
                self.representative_missing_count,
                self.external_owner_orphan_count,
                self.active_group_noncanonical_member_count,
                self.active_group_too_small_count,
                self.active_group_invalid_primary_count,
                self.pending_candidate_noncanonical_reference_count,
            )
        )


def extract_spotify_track_id(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    if not rendered:
        return None
    if rendered.startswith("spotify:track:"):
        rendered = rendered.rsplit(":", 1)[-1].strip()
    return rendered or None


def is_valid_spotify_track_id(value: object) -> bool:
    token = extract_spotify_track_id(value)
    return bool(token and _SPOTIFY_TRACK_ID_PATTERN.fullmatch(token))


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _ensure_owner_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spotify_track_owners (
            spotify_track_id TEXT PRIMARY KEY,
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            evidence_type TEXT NOT NULL DEFAULT 'import_match'
                CHECK(evidence_type IN (
                    'import_match', 'play_majority',
                    'catalog_projection', 'manual_override'
                )),
            first_seen_at TEXT,
            last_seen_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_spotify_track_owners_track
               ON spotify_track_owners(track_id)"""
    )


def _ensure_compat_track_identity(conn: sqlite3.Connection, track_id: int) -> None:
    track_id = int(track_id)
    if conn.execute("SELECT 1 FROM tracks WHERE track_id=?", (track_id,)).fetchone() is None:
        raise ValueError(f"track {track_id} does not exist")
    conn.execute(
        """INSERT OR IGNORE INTO track_l1_identities(
               l1_id, provider, external_track_id, fallback_track_id,
               identity_status, representative_track_id
           ) VALUES (?, 'local', NULL, ?, 'active', ?)""",
        (track_id, track_id, track_id),
    )
    conn.execute(
        """UPDATE track_l1_identities
              SET provider='local', external_track_id=NULL,
                  fallback_track_id=?, identity_status='active',
                  representative_track_id=?, updated_at=datetime('now')
            WHERE l1_id=?""",
        (track_id, track_id, track_id),
    )


def spotify_track_owner(conn: sqlite3.Connection, spotify_track_id: object) -> int | None:
    token = extract_spotify_track_id(spotify_track_id)
    if token is None or not _table_exists(conn, "spotify_track_owners"):
        return None
    row = conn.execute(
        "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id=?",
        (token,),
    ).fetchone()
    return int(row[0]) if row is not None else None


def resolve_canonical_track_id(
    conn: sqlite3.Connection,
    reference_id: int,
) -> int | None:
    """Resolve a legacy track/L1 reference to its authoritative owner track.

    ``track_l1_identities`` intentionally retains one compatibility row for
    every historical ``tracks.track_id``.  Product governance must not expose
    those rows as separate songs when their Spotify id is owned by another
    track.  Existing owner tracks win first; Spotify evidence then resolves
    historical aliases.  A genuinely local-only track remains its own id.
    """
    value = int(reference_id)
    if _table_exists(conn, "track_id_aliases"):
        alias = conn.execute(
            "SELECT canonical_track_id FROM track_id_aliases WHERE alias_track_id=?",
            (value,),
        ).fetchone()
        if alias is not None:
            return int(alias[0])
    identity_exists = (
        _table_exists(conn, "track_l1_identities")
        and conn.execute(
            """SELECT 1 FROM track_l1_identities
                WHERE l1_id=? AND identity_status!='superseded'""",
            (value,),
        ).fetchone()
        is not None
    )
    track_exists = (
        conn.execute("SELECT 1 FROM tracks WHERE track_id=?", (value,)).fetchone() is not None
    )
    if not identity_exists and not track_exists:
        return None
    if not _table_exists(conn, "spotify_track_owners"):
        return value

    # A canonical track may legitimately own several Spotify ids.  Never
    # redirect an existing owner through one incidental compatibility row.
    if (
        conn.execute(
            "SELECT 1 FROM spotify_track_owners WHERE track_id=? LIMIT 1",
            (value,),
        ).fetchone()
        is not None
    ):
        return value

    owner_ids: set[int] = set()
    if _table_exists(conn, "track_l1_external_ids"):
        owner_ids.update(
            int(row[0])
            for row in conn.execute(
                """SELECT DISTINCT owners.track_id
                     FROM track_l1_external_ids external
                     JOIN spotify_track_owners owners
                       ON owners.spotify_track_id=external.external_track_id
                    WHERE external.provider='spotify' AND external.l1_id=?""",
                (value,),
            ).fetchall()
        )
    owner_ids.update(
        int(row[0])
        for row in conn.execute(
            """SELECT DISTINCT owners.track_id
                 FROM tracks source
                 JOIN spotify_track_owners owners
                   ON owners.spotify_track_id=source.spotify_track_id
                WHERE source.track_id=?""",
            (value,),
        ).fetchall()
    )
    if len(owner_ids) == 1:
        return next(iter(owner_ids))
    if len(owner_ids) > 1:
        raise TrackIdentityConflictError(
            f"track reference {value} resolves to multiple Spotify owners: "
            + ", ".join(str(owner) for owner in sorted(owner_ids))
        )
    return value


def ensure_spotify_track_owner(
    conn: sqlite3.Connection,
    *,
    spotify_track_id: object,
    track_id: int,
    evidence_type: str = "import_match",
) -> int:
    """Register a provider id once and always return its existing owner."""
    token = extract_spotify_track_id(spotify_track_id)
    if token is None:
        raise ValueError("spotify_track_id is required")
    if evidence_type not in {
        "import_match",
        "play_majority",
        "catalog_projection",
        "manual_override",
    }:
        raise ValueError(f"unsupported Spotify owner evidence: {evidence_type}")
    _ensure_owner_schema(conn)
    preferred = int(track_id)
    _ensure_compat_track_identity(conn, preferred)
    existing = spotify_track_owner(conn, token)
    owner = existing if existing is not None else preferred
    if existing is None:
        conn.execute(
            """INSERT INTO spotify_track_owners(
                   spotify_track_id, track_id, evidence_type
               ) VALUES (?, ?, ?)""",
            (token, owner, evidence_type),
        )
    _ensure_compat_track_identity(conn, owner)
    has_primary = conn.execute(
        """SELECT 1 FROM track_l1_external_ids
            WHERE l1_id=? AND provider='spotify' AND is_primary=1""",
        (owner,),
    ).fetchone()
    conn.execute(
        """INSERT INTO track_l1_external_ids(
               provider, external_track_id, l1_id, evidence_type, is_primary
           ) VALUES ('spotify', ?, ?, ?, ?)
           ON CONFLICT(provider, external_track_id) DO UPDATE SET
               l1_id=excluded.l1_id,
               evidence_type=excluded.evidence_type,
               updated_at=datetime('now')""",
        (
            token,
            owner,
            "manual_confirmed" if evidence_type == "manual_override" else "provider_observed",
            0 if has_primary else 1,
        ),
    )
    return owner


def _legacy_identity_columns(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "track_l1_identities"):
        return False
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(track_l1_identities)")}
    return {"provider", "external_track_id"}.issubset(columns)


def get_track_identity_revision(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "track_identity_state"):
        return 0
    row = conn.execute(
        "SELECT current_revision FROM track_identity_state WHERE state_id=1"
    ).fetchone()
    return int(row[0]) if row is not None else 0


def bump_track_identity_revision(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        """UPDATE track_identity_state
              SET current_revision=current_revision+1,
                  policy_version=?, updated_at=datetime('now')
            WHERE state_id=1""",
        (TRACK_IDENTITY_POLICY_VERSION,),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("track_identity_state singleton is missing")
    return get_track_identity_revision(conn)


def _assert_active_identity(conn: sqlite3.Connection, l1_id: int) -> None:
    if (
        conn.execute(
            """SELECT 1 FROM track_l1_identities
                WHERE l1_id=? AND identity_status IN ('active', 'unresolved')""",
            (int(l1_id),),
        ).fetchone()
        is None
    ):
        raise ValueError(f"canonical track identity {int(l1_id)} is not active")


def external_ids_for_l1(
    conn: sqlite3.Connection, l1_id: int, *, provider: str | None = None
) -> list[str]:
    if not _table_exists(conn, "track_l1_external_ids"):
        return []
    params: list[object] = [int(l1_id)]
    where = "WHERE l1_id=?"
    if provider is not None:
        where += " AND provider=?"
        params.append(provider)
    return [
        str(row[0])
        for row in conn.execute(
            f"""SELECT external_track_id FROM track_l1_external_ids
                  {where} ORDER BY is_primary DESC, external_track_id""",
            params,
        ).fetchall()
    ]


def ensure_l1_identities(
    conn: sqlite3.Connection,
    *,
    spotify_track_ids: Iterable[object] = (),
    fallback_track_ids: Iterable[int] = (),
    canonical_l1_id: int | None = None,
    evidence_type: str = "provider_observed",
    bump_revision: bool = True,
) -> dict[str, int]:
    """Compatibility wrapper returning existing ``track_id`` owners.

    It never creates a synthetic identity. When no preferred track is given,
    historical plays choose the owner deterministically (play majority,
    metadata completeness, then lowest stable track_id).
    """
    if evidence_type not in {
        "provider_observed",
        "provider_relink",
        "manual_confirmed",
        "migration",
    }:
        raise ValueError(f"unsupported external identity evidence: {evidence_type}")
    tokens = sorted(
        {
            token
            for value in spotify_track_ids
            if (token := extract_spotify_track_id(value)) is not None
        }
    )
    local_ids = sorted({int(value) for value in fallback_track_ids if int(value) > 0})
    if canonical_l1_id is not None:
        _ensure_compat_track_identity(conn, int(canonical_l1_id))

    before = conn.total_changes
    result: dict[str, int] = {}
    for token in tokens:
        owner_id = spotify_track_owner(conn, token)
        if owner_id is None:
            if canonical_l1_id is not None:
                owner_id = int(canonical_l1_id)
            else:
                owner = conn.execute(
                    """SELECT p.track_id
                         FROM plays p
                         JOIN tracks t ON t.track_id=p.track_id
                         LEFT JOIN artists a ON a.artist_id=t.artist_id
                        WHERE p.spotify_track_id_at_play=?
                        GROUP BY p.track_id
                        ORDER BY COUNT(*) DESC,
                                 CASE WHEN t.artist_id IS NULL
                                           OR COALESCE(TRIM(a.artist_name), '')=''
                                      THEN 1 ELSE 0 END,
                                 CASE WHEN t.album_id IS NULL THEN 1 ELSE 0 END,
                                 p.track_id
                        LIMIT 1""",
                    (token,),
                ).fetchone()
                if owner is None:
                    owner = conn.execute(
                        """SELECT track_id FROM tracks
                            WHERE spotify_track_id=? ORDER BY track_id LIMIT 1""",
                        (token,),
                    ).fetchone()
                if owner is None:
                    raise ValueError(f"Spotify track id {token} has no existing track_id owner")
                owner_id = int(owner[0])
            owner_id = ensure_spotify_track_owner(
                conn,
                spotify_track_id=token,
                track_id=owner_id,
                evidence_type="play_majority" if canonical_l1_id is None else "manual_override",
            )
        result[f"spotify:{token}"] = owner_id

    for track_id in local_ids:
        _ensure_compat_track_identity(conn, track_id)
        result[f"local:{track_id}"] = int(track_id)

    if conn.total_changes > before and bump_revision:
        bump_track_identity_revision(conn)
    return result


def upsert_track_source_link(
    conn: sqlite3.Connection,
    *,
    l1_id: int,
    track_id: int,
    evidence_type: str,
    observed_plays: int = 0,
    first_seen_at: str | None = None,
    last_seen_at: str | None = None,
) -> None:
    if evidence_type not in {"play_at_time", "track_projection", "manual"}:
        raise ValueError(f"unsupported track identity evidence: {evidence_type}")
    conn.execute(
        """INSERT INTO track_l1_source_links(
               l1_id, track_id, evidence_type, observed_plays,
               first_seen_at, last_seen_at
           ) VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(l1_id, track_id, evidence_type) DO UPDATE SET
               observed_plays=excluded.observed_plays,
               first_seen_at=COALESCE(excluded.first_seen_at, first_seen_at),
               last_seen_at=COALESCE(excluded.last_seen_at, last_seen_at)""",
        (
            int(l1_id),
            int(track_id),
            evidence_type,
            max(0, int(observed_plays)),
            first_seen_at,
            last_seen_at,
        ),
    )


def ensure_track_projection_identity(
    conn: sqlite3.Connection,
    *,
    track_id: int,
    spotify_track_id: object,
    bump_revision: bool = True,
) -> int:
    token = extract_spotify_track_id(spotify_track_id)
    before = conn.total_changes
    _ensure_compat_track_identity(conn, int(track_id))
    l1_id = (
        ensure_spotify_track_owner(
            conn,
            spotify_track_id=token,
            track_id=int(track_id),
            evidence_type="import_match",
        )
        if token
        else int(track_id)
    )
    conn.execute(
        """INSERT OR IGNORE INTO track_l1_source_links(
               l1_id, track_id, evidence_type, observed_plays
           ) VALUES (?, ?, 'track_projection', 0)""",
        (l1_id, int(track_id)),
    )
    if conn.total_changes > before and bump_revision:
        bump_track_identity_revision(conn)
    return l1_id


def resolve_source_track_l1_ids(conn: sqlite3.Connection, track_id: int) -> list[int]:
    if not _table_exists(conn, "track_l1_source_links"):
        return (
            [int(track_id)]
            if conn.execute("SELECT 1 FROM tracks WHERE track_id=?", (int(track_id),)).fetchone()
            else []
        )
    rows = conn.execute(
        """SELECT DISTINCT links.l1_id
             FROM track_l1_source_links links
             JOIN track_l1_identities identities ON identities.l1_id=links.l1_id
            WHERE links.track_id=? AND identities.identity_status!='superseded'
            ORDER BY links.l1_id""",
        (int(track_id),),
    ).fetchall()
    return [int(row[0]) for row in rows]


def _identity_semantic_signature(conn: sqlite3.Connection) -> tuple[tuple, ...]:
    """Capture ownership/projection semantics, excluding evidence counters and dates."""
    identities = tuple(
        tuple(row)
        for row in conn.execute(
            """SELECT l1_id, fallback_track_id, identity_status, representative_track_id
                 FROM track_l1_identities ORDER BY l1_id"""
        ).fetchall()
    )
    external = tuple(
        tuple(row)
        for row in conn.execute(
            """SELECT provider, external_track_id, l1_id, is_primary
                 FROM track_l1_external_ids ORDER BY provider, external_track_id"""
        ).fetchall()
    )
    sources = tuple(
        tuple(row)
        for row in conn.execute(
            """SELECT l1_id, track_id, evidence_type
                 FROM track_l1_source_links ORDER BY l1_id, track_id, evidence_type"""
        ).fetchall()
    )
    owners = (
        tuple(
            tuple(row)
            for row in conn.execute(
                """SELECT spotify_track_id, track_id, evidence_type
                     FROM spotify_track_owners ORDER BY spotify_track_id"""
            ).fetchall()
        )
        if _table_exists(conn, "spotify_track_owners")
        else ()
    )
    return identities, external, sources, owners


def synchronize_track_identity_projection(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "track_l1_external_ids"):
        return False
    before = _identity_semantic_signature(conn)
    for (track_id,) in conn.execute("SELECT track_id FROM tracks ORDER BY track_id").fetchall():
        _ensure_compat_track_identity(conn, int(track_id))
    refresh_play_source_links(conn, bump_revision=False)
    for track_id, spotify_track_id in conn.execute(
        "SELECT track_id, spotify_track_id FROM tracks ORDER BY track_id"
    ).fetchall():
        ensure_track_projection_identity(
            conn,
            track_id=int(track_id),
            spotify_track_id=spotify_track_id,
            bump_revision=False,
        )
    changed = _identity_semantic_signature(conn) != before
    if changed:
        bump_track_identity_revision(conn)
    return changed


def _refresh_representatives(conn: sqlite3.Connection) -> None:
    conn.execute(
        """UPDATE track_l1_identities
              SET representative_track_id=l1_id,
                  fallback_track_id=l1_id,
                  identity_status='active',
                  updated_at=datetime('now')
            WHERE representative_track_id IS NOT l1_id
               OR fallback_track_id IS NOT l1_id
               OR identity_status!='active'"""
    )


def refresh_play_source_links(conn: sqlite3.Connection, *, bump_revision: bool = True) -> int:
    _ensure_owner_schema(conn)
    before_semantics = _identity_semantic_signature(conn)
    spotify_ids = [
        row[0]
        for row in conn.execute(
            """SELECT spotify_track_id_at_play FROM plays
                WHERE spotify_track_id_at_play IS NOT NULL
                  AND spotify_track_id_at_play!=''
                GROUP BY spotify_track_id_at_play"""
        ).fetchall()
    ]
    ensure_l1_identities(conn, spotify_track_ids=spotify_ids, bump_revision=False)
    desired = [
        (int(row[0]), int(row[1]), int(row[2]), row[3], row[4])
        for row in conn.execute(
            """SELECT owners.track_id, p.track_id, COUNT(*), MIN(p.ts), MAX(p.ts)
                 FROM plays p
                 JOIN spotify_track_owners owners
                   ON owners.spotify_track_id=p.spotify_track_id_at_play
                WHERE p.track_id IS NOT NULL
                  AND p.spotify_track_id_at_play IS NOT NULL
                  AND p.spotify_track_id_at_play!=''
                GROUP BY owners.track_id, p.track_id
                ORDER BY owners.track_id, p.track_id"""
        ).fetchall()
    ]
    current = [
        (int(row[0]), int(row[1]), int(row[2]), row[3], row[4])
        for row in conn.execute(
            """SELECT l1_id, track_id, observed_plays, first_seen_at, last_seen_at
                 FROM track_l1_source_links
                WHERE evidence_type='play_at_time'
                ORDER BY l1_id, track_id"""
        ).fetchall()
    ]
    changed = desired != current
    if changed:
        conn.execute("DELETE FROM track_l1_source_links WHERE evidence_type='play_at_time'")
        conn.executemany(
            """INSERT INTO track_l1_source_links(
                   l1_id, track_id, evidence_type, observed_plays,
                   first_seen_at, last_seen_at
               ) VALUES (?, ?, 'play_at_time', ?, ?, ?)""",
            desired,
        )
    _refresh_representatives(conn)
    semantic_changed = _identity_semantic_signature(conn) != before_semantics
    if semantic_changed and bump_revision:
        bump_track_identity_revision(conn)
    return len(spotify_ids)


def play_identity_sql(play_alias: str = "p", track_alias: str = "t") -> str:
    for alias in (play_alias, track_alias):
        if not alias.replace("_", "").isalnum():
            raise ValueError("SQL aliases must be alphanumeric")
    return (
        f"COALESCE(NULLIF({play_alias}.spotify_track_id_at_play, ''), "
        f"NULLIF({track_alias}.spotify_track_id, ''))"
    )


def merge_l1_identities(
    conn: sqlite3.Connection,
    *,
    survivor_l1_id: int,
    absorbed_l1_ids: Iterable[int],
    reason: str = "manual identity merge",
) -> int:
    """Merge exact-equivalent canonical tracks without touching raw facts."""
    survivor = int(survivor_l1_id)
    absorbed = sorted({int(value) for value in absorbed_l1_ids if int(value) != survivor})
    _assert_active_identity(conn, survivor)
    if not absorbed:
        return survivor
    for l1_id in absorbed:
        _assert_active_identity(conn, l1_id)

    scoped_ids = [survivor, *absorbed]
    if _table_exists(conn, "track_group_l1_members"):
        placeholders = ",".join("?" for _ in scoped_ids)
        conflicts = conn.execute(
            f"""SELECT groups.scope, COUNT(DISTINCT groups.group_id)
                  FROM track_group_l1_members members
                  JOIN track_groups groups ON groups.group_id=members.group_id
                 WHERE members.l1_id IN ({placeholders})
                   AND groups.group_status='active'
                 GROUP BY groups.scope HAVING COUNT(DISTINCT groups.group_id)>1""",
            scoped_ids,
        ).fetchall()
        if conflicts:
            scopes = ", ".join(str(row[0]) for row in conflicts)
            raise TrackIdentityConflictError(
                f"identity merge requires resolving active version groups first: {scopes}"
            )

    before_payload = {str(l1_id): external_ids_for_l1(conn, l1_id) for l1_id in scoped_ids}
    for l1_id in absorbed:
        conn.execute(
            """UPDATE track_l1_external_ids
                  SET l1_id=?, is_primary=0, evidence_type='manual_confirmed',
                      updated_at=datetime('now')
                WHERE l1_id=?""",
            (survivor, l1_id),
        )
        for row in conn.execute(
            """SELECT track_id, evidence_type, observed_plays,
                      first_seen_at, last_seen_at
                 FROM track_l1_source_links WHERE l1_id=?""",
            (l1_id,),
        ).fetchall():
            existing = conn.execute(
                """SELECT observed_plays, first_seen_at, last_seen_at
                     FROM track_l1_source_links
                    WHERE l1_id=? AND track_id=? AND evidence_type=?""",
                (survivor, int(row[0]), str(row[1])),
            ).fetchone()
            first_seen = [value for value in (row[3], existing[1] if existing else None) if value]
            last_seen = [value for value in (row[4], existing[2] if existing else None) if value]
            upsert_track_source_link(
                conn,
                l1_id=survivor,
                track_id=int(row[0]),
                evidence_type=str(row[1]),
                observed_plays=int(row[2]) + (int(existing[0]) if existing else 0),
                first_seen_at=min(first_seen) if first_seen else None,
                last_seen_at=max(last_seen) if last_seen else None,
            )
        conn.execute("DELETE FROM track_l1_source_links WHERE l1_id=?", (l1_id,))
        if _table_exists(conn, "track_group_l1_members"):
            conn.execute(
                """INSERT OR IGNORE INTO track_group_l1_members(group_id, l1_id)
                   SELECT group_id, ? FROM track_group_l1_members WHERE l1_id=?""",
                (survivor, l1_id),
            )
            conn.execute("DELETE FROM track_group_l1_members WHERE l1_id=?", (l1_id,))
            conn.execute(
                "UPDATE track_groups SET primary_l1_id=? WHERE primary_l1_id=?",
                (survivor, l1_id),
            )
        conn.execute(
            """UPDATE track_l1_identities
                  SET identity_status='superseded', updated_at=datetime('now')
                WHERE l1_id=?""",
            (l1_id,),
        )

    primary = conn.execute(
        """SELECT external_track_id FROM track_l1_external_ids
            WHERE l1_id=? AND provider='spotify'
            ORDER BY is_primary DESC, external_track_id LIMIT 1""",
        (survivor,),
    ).fetchone()
    conn.execute(
        "UPDATE track_l1_external_ids SET is_primary=0 WHERE l1_id=? AND provider='spotify'",
        (survivor,),
    )
    if primary is not None:
        conn.execute(
            """UPDATE track_l1_external_ids SET is_primary=1
                WHERE provider='spotify' AND external_track_id=?""",
            (primary[0],),
        )
        if _legacy_identity_columns(conn):
            conn.execute(
                """UPDATE track_l1_identities
                      SET provider='spotify', external_track_id=?,
                          identity_status='active', updated_at=datetime('now')
                    WHERE l1_id=?""",
                (primary[0], survivor),
            )
    _refresh_representatives(conn)
    if _table_exists(conn, "track_identity_events"):
        conn.execute(
            """INSERT INTO track_identity_events(
                   action, survivor_l1_id, affected_l1_ids,
                   before_json, after_json, reason
               ) VALUES ('merge', ?, ?, ?, ?, ?)""",
            (
                survivor,
                json.dumps(absorbed),
                json.dumps(before_payload, ensure_ascii=False, sort_keys=True),
                json.dumps(
                    {str(survivor): external_ids_for_l1(conn, survivor)},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                reason,
            ),
        )
    bump_track_identity_revision(conn)
    return survivor


def split_external_identity(
    conn: sqlite3.Connection,
    *,
    source_l1_id: int,
    provider: str,
    external_track_id: str,
    reason: str = "manual identity split",
) -> int:
    """Detach one provider id into a new canonical track without rewriting raw facts."""
    source = int(source_l1_id)
    provider = str(provider).strip().lower()
    token = str(external_track_id).strip()
    if not provider or not token:
        raise ValueError("provider and external_track_id are required")
    _assert_active_identity(conn, source)
    owner = conn.execute(
        """SELECT l1_id FROM track_l1_external_ids
            WHERE provider=? AND external_track_id=?""",
        (provider, token),
    ).fetchone()
    if owner is None or int(owner[0]) != source:
        raise TrackIdentityConflictError(
            f"{provider} track id {token} does not belong to canonical track {source}"
        )
    external_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM track_l1_external_ids WHERE l1_id=?",
            (source,),
        ).fetchone()[0]
    )
    if external_count < 2:
        raise TrackIdentityConflictError(
            "a canonical track with only one external id cannot be split"
        )

    projection = conn.execute(
        """SELECT MIN(track_id) FROM tracks
            WHERE CASE WHEN ?='spotify' THEN spotify_track_id ELSE NULL END=?""",
        (provider, token),
    ).fetchone()
    representative_track_id = (
        int(projection[0]) if projection and projection[0] is not None else None
    )
    if _legacy_identity_columns(conn):
        cursor = conn.execute(
            """INSERT INTO track_l1_identities(
                   provider, external_track_id, identity_status, representative_track_id
               ) VALUES (?, ?, 'active', ?)""",
            (provider, token, representative_track_id),
        )
    else:
        cursor = conn.execute(
            """INSERT INTO track_l1_identities(identity_status, representative_track_id)
               VALUES ('active', ?)""",
            (representative_track_id,),
        )
    new_l1_id = int(cursor.lastrowid)
    conn.execute(
        """UPDATE track_l1_external_ids
              SET l1_id=?, is_primary=1, evidence_type='manual_confirmed',
                  updated_at=datetime('now')
            WHERE provider=? AND external_track_id=?""",
        (new_l1_id, provider, token),
    )
    conn.execute(
        """UPDATE track_l1_source_links
              SET l1_id=?
            WHERE l1_id=? AND evidence_type='track_projection'
              AND track_id IN (
                  SELECT track_id FROM tracks
                   WHERE CASE WHEN ?='spotify' THEN spotify_track_id ELSE NULL END=?
              )""",
        (new_l1_id, source, provider, token),
    )

    source_primary = conn.execute(
        """SELECT external_track_id FROM track_l1_external_ids
            WHERE l1_id=? AND provider=?
            ORDER BY is_primary DESC, external_track_id LIMIT 1""",
        (source, provider),
    ).fetchone()
    conn.execute(
        "UPDATE track_l1_external_ids SET is_primary=0 WHERE l1_id=? AND provider=?",
        (source, provider),
    )
    if source_primary is not None:
        conn.execute(
            """UPDATE track_l1_external_ids SET is_primary=1
                WHERE l1_id=? AND provider=? AND external_track_id=?""",
            (source, provider, source_primary[0]),
        )
        if _legacy_identity_columns(conn):
            conn.execute(
                """UPDATE track_l1_identities
                      SET provider=?, external_track_id=?, updated_at=datetime('now')
                    WHERE l1_id=?""",
                (provider, source_primary[0], source),
            )

    refresh_play_source_links(conn, bump_revision=False)
    _refresh_representatives(conn)
    if _table_exists(conn, "track_identity_events"):
        conn.execute(
            """INSERT INTO track_identity_events(
                   action, survivor_l1_id, affected_l1_ids,
                   before_json, after_json, reason
               ) VALUES ('split', ?, ?, ?, ?, ?)""",
            (
                source,
                json.dumps([new_l1_id]),
                json.dumps({str(source): [token]}, ensure_ascii=False),
                json.dumps(
                    {
                        str(source): external_ids_for_l1(conn, source),
                        str(new_l1_id): external_ids_for_l1(conn, new_l1_id),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                reason,
            ),
        )
    bump_track_identity_revision(conn)
    return new_l1_id


def validate_track_identity_invariants(conn: sqlite3.Connection) -> TrackIdentityHealth:
    _ensure_owner_schema(conn)
    duplicate = conn.execute(
        """SELECT COUNT(*) FROM (
               SELECT spotify_track_id
                 FROM spotify_track_owners
                GROUP BY spotify_track_id
               HAVING COUNT(DISTINCT track_id)>1
           )"""
    ).fetchone()[0]
    unresolved_plays = conn.execute(
        """SELECT COUNT(*)
             FROM plays p
             LEFT JOIN tracks t ON t.track_id=p.track_id
             LEFT JOIN spotify_track_owners owners
               ON owners.spotify_track_id=COALESCE(
                    NULLIF(p.spotify_track_id_at_play, ''),
                    NULLIF(t.spotify_track_id, '')
                  )
            WHERE COALESCE(NULLIF(p.spotify_track_id_at_play, ''),
                           NULLIF(t.spotify_track_id, '')) IS NOT NULL
              AND owners.track_id IS NULL"""
    ).fetchone()[0]
    orphan_links = conn.execute(
        """SELECT COUNT(*) FROM track_l1_source_links links
             LEFT JOIN track_l1_identities identities ON identities.l1_id=links.l1_id
             LEFT JOIN tracks t ON t.track_id=links.track_id
            WHERE identities.l1_id IS NULL OR t.track_id IS NULL"""
    ).fetchone()[0]
    missing_representative = conn.execute(
        """SELECT COUNT(*) FROM track_l1_identities identities
            WHERE identities.identity_status='active'
              AND identities.representative_track_id IS NULL"""
    ).fetchone()[0]
    external_orphans = conn.execute(
        """SELECT COUNT(*) FROM spotify_track_owners owners
             LEFT JOIN tracks t ON t.track_id=owners.track_id
             LEFT JOIN track_l1_identities identities
               ON identities.l1_id=owners.track_id
            WHERE t.track_id IS NULL
               OR identities.l1_id IS NULL
               OR identities.identity_status!='active'
               OR identities.representative_track_id!=owners.track_id"""
    ).fetchone()[0]
    governance_tables = all(
        _table_exists(conn, table)
        for table in ("track_groups", "track_group_l1_members", "track_group_candidates")
    )
    noncanonical_member_count = 0
    active_group_too_small_count = 0
    invalid_primary_count = 0
    noncanonical_candidate_count = 0
    if governance_tables:
        noncanonical_member_count = conn.execute(
            """SELECT COUNT(*)
                 FROM track_group_l1_members members
                 JOIN track_groups groups ON groups.group_id=members.group_id
                WHERE groups.group_status='active'
                  AND NOT EXISTS (
                      SELECT 1 FROM spotify_track_owners self_owner
                       WHERE self_owner.track_id=members.l1_id
                  )
                  AND (
                      EXISTS (
                          SELECT 1
                            FROM tracks source
                            JOIN spotify_track_owners raw_owner
                              ON raw_owner.spotify_track_id=source.spotify_track_id
                           WHERE source.track_id=members.l1_id
                             AND raw_owner.track_id!=members.l1_id
                      )
                      OR EXISTS (
                          SELECT 1 FROM track_l1_source_links alias_link
                           WHERE alias_link.track_id=members.l1_id
                             AND alias_link.l1_id!=members.l1_id
                      )
                  )"""
        ).fetchone()[0]
        active_group_too_small_count = conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT groups.group_id
                     FROM track_groups groups
                     LEFT JOIN track_group_l1_members members
                       ON members.group_id=groups.group_id
                    WHERE groups.group_status='active'
                    GROUP BY groups.group_id
                   HAVING COUNT(DISTINCT members.l1_id)<2
               )"""
        ).fetchone()[0]
        invalid_primary_count = conn.execute(
            """SELECT COUNT(*)
                 FROM track_groups groups
                WHERE groups.group_status='active'
                  AND (
                      groups.primary_l1_id IS NULL
                      OR NOT EXISTS (
                          SELECT 1 FROM track_group_l1_members members
                           WHERE members.group_id=groups.group_id
                             AND members.l1_id=groups.primary_l1_id
                      )
                  )"""
        ).fetchone()[0]
        noncanonical_candidate_count = conn.execute(
            """SELECT COUNT(*)
                 FROM track_group_candidates candidates
                WHERE candidates.status='pending'
                  AND (
                      (
                          NOT EXISTS (
                              SELECT 1 FROM spotify_track_owners left_self
                               WHERE left_self.track_id=candidates.original_l1_id
                          )
                          AND EXISTS (
                              SELECT 1
                                FROM tracks source
                                JOIN spotify_track_owners raw_owner
                                  ON raw_owner.spotify_track_id=source.spotify_track_id
                               WHERE source.track_id=candidates.original_l1_id
                                 AND raw_owner.track_id!=candidates.original_l1_id
                          )
                      )
                      OR (
                          NOT EXISTS (
                              SELECT 1 FROM spotify_track_owners right_self
                               WHERE right_self.track_id=candidates.candidate_l1_id
                          )
                          AND EXISTS (
                              SELECT 1
                                FROM tracks source
                                JOIN spotify_track_owners raw_owner
                                  ON raw_owner.spotify_track_id=source.spotify_track_id
                               WHERE source.track_id=candidates.candidate_l1_id
                                 AND raw_owner.track_id!=candidates.candidate_l1_id
                          )
                      )
                  )"""
        ).fetchone()[0]
    return TrackIdentityHealth(
        duplicate_spotify_identity_count=int(duplicate),
        unresolved_play_identity_count=int(unresolved_plays),
        source_link_orphan_count=int(orphan_links),
        representative_missing_count=int(missing_representative),
        external_owner_orphan_count=int(external_orphans),
        active_group_noncanonical_member_count=int(noncanonical_member_count),
        active_group_too_small_count=int(active_group_too_small_count),
        active_group_invalid_primary_count=int(invalid_primary_count),
        pending_candidate_noncanonical_reference_count=int(noncanonical_candidate_count),
    )


def l1_ids_for_track(conn: sqlite3.Connection, track_id: int) -> list[int]:
    return resolve_source_track_l1_ids(conn, track_id)

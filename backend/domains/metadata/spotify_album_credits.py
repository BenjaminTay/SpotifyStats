"""Ordered Album provider evidence; never a source of Track playback credits."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS spotify_album_credit_sets (
    spotify_album_id TEXT PRIMARY KEY REFERENCES spotify_album_meta(spotify_album_id),
    artist_count INTEGER NOT NULL CHECK(artist_count > 0),
    credit_signature TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    source TEXT NOT NULL,
    source_run_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS spotify_album_artist_credits (
    spotify_album_id TEXT NOT NULL REFERENCES spotify_album_credit_sets(spotify_album_id)
                     ON DELETE CASCADE,
    spotify_artist_id TEXT,
    credited_name TEXT NOT NULL,
    credit_order INTEGER NOT NULL CHECK(credit_order >= 0),
    PRIMARY KEY(spotify_album_id, credit_order),
    UNIQUE(spotify_album_id, spotify_artist_id)
);
CREATE TABLE IF NOT EXISTS spotify_album_credit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_album_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('observed', 'changed', 'rejected')),
    reason TEXT,
    before_json TEXT,
    after_json TEXT NOT NULL,
    source TEXT NOT NULL,
    source_run_id TEXT,
    observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spotify_album_credit_events_album
    ON spotify_album_credit_events(spotify_album_id, event_id);
"""


def create_schema(conn):
    # execute statements separately: executescript would commit the caller's transaction.
    for statement in SCHEMA.split(";"):
        if statement.strip():
            conn.execute(statement)


def _table_exists(conn, name):
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def evidence_schema_available(conn):
    return _table_exists(conn, "spotify_album_credit_sets")


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _ordered(album):
    artists = album.get("artists")
    if not isinstance(artists, list) or not artists:
        raise ValueError("artists_missing_or_empty")
    result, seen = [], set()
    for item in artists:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("name"), str)
            or not item["name"].strip()
        ):
            raise ValueError("artist_name_missing")
        sid = item.get("id")
        if sid is not None and (not isinstance(sid, str) or not sid.strip()):
            sid = None
        if sid and sid in seen:
            raise ValueError("artist_id_duplicate")
        if sid:
            seen.add(sid)
        result.append({"spotify_artist_id": sid, "credited_name": item["name"]})
    return result


def save_album_credit_evidence(
    conn, album, *, requested_id=None, source="spotify_album", source_run_id=None
):
    """Atomic, caller-owned transaction; incomplete/conflicting refresh retains LKG.

    Missing artist IDs can be stored as unresolved on first observation. An ID
    set change needs review (not a name-based replacement). Names/order may
    change for the same ID set. Duplicate rejected observations are idempotent.
    """
    sid = album.get("id")
    if not isinstance(sid, str) or not sid or (requested_id and sid != requested_id):
        return "rejected"
    if not evidence_schema_available(conn):
        return "legacy"
    old = conn.execute(
        "SELECT credit_signature FROM spotify_album_credit_sets WHERE spotify_album_id=?", (sid,)
    ).fetchone()
    before = [
        {"spotify_artist_id": r[0], "credited_name": r[1]}
        for r in conn.execute(
            "SELECT spotify_artist_id, credited_name FROM spotify_album_artist_credits "
            "WHERE spotify_album_id=? ORDER BY credit_order",
            (sid,),
        )
    ]
    reason = None
    try:
        credits = _ordered(album)
        known_before = {c["spotify_artist_id"] for c in before if c["spotify_artist_id"]}
        known_after = {c["spotify_artist_id"] for c in credits if c["spotify_artist_id"]}
        if old and known_before - known_after:
            reason = (
                "artist_id_set_conflict"
                if all(c["spotify_artist_id"] for c in credits)
                else "artist_id_missing"
            )
        elif old and all(c["spotify_artist_id"] for c in before) and known_before != known_after:
            reason = "artist_id_set_conflict"
    except ValueError as exc:
        credits = album.get("artists")
        reason = str(exc)
    if not conn.in_transaction:
        conn.execute("BEGIN")
    now = datetime.now(timezone.utc).isoformat()
    rendered = _json(credits)
    if reason:
        previous = conn.execute(
            "SELECT event_type, reason, after_json FROM spotify_album_credit_events "
            "WHERE spotify_album_id=? ORDER BY event_id DESC LIMIT 1",
            (sid,),
        ).fetchone()
        if previous is None or tuple(previous) != ("rejected", reason, rendered):
            conn.execute(
                "INSERT INTO spotify_album_credit_events(spotify_album_id,event_type,reason,"
                "before_json,after_json,source,source_run_id,observed_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    sid,
                    "rejected",
                    reason,
                    _json(before) if old else None,
                    rendered,
                    source,
                    source_run_id,
                    now,
                ),
            )
        return "rejected"
    signature = hashlib.sha256(rendered.encode()).hexdigest()
    if old and old[0] == signature:
        conn.execute(
            "UPDATE spotify_album_credit_sets SET fetched_at=?,source=?,source_run_id=?,"
            "updated_at=CURRENT_TIMESTAMP WHERE spotify_album_id=?",
            (now, source, source_run_id, sid),
        )
        return "unchanged"
    conn.execute("SAVEPOINT album_credit_evidence")
    try:
        conn.execute(
            "INSERT INTO spotify_album_credit_sets(spotify_album_id,artist_count,credit_signature,"
            "fetched_at,source,source_run_id) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(spotify_album_id) DO UPDATE SET artist_count=excluded.artist_count,"
            "credit_signature=excluded.credit_signature,fetched_at=excluded.fetched_at,"
            "source=excluded.source,source_run_id=excluded.source_run_id,updated_at=CURRENT_TIMESTAMP",
            (sid, len(credits), signature, now, source, source_run_id),
        )
        conn.execute("DELETE FROM spotify_album_artist_credits WHERE spotify_album_id=?", (sid,))
        conn.executemany(
            "INSERT INTO spotify_album_artist_credits VALUES (?,?,?,?)",
            [(sid, c["spotify_artist_id"], c["credited_name"], i) for i, c in enumerate(credits)],
        )
        state = "changed" if old else "observed"
        conn.execute(
            "INSERT INTO spotify_album_credit_events(spotify_album_id,event_type,before_json,"
            "after_json,source,source_run_id,observed_at) VALUES (?,?,?,?,?,?,?)",
            (sid, state, _json(before) if old else None, rendered, source, source_run_id, now),
        )
        conn.execute("RELEASE SAVEPOINT album_credit_evidence")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT album_credit_evidence")
        conn.execute("RELEASE SAVEPOINT album_credit_evidence")
        raise
    return state


def persist_album_artists(conn, album, *, source="spotify_album", source_run_id=None):
    """Shared write boundary for full and simplified Album objects.

    Writes the compatibility display only after accepting evidence. Old schemas
    keep their display-only behavior; no fabricated IDs or name backfill.
    """
    state = save_album_credit_evidence(conn, album, source=source, source_run_id=source_run_id)
    if state == "rejected":
        return state
    try:
        credits = _ordered(album)
    except ValueError:
        return "rejected"
    conn.execute(
        "UPDATE spotify_album_meta SET album_artists=? WHERE spotify_album_id=?",
        (", ".join(c["credited_name"] for c in credits), album["id"]),
    )
    return state


def _norm(name):
    return (
        "".join(
            c
            for c in unicodedata.normalize("NFKD", str(name or ""))
            if not unicodedata.combining(c)
        )
        .casefold()
        .strip()
    )


def legacy_name_matches(name, text):
    """Compatibility candidate only. Full comma-containing names win first."""
    if not text or not str(text).strip():
        return True
    target = _norm(name)
    if not target:
        return False
    if _norm(text) == target:
        return True
    try:
        values = json.loads(text)
    except (ValueError, TypeError):
        values = str(text).split(",")
    return isinstance(values, list) and any(_norm(value) == target for value in values)


class AlbumArtistResolver:
    """Build-local read-only projection; stable IDs then current manual canonical map."""

    def __init__(self, conn):
        from backend.domains.metadata.artist_identity import get_artist_identity_map

        self.identity = get_artist_identity_map(conn)
        self.by_name = {}
        self.by_external = {}
        for value in self.identity.values():
            self.by_name.setdefault(_norm(value.display_name), set()).add(value.canonical_artist_id)
        for row in conn.execute("SELECT artist_id,artist_name FROM artists"):
            self.by_name.setdefault(_norm(row[1]), set()).add(self.canonical(row[0]))
        columns = {r[1] for r in conn.execute("PRAGMA table_info(artists)")}
        if "spotify_artist_id" in columns:
            for row in conn.execute(
                "SELECT artist_id,spotify_artist_id FROM artists WHERE spotify_artist_id IS NOT NULL"
            ):
                self.by_external.setdefault(row[1], set()).add(self.canonical(row[0]))
        if _table_exists(conn, "artist_identity_external_ids"):
            for row in conn.execute(
                "SELECT artist_id,external_id FROM artist_identity_external_ids WHERE provider='spotify'"
            ):
                if int(row[0]) in self.identity:
                    self.by_external.setdefault(row[1], set()).add(self.canonical(row[0]))
        self.credits = {}
        if evidence_schema_available(conn):
            for row in conn.execute(
                "SELECT spotify_album_id,spotify_artist_id,credited_name,credit_order FROM spotify_album_artist_credits ORDER BY spotify_album_id,credit_order"
            ):
                options = self.by_external.get(row[1], set())
                status = (
                    "resolved" if len(options) == 1 else "ambiguous" if options else "unresolved"
                )
                self.credits.setdefault(row[0], []).append(
                    {
                        "spotify_artist_id": row[1],
                        "credited_name": row[2],
                        "credit_order": row[3],
                        "canonical_artist_id": next(iter(options)) if len(options) == 1 else None,
                        "resolution_status": status,
                    }
                )

    def canonical(self, artist_id):
        value = self.identity.get(int(artist_id))
        return value.canonical_artist_id if value else int(artist_id)

    def read(self, album_id):
        return self.credits.get(str(album_id).removeprefix("spotify:album:"), [])

    def match(self, album_id, artist_id=None, artist_name=None, legacy_text=None):
        credits = self.read(album_id)
        if not credits:
            return (
                "legacy_name_match"
                if legacy_name_matches(artist_name, legacy_text)
                else "legacy_mismatch"
            )
        if artist_id is None:
            targets = self.by_name.get(_norm(artist_name), set())
            if len(targets) != 1:
                return "unresolved_target"
            target = next(iter(targets))
        else:
            if int(artist_id) not in self.identity:
                return "unresolved_target"
            target = self.canonical(artist_id)
        if any(c["resolution_status"] != "resolved" for c in credits):
            return (
                "ambiguous"
                if any(c["resolution_status"] == "ambiguous" for c in credits)
                else "unresolved"
            )
        return (
            "verified_id"
            if target in {c["canonical_artist_id"] for c in credits}
            else "id_mismatch"
        )

    def compatible(self, album_id, artist_id, name, text):
        return self.match(album_id, artist_id, name, text) in {"verified_id", "legacy_name_match"}


def album_artist_match_sql(conn, album_alias="sam", artist_alias="ar"):
    """Indexed query consumers use one preloaded projection, no per-row DB reads."""
    resolver = AlbumArtistResolver(conn)
    conn.create_function("album_artist_evidence_matches", 4, resolver.compatible)
    return (
        f"album_artist_evidence_matches({album_alias}.spotify_album_id,"
        f"{artist_alias}.artist_id,{artist_alias}.artist_name,{album_alias}.album_artists)"
    )


def album_credit_revision(conn):
    if not _table_exists(conn, "analysis_source_revisions"):
        return ()
    return tuple(
        tuple(r)
        for r in conn.execute(
            "SELECT source_table,epoch,revision FROM analysis_source_revisions WHERE source_table IN "
            "('spotify_album_artist_credits','artist_identity_external_ids','artists','spotify_album_meta') ORDER BY source_table"
        )
    )

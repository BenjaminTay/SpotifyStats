"""Write-maintained Archive dependency vectors; no source scans on reads."""

from __future__ import annotations

import sqlite3
import uuid

from backend.core.access_surface import public_readonly_db_guard_active
from backend.services.analysis_snapshot_store import digest

# Only values consumed by the existing Archive adapters participate in updates.
# Row insertion/deletion always changes the corresponding source domain.
SOURCES = {
    "plays": (
        "plays",
        "play_id ts ms_played track_id source_album_id spotify_track_id_at_play content_type",
    ),
    "observation": ("plays", "ts ts_date"),
    "tracks": (
        "tracks",
        "track_id track_name artist_id album_id spotify_track_id spotify_track_uri duration_ms",
    ),
    "artists": ("artists", "artist_id artist_name"),
    "albums": ("albums", "album_id album_name artist_id release_date image_path image_url"),
    "duration": ("spotify_track_meta", "spotify_track_id duration_ms spotify_album_id"),
    "release": ("spotify_album_meta", "spotify_album_id release_date"),
    "identity": (
        "track_l1_identities",
        "l1_id fallback_track_id representative_track_id identity_status",
    ),
    "external_ids": ("track_l1_external_ids", "l1_id provider external_track_id"),
    "source_links": ("track_l1_source_links", "l1_id track_id"),
    "groups": (
        "track_groups",
        "group_id canonical_name primary_track_id primary_l1_id scope parent_group_id group_status",
    ),
    "group_members": ("track_group_members", "group_id track_id"),
    "group_l1_members": ("track_group_l1_members", "group_id l1_id"),
    "collection": (
        "saved_tracks",
        "track_uri track_name artist_name album_name added_date spotify_track_id added_date_source",
    ),
    "search": ("search_queries", "id query_text search_time_utc platform interaction_uri"),
    "podcasts": ("podcast_plays", "id end_time podcast_name episode_name ms_played play_date"),
    "shows": ("saved_shows", "show_name publisher image_url"),
    # Overview consumes counts, not the names or other account export fields.
    "album_count": ("saved_albums", ""),
    "artist_count": ("saved_artists", ""),
    "show_count": ("saved_shows", ""),
    "playlist_count": ("playlists", ""),
    "playlist_item_count": ("playlist_tracks", ""),
}
IDENTITY = ("identity", "external_ids", "source_links")
GROUPS = ("groups", "group_members", "group_l1_members")
SAVED = ("collection", "tracks", "albums", "duration", "release", *IDENTITY)
EVENTS = ("plays", "tracks", "duration", *IDENTITY, *GROUPS)
RELATIONSHIPS = tuple(dict.fromkeys((*SAVED, *EVENTS, "artists", "observation")))
FAMILIES = {
    "cohorts": RELATIONSHIPS,
    "returns": RELATIONSHIPS,
    "discovery": (*RELATIONSHIPS, "search"),
    "overview": (
        *SAVED,
        "observation",
        "album_count",
        "artist_count",
        "show_count",
        "playlist_count",
        "playlist_item_count",
    ),
    "journey": (*SAVED, "observation"),
    "other_media": (
        "plays",
        "observation",
        "tracks",
        "duration",
        "artists",
        "albums",
        *IDENTITY,
        "podcasts",
        "shows",
    ),
}


class ArchiveRevisionUnavailableError(ValueError):
    pass


TRACKING_VERSION = 1


def _expected_triggers(conn: sqlite3.Connection) -> dict[str, str]:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    columns = {
        table: {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        for table in {source[0] for source in SOURCES.values()} & tables
    }
    triggers = {}
    for domain, (table, requested) in SOURCES.items():
        if table not in columns:
            continue
        selected = [c for c in requested.split() if c in columns[table]]
        increment = f"UPDATE account_archive_source_revisions SET revision=revision+1 WHERE domain='{domain}';"
        for operation in ("INSERT", "DELETE", "UPDATE"):
            if operation == "UPDATE" and not selected:
                continue
            suffix = ""
            when = ""
            if operation == "UPDATE":
                suffix = " OF " + ",".join(f'"{c}"' for c in selected)
                when = " WHEN " + " OR ".join(f'NEW."{c}" IS NOT OLD."{c}"' for c in selected)
            name = f"archive_rev_{domain}_{operation.lower()}"
            triggers[name] = (
                f'CREATE TRIGGER {name} AFTER {operation}{suffix} ON "{table}"{when} BEGIN {increment} END'
            )
    return triggers


def _tracking_valid(conn: sqlite3.Connection, expected: dict[str, str]) -> bool:
    try:
        recorded = conn.execute(
            "SELECT schema_version,contract_fingerprint FROM account_archive_revision_schema WHERE singleton=1"
        ).fetchone()
        actual = dict(
            conn.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name GLOB 'archive_rev_*'"
            )
        )
        domains = {
            r[0] for r in conn.execute("SELECT domain FROM account_archive_source_revisions")
        }
        return (
            recorded is not None
            and tuple(recorded) == (TRACKING_VERSION, digest(expected))
            and actual == expected
            and set(SOURCES) <= domains
        )
    except sqlite3.OperationalError:
        return False


def install_revision_tracking(conn: sqlite3.Connection) -> None:
    """Private migration/backfill. Own trigger contract ignores unrelated DDL.

    The legacy schema_version column now stores TRACKING_VERSION. A fingerprint
    records the installed source/column inventory, including absent legacy tables.
    Repairs change epochs because a missing trigger may have missed writes.
    All DDL and counters preserve caller rollback.
    """
    if public_readonly_db_guard_active():
        raise PermissionError("Public Archive requests cannot install revisions")
    expected = _expected_triggers(conn)
    if _tracking_valid(conn, expected):
        return
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute("""CREATE TABLE IF NOT EXISTS account_archive_source_revisions (
        domain TEXT PRIMARY KEY, epoch TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=1))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS account_archive_revision_schema (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL,
        contract_fingerprint TEXT)""")
    if "contract_fingerprint" not in {
        r[1] for r in conn.execute("PRAGMA table_info(account_archive_revision_schema)")
    }:
        conn.execute(
            "ALTER TABLE account_archive_revision_schema ADD COLUMN contract_fingerprint TEXT"
        )
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name GLOB 'archive_rev_*'"
    ).fetchall():
        conn.execute('DROP TRIGGER "' + row[0].replace('"', '""') + '"')
    for domain in SOURCES:
        conn.execute(
            "INSERT OR IGNORE INTO account_archive_source_revisions VALUES(?,?,1)",
            (domain, uuid.uuid4().hex),
        )
    for sql in expected.values():
        conn.execute(sql)
    conn.execute(
        "UPDATE account_archive_source_revisions SET epoch=?,revision=1", (uuid.uuid4().hex,)
    )
    conn.execute(
        "INSERT OR REPLACE INTO account_archive_revision_schema(singleton,schema_version,contract_fingerprint) VALUES(1,?,?)",
        (TRACKING_VERSION, digest(expected)),
    )


def revision_vector(conn: sqlite3.Connection, domains) -> dict[str, str]:
    try:
        if not _tracking_valid(conn, _expected_triggers(conn)):
            raise ArchiveRevisionUnavailableError(
                "Archive revision tracking requires local backfill"
            )
        domains = sorted(set(domains))
        rows = conn.execute(
            f"SELECT domain,epoch,revision FROM account_archive_source_revisions WHERE domain IN ({','.join('?' for _ in domains)})",
            domains,
        ).fetchall()
        if len(rows) != len(domains) or any(not r[1] or r[2] < 1 for r in rows):
            raise ArchiveRevisionUnavailableError("Archive source revision missing")
        return {r[0]: f"{r[1]}:{r[2]}" for r in rows}
    except sqlite3.OperationalError as exc:
        raise ArchiveRevisionUnavailableError(
            "Archive revision tracking requires local backfill"
        ) from exc


def family_revision(conn: sqlite3.Connection, family: str) -> str:
    return digest(revision_vector(conn, FAMILIES[family]))


def revision_or_legacy(conn: sqlite3.Connection, domains) -> str:
    """Private builder compatibility for small pre-migration/in-memory inputs.

    HTTP reads use revision_vector directly and fail closed. Missing legacy
    counters are represented by actual source content, never a constant zero.
    """
    try:
        return digest(revision_vector(conn, domains))
    except ArchiveRevisionUnavailableError:
        if public_readonly_db_guard_active():
            raise
        tables = sorted({SOURCES[d][0] for d in domains})
        values: dict[str, object] = {}
        for table in tables:
            columns = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
            if not columns:
                values[table] = {"state": "absent"}
                continue
            quoted = ",".join(f'"{c}"' for c in columns)
            values[table] = [
                list(r) for r in conn.execute(f'SELECT {quoted} FROM "{table}" ORDER BY {quoted}')
            ]
        return digest({"legacy_content": values})

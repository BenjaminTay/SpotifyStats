"""Analysis semantic revisions maintained transactionally with source writes.

Private migration installs per-table epochs and triggers. Public readers only
validate that contract and read its durable vector; they never scan source rows.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path

from backend.services.analysis_snapshot_store import digest

COMMON = (
    "playback_import_state",
    "plays",
    "tracks",
    "albums",
    "artists",
    "track_artists",
    "spotify_track_meta",
    "spotify_track_owners",
    "track_id_aliases",
    "track_l1_identities",
    "track_l1_source_links",
    "track_l1_external_ids",
    "track_identity_state",
    "track_groups",
    "track_group_members",
    "track_group_l1_members",
    "track_merge_overrides",
    "artist_identity_state",
    "artist_identity_groups",
    "artist_identity_members",
    "artist_identity_aliases",
    "track_credit_state",
    "track_credit_overrides",
    "artist_metadata_attribution_overrides",
)
RECORDS = (
    "album_project_revision_state",
    "album_projects",
    "album_project_albums",
    "album_project_tracks",
    "l3_album_attribution_revision_state",
    "l3_song_album_attributions",
    "l3_song_album_attribution_exclusions",
    "l3_song_album_attribution_overrides",
    "album_spotify_links",
    "spotify_album_meta",
)
TASTE = (
    "artist_genre_sources",
    "artist_genre_overrides",
    "artist_language_sources",
    "spotify_artist_meta",
)
# Presentation assets, audit notes and operational timestamps are not facts.
IGNORED = {
    "created_at",
    "updated_at",
    "first_seen_at",
    "last_seen_at",
    "removed_at",
    "deactivated_at",
    "image_url",
    "cover_url",
    "display_name",
    "display_source",
    "canonical_name",
    "note",
    "reason",
    "actor",
    "evidence_json",
    "evidence_url",
    "evidence_summary",
    "last_error",
    "popularity",
    "followers",
}


def database_identity(conn) -> dict:
    path = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    stat = path.stat()
    # Explicitly file-local. An Online Backup has a new identity; it cannot
    # borrow another database's LKG even if its row count happens to match.
    return {"kind": "file_lineage_v1", "device": stat.st_dev, "inode": stat.st_ino}


def _table_digest(conn, table, *, batch=False):
    """Historical full-content oracle retained for equivalence tests only."""
    info = list(conn.execute(f'PRAGMA table_info("{table}")'))
    ignored = IGNORED | {
        "revision",
        "current_revision",
        "active_aggregate_revision",
        "track_identity_revision",
        "album_project_revision",
        "rebuild_status",
    }
    # These administrative counters also advance on display-only edits.
    # Identity/project revisions here hash the actual complete membership
    # projection instead. playback_revision is retained explicitly.
    columns = [r[1] for r in info if r[1] not in ignored]
    if not columns:
        raise ValueError(f"Missing analysis dependency: {table}")
    if table.endswith("_state") and conn.execute(f'SELECT 1 FROM "{table}"').fetchone() is None:
        raise ValueError(f"Missing analysis revision state: {table}")
    quoted = ",".join(f'"{c}"' for c in columns)
    order = ",".join(f'"{r[1]}"' for r in sorted(info, key=lambda r: r[5]) if r[5]) or quoted
    value = hashlib.sha256(json.dumps(columns).encode())
    where = (
        " WHERE status='approved'"
        if table in {"artist_genre_sources", "artist_language_sources"}
        else ""
    )
    cursor = conn.execute(f'SELECT {quoted} FROM "{table}"{where} ORDER BY {order}')
    if batch:
        # The reference batch path hashes every semantic value in the same order.
        # Tuple rows and bounded hash updates avoid 216k Row wrappers and 432k
        # update calls; byte stream, digest and commit fence stay identical.
        cursor.row_factory = None
        while rows := cursor.fetchmany(512):
            value.update(("\n".join(map(repr, rows)) + "\n").encode("utf-8"))
    else:
        for row in cursor:
            value.update(repr(tuple(row)).encode("utf-8"))
            value.update(b"\n")
    return value.hexdigest()


TRACKING_VERSION = 1


def _trigger_contract(conn):
    ignored = IGNORED | {
        "revision",
        "current_revision",
        "active_aggregate_revision",
        "track_identity_revision",
        "album_project_revision",
        "rebuild_status",
    }
    triggers = {}
    for table in dict.fromkeys(COMMON + RECORDS + TASTE):
        columns = [
            r[1] for r in conn.execute(f'PRAGMA table_info("{table}")') if r[1] not in ignored
        ]
        if not columns:
            raise ValueError(f"Missing analysis dependency: {table}")
        approved = table in {"artist_genre_sources", "artist_language_sources"}
        for operation in ("INSERT", "DELETE", "UPDATE"):
            suffix = ""
            conditions = []
            if operation == "UPDATE":
                suffix = " OF " + ",".join(f'"{c}"' for c in columns)
                conditions.append(
                    "(" + " OR ".join(f'NEW."{c}" IS NOT OLD."{c}"' for c in columns) + ")"
                )
            if approved:
                sides = (
                    ("NEW", "OLD")
                    if operation == "UPDATE"
                    else ("OLD",)
                    if operation == "DELETE"
                    else ("NEW",)
                )
                conditions.append(
                    "(" + " OR ".join(f"{side}.status='approved'" for side in sides) + ")"
                )
            when = " WHEN " + " AND ".join(conditions) if conditions else ""
            name = f"analysis_rev_{table}_{operation.lower()}"
            triggers[name] = (
                f'CREATE TRIGGER {name} AFTER {operation}{suffix} ON "{table}"{when} '
                f"BEGIN UPDATE analysis_source_revisions SET revision=revision+1 WHERE source_table='{table}'; END"
            )
    return triggers


def _tracking_valid(conn, expected):
    try:
        marker = conn.execute(
            "SELECT contract_version,contract_fingerprint FROM analysis_revision_schema WHERE singleton=1"
        ).fetchone()
        actual = dict(
            conn.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name GLOB 'analysis_rev_*'"
            )
        )
        tables = {r[0] for r in conn.execute("SELECT source_table FROM analysis_source_revisions")}
        return (
            marker is not None
            and tuple(marker) == (TRACKING_VERSION, digest(expected))
            and actual == expected
            and tables == set(COMMON + RECORDS + TASTE)
        )
    except sqlite3.Error:
        return False


def install_revision_tracking(conn):
    """Private, rollback-safe installation; repair changes the lineage epoch.

    Existing facts acquire a fresh epoch when tracking starts. Losing or changing
    a trigger invalidates the reader until private repair, even across restarts.
    """
    from backend.core.access_surface import public_readonly_db_guard_active

    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot install Analysis revisions")
    expected = _trigger_contract(conn)
    if _tracking_valid(conn, expected):
        return
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute("""CREATE TABLE IF NOT EXISTS analysis_source_revisions (
        source_table TEXT PRIMARY KEY, epoch TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision>=1))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS analysis_revision_schema (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), contract_version INTEGER NOT NULL,
        contract_fingerprint TEXT NOT NULL)""")
    for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name GLOB 'analysis_rev_*'"
    ).fetchall():
        conn.execute('DROP TRIGGER "' + row[0].replace('"', '""') + '"')
    conn.execute("DELETE FROM analysis_source_revisions")
    epoch = uuid.uuid4().hex
    conn.executemany(
        "INSERT INTO analysis_source_revisions VALUES(?,?,1)",
        [(t, epoch) for t in dict.fromkeys(COMMON + RECORDS + TASTE)],
    )
    for sql in expected.values():
        conn.execute(sql)
    conn.execute(
        "INSERT OR REPLACE INTO analysis_revision_schema VALUES(1,?,?)",
        (TRACKING_VERSION, digest(expected)),
    )


def _revision_vector(conn, tables):
    if not _tracking_valid(conn, _trigger_contract(conn)):
        raise ValueError("Analysis revision tracking requires private migration or repair")
    rows = conn.execute(
        f"SELECT source_table,epoch,revision FROM analysis_source_revisions WHERE source_table IN ({','.join('?' for _ in tables)})",
        tables,
    ).fetchall()
    if len(rows) != len(tables) or any(not r[1] or r[2] < 1 for r in rows):
        raise ValueError("Analysis source revision missing")
    for table in tables:
        if (
            table.endswith("_state")
            and conn.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() is None
        ):
            raise ValueError(f"Missing analysis revision state: {table}")
    return {r[0]: [r[1], r[2]] for r in rows}


def source_revision(conn, family: str, *, _attempt: int = 0) -> str:
    if family not in {"analysis_stats", "analysis_records"}:
        raise ValueError("Unknown analysis family")
    if conn.in_transaction:
        raise ValueError("Analysis revisions require committed source facts")
    from backend.domains.metadata.genre_display_taxonomy import GENRE_DISPLAY_TAXONOMY_VERSION
    from backend.domains.metadata.language_registry import LANGUAGE_REGISTRY_VERSION

    token = conn.execute("PRAGMA data_version").fetchone()[0]
    tables = COMMON + (TASTE if family == "analysis_stats" else RECORDS)
    dependencies = _revision_vector(conn, tables)
    if family == "analysis_stats":
        dependencies["taxonomy"] = GENRE_DISPLAY_TAXONOMY_VERSION
        dependencies["language"] = LANGUAGE_REGISTRY_VERSION
    identity = database_identity(conn)
    if conn.execute("PRAGMA data_version").fetchone()[0] != token:
        if _attempt < 2:
            return source_revision(conn, family, _attempt=_attempt + 1)
        raise ValueError("Analysis source changed during revision collection")
    return digest({"identity": identity, "dependencies": dependencies})

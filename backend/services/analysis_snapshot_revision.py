"""Analysis-only semantic dependency fingerprint, including legacy raw facts.

Legacy imports without a dataset digest are not revision zero. Their actual
facts are hashed. A readonly data_version observer only memoizes this digest
until the next commit; filesystem timestamps are never a semantic revision.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path

from backend.services.analysis_snapshot_store import digest

_lock = threading.RLock()
_observers: OrderedDict = OrderedDict()
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
        # Records cold reads still hash every semantic value in the same order.
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


def source_revision(conn, family: str, *, _attempt: int = 0) -> str:
    if family not in {"analysis_stats", "analysis_records"}:
        raise ValueError("Unknown analysis family")
    if conn.in_transaction:
        raise ValueError("Analysis revisions require committed source facts")
    from backend.domains.metadata.genre_display_taxonomy import GENRE_DISPLAY_TAXONOMY_VERSION
    from backend.domains.metadata.language_registry import LANGUAGE_REGISTRY_VERSION

    path = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    identity = database_identity(conn)
    observer_key = (str(path), identity["device"], identity["inode"])
    with _lock:
        if observer_key not in _observers:
            observer = sqlite3.connect(
                f"{path.as_uri()}?mode=ro", uri=True, check_same_thread=False
            )
            _observers[observer_key] = (observer, None, {})
            if len(_observers) > 4:
                _, (old, _, _) = _observers.popitem(last=False)
                old.close()
        observer, previous, cached = _observers[observer_key]
        token = observer.execute("PRAGMA data_version").fetchone()[0]
        if token != previous:
            cached = {}
        if family in cached:
            return cached[family]
        tables = COMMON + (TASTE if family == "analysis_stats" else RECORDS)
        dependencies = {
            table: _table_digest(conn, table, batch=True)
            if family == "analysis_records"
            else _table_digest(conn, table)
            for table in tables
        }
        if family == "analysis_stats":
            dependencies["taxonomy"] = GENRE_DISPLAY_TAXONOMY_VERSION
            dependencies["language"] = LANGUAGE_REGISTRY_VERSION
        if observer.execute("PRAGMA data_version").fetchone()[0] != token:
            # A worker may commit its running status while startup checks the
            # second family. Retry a bounded number of complete collections;
            # never memoize a digest assembled across source commits.
            if _attempt < 2:
                return source_revision(conn, family, _attempt=_attempt + 1)
            raise ValueError("Analysis source changed during revision collection")
        cached[family] = digest({"identity": identity, "dependencies": dependencies})
        _observers[observer_key] = (observer, token, cached)
        return cached[family]

"""Exact Community semantic revision; no TTL, mtime or cardinality revisions."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path

from backend.services.analysis_snapshot_revision import (
    COMMON,
    IGNORED,
    RECORDS,
    database_identity,
)
from backend.services.analysis_snapshot_store import digest

_lock = threading.RLock()
_observers = OrderedDict()


def source_revision(conn):
    if conn.in_transaction:
        raise ValueError("Community requires committed source facts")
    path = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    identity = database_identity(conn)
    namespace = (str(path), identity["device"], identity["inode"])
    with _lock:
        if namespace not in _observers:
            observer = sqlite3.connect(
                f"{path.as_uri()}?mode=ro", uri=True, check_same_thread=False
            )
            _observers[namespace] = (observer, None, None)
            if len(_observers) > 4:
                _, (old, _, _) = _observers.popitem(last=False)
                old.close()
        observer, previous, cached = _observers[namespace]
        token = observer.execute("PRAGMA data_version").fetchone()[0]
        if token == previous:
            return cached
        conn.execute("BEGIN")
        try:
            # Pin one SQLite read snapshot before the first dependency scan.
            # Cover downloads and background-job bookkeeping may keep committing
            # while this full semantic digest is collected; those writes must not
            # splice multiple database versions into one revision or turn a valid
            # read into a transient 503.
            conn.execute("SELECT rootpage FROM sqlite_schema LIMIT 1").fetchone()
            deps = {
                table: _semantic_table_digest(conn, table)
                for table in (*COMMON, *RECORDS, "saved_tracks", "agg_config")
                if table != "plays"
            }
            # Only fields consumed by raw eligibility, logical event identity, duration,
            # historical date assignment and collection membership enter this projection.
            available = {r[1] for r in conn.execute("PRAGMA table_info(plays)")}
            columns = [
                c
                for c in (
                    "play_id",
                    "ts",
                    "ts_date",
                    "ts_dow",
                    "ts_hour",
                    "ms_played",
                    "track_id",
                    "track_name",
                    "source_album_id",
                    "spotify_track_id_at_play",
                    "episode_name",
                    "audiobook_title",
                )
                if c in available
            ]
            deps["plays"] = _rows_digest(conn, "plays", columns, "play_id")
            revision = digest({"namespace": identity, "dependencies": deps})
        finally:
            conn.rollback()

        # The digest above is still an exact revision of one committed snapshot
        # when a concurrent commit occurred. It is safe to return, but it must not
        # be cached against a later data_version token; the next request will
        # recompute and observe the new committed state.
        if observer.execute("PRAGMA data_version").fetchone()[0] == token:
            _observers[namespace] = (observer, token, revision)
        return revision


def _rows_digest(conn, table, columns, order):
    # SQLite encodes exact scalar values in C; bounded batches avoid thousands
    # of Python tuple/value allocations on every independent process read.
    quoted = ",".join('"' + c + '"' for c in columns)
    cursor = conn.execute(f'SELECT json_array({quoted}) FROM "{table}" ORDER BY {order}')
    cursor.row_factory = None
    value = hashlib.sha256(repr(columns).encode())
    while rows := cursor.fetchmany(1024):
        value.update(("\n".join(r[0] for r in rows) + "\n").encode())
    return value.hexdigest()


def _semantic_table_digest(conn, table):
    info = list(conn.execute(f'PRAGMA table_info("{table}")'))
    ignored = IGNORED | {
        "revision",
        "current_revision",
        "active_aggregate_revision",
        "track_identity_revision",
        "album_project_revision",
        "rebuild_status",
    }
    columns = [r[1] for r in info if r[1] not in ignored]
    if not columns:
        raise ValueError(f"Missing Community dependency: {table}")
    order = ",".join(
        '"' + r[1] + '"' for r in sorted(info, key=lambda r: r[5]) if r[5]
    ) or ",".join('"' + c + '"' for c in columns)
    return _rows_digest(conn, table, columns, order)

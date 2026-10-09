"""Read closed maintenance copies without creating SQLite WAL/SHM files.

This process-local adapter is only for explicit offline CLI operations. Live
readers keep ordinary mode=ro so committed WAL contents are never ignored.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


def closed_file_state(path):
    path = Path(path).resolve()
    if Path(str(path) + "-wal").exists():
        raise RuntimeError("Closed publication source requires no WAL file")
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@contextmanager
def publication_reads(source, *, closed=False, sidecars=()):
    """Force source connections read-only; seal only explicitly closed files."""
    source = Path(source).resolve()
    allowed = {source, *(Path(path).resolve() for path in sidecars)}
    states = {source: closed_file_state(source)} if closed else {}
    original = sqlite3.connect

    def connect(database, *args, **kwargs):
        value = str(database)
        uri = urlsplit(value) if value.startswith("file:") else None
        path = Path(unquote(uri.path) if uri else value).resolve()
        readonly_uri = uri and parse_qs(uri.query).get("mode") == ["ro"]
        if path == source or (closed and path in allowed and readonly_uri):
            if closed:
                state = closed_file_state(path)
                if states.setdefault(path, state) != state:
                    raise RuntimeError("Closed publication source changed during operation")
            kwargs["uri"] = True
            conn = original(
                path.as_uri() + "?mode=ro" + ("&immutable=1" if closed else ""), *args, **kwargs
            )
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA query_only=ON")
            # Revision collectors reject active transactions and fence ordinary
            # committed reads themselves. Closed files are sealed by states.
            return conn
        return original(database, *args, **kwargs)

    sqlite3.connect = connect
    try:
        yield
        for path, state in states.items():
            if closed_file_state(path) != state:
                raise RuntimeError("Closed publication source changed during operation")
    finally:
        sqlite3.connect = original

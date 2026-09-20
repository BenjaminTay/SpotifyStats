"""Install test-owned database/cache paths before importing the application.

The audit guard is process-lifetime: fixture teardown must never restore a
formal data path, including after a test failure or KeyboardInterrupt.
"""

from __future__ import annotations

import atexit
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
FORMAL_DATA = ROOT / "data"
SESSION_ROOT: Path | None = None
VIOLATIONS: list[str] = []


class UnsafeTestPathError(RuntimeError):
    pass


def resolved_path(value):
    if isinstance(value, int) or value is None:
        return None
    value = os.fsdecode(value)
    if value in ("", ":memory:") or (value.startswith("file:") and "mode=memory" in value):
        return None
    if value.startswith("file:"):
        value = unquote(urlparse(value).path)
    return Path(value).resolve()


def require_test_path(value, formal_root=FORMAL_DATA):
    path = resolved_path(value)
    formal = Path(formal_root).resolve()
    if path is not None and (path == formal or formal in path.parents):
        raise UnsafeTestPathError(f"Backend test attempted formal data access: {path}")
    return path


def directory_relative_path(value, directory_fd):
    if (
        directory_fd in (None, -1)
        or isinstance(value, int)
        or Path(os.fsdecode(value)).is_absolute()
    ):
        return value
    if sys.platform == "darwin":
        import fcntl

        base = os.fsdecode(fcntl.fcntl(directory_fd, 50, bytes(1024)).split(b"\0", 1)[0])
    else:
        base = os.readlink(f"/proc/self/fd/{directory_fd}")
    return Path(base) / os.fsdecode(value)


def audit_guard(event, args, *, formal_root=FORMAL_DATA):
    paths = []
    if event == "sqlite3.connect":
        paths = [args[0]]  # Reject even read/write-default SQLite opens.
    elif event == "open":
        path, mode, flags = args
        if (mode and any(flag in mode for flag in "wax+")) or (
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        ):
            paths = [path]
    elif event in ("os.remove", "os.rmdir"):
        paths = [directory_relative_path(args[0], args[1])]
    elif event in ("os.mkdir", "os.chmod", "os.utime"):
        paths = [directory_relative_path(args[0], args[-1])]
    elif event == "os.truncate":
        paths = [args[0]]
    elif event in ("os.rename", "os.link"):
        paths = [directory_relative_path(args[i], args[i + 2]) for i in (0, 1)]
    elif event == "os.symlink":
        paths = [directory_relative_path(value, args[2]) for value in args[:2]]
    for path in paths:
        require_test_path(path, formal_root)


def attachment_guard(action, filename, _argument, _database, _trigger, *, formal_root=FORMAL_DATA):
    if action == sqlite3.SQLITE_ATTACH:
        if filename is None:
            return sqlite3.SQLITE_DENY
        require_test_path(filename, formal_root)
    return sqlite3.SQLITE_OK


def check_attach(sql, parameters, formal_root=FORMAL_DATA):
    if not re.match(r"\s*ATTACH\b", sql, re.I):
        return
    match = re.match(
        r"\s*ATTACH\s+(?:DATABASE\s+)?(\?|:[a-zA-Z_]\w*|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")\s+AS\b",
        sql,
        re.I,
    )
    if not match:
        raise UnsafeTestPathError("Test ATTACH target must be an explicit path")
    token = match[1]
    if token == "?":
        path = parameters[0]
    elif token.startswith(":"):
        path = parameters[token[1:]]
    else:
        path = token[1:-1].replace(token[0] * 2, token[0])
    require_test_path(path, formal_root)
    return True


class TestPathCursor(sqlite3.Cursor):
    def execute(self, sql, parameters=()):
        try:
            self.connection._checked_attach = check_attach(sql, parameters)
            return super().execute(sql, parameters)
        except UnsafeTestPathError as exc:
            VIOLATIONS.append(str(exc))
            raise
        finally:
            self.connection._checked_attach = False


class TestPathConnection(sqlite3.Connection):
    def execute(self, sql, parameters=()):
        try:
            self._checked_attach = check_attach(sql, parameters)
            return super().execute(sql, parameters)
        except UnsafeTestPathError as exc:
            VIOLATIONS.append(str(exc))
            raise
        finally:
            self._checked_attach = False

    def cursor(self, factory=TestPathCursor):
        return super().cursor(factory)


def install_test_paths():
    global SESSION_ROOT
    if SESSION_ROOT is not None:
        return SESSION_ROOT
    # A pytest-owned process directory is available during conftest import,
    # earlier than tmp_path_factory/session fixtures or test-module imports.
    owned = tempfile.TemporaryDirectory(prefix="pytest-spotifystats-")
    root = Path(owned.name).resolve()
    SESSION_ROOT = root
    atexit.register(owned.cleanup)  # Only this process's directory; no path restoration.

    def guard(event, args):
        try:
            audit_guard(event, args)
        except UnsafeTestPathError as exc:
            VIOLATIONS.append(str(exc))
            raise

    sys.addaudithook(guard)
    original_connect = sqlite3.connect

    def connect(*args, **kwargs):
        if len(args) < 6 and "factory" not in kwargs:
            kwargs["factory"] = TestPathConnection
        conn = original_connect(*args, **kwargs)

        def authorize(*arguments):
            try:
                # Guarded execute/cursor checks bound ATTACH on every call,
                # including SQLite statement-cache hits. Scripts use literals.
                if arguments[0] == sqlite3.SQLITE_ATTACH and arguments[1] is None:
                    return (
                        sqlite3.SQLITE_OK
                        if getattr(conn, "_checked_attach", False)
                        else sqlite3.SQLITE_DENY
                    )
                return attachment_guard(*arguments)
            except UnsafeTestPathError as exc:
                VIOLATIONS.append(str(exc))
                return sqlite3.SQLITE_DENY

        conn.set_authorizer(authorize)
        return conn

    sqlite3.connect = connect
    for key, path in {
        "SPOTIFY_STATS_BILLBOARD_CACHE_PATH": root / "billboard.db",
        "SPOTIFY_STATS_ANALYSIS_CACHE_PATH": root / "analysis.db",
        "SPOTIFY_STATS_YEARLY_CACHE_PATH": root / "yearly.db",
        "SPOTIFY_STATS_COMMUNITY_CACHE_PATH": root / "community.db",
        "SPOTIFY_STATS_ARCHIVE_CACHE_PATH": root / "archive.db",
        "SPOTIFY_STATS_GOVERNANCE_CACHE_PATH": root / "governance.db",
    }.items():
        # An unsafe caller export is an error, never silently used or ignored.
        if os.environ.get(key):
            require_test_path(os.environ[key])
        os.environ[key] = str(path)
    source = resolved_path(os.environ.get("SPOTIFY_STATS_TEST_SOURCE_DB"))
    if source is None:
        source = ROOT / "backend/tests/fixtures/seed.db"
    require_test_path(source)
    database = root / "spotify_stats-test.db"
    immutable = "&immutable=1" if source == ROOT / "backend/tests/fixtures/seed.db" else ""
    with sqlite3.connect(f"{source.as_uri()}?mode=ro{immutable}", uri=True) as src:
        with sqlite3.connect(database) as target:
            src.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("isolated backend test database failed integrity_check")
            target.execute("PRAGMA journal_mode=DELETE")
        target.close()
    src.close()

    from backend.core import db

    db.DB_PATH = str(database)
    # These modules derive file paths from DB_PATH at import time. This must
    # precede backend.main and test collection, not just fixture setup.
    from backend.domains.billboard import persistent_cache
    from backend.domains.yearly_review import artifact_cache
    from backend.services import home_service

    persistent_cache.BILLBOARD_CACHE_PATH = str(root / "billboard.db")
    artifact_cache.YEARLY_REVIEW_CACHE_PATH = str(root / "yearly.db")
    home_service.DB_PATH = str(database)
    home_service._HOME_SNAPSHOT_DIR = root / "home"
    return root

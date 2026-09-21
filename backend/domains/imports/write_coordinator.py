"""Cross-process publication lock for snapshot/restore import operations."""

from __future__ import annotations

import fcntl
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Callable

from backend.domains.imports.control_store import control_root


class ImportWriteBusyError(RuntimeError):
    error_code = "write_coordinator_busy"


class ImportWriteQuarantinedError(RuntimeError):
    error_code = "write_coordinator_quarantined"


_process_lock = threading.RLock()
_exclusive_depth: ContextVar[int] = ContextVar("import_publication_depth", default=0)


def publication_lock_path(db_path: str | None = None) -> Path:
    return control_root(db_path) / "publication.lock"


def publication_lock_held() -> bool:
    return _exclusive_depth.get() > 0


class CoordinatedConnection(sqlite3.Connection):
    """SQLite connection that releases its shared writer lease on close."""

    _writer_lease: int | None = None

    def attach_writer_lease(self, descriptor: int | None) -> None:
        self._writer_lease = descriptor

    def close(self) -> None:
        descriptor, self._writer_lease = self._writer_lease, None
        try:
            super().close()
        finally:
            if descriptor is not None:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)


def acquire_writer_lease(*, db_path: str | None = None) -> int | None:
    """Acquire the shared half of the publication gate for a normal writer.

    Connections opened inside an exclusive publication inherit the ContextVar
    and skip the shared lease, avoiding a self-deadlock while still fencing all
    ordinary ``get_db(readonly=False)`` and queue writers.
    """

    if publication_lock_held():
        return None
    path = publication_lock_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH)
        from backend.domains.imports.control_store import import_write_gate_state

        gate = import_write_gate_state(db_path=db_path)
        if gate.get("blocked"):
            raise ImportWriteQuarantinedError(
                f"database writes are quarantined by import run {gate.get('run_id') or 'unknown'}"
            )
    except Exception:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(descriptor)
        raise
    return descriptor


def coordinated_sqlite_connect(
    database: str | os.PathLike[str],
    *,
    active_db_path: str | os.PathLike[str] | None = None,
    **kwargs,
) -> sqlite3.Connection:
    """Open SQLite while coordinating writes to the configured active database.

    Maintenance scripts often accept explicit offline copies.  Those copies do
    not share the live publication gate; only the configured ``DB_PATH`` does.
    """

    from backend.core import db as db_module

    target = Path(database).resolve()
    active = Path(active_db_path or db_module.DB_PATH).resolve()
    if target != active:
        return sqlite3.connect(database, **kwargs)
    lease = acquire_writer_lease(db_path=str(target))
    try:
        conn = sqlite3.connect(database, factory=CoordinatedConnection, **kwargs)
        conn.attach_writer_lease(lease)
        return conn
    except Exception:
        if lease is not None:
            fcntl.flock(lease, fcntl.LOCK_UN)
            os.close(lease)
        raise


@contextmanager
def exclusive_publication(
    *,
    db_path: str | None = None,
    blocking: bool = False,
    on_error: Callable[[BaseException], None] | None = None,
) -> Iterator[None]:
    """Hold the process and filesystem publication gates for one critical window."""

    with _process_lock:
        depth = _exclusive_depth.get()
        if depth:
            token = _exclusive_depth.set(depth + 1)
            try:
                yield
            finally:
                _exclusive_depth.reset(token)
            return
        path = publication_lock_path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
        try:
            try:
                fcntl.flock(descriptor, flags)
            except BlockingIOError as exc:
                raise ImportWriteBusyError("another database publication is running") from exc
            token = _exclusive_depth.set(1)
            try:
                try:
                    yield
                except BaseException as exc:
                    if on_error is not None:
                        on_error(exc)
                    raise
            finally:
                _exclusive_depth.reset(token)
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

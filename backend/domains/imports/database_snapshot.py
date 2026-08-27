"""Consistent SQLite snapshots used as the import rollback boundary."""

from __future__ import annotations

import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core import db as db_module
from backend.core.db import enforce_sqlite_foreign_keys


class DatabaseSnapshotError(RuntimeError):
    """Raised when a database snapshot cannot be created or restored."""


_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_-]+")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_component(value: str | None) -> str:
    cleaned = _SAFE_COMPONENT.sub("-", value or "job")
    return cleaned.strip("-") or "job"


def _temporary_path(path: Path, purpose: str) -> Path:
    return path.with_name(f".{path.name}.{purpose}.{uuid.uuid4().hex}.tmp")


def _remove_sqlite_sidecars(path: Path) -> None:
    """Remove only sidecars belonging to the explicitly supplied database."""
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(f"{path}{suffix}")
        try:
            sidecar.unlink()
        except FileNotFoundError:
            pass


def _verify_integrity(conn: sqlite3.Connection, path: Path) -> None:
    row = conn.execute("PRAGMA integrity_check").fetchone()
    result = row[0] if row else None
    if result != "ok":
        raise DatabaseSnapshotError(f"SQLite integrity_check failed for {path}: {result!r}")


def create_database_snapshot(
    *,
    job_id: str | None = None,
    db_path: str | os.PathLike[str] | None = None,
    backup_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Create a consistent snapshot without changing the live database.

    A missing database is valid for a first import and returns ``skipped``.
    For an existing database, any backup failure raises before the import can
    start; proceeding without a rollback boundary would make a destructive
    import unsafe.
    """
    source_path = Path(db_path or db_module.DB_PATH)
    created_at = _utc_now()
    if not source_path.exists():
        return {
            "status": "skipped",
            "reason": "database_not_found",
            "source_db": str(source_path),
            "path": None,
            "created_at": created_at,
        }

    destination_dir = Path(backup_dir) if backup_dir else source_path.parent / "import_backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = destination_dir / (
        f"spotify_stats_{timestamp}_{_safe_component(job_id)}_{uuid.uuid4().hex[:8]}.db"
    )
    temporary = _temporary_path(destination, "snapshot")
    source_conn: sqlite3.Connection | None = None
    target_conn: sqlite3.Connection | None = None
    try:
        source_conn = sqlite3.connect(source_path, timeout=30)
        enforce_sqlite_foreign_keys(source_conn)
        source_conn.execute("PRAGMA query_only = ON")
        target_conn = sqlite3.connect(temporary, timeout=30)
        enforce_sqlite_foreign_keys(target_conn)
        source_conn.backup(target_conn)
        target_conn.commit()
        _verify_integrity(target_conn, source_path)
        target_conn.close()
        target_conn = None
        source_conn.close()
        source_conn = None
        os.replace(temporary, destination)
        return {
            "status": "created",
            "source_db": str(source_path),
            "path": str(destination),
            "created_at": created_at,
            "size_bytes": destination.stat().st_size,
        }
    except Exception as exc:
        raise DatabaseSnapshotError(f"无法创建数据库快照：{exc}") from exc
    finally:
        if target_conn is not None:
            target_conn.close()
        if source_conn is not None:
            source_conn.close()
        for candidate in (temporary, Path(f"{temporary}-wal"), Path(f"{temporary}-shm")):
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass


def restore_database_snapshot(
    snapshot_path: str | os.PathLike[str],
    *,
    db_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Atomically restore a previously created snapshot into ``db_path``."""
    source_path = Path(snapshot_path)
    target_path = Path(db_path or db_module.DB_PATH)
    if not source_path.is_file():
        raise DatabaseSnapshotError(f"数据库快照不存在：{source_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(target_path, "restore")
    source_conn: sqlite3.Connection | None = None
    target_conn: sqlite3.Connection | None = None
    try:
        source_conn = sqlite3.connect(source_path, timeout=30)
        enforce_sqlite_foreign_keys(source_conn)
        source_conn.execute("PRAGMA query_only = ON")
        target_conn = sqlite3.connect(temporary, timeout=30)
        enforce_sqlite_foreign_keys(target_conn)
        source_conn.backup(target_conn)
        target_conn.commit()
        _verify_integrity(target_conn, source_path)
        target_conn.close()
        target_conn = None
        source_conn.close()
        source_conn = None

        # The restored copy has no WAL state. Remove only sidecars of the
        # explicitly targeted live database before the atomic replacement.
        _remove_sqlite_sidecars(target_path)
        os.replace(temporary, target_path)
        return {
            "status": "restored",
            "path": str(source_path),
            "target_db": str(target_path),
            "restored_at": _utc_now(),
            "size_bytes": target_path.stat().st_size,
        }
    except Exception as exc:
        raise DatabaseSnapshotError(f"无法恢复数据库快照：{exc}") from exc
    finally:
        if target_conn is not None:
            target_conn.close()
        if source_conn is not None:
            source_conn.close()
        for candidate in (temporary, Path(f"{temporary}-wal"), Path(f"{temporary}-shm")):
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass


def discard_database_created_by_failed_import(
    db_path: str | os.PathLike[str],
) -> dict[str, Any]:
    """Remove the database created by a failed first import.

    This is only used when the pre-import snapshot reported that no database
    existed. The caller supplies the exact database path; no directory-wide
    cleanup is performed.
    """
    target_path = Path(db_path)
    if target_path.exists() and not target_path.is_file():
        raise DatabaseSnapshotError(f"导入目标不是数据库文件：{target_path}")

    existed = target_path.exists()
    _remove_sqlite_sidecars(target_path)
    if existed:
        target_path.unlink()
    return {
        "status": "removed_new_database" if existed else "not_needed",
        "target_db": str(target_path),
        "removed_at": _utc_now(),
    }

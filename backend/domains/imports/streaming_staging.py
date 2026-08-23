"""Ephemeral SQLite staging for Spotify streaming-history imports.

The staging database lives under the operating-system temporary directory and
is deliberately disposable.  It lets preflight planning and ETL share one JSON
parse while the source manifest remains the authority: every reuse verifies
the exact file set and SHA-256 digests before any playback write starts.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

StreamingSourceType = Literal["audio", "video"]
_PATTERNS: tuple[tuple[str, StreamingSourceType], ...] = (
    ("Streaming_History_Audio_*.json", "audio"),
    ("Streaming_History_Video_*.json", "video"),
)
_CACHE_TTL_SECONDS = 15 * 60
_CACHE_MAX_ENTRIES = 3
_READ_CHUNK_SIZE = 1024 * 1024
_INSERT_BATCH_SIZE = 1000
_STAGING_DIR_PREFIX = "spotifystats-streaming-import-"
_ORPHAN_MIN_AGE_SECONDS = 24 * 60 * 60


class StreamingJSONError(ValueError):
    """Raised when a streaming-history file is not one valid JSON array."""


def cleanup_orphaned_stagings(
    *,
    temp_root: Path | None = None,
    now: float | None = None,
    min_age_seconds: float = _ORPHAN_MIN_AGE_SECONDS,
) -> tuple[Path, ...]:
    """Remove only old private staging directories owned by this user.

    A crashed process cannot run ``close()`` or the ``atexit`` hook.  Cleanup is
    deliberately conservative: candidates must be direct children of the
    system temp root, use our controlled prefix, be real directories (not
    symlinks), be owned by the current uid, retain the expected ``0700`` mode,
    and be older than the configured threshold.  Anything ambiguous is left
    untouched for an operator rather than broadening the deletion boundary.
    """

    root = (temp_root or Path(tempfile.gettempdir())).resolve()
    current_time = time.time() if now is None else now
    try:
        current_uid = os.getuid()
    except AttributeError:  # pragma: no cover - Windows compatibility
        return ()

    removed: list[Path] = []
    try:
        candidates = tuple(root.iterdir())
    except OSError:
        return ()
    for candidate in candidates:
        if not candidate.name.startswith(_STAGING_DIR_PREFIX):
            continue
        try:
            candidate_stat = candidate.lstat()
        except OSError:
            continue
        if not stat.S_ISDIR(candidate_stat.st_mode) or candidate.is_symlink():
            continue
        if candidate_stat.st_uid != current_uid:
            continue
        if stat.S_IMODE(candidate_stat.st_mode) != 0o700:
            continue
        if current_time - candidate_stat.st_mtime < min_age_seconds:
            continue
        try:
            shutil.rmtree(candidate)
        except OSError:
            continue
        removed.append(candidate)
    return tuple(removed)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_READ_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_json_array(path: Path) -> Iterator[Any]:
    """Decode one top-level JSON array while retaining at most one item buffer.

    Spotify exports can grow well beyond available RAM.  The standard library
    has no incremental array iterator, so this small state machine feeds
    ``JSONDecoder.raw_decode`` bounded text chunks and compacts consumed text
    after every item.  A single unusually large record may still determine the
    peak buffer, but the complete file and all decoded dictionaries are never
    retained together.
    """
    decoder = json.JSONDecoder()
    buffer = ""
    position = 0
    eof = False

    with path.open("r", encoding="utf-8") as handle:

        def compact() -> None:
            nonlocal buffer, position
            if position:
                buffer = buffer[position:]
                position = 0

        def fill() -> bool:
            nonlocal buffer, eof
            if eof:
                return False
            compact()
            chunk = handle.read(_READ_CHUNK_SIZE)
            if not chunk:
                eof = True
                return False
            buffer += chunk
            return True

        def skip_whitespace() -> None:
            nonlocal position
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position < len(buffer) or not fill():
                    return

        skip_whitespace()
        if position >= len(buffer) or buffer[position] != "[":
            raise StreamingJSONError("Streaming History 顶层结构必须是数组")
        position += 1
        expect_value = True
        while True:
            skip_whitespace()
            if position >= len(buffer):
                raise StreamingJSONError("JSON 数组未完整结束")
            if buffer[position] == "]":
                position += 1
                skip_whitespace()
                if position < len(buffer) or fill():
                    skip_whitespace()
                    if position < len(buffer):
                        raise StreamingJSONError("JSON 数组结束后存在多余内容")
                return
            if not expect_value:
                if buffer[position] != ",":
                    raise StreamingJSONError("JSON 数组记录之间缺少逗号")
                position += 1
                skip_whitespace()
                if position >= len(buffer):
                    raise StreamingJSONError("JSON 数组未完整结束")
                if buffer[position] == "]":
                    raise StreamingJSONError("JSON 数组末尾不能有多余逗号")

            while True:
                try:
                    item, end = decoder.raw_decode(buffer, position)
                    position = end
                    yield item
                    expect_value = False
                    compact()
                    break
                except json.JSONDecodeError as exc:
                    if fill():
                        continue
                    raise StreamingJSONError(f"JSON 解析失败：{exc}") from exc


@dataclass(frozen=True)
class StreamingSourceManifestEntry:
    path: str
    file_name: str
    source_type: StreamingSourceType
    size_bytes: int
    mtime_ns: int
    sha256: str


class StreamingImportStaging:
    """A closeable, process-local view of parsed streaming records."""

    def __init__(
        self,
        *,
        temp_dir: Path,
        database_path: Path,
        source_dir: Path,
        manifest: tuple[StreamingSourceManifestEntry, ...],
    ) -> None:
        self.temp_dir = temp_dir
        self.database_path = database_path
        self.source_dir = source_dir
        self.manifest = manifest
        self._closed = False

    @classmethod
    def build(cls, streaming_dir: str | os.PathLike[str]) -> StreamingImportStaging:
        """Parse every streaming file once into a private temporary database."""

        _cleanup_orphans_once()
        source_dir = Path(streaming_dir).resolve()
        temp_dir = Path(tempfile.mkdtemp(prefix=_STAGING_DIR_PREFIX))
        os.chmod(temp_dir, 0o700)
        database_path = temp_dir / "staging.sqlite3"
        conn = sqlite3.connect(database_path)
        try:
            conn.executescript(
                """
                PRAGMA journal_mode=OFF;
                PRAGMA synchronous=OFF;
                CREATE TABLE source_files (
                    file_order INTEGER PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    record_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE source_records (
                    file_order INTEGER NOT NULL,
                    record_order INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    fingerprint TEXT,
                    timestamp TEXT,
                    is_object INTEGER NOT NULL,
                    has_timestamp INTEGER NOT NULL,
                    has_duration INTEGER NOT NULL,
                    PRIMARY KEY(file_order, record_order)
                ) WITHOUT ROWID;
                CREATE INDEX idx_staging_records_type
                    ON source_records(file_order, record_order);
                """
            )
            manifest: list[StreamingSourceManifestEntry] = []
            file_order = 0
            for pattern, source_type in _PATTERNS:
                for path in sorted(source_dir.glob(pattern)):
                    before = path.stat()
                    digest = _sha256_file(path)
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (
                        after.st_size,
                        after.st_mtime_ns,
                    ):
                        raise RuntimeError(f"source file changed while staging: {path.name}")
                    entry = StreamingSourceManifestEntry(
                        path=str(path.resolve()),
                        file_name=path.name,
                        source_type=source_type,
                        size_bytes=after.st_size,
                        mtime_ns=after.st_mtime_ns,
                        sha256=digest,
                    )
                    manifest.append(entry)
                    status = "ok"
                    error: str | None = None
                    conn.execute(
                        """INSERT INTO source_files
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            file_order,
                            entry.path,
                            entry.file_name,
                            source_type,
                            entry.size_bytes,
                            entry.mtime_ns,
                            entry.sha256,
                            status,
                            error,
                            0,
                        ),
                    )
                    from backend.domains.imports.source_inspector import record_fingerprint

                    record_count = 0
                    batch: list[tuple[Any, ...]] = []
                    try:
                        for record_order, item in enumerate(_iter_json_array(path)):
                            is_object = isinstance(item, dict)
                            fingerprint = record_fingerprint(item) if is_object else None
                            timestamp = item.get("ts") if is_object else None
                            batch.append(
                                (
                                    file_order,
                                    record_order,
                                    json.dumps(
                                        item,
                                        ensure_ascii=False,
                                        separators=(",", ":"),
                                    ),
                                    fingerprint,
                                    timestamp if isinstance(timestamp, str) else None,
                                    int(is_object),
                                    int(is_object and bool(item.get("ts"))),
                                    int(is_object and "ms_played" in item),
                                )
                            )
                            record_count += 1
                            if len(batch) >= _INSERT_BATCH_SIZE:
                                conn.executemany(
                                    "INSERT INTO source_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                    batch,
                                )
                                batch.clear()
                        if batch:
                            conn.executemany(
                                "INSERT INTO source_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                batch,
                            )
                    except (OSError, UnicodeDecodeError, StreamingJSONError) as exc:
                        status = "invalid"
                        error = str(exc)
                        record_count = 0
                        conn.execute(
                            "DELETE FROM source_records WHERE file_order=?",
                            (file_order,),
                        )
                    parsed = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (
                        parsed.st_size,
                        parsed.st_mtime_ns,
                    ):
                        raise RuntimeError(f"source file changed while staging: {path.name}")
                    conn.execute(
                        """UPDATE source_files
                           SET status=?, error=?, record_count=?
                           WHERE file_order=?""",
                        (status, error, record_count, file_order),
                    )
                    file_order += 1
            conn.commit()
        except Exception:
            conn.close()
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        else:
            conn.close()
        os.chmod(database_path, 0o600)
        return cls(
            temp_dir=temp_dir,
            database_path=database_path,
            source_dir=source_dir,
            manifest=tuple(manifest),
        )

    def _connect(self) -> sqlite3.Connection:
        if self._closed or not self.database_path.is_file():
            raise RuntimeError("streaming import staging is no longer available")
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def verify_source_manifest(self) -> None:
        """Fail closed unless the source file set and bytes are unchanged."""

        current: list[tuple[str, StreamingSourceType]] = []
        for pattern, source_type in _PATTERNS:
            current.extend(
                (str(path.resolve()), source_type) for path in sorted(self.source_dir.glob(pattern))
            )
        expected = [(entry.path, entry.source_type) for entry in self.manifest]
        if current != expected:
            raise RuntimeError("streaming source file set changed after staging")
        for entry in self.manifest:
            path = Path(entry.path)
            try:
                stat = path.stat()
            except OSError as exc:
                raise RuntimeError(
                    f"streaming source file is no longer readable: {entry.file_name}"
                ) from exc
            if stat.st_size != entry.size_bytes:
                raise RuntimeError(
                    f"streaming source file changed after staging: {entry.file_name}"
                )
            digest = _sha256_file(path)
            if digest != entry.sha256:
                raise RuntimeError(
                    f"streaming source file changed after staging: {entry.file_name}"
                )

    def inspection_rows(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            files = conn.execute("SELECT * FROM source_files ORDER BY file_order").fetchall()
            result: list[dict[str, Any]] = []
            for file_row in files:
                records = conn.execute(
                    """SELECT fingerprint, timestamp, is_object,
                              has_timestamp, has_duration
                       FROM source_records WHERE file_order=? ORDER BY record_order""",
                    (file_row["file_order"],),
                ).fetchall()
                result.append(
                    {
                        **dict(file_row),
                        "records": [
                            {
                                "fingerprint": row["fingerprint"],
                                "timestamp": row["timestamp"],
                                "is_object": bool(row["is_object"]),
                                "has_timestamp": bool(row["has_timestamp"]),
                                "has_duration": bool(row["has_duration"]),
                            }
                            for row in records
                        ],
                    }
                )
            return result
        finally:
            conn.close()

    def file_names(self, source_type: StreamingSourceType) -> list[str]:
        return [entry.path for entry in self.manifest if entry.source_type == source_type]

    def record_count(self) -> int:
        conn = self._connect()
        try:
            return int(conn.execute("SELECT COUNT(*) FROM source_records").fetchone()[0])
        finally:
            conn.close()

    def records_for_file(self, path: str | os.PathLike[str]) -> Iterator[Any]:
        """Yield decoded records for one manifest file in source order."""

        resolved = str(Path(path).resolve())
        if not any(entry.path == resolved for entry in self.manifest):
            raise ValueError("file is not part of this streaming import staging")
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT r.payload_json
                   FROM source_records r
                   JOIN source_files f USING(file_order)
                   WHERE f.path=? ORDER BY r.record_order""",
                (resolved,),
            )
            for row in rows:
                yield json.loads(row["payload_json"])
        finally:
            conn.close()

    def iter_records(self, source_type: StreamingSourceType) -> Iterator[tuple[str, Any]]:
        """Yield ``(file_path, decoded_record)`` in original file/record order."""

        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT f.path, r.payload_json
                   FROM source_records r
                   JOIN source_files f USING(file_order)
                   WHERE f.source_type=?
                   ORDER BY r.file_order, r.record_order""",
                (source_type,),
            )
            for row in rows:
                yield str(row["path"]), json.loads(row["payload_json"])
        finally:
            conn.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        shutil.rmtree(self.temp_dir, ignore_errors=True)


_cache_lock = threading.Lock()
_staging_cache: dict[str, tuple[float, StreamingImportStaging]] = {}
_orphan_cleanup_lock = threading.Lock()
_orphan_cleanup_done = False


def _cleanup_orphans_once() -> None:
    global _orphan_cleanup_done
    with _orphan_cleanup_lock:
        if _orphan_cleanup_done:
            return
        cleanup_orphaned_stagings()
        _orphan_cleanup_done = True


def _prune_cache(now: float) -> None:
    expired = [
        token
        for token, (created_at, _) in _staging_cache.items()
        if now - created_at > _CACHE_TTL_SECONDS
    ]
    while len(_staging_cache) - len(expired) >= _CACHE_MAX_ENTRIES:
        oldest = min(
            (item for item in _staging_cache if item not in expired),
            key=lambda token: _staging_cache[token][0],
        )
        expired.append(oldest)
    for token in expired:
        _, staging = _staging_cache.pop(token)
        staging.close()


def cache_staging(token: str, staging: StreamingImportStaging) -> None:
    """Keep a bounded, short-lived preflight staging for confirmed POST reuse."""

    with _cache_lock:
        _prune_cache(time.monotonic())
        previous = _staging_cache.pop(token, None)
        if previous is not None and previous[1] is not staging:
            previous[1].close()
        _staging_cache[token] = (time.monotonic(), staging)
    timer = threading.Timer(_CACHE_TTL_SECONDS, _expire_cached_staging, args=(token, staging))
    timer.daemon = True
    timer.start()


def _expire_cached_staging(token: str, expected: StreamingImportStaging) -> None:
    with _cache_lock:
        cached = _staging_cache.get(token)
        if cached is None or cached[1] is not expected:
            return
        _staging_cache.pop(token, None)
    expected.close()


def take_cached_staging(token: str | None) -> StreamingImportStaging | None:
    if not token:
        return None
    with _cache_lock:
        _prune_cache(time.monotonic())
        cached = _staging_cache.pop(token, None)
    return cached[1] if cached is not None else None


def _close_cached_stagings() -> None:
    with _cache_lock:
        cached = list(_staging_cache.values())
        _staging_cache.clear()
    for _, staging in cached:
        staging.close()


atexit.register(_close_cached_stagings)

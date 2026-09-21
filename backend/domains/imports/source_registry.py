"""Immutable streaming input batches and active-source resolution."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import AsyncIterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from backend.domains.imports.control_store import (
    active_source_state,
    control_root,
    find_frozen_batch,
    get_batch,
    insert_batch,
    json_text,
    source_root,
    update_batch,
    utc_now,
)
from backend.domains.imports.incremental import (
    FINGERPRINT_VERSION,
    FingerprintRecord,
    dataset_digest,
)
from backend.domains.imports.source_inspector import record_fingerprint
from backend.domains.imports.streaming_staging import StreamingImportStaging, _sha256_file

BatchKind = Literal["snapshot", "delta", "legacy"]
_SOURCE_PATTERNS = (
    ("Streaming_History_Audio_*.json", "audio"),
    ("Streaming_History_Video_*.json", "video"),
)
MAX_IMPORT_FILE_BYTES = 512 * 1024 * 1024
MAX_IMPORT_BATCH_BYTES = 8 * 1024 * 1024 * 1024
_UPLOAD_NAME = re.compile(r"^Streaming_History_(Audio|Video)_[A-Za-z0-9._ -]{1,200}\.json$")


class ImportSourceError(RuntimeError):
    def __init__(self, error_code: str, message: str | None = None):
        super().__init__(message or error_code)
        self.error_code = error_code


@contextmanager
def _batch_mutation_lock(batch_id: str, *, db_path: str | None = None) -> Iterator[None]:
    root = control_root(db_path) / "batch_locks"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{batch_id}.lock"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ImportSourceError("batch_busy") from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _manifest_digest(
    entries: list[dict[str, Any]],
    *,
    parent_manifest_digest: str | None = None,
    resolved_files: list[dict[str, Any]] | None = None,
) -> str:
    payload = {
        "schema_version": "streaming-source-manifest-v1",
        "files": entries,
        "parent_manifest_digest": parent_manifest_digest,
        "resolved_files": resolved_files or entries,
    }
    return hashlib.sha256(json_text(payload).encode("utf-8")).hexdigest()


def _copy_verified(source: Path, target: Path) -> dict[str, Any]:
    before = source.stat()
    source_digest = _sha256_file(source)
    after_hash = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after_hash.st_size, after_hash.st_mtime_ns):
        raise ImportSourceError("source_manifest_drift", f"source changed: {source.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    copied_digest = _sha256_file(target)
    after_copy = source.stat()
    if (
        copied_digest != source_digest
        or (before.st_size, before.st_mtime_ns) != (after_copy.st_size, after_copy.st_mtime_ns)
        or _sha256_file(source) != source_digest
    ):
        raise ImportSourceError("source_manifest_drift", f"source changed: {source.name}")
    return {
        "file_name": source.name,
        "size_bytes": before.st_size,
        "sha256": source_digest,
    }


def _resolved_name(source_type: str, ordinal: int, original: str, *, inherited: bool) -> str:
    marker = "parent" if inherited else "batch"
    safe_original = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in original)
    prefix = "Streaming_History_Audio_" if source_type == "audio" else "Streaming_History_Video_"
    suffix = hashlib.sha256(original.encode("utf-8")).hexdigest()[:12]
    # Repeated flattened delta generations must not grow names past filesystem
    # limits. The digest keeps truncated inherited names deterministic.
    stem = safe_original[:-5] if safe_original.lower().endswith(".json") else safe_original
    return f"{prefix}{marker}_{ordinal:04d}_{stem[:120]}_{suffix}.json"


def _link_or_copy(source: Path, target: Path) -> None:
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _directory_manifest(directory: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for pattern, source_type in _SOURCE_PATTERNS:
        for path in sorted(directory.glob(pattern)):
            files.append(
                {
                    "stored_name": path.name,
                    "source_type": source_type,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    return files


def _validated_upload_name(file_name: str, source_type: str) -> str:
    if len(file_name.encode("utf-8")) > 255 or Path(file_name).name != file_name:
        raise ImportSourceError("upload_file_name_invalid")
    match = _UPLOAD_NAME.fullmatch(file_name)
    if match is None or match.group(1).lower() != source_type:
        raise ImportSourceError("upload_file_name_invalid")
    return file_name


def create_receiving_batch(
    *,
    kind: BatchKind = "snapshot",
    parent_source_version_id: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    if kind not in {"snapshot", "delta", "legacy"}:
        raise ValueError("unsupported import batch kind")
    if kind == "delta" and not parent_source_version_id:
        parent_source_version_id = active_source_state(db_path=db_path).get(
            "active_source_version_id"
        )
    if kind == "delta" and not parent_source_version_id:
        raise ImportSourceError("delta_parent_missing")
    if parent_source_version_id:
        parent = get_batch(str(parent_source_version_id), db_path=db_path)
        if parent is None or parent.get("status") not in {"frozen", "published"}:
            raise ImportSourceError("delta_parent_unavailable")
    if kind == "delta":
        active_parent = active_source_state(db_path=db_path).get("active_source_version_id")
        if str(parent_source_version_id or "") != str(active_parent or ""):
            raise ImportSourceError("delta_parent_not_active")
    batch_id = uuid.uuid4().hex
    final_dir = source_root(db_path) / batch_id
    packet_dir = final_dir / "packet"
    packet_dir.mkdir(parents=True, exist_ok=False)
    try:
        final_dir.chmod(0o700)
        packet_dir.chmod(0o700)
    except OSError:
        pass
    row = {
        "batch_id": batch_id,
        "kind": kind,
        "status": "receiving",
        "parent_source_version_id": parent_source_version_id,
        "packet_path": str(packet_dir),
        "resolved_path": str(final_dir / "resolved"),
        "manifest": {"schema_version": "streaming-source-manifest-v1", "files": []},
        "manifest_digest": f"receiving:{batch_id}",
        "fingerprint_contract_version": FINGERPRINT_VERSION,
        "created_at": utc_now(),
        "frozen_at": None,
    }
    try:
        insert_batch(row, db_path=db_path)
    except Exception:
        shutil.rmtree(final_dir, ignore_errors=True)
        raise
    return get_batch(batch_id, db_path=db_path) or row


async def receive_batch_file(
    batch_id: str,
    file_name: str,
    source_type: Literal["audio", "video"],
    chunks: AsyncIterable[bytes],
    *,
    db_path: str | None = None,
) -> dict[str, Any]:
    with _batch_mutation_lock(batch_id, db_path=db_path):
        return await _receive_batch_file_unlocked(
            batch_id,
            file_name,
            source_type,
            chunks,
            db_path=db_path,
        )


async def _receive_batch_file_unlocked(
    batch_id: str,
    file_name: str,
    source_type: Literal["audio", "video"],
    chunks: AsyncIterable[bytes],
    *,
    db_path: str | None = None,
) -> dict[str, Any]:
    batch = get_batch(batch_id, db_path=db_path)
    if batch is None or batch.get("status") != "receiving":
        raise ImportSourceError("batch_not_receiving")
    safe_name = _validated_upload_name(file_name, source_type)
    packet_dir = Path(str(batch["packet_path"]))
    current_total = sum(path.stat().st_size for path in packet_dir.iterdir() if path.is_file())
    target = packet_dir / safe_name
    if target.exists():
        raise ImportSourceError("upload_file_exists")
    temp = packet_dir / f".{safe_name}.{uuid.uuid4().hex}.upload"
    size = 0
    digest = hashlib.sha256()
    try:
        with temp.open("xb") as handle:
            async for chunk in chunks:
                size += len(chunk)
                if size > MAX_IMPORT_FILE_BYTES or current_total + size > MAX_IMPORT_BATCH_BYTES:
                    raise ImportSourceError("upload_size_limit_exceeded")
                digest.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if size == 0:
            raise ImportSourceError("upload_file_empty")
        current = get_batch(batch_id, db_path=db_path)
        if current is None or current.get("status") != "receiving":
            raise ImportSourceError("batch_not_receiving")
        if target.exists():
            raise ImportSourceError("upload_file_exists")
        os.replace(temp, target)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return {
        "batch_id": batch_id,
        "file_name": safe_name,
        "source_type": source_type,
        "size_bytes": size,
        "sha256": digest.hexdigest(),
        "status": "received",
    }


def finalize_receiving_batch(batch_id: str, *, db_path: str | None = None) -> dict[str, Any]:
    with _batch_mutation_lock(batch_id, db_path=db_path):
        return _finalize_receiving_batch_unlocked(batch_id, db_path=db_path)


def _finalize_receiving_batch_unlocked(
    batch_id: str, *, db_path: str | None = None
) -> dict[str, Any]:
    batch = get_batch(batch_id, db_path=db_path)
    if batch is None or batch.get("status") != "receiving":
        raise ImportSourceError("batch_not_receiving")
    if batch.get("kind") == "delta":
        active_parent = active_source_state(db_path=db_path).get("active_source_version_id")
        if str(batch.get("parent_source_version_id") or "") != str(active_parent or ""):
            update_batch(
                batch_id,
                db_path=db_path,
                status="invalid",
                error_code="delta_parent_not_active",
            )
            raise ImportSourceError("delta_parent_not_active")
    packet_dir = Path(str(batch["packet_path"]))
    candidates: list[tuple[Path, str]] = []
    for pattern, source_type in _SOURCE_PATTERNS:
        candidates.extend((path, source_type) for path in sorted(packet_dir.glob(pattern)))
    if not any(source_type == "audio" for _, source_type in candidates):
        raise ImportSourceError("streaming_audio_missing")
    manifest: list[dict[str, Any]] = [
        {
            "file_name": path.name,
            "stored_name": path.name,
            "source_type": source_type,
            "ordinal": ordinal,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for ordinal, (path, source_type) in enumerate(candidates)
    ]
    resolved_dir = Path(str(batch["resolved_path"]))
    temp_resolved = resolved_dir.parent / f".resolved.{uuid.uuid4().hex}"
    temp_resolved.mkdir()
    parent_digest = None
    try:
        parent_id = batch.get("parent_source_version_id")
        if parent_id:
            parent = get_batch(str(parent_id), db_path=db_path)
            if parent is None:
                raise ImportSourceError("delta_parent_unavailable")
            parent_digest = str(parent["manifest_digest"])
            parent_dir = Path(str(parent["resolved_path"]))
            inherited: list[tuple[Path, str]] = []
            for pattern, source_type in _SOURCE_PATTERNS:
                inherited.extend((path, source_type) for path in sorted(parent_dir.glob(pattern)))
            for ordinal, (path, source_type) in enumerate(inherited):
                _link_or_copy(
                    path,
                    temp_resolved / _resolved_name(source_type, ordinal, path.name, inherited=True),
                )
        for entry in manifest:
            _link_or_copy(packet_dir / entry["stored_name"], temp_resolved / entry["stored_name"])
        descriptor = os.open(temp_resolved, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temp_resolved, resolved_dir)
        if batch.get("parent_source_version_id"):
            current_parent = get_batch(str(batch["parent_source_version_id"]), db_path=db_path)
            if current_parent is None or str(current_parent["manifest_digest"]) != parent_digest:
                raise ImportSourceError("delta_parent_drift")
        resolved_files = _directory_manifest(resolved_dir)
        digest = _manifest_digest(
            manifest,
            parent_manifest_digest=parent_digest,
            resolved_files=resolved_files,
        )
        existing = find_frozen_batch(
            str(batch["kind"]),
            digest,
            batch.get("parent_source_version_id"),
            db_path=db_path,
        )
        if existing is not None:
            update_batch(
                batch_id,
                db_path=db_path,
                status="invalid",
                error_code="duplicate_batch_content",
            )
            shutil.rmtree(resolved_dir.parent, ignore_errors=True)
            return existing
        update_batch(
            batch_id,
            db_path=db_path,
            status="frozen",
            manifest_json={
                "schema_version": "streaming-source-manifest-v1",
                "files": manifest,
                "parent_manifest_digest": parent_digest,
                "resolved_files": resolved_files,
            },
            manifest_digest=digest,
            frozen_at=utc_now(),
            error_code=None,
        )
        return get_batch(batch_id, db_path=db_path) or batch
    except Exception as exc:
        shutil.rmtree(temp_resolved, ignore_errors=True)
        shutil.rmtree(resolved_dir, ignore_errors=True)
        update_batch(
            batch_id,
            db_path=db_path,
            status="invalid",
            error_code=getattr(exc, "error_code", "batch_finalize_failed"),
        )
        raise


def freeze_local_batch(
    source_dir: str | os.PathLike[str],
    *,
    kind: BatchKind = "snapshot",
    parent_source_version_id: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Copy one local packet into an immutable, replayable source version."""

    if kind not in {"snapshot", "delta", "legacy"}:
        raise ValueError("unsupported import batch kind")
    if kind == "delta" and not parent_source_version_id:
        parent_source_version_id = active_source_state(db_path=db_path).get(
            "active_source_version_id"
        )
    if kind == "delta" and not parent_source_version_id:
        raise ImportSourceError("delta_parent_missing")
    parent = (
        get_batch(str(parent_source_version_id), db_path=db_path)
        if parent_source_version_id
        else None
    )
    if parent_source_version_id and (
        parent is None or parent.get("status") not in {"frozen", "published"}
    ):
        raise ImportSourceError("delta_parent_unavailable")
    if kind == "delta":
        active_parent = active_source_state(db_path=db_path).get("active_source_version_id")
        if str(parent_source_version_id or "") != str(active_parent or ""):
            raise ImportSourceError("delta_parent_not_active")

    source = Path(source_dir).resolve()
    candidates: list[tuple[Path, str]] = []
    for pattern, source_type in _SOURCE_PATTERNS:
        candidates.extend((path, source_type) for path in sorted(source.glob(pattern)))
    if not any(source_type == "audio" for _, source_type in candidates):
        raise ImportSourceError("streaming_audio_missing")

    root = source_root(db_path)
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    batch_id = uuid.uuid4().hex
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{batch_id}.", dir=root))
    packet_dir = temp_dir / "packet"
    resolved_dir = temp_dir / "resolved"
    packet_dir.mkdir()
    resolved_dir.mkdir()
    manifest: list[dict[str, Any]] = []
    parent_digest = str(parent["manifest_digest"]) if parent is not None else None
    try:
        for ordinal, (path, source_type) in enumerate(candidates):
            target_name = path.name
            evidence = _copy_verified(path, packet_dir / target_name)
            manifest.append(
                {
                    **evidence,
                    "stored_name": target_name,
                    "source_type": source_type,
                    "ordinal": ordinal,
                }
            )
        if parent is not None:
            current_parent = get_batch(str(parent_source_version_id), db_path=db_path)
            if current_parent is None or str(current_parent["manifest_digest"]) != parent_digest:
                raise ImportSourceError("delta_parent_drift")
            parent_resolved = Path(str(parent["resolved_path"]))
            if not parent_resolved.is_dir():
                raise ImportSourceError("delta_parent_unavailable")
            inherited: list[tuple[Path, str]] = []
            for pattern, source_type in _SOURCE_PATTERNS:
                inherited.extend(
                    (path, source_type) for path in sorted(parent_resolved.glob(pattern))
                )
            for ordinal, (path, source_type) in enumerate(inherited):
                _link_or_copy(
                    path,
                    resolved_dir / _resolved_name(source_type, ordinal, path.name, inherited=True),
                )
        for entry in manifest:
            _link_or_copy(packet_dir / entry["stored_name"], resolved_dir / entry["stored_name"])
        if parent is not None:
            current_parent = get_batch(str(parent_source_version_id), db_path=db_path)
            if current_parent is None or str(current_parent["manifest_digest"]) != parent_digest:
                raise ImportSourceError("delta_parent_drift")
        resolved_files = _directory_manifest(resolved_dir)
        for directory in (packet_dir, resolved_dir, temp_dir):
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        if kind == "delta":
            active_parent = active_source_state(db_path=db_path).get("active_source_version_id")
            if str(parent_source_version_id or "") != str(active_parent or ""):
                raise ImportSourceError("delta_parent_not_active")
        final_dir = root / batch_id
        os.replace(temp_dir, final_dir)
        now = utc_now()
        row = {
            "batch_id": batch_id,
            "kind": kind,
            "status": "frozen",
            "parent_source_version_id": parent_source_version_id,
            "packet_path": str(final_dir / "packet"),
            "resolved_path": str(final_dir / "resolved"),
            "manifest": {
                "schema_version": "streaming-source-manifest-v1",
                "files": manifest,
                "parent_manifest_digest": parent_digest,
                "resolved_files": resolved_files,
            },
            "manifest_digest": _manifest_digest(
                manifest,
                parent_manifest_digest=parent_digest,
                resolved_files=resolved_files,
            ),
            "fingerprint_contract_version": FINGERPRINT_VERSION,
            "created_at": now,
            "frozen_at": now,
        }
        actual_id = insert_batch(row, db_path=db_path)
        if actual_id != batch_id:
            shutil.rmtree(final_dir, ignore_errors=True)
            existing = get_batch(actual_id, db_path=db_path)
            if existing is None:
                raise ImportSourceError("batch_deduplication_failed")
            return existing
        return get_batch(batch_id, db_path=db_path) or row
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        candidate = root / batch_id
        if candidate.exists():
            shutil.rmtree(candidate, ignore_errors=True)
        raise


def resolve_batch_directory(
    batch_id: str,
    *,
    active: bool = False,
    db_path: str | None = None,
) -> Path:
    batch = get_batch(batch_id, db_path=db_path)
    if batch is None or batch.get("status") not in {"frozen", "published"}:
        raise ImportSourceError("batch_unavailable")
    path = Path(str(batch["resolved_path"] if active else batch["packet_path"]))
    if not path.is_dir():
        raise ImportSourceError("batch_files_missing")
    for entry in batch["manifest"].get("files", []):
        packet = Path(str(batch["packet_path"])) / str(entry["stored_name"])
        if not packet.is_file() or packet.stat().st_size != int(entry["size_bytes"]):
            raise ImportSourceError("batch_manifest_drift")
        if _sha256_file(packet) != str(entry["sha256"]):
            raise ImportSourceError("batch_manifest_drift")
    if active:
        resolved_files = batch["manifest"].get("resolved_files")
        if not isinstance(resolved_files, list) or not resolved_files:
            raise ImportSourceError("legacy_unfenced_source")
        expected_names = set()
        for entry in resolved_files:
            name = str(entry.get("stored_name") or "")
            expected_names.add(name)
            resolved = path / name
            if (
                not resolved.is_file()
                or resolved.stat().st_size != int(entry["size_bytes"])
                or _sha256_file(resolved) != str(entry["sha256"])
            ):
                raise ImportSourceError("batch_resolved_manifest_drift")
        actual_names = {item.name for item in path.iterdir() if item.is_file()}
        if actual_names != expected_names:
            raise ImportSourceError("batch_resolved_manifest_drift")
        parent_id = batch.get("parent_source_version_id")
        if parent_id:
            parent = get_batch(str(parent_id), db_path=db_path)
            if parent is None or str(parent.get("manifest_digest") or "") != str(
                batch["manifest"].get("parent_manifest_digest") or ""
            ):
                raise ImportSourceError("delta_parent_drift")
    return path


def resolve_active_source(*, db_path: str | None = None) -> Path | None:
    source_id = active_source_state(db_path=db_path).get("active_source_version_id")
    if not source_id:
        return None
    return resolve_batch_directory(str(source_id), active=True, db_path=db_path)


def source_dataset_summary(
    batch_id: str,
    *,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Return the exact deduplicated fingerprint set represented by a source."""

    source = resolve_batch_directory(batch_id, active=True, db_path=db_path)
    staging = StreamingImportStaging.build(source)
    try:
        records: list[FingerprintRecord] = []
        for source_type in ("audio", "video"):
            for file_name in staging.file_names(source_type):
                records.extend(
                    FingerprintRecord(
                        source_type=source_type,
                        fingerprint=record_fingerprint(record),
                    )
                    for record in staging.records_for_file(file_name)
                )
        identities = {record.identity for record in records}
        return {
            "record_count": len(identities),
            "dataset_digest": dataset_digest(records),
        }
    finally:
        staging.close()


def validate_batch_lineage(batch_id: str, *, db_path: str | None = None) -> None:
    """Fence a delta batch against the source version active at execution time."""

    batch = get_batch(batch_id, db_path=db_path)
    if batch is None or batch.get("status") not in {"frozen", "published"}:
        raise ImportSourceError("batch_unavailable")
    if batch.get("kind") != "delta":
        return
    active_parent = active_source_state(db_path=db_path).get("active_source_version_id")
    if str(batch.get("parent_source_version_id") or "") != str(active_parent or ""):
        raise ImportSourceError("delta_parent_not_active")

#!/usr/bin/env python3
"""Validate, transfer, and retain Docker save layouts through a local SHA-256 CAS."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 2
STATE_SCHEMA_VERSION = 1
LAYOUT_FILES = ("index.json", "manifest.json", "oci-layout", "repositories")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_BLOBS = 4096
MAX_LAYOUT_FILE_BYTES = 8 * 1024 * 1024
MAX_BLOB_BYTES = 20 * 1024 * 1024 * 1024
MAX_TOTAL_BLOB_BYTES = 40 * 1024 * 1024 * 1024


class TransportError(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, payload: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=str(path.parent)
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_json(path: Path, *, max_bytes: int = MAX_LAYOUT_FILE_BYTES) -> Any:
    if path.is_symlink() or not path.is_file():
        raise TransportError(f"不是安全的普通 JSON 文件：{path}")
    size = path.stat().st_size
    if size <= 0 or size > max_bytes:
        raise TransportError(f"JSON 文件大小超限：{path} ({size})")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TransportError(f"无法解析 JSON：{path}") from error


def require_revision(revision: str) -> None:
    if not SHA_RE.fullmatch(revision):
        raise TransportError("revision 必须是 40 位小写十六进制 commit SHA")


def require_mode(mode: str) -> None:
    if mode not in {"smoke", "release"}:
        raise TransportError("mode 必须是 smoke 或 release")


def expected_transport_refs(revision: str) -> dict[str, str]:
    return {
        "api": f"spotify-stats-api:transport-{revision}",
        "web": f"spotify-stats-web:transport-{revision}",
    }


def _safe_tar_member_name(name: str) -> str:
    normalized = name.rstrip("/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise TransportError(f"Docker save 包含不安全路径：{name}")
    return normalized


def _allowed_layout_path(name: str, *, directory: bool) -> bool:
    if directory:
        return name in {"blobs", "blobs/sha256"}
    if name in LAYOUT_FILES:
        return True
    parts = PurePosixPath(name).parts
    return (
        len(parts) == 3 and parts[:2] == ("blobs", "sha256") and bool(DIGEST_RE.fullmatch(parts[2]))
    )


def extract_docker_save(archive: Path, layout: Path) -> None:
    if archive.is_symlink() or not archive.is_file():
        raise TransportError(f"Docker save archive 不存在或不是普通文件：{archive}")
    if layout.exists():
        raise TransportError(f"layout 目标必须不存在：{layout}")
    layout.mkdir(parents=True, mode=0o700)
    seen: set[str] = set()
    with tarfile.open(archive, mode="r:") as source:
        members = source.getmembers()
        if len(members) > MAX_BLOBS + 16:
            raise TransportError("Docker save archive 条目数超过安全上限")
        for member in members:
            name = _safe_tar_member_name(member.name)
            if name in seen:
                raise TransportError(f"Docker save archive 包含重复路径：{name}")
            seen.add(name)
            is_directory = member.isdir()
            if not is_directory and not member.isfile():
                raise TransportError(f"Docker save archive 包含非普通文件：{name}")
            if not _allowed_layout_path(name, directory=is_directory):
                raise TransportError(f"Docker save archive 包含未知条目：{name}")
            destination = layout.joinpath(*PurePosixPath(name).parts)
            if is_directory:
                destination.mkdir(parents=True, exist_ok=True, mode=0o700)
                continue
            if member.size < 0 or member.size > MAX_BLOB_BYTES:
                raise TransportError(f"Docker save archive 文件大小超限：{name}")
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            extracted = source.extractfile(member)
            if extracted is None:
                raise TransportError(f"无法读取 Docker save archive 条目：{name}")
            with destination.open("xb") as target:
                shutil.copyfileobj(extracted, target, length=1024 * 1024)
            os.chmod(destination, 0o600)


def _blob_name_from_path(value: Any) -> str:
    if not isinstance(value, str):
        raise TransportError("Docker save blob 路径必须是字符串")
    parts = PurePosixPath(value).parts
    if len(parts) != 3 or parts[:2] != ("blobs", "sha256") or not DIGEST_RE.fullmatch(parts[2]):
        raise TransportError(f"Docker save blob 路径不安全：{value}")
    return parts[2]


def _blob_name_from_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise TransportError(f"{label} digest 无效")
    name = value.removeprefix("sha256:")
    if not DIGEST_RE.fullmatch(name):
        raise TransportError(f"{label} digest 无效")
    return name


def _validate_image_config(layout: Path, config_name: str, role: str, revision: str) -> None:
    config_path = layout / "blobs" / "sha256" / config_name
    if sha256_path(config_path) != config_name:
        raise TransportError(f"镜像 config digest 不匹配：{role}")
    config = read_json(config_path)
    if not isinstance(config, dict):
        raise TransportError(f"镜像 config JSON 格式无效：{role}")
    config_section = config.get("config", {})
    if not isinstance(config_section, dict):
        raise TransportError(f"镜像 config.config 格式无效：{role}")
    labels = config_section.get("Labels", {})
    if config.get("os") != "linux" or config.get("architecture") != "amd64":
        raise TransportError(f"镜像 config 平台不是 linux/amd64：{role}")
    if not isinstance(labels, dict) or labels.get("org.opencontainers.image.revision") != revision:
        raise TransportError(f"镜像 revision label 不匹配：{role}")


def _validate_layout_json(
    layout: Path,
    revision: str,
    expected_refs: Mapping[str, str],
    *,
    require_blob_contents: bool,
) -> tuple[list[dict[str, str]], set[str]]:
    oci_layout = read_json(layout / "oci-layout")
    if oci_layout != {"imageLayoutVersion": "1.0.0"}:
        raise TransportError("oci-layout 版本不受支持")

    manifest = read_json(layout / "manifest.json")
    if not isinstance(manifest, list) or len(manifest) != 2:
        raise TransportError("manifest.json 必须恰好包含 API/Web 两张镜像")
    expected_by_ref = {value: role for role, value in expected_refs.items()}
    seen_roles: set[str] = set()
    referenced_blobs: set[str] = set()
    images: list[dict[str, str]] = []
    for entry in manifest:
        if not isinstance(entry, dict):
            raise TransportError("manifest.json 镜像项格式无效")
        repo_tags = entry.get("RepoTags")
        if (
            not isinstance(repo_tags, list)
            or len(repo_tags) != 1
            or repo_tags[0] not in expected_by_ref
        ):
            raise TransportError(f"Docker save 包含额外或错误 RepoTags：{repo_tags}")
        role = expected_by_ref[repo_tags[0]]
        if role in seen_roles:
            raise TransportError(f"Docker save 重复镜像角色：{role}")
        seen_roles.add(role)
        config_name = _blob_name_from_path(entry.get("Config"))
        layers = entry.get("Layers")
        if not isinstance(layers, list) or not layers:
            raise TransportError(f"Docker save 镜像缺少 layers：{role}")
        layer_names = [_blob_name_from_path(value) for value in layers]
        referenced_blobs.update([config_name, *layer_names])
        if require_blob_contents:
            _validate_image_config(layout, config_name, role, revision)
        images.append(
            {
                "role": role,
                "archive_ref": repo_tags[0],
                "config_digest": f"sha256:{config_name}",
                "image_id": f"sha256:{config_name}",
            }
        )

    if seen_roles != set(expected_refs):
        raise TransportError("Docker save 未包含完整 API/Web 镜像集合")
    images_by_role = {image["role"]: image for image in images}

    index = read_json(layout / "index.json")
    descriptors = index.get("manifests") if isinstance(index, dict) else None
    if (
        not isinstance(index, dict)
        or index.get("schemaVersion") != 2
        or not isinstance(descriptors, list)
        or len(descriptors) != 2
    ):
        raise TransportError("index.json 必须恰好描述 API/Web 两张镜像")
    descriptor_roles: set[str] = set()
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise TransportError("index.json descriptor 格式无效")
        descriptor_name = _blob_name_from_digest(descriptor.get("digest"), "index.json descriptor")
        annotations = descriptor.get("annotations")
        image_ref = (
            annotations.get("io.containerd.image.name") if isinstance(annotations, dict) else None
        )
        role = expected_by_ref.get(image_ref) if isinstance(image_ref, str) else None
        if role is None or role in descriptor_roles:
            raise TransportError("index.json descriptor 未精确映射 API/Web archive ref")
        descriptor_roles.add(role)
        referenced_blobs.add(descriptor_name)
        if not require_blob_contents:
            continue

        descriptor_path = layout / "blobs" / "sha256" / descriptor_name
        if sha256_path(descriptor_path) != descriptor_name:
            raise TransportError(f"OCI manifest digest 不匹配：{role}")
        descriptor_size = descriptor.get("size")
        if (
            not isinstance(descriptor_size, int)
            or descriptor_size <= 0
            or descriptor_path.stat().st_size != descriptor_size
        ):
            raise TransportError(f"OCI manifest size 不匹配：{role}")
        oci_manifest = read_json(descriptor_path)
        if not isinstance(oci_manifest, dict) or oci_manifest.get("schemaVersion") != 2:
            raise TransportError(f"OCI manifest 格式无效：{role}")
        config_descriptor = oci_manifest.get("config")
        layer_descriptors = oci_manifest.get("layers")
        if not isinstance(config_descriptor, dict) or not isinstance(layer_descriptors, list):
            raise TransportError(f"OCI manifest config/layers 格式无效：{role}")
        if not layer_descriptors:
            raise TransportError(f"OCI manifest 缺少 layers：{role}")
        config_name = _blob_name_from_digest(config_descriptor.get("digest"), f"OCI config {role}")
        config_path = layout / "blobs" / "sha256" / config_name
        config_size = config_descriptor.get("size")
        if (
            not isinstance(config_size, int)
            or config_size <= 0
            or config_path.stat().st_size != config_size
        ):
            raise TransportError(f"OCI config size 不匹配：{role}")
        _validate_image_config(layout, config_name, role, revision)
        referenced_blobs.add(config_name)
        for layer_descriptor in layer_descriptors:
            if not isinstance(layer_descriptor, dict):
                raise TransportError(f"OCI layer descriptor 格式无效：{role}")
            layer_name = _blob_name_from_digest(layer_descriptor.get("digest"), f"OCI layer {role}")
            layer_path = layout / "blobs" / "sha256" / layer_name
            layer_size = layer_descriptor.get("size")
            if (
                not isinstance(layer_size, int)
                or layer_size <= 0
                or layer_path.stat().st_size != layer_size
            ):
                raise TransportError(f"OCI layer size 不匹配：{role}")
            referenced_blobs.add(layer_name)
        images_by_role[role]["config_digest"] = f"sha256:{config_name}"
        images_by_role[role]["image_id"] = f"sha256:{config_name}"

    if descriptor_roles != set(expected_refs):
        raise TransportError("index.json 未包含完整 API/Web descriptor")

    repositories = read_json(layout / "repositories")
    if not isinstance(repositories, dict) or set(repositories) != {
        ref.rsplit(":", 1)[0] for ref in expected_refs.values()
    }:
        raise TransportError("repositories 包含额外或缺失仓库")
    expected_tags = {ref.rsplit(":", 1)[0]: ref.rsplit(":", 1)[1] for ref in expected_refs.values()}
    for repository, values in repositories.items():
        if not isinstance(values, dict) or set(values) != {expected_tags[repository]}:
            raise TransportError(f"repositories 包含额外或缺失 tag：{repository}")

    images.sort(key=lambda image: image["role"])
    return images, referenced_blobs


def _blob_records(layout: Path, *, verify_contents: bool) -> list[dict[str, Any]]:
    blob_root = layout / "blobs" / "sha256"
    if blob_root.is_symlink() or not blob_root.is_dir():
        raise TransportError("layout 缺少 blobs/sha256")
    paths = sorted(blob_root.iterdir(), key=lambda item: item.name)
    if not paths or len(paths) > MAX_BLOBS:
        raise TransportError("blob 数量为空或超过安全上限")
    records: list[dict[str, Any]] = []
    total = 0
    for path in paths:
        if path.is_symlink() or not path.is_file() or not DIGEST_RE.fullmatch(path.name):
            raise TransportError(f"blob 文件名或类型无效：{path}")
        size = path.stat().st_size
        if size <= 0 or size > MAX_BLOB_BYTES:
            raise TransportError(f"blob 大小无效：{path.name} ({size})")
        if verify_contents and sha256_path(path) != path.name:
            raise TransportError(f"blob 文件名与内容 SHA-256 不匹配：{path.name}")
        total += size
        if total > MAX_TOTAL_BLOB_BYTES:
            raise TransportError("blob 总大小超过安全上限")
        records.append({"digest": f"sha256:{path.name}", "size": size})
    return records


def build_artifact(
    archive: Path,
    artifact: Path,
    revision: str,
    mode: str,
    api_ref: str | None = None,
    web_ref: str | None = None,
) -> dict[str, Any]:
    require_revision(revision)
    require_mode(mode)
    if artifact.exists():
        raise TransportError(f"Artifact 目标必须不存在：{artifact}")
    artifact.mkdir(parents=True, mode=0o700)
    layout = artifact / "layout"
    extract_docker_save(archive, layout)
    expected_refs = expected_transport_refs(revision)
    if api_ref is not None or web_ref is not None:
        if not api_ref or not web_ref or api_ref == web_ref:
            raise TransportError("bootstrap API/Web archive refs 必须同时提供且不同")
        expected_refs = {"api": api_ref, "web": web_ref}
    images, referenced_blobs = _validate_layout_json(
        layout, revision, expected_refs, require_blob_contents=True
    )
    blobs = _blob_records(layout, verify_contents=True)
    blob_names = {record["digest"].removeprefix("sha256:") for record in blobs}
    if not referenced_blobs.issubset(blob_names):
        raise TransportError("layout JSON 引用了不存在的 blob")
    layout_files = [
        {"path": name, "sha256": sha256_path(layout / name), "size": (layout / name).stat().st_size}
        for name in LAYOUT_FILES
    ]
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "revision": revision,
        "mode": mode,
        "platform": "linux/amd64",
        "images": images,
        "layout_files": layout_files,
        "blobs": blobs,
        "total_blob_bytes": sum(record["size"] for record in blobs),
    }
    atomic_write(artifact / "transport-manifest.json", canonical_json_bytes(manifest))
    return manifest


def load_transport_manifest(
    manifest_path: Path,
    expected_digest: str,
    expected_revision: str,
    expected_mode: str,
) -> dict[str, Any]:
    require_revision(expected_revision)
    require_mode(expected_mode)
    if not DIGEST_RE.fullmatch(expected_digest):
        raise TransportError("transport manifest digest 无效")
    if sha256_path(manifest_path) != expected_digest:
        raise TransportError("transport manifest 与 workflow 透传 digest 不匹配")
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise TransportError("transport manifest schema 不受支持")
    if manifest.get("revision") != expected_revision or manifest.get("mode") != expected_mode:
        raise TransportError("transport manifest revision/mode 不匹配")
    if manifest.get("platform") != "linux/amd64":
        raise TransportError("transport manifest 平台不受支持")
    expected_keys = {
        "schema_version",
        "revision",
        "mode",
        "platform",
        "images",
        "layout_files",
        "blobs",
        "total_blob_bytes",
    }
    if set(manifest) != expected_keys:
        raise TransportError("transport manifest 包含未知或缺失字段")
    return manifest


def _validate_manifest_records(manifest: Mapping[str, Any], layout: Path) -> None:
    layout_files = manifest.get("layout_files")
    if not isinstance(layout_files, list) or len(layout_files) != len(LAYOUT_FILES):
        raise TransportError("transport manifest layout_files 无效")
    seen_layout: set[str] = set()
    for record in layout_files:
        if not isinstance(record, dict) or set(record) != {"path", "sha256", "size"}:
            raise TransportError("layout file record 无效")
        name, digest, size = record["path"], record["sha256"], record["size"]
        if name not in LAYOUT_FILES or name in seen_layout or not DIGEST_RE.fullmatch(str(digest)):
            raise TransportError("layout file record 路径或 digest 无效")
        path = layout / name
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != size
            or sha256_path(path) != digest
        ):
            raise TransportError(f"layout metadata 校验失败：{name}")
        seen_layout.add(name)
    if seen_layout != set(LAYOUT_FILES):
        raise TransportError("layout metadata 不完整")

    blobs = manifest.get("blobs")
    if not isinstance(blobs, list) or not blobs or len(blobs) > MAX_BLOBS:
        raise TransportError("transport manifest blobs 无效")
    seen_blobs: set[str] = set()
    total = 0
    for record in blobs:
        if not isinstance(record, dict) or set(record) != {"digest", "size"}:
            raise TransportError("blob record 无效")
        digest, size = record["digest"], record["size"]
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise TransportError("blob digest 无效")
        name = digest.removeprefix("sha256:")
        if not DIGEST_RE.fullmatch(name) or name in seen_blobs:
            raise TransportError("blob digest 重复或格式无效")
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or size > MAX_BLOB_BYTES
        ):
            raise TransportError("blob size 无效")
        seen_blobs.add(name)
        total += size
        if total > MAX_TOTAL_BLOB_BYTES:
            raise TransportError("blob 总大小超过安全上限")
    if manifest.get("total_blob_bytes") != total:
        raise TransportError("transport manifest total_blob_bytes 不匹配")

    images = manifest.get("images")
    if not isinstance(images, list) or len(images) != 2:
        raise TransportError("transport manifest images 无效")
    if {image.get("role") for image in images if isinstance(image, dict)} != {"api", "web"}:
        raise TransportError("transport manifest 必须恰好包含 API/Web")
    for image in images:
        if not isinstance(image, dict) or set(image) != {
            "role",
            "archive_ref",
            "config_digest",
            "image_id",
        }:
            raise TransportError("transport manifest image record 无效")
        for field in ("config_digest", "image_id"):
            value = image[field]
            if (
                not isinstance(value, str)
                or not value.startswith("sha256:")
                or not DIGEST_RE.fullmatch(value.removeprefix("sha256:"))
            ):
                raise TransportError(f"transport manifest image {field} 无效")


def _blob_is_valid(path: Path, digest: str, size: int) -> bool:
    return (
        not path.is_symlink()
        and path.is_file()
        and path.stat().st_size == size
        and sha256_path(path) == digest
    )


def plan_transfer(
    staging: Path, releases_root: Path, revision: str, mode: str, digest: str
) -> dict[str, Any]:
    manifest = load_transport_manifest(staging / "transport-manifest.json", digest, revision, mode)
    layout = staging / "layout"
    _validate_manifest_records(manifest, layout)
    expected_refs = {image["role"]: image["archive_ref"] for image in manifest["images"]}
    _images, referenced_blobs = _validate_layout_json(
        layout, revision, expected_refs, require_blob_contents=False
    )
    if expected_refs != expected_transport_refs(revision):
        raise TransportError("normal transport artifact 必须使用不可部署的 transport-<SHA> refs")
    manifest_blobs = {record["digest"].removeprefix("sha256:") for record in manifest["blobs"]}
    if not referenced_blobs.issubset(manifest_blobs):
        raise TransportError("layout metadata 引用了 manifest 未声明的 blob")
    missing_records: list[tuple[str, int]] = []
    missing_bytes = 0
    cache_root = releases_root / "blobs" / "sha256"
    for record in manifest["blobs"]:
        name = record["digest"].removeprefix("sha256:")
        if not _blob_is_valid(cache_root / name, name, record["size"]):
            missing_records.append((f"layout/blobs/sha256/{name}", record["size"]))
            missing_bytes += record["size"]
    missing = sorted(path for path, _size in missing_records)
    atomic_write(
        staging / "missing-blobs.txt", ("\n".join(missing) + ("\n" if missing else "")).encode()
    )
    shard_paths: list[list[str]] = [[], [], [], []]
    shard_bytes = [0, 0, 0, 0]
    for path, size in sorted(missing_records, key=lambda item: (-item[1], item[0])):
        shard = min(range(4), key=lambda index: (shard_bytes[index], index))
        shard_paths[shard].append(path)
        shard_bytes[shard] += size
    for index, paths in enumerate(shard_paths):
        paths.sort()
        atomic_write(
            staging / f"missing-blobs.{index}.txt",
            ("\n".join(paths) + ("\n" if paths else "")).encode(),
        )
    (staging / "upload").mkdir(parents=True, exist_ok=True, mode=0o700)
    result = {
        "blob_count": len(manifest["blobs"]),
        "cache_hits": len(manifest["blobs"]) - len(missing),
        "missing_count": len(missing),
        "missing_bytes": missing_bytes,
        "shard_bytes": shard_bytes,
    }
    atomic_write(staging / "plan-result.json", canonical_json_bytes(result))
    return result


def _cache_blob(source: Path, destination: Path, digest: str, size: int) -> None:
    if not _blob_is_valid(source, digest, size):
        raise TransportError(f"上传 blob 校验失败：{digest}")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if source.stat().st_dev != destination.parent.stat().st_dev:
        raise TransportError("incoming 与 blob CAS 必须位于同一文件系统")
    if destination.exists() or destination.is_symlink():
        if _blob_is_valid(destination, digest, size):
            return
        quarantine = destination.parent.parent / "quarantine"
        quarantine.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.replace(destination, quarantine / f"{digest}.{os.getpid()}")
    os.chmod(source, 0o600)
    with source.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(source, destination)
    _fsync_directory(destination.parent)
    if not _blob_is_valid(destination, digest, size):
        raise TransportError(f"CAS 原子发布后复验失败：{digest}")


def _build_archive(layout: Path, archive: Path) -> None:
    partial = archive.with_name(f".{archive.name}.partial")
    if partial.exists() or partial.is_symlink():
        partial.unlink()
    with tarfile.open(partial, mode="w", format=tarfile.PAX_FORMAT) as output:
        for name in (*LAYOUT_FILES, "blobs"):
            output.add(layout / name, arcname=name, recursive=True)
    with partial.open("rb") as handle:
        os.fsync(handle.fileno())
    os.chmod(partial, 0o600)
    os.replace(partial, archive)
    _fsync_directory(archive.parent)


def materialize(
    staging: Path, releases_root: Path, revision: str, mode: str, digest: str
) -> dict[str, Any]:
    manifest = load_transport_manifest(staging / "transport-manifest.json", digest, revision, mode)
    layout = staging / "layout"
    _validate_manifest_records(manifest, layout)
    locks = releases_root / "locks"
    locks.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = locks / "cas.lock"
    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        cache_root = releases_root / "blobs" / "sha256"
        cache_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for record in manifest["blobs"]:
            name = record["digest"].removeprefix("sha256:")
            destination = cache_root / name
            if _blob_is_valid(destination, name, record["size"]):
                continue
            source = staging / "upload" / "layout" / "blobs" / "sha256" / name
            _cache_blob(source, destination, name, record["size"])

        with tempfile.TemporaryDirectory(prefix=".materialized-", dir=str(staging)) as temporary:
            rebuilt = Path(temporary)
            for name in LAYOUT_FILES:
                shutil.copyfile(layout / name, rebuilt / name)
                os.chmod(rebuilt / name, 0o600)
            rebuilt_blobs = rebuilt / "blobs" / "sha256"
            rebuilt_blobs.mkdir(parents=True, mode=0o700)
            for record in manifest["blobs"]:
                name = record["digest"].removeprefix("sha256:")
                os.link(cache_root / name, rebuilt_blobs / name)
            expected_refs = {image["role"]: image["archive_ref"] for image in manifest["images"]}
            validated_images, _referenced_blobs = _validate_layout_json(
                rebuilt, revision, expected_refs, require_blob_contents=True
            )
            if validated_images != manifest["images"]:
                raise TransportError("CAS 重建后的 OCI 镜像身份与 manifest 不一致")
            rebuilt_records = _blob_records(rebuilt, verify_contents=True)
            if rebuilt_records != manifest["blobs"]:
                raise TransportError("CAS 重建后的 blob 集合与 manifest 不一致")
            _build_archive(rebuilt, staging / "docker-save.tar")
    return manifest


def _release_key(revision: str, digest: str) -> str:
    require_revision(revision)
    if not DIGEST_RE.fullmatch(digest):
        raise TransportError("manifest digest 无效")
    return f"{revision}-{digest}"


def persist_release_record(
    releases_root: Path,
    revision: str,
    manifest_digest: str,
    manifest_path: Path,
    archive_path: Path,
    image_ids: Mapping[str, str],
) -> dict[str, Any]:
    key = _release_key(revision, manifest_digest)
    record_dir = releases_root / "records" / key
    record_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stored_archive = record_dir / "docker-save.tar"
    if not stored_archive.exists():
        if archive_path.stat().st_dev != record_dir.stat().st_dev:
            raise TransportError("release archive 与 retention 目录必须位于同一文件系统")
        os.link(archive_path, stored_archive)
        os.chmod(stored_archive, 0o600)
    elif sha256_path(stored_archive) != sha256_path(archive_path):
        raise TransportError("同一 release key 的 retained archive 内容冲突")
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != manifest_digest:
        raise TransportError("retained manifest digest 不匹配")
    atomic_write(record_dir / "transport-manifest.json", manifest_bytes)
    record = {
        "revision": revision,
        "manifest_sha256": manifest_digest,
        "archive_path": str(stored_archive),
        "archive_sha256": sha256_path(stored_archive),
        "archive_bytes": stored_archive.stat().st_size,
        "image_ids": dict(sorted(image_ids.items())),
    }
    atomic_write(record_dir / "record.json", canonical_json_bytes(record))
    return record


def record_load(
    staging: Path,
    releases_root: Path,
    revision: str,
    mode: str,
    digest: str,
    api_image_id: str,
    web_image_id: str,
) -> dict[str, Any]:
    manifest = load_transport_manifest(staging / "transport-manifest.json", digest, revision, mode)
    expected_ids = {image["role"]: image["image_id"] for image in manifest["images"]}
    actual_ids = {"api": api_image_id, "web": web_image_id}
    if actual_ids != expected_ids:
        raise TransportError(
            f"docker load image IDs 不匹配：expected={expected_ids} actual={actual_ids}"
        )
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "revision": revision,
        "mode": mode,
        "manifest_sha256": digest,
        "image_ids": actual_ids,
    }
    if mode == "release":
        receipt["retained"] = persist_release_record(
            releases_root,
            revision,
            digest,
            staging / "transport-manifest.json",
            staging / "docker-save.tar",
            actual_ids,
        )
    atomic_write(staging / "load-receipt.json", canonical_json_bytes(receipt))
    return receipt


def _state_path(releases_root: Path) -> Path:
    return releases_root / "state" / "retention.json"


def read_state(releases_root: Path) -> dict[str, Any]:
    path = _state_path(releases_root)
    if not path.exists():
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "generation": 0,
            "current": None,
            "previous": None,
        }
    state = read_json(path)
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise TransportError("CAS retention state schema 无效")
    return state


def has_current(releases_root: Path) -> bool:
    return read_state(releases_root).get("current") is not None


def activate_release(releases_root: Path, revision: str, digest: str) -> dict[str, Any]:
    key = _release_key(revision, digest)
    record_path = releases_root / "records" / key / "record.json"
    record = read_json(record_path)
    locks = releases_root / "locks"
    locks.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (locks / "retention.lock").open("a+b") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        state = read_state(releases_root)
        current = state.get("current")
        if (
            isinstance(current, dict)
            and current.get("revision") == revision
            and current.get("manifest_sha256") == digest
        ):
            return state
        new_state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "generation": int(state.get("generation", 0)) + 1,
            "current": record,
            "previous": current,
        }
        atomic_write(_state_path(releases_root), canonical_json_bytes(new_state))
        keep = {
            f"{item['revision']}-{item['manifest_sha256']}"
            for item in (new_state["current"], new_state["previous"])
            if isinstance(item, dict)
        }
        records_root = releases_root / "records"
        if records_root.exists():
            for child in records_root.iterdir():
                if child.is_dir() and not child.is_symlink() and child.name not in keep:
                    shutil.rmtree(child)
        return new_state


def seed_bootstrap(
    artifact: Path,
    archive: Path,
    releases_root: Path,
    revision: str,
    digest: str,
    api_image_id: str,
    web_image_id: str,
) -> dict[str, Any]:
    manifest = load_transport_manifest(
        artifact / "transport-manifest.json", digest, revision, "release"
    )
    _validate_manifest_records(manifest, artifact / "layout")
    expected_refs = {image["role"]: image["archive_ref"] for image in manifest["images"]}
    validated_images, _referenced_blobs = _validate_layout_json(
        artifact / "layout", revision, expected_refs, require_blob_contents=True
    )
    if validated_images != manifest["images"]:
        raise TransportError("bootstrap OCI 镜像身份与 manifest 不一致")
    actual_ids = {"api": api_image_id, "web": web_image_id}
    expected_ids = {image["role"]: image["image_id"] for image in manifest["images"]}
    if actual_ids != expected_ids:
        raise TransportError("bootstrap current image IDs 与 Docker save config digest 不一致")
    locks = releases_root / "locks"
    locks.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (locks / "cas.lock").open("a+b") as cache_lock:
        fcntl.flock(cache_lock, fcntl.LOCK_EX)
        cache_root = releases_root / "blobs" / "sha256"
        cache_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for record in manifest["blobs"]:
            name = record["digest"].removeprefix("sha256:")
            source = artifact / "layout" / "blobs" / "sha256" / name
            destination = cache_root / name
            if not _blob_is_valid(destination, name, record["size"]):
                file_descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{name}.", suffix=".partial", dir=str(cache_root)
                )
                os.close(file_descriptor)
                temporary = Path(temporary_name)
                try:
                    shutil.copyfile(source, temporary)
                    _cache_blob(temporary, destination, name, record["size"])
                finally:
                    if temporary.exists():
                        temporary.unlink()
    record = persist_release_record(
        releases_root,
        revision,
        digest,
        artifact / "transport-manifest.json",
        archive,
        actual_ids,
    )
    locks = releases_root / "locks"
    locks.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (locks / "retention.lock").open("a+b") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        state = read_state(releases_root)
        if state.get("current") is not None:
            return state
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "generation": 1,
            "current": record,
            "previous": None,
        }
        atomic_write(_state_path(releases_root), canonical_json_bytes(state))
        return state


def seed_cache(artifact: Path, releases_root: Path, revision: str, digest: str) -> dict[str, Any]:
    manifest = load_transport_manifest(
        artifact / "transport-manifest.json", digest, revision, "release"
    )
    _validate_manifest_records(manifest, artifact / "layout")
    expected_refs = {image["role"]: image["archive_ref"] for image in manifest["images"]}
    validated_images, _referenced_blobs = _validate_layout_json(
        artifact / "layout", revision, expected_refs, require_blob_contents=True
    )
    if validated_images != manifest["images"]:
        raise TransportError("seed OCI 镜像身份与 manifest 不一致")
    locks = releases_root / "locks"
    locks.mkdir(parents=True, exist_ok=True, mode=0o700)
    added = 0
    with (locks / "cas.lock").open("a+b") as cache_lock:
        fcntl.flock(cache_lock, fcntl.LOCK_EX)
        cache_root = releases_root / "blobs" / "sha256"
        cache_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for record in manifest["blobs"]:
            name = record["digest"].removeprefix("sha256:")
            destination = cache_root / name
            if _blob_is_valid(destination, name, record["size"]):
                continue
            source = artifact / "layout" / "blobs" / "sha256" / name
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{name}.", suffix=".partial", dir=str(cache_root)
            )
            os.close(file_descriptor)
            temporary = Path(temporary_name)
            try:
                shutil.copyfile(source, temporary)
                _cache_blob(temporary, destination, name, record["size"])
                added += 1
            finally:
                if temporary.exists():
                    temporary.unlink()
    return {"blob_count": len(manifest["blobs"]), "added": added}


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-artifact")
    build.add_argument("--archive", type=Path, required=True)
    build.add_argument("--artifact", type=Path, required=True)
    build.add_argument("--revision", required=True)
    build.add_argument("--mode", required=True)
    build.add_argument("--api-ref")
    build.add_argument("--web-ref")

    for command in ("plan", "materialize"):
        current = subparsers.add_parser(command)
        current.add_argument("--staging", type=Path, required=True)
        current.add_argument("--releases-root", type=Path, required=True)
        current.add_argument("--revision", required=True)
        current.add_argument("--mode", required=True)
        current.add_argument("--manifest-sha256", required=True)

    record = subparsers.add_parser("record-load")
    record.add_argument("--staging", type=Path, required=True)
    record.add_argument("--releases-root", type=Path, required=True)
    record.add_argument("--revision", required=True)
    record.add_argument("--mode", required=True)
    record.add_argument("--manifest-sha256", required=True)
    record.add_argument("--api-image-id", required=True)
    record.add_argument("--web-image-id", required=True)

    status = subparsers.add_parser("has-current")
    status.add_argument("--releases-root", type=Path, required=True)

    activate = subparsers.add_parser("activate")
    activate.add_argument("--releases-root", type=Path, required=True)
    activate.add_argument("--revision", required=True)
    activate.add_argument("--manifest-sha256", required=True)

    bootstrap = subparsers.add_parser("seed-bootstrap")
    bootstrap.add_argument("--artifact", type=Path, required=True)
    bootstrap.add_argument("--archive", type=Path, required=True)
    bootstrap.add_argument("--releases-root", type=Path, required=True)
    bootstrap.add_argument("--revision", required=True)
    bootstrap.add_argument("--manifest-sha256", required=True)
    bootstrap.add_argument("--api-image-id", required=True)
    bootstrap.add_argument("--web-image-id", required=True)

    seed = subparsers.add_parser("seed-cache")
    seed.add_argument("--artifact", type=Path, required=True)
    seed.add_argument("--releases-root", type=Path, required=True)
    seed.add_argument("--revision", required=True)
    seed.add_argument("--manifest-sha256", required=True)

    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "build-artifact":
            result = build_artifact(
                arguments.archive,
                arguments.artifact,
                arguments.revision,
                arguments.mode,
                arguments.api_ref,
                arguments.web_ref,
            )
        elif arguments.command == "plan":
            result = plan_transfer(
                arguments.staging,
                arguments.releases_root,
                arguments.revision,
                arguments.mode,
                arguments.manifest_sha256,
            )
        elif arguments.command == "materialize":
            result = materialize(
                arguments.staging,
                arguments.releases_root,
                arguments.revision,
                arguments.mode,
                arguments.manifest_sha256,
            )
        elif arguments.command == "record-load":
            result = record_load(
                arguments.staging,
                arguments.releases_root,
                arguments.revision,
                arguments.mode,
                arguments.manifest_sha256,
                arguments.api_image_id,
                arguments.web_image_id,
            )
        elif arguments.command == "has-current":
            return 0 if has_current(arguments.releases_root) else 1
        elif arguments.command == "activate":
            result = activate_release(
                arguments.releases_root, arguments.revision, arguments.manifest_sha256
            )
        elif arguments.command == "seed-bootstrap":
            result = seed_bootstrap(
                arguments.artifact,
                arguments.archive,
                arguments.releases_root,
                arguments.revision,
                arguments.manifest_sha256,
                arguments.api_image_id,
                arguments.web_image_id,
            )
        else:
            result = seed_cache(
                arguments.artifact,
                arguments.releases_root,
                arguments.revision,
                arguments.manifest_sha256,
            )
    except (OSError, TransportError, tarfile.TarError) as error:
        parser.exit(1, f"image transport error: {error}\n")
    _print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

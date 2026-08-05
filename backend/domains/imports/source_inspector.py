"""Read-only inspection of Spotify export files before an import.

This module deliberately does not touch the database. It gives the UI enough
information to distinguish a missing optional Account Data file from a
malformed required Streaming History file before the destructive, full import
pipeline starts.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

ACCOUNT_SOURCES: tuple[tuple[str, str, bool, str], ...] = (
    ("wrapped", "Wrapped2025.json", False, "Wrapped 年度数据"),
    ("library", "YourLibrary.json", False, "音乐库"),
    ("playlists", "Playlist1.json", False, "歌单"),
    ("search", "SearchQueries.json", False, "搜索记录"),
    ("inferences", "Inferences.json", False, "兴趣画像"),
    ("sound_capsule", "YourSoundCapsule.json", False, "Sound Capsule"),
    ("marquee", "Marquee.json", False, "推广记录"),
    ("podcast_history", "StreamingHistory_podcast_0.json", False, "播客历史"),
    ("profile", "Identity.json", False, "个人档案"),
)

_DATE_FORMATS = ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M")


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z[UTC]", "Z")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _record_items(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        return (item for item in payload if isinstance(item, dict))
    if isinstance(payload, dict):
        return (value for value in payload.values() if isinstance(value, dict))
    return ()


def _semantic_record_count(source_key: str, payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return 0
    list_keys = {
        "wrapped": ("topTracks", "topArtists", "topAlbums", "archiveReports"),
        "library": ("tracks", "albums", "artists", "shows"),
        "playlists": ("playlists",),
        "inferences": ("inferences",),
        "sound_capsule": ("highlights", "stats"),
    }
    direct_count = sum(
        len(payload.get(key, []))
        for key in list_keys.get(source_key, ())
        if isinstance(payload.get(key), list)
    )
    if direct_count:
        return direct_count

    def nested_list_count(value: Any) -> int:
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return sum(nested_list_count(item) for item in value.values())
        return 0

    return nested_list_count(payload) or (1 if payload else 0)


def record_fingerprint(item: dict[str, Any]) -> str:
    """Build the exact, deterministic identity used by preflight and import."""
    canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _inspect_file(
    path: Path,
    *,
    source_key: str,
    required: bool,
    label: str,
    streaming: bool = False,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source_key": source_key,
        "label": label,
        "file_name": path.name,
        "required": required,
        "status": "missing",
        "size_bytes": 0,
        "record_count": 0,
        "duplicate_record_count": 0,
        "first_date": None,
        "last_date": None,
        "errors": [],
        "warnings": [],
        "_content_sha256": None,
        "_record_fingerprints": set(),
    }
    if not path.exists():
        return base

    try:
        base["size_bytes"] = path.stat().st_size
    except OSError as exc:
        base["errors"].append(f"无法读取文件信息：{exc}")
        base["status"] = "invalid"
        return base

    try:
        raw = path.read_bytes()
        base["_content_sha256"] = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        base["status"] = "invalid"
        base["errors"].append(f"JSON 解析失败：{exc}")
        return base

    if streaming and not isinstance(payload, list):
        base["status"] = "invalid"
        base["errors"].append("Streaming History 顶层结构必须是数组")
        return base

    base["record_count"] = _semantic_record_count(source_key, payload)
    if base["record_count"] == 0:
        base["status"] = "empty"
        base["warnings"].append("文件可解析，但没有可用记录")
    else:
        base["status"] = "ok"

    items = list(_record_items(payload))
    if streaming:
        fingerprints = [record_fingerprint(item) for item in items]
        base["_record_fingerprints"] = set(fingerprints)
        base["duplicate_record_count"] = len(fingerprints) - len(base["_record_fingerprints"])
        timestamps = [_parse_timestamp(item.get("ts")) for item in items]
        invalid_timestamps = sum(
            1 for item, parsed in zip(items, timestamps) if item.get("ts") and parsed is None
        )
        missing_timestamp = sum(1 for item in items if not item.get("ts"))
        missing_duration = sum(1 for item in items if "ms_played" not in item)
        valid_dates = [parsed.date().isoformat() for parsed in timestamps if parsed is not None]
        base["first_date"] = min(valid_dates) if valid_dates else None
        base["last_date"] = max(valid_dates) if valid_dates else None
        if invalid_timestamps:
            base["warnings"].append(f"{invalid_timestamps} 条记录的时间戳无法解析")
        if missing_timestamp:
            base["errors"].append(f"{missing_timestamp} 条记录缺少 ts")
        if missing_duration:
            base["warnings"].append(f"{missing_duration} 条记录缺少 ms_played")
        if base["errors"]:
            base["status"] = "invalid"
    elif isinstance(payload, dict) and not items and not payload:
        base["status"] = "empty"

    return base


def _streaming_quality_findings(
    streaming_files: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return exact duplicate file groups and date-overlap evidence."""
    hashes: dict[str, list[str]] = {}
    for item in streaming_files:
        file_hash = item.get("_content_sha256")
        if file_hash and item["status"] in {"ok", "empty"}:
            hashes.setdefault(file_hash, []).append(item["file_name"])
    duplicate_file_groups = [
        {"file_names": file_names, "sha256": file_hash}
        for file_hash, file_names in hashes.items()
        if len(file_names) > 1
    ]

    date_overlaps: list[dict[str, Any]] = []
    for index, left in enumerate(streaming_files):
        if not left.get("first_date") or not left.get("last_date"):
            continue
        for right in streaming_files[index + 1 :]:
            if left["source_key"] != right["source_key"]:
                continue
            if not right.get("first_date") or not right.get("last_date"):
                continue
            overlap_start = max(left["first_date"], right["first_date"])
            overlap_end = min(left["last_date"], right["last_date"])
            if overlap_start > overlap_end:
                continue
            start = datetime.fromisoformat(overlap_start)
            end = datetime.fromisoformat(overlap_end)
            left_fingerprints = left.get("_record_fingerprints", set())
            right_fingerprints = right.get("_record_fingerprints", set())
            date_overlaps.append(
                {
                    "left_file": left["file_name"],
                    "right_file": right["file_name"],
                    "overlap_start": overlap_start,
                    "overlap_end": overlap_end,
                    "overlap_days": (end - start).days + 1,
                    "shared_record_count": len(left_fingerprints & right_fingerprints),
                }
            )
    return duplicate_file_groups, date_overlaps


def inspect_data_sources(
    streaming_dir: str | os.PathLike[str],
    account_dir: str | os.PathLike[str],
) -> dict[str, Any]:
    """Inspect the default export directories without mutating any state."""

    streaming_path = Path(streaming_dir)
    account_path = Path(account_dir)
    streaming_files: list[dict[str, Any]] = []
    for pattern, source_key, label in (
        ("Streaming_History_Audio_*.json", "streaming_audio", "音频播放历史"),
        ("Streaming_History_Video_*.json", "streaming_video", "视频播放历史"),
    ):
        for path in sorted(streaming_path.glob(pattern)):
            streaming_files.append(
                _inspect_file(
                    path,
                    source_key=source_key,
                    required=source_key == "streaming_audio",
                    label=label,
                    streaming=True,
                )
            )

    account_files = [
        _inspect_file(
            account_path / file_name,
            source_key=source_key,
            required=required,
            label=label,
        )
        for source_key, file_name, required, label in ACCOUNT_SOURCES
    ]

    duplicate_file_groups, date_overlaps = _streaming_quality_findings(streaming_files)

    blockers: list[str] = []
    warnings: list[str] = []
    audio_files = [item for item in streaming_files if item["source_key"] == "streaming_audio"]
    if not audio_files:
        blockers.append("未找到 Streaming_History_Audio_*.json")
    elif any(item["status"] == "invalid" for item in audio_files):
        blockers.append("至少一个音频播放历史文件无法解析")
    elif not any(item["record_count"] > 0 for item in audio_files):
        blockers.append("音频播放历史文件为空")

    if duplicate_file_groups:
        blockers.append(f"发现 {len(duplicate_file_groups)} 组完全重复的串流文件，导入会重复计数")

    duplicate_record_total = sum(item["duplicate_record_count"] for item in streaming_files)
    if duplicate_record_total:
        warnings.append(
            f"发现 {duplicate_record_total} 条文件内完全重复的串流记录，需核对是否应去重"
        )
    if date_overlaps:
        warnings.append(f"发现 {len(date_overlaps)} 对串流文件的日期范围重叠，需核对共同记录数")
    shared_record_total = sum(item["shared_record_count"] for item in date_overlaps)
    if shared_record_total:
        warnings.append(f"发现 {shared_record_total} 条跨文件完全重复的串流记录，可能导致重复计数")

    for item in streaming_files + account_files:
        if item["status"] == "invalid":
            (blockers if item["required"] else warnings).append(
                f"{item['file_name']}：{item['errors'][0] if item['errors'] else '文件无效'}"
            )
        elif item["status"] == "missing" and item["required"]:
            blockers.append(f"{item['file_name']}：必需文件未提供")
        elif item["status"] == "missing" and not item["required"]:
            warnings.append(f"{item['file_name']}：可选文件未提供")
        warnings.extend(f"{item['file_name']}：{warning}" for warning in item["warnings"])

    status = "blocked" if blockers else ("partial" if warnings else "healthy")
    for item in streaming_files:
        item.pop("_content_sha256", None)
        item.pop("_record_fingerprints", None)
    return {
        "status": status,
        "streaming_files": streaming_files,
        "account_files": account_files,
        "duplicate_file_groups": duplicate_file_groups,
        "date_overlaps": date_overlaps,
        "blockers": blockers,
        "warnings": warnings,
    }

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


def test_inspect_data_sources_reports_streaming_range_and_optional_files(tmp_path):
    from backend.domains.imports.source_inspector import inspect_data_sources

    streaming_dir = tmp_path / "streaming"
    account_dir = tmp_path / "account"
    streaming_dir.mkdir()
    account_dir.mkdir()
    (streaming_dir / "Streaming_History_Audio_000.json").write_text(
        json.dumps(
            [
                {"ts": "2026-01-02T01:02:03Z", "ms_played": 30_000},
                {"ts": "2026-02-03T01:02:03Z", "ms_played": 40_000},
            ]
        ),
        encoding="utf-8",
    )
    (account_dir / "YourLibrary.json").write_text(
        json.dumps({"tracks": [{"uri": "spotify:track:1"}]}),
        encoding="utf-8",
    )

    report = inspect_data_sources(streaming_dir, account_dir)

    assert report["status"] == "partial"
    audio = report["streaming_files"][0]
    assert audio["status"] == "ok"
    assert audio["record_count"] == 2
    assert audio["first_date"] == "2026-01-02"
    assert audio["last_date"] == "2026-02-03"
    library = next(item for item in report["account_files"] if item["source_key"] == "library")
    assert library["status"] == "ok"
    assert library["record_count"] == 1
    assert any("Playlist1.json" in warning for warning in report["warnings"])


def test_inspect_data_sources_blocks_invalid_required_streaming_file(tmp_path):
    from backend.domains.imports.source_inspector import inspect_data_sources

    streaming_dir = tmp_path / "streaming"
    account_dir = tmp_path / "account"
    streaming_dir.mkdir()
    account_dir.mkdir()
    (streaming_dir / "Streaming_History_Audio_000.json").write_text("{not-json", encoding="utf-8")

    report = inspect_data_sources(streaming_dir, account_dir)

    assert report["status"] == "blocked"
    assert report["streaming_files"][0]["status"] == "invalid"
    assert report["blockers"]


def test_inspect_data_sources_does_not_require_optional_account_files(tmp_path):
    from backend.domains.imports.source_inspector import inspect_data_sources

    streaming_dir = tmp_path / "streaming"
    account_dir = tmp_path / "account"
    streaming_dir.mkdir()
    account_dir.mkdir()
    (streaming_dir / "Streaming_History_Audio_000.json").write_text("[]", encoding="utf-8")

    report = inspect_data_sources(streaming_dir, account_dir)

    assert report["status"] == "blocked"
    assert any("音频播放历史文件为空" in blocker for blocker in report["blockers"])
    assert not any(
        "必需文件未提供" in blocker for blocker in report["blockers"] if "account" in blocker
    )


def test_inspect_data_sources_reports_duplicate_files_and_record_overlap(tmp_path):
    from backend.domains.imports.source_inspector import inspect_data_sources

    streaming_dir = tmp_path / "streaming"
    account_dir = tmp_path / "account"
    streaming_dir.mkdir()
    account_dir.mkdir()
    shared = {
        "ts": "2026-01-02T01:02:03Z",
        "ms_played": 30_000,
        "master_metadata_track_name": "Shared",
    }
    first = [
        {"ts": "2026-01-01T01:02:03Z", "ms_played": 30_000},
        shared,
        shared,
    ]
    second = [shared, {"ts": "2026-01-03T01:02:03Z", "ms_played": 40_000}]
    (streaming_dir / "Streaming_History_Audio_000.json").write_text(
        json.dumps(first), encoding="utf-8"
    )
    (streaming_dir / "Streaming_History_Audio_001.json").write_text(
        json.dumps(second), encoding="utf-8"
    )
    (streaming_dir / "Streaming_History_Audio_002.json").write_text(
        json.dumps(second), encoding="utf-8"
    )

    report = inspect_data_sources(streaming_dir, account_dir)

    assert report["status"] == "blocked"
    assert len(report["duplicate_file_groups"]) == 1
    assert report["duplicate_file_groups"][0]["file_names"] == [
        "Streaming_History_Audio_001.json",
        "Streaming_History_Audio_002.json",
    ]
    first_report = report["streaming_files"][0]
    assert first_report["duplicate_record_count"] == 1
    overlap = next(
        item
        for item in report["date_overlaps"]
        if item["left_file"] == "Streaming_History_Audio_000.json"
        and item["right_file"] == "Streaming_History_Audio_001.json"
    )
    assert overlap["overlap_start"] == "2026-01-02"
    assert overlap["overlap_end"] == "2026-01-02"
    assert overlap["shared_record_count"] == 1
    assert any("跨文件完全重复" in warning for warning in report["warnings"])

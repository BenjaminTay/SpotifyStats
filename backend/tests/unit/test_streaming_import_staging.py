from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _streaming_dir(tmp_path: Path) -> Path:
    source = tmp_path / "streaming"
    source.mkdir(parents=True)
    (source / "Streaming_History_Audio_000.json").write_text(
        json.dumps(
            [
                {"ts": "2026-01-01T00:00:00Z", "ms_played": 30_000},
                {"ts": "2026-01-02T00:00:00Z", "ms_played": 40_000},
            ]
        ),
        encoding="utf-8",
    )
    return source


def test_staging_is_private_temporary_and_close_removes_it(tmp_path):
    from backend.domains.imports.streaming_staging import StreamingImportStaging

    source = _streaming_dir(tmp_path)
    staging = StreamingImportStaging.build(source)
    staging_dir = staging.temp_dir

    assert staging_dir != source
    assert staging.database_path.is_file()
    assert staging.record_count() == 2
    assert [record["ts"] for _, record in staging.iter_records("audio")] == [
        "2026-01-01T00:00:00Z",
        "2026-01-02T00:00:00Z",
    ]
    per_file = staging.records_for_file(source / "Streaming_History_Audio_000.json")
    assert iter(per_file) is per_file
    assert [record["ms_played"] for record in per_file] == [30_000, 40_000]

    staging.close()

    assert not staging_dir.exists()


def test_staging_streams_large_array_in_bounded_insert_batches(tmp_path, monkeypatch):
    from backend.domains.imports import streaming_staging as staging_mod

    source = tmp_path / "streaming"
    source.mkdir()
    records = [
        {
            "ts": f"2026-01-{(index % 28) + 1:02d}T00:00:00Z",
            "ms_played": index,
            "label": f"Unicode 歌曲 {index}",
        }
        for index in range(2505)
    ]
    (source / "Streaming_History_Audio_000.json").write_text(
        json.dumps(records, ensure_ascii=False),
        encoding="utf-8",
    )

    def forbid_read_bytes(_path):
        raise AssertionError("staging must not retain the complete source bytes")

    monkeypatch.setattr(Path, "read_bytes", forbid_read_bytes)
    staging = staging_mod.StreamingImportStaging.build(source)
    try:
        assert staging.record_count() == 2505
        assert [item[1]["label"] for item in staging.iter_records("audio")][-1] == (
            "Unicode 歌曲 2504"
        )
    finally:
        staging.close()


def test_orphan_cleanup_only_removes_old_private_owned_staging(tmp_path, monkeypatch):
    from backend.domains.imports import streaming_staging as staging_mod

    now = 2_000_000.0

    def directory(name: str, *, mode: int = 0o700, age: float = 100_000) -> Path:
        path = tmp_path / name
        path.mkdir(mode=mode)
        (path / "staging.sqlite3").write_bytes(b"disposable")
        os.chmod(path, mode)
        os.utime(path, (now - age, now - age))
        return path

    old_private = directory("spotifystats-streaming-import-old")
    young = directory("spotifystats-streaming-import-young", age=60)
    permissive = directory("spotifystats-streaming-import-permissive", mode=0o755)
    unrelated = directory("some-other-prefix")
    symlink = tmp_path / "spotifystats-streaming-import-link"
    symlink.symlink_to(old_private, target_is_directory=True)

    monkeypatch.setattr(staging_mod.os, "getuid", lambda: old_private.stat().st_uid)
    removed = staging_mod.cleanup_orphaned_stagings(
        temp_root=tmp_path,
        now=now,
        min_age_seconds=3600,
    )

    assert removed == (old_private,)
    assert not old_private.exists()
    assert young.is_dir()
    assert permissive.is_dir()
    assert unrelated.is_dir()
    assert symlink.is_symlink()


def test_orphan_cleanup_leaves_directory_owned_by_another_uid(tmp_path, monkeypatch):
    from backend.domains.imports import streaming_staging as staging_mod

    orphan = tmp_path / "spotifystats-streaming-import-foreign"
    orphan.mkdir(mode=0o700)
    os.chmod(orphan, 0o700)
    os.utime(orphan, (1.0, 1.0))
    monkeypatch.setattr(staging_mod.os, "getuid", lambda: orphan.stat().st_uid + 1)

    removed = staging_mod.cleanup_orphaned_stagings(
        temp_root=tmp_path,
        now=100_000.0,
        min_age_seconds=3600,
    )

    assert removed == ()
    assert orphan.is_dir()


def test_first_staging_build_runs_orphan_cleanup_once(tmp_path, monkeypatch):
    from backend.domains.imports import streaming_staging as staging_mod

    calls = 0

    def fake_cleanup(**_kwargs):
        nonlocal calls
        calls += 1
        return ()

    monkeypatch.setattr(staging_mod, "cleanup_orphaned_stagings", fake_cleanup)
    monkeypatch.setattr(staging_mod, "_orphan_cleanup_done", False)
    first = staging_mod.StreamingImportStaging.build(_streaming_dir(tmp_path / "first"))
    second = staging_mod.StreamingImportStaging.build(_streaming_dir(tmp_path / "second"))
    try:
        assert calls == 1
    finally:
        first.close()
        second.close()


@pytest.mark.parametrize(
    "payload, expected_error",
    [
        ('{"not":"an array"}', "顶层结构必须是数组"),
        ('[{"ts":"2026-01-01T00:00:00Z"},]', "末尾不能有多余逗号"),
        ('[{"ts":"2026-01-01T00:00:00Z"}', "未完整结束"),
    ],
)
def test_staging_marks_invalid_streamed_json_without_partial_records(
    tmp_path, payload, expected_error
):
    from backend.domains.imports.streaming_staging import StreamingImportStaging

    source = tmp_path / "streaming"
    source.mkdir()
    (source / "Streaming_History_Audio_000.json").write_text(payload, encoding="utf-8")

    staging = StreamingImportStaging.build(source)
    try:
        row = staging.inspection_rows()[0]
        assert row["status"] == "invalid"
        assert expected_error in row["error"]
        assert staging.record_count() == 0
    finally:
        staging.close()


def test_staging_manifest_rejects_changed_or_added_source_files(tmp_path):
    from backend.domains.imports.streaming_staging import StreamingImportStaging

    source = _streaming_dir(tmp_path)
    staging = StreamingImportStaging.build(source)
    try:
        original = source / "Streaming_History_Audio_000.json"
        original.write_text(
            json.dumps([{"ts": "2026-01-03T00:00:00Z", "ms_played": 50_000}]),
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="changed after staging"):
            staging.verify_source_manifest()

        original.write_text(
            json.dumps(
                [
                    {"ts": "2026-01-01T00:00:00Z", "ms_played": 30_000},
                    {"ts": "2026-01-02T00:00:00Z", "ms_played": 40_000},
                ]
            ),
            encoding="utf-8",
        )
        # Even when original bytes return, a newly added matching source must
        # invalidate the confirmation-bound manifest.
        (source / "Streaming_History_Audio_001.json").write_text("[]", encoding="utf-8")
        with pytest.raises(RuntimeError, match="file set changed"):
            staging.verify_source_manifest()
    finally:
        staging.close()


def test_planning_and_import_can_share_staging_without_json_load(tmp_path, monkeypatch):
    from backend.core import import_data as import_mod
    from backend.domains.imports.streaming_staging import StreamingImportStaging
    from backend.services.import_plan_service import assess_streaming_import

    source = _streaming_dir(tmp_path)
    account = tmp_path / "account"
    account.mkdir()
    staging = StreamingImportStaging.build(source)
    assessment = assess_streaming_import(
        source,
        account,
        staging=staging,
        retain_staging=True,
    )
    assert assessment.report["incoming_record_count"] == 2

    def unexpected_json_load(*args, **kwargs):
        raise AssertionError("staged import must not json.load source files")

    monkeypatch.setattr(import_mod.json, "load", unexpected_json_load)
    monkeypatch.setattr(import_mod, "init_db", lambda: None)
    monkeypatch.setattr(import_mod, "_prepare_replace_schema", lambda: None)

    # The full ETL database behavior is covered by test_import_data_flow.  This
    # focused assertion proves the staged path reaches DB setup without the old
    # pre-count/source-file json.load passes.
    def stop_before_database(*args, **kwargs):
        raise RuntimeError("database boundary reached")

    monkeypatch.setattr(import_mod, "get_db", stop_before_database)
    try:
        with pytest.raises(RuntimeError, match="database boundary reached"):
            import_mod.import_data(str(source), staging=staging)
    finally:
        staging.close()


def test_confirmation_cache_transfers_ownership_and_cleanup(tmp_path):
    from backend.domains.imports.streaming_staging import (
        StreamingImportStaging,
        cache_staging,
        take_cached_staging,
    )

    staging = StreamingImportStaging.build(_streaming_dir(tmp_path))
    temp_dir = staging.temp_dir
    cache_staging("token", staging)

    claimed = take_cached_staging("token")
    assert claimed is staging
    assert take_cached_staging("token") is None

    claimed.close()
    assert not temp_dir.exists()


def test_staged_import_preserves_etl_result_and_rechecks_manifest(tmp_path, monkeypatch):
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod
    from backend.domains.imports.streaming_staging import StreamingImportStaging

    source = _streaming_dir(tmp_path)
    database = tmp_path / "spotify-staged.db"
    monkeypatch.setattr(db_mod, "DB_PATH", str(database))
    staging = StreamingImportStaging.build(source)
    verify_calls = 0
    original_verify = staging.verify_source_manifest

    def counting_verify() -> None:
        nonlocal verify_calls
        verify_calls += 1
        original_verify()

    monkeypatch.setattr(staging, "verify_source_manifest", counting_verify)
    try:
        result = import_mod.import_data(
            str(source),
            staging=staging,
            build_preaggregations=False,
            generation_id="staged-generation",
        )
        assert result["inserted_records"] == 2
        assert result["active_records"] == 2
        assert result["generation_id"] == "staged-generation"
        assert verify_calls == 2

        changed = StreamingImportStaging.build(source)
        try:
            (source / "Streaming_History_Audio_000.json").write_text("[]", encoding="utf-8")
            with pytest.raises(RuntimeError, match="changed after staging"):
                import_mod.import_data(
                    str(source),
                    staging=changed,
                    build_preaggregations=False,
                )
        finally:
            changed.close()
    finally:
        staging.close()
        db_mod._load_plays_cached.cache_clear()
        db_mod._load_plays_for_artists_cached.cache_clear()

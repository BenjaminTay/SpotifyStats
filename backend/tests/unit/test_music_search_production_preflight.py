from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from scripts.rebuild_music_search_derived_data import _success_report

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
PRODUCTION = ROOT / "deploy" / "production"
BUILDER_VERSION = "music_search_snapshot_v2"
VARIANTS = ((2, True), (1, True), (3, True), (2, False), (1, False), (3, False))


def _build_preflight_fixture(
    tmp_path: Path,
    *,
    orphan: bool = False,
    wrong_fingerprint: bool = False,
) -> tuple[Path, Path, Path]:
    database = tmp_path / "preflight-copy.db"
    conn = sqlite3.connect(database)
    conn.executescript(
        """
        CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE music_search_snapshot_meta(
            snapshot_key TEXT PRIMARY KEY,
            filter_fingerprint TEXT NOT NULL,
            semantic_base_key TEXT,
            merge_level INTEGER,
            dynamic_threshold INTEGER,
            status TEXT,
            builder_version TEXT
        );
        CREATE TABLE music_search_entity_context(
            snapshot_key TEXT NOT NULL,
            entity_key TEXT NOT NULL
        );
        """
    )
    conn.executemany(
        "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
        (
            (35, "search identity split"),
            (36, "search candidate ngram index"),
        ),
    )
    for index, (merge_level, dynamic_threshold) in enumerate(VARIANTS):
        snapshot_key = f"snapshot-{index}"
        fingerprint = f"fingerprint-{index}"
        database_fingerprint = (
            "wrong-fingerprint" if wrong_fingerprint and index == 0 else fingerprint
        )
        conn.execute(
            """INSERT INTO music_search_snapshot_meta(
                   snapshot_key, filter_fingerprint, semantic_base_key, merge_level,
                   dynamic_threshold, status, builder_version
               ) VALUES (?, ?, 'semantic-base', ?, ?, 'ready', ?)""",
            (
                snapshot_key,
                database_fingerprint,
                merge_level,
                int(dynamic_threshold),
                BUILDER_VERSION,
            ),
        )
        conn.execute(
            "INSERT INTO music_search_entity_context(snapshot_key, entity_key) VALUES (?, ?)",
            (snapshot_key, f"track:{index}"),
        )
    if orphan:
        conn.execute(
            "INSERT INTO music_search_entity_context(snapshot_key, entity_key) "
            "VALUES ('missing-snapshot', 'track:orphan')"
        )
    conn.commit()
    conn.close()

    rebuild_report = tmp_path / "rebuild.json"
    raw_report = {
        "index": {"status": "ready"},
        "snapshot_set": {
            "status": "ready",
            "semantic_base_key": "semantic-base",
            "ready_count": 6,
            "failed_count": 0,
            "duration_ms": 1.0,
            "variants": [
                {
                    "merge_level": merge_level,
                    "dynamic_threshold": dynamic_threshold,
                    "status": "ready",
                    "builder_version": BUILDER_VERSION,
                    "filter_fingerprint": f"fingerprint-{index}",
                    "entity_count": 1,
                    "duration_ms": 0.1,
                }
                for index, (merge_level, dynamic_threshold) in enumerate(VARIANTS)
            ],
        },
    }
    report = _success_report(
        raw_report,
        require_all_ready=True,
        prior_inventory={},
        base_counts={
            "row_count": 6,
            "unique_fingerprint_count": 6,
            "duplicate_fingerprint_count": 0,
        },
        migration={
            "applied_version": 36,
            "target_version": 36,
            "applied_count": 36,
            "expected_count": 36,
            "missing_count": 0,
            "up_to_date": True,
        },
        elapsed_ms=2.0,
        storage={
            "before": {"database_bytes": 1, "wal_bytes": 0, "combined_bytes": 1},
            "after": {"database_bytes": 2, "wal_bytes": 0, "combined_bytes": 2},
            "delta": {"database_bytes": 1, "wal_bytes": 0, "combined_bytes": 1},
        },
    )
    rebuild_report.write_text(
        json.dumps(report),
        encoding="utf-8",
    )
    capacity_report = tmp_path / "capacity.json"
    capacity_report.write_text(
        json.dumps(
            {
                "requirements": {
                    "minimum_available_memory_mib": 2560,
                    "required_disk_bytes_before": 1024**3,
                    "required_disk_bytes_after": 1024**3,
                },
                "before": {
                    "available_memory_bytes": 4 * 1024**3,
                    "available_disk_bytes": 8 * 1024**3,
                },
                "after": {
                    "available_memory_bytes": 3 * 1024**3,
                    "available_disk_bytes": 7 * 1024**3,
                },
                "passed": True,
            }
        ),
        encoding="utf-8",
    )
    return database, rebuild_report, capacity_report


def test_preflight_validator_requires_migration_variants_builder_and_zero_orphans(
    tmp_path: Path,
) -> None:
    database, rebuild_report, capacity_report = _build_preflight_fixture(tmp_path)
    output = tmp_path / "validated.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(PRODUCTION / "validate-music-search-preflight.py"),
            "--db-path",
            str(database),
            "--rebuild-report",
            str(rebuild_report),
            "--capacity-report",
            str(capacity_report),
            "--json-output",
            str(output),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "ready"
    assert "snapshot_set" not in payload
    assert payload["gate"]["all_six_ready"] is True
    assert payload["host_capacity"]["passed"] is True
    assert payload["production_validation"] == {
        "builder_version": BUILDER_VERSION,
        "context_orphan_count": 0,
        "integrity_check": "ok",
        "migration_36": True,
        "ready_variants": 6,
        "required_variants": 6,
    }


def test_preflight_validator_fails_on_context_orphan(tmp_path: Path) -> None:
    database, rebuild_report, capacity_report = _build_preflight_fixture(tmp_path, orphan=True)
    output = tmp_path / "invalid.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(PRODUCTION / "validate-music-search-preflight.py"),
            "--db-path",
            str(database),
            "--rebuild-report",
            str(rebuild_report),
            "--capacity-report",
            str(capacity_report),
            "--json-output",
            str(output),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 1
    assert "context orphan count is not zero" in completed.stderr
    assert not output.exists()


def test_preflight_validator_fails_on_current_fingerprint_mismatch(tmp_path: Path) -> None:
    database, rebuild_report, capacity_report = _build_preflight_fixture(
        tmp_path, wrong_fingerprint=True
    )
    output = tmp_path / "invalid-fingerprint.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(PRODUCTION / "validate-music-search-preflight.py"),
            "--db-path",
            str(database),
            "--rebuild-report",
            str(rebuild_report),
            "--capacity-report",
            str(capacity_report),
            "--json-output",
            str(output),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 1
    assert "fingerprints do not match" in completed.stderr
    assert not output.exists()


def test_capacity_helpers_use_memavailable_and_four_database_copies() -> None:
    module_path = PRODUCTION / "music_search_preflight_capacity.py"
    spec = importlib.util.spec_from_file_location("music_search_preflight_capacity", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.parse_mem_available_bytes("MemTotal: 1 kB\nMemAvailable: 2621440 kB\n") == (
        2560 * 1024 * 1024
    )
    assert module.required_disk_bytes(10) == 1024**3
    assert module.required_disk_bytes(512 * 1024**2) == 2 * 1024**3


def test_capacity_helper_can_parse_macos_vm_stat() -> None:
    module_path = PRODUCTION / "music_search_preflight_capacity.py"
    spec = importlib.util.spec_from_file_location("music_search_preflight_capacity", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    vm_stat = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free: 100.
Pages inactive: 200.
Pages speculative: 30.
Pages purgeable: 20.
Pages active: 999.
"""
    assert module.parse_vm_stat_available_bytes(vm_stat) == 350 * 16384


def test_preflight_shell_requires_explicit_resolved_copy_and_never_targets_live_data(
    tmp_path: Path,
) -> None:
    deployment = tmp_path / "production"
    deployment.mkdir()
    script = deployment / "preflight-music-search.sh"
    shutil.copy2(PRODUCTION / "preflight-music-search.sh", script)
    script.chmod(0o700)

    missing = subprocess.run(
        [
            str(script),
            "--db-copy",
            str(tmp_path / "missing.db"),
            "--json-report",
            str(tmp_path / "report.json"),
            "--image",
            "registry.invalid/backend:abc1234",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert missing.returncode == 2
    assert "路径无法完整解析" in missing.stderr

    live_data = deployment / "data"
    live_data.mkdir()
    live_database = live_data / "spotify_stats.db"
    live_database.write_bytes(b"not-opened-before-safety-check")
    live = subprocess.run(
        [
            str(script),
            "--db-copy",
            str(live_database),
            "--json-report",
            str(tmp_path / "report.json"),
            "--image",
            "registry.invalid/backend:abc1234",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert live.returncode == 2
    assert "真实数据库" in live.stderr


def test_production_deploy_stages_search_before_atomic_database_promotion() -> None:
    deploy = (PRODUCTION / "deploy.sh").read_text(encoding="utf-8")
    preflight = (PRODUCTION / "preflight-music-search.sh").read_text(encoding="utf-8")
    verify = (PRODUCTION / "verify.sh").read_text(encoding="utf-8")
    runtime_gate = (PRODUCTION / "verify-music-search-runtime.py").read_text(encoding="utf-8")

    assert "pull_mode_for_tag" in deploy
    assert "SPOTIFY_STATS_BACKUP_NAME" in deploy
    assert 'preflight-music-search.sh"' in deploy
    assert "compose_all stop backend" in deploy
    assert "cmp -s" in deploy
    assert "rebase_music_search_preflight.py" in deploy
    assert "生产数据库仅发生非搜索写入" in deploy
    assert "replace_live_database" in deploy
    assert "database_promoted" in deploy
    assert "正在恢复发布前 SQLite 备份" in deploy
    release_flow = deploy.split('backend_was_running="false"', 1)[1]
    assert release_flow.index('preflight-music-search.sh"') < release_flow.index(
        "compose_all stop backend"
    )
    assert release_flow.index("compose_all stop backend") < release_flow.index(
        'replace_live_database "$staged_database"'
    )

    assert "--require-all-ready" in preflight
    assert "--statistics-reuse-only" in preflight
    assert "SPOTIFY_STATS_SEARCH_STARTUP_REBUILD=0" in preflight
    assert "--db-copy" in preflight
    assert '"$production_data_dir"/*' in preflight
    assert "SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB" in preflight
    assert "--phase before" in preflight
    assert "--phase after" in preflight
    assert '--name "$container_name"' in preflight
    assert "prepare_music_search_resume.py" in preflight
    assert "音乐搜索续建副本判定" in preflight
    assert "ready_snapshot_rows" in preflight
    assert "--resume-db" in deploy
    assert "检测到仍在运行的音乐搜索副本重建容器" in preflight
    assert "音乐搜索候选维护与统计复用校验仍在运行" in preflight
    assert "音乐搜索预检失败摘要" in preflight
    assert "error.get('stage')" in preflight
    assert "error.get('type')" in preflight
    assert "error.get('message')" not in preflight
    assert "trap terminate HUP INT TERM" in preflight
    assert 'sudo chown -- "$host_uid:$host_gid" "$resume_db_path"' in preflight
    assert '! -r "$resume_db_path" || ! -w "$resume_db_path"' in preflight
    assert preflight.count('--user "$host_uid:$host_gid"') == 2
    assert '[[ -L "$resume_db_path" ]]' in preflight
    assert "verify-music-search-runtime.py" in verify
    assert "version=36" in runtime_gate
    assert "filter_fingerprint" in runtime_gate
    assert "context orphan count is not zero" in runtime_gate


def test_production_compose_and_workflow_ship_search_release_gates() -> None:
    compose = yaml.safe_load((PRODUCTION / "compose.yml").read_text(encoding="utf-8"))
    environment = compose["services"]["backend"]["environment"]
    assert environment["SPOTIFY_STATS_SEARCH_STARTUP_REBUILD"] == (
        "${SPOTIFY_STATS_SEARCH_STARTUP_REBUILD:-1}"
    )
    env_template = (PRODUCTION / ".env.example").read_text(encoding="utf-8")
    assert "SPOTIFY_STATS_SEARCH_STARTUP_REBUILD=1" in env_template
    assert "SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB=1280" in env_template

    workflow = (ROOT / ".github" / "workflows" / "deploy-production.yml").read_text(
        encoding="utf-8"
    )
    assert "timeout-minutes: 35" in workflow
    assert "preflight-music-search.sh" in workflow
    assert "validate-music-search-preflight.py" in workflow
    assert "music_search_preflight_capacity.py" in workflow
    assert "verify-music-search-runtime.py" in workflow


def test_one_time_statistics_bootstrap_is_manual_resumable_and_never_deploys() -> None:
    bootstrap = (PRODUCTION / "bootstrap-music-search-statistics.sh").read_text(encoding="utf-8")
    helper = (PRODUCTION / "prepare-music-search-bootstrap-resume.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "bootstrap-production-music-search.yml").read_text(
        encoding="utf-8"
    )
    production_workflow = (ROOT / ".github" / "workflows" / "deploy-production.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "push:" not in workflow
    assert "timeout-minutes: 45" in workflow
    assert "timeout --signal=TERM --kill-after=30s 38m" in workflow
    assert "docker ps --no-trunc" in workflow
    assert "cmp --silent" in workflow
    assert "retention-days: 1" in workflow
    assert "bootstrap-production-music-search.yml" in production_workflow
    assert "bootstrap-music-search-statistics.sh" in production_workflow
    assert "prepare-music-search-bootstrap-resume.py" in production_workflow

    assert "source.backup(target)" in bootstrap
    assert "--require-all-ready" in bootstrap
    assert "--statistics-reuse-only" not in bootstrap
    assert "compose_all stop" not in bootstrap
    assert "replace_live_database" not in bootstrap
    assert "deploy.sh" not in bootstrap
    assert "music-search-resume.db" in bootstrap
    assert "同源部分成果" in bootstrap
    assert "src=$DEPLOY_DIR,dst=/bootstrap" not in bootstrap
    assert "src=$PREPARE_HELPER" in bootstrap
    assert 'sudo chown -- "$host_uid:$host_gid" "$baseline_path"' in bootstrap
    assert bootstrap.count('--user "$host_uid:$host_gid"') == 2
    assert "source_equivalent_partial_statistics_resume" in helper
    assert "ALLOWED_PARTIAL_STATUSES" in helper

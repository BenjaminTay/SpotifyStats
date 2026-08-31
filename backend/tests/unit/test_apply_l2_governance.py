from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core import db as db_mod
from backend.domains.music_search.context import MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
from backend.domains.music_search.year_end_projection import (
    YEAR_END_PROJECTION_BUILDER_VERSION,
)
from backend.domains.playback.album_composition_auto_merge import (
    ALBUM_COMPOSITION_POLICY_VERSION,
    AlbumCompositionApplyReport,
)
from backend.domains.playback.album_project_auto_merge import (
    AlbumProjectAutoMergeApplyReport,
)
from scripts import apply_l2_governance as governance

pytestmark = pytest.mark.unit


def _create_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO schema_migrations VALUES (67, 'fixture');
            CREATE TABLE plays(
                play_id INTEGER PRIMARY KEY,
                track_id INTEGER NOT NULL,
                ms_played INTEGER NOT NULL
            );
            CREATE TABLE tracks(
                track_id INTEGER PRIMARY KEY,
                track_name TEXT NOT NULL
            );
            CREATE TABLE track_artists(
                track_id INTEGER NOT NULL,
                artist_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                PRIMARY KEY(track_id, artist_id, role)
            );
            INSERT INTO tracks VALUES (1, 'Song'), (2, 'Song');
            INSERT INTO plays VALUES (1, 1, 180000);
            INSERT INTO track_artists VALUES (1, 1, 'primary'), (2, 1, 'primary');

            CREATE TABLE track_identity_state(
                state_id INTEGER PRIMARY KEY,
                current_revision INTEGER NOT NULL,
                policy_version TEXT NOT NULL,
                updated_at TEXT
            );
            INSERT INTO track_identity_state VALUES (1, 5, 'fixture', datetime('now'));
            CREATE TABLE album_project_revision_state(
                state_id INTEGER PRIMARY KEY,
                current_revision INTEGER NOT NULL,
                updated_at TEXT
            );
            INSERT INTO album_project_revision_state VALUES (1, 2, datetime('now'));
            CREATE TABLE track_l1_identities(
                l1_id INTEGER PRIMARY KEY,
                fallback_track_id INTEGER,
                identity_status TEXT NOT NULL,
                representative_track_id INTEGER
            );
            INSERT INTO track_l1_identities VALUES
                (1, 1, 'active', 1), (2, 2, 'active', 2);
            CREATE TABLE track_l1_external_ids(
                provider TEXT NOT NULL,
                external_track_id TEXT NOT NULL,
                l1_id INTEGER NOT NULL,
                evidence_type TEXT NOT NULL,
                is_primary INTEGER NOT NULL,
                PRIMARY KEY(provider, external_track_id)
            );
            INSERT INTO track_l1_external_ids VALUES
                ('spotify', 'base', 1, 'provider_observed', 1),
                ('spotify', 'variant', 1, 'provider_observed', 0);
            CREATE TABLE spotify_track_owners(
                spotify_track_id TEXT PRIMARY KEY,
                track_id INTEGER NOT NULL,
                evidence_type TEXT NOT NULL
            );
            INSERT INTO spotify_track_owners VALUES
                ('base', 1, 'import_match'), ('variant', 1, 'import_match');
            CREATE TABLE track_l1_source_links(
                l1_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                evidence_type TEXT NOT NULL,
                observed_plays INTEGER NOT NULL,
                PRIMARY KEY(l1_id, track_id, evidence_type)
            );
            INSERT INTO track_l1_source_links VALUES
                (1, 1, 'track_projection', 0),
                (1, 2, 'track_projection', 0);

            CREATE TABLE track_groups(
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL,
                primary_track_id INTEGER,
                primary_l1_id INTEGER,
                scope TEXT NOT NULL,
                parent_group_id INTEGER,
                is_manual INTEGER NOT NULL,
                group_status TEXT NOT NULL,
                automatic_spotify_track_id TEXT,
                automatic_artist_id INTEGER,
                automatic_title_key TEXT,
                automatic_version_tag TEXT,
                identity_policy_version TEXT
            );
            CREATE TABLE track_group_l1_members(
                group_id INTEGER NOT NULL,
                l1_id INTEGER NOT NULL,
                PRIMARY KEY(group_id, l1_id)
            );
            CREATE TABLE track_group_candidates(
                candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                original_l1_id INTEGER NOT NULL,
                candidate_l1_id INTEGER NOT NULL,
                confidence REAL,
                evidence_json TEXT NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(scope, original_l1_id, candidate_l1_id)
            );

            CREATE TABLE release_groups(
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL,
                artist_id INTEGER,
                primary_album_id INTEGER,
                scope TEXT NOT NULL,
                parent_group_id INTEGER,
                is_manual INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE release_group_members(group_id INTEGER, album_id INTEGER);

            CREATE TABLE album_projects(
                project_id INTEGER PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                primary_album_id INTEGER,
                scope TEXT,
                project_type TEXT,
                identity_policy_version TEXT
            );
            CREATE TABLE album_project_albums(project_id INTEGER, album_id INTEGER);
            CREATE TABLE album_project_external_ids(
                provider TEXT,
                external_album_id TEXT,
                project_id INTEGER,
                evidence_type TEXT,
                confidence REAL,
                is_primary INTEGER
            );

            CREATE TABLE version_governance_runs(
                run_id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                status TEXT NOT NULL,
                dry_run INTEGER NOT NULL,
                summary_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            );
            CREATE TABLE version_governance_events(
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                action TEXT NOT NULL,
                survivor_id INTEGER,
                affected_ids_json TEXT NOT NULL,
                before_json TEXT NOT NULL,
                after_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL
            );

            CREATE TABLE music_search_snapshot_variant_state(
                merge_level INTEGER,
                dynamic_threshold INTEGER,
                active_snapshot_key TEXT,
                active_filter_fingerprint TEXT,
                target_filter_fingerprint TEXT,
                maintenance_status TEXT
            );
            CREATE TABLE music_search_snapshot_meta(
                snapshot_key TEXT PRIMARY KEY,
                filter_fingerprint TEXT,
                status TEXT,
                builder_version TEXT
            );
            CREATE TABLE music_search_entity_context(
                snapshot_key TEXT,
                entity_key TEXT
            );
            CREATE TABLE music_search_year_end_projection_state(
                snapshot_key TEXT PRIMARY KEY,
                builder_version TEXT,
                status TEXT
            );
            CREATE TABLE music_search_year_end_meta(snapshot_key TEXT, year INTEGER);
            CREATE TABLE music_search_entity_year_end(snapshot_key TEXT, entity_key TEXT);
            """
        )
        for merge_level, dynamic_threshold in sorted(governance.EXPECTED_SEARCH_VARIANTS):
            key = f"snapshot-{merge_level}-{dynamic_threshold}"
            conn.execute(
                "INSERT INTO music_search_snapshot_variant_state VALUES (?, ?, ?, ?, ?, 'ready')",
                (merge_level, dynamic_threshold, key, key, key),
            )
            conn.execute(
                "INSERT INTO music_search_snapshot_meta VALUES (?, ?, 'ready', ?)",
                (key, key, MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION),
            )
            conn.execute("INSERT INTO music_search_entity_context VALUES (?, 'track:1')", (key,))
            conn.execute(
                "INSERT INTO music_search_year_end_projection_state VALUES (?, ?, 'ready')",
                (key, YEAR_END_PROJECTION_BUILDER_VERSION),
            )
            conn.execute("INSERT INTO music_search_year_end_meta VALUES (?, 2026)", (key,))
            conn.execute("INSERT INTO music_search_entity_year_end VALUES (?, 'track:1')", (key,))
        conn.commit()
    finally:
        conn.close()


def _args(path: Path, backup_dir: Path, *, skip_derived: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        db_path=path,
        backup_dir=backup_dir,
        skip_l1_safe_splits=False,
        skip_derived_rebuild=skip_derived,
    )


def _operation() -> dict:
    return {
        "operation": "reassign_external_identity",
        "source_l1_id": 1,
        "target_l1_id": 2,
        "provider": "spotify",
        "external_track_id": "variant",
        "reason": "fixture split",
        "preconditions": {"local_projection_track_ids": [2]},
    }


def _l1_plan() -> dict:
    return {
        "confirmation_token": "confirmed",
        "operations": [_operation()],
        "summary": {"auto_split_operation_count": 1},
    }


def _track_plan() -> dict:
    return {
        "policy_version": "fixture-l2",
        "changed": True,
        "groups_to_create": 1,
        "groups_to_update": 0,
        "groups_to_archive": 0,
        "archived_group_ids": [],
        "accepted_edges": [
            {
                "left_l1_id": 1,
                "right_l1_id": 2,
                "evidence_type": "canonical_artist_normalized_title",
                "confidence": 1.0,
            }
        ],
        "blocked_edges": [],
        "groups": [
            {
                "action": "create",
                "target_group_id": None,
                "member_l1_ids": [1, 2],
                "primary_l1_id": 1,
                "primary_track_id": 1,
                "canonical_name": "Song",
                "artist_ids": [1],
                "normalized_title": "song",
                "semantic_version_tags": [],
                "evidence_types": ["canonical_artist_normalized_title"],
            }
        ],
    }


def _ready_report(*, projection_status: str = "ready") -> dict:
    variants = []
    projections = []
    for merge_level, dynamic_threshold in sorted(governance.EXPECTED_SEARCH_VARIANTS):
        key = f"snapshot-{merge_level}-{dynamic_threshold}"
        variants.append(
            {
                "status": "ready",
                "snapshot_key": key,
                "merge_level": merge_level,
                "dynamic_threshold": bool(dynamic_threshold),
            }
        )
        projections.append({"status": projection_status, "snapshot_key": key})
    projection = {
        "status": projection_status,
        "ready_count": 4 if projection_status == "ready" else 0,
        "failed_count": 0 if projection_status == "ready" else 4,
        "variants": projections,
    }
    snapshots = {
        "status": "ready",
        "ready_count": 4,
        "failed_count": 0,
        "variants": variants,
        "year_end_projection": projection,
    }
    return {
        "status": "ready",
        "snapshot_set": snapshots,
        "year_end_projection": projection,
    }


def _empty_album_report() -> AlbumProjectAutoMergeApplyReport:
    return AlbumProjectAutoMergeApplyReport(
        candidate_count=0,
        groups_created=0,
        projects_merged=0,
        albums_merged=0,
        release_group_ids=(),
        album_project_revision=2,
        requires_downstream_refresh=False,
    )


def _empty_album_composition_report() -> AlbumCompositionApplyReport:
    return AlbumCompositionApplyReport(
        candidate_count=0,
        groups_created=0,
        groups_updated=0,
        groups_archived=0,
        release_children_created=0,
        unchanged_groups=0,
        album_project_revision=2,
        requires_downstream_refresh=False,
    )


def _patch_successful_relations(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[bool]]:
    calls: dict[str, list[bool]] = {"l1_bump": [], "l2_bump": [], "l3_bump": []}
    monkeypatch.setattr(governance, "run_migrations", lambda: None)
    monkeypatch.setattr(
        governance,
        "validate_track_identity_invariants",
        lambda _conn: SimpleNamespace(healthy=True, issue_count=0),
    )

    def build_l1(conn, *_args, **_kwargs):
        owner = conn.execute(
            "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id='variant'"
        ).fetchone()
        if owner is not None and int(owner[0]) == 1:
            return _l1_plan()
        return {
            "confirmation_token": "settled",
            "operations": [],
            "summary": {"auto_split_operation_count": 0},
        }

    monkeypatch.setattr(governance, "build_l1_external_identity_risk_plan", build_l1)

    def apply_l1(conn, _token, *, bump_revision=True):
        calls["l1_bump"].append(bool(bump_revision))
        conn.execute(
            "UPDATE spotify_track_owners SET track_id=2, evidence_type='manual_override' "
            "WHERE spotify_track_id='variant'"
        )
        conn.execute(
            "UPDATE track_l1_external_ids SET l1_id=2, is_primary=1, "
            "evidence_type='manual_confirmed' WHERE external_track_id='variant'"
        )
        conn.execute("DELETE FROM track_l1_source_links WHERE l1_id=1 AND track_id=2")
        conn.execute("INSERT INTO track_l1_source_links VALUES (2, 2, 'track_projection', 0)")
        return {"status": "applied_uncommitted", "operation_count": 1}

    monkeypatch.setattr(governance, "apply_split_plan", apply_l1)

    def build_l2(conn):
        if (
            conn.execute(
                "SELECT 1 FROM track_groups WHERE scope='recording' AND group_status='active'"
            ).fetchone()
            is None
        ):
            return _track_plan()
        return {
            **_track_plan(),
            "changed": False,
            "groups_to_create": 0,
            "groups_to_update": 0,
            "groups_to_archive": 0,
            "archived_group_ids": [],
            "accepted_edges": [],
            "blocked_edges": [],
            "groups": [],
        }

    monkeypatch.setattr(governance, "build_l2_track_merge_plan", build_l2)

    def apply_l2(conn, _plan, *, commit=False, bump_revision=True):
        assert commit is False
        calls["l2_bump"].append(bool(bump_revision))
        if not _plan["changed"]:
            return {"status": "unchanged", "changed": False, "group_count": 1}
        cursor = conn.execute(
            """INSERT INTO track_groups(
                   canonical_name, primary_track_id, primary_l1_id, scope,
                   is_manual, group_status, automatic_artist_id,
                   automatic_title_key, automatic_version_tag, identity_policy_version
               ) VALUES ('Song', 1, 1, 'recording', 0, 'active', 1, 'song', '', 'fixture-l2')"""
        )
        group_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO track_group_l1_members VALUES (?, ?)",
            ((group_id, 1), (group_id, 2)),
        )
        conn.execute(
            """INSERT INTO track_group_candidates(
                   scope, original_l1_id, candidate_l1_id,
                   confidence, evidence_json, status
               ) VALUES ('recording', 1, 2, 1.0, '{"fixture":true}', 'accepted')"""
        )
        return {"status": "applied", "changed": True, "group_count": 1}

    monkeypatch.setattr(governance, "apply_l2_track_merge_plan", apply_l2)

    def build_l3(_conn):
        return {
            "policy_version": "fixture-l3",
            "state_digest": "fixture",
            "changed": False,
            "desired_group_count": 0,
            "groups_to_create": 0,
            "groups_to_update": 0,
            "groups_to_archive": 0,
            "archived_group_ids": [],
            "accepted_edges": [],
            "blocked_edges": [],
            "warning_edges": [],
            "warning_reason_counts": {},
            "groups": [],
        }

    monkeypatch.setattr(governance, "build_l3_track_merge_plan", build_l3)

    def apply_l3(_conn, _plan, *, commit=False, bump_revision=True):
        assert commit is False
        calls["l3_bump"].append(bool(bump_revision))
        return {
            "status": "unchanged",
            "changed": False,
            "group_count": 0,
            "groups_created": 0,
            "groups_updated": 0,
            "groups_archived": 0,
            "members_added": 0,
            "members_removed": 0,
            "recording_parents_updated": 0,
            "candidate_evidence_upserted": 0,
            "revision_bumped": False,
            "track_identity_revision": 5,
        }

    monkeypatch.setattr(governance, "apply_l3_track_merge_plan", apply_l3)
    monkeypatch.setattr(
        governance,
        "plan_album_project_auto_merges",
        lambda _conn: SimpleNamespace(
            candidates=(),
            scanned_project_count=0,
            strong_evidence_project_count=0,
            skipped_reason_counts={},
        ),
    )
    monkeypatch.setattr(
        governance,
        "apply_album_project_auto_merge_plan",
        lambda *_a, **_k: _empty_album_report(),
    )
    monkeypatch.setattr(
        governance,
        "plan_album_composition_merges",
        lambda _conn: SimpleNamespace(
            policy_version=ALBUM_COMPOSITION_POLICY_VERSION,
            candidates=(),
            archive_group_ids=(),
            scanned_project_count=0,
            skipped_reason_counts=(),
        ),
    )
    monkeypatch.setattr(
        governance,
        "apply_album_composition_plan",
        lambda *_a, **_k: _empty_album_composition_report(),
    )
    monkeypatch.setattr(
        governance,
        "rebuild_album_projects",
        lambda conn, **_kwargs: conn.execute(
            "UPDATE album_project_revision_state SET current_revision=current_revision+1"
        ),
    )
    monkeypatch.setattr(governance, "invalidate", lambda _name: None)
    monkeypatch.setattr(governance, "mark_music_search_for_rebuild", lambda **_kwargs: None)
    return calls


def test_clone_plan_runs_two_round_simulation_and_reports_aggregate_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "plan.db"
    _create_database(path)
    calls = _patch_successful_relations(monkeypatch)
    source = governance._connect(path, readonly=True)
    try:
        report = governance._plan_on_clone(source, apply_l1_safe_splits=True)
    finally:
        source.close()

    assert report["l1"]["simulation"]["status"] == "pass"
    assert report["l1"]["simulation"]["convergence"] == {
        "l1_operation_count": 0,
        "l2_changed": False,
        "l2_groups_to_archive": 0,
        "l3_changed": False,
        "l2_preserved_by_l3": True,
        "album_l3_changed": False,
        "l3_album_attribution_changed": False,
        "l3_album_attribution_issue_count": 0,
    }
    assert len(report["l1"]["rounds"]) == 2
    assert len(report["track"]["rounds"]) == 2
    assert len(report["l1"]["operations"]) == 1
    assert report["track"]["changed"] is True
    assert report["track"]["groups_to_create"] == 1
    assert report["track"]["groups_to_update"] == 0
    assert report["track"]["groups_to_archive"] == 0
    assert report["track"]["groups"][0]["governance_round"] == 1
    assert calls == {
        "l1_bump": [False],
        "l2_bump": [False, False],
        "l3_bump": [False],
    }

    conn = sqlite3.connect(path)
    try:
        assert (
            conn.execute(
                "SELECT current_revision FROM track_identity_state WHERE state_id=1"
            ).fetchone()[0]
            == 5
        )
        assert conn.execute("SELECT COUNT(*) FROM track_groups").fetchone()[0] == 0
    finally:
        conn.close()


def test_apply_commits_auditable_header_preserves_raw_and_bumps_revision_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "governance.db"
    _create_database(path)
    calls = _patch_successful_relations(monkeypatch)
    monkeypatch.setattr(
        governance,
        "rebuild_current_music_search_derived_data",
        lambda *_a, **_k: _ready_report(),
    )

    original_db_path = db_mod.DB_PATH
    report = governance._apply(_args(path, tmp_path / "backups"))

    assert report["governance_status"] == "applied"
    assert db_mod.DB_PATH == original_db_path
    assert calls == {
        "l1_bump": [False],
        "l2_bump": [False, False],
        "l3_bump": [False],
    }
    assert report["track_identity_revision"] == {"before": 5, "after": 6, "delta": 1}
    assert report["relation_validation"]["raw_facts_preserved"] is True
    conn = sqlite3.connect(path)
    try:
        run = conn.execute("SELECT status, summary_json FROM version_governance_runs").fetchone()
        assert run[0] == "applied"
        summary = json.loads(run[1])
        assert summary["final_validation"]["raw_facts_preserved"] is True
        events = conn.execute(
            "SELECT before_json, after_json, evidence_json FROM version_governance_events"
        ).fetchall()
        assert events
        assert all(json.loads(before) for before, _after, _evidence in events)
        assert all(json.loads(after) for _before, after, _evidence in events)
        assert all(json.loads(evidence) for _before, _after, evidence in events)
    finally:
        conn.close()


def test_relation_failure_rolls_back_changes_but_keeps_failed_run_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "failed.db"
    _create_database(path)
    monkeypatch.setattr(governance, "run_migrations", lambda: None)
    monkeypatch.setattr(
        governance,
        "validate_track_identity_invariants",
        lambda _conn: SimpleNamespace(healthy=True, issue_count=0),
    )
    monkeypatch.setattr(
        governance,
        "build_l1_external_identity_risk_plan",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("planned failure")),
    )

    original_db_path = db_mod.DB_PATH
    with pytest.raises(RuntimeError, match="planned failure"):
        governance._apply(_args(path, tmp_path / "backups"))
    assert db_mod.DB_PATH == original_db_path

    conn = sqlite3.connect(path)
    try:
        status, summary_json = conn.execute(
            "SELECT status, summary_json FROM version_governance_runs"
        ).fetchone()
        assert status == "failed"
        assert json.loads(summary_json)["failure"] == {
            "stage": "relation_transaction",
            "error_type": "RuntimeError",
        }
        assert (
            conn.execute(
                "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id='variant'"
            ).fetchone()[0]
            == 1
        )
    finally:
        conn.close()


def test_year_end_failure_never_marks_governance_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "year-end-failed.db"
    _create_database(path)
    _patch_successful_relations(monkeypatch)
    monkeypatch.setattr(
        governance,
        "rebuild_current_music_search_derived_data",
        lambda *_a, **_k: _ready_report(projection_status="failed"),
    )

    with pytest.raises(RuntimeError, match="post-apply validation failed"):
        governance._apply(_args(path, tmp_path / "backups"))

    conn = sqlite3.connect(path)
    try:
        status, summary_json = conn.execute(
            "SELECT status, summary_json FROM version_governance_runs"
        ).fetchone()
        assert status == "failed"
        summary = json.loads(summary_json)
        assert summary["derived"]["year_end_projection"]["status"] == "failed"
        assert summary["failure"]["stage"] == "derived_maintenance"
    finally:
        conn.close()


def test_skip_derived_keeps_run_running_and_returns_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "pending.db"
    _create_database(path)
    _patch_successful_relations(monkeypatch)
    monkeypatch.setattr(
        governance,
        "rebuild_current_music_search_derived_data",
        lambda *_a, **_k: pytest.fail("skip-derived must not rebuild"),
    )

    report = governance._apply(_args(path, tmp_path / "backups", skip_derived=True))

    assert report["governance_status"] == "pending_derived"
    conn = sqlite3.connect(path)
    try:
        status, completed_at, summary_json = conn.execute(
            "SELECT status, completed_at, summary_json FROM version_governance_runs"
        ).fetchone()
        assert status == "running"
        assert completed_at is None
        assert json.loads(summary_json)["derived"]["status"] == "pending"
    finally:
        conn.close()

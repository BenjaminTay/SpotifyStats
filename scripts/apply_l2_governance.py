#!/usr/bin/env python3
"""Plan or atomically apply machine-first L2 governance.

Dry-run is the default and never writes the source database. Apply mode makes
an online SQLite backup, performs only strongly evidenced L1 corrections,
reconciles L2 recording groups, merges catalog-proven Album Projects, records
an audit run, and optionally rebuilds all four exact music-search variants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db as db_mod  # noqa: E402
from backend.core.cache_manager import invalidate  # noqa: E402
from backend.core.migrations import LATEST_SCHEMA_VERSION, run_migrations  # noqa: E402
from backend.domains.metadata.l2_track_auto_merge import (  # noqa: E402
    L2_AUTO_MERGE_POLICY_VERSION,
    apply_l2_track_merge_plan,
    build_l2_track_merge_plan,
)
from backend.domains.metadata.track_identity_risk import (  # noqa: E402
    apply_split_plan,
    build_l1_external_identity_risk_plan,
)
from backend.domains.playback.album_project_auto_merge import (  # noqa: E402
    ALBUM_PROJECT_AUTO_IDENTITY_POLICY_VERSION,
    apply_album_project_auto_merge_plan,
    plan_album_project_auto_merges,
)
from backend.domains.playback.album_projects import rebuild_album_projects  # noqa: E402
from backend.services.music_search_maintenance_service import (  # noqa: E402
    mark_music_search_for_rebuild,
    rebuild_current_music_search_derived_data,
)

GOVERNANCE_POLICY_VERSION = (
    f"l2_governance_v1:{L2_AUTO_MERGE_POLICY_VERSION}:{ALBUM_PROJECT_AUTO_IDENTITY_POLICY_VERSION}"
)
RAW_FACT_TABLES = ("plays", "tracks", "track_artists")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or apply automatic L2 governance")
    parser.add_argument("--db-path", type=Path, default=Path(db_mod.DB_PATH))
    parser.add_argument("--apply", action="store_true", help="Apply the current plan")
    parser.add_argument(
        "--skip-l1-safe-splits",
        action="store_true",
        help="Audit L1 risks but do not apply strongly evidenced owner corrections",
    )
    parser.add_argument(
        "--skip-derived-rebuild",
        action="store_true",
        help="Apply governance but leave exact search snapshots pending",
    )
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _connect(path: Path, *, readonly: bool) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _online_backup(source_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"spotify_stats_{timestamp}_before-l2-governance.db"
    if target.exists():
        target = (
            backup_dir / f"spotify_stats_{timestamp}_{uuid.uuid4().hex[:8]}_before-l2-governance.db"
        )
    # Open through SQLite (not a file copy) so committed WAL pages are included.
    # Read-write mode is required for WAL databases that need sidecar creation;
    # the backup API itself does not mutate source rows.
    source = _connect(source_path, readonly=False)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()
    # A backup inherits WAL journal mode. Opening it writable for this check
    # lets SQLite create/remove the empty WAL sidecars before the file is later
    # used as a standalone restore point.
    check = _connect(target, readonly=False)
    try:
        if str(check.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise RuntimeError("online backup failed integrity_check")
    finally:
        check.close()
    return target


def _table_digest(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    primary = [str(row[1]) for row in sorted(info, key=lambda row: int(row[5])) if int(row[5])]
    order_by = ", ".join(f'"{column}"' for column in primary) or "rowid"
    digest = hashlib.sha256()
    row_count = 0
    for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY {order_by}'):
        digest.update(
            json.dumps(tuple(row), ensure_ascii=False, default=str, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        digest.update(b"\n")
        row_count += 1
    return {"rows": row_count, "sha256": digest.hexdigest()}


def _raw_fact_state(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {table: _table_digest(conn, table) for table in RAW_FACT_TABLES}


def _schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0] or 0)


def _album_plan_json(plan: Any) -> dict[str, Any]:
    return {
        "candidate_count": len(plan.candidates),
        "scanned_project_count": plan.scanned_project_count,
        "strong_evidence_project_count": plan.strong_evidence_project_count,
        "skipped_reason_counts": dict(plan.skipped_reason_counts),
        "candidates": [asdict(candidate) for candidate in plan.candidates],
    }


def _plan_on_clone(source: sqlite3.Connection, *, apply_l1_safe_splits: bool) -> dict[str, Any]:
    clone = sqlite3.connect(":memory:")
    clone.row_factory = sqlite3.Row
    clone.execute("PRAGMA foreign_keys=ON")
    source.backup(clone)
    try:
        l1_plan = build_l1_external_identity_risk_plan(clone, include_keep=False)
        l1_simulation: dict[str, Any] | None = None
        if apply_l1_safe_splits and l1_plan.get("operations"):
            clone.execute("BEGIN")
            l1_simulation = apply_split_plan(clone, str(l1_plan["confirmation_token"]))
        track_plan = build_l2_track_merge_plan(clone)
        album_plan = plan_album_project_auto_merges(clone)
        return {
            "l1": {
                "summary": l1_plan.get("summary", {}),
                "operations": l1_plan.get("operations", []),
                "simulation": l1_simulation,
            },
            "track": track_plan,
            "album": _album_plan_json(album_plan),
        }
    finally:
        clone.rollback()
        clone.close()


def _insert_event(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    entity_type: str,
    action: str,
    survivor_id: int | None,
    affected_ids: list[int],
    evidence: dict[str, Any],
) -> None:
    conn.execute(
        """INSERT INTO version_governance_events(
               run_id, entity_type, action, survivor_id,
               affected_ids_json, evidence_json
           ) VALUES (?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            entity_type,
            action,
            survivor_id,
            json.dumps(affected_ids, separators=(",", ":")),
            json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        ),
    )


def _apply(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.resolve()
    backup_dir = (args.backup_dir or (PROJECT_ROOT / "data" / "backups")).resolve()
    backup_path = _online_backup(db_path, backup_dir)
    db_mod.DB_PATH = str(db_path)
    run_migrations()
    conn = _connect(db_path, readonly=False)
    run_id = str(uuid.uuid4())
    before_raw = _raw_fact_state(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """INSERT INTO version_governance_runs(
                   run_id, scope, policy_version, status, dry_run
               ) VALUES (?, 'l1+l2+album_project', ?, 'running', 0)""",
            (run_id, GOVERNANCE_POLICY_VERSION),
        )

        l1_plan = build_l1_external_identity_risk_plan(conn, include_keep=False)
        l1_report: dict[str, Any] = {
            "status": "audit_only",
            "operation_count": 0,
        }
        if not args.skip_l1_safe_splits and l1_plan.get("operations"):
            l1_report = apply_split_plan(conn, str(l1_plan["confirmation_token"]))
            for operation in l1_plan["operations"]:
                _insert_event(
                    conn,
                    run_id=run_id,
                    entity_type="l1_external_identity",
                    action="reassign_external_identity",
                    survivor_id=int(operation["source_l1_id"]),
                    affected_ids=[int(operation["target_l1_id"])],
                    evidence=operation,
                )

        track_plan = build_l2_track_merge_plan(conn)
        track_report = apply_l2_track_merge_plan(conn, track_plan, commit=False)
        if track_report.get("changed"):
            for group in track_plan["groups"]:
                if group["action"] == "unchanged":
                    continue
                _insert_event(
                    conn,
                    run_id=run_id,
                    entity_type="recording_group",
                    action=str(group["action"]),
                    survivor_id=(
                        int(group["target_group_id"])
                        if group["target_group_id"] is not None
                        else None
                    ),
                    affected_ids=[int(value) for value in group["member_l1_ids"]],
                    evidence={
                        "policy_version": track_plan["policy_version"],
                        "title_key": group["normalized_title"],
                        "version_tags": group["semantic_version_tags"],
                        "artist_ids": group["artist_ids"],
                        "evidence_types": group["evidence_types"],
                    },
                )
            for group_id in track_plan["archived_group_ids"]:
                _insert_event(
                    conn,
                    run_id=run_id,
                    entity_type="recording_group",
                    action="archive",
                    survivor_id=int(group_id),
                    affected_ids=[],
                    evidence={"policy_version": track_plan["policy_version"]},
                )

        album_plan = plan_album_project_auto_merges(conn)
        album_report = apply_album_project_auto_merge_plan(
            conn,
            album_plan,
            commit=False,
            ensure_schema=False,
        )
        if not album_plan.candidates and (
            track_report.get("changed") or int(l1_report.get("operation_count", 0)) > 0
        ):
            rebuild_album_projects(conn, commit=False, ensure_schema=False)
        for candidate in album_plan.candidates:
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="album_project",
                action="merge_catalog_release",
                survivor_id=None,
                affected_ids=[int(value) for value in candidate.project_ids],
                evidence=asdict(candidate),
            )

        relation_summary = {
            "l1": l1_report,
            "l1_audit": l1_plan.get("summary", {}),
            "track": track_report,
            "album": asdict(album_report),
        }
        conn.execute(
            "UPDATE version_governance_runs SET summary_json=? WHERE run_id=?",
            (
                json.dumps(relation_summary, ensure_ascii=False, sort_keys=True, default=str),
                run_id,
            ),
        )
        conn.commit()

        changed = bool(
            track_report.get("changed")
            or int(l1_report.get("operation_count", 0))
            or album_report.requires_downstream_refresh
        )
        derived_report: dict[str, Any] = {"status": "unchanged"}
        if changed:
            invalidate("analysis")
            invalidate("billboard")
            invalidate("yearly_review")
            mark_music_search_for_rebuild(
                reason=f"automatic L2 governance run {run_id}",
                documents=True,
                revision_kinds=("metadata", "candidate"),
                conn=conn,
            )
            if args.skip_derived_rebuild:
                derived_report = {"status": "pending"}
            else:
                derived_report = rebuild_current_music_search_derived_data(
                    conn,
                    rebuild_documents=True,
                )

        after_raw = _raw_fact_state(conn)
        raw_preserved = before_raw == after_raw
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_issues = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        final_summary = {
            **relation_summary,
            "derived": {
                "status": derived_report.get("status"),
                "snapshot_set": derived_report.get("snapshot_set"),
            },
            "raw_facts_preserved": raw_preserved,
            "integrity_check": integrity,
            "foreign_key_issue_count": foreign_key_issues,
        }
        success = (
            raw_preserved
            and integrity == "ok"
            and foreign_key_issues == 0
            and derived_report.get("status") in {"ready", "unchanged", "pending"}
        )
        conn.execute(
            """UPDATE version_governance_runs
                  SET status=?, summary_json=?, completed_at=CURRENT_TIMESTAMP
                WHERE run_id=?""",
            (
                "applied" if success else "failed",
                json.dumps(final_summary, ensure_ascii=False, sort_keys=True, default=str),
                run_id,
            ),
        )
        conn.commit()
        if not success:
            raise RuntimeError(f"post-apply validation failed: {final_summary}")
        return {
            "mode": "apply",
            "run_id": run_id,
            "policy_version": GOVERNANCE_POLICY_VERSION,
            "schema_version": _schema_version(conn),
            "backup_path": str(backup_path),
            **final_summary,
        }
    except Exception as exc:
        conn.rollback()
        try:
            conn.execute(
                """UPDATE version_governance_runs
                      SET status='failed', completed_at=CURRENT_TIMESTAMP,
                          summary_json=? WHERE run_id=?""",
                (json.dumps({"error_type": type(exc).__name__}), run_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    args = _parse_args()
    db_path = args.db_path.resolve()
    if not db_path.is_file():
        raise SystemExit(f"database not found: {db_path}")
    if args.apply:
        report = _apply(args)
    else:
        conn = _connect(db_path, readonly=True)
        try:
            version = _schema_version(conn)
            if version < 66:
                raise SystemExit(
                    f"dry-run requires schema >=66; current={version}, latest={LATEST_SCHEMA_VERSION}"
                )
            report = {
                "mode": "dry_run",
                "policy_version": GOVERNANCE_POLICY_VERSION,
                "schema_version": version,
                "raw_facts": _raw_fact_state(conn),
                **_plan_on_clone(
                    conn,
                    apply_l1_safe_splits=not args.skip_l1_safe_splits,
                ),
            }
        finally:
            conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

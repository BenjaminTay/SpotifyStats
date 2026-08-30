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
from backend.domains.metadata.track_identity import (  # noqa: E402
    bump_track_identity_revision,
    validate_track_identity_invariants,
)
from backend.domains.metadata.track_identity_risk import (  # noqa: E402
    apply_split_plan,
    build_l1_external_identity_risk_plan,
)
from backend.domains.music_search.context import (  # noqa: E402
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
)
from backend.domains.music_search.year_end_projection import (  # noqa: E402
    YEAR_END_PROJECTION_BUILDER_VERSION,
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
EXPECTED_SEARCH_VARIANTS = {(2, 0), (2, 1), (3, 0), (3, 1)}


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
        before_raw = _raw_fact_state(clone)
        before_identity = _identity_health(clone)
        clone.execute("BEGIN")
        l1_rounds: list[dict[str, Any]] = []
        l2_rounds: list[dict[str, Any]] = []
        all_operations: list[dict[str, Any]] = []
        planned_group_changes: list[dict[str, Any]] = []
        planned_archived_group_ids: list[int] = []
        planned_accepted_edges: list[dict[str, Any]] = []
        planned_blocked_edges: list[dict[str, Any]] = []
        for round_number in (1, 2):
            l1_plan = build_l1_external_identity_risk_plan(clone, include_keep=False)
            l1_report: dict[str, Any] = {"status": "audit_only", "operation_count": 0}
            if apply_l1_safe_splits and l1_plan.get("operations"):
                l1_report = apply_split_plan(
                    clone,
                    str(l1_plan["confirmation_token"]),
                    bump_revision=False,
                )
                all_operations.extend(l1_plan["operations"])
            track_plan = build_l2_track_merge_plan(clone)
            planned_group_changes.extend(
                {"governance_round": round_number, **group}
                for group in track_plan.get("groups", [])
                if group.get("action") != "unchanged"
            )
            planned_archived_group_ids.extend(
                int(group_id) for group_id in track_plan.get("archived_group_ids", [])
            )
            planned_accepted_edges.extend(track_plan.get("accepted_edges", []))
            planned_blocked_edges.extend(track_plan.get("blocked_edges", []))
            track_report = apply_l2_track_merge_plan(
                clone,
                track_plan,
                commit=False,
                bump_revision=False,
            )
            l1_rounds.append(
                {
                    "round": round_number,
                    "summary": l1_plan.get("summary", {}),
                    "operation_count": int(l1_report.get("operation_count", 0)),
                }
            )
            l2_rounds.append(
                {
                    "round": round_number,
                    "plan": {
                        "changed": bool(track_plan.get("changed")),
                        "groups_to_create": int(track_plan.get("groups_to_create", 0)),
                        "groups_to_update": int(track_plan.get("groups_to_update", 0)),
                        "groups_to_archive": int(track_plan.get("groups_to_archive", 0)),
                    },
                    "report": track_report,
                }
            )
            if not (int(l1_report.get("operation_count", 0)) or bool(track_report.get("changed"))):
                break

        final_l1_plan = build_l1_external_identity_risk_plan(clone, include_keep=False)
        final_track_plan = build_l2_track_merge_plan(clone)
        convergence = {
            "l1_operation_count": len(final_l1_plan.get("operations", [])),
            "l2_changed": bool(final_track_plan.get("changed")),
            "l2_groups_to_archive": len(final_track_plan.get("archived_group_ids", [])),
        }
        converged = bool(
            (not apply_l1_safe_splits or convergence["l1_operation_count"] == 0)
            and not convergence["l2_changed"]
        )
        album_plan = plan_album_project_auto_merges(clone)
        relation_gate = _relation_gate(clone, before_raw, before_identity)
        return {
            "l1": {
                "summary": final_l1_plan.get("summary", {}),
                "operations": all_operations,
                "rounds": l1_rounds,
                "simulation": {
                    "status": "pass" if converged and relation_gate["status"] == "pass" else "fail",
                    "convergence": convergence,
                    "relation_validation": relation_gate,
                },
            },
            "track": {
                **final_track_plan,
                "changed": any(bool(item["report"].get("changed")) for item in l2_rounds),
                "groups_to_create": sum(
                    int(item["plan"]["groups_to_create"]) for item in l2_rounds
                ),
                "groups_to_update": sum(
                    int(item["plan"]["groups_to_update"]) for item in l2_rounds
                ),
                "groups_to_archive": sum(
                    int(item["plan"]["groups_to_archive"]) for item in l2_rounds
                ),
                "groups": planned_group_changes,
                "archived_group_ids": sorted(set(planned_archived_group_ids)),
                "accepted_edges": planned_accepted_edges,
                "blocked_edges": planned_blocked_edges,
                "rounds": l2_rounds,
                "convergence": convergence,
            },
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
    before: dict[str, Any],
    after: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    if not before or not after or not evidence:
        raise ValueError("governance events require non-empty before, after, and evidence")
    conn.execute(
        """INSERT INTO version_governance_events(
               run_id, entity_type, action, survivor_id,
               affected_ids_json, before_json, after_json, evidence_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            entity_type,
            action,
            survivor_id,
            json.dumps(affected_ids, separators=(",", ":")),
            json.dumps(before, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            json.dumps(after, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        ),
    )


def _rows_as_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _l1_operation_state(
    conn: sqlite3.Connection,
    operation: dict[str, Any],
) -> dict[str, Any]:
    l1_ids = sorted(
        {
            int(operation["source_l1_id"]),
            int(operation["target_l1_id"]),
        }
    )
    placeholders = ",".join("?" for _ in l1_ids)
    token_value = operation.get("external_track_id")
    token = str(token_value) if token_value is not None else None
    identities = _rows_as_dicts(
        conn.execute(
            f"""SELECT l1_id, fallback_track_id, identity_status,
                       representative_track_id
                  FROM track_l1_identities
                 WHERE l1_id IN ({placeholders}) ORDER BY l1_id""",
            l1_ids,
        ).fetchall()
    )
    external_where = f"l1_id IN ({placeholders})"
    external_params: tuple[Any, ...] = tuple(l1_ids)
    if token is not None:
        external_where += " OR external_track_id=?"
        external_params = (*external_params, token)
    external_ids = _rows_as_dicts(
        conn.execute(
            f"""SELECT provider, external_track_id, l1_id, evidence_type, is_primary
                  FROM track_l1_external_ids
                 WHERE {external_where}
                 ORDER BY provider, external_track_id""",
            external_params,
        ).fetchall()
    )
    source_links = _rows_as_dicts(
        conn.execute(
            f"""SELECT l1_id, track_id, evidence_type, observed_plays
                  FROM track_l1_source_links
                 WHERE l1_id IN ({placeholders})
                 ORDER BY l1_id, track_id, evidence_type""",
            l1_ids,
        ).fetchall()
    )
    owner = (
        conn.execute(
            """SELECT spotify_track_id, track_id, evidence_type
                 FROM spotify_track_owners WHERE spotify_track_id=?""",
            (token,),
        ).fetchone()
        if token is not None
        else None
    )
    return {
        "identities": identities,
        "external_ids": external_ids,
        "source_links": source_links,
        "spotify_owner": dict(owner) if owner is not None else None,
    }


def _recording_group_state(
    conn: sqlite3.Connection,
    *,
    group_id: int | None = None,
    member_l1_ids: list[int] | None = None,
) -> dict[str, Any]:
    resolved_group_id = int(group_id) if group_id is not None else None
    if resolved_group_id is None and member_l1_ids:
        members = sorted({int(value) for value in member_l1_ids})
        placeholders = ",".join("?" for _ in members)
        row = conn.execute(
            f"""SELECT groups.group_id
                  FROM track_groups groups
                  JOIN track_group_l1_members members
                    ON members.group_id=groups.group_id
                 WHERE groups.scope='recording' AND groups.group_status='active'
                 GROUP BY groups.group_id
                HAVING COUNT(DISTINCT members.l1_id)=?
                   AND SUM(members.l1_id IN ({placeholders}))=?
                 ORDER BY groups.group_id LIMIT 1""",
            (len(members), *members, len(members)),
        ).fetchone()
        resolved_group_id = int(row[0]) if row is not None else None
    if resolved_group_id is None:
        return {"exists": False}
    group = conn.execute(
        """SELECT group_id, canonical_name, primary_track_id, primary_l1_id,
                  scope, parent_group_id, is_manual, group_status,
                  automatic_artist_id, automatic_title_key,
                  automatic_version_tag, identity_policy_version
             FROM track_groups WHERE group_id=?""",
        (resolved_group_id,),
    ).fetchone()
    if group is None:
        return {"exists": False, "group_id": resolved_group_id}
    members = [
        int(row[0])
        for row in conn.execute(
            """SELECT l1_id FROM track_group_l1_members
                WHERE group_id=? ORDER BY l1_id""",
            (resolved_group_id,),
        ).fetchall()
    ]
    return {"exists": True, **dict(group), "member_l1_ids": members}


def _candidate_state(conn: sqlite3.Connection, left: int, right: int) -> dict[str, Any]:
    row = conn.execute(
        """SELECT candidate_id, scope, original_l1_id, candidate_l1_id,
                  confidence, evidence_json, status
             FROM track_group_candidates
            WHERE scope='recording'
              AND MIN(original_l1_id, candidate_l1_id)=?
              AND MAX(original_l1_id, candidate_l1_id)=?""",
        (min(left, right), max(left, right)),
    ).fetchone()
    return {"exists": False} if row is None else {"exists": True, **dict(row)}


def _album_candidate_state(conn: sqlite3.Connection, candidate: Any) -> dict[str, Any]:
    album_ids = sorted(int(value) for value in candidate.album_ids)
    placeholders = ",".join("?" for _ in album_ids)
    projects = _rows_as_dicts(
        conn.execute(
            f"""SELECT DISTINCT projects.project_id, projects.canonical_name,
                        projects.primary_album_id, projects.scope,
                        projects.project_type, projects.identity_policy_version
                   FROM album_project_albums members
                   JOIN album_projects projects ON projects.project_id=members.project_id
                  WHERE members.album_id IN ({placeholders})
                  ORDER BY projects.project_id""",
            album_ids,
        ).fetchall()
    )
    memberships = _rows_as_dicts(
        conn.execute(
            f"""SELECT project_id, album_id FROM album_project_albums
                  WHERE album_id IN ({placeholders}) ORDER BY project_id, album_id""",
            album_ids,
        ).fetchall()
    )
    external = conn.execute(
        """SELECT provider, external_album_id, project_id, evidence_type,
                  confidence, is_primary
             FROM album_project_external_ids
            WHERE provider='spotify' AND external_album_id=?""",
        (str(candidate.spotify_album_id),),
    ).fetchone()
    return {
        "album_ids": album_ids,
        "projects": projects,
        "memberships": memberships,
        "external_identity": dict(external) if external is not None else None,
    }


def _identity_health(conn: sqlite3.Connection) -> dict[str, Any]:
    health = validate_track_identity_invariants(conn)
    counts = {
        key: int(value)
        for key, value in vars(health).items()
        if isinstance(value, int) and not isinstance(value, bool)
    }
    return {"healthy": bool(health.healthy), **counts}


def _recording_group_health(conn: sqlite3.Connection) -> dict[str, int]:
    overlap = int(
        conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT members.l1_id
                     FROM track_group_l1_members members
                     JOIN track_groups groups ON groups.group_id=members.group_id
                    WHERE groups.scope='recording' AND groups.group_status='active'
                    GROUP BY members.l1_id
                   HAVING COUNT(DISTINCT groups.group_id)>1
               )"""
        ).fetchone()[0]
    )
    too_small = int(
        conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT groups.group_id
                     FROM track_groups groups
                     LEFT JOIN track_group_l1_members members
                       ON members.group_id=groups.group_id
                    WHERE groups.scope='recording' AND groups.group_status='active'
                    GROUP BY groups.group_id
                   HAVING COUNT(DISTINCT members.l1_id)<2
               )"""
        ).fetchone()[0]
    )
    invalid_primary = int(
        conn.execute(
            """SELECT COUNT(*) FROM track_groups groups
                WHERE groups.scope='recording' AND groups.group_status='active'
                  AND (groups.primary_l1_id IS NULL OR NOT EXISTS (
                      SELECT 1 FROM track_group_l1_members members
                       WHERE members.group_id=groups.group_id
                         AND members.l1_id=groups.primary_l1_id
                  ))"""
        ).fetchone()[0]
    )
    return {
        "member_overlap_count": overlap,
        "undersized_active_group_count": too_small,
        "invalid_primary_count": invalid_primary,
    }


def _relation_gate(
    conn: sqlite3.Connection,
    before_raw: dict[str, dict[str, Any]],
    before_identity: dict[str, Any],
) -> dict[str, Any]:
    after_raw = _raw_fact_state(conn)
    identity = _identity_health(conn)
    identity_regressions = {
        key: {"before": int(before_identity.get(key, 0)), "after": int(value)}
        for key, value in identity.items()
        if key != "healthy"
        and isinstance(value, int)
        and int(value) > int(before_identity.get(key, 0))
    }
    hard_identity_keys = {
        "duplicate_spotify_identity_count",
        "unresolved_play_identity_count",
        "source_link_orphan_count",
        "representative_missing_count",
        "external_owner_orphan_count",
        "active_group_too_small_count",
        "active_group_invalid_primary_count",
    }
    hard_identity_issues = {
        key: int(identity.get(key, 0))
        for key in hard_identity_keys
        if int(identity.get(key, 0)) > 0
    }
    recording = _recording_group_health(conn)
    integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    foreign_key_issues = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    passed = bool(
        before_raw == after_raw
        and not hard_identity_issues
        and not identity_regressions
        and not any(recording.values())
        and integrity == "ok"
        and foreign_key_issues == 0
    )
    return {
        "status": "pass" if passed else "fail",
        "raw_facts_before": before_raw,
        "raw_facts_after": after_raw,
        "raw_facts_preserved": before_raw == after_raw,
        "identity": identity,
        "identity_before": before_identity,
        "identity_regressions": identity_regressions,
        "hard_identity_issues": hard_identity_issues,
        "recording_groups": recording,
        "integrity_check": integrity,
        "foreign_key_issue_count": foreign_key_issues,
    }


def _derived_report_ready(report: dict[str, Any]) -> bool:
    snapshots = report.get("snapshot_set") or {}
    projection = report.get("year_end_projection") or snapshots.get("year_end_projection") or {}
    snapshot_variants = snapshots.get("variants") or []
    projection_variants = projection.get("variants") or []
    return bool(
        report.get("status") == "ready"
        and snapshots.get("status") == "ready"
        and int(snapshots.get("ready_count", 0)) == 4
        and int(snapshots.get("failed_count", 0)) == 0
        and len(snapshot_variants) == 4
        and all(item.get("status") == "ready" for item in snapshot_variants)
        and projection.get("status") == "ready"
        and int(projection.get("ready_count", 0)) == 4
        and int(projection.get("failed_count", 0)) == 0
        and len(projection_variants) == 4
        and all(item.get("status") == "ready" for item in projection_variants)
    )


def _derived_database_state(conn: sqlite3.Connection) -> dict[str, Any]:
    variants = _rows_as_dicts(
        conn.execute(
            """SELECT state.merge_level, state.dynamic_threshold,
                      state.active_snapshot_key, state.active_filter_fingerprint,
                      state.target_filter_fingerprint, state.maintenance_status,
                      meta.status AS snapshot_status,
                      meta.filter_fingerprint, meta.builder_version,
                      (SELECT COUNT(*) FROM music_search_entity_context context
                        WHERE context.snapshot_key=state.active_snapshot_key) AS entity_count,
                      projection.status AS projection_status,
                      projection.builder_version AS projection_builder_version,
                      (SELECT COUNT(*) FROM music_search_year_end_meta annual_meta
                        WHERE annual_meta.snapshot_key=state.active_snapshot_key) AS year_count,
                      (SELECT COUNT(*) FROM music_search_entity_year_end annual
                        WHERE annual.snapshot_key=state.active_snapshot_key) AS projection_row_count
                 FROM music_search_snapshot_variant_state state
                 LEFT JOIN music_search_snapshot_meta meta
                   ON meta.snapshot_key=state.active_snapshot_key
                 LEFT JOIN music_search_year_end_projection_state projection
                   ON projection.snapshot_key=state.active_snapshot_key
                ORDER BY state.merge_level, state.dynamic_threshold"""
        ).fetchall()
    )
    variant_keys = {(int(item["merge_level"]), int(item["dynamic_threshold"])) for item in variants}
    ready = bool(
        variant_keys == EXPECTED_SEARCH_VARIANTS
        and all(
            item["maintenance_status"] == "ready"
            and item["snapshot_status"] == "ready"
            and item["projection_status"] == "ready"
            and item["builder_version"] == MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
            and item["projection_builder_version"] == YEAR_END_PROJECTION_BUILDER_VERSION
            and item["active_snapshot_key"] == item["active_filter_fingerprint"]
            and item["active_filter_fingerprint"] == item["target_filter_fingerprint"]
            and item["filter_fingerprint"] == item["active_filter_fingerprint"]
            and int(item["entity_count"] or 0) > 0
            for item in variants
        )
    )
    return {"status": "ready" if ready else "incomplete", "variants": variants}


def _merge_summary(existing: dict[str, Any], **updates: Any) -> dict[str, Any]:
    return {**existing, **updates}


def _apply_l1_round(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    skip_safe_splits: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = build_l1_external_identity_risk_plan(conn, include_keep=False)
    report: dict[str, Any] = {"status": "audit_only", "operation_count": 0}
    before_states = [
        _l1_operation_state(conn, operation) for operation in plan.get("operations", [])
    ]
    if not skip_safe_splits and plan.get("operations"):
        report = apply_split_plan(
            conn,
            str(plan["confirmation_token"]),
            bump_revision=False,
        )
        for index, operation in enumerate(plan["operations"]):
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="l1_external_identity",
                action=str(operation["operation"]),
                survivor_id=int(operation["source_l1_id"]),
                affected_ids=[int(operation["target_l1_id"])],
                before=before_states[index],
                after=_l1_operation_state(conn, operation),
                evidence=operation,
            )
    return plan, report


def _apply_l2_round(
    conn: sqlite3.Connection,
    *,
    run_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = build_l2_track_merge_plan(conn)
    group_before = {
        index: _recording_group_state(
            conn,
            group_id=group.get("target_group_id"),
            member_l1_ids=group.get("member_l1_ids"),
        )
        for index, group in enumerate(plan["groups"])
    }
    archived_before = {
        int(group_id): _recording_group_state(conn, group_id=int(group_id))
        for group_id in plan["archived_group_ids"]
    }
    decision_edges = [*plan["accepted_edges"], *plan["blocked_edges"]]
    candidate_before = {
        index: _candidate_state(
            conn,
            int(edge["left_l1_id"]),
            int(edge["right_l1_id"]),
        )
        for index, edge in enumerate(decision_edges)
    }
    report = apply_l2_track_merge_plan(
        conn,
        plan,
        commit=False,
        bump_revision=False,
    )
    if report.get("changed"):
        for index, group in enumerate(plan["groups"]):
            if group["action"] == "unchanged":
                continue
            after = _recording_group_state(
                conn,
                group_id=group.get("target_group_id"),
                member_l1_ids=group["member_l1_ids"],
            )
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="recording_group",
                action=str(group["action"]),
                survivor_id=int(after["group_id"]) if after.get("exists") else None,
                affected_ids=[int(value) for value in group["member_l1_ids"]],
                before=group_before[index],
                after=after,
                evidence={
                    "policy_version": plan["policy_version"],
                    "title_key": group["normalized_title"],
                    "version_tags": group["semantic_version_tags"],
                    "artist_ids": group["artist_ids"],
                    "evidence_types": group["evidence_types"],
                },
            )
        for group_id in plan["archived_group_ids"]:
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="recording_group",
                action="archive",
                survivor_id=int(group_id),
                affected_ids=[],
                before=archived_before[int(group_id)],
                after=_recording_group_state(conn, group_id=int(group_id)),
                evidence={"policy_version": plan["policy_version"]},
            )
    for index, edge in enumerate(decision_edges):
        left = int(edge["left_l1_id"])
        right = int(edge["right_l1_id"])
        after = _candidate_state(conn, left, right)
        before = candidate_before[index]
        if before == after:
            continue
        status = str(after.get("status") or edge.get("status") or "accepted")
        _insert_event(
            conn,
            run_id=run_id,
            entity_type="recording_candidate",
            action=f"decision_{status}",
            survivor_id=None,
            affected_ids=[left, right],
            before=before,
            after=after,
            evidence={"policy_version": plan["policy_version"], **edge},
        )
    return plan, report


def _aggregate_l1_rounds(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    reports = [dict(item["report"]) for item in rounds]
    operation_count = sum(int(report.get("operation_count", 0)) for report in reports)
    return {
        **(reports[-1] if reports else {"status": "audit_only"}),
        "status": "applied_uncommitted" if operation_count else "audit_only",
        "operation_count": operation_count,
        "semantic_changed": operation_count > 0,
        "revision_bumped": False,
        "rounds": rounds,
    }


def _aggregate_l2_rounds(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    reports = [dict(item["report"]) for item in rounds]
    changed = any(bool(report.get("changed")) for report in reports)
    summed_keys = (
        "groups_created",
        "groups_updated",
        "groups_archived",
        "members_added",
        "members_removed",
        "candidate_evidence_upserted",
    )
    result = dict(reports[-1]) if reports else {"status": "unchanged", "changed": False}
    for key in summed_keys:
        result[key] = sum(int(report.get(key, 0)) for report in reports)
    result.update(
        {
            "status": "applied" if changed else "unchanged",
            "changed": changed,
            "revision_bumped": False,
            "rounds": rounds,
        }
    )
    return result


def _apply(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.resolve()
    backup_dir = (args.backup_dir or (PROJECT_ROOT / "data" / "backups")).resolve()
    backup_path = _online_backup(db_path, backup_dir)
    db_mod.DB_PATH = str(db_path)
    run_migrations()
    conn = _connect(db_path, readonly=False)
    run_id = str(uuid.uuid4())
    before_raw = _raw_fact_state(conn)
    backup_conn = _connect(backup_path, readonly=True)
    try:
        backup_raw = _raw_fact_state(backup_conn)
    finally:
        backup_conn.close()
    if backup_raw != before_raw:
        conn.close()
        raise RuntimeError("online backup raw-fact digest does not match source database")

    initial_summary = {
        "backup_path": str(backup_path),
        "backup_raw_facts": backup_raw,
        "raw_facts_before": before_raw,
    }
    conn.execute(
        """INSERT INTO version_governance_runs(
               run_id, scope, policy_version, status, dry_run, summary_json
           ) VALUES (?, 'l1+l2+album_project', ?, 'running', 0, ?)""",
        (
            run_id,
            GOVERNANCE_POLICY_VERSION,
            json.dumps(initial_summary, ensure_ascii=False, sort_keys=True),
        ),
    )
    # The audit header must survive a rollback of the governed relationships.
    conn.commit()
    stage = "relation_transaction"
    try:
        conn.execute("BEGIN IMMEDIATE")
        revision_before = int(
            conn.execute(
                "SELECT current_revision FROM track_identity_state WHERE state_id=1"
            ).fetchone()[0]
        )
        album_revision_before = int(
            conn.execute(
                "SELECT current_revision FROM album_project_revision_state WHERE state_id=1"
            ).fetchone()[0]
        )
        identity_before = _identity_health(conn)
        l1_rounds: list[dict[str, Any]] = []
        l2_rounds: list[dict[str, Any]] = []
        for round_number in (1, 2):
            l1_plan, round_l1_report = _apply_l1_round(
                conn,
                run_id=run_id,
                skip_safe_splits=args.skip_l1_safe_splits,
            )
            track_plan, round_track_report = _apply_l2_round(conn, run_id=run_id)
            l1_rounds.append(
                {
                    "round": round_number,
                    "audit": l1_plan.get("summary", {}),
                    "report": round_l1_report,
                }
            )
            l2_rounds.append(
                {
                    "round": round_number,
                    "plan": {
                        "policy_version": track_plan["policy_version"],
                        "desired_group_count": track_plan.get("desired_group_count"),
                        "groups_to_archive": len(track_plan["archived_group_ids"]),
                        "blocked_edge_count": len(track_plan["blocked_edges"]),
                    },
                    "report": round_track_report,
                }
            )
            if not (
                int(round_l1_report.get("operation_count", 0))
                or bool(round_track_report.get("changed"))
            ):
                break

        convergence_l1_plan = build_l1_external_identity_risk_plan(conn, include_keep=False)
        convergence_track_plan = build_l2_track_merge_plan(conn)
        convergence = {
            "l1_operation_count": len(convergence_l1_plan.get("operations", [])),
            "l2_changed": bool(convergence_track_plan.get("changed")),
            "l2_groups_to_archive": len(convergence_track_plan.get("archived_group_ids", [])),
        }
        if convergence["l1_operation_count"] or convergence["l2_changed"]:
            raise RuntimeError(f"L1/L2 governance did not converge in two rounds: {convergence}")
        l1_report = _aggregate_l1_rounds(l1_rounds)
        track_report = _aggregate_l2_rounds(l2_rounds)

        album_plan = plan_album_project_auto_merges(conn)
        album_before = [
            _album_candidate_state(conn, candidate) for candidate in album_plan.candidates
        ]
        album_report = apply_album_project_auto_merge_plan(
            conn,
            album_plan,
            commit=False,
            ensure_schema=False,
        )
        forced_album_rebuild = False
        if not album_plan.candidates and (
            track_report.get("changed") or int(l1_report.get("operation_count", 0)) > 0
        ):
            rebuild_album_projects(conn, commit=False, ensure_schema=False)
            forced_album_rebuild = True
        for index, candidate in enumerate(album_plan.candidates):
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="album_project",
                action="merge_catalog_release",
                survivor_id=None,
                affected_ids=[int(value) for value in candidate.project_ids],
                before=album_before[index],
                after=_album_candidate_state(conn, candidate),
                evidence=asdict(candidate),
            )

        semantic_changed = bool(
            int(l1_report.get("operation_count", 0)) > 0 or track_report.get("changed")
        )
        if semantic_changed:
            revision_after = bump_track_identity_revision(conn)
        else:
            revision_after = revision_before
        track_report["track_identity_revision"] = revision_after
        track_report["revision_bumped"] = semantic_changed
        album_revision_after = int(
            conn.execute(
                "SELECT current_revision FROM album_project_revision_state WHERE state_id=1"
            ).fetchone()[0]
        )
        relation_gate = _relation_gate(conn, before_raw, identity_before)
        if relation_gate["status"] != "pass":
            raise RuntimeError(f"relation validation failed: {relation_gate}")
        relation_summary = {
            "l1": l1_report,
            "l1_audit": convergence_l1_plan.get("summary", {}),
            "track": track_report,
            "convergence": convergence,
            "album": asdict(album_report),
            "forced_album_rebuild": forced_album_rebuild,
            "track_identity_revision": {
                "before": revision_before,
                "after": revision_after,
                "delta": revision_after - revision_before,
            },
            "album_project_revision": {
                "before": album_revision_before,
                "after": album_revision_after,
                "delta": album_revision_after - album_revision_before,
            },
            "relation_validation": relation_gate,
        }
        conn.execute(
            "UPDATE version_governance_runs SET summary_json=? WHERE run_id=?",
            (
                json.dumps(
                    _merge_summary(initial_summary, **relation_summary),
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ),
                run_id,
            ),
        )
        conn.commit()

        changed = bool(
            semantic_changed or album_report.requires_downstream_refresh or forced_album_rebuild
        )
        stage = "derived_maintenance"
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
            pending_summary = _merge_summary(
                initial_summary,
                **relation_summary,
                derived={"status": "pending"},
            )
            conn.execute(
                "UPDATE version_governance_runs SET summary_json=? WHERE run_id=?",
                (
                    json.dumps(pending_summary, ensure_ascii=False, sort_keys=True, default=str),
                    run_id,
                ),
            )
            conn.commit()
            return {
                "mode": "apply",
                "governance_status": "pending_derived",
                "run_id": run_id,
                "policy_version": GOVERNANCE_POLICY_VERSION,
                "schema_version": _schema_version(conn),
                "backup_path": str(backup_path),
                **relation_summary,
                "derived": {"status": "pending"},
            }

        derived_report = rebuild_current_music_search_derived_data(
            conn,
            rebuild_documents=changed,
            atomic_snapshot_set=True,
        )
        derived_database = _derived_database_state(conn)
        final_validation = _relation_gate(conn, before_raw, identity_before)
        final_summary = {
            **initial_summary,
            **relation_summary,
            "derived": {
                "status": derived_report.get("status"),
                "snapshot_set": derived_report.get("snapshot_set"),
                "year_end_projection": derived_report.get("year_end_projection"),
                "database_state": derived_database,
            },
            "final_validation": final_validation,
        }
        success = (
            final_validation["status"] == "pass"
            and _derived_report_ready(derived_report)
            and derived_database["status"] == "ready"
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
            "governance_status": "applied",
            "run_id": run_id,
            "policy_version": GOVERNANCE_POLICY_VERSION,
            "schema_version": _schema_version(conn),
            "backup_path": str(backup_path),
            **final_summary,
        }
    except Exception as exc:
        conn.rollback()
        try:
            row = conn.execute(
                "SELECT summary_json FROM version_governance_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            persisted = json.loads(str(row[0])) if row is not None and row[0] else initial_summary
            failed_summary = _merge_summary(
                persisted,
                failure={"stage": stage, "error_type": type(exc).__name__},
            )
            conn.execute(
                """UPDATE version_governance_runs
                      SET status='failed', completed_at=CURRENT_TIMESTAMP,
                          summary_json=? WHERE run_id=?""",
                (
                    json.dumps(failed_summary, ensure_ascii=False, sort_keys=True, default=str),
                    run_id,
                ),
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

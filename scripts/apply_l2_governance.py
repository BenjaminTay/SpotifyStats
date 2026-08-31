#!/usr/bin/env python3
"""Plan or atomically apply machine-first version governance.

Dry-run is the default and never writes the source database. Apply mode makes
an online SQLite backup, performs only strongly evidenced L1 corrections,
reconciles L2 recording and L3 composition groups, maintains album relations,
records an audit run, and rebuilds all four exact music-search variants.
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
from backend.domains.metadata.l3_track_auto_merge import (  # noqa: E402
    L3_AUTO_MERGE_POLICY_VERSION,
    apply_l3_track_merge_plan,
    build_l3_track_merge_plan,
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
from backend.domains.playback.album_composition_auto_merge import (  # noqa: E402
    ALBUM_COMPOSITION_POLICY_VERSION,
    apply_album_composition_plan,
    plan_album_composition_merges,
)
from backend.domains.playback.album_project_auto_merge import (  # noqa: E402
    ALBUM_PROJECT_AUTO_IDENTITY_POLICY_VERSION,
    apply_album_project_auto_merge_plan,
    plan_album_project_auto_merges,
)
from backend.domains.playback.album_projects import rebuild_album_projects  # noqa: E402
from backend.domains.playback.l3_album_attribution import (  # noqa: E402
    L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
    apply_l3_album_attribution_plan,
    ensure_l3_album_attribution_schema,
    get_l3_album_attribution_state,
    plan_l3_album_attributions,
)
from backend.services.music_search_maintenance_service import (  # noqa: E402
    mark_music_search_for_rebuild,
    rebuild_current_music_search_derived_data,
)

GOVERNANCE_POLICY_VERSION = (
    f"version_governance_v2:{L2_AUTO_MERGE_POLICY_VERSION}:"
    f"{L3_AUTO_MERGE_POLICY_VERSION}:{ALBUM_PROJECT_AUTO_IDENTITY_POLICY_VERSION}:"
    f"{ALBUM_COMPOSITION_POLICY_VERSION}:{L3_ALBUM_ATTRIBUTION_POLICY_VERSION}"
)
RAW_FACT_TABLES = ("plays", "tracks", "track_artists")
EXPECTED_SEARCH_VARIANTS = {(2, 0), (2, 1), (3, 0), (3, 1)}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or apply automatic version governance")
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
    target = backup_dir / f"spotify_stats_{timestamp}_before-version-governance.db"
    if target.exists():
        target = (
            backup_dir
            / f"spotify_stats_{timestamp}_{uuid.uuid4().hex[:8]}_before-version-governance.db"
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


def _album_composition_plan_json(plan: Any) -> dict[str, Any]:
    return {
        "policy_version": plan.policy_version,
        "candidate_count": len(plan.candidates),
        "archive_group_ids": list(plan.archive_group_ids),
        "scanned_project_count": plan.scanned_project_count,
        "skipped_reason_counts": dict(plan.skipped_reason_counts),
        "candidates": [candidate.to_dict() for candidate in plan.candidates],
    }


def _l3_album_attribution_plan_json(plan: Any) -> dict[str, Any]:
    return {
        "policy_version": plan.policy_version,
        "track_identity_revision": plan.track_identity_revision,
        "album_project_revision": plan.album_project_revision,
        "input_digest": plan.input_digest,
        "scanned_song_count": plan.scanned_song_count,
        "decision_count": len(plan.decisions),
        "automatic_count": sum(
            item.decision_source == "automatic" for item in plan.decisions
        ),
        "manual_count": sum(item.decision_source == "manual" for item in plan.decisions),
        "excluded_count": len(plan.excluded_song_keys),
        "uncovered_count": len(plan.uncovered_song_keys),
        "conflict_count": len(plan.conflict_song_keys),
        "changed": plan.changed,
        "issues": [item.to_dict() for item in plan.issues],
        "exclusions": [item.to_dict() for item in plan.exclusions],
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
        l2_digest_before_l3 = _l2_relationship_digest(clone)
        composition_plan = build_l3_track_merge_plan(clone)
        composition_report = apply_l3_track_merge_plan(
            clone,
            composition_plan,
            commit=False,
            bump_revision=False,
        )
        l2_digest_after_l3 = _l2_relationship_digest(clone)
        l2_preserved_by_l3 = l2_digest_before_l3 == l2_digest_after_l3
        convergence_composition_plan = build_l3_track_merge_plan(clone)
        convergence["l3_changed"] = bool(convergence_composition_plan.get("changed"))
        convergence["l2_preserved_by_l3"] = l2_preserved_by_l3

        album_plan = plan_album_project_auto_merges(clone)
        album_report = apply_album_project_auto_merge_plan(
            clone,
            album_plan,
            commit=False,
            ensure_schema=False,
        )
        album_composition_plan = plan_album_composition_merges(clone)
        album_composition_report = apply_album_composition_plan(
            clone,
            album_composition_plan,
            commit=False,
            ensure_schema=False,
        )
        if (
            not album_plan.candidates
            and not album_composition_report.requires_downstream_refresh
            and (
                any(bool(item["report"].get("changed")) for item in l2_rounds)
                or bool(composition_report.get("changed"))
                or bool(all_operations)
            )
        ):
            rebuild_album_projects(clone, commit=False, ensure_schema=False)
        convergence_album_composition = plan_album_composition_merges(clone)
        convergence["album_l3_changed"] = bool(
            any(item.action != "unchanged" for item in convergence_album_composition.candidates)
            or convergence_album_composition.archive_group_ids
        )
        converged = bool(
            converged
            and l2_preserved_by_l3
            and not convergence["l3_changed"]
            and not convergence["album_l3_changed"]
        )
        semantic_changed = bool(
            any(bool(item["report"].get("changed")) for item in l2_rounds)
            or bool(composition_report.get("changed"))
            or bool(all_operations)
        )
        if semantic_changed:
            bump_track_identity_revision(clone)
        ensure_l3_album_attribution_schema(clone)
        attribution_plan = plan_l3_album_attributions(clone)
        attribution_report = apply_l3_album_attribution_plan(
            clone,
            attribution_plan,
            commit=False,
            ensure_schema=False,
        )
        convergence_attribution = plan_l3_album_attributions(clone)
        convergence["l3_album_attribution_changed"] = convergence_attribution.changed
        convergence["l3_album_attribution_issue_count"] = len(
            convergence_attribution.issues
        )
        converged = bool(
            converged
            and not convergence_attribution.changed
            and not convergence_attribution.issues
        )
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
            "album_apply_simulation": asdict(album_report),
            "composition": {
                **composition_plan,
                "apply_simulation": composition_report,
                "l2_relationship_digest_before": l2_digest_before_l3,
                "l2_relationship_digest_after": l2_digest_after_l3,
                "l2_relationships_preserved": l2_preserved_by_l3,
                "convergence": {
                    "changed": bool(convergence_composition_plan.get("changed")),
                    "groups_to_archive": len(
                        convergence_composition_plan.get("archived_group_ids", [])
                    ),
                },
            },
            "album_composition": {
                **_album_composition_plan_json(album_composition_plan),
                "apply_simulation": album_composition_report.to_dict(),
                "convergence": _album_composition_plan_json(convergence_album_composition),
            },
            "l3_album_attribution": {
                "plan": _l3_album_attribution_plan_json(attribution_plan),
                "apply_simulation": attribution_report.to_dict(),
                "convergence": _l3_album_attribution_plan_json(
                    convergence_attribution
                ),
            },
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
    scope: str = "recording",
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
                 WHERE groups.scope=? AND groups.group_status='active'
                 GROUP BY groups.group_id
                HAVING COUNT(DISTINCT members.l1_id)=?
                   AND SUM(members.l1_id IN ({placeholders}))=?
                 ORDER BY groups.group_id LIMIT 1""",
            (scope, len(members), *members, len(members)),
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


def _candidate_state(
    conn: sqlite3.Connection, left: int, right: int, *, scope: str = "recording"
) -> dict[str, Any]:
    row = conn.execute(
        """SELECT candidate_id, scope, original_l1_id, candidate_l1_id,
                  confidence, evidence_json, status
             FROM track_group_candidates
            WHERE scope=?
              AND MIN(original_l1_id, candidate_l1_id)=?
              AND MAX(original_l1_id, candidate_l1_id)=?""",
        (scope, min(left, right), max(left, right)),
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


def _album_composition_state(
    conn: sqlite3.Connection,
    *,
    group_id: int | None = None,
    album_ids: tuple[int, ...] | list[int] = (),
) -> dict[str, Any]:
    albums = sorted({int(value) for value in album_ids})
    resolved_group_id = int(group_id) if group_id is not None else None
    if resolved_group_id is None and albums:
        placeholders = ",".join("?" for _ in albums)
        row = conn.execute(
            f"""SELECT groups.group_id
                  FROM release_groups groups
                  JOIN release_group_members members ON members.group_id=groups.group_id
                 WHERE groups.scope='composition'
                 GROUP BY groups.group_id
                HAVING COUNT(DISTINCT members.album_id)=?
                   AND SUM(members.album_id IN ({placeholders}))=?
                 ORDER BY groups.group_id LIMIT 1""",
            (len(albums), *albums, len(albums)),
        ).fetchone()
        resolved_group_id = int(row[0]) if row is not None else None
    if resolved_group_id is None:
        return {"exists": False, "album_ids": albums}
    group = conn.execute(
        """SELECT group_id, canonical_name, artist_id, primary_album_id,
                  scope, parent_group_id, is_manual
             FROM release_groups WHERE group_id=?""",
        (resolved_group_id,),
    ).fetchone()
    if group is None:
        return {"exists": False, "group_id": resolved_group_id, "album_ids": albums}
    members = [
        int(row[0])
        for row in conn.execute(
            "SELECT album_id FROM release_group_members WHERE group_id=? ORDER BY album_id",
            (resolved_group_id,),
        ).fetchall()
    ]
    children = [
        int(row[0])
        for row in conn.execute(
            "SELECT group_id FROM release_groups WHERE parent_group_id=? ORDER BY group_id",
            (resolved_group_id,),
        ).fetchall()
    ]
    return {
        "exists": True,
        **dict(group),
        "album_ids": members,
        "child_release_group_ids": children,
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


def _composition_group_health(conn: sqlite3.Connection) -> dict[str, int]:
    overlap = int(
        conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT members.l1_id
                     FROM track_group_l1_members members
                     JOIN track_groups groups ON groups.group_id=members.group_id
                    WHERE groups.scope='composition' AND groups.group_status='active'
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
                    WHERE groups.scope='composition' AND groups.group_status='active'
                    GROUP BY groups.group_id
                   HAVING COUNT(DISTINCT members.l1_id)<2
               )"""
        ).fetchone()[0]
    )
    invalid_primary = int(
        conn.execute(
            """SELECT COUNT(*) FROM track_groups groups
                WHERE groups.scope='composition' AND groups.group_status='active'
                  AND (groups.primary_l1_id IS NULL OR NOT EXISTS (
                      SELECT 1 FROM track_group_l1_members members
                       WHERE members.group_id=groups.group_id
                         AND members.l1_id=groups.primary_l1_id
                  ))"""
        ).fetchone()[0]
    )
    invalid_recording_parent = int(
        conn.execute(
            """SELECT COUNT(*) FROM track_groups child
                LEFT JOIN track_groups parent ON parent.group_id=child.parent_group_id
               WHERE child.scope='recording' AND child.group_status='active'
                 AND child.parent_group_id IS NOT NULL
                 AND (parent.group_id IS NULL OR parent.scope!='composition'
                      OR parent.group_status!='active')"""
        ).fetchone()[0]
    )
    composition_parent_count = int(
        conn.execute(
            """SELECT COUNT(*) FROM track_groups
                WHERE scope='composition' AND group_status='active'
                  AND parent_group_id IS NOT NULL"""
        ).fetchone()[0]
    )
    incomplete_recording_parent_membership = int(
        conn.execute(
            """SELECT COUNT(*)
                 FROM track_groups child
                 JOIN track_group_l1_members child_member
                   ON child_member.group_id=child.group_id
                 LEFT JOIN track_group_l1_members parent_member
                   ON parent_member.group_id=child.parent_group_id
                  AND parent_member.l1_id=child_member.l1_id
                WHERE child.scope='recording' AND child.group_status='active'
                  AND child.parent_group_id IS NOT NULL
                  AND parent_member.l1_id IS NULL"""
        ).fetchone()[0]
    )
    parent_cycle_count = int(
        conn.execute(
            """WITH RECURSIVE chain(origin_group_id, current_group_id) AS (
                   SELECT group_id, parent_group_id
                     FROM track_groups WHERE parent_group_id IS NOT NULL
                   UNION
                   SELECT chain.origin_group_id, groups.parent_group_id
                     FROM chain
                     JOIN track_groups groups ON groups.group_id=chain.current_group_id
                    WHERE groups.parent_group_id IS NOT NULL
               )
               SELECT COUNT(DISTINCT origin_group_id)
                 FROM chain WHERE origin_group_id=current_group_id"""
        ).fetchone()[0]
    )
    return {
        "member_overlap_count": overlap,
        "undersized_active_group_count": too_small,
        "invalid_primary_count": invalid_primary,
        "invalid_recording_parent_count": invalid_recording_parent,
        "composition_parent_count": composition_parent_count,
        "incomplete_recording_parent_membership_count": incomplete_recording_parent_membership,
        "parent_cycle_count": parent_cycle_count,
    }


def _l2_relationship_digest(conn: sqlite3.Connection) -> str:
    """Hash only L2 semantics; composition parent pointers are intentionally excluded."""

    payload = {
        "groups": _rows_as_dicts(
            conn.execute(
                """SELECT group_id, canonical_name, primary_track_id, primary_l1_id,
                          is_manual, group_status, automatic_spotify_track_id,
                          automatic_artist_id, automatic_title_key,
                          automatic_version_tag, identity_policy_version
                     FROM track_groups
                    WHERE scope='recording' AND group_status='active'
                    ORDER BY group_id"""
            ).fetchall()
        ),
        "members": _rows_as_dicts(
            conn.execute(
                """SELECT members.group_id, members.l1_id
                     FROM track_group_l1_members members
                     JOIN track_groups groups ON groups.group_id=members.group_id
                    WHERE groups.scope='recording' AND groups.group_status='active'
                    ORDER BY members.group_id, members.l1_id"""
            ).fetchall()
        ),
        "candidates": _rows_as_dicts(
            conn.execute(
                """SELECT original_l1_id, candidate_l1_id, confidence,
                          evidence_json, status
                     FROM track_group_candidates
                    WHERE scope='recording'
                    ORDER BY MIN(original_l1_id, candidate_l1_id),
                             MAX(original_l1_id, candidate_l1_id)"""
            ).fetchall()
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _album_composition_health(conn: sqlite3.Connection) -> dict[str, int]:
    overlap = int(
        conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT members.album_id
                     FROM release_group_members members
                     JOIN release_groups groups ON groups.group_id=members.group_id
                    WHERE groups.scope='composition'
                    GROUP BY members.album_id
                   HAVING COUNT(DISTINCT groups.group_id)>1
               )"""
        ).fetchone()[0]
    )
    too_small = int(
        conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT groups.group_id
                     FROM release_groups groups
                     LEFT JOIN release_group_members members
                       ON members.group_id=groups.group_id
                    WHERE groups.scope='composition'
                    GROUP BY groups.group_id
                   HAVING COUNT(DISTINCT members.album_id)<2
               )"""
        ).fetchone()[0]
    )
    invalid_primary = int(
        conn.execute(
            """SELECT COUNT(*) FROM release_groups groups
                WHERE groups.scope='composition'
                  AND (groups.primary_album_id IS NULL OR NOT EXISTS (
                      SELECT 1 FROM release_group_members members
                       WHERE members.group_id=groups.group_id
                         AND members.album_id=groups.primary_album_id
                  ))"""
        ).fetchone()[0]
    )
    invalid_release_parent = int(
        conn.execute(
            """SELECT COUNT(*) FROM release_groups child
                LEFT JOIN release_groups parent ON parent.group_id=child.parent_group_id
               WHERE child.scope='release' AND child.parent_group_id IS NOT NULL
                 AND (parent.group_id IS NULL OR parent.scope!='composition')"""
        ).fetchone()[0]
    )
    composition_parent_count = int(
        conn.execute(
            """SELECT COUNT(*) FROM release_groups
                WHERE scope='composition' AND parent_group_id IS NOT NULL"""
        ).fetchone()[0]
    )
    incomplete_child_membership = int(
        conn.execute(
            """SELECT COUNT(*)
                 FROM release_groups child
                 JOIN release_group_members child_member
                   ON child_member.group_id=child.group_id
                 LEFT JOIN release_group_members parent_member
                   ON parent_member.group_id=child.parent_group_id
                  AND parent_member.album_id=child_member.album_id
                WHERE child.scope='release' AND child.parent_group_id IS NOT NULL
                  AND parent_member.album_id IS NULL"""
        ).fetchone()[0]
    )
    return {
        "member_overlap_count": overlap,
        "undersized_group_count": too_small,
        "invalid_primary_count": invalid_primary,
        "invalid_release_parent_count": invalid_release_parent,
        "composition_parent_count": composition_parent_count,
        "incomplete_child_membership_count": incomplete_child_membership,
    }


def _l3_album_attribution_health(conn: sqlite3.Connection) -> dict[str, int]:
    required = {
        "l3_song_album_attributions",
        "l3_song_album_attribution_issues",
        "l3_album_attribution_revision_state",
    }
    existing = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if not required.issubset(existing):
        return {"missing_schema_count": len(required - existing)}
    state = get_l3_album_attribution_state(conn)
    plan = plan_l3_album_attributions(conn)
    row_count = int(
        conn.execute("SELECT COUNT(*) FROM l3_song_album_attributions").fetchone()[0]
    )
    duplicate_count = int(
        conn.execute(
            """SELECT COUNT(*) FROM (
                   SELECT canonical_song_key
                     FROM l3_song_album_attributions
                    GROUP BY canonical_song_key HAVING COUNT(*)>1
               )"""
        ).fetchone()[0]
    )
    orphan_count = int(
        conn.execute(
            """SELECT COUNT(*)
                 FROM l3_song_album_attributions attribution
                 LEFT JOIN album_projects target
                   ON target.project_id=attribution.target_project_id
                 LEFT JOIN album_projects origin
                   ON origin.project_id=attribution.origin_release_project_id
                WHERE target.project_id IS NULL OR origin.project_id IS NULL"""
        ).fetchone()[0]
    )
    return {
        "not_ready_count": int(state["status"] != "ready"),
        "policy_mismatch_count": int(
            state["policy_version"] != L3_ALBUM_ATTRIBUTION_POLICY_VERSION
        ),
        "plan_changed_count": int(plan.changed),
        "unresolved_issue_count": len(plan.issues),
        "state_count_mismatch_count": int(
            int(state["attributed_count"]) != row_count
            or row_count != len(plan.decisions)
        ),
        "duplicate_owner_count": duplicate_count,
        "orphan_owner_count": orphan_count,
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
        "active_group_noncanonical_member_count",
        "active_group_too_small_count",
        "active_group_invalid_primary_count",
    }
    hard_identity_issues = {
        key: int(identity.get(key, 0))
        for key in hard_identity_keys
        if int(identity.get(key, 0)) > 0
    }
    recording = _recording_group_health(conn)
    composition = _composition_group_health(conn)
    album_composition = _album_composition_health(conn)
    l3_album_attribution = _l3_album_attribution_health(conn)
    integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    foreign_key_issues = len(conn.execute("PRAGMA foreign_key_check").fetchall())
    passed = bool(
        before_raw == after_raw
        and not hard_identity_issues
        and not identity_regressions
        and not any(recording.values())
        and not any(composition.values())
        and not any(album_composition.values())
        and not any(l3_album_attribution.values())
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
        "composition_groups": composition,
        "album_composition_groups": album_composition,
        "l3_album_attribution": l3_album_attribution,
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
            and int(item["year_count"] or 0) > 0
            and int(item["projection_row_count"] or 0) > 0
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


def _apply_l3_round(
    conn: sqlite3.Connection,
    *,
    run_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = build_l3_track_merge_plan(conn)
    group_before = {
        index: _recording_group_state(
            conn,
            group_id=group.get("target_group_id"),
            member_l1_ids=group.get("member_l1_ids"),
            scope="composition",
        )
        for index, group in enumerate(plan["groups"])
    }
    archived_before = {
        int(group_id): _recording_group_state(conn, group_id=int(group_id), scope="composition")
        for group_id in plan["archived_group_ids"]
    }
    decision_edges = [*plan["accepted_edges"], *plan["blocked_edges"]]
    candidate_before = {
        index: _candidate_state(
            conn,
            int(edge["left_l1_id"]),
            int(edge["right_l1_id"]),
            scope="composition",
        )
        for index, edge in enumerate(decision_edges)
    }
    report = apply_l3_track_merge_plan(
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
                scope="composition",
            )
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="composition_group",
                action=str(group["action"]),
                survivor_id=int(after["group_id"]) if after.get("exists") else None,
                affected_ids=[int(value) for value in group["member_l1_ids"]],
                before=group_before[index],
                after=after,
                evidence={
                    "policy_version": plan["policy_version"],
                    "title_key": group["base_title"],
                    "relation_tags": group["relation_tags"],
                    "recording_group_ids": group["recording_group_ids"],
                    "evidence_types": group["evidence_types"],
                },
            )
        for group_id in plan["archived_group_ids"]:
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="composition_group",
                action="archive",
                survivor_id=int(group_id),
                affected_ids=[],
                before=archived_before[int(group_id)],
                after=_recording_group_state(conn, group_id=int(group_id), scope="composition"),
                evidence={"policy_version": plan["policy_version"]},
            )
    for index, edge in enumerate(decision_edges):
        left = int(edge["left_l1_id"])
        right = int(edge["right_l1_id"])
        after = _candidate_state(conn, left, right, scope="composition")
        before = candidate_before[index]
        if before == after:
            continue
        status = str(after.get("status") or edge.get("status") or "accepted")
        _insert_event(
            conn,
            run_id=run_id,
            entity_type="composition_candidate",
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
    """Apply governance without leaking the selected database into the process."""

    original_db_path = db_mod.DB_PATH
    try:
        return _apply_with_db_path(args)
    finally:
        db_mod.DB_PATH = original_db_path


def _apply_with_db_path(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.resolve()
    backup_dir = (args.backup_dir or (PROJECT_ROOT / "data" / "backups")).resolve()
    backup_path = _online_backup(db_path, backup_dir)
    db_mod.DB_PATH = str(db_path)
    run_migrations()
    conn = _connect(db_path, readonly=False)
    # Legacy test/staging fixtures can declare a schema revision without
    # containing every table from that revision.  Ensure this additive schema
    # before opening the governed transaction; executescript must not run
    # inside the transaction because SQLite would commit it implicitly.
    ensure_l3_album_attribution_schema(conn)
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
           ) VALUES (?, 'l1+l2+l3+album_project+album_attribution', ?, 'running', 0, ?)""",
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

        l2_digest_before_l3 = _l2_relationship_digest(conn)
        composition_plan, composition_report = _apply_l3_round(conn, run_id=run_id)
        l2_digest_after_l3 = _l2_relationship_digest(conn)
        l2_preserved_by_l3 = l2_digest_before_l3 == l2_digest_after_l3
        if not l2_preserved_by_l3:
            raise RuntimeError("L3 reconciliation changed L2 recording semantics")
        convergence_composition_plan = build_l3_track_merge_plan(conn)
        convergence.update(
            {
                "l3_changed": bool(convergence_composition_plan.get("changed")),
                "l3_groups_to_archive": len(
                    convergence_composition_plan.get("archived_group_ids", [])
                ),
                "l2_preserved_by_l3": True,
            }
        )
        if convergence["l3_changed"]:
            raise RuntimeError(f"L3 governance did not converge: {convergence}")

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

        album_composition_plan = plan_album_composition_merges(conn)
        album_composition_before = [
            _album_composition_state(
                conn,
                group_id=album_composition_candidate.existing_group_id,
                album_ids=album_composition_candidate.album_ids,
            )
            for album_composition_candidate in album_composition_plan.candidates
        ]
        album_composition_archived_before = {
            int(group_id): _album_composition_state(conn, group_id=int(group_id))
            for group_id in album_composition_plan.archive_group_ids
        }
        album_composition_report = apply_album_composition_plan(
            conn,
            album_composition_plan,
            commit=False,
            ensure_schema=False,
        )
        for index, album_composition_candidate in enumerate(
            album_composition_plan.candidates
        ):
            if album_composition_candidate.action == "unchanged":
                continue
            after = _album_composition_state(
                conn, album_ids=album_composition_candidate.album_ids
            )
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="album_composition",
                action=str(album_composition_candidate.action),
                survivor_id=int(after["group_id"]) if after.get("exists") else None,
                affected_ids=[
                    int(value) for value in album_composition_candidate.album_ids
                ],
                before=album_composition_before[index],
                after=after,
                evidence=album_composition_candidate.to_dict(),
            )
        for group_id in album_composition_plan.archive_group_ids:
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="album_composition",
                action="archive",
                survivor_id=int(group_id),
                affected_ids=[],
                before=album_composition_archived_before[int(group_id)],
                after=_album_composition_state(conn, group_id=int(group_id)),
                evidence={
                    "policy_version": album_composition_plan.policy_version,
                    "automatic_ownership": True,
                },
            )
        if (
            not album_plan.candidates
            and not album_composition_report.requires_downstream_refresh
            and (
                track_report.get("changed")
                or composition_report.get("changed")
                or int(l1_report.get("operation_count", 0)) > 0
            )
        ):
            rebuild_album_projects(conn, commit=False, ensure_schema=False)
            forced_album_rebuild = True
        convergence_album_composition = plan_album_composition_merges(conn)
        album_l3_changed = bool(
            any(item.action != "unchanged" for item in convergence_album_composition.candidates)
            or convergence_album_composition.archive_group_ids
        )
        convergence["album_l3_changed"] = album_l3_changed
        if album_l3_changed:
            raise RuntimeError(f"Album L3 governance did not converge: {convergence}")

        semantic_changed = bool(
            int(l1_report.get("operation_count", 0)) > 0
            or track_report.get("changed")
            or composition_report.get("changed")
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
        attribution_before = get_l3_album_attribution_state(conn)
        attribution_plan = plan_l3_album_attributions(conn)
        if attribution_plan.issues:
            raise RuntimeError(
                "L3 album attribution has unresolved issues: "
                f"conflicts={len(attribution_plan.conflict_song_keys)}, "
                f"uncovered={len(attribution_plan.uncovered_song_keys)}"
            )
        attribution_report = apply_l3_album_attribution_plan(
            conn,
            attribution_plan,
            commit=False,
            ensure_schema=False,
        )
        convergence_attribution = plan_l3_album_attributions(conn)
        convergence["l3_album_attribution_changed"] = convergence_attribution.changed
        convergence["l3_album_attribution_issue_count"] = len(
            convergence_attribution.issues
        )
        if convergence_attribution.changed or convergence_attribution.issues:
            raise RuntimeError(
                "L3 album attribution governance did not converge: "
                f"changed={convergence_attribution.changed}, "
                f"issues={len(convergence_attribution.issues)}"
            )
        if attribution_report.changed:
            _insert_event(
                conn,
                run_id=run_id,
                entity_type="l3_album_attribution",
                action="publish_projection",
                survivor_id=None,
                affected_ids=[],
                before=attribution_before,
                after=get_l3_album_attribution_state(conn),
                evidence=_l3_album_attribution_plan_json(attribution_plan),
            )
        relation_gate = _relation_gate(conn, before_raw, identity_before)
        if relation_gate["status"] != "pass":
            raise RuntimeError(f"relation validation failed: {relation_gate}")
        relation_summary = {
            "l1": l1_report,
            "l1_audit": convergence_l1_plan.get("summary", {}),
            "track": track_report,
            "composition": {
                **composition_report,
                "plan": {
                    "policy_version": composition_plan["policy_version"],
                    "desired_group_count": composition_plan["desired_group_count"],
                    "groups_to_create": composition_plan["groups_to_create"],
                    "groups_to_update": composition_plan["groups_to_update"],
                    "groups_to_archive": composition_plan["groups_to_archive"],
                    "accepted_edge_count": len(composition_plan["accepted_edges"]),
                    "blocked_edge_count": len(composition_plan["blocked_edges"]),
                    "warning_reason_counts": composition_plan["warning_reason_counts"],
                },
                "l2_relationship_digest_before": l2_digest_before_l3,
                "l2_relationship_digest_after": l2_digest_after_l3,
                "l2_relationships_preserved": l2_preserved_by_l3,
            },
            "convergence": convergence,
            "album": asdict(album_report),
            "album_composition": {
                "plan": _album_composition_plan_json(album_composition_plan),
                "report": album_composition_report.to_dict(),
            },
            "l3_album_attribution": {
                "plan": _l3_album_attribution_plan_json(attribution_plan),
                "report": attribution_report.to_dict(),
                "convergence": _l3_album_attribution_plan_json(
                    convergence_attribution
                ),
            },
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
            semantic_changed
            or album_report.requires_downstream_refresh
            or album_composition_report.requires_downstream_refresh
            or attribution_report.requires_downstream_refresh
            or forced_album_rebuild
        )
        stage = "derived_maintenance"
        if changed:
            invalidate("analysis")
            invalidate("billboard")
            invalidate("yearly_review")
            mark_music_search_for_rebuild(
                reason=f"automatic version governance run {run_id}",
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

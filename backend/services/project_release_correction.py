"""Explicit source/date maintenance with owner-preserving, scoped publication.

The caller owns the transaction and the isolated database. Unlike automatic
same-year precision upgrades, these proposals may correct a legacy year.
"""

from __future__ import annotations

import json

from backend.domains.metadata.album_track_release_evidence import (
    _json,
    _now,
    read_assertion,
    require_transaction,
    review_assertion,
    source_guard,
    valid_assertion,
    validate_sources,
)
from backend.domains.metadata.release_dates import compare_release_dates, parse_release_date
from backend.domains.playback.album_projects import _bump_album_project_revision
from backend.domains.playback.l3_album_attribution import (
    L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
    _current_projection_digest,
    l3_album_attribution_dependencies_ready,
    plan_l3_album_attributions,
)


def _project(conn, project_id):
    cur = conn.execute("SELECT * FROM album_projects WHERE project_id=?", (project_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError("project_not_found")
    return dict(zip([col[0] for col in cur.description], row))


def _members(conn, project_id):
    return {
        table: [
            list(row)
            for row in conn.execute(
                f"SELECT * FROM {table} WHERE project_id=? ORDER BY 1,2", (project_id,)
            )
        ]
        for table in ("album_project_albums", "album_project_tracks")
    }


def prepare_release_correction(conn, request):
    """Read-only proposal; all protected values come from the actual baseline."""
    if not l3_album_attribution_dependencies_ready(conn):
        raise ValueError("exact_published_attribution_required")
    if not isinstance(request.get("request_id"), str) or not 1 <= len(request["request_id"]) <= 128:
        raise ValueError("bounded_request_id_required")
    if type(request.get("project_id")) is not int:
        raise ValueError("stable_project_id_required")
    if request.get("date_kind") != "original_release":
        raise ValueError("project_correction_requires_original_release")
    if parse_release_date(request.get("release_date"), "day").exact_day is None:
        raise ValueError("confirmed_project_day_required")
    for key in ("territory", "medium", "scope_note", "source_id"):
        if not isinstance(request.get(key), str) or not request[key].strip():
            raise ValueError(key + "_required")
    validate_sources(request.get("sources"))
    pid = request["project_id"]
    if conn.execute(
        "SELECT 1 FROM album_release_date_assertions WHERE project_id=? AND status='approved' "
        "AND date_kind='original_release' AND (release_date<>? OR spotify_album_id<>?)",
        (pid, request["release_date"], request["source_id"]),
    ).fetchone():
        raise ValueError("approved_original_date_requires_separate_review")
    guard, _ = source_guard(conn, pid, request["source_id"])
    if (
        compare_release_dates(
            parse_release_date(*guard["source_identity"][2:4]),
            parse_release_date(request["release_date"], "day"),
        )
        == "conflict"
    ):
        from backend.domains.metadata.release_dates import release_anchor_sources

        project = _project(conn, pid)
        reviewed = release_anchor_sources(conn, project["primary_album_id"], project_id=pid)
        if not any(
            row["spotify_album_id"] == request["source_id"]
            and row.get("release_date_assertion_id")
            and not row.get("independent_date_conflict")
            and row["release_date"] == request["release_date"]
            for row in reviewed
        ):
            raise ValueError("source_date_conflict_requires_explicit_date_review")
    plan = plan_l3_album_attributions(conn)
    scope = sorted(d.canonical_song_key for d in plan.decisions if pid in d.source_project_ids)
    if not scope:
        raise ValueError("project_has_no_attributed_scope")
    decisions = {d.canonical_song_key: d for d in plan.decisions}
    tracks = request.get("preserve_track_ids", [])
    assertion_ids = request.get("assertion_ids", [])
    if not isinstance(tracks, list) or len(tracks) > 100 or any(type(t) is not int for t in tracks):
        raise ValueError("bounded_preservation_scope_required")
    if (
        not isinstance(assertion_ids, list)
        or len(assertion_ids) > 100
        or any(type(i) is not int for i in assertion_ids)
    ):
        raise ValueError("bounded_assertion_scope_required")
    preserves = []
    for track in sorted(set(tracks)):
        rows = conn.execute(
            "SELECT canonical_song_key,target_project_id FROM l3_song_album_attributions "
            "WHERE representative_track_id=?",
            (track,),
        ).fetchall()
        if len(rows) != 1 or rows[0][0] not in scope:
            raise ValueError("preservation_anchor_outside_scope")
        preserves.append(
            {
                "anchor_track_id": track,
                "canonical_song_key": rows[0][0],
                "target_project_id": rows[0][1],
            }
        )
    assertions = []
    project_tracks = {
        row[0]
        for row in conn.execute(
            "SELECT track_id FROM album_project_tracks WHERE project_id=?", (pid,)
        )
    }
    related_projects = {project for key in scope for project in decisions[key].source_project_ids}
    for assertion_id in sorted(set(assertion_ids)):
        row = read_assertion(conn, assertion_id)
        if (
            row["project_id"] not in related_projects
            or row["anchor_track_id"] not in project_tracks
        ):
            raise ValueError("assertion_outside_correction_scope")
        if row["status"] != "pending":
            raise ValueError("pending_assertion_required")
        assertions.append(row)
    return {
        "request": request,
        "expected_project": _project(conn, pid),
        "expected_members": _members(conn, pid),
        "source_guard": guard,
        "scope": scope,
        "preserve_owners": preserves,
        "assertions": assertions,
        "expected_plan_digest": plan.input_digest,
        "expected_published_digest": _current_projection_digest(conn),
    }


def _publish_scope(conn, before, after, scope):
    """Carry unchanged dependencies forward; never adopt unrelated planner drift."""
    if plan_l3_album_attributions(conn) != after:
        raise ValueError("stale_scoped_attribution_plan")
    old = {d.canonical_song_key: d for d in before.decisions}
    new = {d.canonical_song_key: d for d in after.decisions}
    if old.keys() != new.keys():
        raise ValueError("correction_changed_song_inventory")
    for key in old.keys() - scope:
        if old[key] != new[key]:
            raise ValueError("correction_escaped_scope:" + key)
    for field in (
        "issues",
        "exclusions",
        "uncovered_song_keys",
        "conflict_song_keys",
        "excluded_song_keys",
        "scanned_song_count",
    ):
        if getattr(before, field) != getattr(after, field):
            raise ValueError("correction_changed_attribution_" + field)
    cur = conn.execute("SELECT * FROM l3_song_album_attributions")
    columns = [col[0] for col in cur.description]
    published = {row[0]: dict(zip(columns, row)) for row in cur.fetchall()}
    if set(published) != new.keys():
        raise ValueError("published_inventory_differs_from_plan")
    for key in scope:
        decision = new[key]
        previous = published[key]
        for field in (
            "target_project_id",
            "origin_release_project_id",
            "representative_track_id",
            "canonical_artist_key",
            "attribution_kind",
        ):
            if previous[field] != getattr(decision, field):
                raise ValueError("unapproved_attribution_change:" + key + ":" + field)
        evidence = {
            "canonical_song_name": decision.canonical_song_name,
            "target_project_name": decision.target_project_name,
            "origin_project_name": decision.origin_project_name,
            "source_project_ids": decision.source_project_ids,
            "candidate_project_ids": decision.candidate_project_ids,
            "evidence_codes": decision.evidence_codes,
            "evidence": dict(decision.evidence),
        }
        conn.execute(
            "UPDATE l3_song_album_attributions SET decision_source=?,confidence=?,evidence_json=?,updated_at=CURRENT_TIMESTAMP "
            "WHERE canonical_song_key=?",
            (
                decision.decision_source,
                decision.confidence,
                json.dumps(evidence, ensure_ascii=False, sort_keys=True, default=str),
                key,
            ),
        )
    # A complete before/after plan proves every non-scope input decision is
    # unchanged. Only the shared upstream watermark is advanced for those rows.
    for table in (
        "l3_song_album_attributions",
        "l3_song_album_attribution_issues",
        "l3_song_album_attribution_exclusions",
    ):
        conn.execute(
            f"UPDATE {table} SET album_project_revision=?", (after.album_project_revision,)
        )
    conn.execute(
        "UPDATE l3_album_attribution_revision_state SET current_revision=current_revision+1,"
        "album_project_revision=?,mapping_digest=?,updated_at=CURRENT_TIMESTAMP WHERE state_id=1",
        (after.album_project_revision, _current_projection_digest(conn)),
    )
    if (
        after.policy_version != L3_ALBUM_ATTRIBUTION_POLICY_VERSION
        or not l3_album_attribution_dependencies_ready(conn)
    ):
        raise ValueError("scoped_publication_not_ready")


def apply_release_correction(conn, proposal, *, actor, reason):
    """Apply exactly one fenced proposal; caller must explicitly commit it."""
    require_transaction(conn, actor, reason)
    request = proposal["request"]
    pid = request["project_id"]
    prior = conn.execute(
        "SELECT request_json,result_json FROM album_release_corrections WHERE request_id=?",
        (request["request_id"],),
    ).fetchone()
    if prior:
        if prior[0] != _json(proposal):
            raise ValueError("request_id_reused_with_different_proposal")
        current = _project(conn, pid)
        if [current["release_date"], current["release_date_precision"]] != [
            request["release_date"],
            "day",
        ]:
            raise ValueError("applied_project_date_changed")
        if source_guard(conn, pid, request["source_id"])[0] != proposal[
            "source_guard"
        ] or not l3_album_attribution_dependencies_ready(conn):
            raise ValueError("applied_correction_dependencies_changed")
        binding = conn.execute(
            "SELECT project_id,is_primary FROM album_project_external_ids WHERE provider='spotify' AND external_album_id=?",
            (request["source_id"],),
        ).fetchone()
        if not binding or tuple(binding) != (pid, 1):
            raise ValueError("applied_primary_source_changed")
        if _members(conn, pid) != proposal["expected_members"]:
            raise ValueError("applied_project_members_changed")
        for assertion in proposal["assertions"]:
            active = read_assertion(conn, assertion["assertion_id"])
            if active["status"] != "approved" or not valid_assertion(conn, active):
                raise ValueError("applied_membership_evidence_changed")
        for preserve in proposal["preserve_owners"]:
            row = conn.execute(
                "SELECT target_project_id FROM l3_song_album_attributions WHERE canonical_song_key=?",
                (preserve["canonical_song_key"],),
            ).fetchone()
            override = conn.execute(
                "SELECT target_project_id FROM l3_song_album_attribution_overrides WHERE anchor_track_id=? AND active=1",
                (preserve["anchor_track_id"],),
            ).fetchone()
            if (
                not row
                or not override
                or row[0] != preserve["target_project_id"]
                or override[0] != row[0]
            ):
                raise ValueError("applied_owner_preservation_changed")
        return {**json.loads(prior[1]), "idempotent": True}
    if prepare_release_correction(conn, request) != proposal:
        raise ValueError("stale_release_correction_proposal")
    before = plan_l3_album_attributions(conn)
    conn.execute("SAVEPOINT explicit_release_correction")
    try:
        source = conn.execute(
            "SELECT project_id FROM album_project_external_ids WHERE provider='spotify' AND external_album_id=?",
            (request["source_id"],),
        ).fetchone()
        if source and source[0] != pid:
            raise ValueError("source_owned_by_another_project")
        conn.execute(
            "UPDATE album_project_external_ids SET is_primary=0 WHERE project_id=? AND provider='spotify'",
            (pid,),
        )
        if source:
            conn.execute(
                "UPDATE album_project_external_ids SET is_primary=1 WHERE provider='spotify' AND external_album_id=?",
                (request["source_id"],),
            )
        else:
            conn.execute(
                "INSERT INTO album_project_external_ids(provider,external_album_id,project_id,evidence_type,confidence,is_primary) VALUES('spotify',?,?,'reviewed_release_correction',1,1)",
                (request["source_id"], pid),
            )
        conn.execute(
            "UPDATE album_projects SET release_date=?,release_date_precision='day' WHERE project_id=?",
            (request["release_date"], pid),
        )
        for preserve in proposal["preserve_owners"]:
            override = conn.execute(
                "SELECT target_project_id FROM l3_song_album_attribution_overrides WHERE anchor_track_id=? AND active=1",
                (preserve["anchor_track_id"],),
            ).fetchone()
            if override and override[0] != preserve["target_project_id"]:
                raise ValueError("existing_manual_owner_conflicts")
            if not override:
                conn.execute(
                    "INSERT INTO l3_song_album_attribution_overrides(anchor_track_id,target_project_id,action,reason) VALUES(?,?,'force_target',?)",
                    (preserve["anchor_track_id"], preserve["target_project_id"], reason),
                )
        for row in proposal["assertions"]:
            if read_assertion(conn, row["assertion_id"]) != row:
                raise ValueError("assertion_changed")
            review_assertion(conn, row["assertion_id"], "approve", actor=actor, reason=reason)
        _bump_album_project_revision(conn)
        after = plan_l3_album_attributions(conn)
        _publish_scope(conn, before, after, set(proposal["scope"]))
        if _members(conn, pid) != proposal["expected_members"]:
            raise ValueError("project_members_changed")
        result = {
            "request_id": request["request_id"],
            "project_id": pid,
            "project_date_before": [
                proposal["expected_project"]["release_date"],
                proposal["expected_project"]["release_date_precision"],
            ],
            "project_date_after": [request["release_date"], "day"],
            "source_id": request["source_id"],
            "scope": proposal["scope"],
            "preserve_owners": proposal["preserve_owners"],
            "owner_changes": 0,
            "members_changed": False,
            "requires_downstream_refresh": True,
            "published_revision": after.album_project_revision,
            "idempotent": False,
        }
        conn.execute(
            "INSERT INTO album_release_corrections(request_id,request_json,result_json,actor,reason,created_at) VALUES(?,?,?,?,?,?)",
            (request["request_id"], _json(proposal), _json(result), actor, reason, _now()),
        )
        conn.execute("RELEASE SAVEPOINT explicit_release_correction")
        return result
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT explicit_release_correction")
        conn.execute("RELEASE SAVEPOINT explicit_release_correction")
        raise

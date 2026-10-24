"""Atomic review with complete before/after attribution and published-owner fences."""

from backend.domains.metadata.album_release_date_evidence import approve_date_conflict
from backend.domains.metadata.album_release_references import review_reference
from backend.domains.metadata.album_track_release_evidence import require_transaction
from backend.domains.playback.l3_album_attribution import (
    l3_album_attribution_dependencies_ready,
    plan_l3_album_attributions,
)
from backend.services.project_release_correction import _publish_scope


def review_release_evidence(conn, *, references=(), date_conflicts=(), actor, reason, run_id):
    """All-or-nothing review; reject any changed target/origin/kind, including preexisting drift."""
    require_transaction(conn, actor, reason)
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id_required")
    if not 1 <= len(references) + len(date_conflicts) <= 50:
        raise ValueError("bounded_review_batch_required")
    if not l3_album_attribution_dependencies_ready(conn):
        raise ValueError("exact_published_attribution_required")
    before = plan_l3_album_attributions(conn)
    project_ids = {p["assertion"]["project_id"] for p in date_conflicts}
    for reference_id, _ in references:
        row = conn.execute(
            "SELECT project_id FROM album_release_references WHERE reference_id=?", (reference_id,)
        ).fetchone()
        if row is None:
            raise ValueError("reference_not_found")
        project_ids.add(row[0])
    scope = {
        d.canonical_song_key
        for d in before.decisions
        if project_ids.intersection(d.source_project_ids)
    }
    conn.execute("SAVEPOINT release_evidence_review")
    try:
        changed = 0
        for reference_id, decision in references:
            changed += review_reference(conn, reference_id, decision, actor=actor, reason=reason)
        for proposal in date_conflicts:
            changed += approve_date_conflict(
                conn, proposal, actor=actor, reason=reason, run_id=run_id
            )
        if changed:
            after = plan_l3_album_attributions(conn)
            # Check every published song, including origin and representative;
            # never publish a whole fresh plan to silently adopt old drift.
            _publish_scope(conn, before, after, scope)
        conn.execute("RELEASE SAVEPOINT release_evidence_review")
        return {"changed": changed, "owner_changes": 0, "members_changed": False}
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT release_evidence_review")
        conn.execute("RELEASE SAVEPOINT release_evidence_review")
        raise

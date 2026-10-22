"""Register/review independent album dates on an explicit database copy.

Without --apply all changes run on a temporary disk backup and are discarded.
Source dates, album memberships and published song ownership are never rewritten.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.core import db  # noqa: E402
from backend.core.migrations import migrate_094  # noqa: E402
from backend.domains.metadata.album_release_date_evidence import (  # noqa: E402
    record_assertion,
    review_assertion,
)
from backend.domains.playback.l3_album_attribution import (  # noqa: E402
    _current_projection_digest,
    l3_album_attribution_dependencies_ready,
    plan_l3_album_attributions,
)


def review_batch(conn, ids, action, *, actor, reason, run_id):
    """Atomic publication guard: preserve all owners, reject attribution side effects."""
    if action == "reject":
        return {
            "changed": sum(
                review_assertion(conn, i, action, actor=actor, reason=reason, run_id=run_id)
                for i in ids
            ),
            "owner_changes": 0,
            "decision_evidence_changes": 0,
        }
    if not l3_album_attribution_dependencies_ready(conn):
        raise ValueError("L3 dependencies must be ready before date review")
    before = plan_l3_album_attributions(conn)
    changed = sum(
        review_assertion(conn, i, action, actor=actor, reason=reason, run_id=run_id) for i in ids
    )
    if not changed:
        return {"changed": changed, "owner_changes": 0, "decision_evidence_changes": 0}
    after = plan_l3_album_attributions(conn)
    old = {d.canonical_song_key: asdict(d) for d in before.decisions}
    new = {d.canonical_song_key: asdict(d) for d in after.decisions}
    if old.keys() != new.keys():
        raise ValueError("date review changed the canonical song inventory")
    owners = [key for key in old if old[key]["target_project_id"] != new[key]["target_project_id"]]
    if owners:
        raise ValueError("date review would change song ownership: " + ",".join(owners[:20]))
    for key in old:
        a = {k: v for k, v in old[key].items() if k != "evidence"}
        b = {k: v for k, v in new[key].items() if k != "evidence"}
        if a != b:
            raise ValueError("date review changed attribution semantics: " + key)
    for field in (
        "issues",
        "exclusions",
        "uncovered_song_keys",
        "conflict_song_keys",
        "excluded_song_keys",
        "scanned_song_count",
    ):
        if getattr(before, field) != getattr(after, field):
            raise ValueError("date review changed attribution " + field)
    revision = conn.execute(
        "SELECT current_revision FROM album_project_revision_state WHERE state_id=1"
    ).fetchone()[0]
    # Retain published decisions; do not adopt unrelated planner drift.
    for table in (
        "l3_song_album_attributions",
        "l3_song_album_attribution_issues",
        "l3_song_album_attribution_exclusions",
    ):
        conn.execute(f"UPDATE {table} SET album_project_revision=?", (revision,))
    conn.execute(
        "UPDATE l3_album_attribution_revision_state SET current_revision=current_revision+1,album_project_revision=?,mapping_digest=?,updated_at=CURRENT_TIMESTAMP WHERE state_id=1",
        (revision, _current_projection_digest(conn)),
    )
    if not l3_album_attribution_dependencies_ready(conn):
        raise ValueError("date review did not preserve L3 readiness")
    return {
        "changed": changed,
        "owner_changes": 0,
        "decision_evidence_changes": sum(old[k] != new[k] for k in old),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument(
        "--action", choices=("list", "stage", "approve", "reject", "revoke"), required=True
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--assertion-ids", type=int, nargs="+")
    parser.add_argument("--actor")
    parser.add_argument("--run-id")
    parser.add_argument("--reason")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    source = args.db_path.resolve(strict=True)
    configured = Path(db.DB_PATH).resolve()
    if args.apply and (
        source == configured or (configured.exists() and source.samefile(configured))
    ):
        parser.error("Writes require an isolated database copy; configured source is forbidden")
    if args.action != "list" and (not args.actor or not args.run_id):
        parser.error("--actor and --run-id are required for evidence mutations")
    if args.action not in ("list", "stage") and not args.reason:
        parser.error("--reason is required for a review decision")
    if args.action in ("stage", "approve") and args.manifest:
        items = json.loads(args.manifest.read_text())["items"]
        if not 1 <= len(items) <= 50:
            parser.error("Manifest requires 1..50 explicit assertions")
    else:
        items = []
    if args.action == "stage" and not items:
        parser.error("Stage requires --manifest")
    if args.action not in ("list", "stage") and not (items or args.assertion_ids):
        parser.error("Review requires --assertion-ids or an explicit approval manifest")
    if args.assertion_ids and not 1 <= len(set(args.assertion_ids)) <= 50:
        parser.error("Review requires 1..50 distinct assertions")
    with tempfile.TemporaryDirectory(prefix="spotify-date-preview-") as temporary:
        if args.action == "list":
            conn = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
        elif args.apply:
            conn = sqlite3.connect(source)
        else:
            ro = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
            conn = sqlite3.connect(Path(temporary) / "preview.db")
            ro.backup(conn)
            ro.close()
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            if args.action == "list":
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='album_release_date_assertions'"
                ).fetchone()
                result = {
                    "status": "read_only",
                    "assertions": [
                        dict(r)
                        for r in conn.execute(
                            "SELECT * FROM album_release_date_assertions ORDER BY assertion_id"
                        )
                    ]
                    if exists
                    else [],
                }
            else:
                with conn:
                    conn.execute("BEGIN IMMEDIATE")
                    if not conn.execute(
                        "SELECT 1 FROM schema_migrations WHERE version=93"
                    ).fetchone():
                        raise ValueError("schema93 migration baseline required")
                    migrate_094(conn)
                    conn.execute(
                        "INSERT OR IGNORE INTO schema_migrations(version,name) VALUES(94,'independent_album_release_date_evidence')"
                    )
                    # Match run_migrations' finalizers before publishing ready
                    # consumers. The governance schema marker must be written last.
                    from backend.domains.metadata.governance_revision import (
                        install_revision_tracking as install_governance,
                    )
                    from backend.services.analysis_snapshot_revision import (
                        install_revision_tracking as install_analysis,
                    )

                    install_analysis(conn)
                    install_governance(conn)
                    ids = [
                        record_assertion(conn, item, actor=args.actor, run_id=args.run_id)
                        for item in items
                    ] or args.assertion_ids
                    review = (
                        review_batch(
                            conn,
                            ids,
                            args.action,
                            actor=args.actor,
                            reason=args.reason,
                            run_id=args.run_id,
                        )
                        if args.action != "stage"
                        else {"changed": 0}
                    )
                    result = {
                        "status": "applied_to_copy" if args.apply else "preview_only",
                        "action": args.action,
                        "assertion_ids": ids,
                        "review": review,
                        "source_statements_changed": False,
                        "members_changed": False,
                    }
                    if conn.execute("PRAGMA foreign_key_check").fetchone():
                        raise ValueError("foreign key integrity failed")
        finally:
            conn.close()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "assertions"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

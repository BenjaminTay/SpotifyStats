"""Review explicit references/date conflicts on an Online Backup; never write the input DB."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.core.migrations import migrate_096  # noqa: E402
from backend.domains.metadata import album_release_date_evidence as dates  # noqa: E402
from backend.domains.metadata.album_release_references import record_reference  # noqa: E402
from backend.services.release_evidence_review import review_release_evidence  # noqa: E402


def preview(conn, manifest, *, actor, reason, run_id):
    references, conflicts = manifest.get("references", []), manifest.get("date_conflicts", [])
    if (
        not isinstance(references, list)
        or not isinstance(conflicts, list)
        or not 1 <= len(references) + len(conflicts) <= 50
    ):
        raise ValueError("manifest_requires_1_to_50_explicit_items")
    ids = [record_reference(conn, i, actor=actor, reason=reason) for i in references]
    reference_result = (
        review_release_evidence(
            conn,
            references=[(i, "approve") for i in ids],
            actor=actor,
            reason=reason,
            run_id=run_id,
        )
        if ids
        else {"changed": 0}
    )
    proposals = [
        dates.prepare_date_conflict(
            conn, dates.record_assertion(conn, i, actor=actor, run_id=run_id)
        )
        for i in conflicts
    ]
    result = (
        review_release_evidence(
            conn, date_conflicts=proposals, actor=actor, reason=reason, run_id=run_id
        )
        if proposals
        else {"changed": 0}
    )
    result["changed"] += reference_result["changed"]
    return {"review": result, "reference_ids": ids, "date_conflict_proposals": proposals}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    source, manifest, output = (
        args.db_path.resolve(strict=True),
        args.manifest.resolve(strict=True),
        args.output.resolve(),
    )
    if output.suffix != ".json" or output in (source, manifest) or output.exists():
        parser.error("output must be a new, separate JSON evidence file")
    payload = json.loads(manifest.read_text())
    with tempfile.TemporaryDirectory(prefix="release-evidence-preview-") as temporary:
        reader = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
        conn = sqlite3.connect(Path(temporary) / "preview.db")
        try:
            reader.backup(conn)
        finally:
            reader.close()
        conn.row_factory = sqlite3.Row
        try:
            if conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] not in (
                95,
                96,
            ):
                raise ValueError("schema95_or96_baseline_required")
            conn.execute("PRAGMA foreign_keys=ON")
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                migrate_096(conn)
                result = preview(
                    conn, payload, actor=args.actor, reason=args.reason, run_id=args.run_id
                )
                if conn.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("foreign_key_violations")
        finally:
            conn.close()
    output.write_text(
        json.dumps(
            {"status": "preview_passed", "source_database_written": False, **result},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    output.chmod(0o600)
    print(
        json.dumps(
            {"status": "preview_passed", "source_database_written": False, **result["review"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

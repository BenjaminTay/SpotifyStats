"""Preview an explicit project-date correction; writes only to an isolated copy.

Prepare reads a request manifest, exercises the complete transaction on an
Online Backup, and emits a fenced proposal. Apply accepts that exact proposal
and refuses the configured database (including hard links and symlinks).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.core import db  # noqa: E402
from backend.core.access_surface import (  # noqa: E402
    reset_public_readonly_db_guard,
    set_public_readonly_db_guard,
)
from backend.core.migrations import MIGRATIONS, _ensure_migrations_table  # noqa: E402
from backend.services.project_release_correction import (  # noqa: E402
    apply_release_correction,
    prepare_release_correction,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--mode", choices=("prepare", "apply"), default="prepare")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    source = args.db_path.resolve(strict=True)
    configured = Path(db.DB_PATH).resolve()
    if args.mode == "apply" and (
        source == configured or (configured.exists() and source.samefile(configured))
    ):
        parser.error("Apply requires an isolated copy; configured database is forbidden")
    output = args.output.resolve()
    if output.suffix != ".json" or output in (source, args.manifest.resolve()):
        parser.error("Output must be a separate JSON evidence file")
    payload = json.loads(args.manifest.read_text())
    guard_token = set_public_readonly_db_guard(True)
    try:
        with tempfile.TemporaryDirectory(prefix="project-release-correction-") as temporary:
            target = source if args.mode == "apply" else Path(temporary) / "preview.db"
            if args.mode == "prepare":
                reader = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
                writer = sqlite3.connect(target)
                try:
                    reader.backup(writer)
                finally:
                    reader.close()
                    writer.close()
            conn = sqlite3.connect(target)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("BEGIN IMMEDIATE")
                _ensure_migrations_table(conn)
                applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
                for version, name, migrate in sorted(MIGRATIONS):
                    if version in (94, 95) and version not in applied:
                        migrate(conn)
                        conn.execute(
                            "INSERT INTO schema_migrations(version,name) VALUES(?,?)",
                            (version, name),
                        )
                proposal = (
                    prepare_release_correction(conn, payload)
                    if args.mode == "prepare"
                    else payload.get("proposal", payload)
                )
                result = apply_release_correction(
                    conn, proposal, actor=args.actor, reason=args.reason
                )
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise ValueError("foreign_key_violations")
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    finally:
        reset_public_readonly_db_guard(guard_token)
    evidence = {
        "status": "preview_passed" if args.mode == "prepare" else "applied_to_isolated_copy",
        "configured_database_written": False,
        "proposal": proposal,
        "result": result,
    }
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    output.chmod(0o600)
    print(
        json.dumps(
            {key: value for key, value in evidence.items() if key != "proposal"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()

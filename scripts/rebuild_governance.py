#!/usr/bin/env python3
"""Explicit local Governance backfill; never invoked by page reads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", required=True, type=Path, help="Existing local database to maintain"
    )
    parser.add_argument("--cache", type=Path, help="Governance sidecar (defaults beside --db)")
    parser.add_argument(
        "--install-revisions",
        action="store_true",
        help="Install/repair local Governance revision tracking before rebuilding",
    )
    parser.add_argument(
        "--filters-json", default="{}", help="Governance filter overrides as a JSON object"
    )
    parser.add_argument("--families", default="", help="Optional comma-separated family subset")
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error("--db must name an existing database")
    from backend.core import config, db
    from backend.domains.metadata.governance_revision import install_revision_tracking
    from backend.services.governance_snapshot_service import ensure

    db.DB_PATH = str(args.db.resolve())
    if args.cache:
        config.SPOTIFY_STATS_GOVERNANCE_CACHE_PATH = str(args.cache.resolve())
    from backend.core.migrations import run_migrations

    run_migrations()
    if args.install_revisions:
        conn = db.get_db(readonly=False)
        try:
            with conn:
                install_revision_tracking(conn)
        finally:
            conn.close()
    conn = db.get_db(readonly=True)
    try:
        print(
            json.dumps(
                ensure(
                    conn,
                    json.loads(args.filters_json),
                    args.families.split(",") if args.families else None,
                ),
                ensure_ascii=False,
            )
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Rebuild the active search index and all six exact context variants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db as db_mod  # noqa: E402
from backend.core.db import get_db  # noqa: E402
from backend.core.migrations import run_migrations  # noqa: E402
from backend.services.music_search_maintenance_service import (  # noqa: E402
    rebuild_current_music_search_derived_data,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild music-search documents and the six-variant snapshot set"
    )
    parser.add_argument("--db-path", type=Path, default=Path(db_mod.DB_PATH))
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Reuse a current document generation when its source revision matches",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--require-all-ready",
        action="store_true",
        help="Exit non-zero unless all six supported variants are ready",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = args.db_path.expanduser().resolve()
    if not db_path.is_file():
        print("music-search derived rebuild failed: database not found", file=sys.stderr)
        return 2
    db_mod.DB_PATH = str(db_path)
    run_migrations()
    conn = get_db(readonly=False)
    try:
        report = rebuild_current_music_search_derived_data(
            conn,
            rebuild_documents=not args.snapshot_only,
        )
    except Exception as exc:
        print(f"music-search derived rebuild failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    snapshot_set = report["snapshot_set"]
    if args.json:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    else:
        print(
            "Music-search derived data ready: "
            f"ready={snapshot_set['ready_count']} failed={snapshot_set['failed_count']} "
            f"base={snapshot_set['semantic_base_key'][:12]} "
            f"duration_ms={snapshot_set['duration_ms']}"
        )
        for variant in snapshot_set["variants"]:
            print(
                "  "
                f"L{variant['merge_level']} dynamic={str(variant['dynamic_threshold']).lower()} "
                f"status={variant['status']} entities={variant['entity_count']} "
                f"duration_ms={variant['duration_ms']}"
            )
    if args.require_all_ready and snapshot_set["failed_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Rebuild and atomically publish the local derived music-search index."""

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
from backend.domains.music_search.index import rebuild_music_search_index  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild the derived music-search index")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(db_mod.DB_PATH),
        help="SQLite database to update (defaults to the application database)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the non-sensitive rebuild report as JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = args.db_path.expanduser().resolve()
    if not db_path.is_file():
        print("music-search index rebuild failed: database not found", file=sys.stderr)
        return 2
    db_mod.DB_PATH = str(db_path)
    run_migrations()
    conn = get_db(readonly=False)
    try:
        report = rebuild_music_search_index(conn)
    except Exception as exc:
        print(f"music-search index rebuild failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    if args.json:
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    else:
        print(
            "Music-search index ready: "
            f"status={report['status']} documents={report['document_count']} "
            f"tokenizer={report['tokenizer']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

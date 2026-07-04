#!/usr/bin/env python3
"""Review AI-suggested artist genre source rows."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db
from backend.domains.metadata.artist_genre_review import list_reviews, review_suggestion


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="review_artist_genre_suggestions.py",
        description="List, approve, or reject artist genre review queue items.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List review queue items.")
    list_parser.add_argument("--status", default="open", help="Queue status to list.")
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum rows to return.")
    list_parser.add_argument("--json-output", type=Path)

    for command in ("approve", "reject"):
        action_parser = subparsers.add_parser(command, help=f"{command} one review item.")
        action_parser.add_argument("review_id", type=int)
        action_parser.add_argument("--json-output", type=Path)

    return parser.parse_args(argv)


def write_json_report(report: Any, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    readonly = args.command == "list"
    conn = get_db(readonly=readonly)
    report: list[dict[str, Any]] | dict[str, Any]
    try:
        if args.command == "list":
            report = list_reviews(conn, status=args.status, limit=args.limit)
        else:
            report = review_suggestion(
                conn,
                review_id=args.review_id,
                decision=args.command,
            )
    except Exception as exc:
        print(f"review_artist_genre_suggestions.py failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    if args.json_output:
        write_json_report(report, args.json_output)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

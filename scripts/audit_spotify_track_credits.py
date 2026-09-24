#!/usr/bin/env python3
"""Read-only Spotify provider credit comparison report."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import DB_PATH  # noqa: E402
from backend.domains.metadata.spotify_track_credits import (  # noqa: E402
    audit_track_credit_evidence,
    credit_evidence_coverage,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path(DB_PATH))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    conn = sqlite3.connect(f"{args.db_path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        report = audit_track_credit_evidence(conn, limit=args.limit)
        report["coverage"] = credit_evidence_coverage(conn)
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.report:
            args.report.write_text(rendered + "\n", encoding="utf-8")
            print(
                json.dumps(
                    {
                        key: report[key]
                        for key in (
                            "status",
                            "eligible",
                            "counts",
                            "artist_counts",
                            "affected_owner_count",
                            "affected_raw_play_rows",
                            "affected_raw_ms_played",
                            "coverage",
                        )
                        if key in report
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(rendered)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

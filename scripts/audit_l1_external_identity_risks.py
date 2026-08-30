#!/usr/bin/env python3
"""Generate a read-only L1 external identity risk and auto-split plan."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domains.metadata.track_identity_risk import (  # noqa: E402
    build_l1_external_identity_risk_plan,
    simulate_split_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    parser.add_argument("--exclude-keep", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    uri = f"file:{args.db.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only=ON")
    try:
        payload = build_l1_external_identity_risk_plan(conn, include_keep=not args.exclude_keep)
        if args.simulate and payload.get("status") == "ready":
            payload["simulation"] = simulate_split_plan(conn, str(payload["confirmation_token"]))
    finally:
        conn.close()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

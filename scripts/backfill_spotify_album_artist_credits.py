#!/usr/bin/env python3
"""Bounded Album evidence rehearsal. CLI writes only a newly created Online Backup."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.domains.metadata.spotify_album_credits import (  # noqa: E402
    AlbumArtistResolver,
    persist_album_artists,
)
from backend.providers.spotify.client import SpotifyProvider  # noqa: E402


def run_backfill(conn, provider, ids, *, run_id):
    """Persist only requested Album artists; never touch Track metadata or raw facts."""
    ids = list(dict.fromkeys(ids))
    report = {
        "requested": len(ids),
        "observed": 0,
        "changed": 0,
        "unchanged": 0,
        "rejected": 0,
        "failed": 0,
    }
    token = provider.get_cc_token()
    if not token:
        report["failed"] = len(ids)
        return report
    for offset in range(0, len(ids), 20):
        batch = ids[offset : offset + 20]
        try:
            data = provider.get_albums(batch, token)
        except Exception:
            data = None
        items = data.get("albums") if isinstance(data, dict) else None
        returned = {
            a["id"]: a
            for a in (items if isinstance(items, list) else [])
            if isinstance(a, dict) and a.get("id") in batch
        }
        for sid in batch:
            if sid not in returned:
                report["failed"] += 1
                continue
            conn.execute("SAVEPOINT album_backfill")
            try:
                # Minimal parent for a requested ID; preserve every other metadata field.
                conn.execute(
                    "INSERT OR IGNORE INTO spotify_album_meta(spotify_album_id,album_name) VALUES(?,?)",
                    (sid, returned[sid].get("name") or ""),
                )
                state = persist_album_artists(
                    conn, returned[sid], source="album_evidence_backfill", source_run_id=run_id
                )
                conn.execute("RELEASE SAVEPOINT album_backfill")
                report[state] += 1
            except Exception:
                conn.execute("ROLLBACK TO SAVEPOINT album_backfill")
                conn.execute("RELEASE SAVEPOINT album_backfill")
                report["failed"] += 1
        conn.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--ids", nargs="*")
    args = parser.parse_args()
    source, output = args.source_db.resolve(), args.output_db.resolve()
    if not source.is_file() or output.exists() or output == source or not 1 <= args.limit <= 100:
        parser.error("source 必须存在；output 必须为新副本；limit 必须在 1..100")
    if args.ids and len(args.ids) > args.limit:
        parser.error("显式 IDs 不能超过 limit")
    # Reserve destination exclusively; a typo cannot overwrite an existing database.
    with output.open("xb"):
        pass
    conn = sqlite3.connect(output)
    readonly = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
    try:
        readonly.backup(conn)
    finally:
        readonly.close()
        conn.close()
    from backend.core import db as db_mod
    from backend.core.migrations import run_migrations

    previous = db_mod.DB_PATH
    try:
        db_mod.DB_PATH = str(output)
        run_migrations()
    finally:
        db_mod.DB_PATH = previous
    conn = sqlite3.connect(output)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        ids = args.ids or [
            r[0]
            for r in conn.execute(
                "SELECT m.spotify_album_id FROM spotify_album_meta m "
                "LEFT JOIN spotify_album_credit_sets s USING(spotify_album_id) "
                "WHERE s.spotify_album_id IS NULL ORDER BY m.spotify_album_id LIMIT ?",
                (args.limit,),
            )
        ]
        report = run_backfill(conn, SpotifyProvider(), ids, run_id=str(uuid.uuid4()))
        resolver = AlbumArtistResolver(conn)
        print(
            json.dumps(
                {
                    "database_copy": str(output),
                    "counts": report,
                    "evidence": {sid: resolver.read(sid) for sid in ids},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()

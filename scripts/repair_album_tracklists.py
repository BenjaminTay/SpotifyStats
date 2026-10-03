#!/usr/bin/env python3
"""Bounded, explicit repair. Audit is the default; DB path is always required."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domains.metadata.album_tracklist import (
    release_position_evidence,
    select_missing_position_evidence_ids,
)
from backend.domains.metadata.spotify_refresh import select_incomplete_album_ids, upsert_album_batch
from backend.providers.spotify.album_tracks import complete_track_ids


def audit(conn):
    rows = []
    counts = {"complete": 0, "missing": 0, "partial": 0}
    position_counts = {}
    for sid, name, total, raw in conn.execute(
        "SELECT spotify_album_id, album_name, total_tracks, track_list FROM spotify_album_meta ORDER BY spotify_album_id"
    ):
        try:
            decoded = json.loads(raw or "null")
        except ValueError:
            decoded = None
        positions = len(decoded) if isinstance(decoded, list) else 0
        state = (
            "complete"
            if complete_track_ids(raw, total) is not None
            else "partial"
            if positions
            else "missing"
        )
        counts[state] += 1
        position_state = release_position_evidence(conn, sid).status
        position_counts[position_state] = position_counts.get(position_state, 0) + 1
        if state != "complete" or positions == total == 50:
            rows.append(
                dict(
                    spotify_album_id=sid,
                    album_name=name,
                    total_tracks=total,
                    positions=positions,
                    status=state,
                    boundary_50=positions == total == 50,
                )
            )
    return {"counts": counts, "position_evidence_counts": position_counts, "candidates": rows}


def repair(conn, provider, token, ids):
    outcomes = []
    for offset in range(0, len(ids), 20):
        batch = ids[offset : offset + 20]
        try:
            data = provider.get_albums(batch, token)
        except Exception as exc:
            data = None
            error = f"provider_failed:{type(exc).__name__}"
        else:
            error = "albums_batch_failed"
        albums = [a for a in (data or {}).get("albums", []) if a and a.get("id") in batch]
        returned = {a["id"] for a in albums}
        for sid in batch:
            if sid not in returned:
                row = conn.execute(
                    "SELECT total_tracks FROM spotify_album_meta WHERE spotify_album_id=?", (sid,)
                ).fetchone()
                conn.execute(
                    """INSERT INTO spotify_album_tracklist_evidence
                    (spotify_album_id, last_status, attempted_total, last_error) VALUES (?, 'incomplete', ?, ?)
                    ON CONFLICT(spotify_album_id) DO UPDATE SET last_status='incomplete',
                    last_error=excluded.last_error, updated_at=CURRENT_TIMESTAMP""",
                    (sid, row[0] if row else None, error),
                )
                outcomes.append((sid, "incomplete", error))
        # Do not commit a failed observation separately from successful batch writes.
        upsert_album_batch(conn, albums, provider=provider, access_token=token, outcomes=outcomes)
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--album-id", action="append", default=[])
    parser.add_argument("--verify-boundary-50", action="store_true")
    parser.add_argument(
        "--include-position-evidence",
        action="store_true",
        help="also select bounded played releases with missing or mismatching position evidence",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not 1 <= args.limit <= 200:
        parser.error("limit must be between 1 and 200")
    path = args.db.resolve(strict=True)
    conn = sqlite3.connect(f"{path.as_uri()}?mode={'rw' if args.apply else 'ro'}", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        before = audit(conn)
        report = {"database": str(path), "before": before, "applied": args.apply}
        ids = (
            sorted(set(args.album_id))
            if args.album_id
            else select_incomplete_album_ids(conn, args.limit)
        )
        if args.include_position_evidence and not args.album_id:
            ids = list(
                dict.fromkeys([*ids, *select_missing_position_evidence_ids(conn, args.limit)])
            )
        if args.verify_boundary_50:
            ids = sorted(
                set(ids) | {r["spotify_album_id"] for r in before["candidates"] if r["boundary_50"]}
            )
        ids = ids[: args.limit]
        report["selected"] = ids
        if args.apply:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='spotify_album_tracklist_evidence'"
            ).fetchone():
                parser.error("run the project migration on this database before applying repair")
            from backend.providers.spotify.client import SpotifyProvider

            provider = SpotifyProvider()
            token = provider.get_cc_token() if ids else None
            if ids and not token:
                report["error"] = "spotify_credentials_missing"
            else:
                report["outcomes"] = repair(conn, provider, token, ids)
                report["after"] = audit(conn)
                # Durable revisions change in the same transaction; no statistics
                # rebuild or release/project approval occurs here.
                from backend.core.cache_manager import invalidate_many

                if any(status == "complete" for _, status, _ in report["outcomes"]):
                    invalidate_many("analysis", "yearly_review")
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(
            json.dumps(
                {k: v for k, v in report.items() if k not in {"before", "after"}},
                ensure_ascii=False,
            )
        )
        print(
            json.dumps(
                {"before": before["counts"], "after": report.get("after", {}).get("counts")},
                ensure_ascii=False,
            )
        )
        return (
            1
            if report.get("error") or any(o[1] != "complete" for o in report.get("outcomes", []))
            else 0
        )
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

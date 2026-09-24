#!/usr/bin/env python3
"""Explicit, resumable Spotify Track artists[] evidence backfill."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import DB_PATH  # noqa: E402
from backend.domains.metadata.spotify_track_credits import (  # noqa: E402
    InvalidSpotifyCreditsError,
    credit_evidence_coverage,
    evidence_schema_available,
    save_track_credit_evidence,
    select_missing_credit_evidence,
)
from backend.providers.spotify.client import SpotifyProvider  # noqa: E402


class TrackLookupProvider(Protocol):
    def get_cc_token(self) -> str | None: ...

    def get_tracks(self, track_ids: list[str], access_token: str, /) -> dict | None: ...


def _connection(path: Path, *, write: bool) -> sqlite3.Connection:
    if write:
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys=ON")
    else:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _eligible_ids(
    conn: sqlite3.Connection, after_id: str, maximum: int, *, refresh_existing: bool = False
) -> list[str]:
    # The selector returns ordered missing IDs. Its default cap is intentionally
    # overridden for a complete explicit backfill, then the CLI applies a limit.
    if refresh_existing:
        ids = [
            str(row[0])
            for row in conn.execute(
                "SELECT spotify_track_id FROM spotify_track_credit_sets ORDER BY spotify_track_id"
            )
        ]
    else:
        ids = select_missing_credit_evidence(conn, limit=2_147_483_647)
    selected = [value for value in ids if value > after_id]
    return selected[:maximum] if maximum > 0 else selected


def run_backfill(
    conn: sqlite3.Connection,
    provider: TrackLookupProvider,
    ids: list[str],
    *,
    run_id: str,
) -> dict:
    counts = {"requested": len(ids), "observed": 0, "changed": 0, "unchanged": 0, "failed": 0}
    failures: list[dict[str, str]] = []
    completed = ""
    token = provider.get_cc_token()
    if not token:
        return {
            "counts": {**counts, "failed": len(ids)},
            "failures": [
                {"spotify_track_id": value, "reason": "spotify_credentials_missing"}
                for value in ids
            ],
            "last_processed_id": completed,
        }
    for offset in range(0, len(ids), 50):
        batch = ids[offset : offset + 50]
        data = provider.get_tracks(batch, token)
        if not isinstance(data, dict) or not isinstance(data.get("tracks"), list):
            failures.extend(
                {"spotify_track_id": value, "reason": "tracks_batch_failed"} for value in batch
            )
            counts["failed"] += len(batch)
            break
        returned = {
            str(item.get("id")): item
            for item in data["tracks"]
            if isinstance(item, dict) and item.get("id")
        }
        for track_id in batch:
            track = returned.get(track_id)
            if track is None:
                failures.append(
                    {"spotify_track_id": track_id, "reason": "track_missing_from_batch"}
                )
                counts["failed"] += 1
                completed = track_id
                continue
            try:
                # A savepoint ensures an invalid or failing Track leaves no
                # metadata parent or partial evidence row behind.
                conn.execute("SAVEPOINT spotify_credit_track")
                conn.execute(
                    """INSERT OR IGNORE INTO spotify_track_meta(
                           spotify_track_id, track_name, duration_ms, popularity,
                           explicit, track_number, disc_number, isrc, spotify_album_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        track_id,
                        track.get("name") or track_id,
                        track.get("duration_ms"),
                        track.get("popularity"),
                        int(bool(track.get("explicit"))),
                        track.get("track_number"),
                        track.get("disc_number"),
                        (track.get("external_ids") or {}).get("isrc"),
                        (track.get("album") or {}).get("id"),
                    ),
                )
                outcome = save_track_credit_evidence(
                    conn, track, requested_id=track_id, source_run_id=run_id
                )
                conn.execute("RELEASE SAVEPOINT spotify_credit_track")
                counts[outcome] += 1
            except InvalidSpotifyCreditsError as exc:
                conn.execute("ROLLBACK TO SAVEPOINT spotify_credit_track")
                conn.execute("RELEASE SAVEPOINT spotify_credit_track")
                failures.append({"spotify_track_id": track_id, "reason": str(exc)})
                counts["failed"] += 1
            except Exception:
                conn.rollback()
                raise
            completed = track_id
        conn.commit()
    return {"counts": counts, "failures": failures, "last_processed_id": completed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path(DB_PATH))
    parser.add_argument("--apply", action="store_true", help="Call Spotify and write evidence")
    parser.add_argument("--after-id", default="", help="Resume after this Spotify track ID")
    parser.add_argument("--max-tracks", type=int, default=200, help="0 means all remaining IDs")
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Re-fetch stored evidence to verify idempotence or provider changes",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--report", type=Path, help="Write the JSON run report to this path")
    args = parser.parse_args()
    if args.max_tracks < 0:
        parser.error("--max-tracks must be nonnegative")
    if args.apply and args.db_path.resolve() == Path(DB_PATH).resolve():
        parser.error(
            "--apply requires an explicit isolated --db-path; primary DB backfill is a separate release operation"
        )
    conn = _connection(args.db_path, write=args.apply)
    try:
        if not evidence_schema_available(conn):
            parser.error("credit evidence migration is missing from the selected database")
        ids = _eligible_ids(
            conn, args.after_id, args.max_tracks, refresh_existing=args.refresh_existing
        )
        report = {
            "mode": "apply" if args.apply else "dry_run",
            "db_path": str(args.db_path.resolve()),
            "run_id": args.run_id or str(uuid.uuid4()),
            "after_id": args.after_id,
            "refresh_existing": args.refresh_existing,
            "selected": len(ids),
            "first_id": ids[0] if ids else None,
            "last_selected_id": ids[-1] if ids else None,
            "coverage_before": credit_evidence_coverage(conn),
        }
        if args.apply:
            report.update(run_backfill(conn, SpotifyProvider(), ids, run_id=report["run_id"]))
            report["coverage_after"] = credit_evidence_coverage(conn)
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.report:
            args.report.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 1 if args.apply and report["counts"]["failed"] else 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

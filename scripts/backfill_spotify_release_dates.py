"""Bounded date-only maintenance on an explicitly named isolated database copy.

No ID discovery or relationship rebuilding. Observations can be replayed offline;
network calls use the existing Spotify Provider and only the requested Album IDs.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domains.metadata.release_dates import (
    persist_release_date,
    sync_project_release_precisions,
)


def apply_observations(conn, observations, *, album_ids, source_run_id=None):
    allowed = set(album_ids)
    if not allowed or len(allowed) > 200:
        raise ValueError("require 1..200 explicitly selected Album IDs")
    if len(observations) > len(allowed) or len({r.get("id") for r in observations}) != len(
        observations
    ):
        raise ValueError("duplicate or excessive observations")
    if any(r.get("id") not in allowed for r in observations):
        raise ValueError("unrequested Spotify Album ID")
    conn.execute("SAVEPOINT release_date_maintenance")
    try:
        results = {
            r["id"]: persist_release_date(
                conn, r, source="bounded_spotify_album_date", source_run_id=source_run_id
            )
            for r in observations
        }
        changed = sync_project_release_precisions(conn, allowed)
        conn.execute("RELEASE SAVEPOINT release_date_maintenance")
        return {
            "outcomes": results,
            "missing_ids": sorted(allowed - set(results)),
            "project_precision_changes": changed,
        }
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT release_date_maintenance")
        conn.execute("RELEASE SAVEPOINT release_date_maintenance")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-copy", type=Path, required=True)
    parser.add_argument("--album-id", action="append", required=True)
    parser.add_argument("--observations-json", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    path = args.database_copy.resolve()
    formal = Path(__file__).resolve().parents[1] / "data"
    if not path.is_file() or path == formal or formal in path.parents:
        parser.error("database-copy must be an existing isolated copy outside formal data/")
    from backend.core.config import SPOTIFY_STATS_DB_PATH

    if SPOTIFY_STATS_DB_PATH and path == Path(SPOTIFY_STATS_DB_PATH).resolve():
        parser.error("database-copy cannot be the configured application database")
    ids = sorted(set(args.album_id))
    if not 1 <= len(ids) <= 200:
        parser.error("select 1..200 Album IDs")
    if args.observations_json:
        observations = json.loads(args.observations_json.read_text())
    else:
        from backend.providers.spotify.client import SpotifyProvider

        provider = SpotifyProvider()
        token = provider.get_cc_token()
        if not token:
            parser.error("Spotify token unavailable; no database writes")
        observations = []
        for offset in range(0, len(ids), 20):
            response = provider.get_albums(ids[offset : offset + 20], token)
            if response is None:
                parser.error("Spotify batch failed; no database writes")
            observations.extend(r for r in response.get("albums", []) if r)
    conn = sqlite3.connect(path if args.apply else path.as_uri() + "?mode=ro", uri=not args.apply)
    conn.row_factory = sqlite3.Row
    # Preview uses a transient SQLite copy, never write/rollback against the source file.
    if not args.apply:
        preview = sqlite3.connect(":memory:")
        conn.backup(preview)
        conn.close()
        conn = preview
    try:
        report = apply_observations(
            conn, observations, album_ids=ids, source_run_id="explicit_date_maintenance"
        )
        conn.commit()
        report["applied"] = args.apply
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

"""Bounded Spotify Album date + artist evidence maintenance, with offline replay.

Inventory: --database-copy COPY --manifest-only --output manifest.json
Fetch: --database-copy COPY --manifest-json manifest.json --batch-index 0
       --fetch-only --responses-output batch-000.json --output fetch-000.json
Replay/preview: --database-copy COPY --observations-json batch-000.json --output preview.json
Install on isolated copy: same command plus --apply
Online Backup: --snapshot-from SOURCE --database-copy NEW_COPY --manifest-only --output manifest.json

Each explicit batch has <=200 IDs. Fetches use only Album endpoints, never track
pagination. Saved responses can be replayed without credentials or network access.
A response file can be resumed; only failed/missing IDs are fetched again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domains.metadata.release_dates import (
    install_album_release_evidence,
    release_evidence_inventory,
)


def _validate_ids(album_ids):
    ids = sorted(set(album_ids))
    if not ids or len(ids) > 200 or any(not isinstance(sid, str) or not sid for sid in ids):
        raise ValueError("require 1..200 explicitly selected Album IDs")
    return ids


def evidence_fingerprint(conn, album_ids):
    """Fence the evidence/project inputs; unrelated new playback does not block replay."""
    ids = _validate_ids(album_ids)
    marks = ",".join("?" for _ in ids)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    facts = {
        "sources": [
            tuple(r)
            for r in conn.execute(
                f"SELECT spotify_album_id,album_name,album_type,release_date,release_date_precision FROM spotify_album_meta WHERE spotify_album_id IN ({marks}) ORDER BY spotify_album_id",
                ids,
            )
        ]
    }
    if "spotify_album_credit_sets" in tables:
        facts["credits"] = [
            tuple(r)
            for r in conn.execute(
                f"SELECT spotify_album_id,credit_signature FROM spotify_album_credit_sets WHERE spotify_album_id IN ({marks}) ORDER BY spotify_album_id",
                ids,
            )
        ]
    if {"albums", "album_spotify_links"}.issubset(tables):
        facts["links"] = [
            tuple(r)
            for r in conn.execute(
                f"""SELECT asl.album_id,asl.spotify_album_id,asl.evidence,asl.confidence,a.album_name
            FROM album_spotify_links asl JOIN albums a USING(album_id)
            WHERE asl.album_id IN (SELECT album_id FROM album_spotify_links WHERE spotify_album_id IN ({marks}))
            ORDER BY asl.album_id,asl.spotify_album_id,asl.evidence""",
                ids,
            )
        ]
    if {"album_projects", "album_spotify_links"}.issubset(tables):
        external_clause = ""
        parameters = list(ids)
        if "album_project_external_ids" in tables:
            external_clause = f"""OR EXISTS (SELECT 1 FROM album_project_external_ids e
                WHERE e.project_id=ap.project_id AND e.provider='spotify'
                AND e.external_album_id IN ({marks}))"""
            parameters += ids
        facts["projects"] = [
            tuple(r)
            for r in conn.execute(
                f"""SELECT ap.project_id,ap.primary_album_id,ap.release_date,ap.release_date_precision,ap.is_manual
            FROM album_projects ap WHERE EXISTS (
                SELECT 1 FROM album_spotify_links asl WHERE asl.album_id=ap.primary_album_id
                AND asl.spotify_album_id IN ({marks})) {external_clause} ORDER BY ap.project_id""",
                parameters,
            )
        ]
        affected = [row[0] for row in facts["projects"]]
        if "album_project_external_ids" in tables:
            project_marks = ",".join("?" for _ in affected) or "NULL"
            facts["project_external_ids"] = [
                tuple(r)
                for r in conn.execute(
                    f"""SELECT provider,external_album_id,project_id,evidence_type,confidence,is_primary
                FROM album_project_external_ids WHERE project_id IN ({project_marks})
                OR (provider='spotify' AND external_album_id IN ({marks}))
                ORDER BY provider,external_album_id""",
                    (*affected, *ids),
                )
            ]
    return hashlib.sha256(
        json.dumps(facts, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def build_manifest(conn):
    report = release_evidence_inventory(conn)
    ids = [item["id"] for item in report["items"] if item["needs_fetch"]]
    report["schema"] = "spotify_album_release_evidence_v1"
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    report["batches"] = [
        {
            "album_ids": ids[i : i + 200],
            "input_fingerprint": evidence_fingerprint(conn, ids[i : i + 200]),
        }
        for i in range(0, len(ids), 200)
    ]
    return report


def apply_observations(
    conn, observations, *, album_ids, source_run_id=None, expected_fingerprint=None
):
    allowed = set(_validate_ids(album_ids))
    if len(observations) > len(allowed) or len({r.get("id") for r in observations}) != len(
        observations
    ):
        raise ValueError("duplicate or excessive observations")
    if any(r.get("id") not in allowed for r in observations):
        raise ValueError("unrequested Spotify Album ID")
    conn.execute("SAVEPOINT release_date_maintenance")
    try:
        if expected_fingerprint and evidence_fingerprint(conn, allowed) != expected_fingerprint:
            raise ValueError("evidence inputs drifted; regenerate/review batch before installation")
        # A referenced uncached ID may be recovered from an explicitly identified
        # official response. No relationship, membership or track data is inferred.
        for album in observations:
            if album.get("name"):
                conn.execute(
                    "INSERT OR IGNORE INTO spotify_album_meta(spotify_album_id,album_name,album_type) VALUES (?,?,?)",
                    (album["id"], album["name"], album.get("album_type")),
                )
        report = install_album_release_evidence(
            conn, observations, source="bounded_spotify_album_date", source_run_id=source_run_id
        )
        report["outcomes"] = {
            sid: state["date"] for sid, state in report["evidence_outcomes"].items()
        }
        report["missing_ids"] = sorted(allowed - set(report["outcomes"]))
        conn.execute("RELEASE SAVEPOINT release_date_maintenance")
        return report
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT release_date_maintenance")
        conn.execute("RELEASE SAVEPOINT release_date_maintenance")
        raise


def fetch_observations(provider, access_token, album_ids, *, existing=None):
    """Save only necessary official evidence, and report each missing/failed ID."""
    ids = _validate_ids(album_ids)
    old = existing or {}
    if old and sorted(old.get("album_ids", [])) != ids:
        raise ValueError("saved response belongs to a different explicit batch")
    results = {r["id"]: r for r in old.get("observations", [])}
    if set(results) - set(ids):
        raise ValueError("unrequested saved response")
    failures = {}
    pending = [sid for sid in ids if sid not in results]
    for offset in range(0, len(pending), 20):
        batch = pending[offset : offset + 20]
        try:
            response = provider.get_albums(batch, access_token)
            if response is None:
                raise RuntimeError("provider_batch_failed")
            received = response.get("albums", [])
            valid = [r for r in received if r and r.get("id") in batch]
            if len(valid) != len({r["id"] for r in valid}) or any(
                r and r.get("id") not in batch for r in received
            ):
                raise ValueError("provider_response_id_mismatch")
            for album in valid:
                results[album["id"]] = {
                    key: album.get(key)
                    for key in (
                        "id",
                        "name",
                        "album_type",
                        "release_date",
                        "release_date_precision",
                        "artists",
                    )
                }
            failures.update(
                {sid: "album_missing_from_response" for sid in batch if sid not in results}
            )
        except Exception as exc:
            # Provider exception text may include request headers/URLs; keep a
            # stable classification and no credential-bearing message.
            failures.update({sid: "provider_batch_failed:" + type(exc).__name__ for sid in batch})
    return {
        "schema": "spotify_album_release_response_v1",
        "album_ids": ids,
        "observations": [results[sid] for sid in ids if sid in results],
        "failures": failures,
    }


def online_backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError("Online Backup destination must not already exist")
    if source == destination:
        raise ValueError("Online Backup requires a different path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Online Backup quick_check failed")


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--database-copy", type=Path, required=True)
    parser.add_argument("--snapshot-from", type=Path)
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--manifest-json", type=Path)
    parser.add_argument("--batch-index", type=int)
    parser.add_argument(
        "--expected-fingerprint",
        help="Reviewed current batch fingerprint; use after inspecting legitimate prior-batch project changes",
    )
    parser.add_argument("--album-id", action="append", default=[])
    parser.add_argument("--observations-json", type=Path)
    parser.add_argument("--responses-output", type=Path)
    parser.add_argument("--fetch-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    path = args.database_copy.resolve()
    formal = Path(__file__).resolve().parents[1] / "data"
    if path == formal or formal in path.parents:
        parser.error("database-copy must be an isolated copy outside formal data/")
    from backend.core.config import SPOTIFY_STATS_DB_PATH

    if SPOTIFY_STATS_DB_PATH and path == Path(SPOTIFY_STATS_DB_PATH).resolve():
        parser.error("database-copy cannot be the configured application database")
    if args.snapshot_from:
        online_backup(args.snapshot_from, path)
    if not path.is_file():
        parser.error("database-copy does not exist")
    expected = None
    if args.manifest_only:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
            _write(args.output, build_manifest(conn))
        return
    payload = json.loads(args.observations_json.read_text()) if args.observations_json else None
    ids = args.album_id or (payload.get("album_ids", []) if isinstance(payload, dict) else [])
    if args.manifest_json:
        if args.batch_index is None or args.batch_index < 0:
            parser.error("manifest requires a nonnegative --batch-index")
        manifest = json.loads(args.manifest_json.read_text())
        try:
            batch = manifest["batches"][args.batch_index]
        except IndexError:
            parser.error("batch-index outside manifest")
        if ids and sorted(set(ids)) != batch["album_ids"]:
            parser.error("explicit IDs differ from manifest batch")
        ids, expected = batch["album_ids"], batch["input_fingerprint"]
    try:
        ids = _validate_ids(ids)
    except ValueError as exc:
        parser.error(str(exc))
    if payload is None:
        if not args.responses_output:
            parser.error("network fetch requires --responses-output for offline replay")
        from backend.providers.spotify.client import SpotifyProvider

        provider = SpotifyProvider()
        token = provider.get_cc_token()
        if not token:
            parser.error("Spotify token unavailable; no database writes")
        existing = (
            json.loads(args.responses_output.read_text())
            if args.responses_output.exists()
            else None
        )
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as current:
            current_fingerprint = evidence_fingerprint(current, ids)
        expected = args.expected_fingerprint or expected or current_fingerprint
        if expected != current_fingerprint:
            parser.error("manifest inputs drifted before fetch; review and rebase batch")
        if (
            existing
            and existing.get("input_fingerprint") not in {None, expected}
            and not args.expected_fingerprint
        ):
            parser.error("saved response inputs drifted; review and explicitly rebase batch")
        payload = fetch_observations(provider, token, ids, existing=existing)
        payload["input_fingerprint"] = expected
        _write(args.responses_output, payload)
    if args.fetch_only:
        if args.apply:
            parser.error("fetch-only cannot apply")
        _write(
            args.output,
            {
                "requested": len(ids),
                "received": len(payload["observations"]),
                "failures": payload["failures"],
            },
        )
        return
    observations = payload.get("observations", []) if isinstance(payload, dict) else payload
    expected = (
        args.expected_fingerprint
        or expected
        or (payload.get("input_fingerprint") if isinstance(payload, dict) else None)
    )
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    if not args.apply:
        preview = sqlite3.connect(":memory:")
        conn.backup(preview)
        conn.close()
        conn = preview
    else:
        conn.close()
        conn = sqlite3.connect(path)
    try:
        report = apply_observations(
            conn,
            observations,
            album_ids=ids,
            source_run_id=args.observations_json.name
            if args.observations_json
            else args.responses_output.name,
            expected_fingerprint=expected,
        )
        conn.commit()
        report["applied"] = args.apply
        report["fetch_failures"] = payload.get("failures", {}) if isinstance(payload, dict) else {}
        _write(args.output, report)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Prepare private detail projections on a copy, then transfer exact publications."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from backend.core import db  # noqa: E402
from backend.core.migrations import run_migrations  # noqa: E402
from backend.domains.music_search.detail_projection import (  # noqa: E402
    DETAIL_PROJECTION_VERSION,
    _assert_writer_allowed,
    backfill_detail_projection_set,
    ledger_checks,
    payload_digest,
    projection_available,
    publish_detail_projection,
    source_checks,
)
from backend.domains.music_search.snapshot_lineage import (  # noqa: E402
    active_playback_lineage,
    music_search_snapshot_dependency_digest,
)
from backend.domains.music_search.variants import build_music_search_variant_contexts  # noqa: E402
from backend.services.music_search_maintenance_service import _current_filter_values  # noqa: E402
from scripts.closed_publication_source import publication_reads  # noqa: E402


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def publication_fence(conn, contexts):
    return {
        "playback_lineage": list(active_playback_lineage(conn)),
        "governance_digest": music_search_snapshot_dependency_digest(conn),
        "variants": [
            {
                "snapshot_key": c.filter_fingerprint,
                "filter_fingerprint": c.filter_fingerprint,
                "source_revision": c.source_revision,
            }
            for c in contexts
        ],
    }


def verify_payload_rows(conn, source, entities):
    seen = set()
    for row in source:
        if not isinstance(row, (list, tuple)) or len(row) != 7:
            raise RuntimeError("detail source row shape mismatch")
        if (
            any(
                isinstance(row[i], bool) or not isinstance(row[i], int) or row[i] < 0
                for i in (0, 1, 2, 5, 6)
            )
            or row[0] <= 0
        ):
            raise RuntimeError("detail source row metrics mismatch")
        from datetime import date

        for index in (3, 4):
            if (
                not isinstance(row[index], str)
                or date.fromisoformat(row[index]).isoformat() != row[index]
            ):
                raise RuntimeError("detail source date mismatch")
        identity = tuple(row[:5])
        if identity in seen:
            raise RuntimeError("duplicate detail source fact")
        seen.add(identity)
    by_key = {}
    allowed = {
        "membership",
        "artist_track_keys",
        "album_track_keys",
        "artist_album_keys",
        "source_check_l1",
        "source_check_album",
        "source_check_all",
        "ledger_check_track",
        "ledger_check_album",
        "ledger_check_artist",
        "global_no1_albums",
        "context_check_track",
        "context_check_album",
        "context_check_album_project",
        "context_check_artist",
    }
    for row in entities:
        if (
            not isinstance(row, (list, tuple))
            or len(row) != 3
            or row[0] not in allowed
            or not isinstance(row[1], int)
            or isinstance(row[1], bool)
            or row[1] < 0
        ):
            raise RuntimeError("detail entity row shape mismatch")
        key = (row[0], row[1])
        if key in by_key:
            raise RuntimeError("duplicate detail entity projection")
        payload = json.loads(row[2])
        if not isinstance(
            payload,
            dict
            if row[0].startswith(("source_check_", "ledger_check_", "context_check_"))
            else list,
        ):
            raise RuntimeError("detail entity payload type mismatch")
        by_key[key] = payload
    for kind, entity_id, expected in source_checks(source, conn):
        if by_key.get((kind, entity_id)) != json.loads(expected):
            raise RuntimeError("detail source completeness checksum mismatch")
    return by_key


def verify_projection_set(conn, contexts):
    for context in contexts:
        key = context.filter_fingerprint
        if not projection_available(conn, key):
            raise RuntimeError("detail exact projection unavailable")
        source = [
            list(row)
            for row in conn.execute(
                "SELECT l1_id,source_album_id,track_album_id,week,day,play_count,total_ms FROM music_search_detail_source_facts WHERE snapshot_key=?",
                (key,),
            )
        ]
        entities = []
        for row in conn.execute(
            "SELECT kind,entity_id,payload_json,payload_digest FROM music_search_detail_entity_projection WHERE snapshot_key=?",
            (key,),
        ):
            if payload_digest(row[2]) != row[3]:
                raise RuntimeError("detail entity publication digest mismatch")
            entities.append(list(row[:3]))
        by_key = verify_payload_rows(conn, source, entities)
        for kind, entity_id, expected in ledger_checks(conn, key):
            if by_key.get((kind, entity_id)) != json.loads(expected):
                raise RuntimeError("detail target ledger completeness mismatch")
        for row in conn.execute("SELECT project_id FROM album_projects"):
            if ("membership", int(row[0])) not in by_key or (
                "album_track_keys",
                int(row[0]),
            ) not in by_key:
                raise RuntimeError("detail project projection missing")
        for row in conn.execute("SELECT artist_id FROM artists"):
            if ("artist_track_keys", int(row[0])) not in by_key or (
                "artist_album_keys",
                int(row[0]),
            ) not in by_key:
                raise RuntimeError("detail artist projection missing")
    return {
        "status": "ready",
        "variants": len(contexts),
        "projection_version": DETAIL_PROJECTION_VERSION,
    }


def export_projection(conn, contexts, path):
    verify_projection_set(conn, contexts)
    captured = publication_fence(conn, contexts)
    variants = []
    for context in contexts:
        key = context.filter_fingerprint
        if not projection_available(conn, key):
            raise RuntimeError("detail export requires every exact projection ready")
        source = [
            list(row)
            for row in conn.execute(
                "SELECT l1_id,source_album_id,track_album_id,week,day,play_count,total_ms FROM music_search_detail_source_facts WHERE snapshot_key=? ORDER BY l1_id,source_album_id,track_album_id,week,day",
                (key,),
            )
        ]
        entities = [
            list(row)
            for row in conn.execute(
                "SELECT kind,entity_id,payload_json FROM music_search_detail_entity_projection WHERE snapshot_key=? ORDER BY kind,entity_id",
                (key,),
            )
        ]
        variants.append({"snapshot_key": key, "source_rows": source, "entity_rows": entities})
    if captured != publication_fence(conn, contexts):
        raise RuntimeError("detail export source fence changed")
    payload = {
        "projection_version": DETAIL_PROJECTION_VERSION,
        "fence": captured,
        "variants": variants,
    }
    manifest = {"digest": digest(payload), "payload": payload}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=True, separators=(",", ":")) + "\n")
    path.chmod(0o600)
    return {"status": "exported", "variants": len(variants), "manifest_digest": manifest["digest"]}


def validate_manifest(conn, contexts, path):
    manifest = json.loads(path.read_text())
    payload = manifest["payload"]
    if (
        manifest["digest"] != digest(payload)
        or payload["projection_version"] != DETAIL_PROJECTION_VERSION
    ):
        raise RuntimeError("detail manifest digest/version mismatch")
    if payload["fence"] != publication_fence(conn, contexts):
        raise RuntimeError("detail manifest source/governance fence mismatch")
    by_key = {item["snapshot_key"]: item for item in payload["variants"]}
    if len(by_key) != len(payload["variants"]) or set(by_key) != {
        c.filter_fingerprint for c in contexts
    }:
        raise RuntimeError("detail manifest variants mismatch")
    for context in contexts:
        key = context.filter_fingerprint
        meta = conn.execute(
            "SELECT source_revision,status FROM music_search_snapshot_meta WHERE snapshot_key=?",
            (key,),
        ).fetchone()
        if meta is None or tuple(meta) != (context.source_revision, "ready"):
            raise RuntimeError("detail manifest target search snapshot is not exact ready")
        item = by_key[key]
        by_entity = verify_payload_rows(conn, item["source_rows"], item["entity_rows"])
        for kind, entity_id, expected in ledger_checks(conn, key):
            if by_entity.get((kind, entity_id)) != json.loads(expected):
                raise RuntimeError("detail manifest target ledger checksum mismatch")
    return manifest, by_key


def import_projection(conn, contexts, path):
    _assert_writer_allowed()
    conn.execute("BEGIN IMMEDIATE")
    try:
        manifest, by_key = validate_manifest(conn, contexts, path)
        for context in contexts:
            item = by_key[context.filter_fingerprint]
            publish_detail_projection(conn, context, item["source_rows"], item["entity_rows"])
        verify_projection_set(conn, contexts)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"status": "imported", "variants": len(contexts), "manifest_digest": manifest["digest"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    operations = parser.add_mutually_exclusive_group(required=True)
    operations.add_argument("--build-on-copy", action="store_true")
    operations.add_argument("--export", type=Path)
    operations.add_argument("--import-manifest", type=Path)
    operations.add_argument("--verify", action="store_true")
    operations.add_argument("--validate-manifest", type=Path)
    parser.add_argument(
        "--closed-source",
        action="store_true",
        help="Read a closed copy with no WAL using immutable mode; never use for a live database",
    )
    parser.add_argument(
        "--owned-copy",
        action="store_true",
        help="Explicitly identify an isolated maintenance copy even when DB_PATH points at it",
    )
    args = parser.parse_args()
    readonly = bool(args.export or args.verify or args.validate_manifest)
    if args.closed_source and not readonly:
        parser.error("--closed-source is only valid for read-only operations")
    _assert_writer_allowed()
    if not args.db_path.is_file():
        raise RuntimeError("detail database copy does not exist")
    requested_path = args.db_path.resolve()
    if args.build_on_copy and (
        requested_path.is_relative_to(PROJECT_ROOT / "data")
        or (requested_path == Path(db.DB_PATH).resolve() and not args.owned_copy)
    ):
        raise RuntimeError("detail build requires an explicitly owned copy outside formal data/")
    db.DB_PATH = str(requested_path)
    if args.build_on_copy:
        run_migrations()
    if readonly:
        with publication_reads(requested_path, closed=args.closed_source):
            result = _run(args, readonly=True)
    else:
        result = _run(args, readonly=False)
    print(json.dumps(result, ensure_ascii=True))


def _run(args, *, readonly):
    conn = db.get_db(readonly=readonly)
    try:
        contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        if args.build_on_copy:
            result = backfill_detail_projection_set(conn, contexts)
        elif args.verify:
            result = verify_projection_set(conn, contexts)
        elif args.validate_manifest:
            manifest, _ = validate_manifest(conn, contexts, args.validate_manifest)
            result = {
                "status": "validated",
                "variants": len(contexts),
                "manifest_digest": manifest["digest"],
            }
        elif args.export:
            result = export_projection(conn, contexts, args.export)
        else:
            result = import_projection(conn, contexts, args.import_manifest)
        return result
    finally:
        conn.close()


if __name__ == "__main__":
    main()

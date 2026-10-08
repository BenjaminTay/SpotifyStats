#!/usr/bin/env python3
"""Build/export on a database copy, or install exact ranks against a read-only source."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import config, db  # noqa: E402
from backend.services import versus_rank_context_service as ranks  # noqa: E402
from backend.services.versus_rank_publication import (  # noqa: E402
    _validated_publications,
    export_bundle,
    install_bundle,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("build", "export", "install", "import", "verify", "validate")
    )
    parser.add_argument(
        "--source-db",
        type=Path,
        required=True,
        help="Existing migrated source DB; opened read-only",
    )
    parser.add_argument(
        "--analysis-cache", type=Path, required=True, help="Explicit Analysis sidecar output/input"
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--release-sha", help="Bind export to, or require import from, this exact release SHA"
    )
    parser.add_argument(
        "--require-defaults",
        action="store_true",
        help="Require all four current default configurations for deployment",
    )
    parser.add_argument(
        "--filters-json",
        help="One normalized custom configuration; omitted means current four defaults",
    )
    parser.add_argument(
        "--closed-source",
        action="store_true",
        help="Assert a stopped source or static copy with no WAL, allowing immutable read-only opening",
    )
    args = parser.parse_args(argv)
    if args.mode == "import":
        args.mode = "install"
    source = args.source_db.resolve(strict=True)
    sidecar = args.analysis_cache.resolve()
    if args.mode != "verify" and args.manifest is None:
        parser.error("This mode requires --manifest")
    manifest = args.manifest.resolve() if args.manifest is not None else None
    paths = (source, sidecar) + ((manifest,) if manifest is not None else ())
    if any(
        left == right or (left.exists() and right.exists() and left.samefile(right))
        for index, left in enumerate(paths)
        for right in paths[index + 1 :]
    ):
        parser.error("Source DB, Analysis sidecar and manifest must be different files")
    configured_source = Path(db.DB_PATH).resolve()
    if args.mode == "build" and (
        source == configured_source
        or (configured_source.exists() and source.samefile(configured_source))
    ):
        parser.error(
            "Build requires an isolated database copy; the configured source is not allowed"
        )
    if args.mode in ("install", "validate", "verify") and args.filters_json:
        parser.error("Install accepts filters only from the validated manifest")
    db.DB_PATH = str(source)
    config.SPOTIFY_STATS_ANALYSIS_CACHE_PATH = str(sidecar)
    filters = json.loads(args.filters_json) if args.filters_json else None
    wal = source.with_name(source.name + "-wal")
    if args.closed_source and wal.exists():
        raise ValueError("Closed-source immutable reads require no WAL file")
    original_stat = source.stat()
    original_state = (
        original_stat.st_dev,
        original_stat.st_ino,
        original_stat.st_size,
        original_stat.st_mtime_ns,
    )

    def source_fence():
        if args.closed_source:
            current = source.stat()
            state = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
            if wal.exists() or state != original_state:
                raise ValueError("Closed personal rank source changed during the operation")

    uri = source.as_uri() + "?mode=ro" + ("&immutable=1" if args.closed_source else "")
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    try:
        if args.mode == "verify":
            snapshots = [
                ranks.read(conn, params)[1] for params in ranks.default_configurations(conn)
            ]
            result = {
                "ready": len(snapshots),
                "builder_version": ranks.VERSION,
                "source_revisions": list({snapshot["source_revision"] for snapshot in snapshots}),
            }
            if len(result["source_revisions"]) != 1:
                raise ValueError("Personal rank source changed during ready verification")
        elif args.mode in ("install", "validate"):
            if manifest.stat().st_size > 4 * 32 * 1024 * 1024:
                raise ValueError("Personal rank manifest exceeds four bounded payloads")
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            if args.mode == "install":
                result = install_bundle(
                    conn,
                    bundle,
                    expected_release_sha=args.release_sha,
                    require_defaults=args.require_defaults,
                    source_fence=source_fence,
                )
            else:
                entries = _validated_publications(
                    conn,
                    bundle,
                    expected_release_sha=args.release_sha,
                    require_defaults=args.require_defaults,
                )
                result = {"validated": len(entries), "source_revision": entries[0][2]}
        else:
            if args.mode == "build":
                variants = [filters] if filters is not None else ranks.default_configurations(conn)
                for variant in variants:
                    ranks.ensure(conn, variant)
            bundle = export_bundle(conn, filters, release_sha=args.release_sha)
            manifest.parent.mkdir(parents=True, exist_ok=True)
            source_fence()
            manifest.write_text(
                json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(",", ":")),
                encoding="utf-8",
            )
            result = {
                "exported": len(bundle["publications"]),
                "manifest": str(manifest),
                "builder_version": ranks.VERSION,
            }
        source_fence()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate persisted list thumbnails from existing local covers without DB writes."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core import db as db_module
from backend.services.cover_thumbnail_service import (
    ensure_cover_thumbnail,
    thumbnail_path,
)


def backfill(covers_root: Path) -> tuple[int, int, int]:
    scanned = generated = failed = 0
    for cover_type in ("albums", "artists"):
        for source in sorted((covers_root / cover_type).glob("*.jpg")):
            if not source.stem.isdecimal():
                continue
            scanned += 1
            try:
                if ensure_cover_thumbnail(
                    source, thumbnail_path(covers_root, cover_type, source.stem)
                ):
                    generated += 1
            except (OSError, ValueError) as exc:
                failed += 1
                print(f"{cover_type}/{source.name}: {exc}", file=sys.stderr)
    return scanned, generated, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--covers-root",
        type=Path,
        default=Path(os.path.dirname(db_module.DB_PATH)) / "covers",
    )
    args = parser.parse_args()
    scanned, generated, failed = backfill(args.covers_root)
    print(f"scanned={scanned} generated={generated} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

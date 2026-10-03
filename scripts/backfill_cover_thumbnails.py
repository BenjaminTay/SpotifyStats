#!/usr/bin/env python3
"""Generate fixed cover variants from local originals without DB writes."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core import db as db_module
from backend.services.cover_thumbnail_service import (
    COVER_VARIANT_SIZES,
    THUMBNAIL_SIZE,
    ensure_cover_thumbnail,
    thumbnail_is_current,
    thumbnail_path,
)


@dataclass
class BackfillResult:
    scanned: int = 0
    processed: int = 0
    generated: int = 0
    skipped: int = 0
    failed: int = 0


def backfill(
    covers_root: Path, sizes: tuple[int, ...] = (THUMBNAIL_SIZE,), limit: int | None = None
) -> BackfillResult:
    """Bound sources needing work, so repeated batches advance past ready files."""
    if not sizes or any(size not in COVER_VARIANT_SIZES for size in sizes):
        raise ValueError(f"sizes must be chosen from {COVER_VARIANT_SIZES}")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    sizes = tuple(dict.fromkeys(sizes))
    result = BackfillResult()
    for cover_type in ("albums", "artists"):
        for source in sorted((covers_root / cover_type).glob("*.jpg")):
            if not source.stem.isdecimal():
                continue
            pending = [
                size
                for size in sizes
                if not thumbnail_is_current(
                    source, thumbnail_path(covers_root, cover_type, source.stem, size)
                )
            ]
            if pending and limit is not None and result.processed >= limit:
                return result
            result.scanned += 1
            result.skipped += len(sizes) - len(pending)
            if pending:
                result.processed += 1
            for size in pending:
                thumbnail = thumbnail_path(covers_root, cover_type, source.stem, size)
                try:
                    if ensure_cover_thumbnail(source, thumbnail, size):
                        result.generated += 1
                    elif thumbnail_is_current(source, thumbnail):
                        result.skipped += 1
                    else:
                        raise OSError("source changed during encoding; retry this batch")
                except (OSError, ValueError) as exc:
                    result.failed += 1
                    print(f"{cover_type}/{source.name} {size}px: {exc}", file=sys.stderr)
    return result


def _positive_limit(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("limit must be positive")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--covers-root",
        type=Path,
        default=Path(os.path.dirname(db_module.DB_PATH)) / "covers",
    )
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        choices=COVER_VARIANT_SIZES,
        default=[THUMBNAIL_SIZE],
        help="fixed sizes to build (default: compatible 160px thumbnails)",
    )
    parser.add_argument(
        "--limit",
        type=_positive_limit,
        help="maximum originals requiring generation; ready originals do not consume the limit",
    )
    args = parser.parse_args()
    result = backfill(args.covers_root, tuple(args.sizes), args.limit)
    print(
        f"scanned={result.scanned} generated={result.generated} failed={result.failed} "
        f"processed={result.processed} skipped={result.skipped}"
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

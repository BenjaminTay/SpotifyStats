#!/usr/bin/env python3
"""Import reviewed artist genre seed rows into the local metadata source table."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db
from backend.domains.metadata.artist_genres import normalize_genres, upsert_genre_source

DEFAULT_SEED = ROOT / "data" / "artist_genre_overrides.seed.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="import_artist_genre_overrides.py",
        description="Import reviewed artist genre seed rows into artist_genre_sources.",
    )
    parser.add_argument(
        "--seed",
        type=Path,
        default=DEFAULT_SEED,
        help="Path to the artist genre seed JSON file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report seed rows without writing to the database.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Write a machine-readable import report to this JSON file.",
    )
    return parser.parse_args(argv)


def write_json_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _require_text(row: dict[str, Any], field: str, index: int) -> str:
    value = str(row.get(field) or "").strip()
    if not value:
        raise ValueError(f"row {index}: {field} is required")
    return value


def _optional_text(row: dict[str, Any], field: str) -> str | None:
    value = row.get(field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _validate_seed_row(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"row {index}: expected object")

    genres_value = raw.get("genres")
    if not isinstance(genres_value, list):
        raise ValueError(f"row {index}: genres must be a list")
    genres = normalize_genres(genres_value)
    if not genres:
        raise ValueError(f"row {index}: genres must contain at least one value")

    status = _optional_text(raw, "status") or "approved"
    if status not in {"approved", "suggested"}:
        raise ValueError(f"row {index}: status must be approved or suggested")

    confidence = float(raw.get("confidence", 0.0))
    if confidence < 0 or confidence > 1:
        raise ValueError(f"row {index}: confidence must be between 0 and 1")

    primary_genre = _optional_text(raw, "primary_genre") or genres[0]
    return {
        "artist_name": _require_text(raw, "artist_name", index),
        "spotify_artist_id": _optional_text(raw, "spotify_artist_id"),
        "source": _require_text(raw, "source", index),
        "source_key": _require_text(raw, "source_key", index),
        "genres": genres,
        "primary_genre": primary_genre.lower(),
        "language": _optional_text(raw, "language"),
        "region": _optional_text(raw, "region"),
        "confidence": confidence,
        "evidence_url": _optional_text(raw, "evidence_url"),
        "evidence_summary": _optional_text(raw, "evidence_summary"),
        "status": status,
    }


def load_seed(seed_path: Path) -> list[dict[str, Any]]:
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("seed file must contain a JSON list")
    return [_validate_seed_row(row, index) for index, row in enumerate(data, start=1)]


def build_report(rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
    return {
        "loaded": len(rows),
        "approved": sum(1 for row in rows if row["status"] == "approved"),
        "suggested": sum(1 for row in rows if row["status"] == "suggested"),
        "dry_run": dry_run,
        "artists": [row["artist_name"] for row in rows],
    }


def import_seed(rows: list[dict[str, Any]], *, dry_run: bool, conn=None) -> dict[str, Any]:
    report = build_report(rows, dry_run=dry_run)
    if dry_run:
        return report

    close_conn = conn is None
    if conn is None:
        conn = get_db(readonly=False)
    try:
        for row in rows:
            upsert_genre_source(
                conn,
                artist_name=row["artist_name"],
                spotify_artist_id=row["spotify_artist_id"],
                source=row["source"],
                source_key=row["source_key"],
                raw_genres=row["genres"],
                normalized_genres=row["genres"],
                primary_genre=row["primary_genre"],
                language=row["language"],
                region=row["region"],
                confidence=row["confidence"],
                evidence_url=row["evidence_url"],
                evidence_summary=row["evidence_summary"],
                status=row["status"],
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if close_conn:
            conn.close()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rows = load_seed(args.seed)
        report = import_seed(rows, dry_run=args.dry_run)
    except Exception as exc:
        print(f"import_artist_genre_overrides.py failed: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        write_json_report(report, args.json_output)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

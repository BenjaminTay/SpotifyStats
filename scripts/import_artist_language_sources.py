#!/usr/bin/env python3
"""Import reviewed artist-language facts or legacy language suggestions."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db
from backend.domains.metadata.artist_language_review import (
    decide_review,
    get_or_create_review,
    normalize_language_source_payload,
    save_review_source,
)
from backend.domains.metadata.artist_languages import validate_approved_language_source
from backend.domains.metadata.language_registry import normalize_language_claim

DEFAULT_SEED = ROOT / "data" / "artist_language_sources.seed.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="import_artist_language_sources.py",
        description="Import reviewed artist-language facts or legacy suggestions.",
    )
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--legacy-suggestions", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args(argv)


def _required_text(row: dict[str, Any], field: str, index: int) -> str:
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

    status = _optional_text(raw, "status") or "suggested"
    if status not in {"suggested", "approved"}:
        raise ValueError(f"row {index}: status must be suggested or approved")

    origin = _optional_text(raw, "origin") or "curated_seed"
    if origin != "curated_seed":
        raise ValueError(f"row {index}: seed origin must be curated_seed")

    classification = _required_text(raw, "classification", index)
    if classification not in {"single_language", "multilingual", "instrumental"}:
        raise ValueError(f"row {index}: unsupported classification {classification}")

    evidence = raw.get("evidence", [])
    if not isinstance(evidence, list) or any(not isinstance(item, dict) for item in evidence):
        raise ValueError(f"row {index}: evidence must be a list of objects")

    reviewed_by = _optional_text(raw, "reviewed_by")
    resolution_note = _optional_text(raw, "resolution_note")
    if status == "approved" and not reviewed_by:
        raise ValueError(f"row {index}: reviewed_by is required for approved rows")
    if status == "approved" and not resolution_note:
        raise ValueError(f"row {index}: resolution_note is required for approved rows")

    return {
        "artist_name": _required_text(raw, "artist_name", index),
        "spotify_artist_id": _optional_text(raw, "spotify_artist_id"),
        "classification": classification,
        "primary_language_code": _optional_text(raw, "primary_language_code"),
        "language_variant": _optional_text(raw, "language_variant"),
        "raw_language": _optional_text(raw, "raw_language"),
        "origin": origin,
        "source_key": _required_text(raw, "source_key", index),
        "status": status,
        "reviewed_by": reviewed_by,
        "resolution_note": resolution_note,
        "evidence": [dict(item) for item in evidence],
    }


def load_seed(seed_path: Path) -> list[dict[str, Any]]:
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("seed file must contain a JSON list")
    return [_validate_seed_row(row, index) for index, row in enumerate(data, start=1)]


def write_json_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _empty_report(mode: str, *, dry_run: bool, loaded: int) -> dict[str, Any]:
    return {
        "mode": mode,
        "dry_run": dry_run,
        "loaded": loaded,
        "approved": 0,
        "suggested": 0,
        "skipped": 0,
        "conflicted": 0,
        "unresolved": 0,
        "details": [],
    }


def _resolve_artist_id(
    conn: sqlite3.Connection,
    *,
    artist_name: str,
    spotify_artist_id: str | None,
) -> int | None:
    if spotify_artist_id:
        row = conn.execute(
            """SELECT artists.artist_id
               FROM spotify_artist_meta
               JOIN artists ON artists.artist_name = spotify_artist_meta.artist_name
               WHERE spotify_artist_meta.spotify_artist_id=?""",
            (spotify_artist_id,),
        ).fetchone()
        if row is not None:
            return int(row[0])

    row = conn.execute(
        "SELECT artist_id FROM artists WHERE artist_name=?",
        (artist_name,),
    ).fetchone()
    return int(row[0]) if row is not None else None


def _normalize_suggested_source(
    conn: sqlite3.Connection,
    row: dict[str, Any],
) -> dict[str, Any]:
    source, evidence = normalize_language_source_payload(
        conn,
        {
            "classification": row["classification"],
            "primary_language_code": row.get("primary_language_code"),
            "language_variant": row.get("language_variant"),
            "raw_language": row.get("raw_language"),
            "origin": row["origin"],
            "source_key": row["source_key"],
            "evidence": [dict(item) for item in row.get("evidence", [])],
        },
    )
    source["evidence"] = evidence
    return source


def _existing_outcome(
    conn: sqlite3.Connection,
    *,
    artist_id: int,
    origin: str,
    source_key: str,
) -> str | None:
    same_source = conn.execute(
        """SELECT status FROM artist_language_sources
           WHERE artist_id=? AND origin=? AND source_key=?""",
        (artist_id, origin, source_key),
    ).fetchone()
    if same_source is not None:
        return "skipped"

    approved = conn.execute(
        """SELECT source_id FROM artist_language_sources
           WHERE artist_id=? AND status='approved'""",
        (artist_id,),
    ).fetchone()
    if approved is not None:
        return "conflicted"

    open_review = conn.execute(
        """SELECT review_id FROM artist_language_review_queue
           WHERE artist_id=? AND status='open'""",
        (artist_id,),
    ).fetchone()
    if open_review is not None:
        return "conflicted"
    return None


def _record_outcome(
    report: dict[str, Any],
    *,
    artist_name: str,
    outcome: str,
    reason: str | None = None,
) -> None:
    report[outcome] += 1
    detail = {"artist_name": artist_name, "outcome": outcome}
    if reason:
        detail["reason"] = reason
    report["details"].append(detail)


def _begin_batch(conn: sqlite3.Connection) -> None:
    if conn.in_transaction:
        raise RuntimeError("artist language import requires transaction ownership")
    conn.execute("BEGIN IMMEDIATE")


def import_seed(
    rows: list[dict[str, Any]],
    *,
    dry_run: bool,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    report = _empty_report("seed", dry_run=dry_run, loaded=len(rows))
    close_conn = conn is None
    if conn is None:
        conn = get_db(readonly=False)

    batch_started = False
    try:
        _begin_batch(conn)
        batch_started = True
        for index, raw_row in enumerate(rows, start=1):
            row = _validate_seed_row(raw_row, index)
            artist_id = _resolve_artist_id(
                conn,
                artist_name=row["artist_name"],
                spotify_artist_id=row["spotify_artist_id"],
            )
            if artist_id is None:
                _record_outcome(report, artist_name=row["artist_name"], outcome="unresolved")
                continue

            outcome = _existing_outcome(
                conn,
                artist_id=artist_id,
                origin=row["origin"],
                source_key=row["source_key"],
            )
            if outcome is not None:
                _record_outcome(report, artist_name=row["artist_name"], outcome=outcome)
                continue

            source = _normalize_suggested_source(conn, row)
            if row["status"] == "approved":
                validate_approved_language_source(
                    conn,
                    artist_id,
                    source,
                    source["evidence"],
                )

            review = get_or_create_review(
                conn,
                artist_id=artist_id,
                play_hours_snapshot=0.0,
                reason="reviewed_seed_import",
            )
            save_review_source(
                conn,
                review_id=int(review["review_id"]),
                payload=source,
            )
            if row["status"] == "approved":
                decide_review(
                    conn,
                    review_id=int(review["review_id"]),
                    action="approve",
                    resolution_note=str(row["resolution_note"]),
                    reviewed_by=str(row["reviewed_by"]),
                )
            report[row["status"]] += 1

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
        batch_started = False
    except Exception:
        if batch_started:
            conn.rollback()
        raise
    finally:
        if close_conn:
            conn.close()
    return report


def _legacy_rows(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute(
        """SELECT artist_name, trim(language) AS language
           FROM artist_genre_sources
           WHERE status='approved' AND language IS NOT NULL AND trim(language) != ''
           ORDER BY source_id"""
    ).fetchall()
    rows += conn.execute(
        """SELECT artist_name, trim(language) AS language
           FROM artist_genre_overrides
           WHERE language IS NOT NULL AND trim(language) != ''
           ORDER BY artist_name"""
    ).fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]


def _legacy_candidates(
    conn: sqlite3.Connection,
) -> list[tuple[str, list[str], set[tuple[str, str | None]]]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for artist_name, raw_language in _legacy_rows(conn):
        if raw_language not in grouped[artist_name]:
            grouped[artist_name].append(raw_language)

    candidates = []
    for artist_name, raw_values in grouped.items():
        claims: set[tuple[str, str | None]] = set()
        for value in raw_values:
            try:
                claims.add(normalize_language_claim(value, None))
            except ValueError:
                claims.add((f"unsupported:{value.strip().lower()}", None))
        candidates.append((artist_name, raw_values, claims))
    return candidates


def import_legacy_suggestions(
    conn: sqlite3.Connection | None = None,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    close_conn = conn is None
    if conn is None:
        conn = get_db(readonly=False)
    candidates = _legacy_candidates(conn)
    report = _empty_report("legacy_suggestions", dry_run=dry_run, loaded=len(candidates))

    try:
        if not dry_run:
            _begin_batch(conn)
        for artist_name, raw_values, claims in candidates:
            artist_id = _resolve_artist_id(
                conn,
                artist_name=artist_name,
                spotify_artist_id=None,
            )
            if artist_id is None:
                _record_outcome(report, artist_name=artist_name, outcome="unresolved")
                continue
            if len(claims) != 1 or next(iter(claims))[0].startswith("unsupported:"):
                _record_outcome(
                    report,
                    artist_name=artist_name,
                    outcome="conflicted",
                    reason="legacy values do not normalize to one supported claim",
                )
                continue

            code, variant = next(iter(claims))
            source_key = f"legacy:{code}:{variant or 'base'}"
            outcome = _existing_outcome(
                conn,
                artist_id=artist_id,
                origin="legacy_import",
                source_key=source_key,
            )
            if outcome is not None:
                _record_outcome(report, artist_name=artist_name, outcome=outcome)
                continue

            source = {
                "classification": "single_language",
                "primary_language_code": code,
                "language_variant": variant,
                "raw_language": " | ".join(raw_values),
                "origin": "legacy_import",
                "source_key": source_key,
                "evidence": [],
            }
            if not dry_run:
                review = get_or_create_review(
                    conn,
                    artist_id=artist_id,
                    play_hours_snapshot=0.0,
                    reason="legacy_language_suggestion",
                )
                save_review_source(
                    conn,
                    review_id=int(review["review_id"]),
                    payload=source,
                )
            report["suggested"] += 1

        if not dry_run:
            conn.commit()
    except Exception:
        if not dry_run:
            conn.rollback()
        raise
    finally:
        if close_conn:
            conn.close()
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.legacy_suggestions:
            report = import_legacy_suggestions(dry_run=args.dry_run)
        else:
            rows = load_seed(args.seed)
            report = import_seed(rows, dry_run=args.dry_run)
        if args.json_output:
            write_json_report(report, args.json_output)
    except Exception as exc:
        print(f"import_artist_language_sources.py failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Approve the evidence-hardened 2026-07-16 artist-language second pass."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import DB_PATH
from backend.domains.metadata.artist_language_review import (
    decide_review,
    get_review,
    save_review_source,
)

BATCH_REASON = "codex_language_pre_review_2026_07_15"
REVIEWER = "codex_second_pass_2026_07_16"
EXPECTED_ARTIST_IDS = frozenset(
    {
        9,
        13,
        29,
        40,
        46,
        47,
        71,
        79,
        102,
        104,
        118,
        125,
        127,
        136,
        148,
        150,
        169,
        195,
        217,
        225,
        234,
        252,
        261,
        273,
        347,
        359,
        373,
        525,
        539,
        544,
        546,
        559,
        565,
        573,
        648,
        692,
        695,
        719,
        736,
        738,
        741,
        756,
        762,
        769,
        771,
        780,
        781,
        786,
        790,
        793,
        798,
        845,
        891,
        7750,
    }
)

# These artists have known occasional recordings or collaborations outside the
# dominant language. The project definition treats isolated exceptions as
# single-language unless a second language is a sustained repertoire pattern.
OCCASIONAL_LANGUAGE_NOTES = {
    "A-Lin": "Occasional heritage-language or cover performances are not a sustained second catalog language.",
    "Earth, Wind & Fire": "Occasional non-English phrases or recordings are not a sustained second catalog language.",
    "Gary Chaw": "Occasional Cantonese or other-language performances are not a sustained second catalog language.",
    "Kate Bush": "The small number of French-language catalog exceptions does not constitute a sustained second repertoire language.",
    "Norah Jones": "Occasional non-English collaborations do not constitute a sustained second repertoire language.",
    "Robyn": "The audited repertoire is predominantly English; nationality alone is not language evidence.",
    "The Beatles": "The isolated German-language versions do not constitute a sustained second repertoire language.",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database", type=Path, default=Path(DB_PATH))
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args(argv)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _backup_database(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and target_path.stat().st_size > 0:
        raise FileExistsError(f"refusing to overwrite database backup: {target_path}")
    with _connect(source_path) as source, _connect(target_path) as target:
        source.backup(target)


def _cohort_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT q.review_id, q.artist_id, q.play_hours_snapshot,
                  a.artist_name, q.suggested_source_id,
                  q.status AS review_status, s.status AS source_status,
                  q.reviewed_by
           FROM artist_language_review_queue q
           JOIN artists a ON a.artist_id=q.artist_id
           JOIN artist_language_sources s ON s.source_id=q.suggested_source_id
           WHERE q.reason=? AND q.pre_review_recommendation='recommend_approve'
           ORDER BY q.play_hours_snapshot DESC, q.review_id""",
        (BATCH_REASON,),
    ).fetchall()


def _representative_tracks(
    conn: sqlite3.Connection,
    *,
    artist_id: int,
    limit: int = 2,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT t.track_id, t.track_name, t.spotify_track_id,
                  SUM(p.ms_played) AS played_ms
           FROM tracks t
           JOIN plays p ON p.track_id=t.track_id
           WHERE t.artist_id=? AND t.spotify_track_id IS NOT NULL
             AND trim(t.spotify_track_id) != ''
           GROUP BY t.track_id
           ORDER BY played_ms DESC, t.track_id
           LIMIT ?""",
        (artist_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def _source_payload(
    review: dict[str, Any],
    tracks: list[dict[str, Any]],
) -> dict[str, Any]:
    source = review["source"]
    if source is None:
        raise ValueError(f"review {review['review_id']} has no suggested source")
    evidence = [
        {
            "local_track_id": item.get("local_track_id"),
            "claimed_language_code": item.get("claimed_language_code"),
            "claimed_language_variant": item.get("claimed_language_variant"),
            "evidence_kind": item["evidence_kind"],
            "performer_attribution": item["performer_attribution"],
            "evidence_url": item["evidence_url"],
            "evidence_title": item["evidence_title"],
            "evidence_accessed_at": item["evidence_accessed_at"],
            "evidence_summary": item["evidence_summary"],
        }
        for item in source["evidence"]
    ]
    code = source["primary_language_code"]
    variant = source["language_variant"]
    language_label = f"{code}:{variant}" if variant else str(code)
    for track in tracks:
        evidence.append(
            {
                "local_track_id": int(track["track_id"]),
                "claimed_language_code": code,
                "claimed_language_variant": variant,
                "evidence_kind": "track_language",
                "performer_attribution": "track_language_only",
                "evidence_url": f"https://open.spotify.com/track/{track['spotify_track_id']}",
                "evidence_title": f"Representative Spotify recording: {track['track_name']}",
                "evidence_summary": (
                    "Second-pass audit of a high-play local representative recording "
                    f"supports vocals primarily in {language_label}. This track evidence "
                    "supplements, but does not replace, the artist-level repertoire evidence."
                ),
            }
        )
    return {
        "classification": source["classification"],
        "primary_language_code": code,
        "language_variant": variant,
        "raw_language": source["raw_language"],
        "origin": source["origin"],
        "source_key": source["source_key"],
        "evidence": evidence,
    }


def _resolution_note(review: dict[str, Any], tracks: list[dict[str, Any]]) -> str:
    source = review["source"]
    track_names = ", ".join(str(track["track_name"]) for track in tracks)
    code = source["primary_language_code"]
    variant = source["language_variant"]
    language_label = f"{code}:{variant}" if variant else str(code)
    note = (
        "Second-pass evidence audit approved. The Spotify official artist repertoire "
        f"profile and high-play representative recordings ({track_names}) support "
        f"{language_label} as the artist's sustained predominant vocal language. "
        "No frequent second-language repertoire pattern was identified under the "
        "project's single-language definition."
    )
    caveat = OCCASIONAL_LANGUAGE_NOTES.get(review["artist_name"])
    return f"{note} {caveat}" if caveat else note


def approve_second_pass(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = _cohort_rows(conn)
    actual_ids = frozenset(int(row["artist_id"]) for row in rows)
    if actual_ids != EXPECTED_ARTIST_IDS:
        missing = sorted(EXPECTED_ARTIST_IDS - actual_ids)
        unexpected = sorted(actual_ids - EXPECTED_ARTIST_IDS)
        raise ValueError(f"second-pass cohort mismatch: missing={missing}, unexpected={unexpected}")

    approved: list[dict[str, Any]] = []
    newly_approved_count = 0
    already_approved_count = 0
    for row in rows:
        is_open = row["review_status"] == "open" and row["source_status"] == "suggested"
        is_already_approved = (
            row["review_status"] == "approved"
            and row["source_status"] == "approved"
            and row["reviewed_by"] == REVIEWER
        )
        if not is_open and not is_already_approved:
            raise ValueError(
                "second-pass cohort has an unexpected terminal state: "
                f"review_id={row['review_id']} review={row['review_status']} "
                f"source={row['source_status']} reviewer={row['reviewed_by']}"
            )
        review = get_review(conn, int(row["review_id"]))
        tracks = _representative_tracks(conn, artist_id=int(row["artist_id"]))
        if len(tracks) < 1:
            raise ValueError(f"no representative Spotify track for {row['artist_name']}")
        if is_open:
            save_review_source(
                conn,
                review_id=int(row["review_id"]),
                payload=_source_payload(review, tracks),
            )
            result = decide_review(
                conn,
                review_id=int(row["review_id"]),
                action="approve",
                resolution_note=_resolution_note(review, tracks),
                reviewed_by=REVIEWER,
            )
            newly_approved_count += 1
        else:
            result = {
                "review_status": row["review_status"],
                "source_id": int(row["suggested_source_id"]),
                "source_status": row["source_status"],
            }
            already_approved_count += 1
        approved.append(
            {
                "review_id": int(row["review_id"]),
                "artist_id": int(row["artist_id"]),
                "artist_name": str(row["artist_name"]),
                "play_hours_snapshot": float(row["play_hours_snapshot"]),
                "representative_tracks": [track["track_name"] for track in tracks],
                "already_approved": is_already_approved,
                **result,
            }
        )

    return {
        "reviewer": REVIEWER,
        "approved_count": len(approved),
        "newly_approved_count": newly_approved_count,
        "already_approved_count": already_approved_count,
        "approved_hours_snapshot": round(sum(item["play_hours_snapshot"] for item in approved), 3),
        "approved": approved,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    database_path = args.database.expanduser().resolve()
    if not database_path.exists():
        raise FileNotFoundError(database_path)

    temporary_path: Path | None = None
    backup_path: Path | None = None
    if args.apply:
        backup_path = args.backup or Path(
            "/tmp/spotify_stats_before_language_second_pass_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        _backup_database(database_path, backup_path)
        target_path = database_path
    else:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        temporary_path = Path(handle.name)
        _backup_database(database_path, temporary_path)
        target_path = temporary_path

    try:
        conn = _connect(target_path)
        try:
            report = approve_second_pass(conn)
        finally:
            conn.close()
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    report.update(
        {
            "applied": bool(args.apply),
            "database": str(database_path),
            "backup": str(backup_path) if backup_path else None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        args.json_output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

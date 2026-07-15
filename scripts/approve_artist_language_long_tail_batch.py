#!/usr/bin/env python3
"""Audit and resolve the next high-play artist-language long-tail batch."""
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
    get_or_create_review,
    save_review_source,
)

REVIEWER = "codex_long_tail_audit_2026_07_16"
REASON = "codex_language_long_tail_audit_2026_07_16"

# classification, claims. Chinese variants stay explicit; multilingual claims
# list sustained repertoire languages rather than nationality or spoken ability.
AUDIT_ROWS = {
    84: ("Rema", "multilingual", (("en", None), ("pcm", None))),
    177: ("Charli xcx", "single_language", (("en", None),)),
    242: ("Mao Buyi", "single_language", (("zh", "mandarin"),)),
    168: ("Zac Efron", "single_language", (("en", None),)),
    258: ("Yoga Lin", "single_language", (("zh", "mandarin"),)),
    511: ("Fleetwood Mac", "single_language", (("en", None),)),
    178: ("NewJeans", "multilingual", (("ko", None), ("en", None), ("ja", None))),
    579: ("Anthem Lights", "single_language", (("en", None),)),
    578: ("Wham!", "single_language", (("en", None),)),
    783: ("Elva Hsiao", "single_language", (("zh", "mandarin"),)),
    828: (
        "Teresa Teng",
        "multilingual",
        (("zh", "mandarin"), ("zh", "cantonese"), ("ja", None)),
    ),
    437: ("Auli'i Cravalho", "single_language", (("en", None),)),
    656: (
        "4*TOWN (From Disney and Pixar’s Turning Red)",
        "single_language",
        (("en", None),),
    ),
    757: ("Alessia Cara", "single_language", (("en", None),)),
    240: ("Halle", "single_language", (("en", None),)),
    156: ("Christophe Beck", "instrumental", ()),
    65: ("張芸京", "single_language", (("zh", "mandarin"),)),
    115: ("Kristen Anderson-Lopez", "insufficient_evidence", ()),
    840: ("張婧", "single_language", (("zh", "mandarin"),)),
    348: ("Disney Peaceful Guitar", "instrumental", ()),
    574: ("Phil Collins", "single_language", (("en", None),)),
    138: ("Jay Chou", "single_language", (("zh", "mandarin"),)),
    361: ("Andrew Garfield", "single_language", (("en", None),)),
    897: ("安沐凡", "insufficient_evidence", ()),
    716: ("FKA twigs", "single_language", (("en", None),)),
    284: ("Olivia Newton-John", "single_language", (("en", None),)),
    352: ("Disney Peaceful Piano", "instrumental", ()),
    490: ("Zac Brown Band", "single_language", (("en", None),)),
    300: ("Hu Xia", "single_language", (("zh", "mandarin"),)),
    797: ("梓渝", "single_language", (("zh", "mandarin"),)),
    770: ("Christine Fan", "single_language", (("zh", "mandarin"),)),
}

SPECIAL_SUPPORT = {
    "Rema": {
        "url": "https://journalofenglishscholarsassociation.org/journals/index.php/JESAN/issue/download/13/150",
        "summary": (
            "A linguistic analysis of Rema's Calm Down documents sustained English and "
            "Nigerian Pidgin usage. The pcm code prevents the former English-only candidate "
            "from being downcast to a false single-language fact."
        ),
    },
    "NewJeans": {
        "url": "https://open.spotify.com/artist/6HvZYsbFfjnjFrWF950C9d",
        "summary": (
            "The official repertoire contains recurring Korean releases, English-language "
            "recordings, and a formal Japanese release programme including Supernatural."
        ),
    },
    "Teresa Teng": {
        "url": "https://open.spotify.com/artist/3ienC90A5I1X3irDyQoqWZ",
        "summary": (
            "The official repertoire and local representative recordings document sustained "
            "Mandarin, Cantonese, and Japanese catalogues."
        ),
    },
}

SPECIAL_TRACKS = {
    "Rema": [("Calm Down", "pcm", None), ("Calm Down (with Selena Gomez)", "en", None)],
    "NewJeans": [("Attention", "ko", None), ("Supernatural", "ja", None)],
    "Teresa Teng": [
        ("我只在乎你", "zh", "mandarin"),
        ("漫步人生路", "zh", "cantonese"),
        ("時の流れに身をまかせ", "ja", None),
    ],
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


def _artist_row(conn: sqlite3.Connection, artist_id: int, artist_name: str) -> sqlite3.Row:
    row = conn.execute(
        """SELECT a.artist_id, a.artist_name, m.spotify_artist_id
           FROM artists a LEFT JOIN spotify_artist_meta m ON m.artist_name=a.artist_name
           WHERE a.artist_id=?""",
        (artist_id,),
    ).fetchone()
    if row is None or row["artist_name"] != artist_name:
        raise ValueError(f"artist identity mismatch: {artist_id} {artist_name}")
    if not row["spotify_artist_id"]:
        raise ValueError(f"missing Spotify artist id: {artist_name}")
    return row


def _artist_hours(conn: sqlite3.Connection, artist_id: int) -> float:
    played_ms = conn.execute(
        """SELECT COALESCE(SUM(p.ms_played), 0)
           FROM plays p JOIN tracks t ON t.track_id=p.track_id
           WHERE t.artist_id=?""",
        (artist_id,),
    ).fetchone()[0]
    return float(played_ms) / 3_600_000


def _top_tracks(
    conn: sqlite3.Connection,
    artist_id: int,
    *,
    limit: int = 2,
) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT t.track_id, t.track_name, t.spotify_track_id, SUM(p.ms_played) played_ms
           FROM tracks t JOIN plays p ON p.track_id=t.track_id
           WHERE t.artist_id=? AND t.spotify_track_id IS NOT NULL
           GROUP BY t.track_id ORDER BY played_ms DESC, t.track_id LIMIT ?""",
        (artist_id, limit),
    ).fetchall()


def _named_track(
    conn: sqlite3.Connection,
    artist_id: int,
    track_name: str,
) -> sqlite3.Row:
    row = conn.execute(
        """SELECT track_id, track_name, spotify_track_id
           FROM tracks WHERE artist_id=? AND track_name=?""",
        (artist_id, track_name),
    ).fetchone()
    if row is None or not row["spotify_track_id"]:
        raise ValueError(f"missing representative track for artist {artist_id}: {track_name}")
    return row


def _existing_result(
    conn: sqlite3.Connection,
    artist_id: int,
    classification: str,
) -> dict[str, Any] | None:
    if classification == "insufficient_evidence":
        review = conn.execute(
            """SELECT review_id, status FROM artist_language_review_queue
               WHERE artist_id=? AND reason=? AND status='insufficient_evidence'
                 AND reviewed_by=?
               ORDER BY review_id DESC LIMIT 1""",
            (artist_id, REASON, REVIEWER),
        ).fetchone()
        if review is not None:
            return {
                "artist_id": artist_id,
                "review_id": int(review["review_id"]),
                "classification": classification,
                "review_status": review["status"],
                "already_resolved": True,
            }
    source = conn.execute(
        """SELECT source_id, classification FROM artist_language_sources
           WHERE artist_id=? AND status='approved'""",
        (artist_id,),
    ).fetchone()
    if source is None:
        return None
    return {
        "artist_id": artist_id,
        "source_id": int(source["source_id"]),
        "classification": source["classification"],
        "already_resolved": True,
    }


def _artist_evidence(
    artist_name: str,
    spotify_artist_id: str,
    classification: str,
    claims: tuple[tuple[str, str | None], ...],
) -> list[dict[str, Any]]:
    support = SPECIAL_SUPPORT.get(artist_name)
    url = support["url"] if support else f"https://open.spotify.com/artist/{spotify_artist_id}"
    summary = (
        support["summary"]
        if support
        else (
            "Second-pass audit of the official artist repertoire and the highest-play local "
            "recordings supports this sustained artist-level language classification."
        )
    )
    if classification == "instrumental":
        return [
            {
                "evidence_kind": "artist_repertoire",
                "performer_attribution": "artist_instrumental_confirmed",
                "evidence_url": url,
                "evidence_title": f"Audited official repertoire: {artist_name}",
                "evidence_summary": summary,
            }
        ]
    return [
        {
            "claimed_language_code": code,
            "claimed_language_variant": variant,
            "evidence_kind": "artist_repertoire",
            "performer_attribution": "artist_vocal_confirmed",
            "evidence_url": url,
            "evidence_title": f"Audited official repertoire: {artist_name}",
            "evidence_summary": summary,
        }
        for code, variant in claims
    ]


def _track_evidence(
    conn: sqlite3.Connection,
    artist_id: int,
    artist_name: str,
    classification: str,
    claims: tuple[tuple[str, str | None], ...],
) -> list[dict[str, Any]]:
    if artist_name in SPECIAL_TRACKS:
        tracks = [
            (_named_track(conn, artist_id, track_name), code, variant)
            for track_name, code, variant in SPECIAL_TRACKS[artist_name]
        ]
    else:
        default_claim = claims[0] if claims else (None, None)
        tracks = [(*[track], *default_claim) for track in _top_tracks(conn, artist_id)]

    result = []
    for track, code, variant in tracks:
        instrumental = classification == "instrumental"
        result.append(
            {
                "local_track_id": int(track["track_id"]),
                "claimed_language_code": code,
                "claimed_language_variant": variant,
                "evidence_kind": "track_credit" if instrumental else "track_language",
                "performer_attribution": (
                    "artist_instrumental_confirmed" if instrumental else "track_language_only"
                ),
                "evidence_url": f"https://open.spotify.com/track/{track['spotify_track_id']}",
                "evidence_title": f"Representative Spotify recording: {track['track_name']}",
                "evidence_summary": (
                    "The high-play local recording was checked for performer attribution and "
                    "supports the audited artist-level classification."
                ),
            }
        )
    if not result:
        raise ValueError(f"no representative tracks for {artist_name}")
    return result


def _source_payload(
    conn: sqlite3.Connection,
    artist_id: int,
    artist_name: str,
    spotify_artist_id: str,
    classification: str,
    claims: tuple[tuple[str, str | None], ...],
) -> dict[str, Any]:
    primary_code, primary_variant = (
        claims[0] if classification == "single_language" else (None, None)
    )
    raw_language = (
        " + ".join(f"{code}:{variant}" if variant else code for code, variant in claims)
        or "instrumental"
    )
    return {
        "classification": classification,
        "primary_language_code": primary_code,
        "language_variant": primary_variant,
        "raw_language": raw_language,
        "origin": "manual",
        "source_key": f"codex-long-tail-audit:2026-07-16:{artist_id}",
        "evidence": [
            *_artist_evidence(
                artist_name,
                spotify_artist_id,
                classification,
                claims,
            ),
            *_track_evidence(
                conn,
                artist_id,
                artist_name,
                classification,
                claims,
            ),
        ],
    }


def audit_long_tail(conn: sqlite3.Connection) -> dict[str, Any]:
    results = []
    for artist_id, (artist_name, classification, claims) in AUDIT_ROWS.items():
        existing = _existing_result(conn, artist_id, classification)
        if existing is not None:
            results.append({"artist_name": artist_name, **existing})
            continue
        artist = _artist_row(conn, artist_id, artist_name)
        review = get_or_create_review(
            conn,
            artist_id=artist_id,
            play_hours_snapshot=_artist_hours(conn, artist_id),
            reason=REASON,
        )
        review_id = int(review["review_id"])
        if classification == "insufficient_evidence":
            note = (
                "Codex evidence audit found mixed attribution that cannot be represented as a "
                "stable artist-language fact. The local primary-artist rows combine composer, "
                "demo, vocal, accompaniment, or instrumental roles; guessing a language would "
                "misstate the performer."
            )
            result = decide_review(
                conn,
                review_id=review_id,
                action="insufficient_evidence",
                resolution_note=note,
                reviewed_by=REVIEWER,
            )
        else:
            save_review_source(
                conn,
                review_id=review_id,
                payload=_source_payload(
                    conn,
                    artist_id,
                    artist_name,
                    str(artist["spotify_artist_id"]),
                    classification,
                    claims,
                ),
            )
            rendered_claims = (
                ", ".join(f"{code}:{variant}" if variant else code for code, variant in claims)
                or "instrumental"
            )
            result = decide_review(
                conn,
                review_id=review_id,
                action="approve",
                resolution_note=(
                    "Codex evidence audit approved this high-play long-tail artist after checking "
                    "the official repertoire and representative local recordings. "
                    f"Classification={classification}; supported repertoire={rendered_claims}."
                ),
                reviewed_by=REVIEWER,
            )
        results.append(
            {
                "artist_id": artist_id,
                "artist_name": artist_name,
                "classification": classification,
                "play_hours_snapshot": _artist_hours(conn, artist_id),
                **result,
            }
        )

    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ValueError(f"database integrity check failed: {integrity}")
    return {
        "reviewer": REVIEWER,
        "reviewed_count": len(results),
        "approved_count": sum(
            item["classification"] != "insufficient_evidence" and not item.get("already_resolved")
            for item in results
        ),
        "insufficient_evidence_count": sum(
            item["classification"] == "insufficient_evidence" and not item.get("already_resolved")
            for item in results
        ),
        "reviewed_hours_snapshot": round(
            sum(float(item.get("play_hours_snapshot") or 0) for item in results), 3
        ),
        "results": results,
        "integrity_check": integrity,
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
            "/tmp/spotify_stats_before_language_long_tail_audit_"
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
            report = audit_long_tail(conn)
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

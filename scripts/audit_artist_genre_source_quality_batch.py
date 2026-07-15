#!/usr/bin/env python3
"""Audit the highest-impact LLM Genre sources against reliable references."""
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

from backend.core.db import DB_PATH, load_plays
from backend.domains.metadata.artist_genre_review import review_suggestion
from backend.domains.metadata.artist_genres import (
    compute_genre_taxonomy_audit,
    upsert_genre_source,
)
from backend.domains.metadata.artist_languages import build_primary_artist_ms

REVIEWER = "codex_genre_quality_audit_2026_07_16"
REASON = "genre_source_quality_audit_2026_07_16"
SOURCE_KEY_PREFIX = "codex-genre-quality-audit:2026-07-16"
TARGET_STYLES = {"electronic/dance", "hip hop/rap"}

# These values describe sustained artist-level styles supported by the linked
# profile. Incidental collaborations and isolated era influences are excluded.
DECISIONS: dict[str, dict[str, Any]] = {
    "Chappell Roan": {
        "genres": ["pop", "dance-pop"],
        "confidence": 0.94,
        "url": "https://www.allmusic.com/artist/chappell-roan-mn0003654352",
        "summary": (
            "AllMusic classifies Chappell Roan as a pop/electronic artist and explicitly "
            "describes her sustained sound as anthemic dance-pop."
        ),
    },
    "Kesha": {
        "genres": ["pop", "dance-pop", "electropop"],
        "confidence": 0.94,
        "url": "https://www.allmusic.com/artist/kesha-mn0000080358",
        "summary": (
            "AllMusic identifies Kesha as a pop artist known for dance anthems and an "
            "exuberant electro-pop sound, supporting pop and electronic/dance axes."
        ),
    },
    "Beyoncé": {
        "genres": ["pop", "r&b", "dance-pop"],
        "confidence": 0.95,
        "url": "https://www.allmusic.com/artist/beyonc%C3%A9-mn0000761179",
        "summary": (
            "AllMusic describes Beyoncé as a pop-R&B artist and lists contemporary R&B, "
            "pop, and dance-pop. Her dance/electronic repertoire is also formally recognized "
            "by the Recording Academy. Hip-hop is removed as an equal lifetime artist style."
        ),
    },
    "Troye Sivan": {
        "genres": ["pop", "synth-pop"],
        "confidence": 0.93,
        "url": "https://music.apple.com/us/artist/troye-sivan/396295677",
        "summary": (
            "Apple Music identifies Troye Sivan as a pop artist and describes the sustained "
            "synth-pop direction of his catalogue."
        ),
    },
    "Halsey": {
        "genres": ["pop", "electronic", "alternative rock"],
        "confidence": 0.92,
        "url": "https://www.allmusic.com/artist/halsey-mn0003010517",
        "summary": (
            "AllMusic describes Halsey's recurring blend of pop, electronic, and alternative "
            "rock, so all three supported style families remain explicit."
        ),
    },
    "Selena Gomez": {
        "genres": ["pop", "dance-pop"],
        "confidence": 0.93,
        "url": "https://www.allmusic.com/artist/selena-gomez-mn0000996096",
        "summary": (
            "AllMusic lists Selena Gomez under pop, club/dance, and dance-pop. The former "
            "LLM-added R&B label is removed because this source does not support it as a "
            "stable artist-level style."
        ),
    },
    "Rihanna": {
        "genres": ["pop", "r&b", "dance-pop"],
        "confidence": 0.94,
        "url": "https://www.allmusic.com/artist/rihanna-mn0000367188",
        "summary": (
            "AllMusic documents Rihanna's sustained mixture of pop, R&B, dancehall, and EDM; "
            "the statistical fallback retains the three supported style families."
        ),
    },
    "RAYE": {
        "genres": ["pop", "dance-pop"],
        "confidence": 0.91,
        "url": "https://www.allmusic.com/artist/raye-mn0002593543",
        "summary": (
            "AllMusic classifies RAYE as pop and dance-pop. R&B is omitted from the "
            "artist-level fallback because the audited profile does not establish it as an "
            "equal long-term classification."
        ),
    },
    "Carly Rae Jepsen": {
        "genres": ["pop", "dance-pop"],
        "confidence": 0.93,
        "url": "https://www.allmusic.com/artist/carly-rae-jepsen-mn0002089077",
        "summary": (
            "AllMusic identifies Carly Rae Jepsen as a pop artist with a sustained dance-pop "
            "style and an extensively documented dance-oriented catalogue."
        ),
    },
    "Nicki Minaj": {
        "genres": ["hip hop", "pop"],
        "confidence": 0.95,
        "url": "https://music.apple.com/us/artist/nicki-minaj/278464538",
        "summary": (
            "Apple Music classifies Nicki Minaj as Hip-Hop/Rap and describes her sharp pop "
            "instincts as a sustained part of her catalogue."
        ),
    },
    "Doja Cat": {
        "genres": ["hip hop", "pop", "r&b"],
        "confidence": 0.93,
        "url": "https://www.allmusic.com/artist/doja-cat-mn0003341964",
        "summary": (
            "AllMusic documents Doja Cat's recurring hip-hop, pop, and R&B repertoire and "
            "her later return to rap and hip-hop roots."
        ),
    },
    "Lil Nas X": {
        "genres": ["pop rap"],
        "confidence": 0.94,
        "url": "https://www.allmusic.com/artist/lil-nas-x-mn0003827666",
        "summary": (
            "AllMusic classifies Lil Nas X as a rap artist whose genre-blurring catalogue "
            "sustains both hip-hop and pop-rap, so the fallback uses pop rap rather than an "
            "undifferentiated hip-hop-only label."
        ),
    },
    "Lizzo": {
        "genres": ["hip hop", "r&b", "pop"],
        "confidence": 0.92,
        "url": "https://www.allmusic.com/artist/lizzo-mn0003167672",
        "summary": (
            "AllMusic describes Lizzo as a singer/rapper combining Houston rap, gospel soul, "
            "R&B, and crossover pop repertoire."
        ),
    },
    "Cardi B": {
        "genres": ["hip hop"],
        "confidence": 0.96,
        "url": "https://music.apple.com/gb/artist/cardi-b/956078923",
        "summary": (
            "Apple Music classifies Cardi B as Hip-Hop/Rap. The previous generic pop label is "
            "removed because crossover popularity alone is not an artist-level style fact."
        ),
    },
    "Ice Spice": {
        "genres": ["hip hop", "drill"],
        "confidence": 0.96,
        "url": "https://www.allmusic.com/artist/ice-spice-mn0004302959",
        "summary": (
            "AllMusic identifies Ice Spice as a Bronx drill rapper and lists rap, drill, and "
            "East Coast rap as her sustained styles."
        ),
    },
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


def _artist_hours(conn: sqlite3.Connection) -> dict[str, float]:
    plays = load_plays(
        conn,
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=None,
    )
    artist_ms, _ = build_primary_artist_ms(conn, plays)
    if not artist_ms:
        return {}
    placeholders = ",".join("?" for _ in artist_ms)
    rows = conn.execute(
        f"SELECT artist_id, artist_name FROM artists WHERE artist_id IN ({placeholders})",
        list(artist_ms),
    ).fetchall()
    names = {int(row["artist_id"]): str(row["artist_name"]) for row in rows}
    return {
        names[artist_id]: float(ms) / 3_600_000
        for artist_id, ms in artist_ms.items()
        if artist_id in names and ms > 0
    }


def _risk_snapshot(conn: sqlite3.Connection, artist_hours: dict[str, float]) -> dict[str, Any]:
    audit = compute_genre_taxonomy_audit(conn, artist_hours)
    rows = {
        row["name"]: {
            "hours": row["hours"],
            "confidence_tier": row["confidence_tier"],
            "source_mix": row["source_mix"],
            "risk_flags": row["risk_flags"],
        }
        for row in audit["top_canonical_genres"]
        if row["name"] in TARGET_STYLES
    }
    return {
        "style_axis": next(row for row in audit["axis_summary"] if row["axis"] == "style"),
        "target_styles": rows,
    }


def _spotify_artist_id(conn: sqlite3.Connection, artist_name: str) -> str:
    row = conn.execute(
        "SELECT spotify_artist_id FROM spotify_artist_meta WHERE artist_name=?",
        (artist_name,),
    ).fetchone()
    if row is None or not row["spotify_artist_id"]:
        raise ValueError(f"missing Spotify artist identity: {artist_name}")
    return str(row["spotify_artist_id"])


def _ensure_open_review(
    conn: sqlite3.Connection,
    *,
    artist_name: str,
    play_hours: float,
    decision: dict[str, Any],
) -> int | None:
    source_key = f"{SOURCE_KEY_PREFIX}:{artist_name}"
    existing = conn.execute(
        """SELECT source_id, status FROM artist_genre_sources
           WHERE artist_name=? AND source='external_consensus' AND source_key=?""",
        (artist_name, source_key),
    ).fetchone()
    if existing is not None and existing["status"] == "approved":
        review = conn.execute(
            """SELECT review_id FROM artist_genre_review_queue
               WHERE suggested_source_id=? AND status='approved' AND reviewed_by=?""",
            (int(existing["source_id"]), REVIEWER),
        ).fetchone()
        if review is None:
            raise ValueError(f"approved source lacks matching audit review: {artist_name}")
        return None

    if existing is None:
        genres = list(decision["genres"])
        upsert_genre_source(
            conn,
            artist_name=artist_name,
            spotify_artist_id=_spotify_artist_id(conn, artist_name),
            source="external_consensus",
            source_key=source_key,
            raw_genres=genres,
            normalized_genres=genres,
            primary_genre=genres[0],
            language=None,
            region=None,
            confidence=float(decision["confidence"]),
            evidence_url=str(decision["url"]),
            evidence_summary=str(decision["summary"]),
            status="suggested",
        )
        source_id = int(
            conn.execute(
                """SELECT source_id FROM artist_genre_sources
                   WHERE artist_name=? AND source='external_consensus' AND source_key=?""",
                (artist_name, source_key),
            ).fetchone()["source_id"]
        )
        cursor = conn.execute(
            """INSERT INTO artist_genre_review_queue(
                   artist_name, play_hours, reason, suggested_source_id, status)
               VALUES (?, ?, ?, ?, 'open')""",
            (artist_name, float(play_hours), REASON, source_id),
        )
        conn.commit()
        return int(cursor.lastrowid)

    if existing["status"] != "suggested":
        raise ValueError(f"unexpected source state for {artist_name}: {existing['status']}")
    review = conn.execute(
        """SELECT review_id FROM artist_genre_review_queue
           WHERE suggested_source_id=? AND status='open' ORDER BY review_id DESC LIMIT 1""",
        (int(existing["source_id"]),),
    ).fetchone()
    if review is None:
        raise ValueError(f"suggested source lacks open review: {artist_name}")
    return int(review["review_id"])


def audit_batch(conn: sqlite3.Connection) -> dict[str, Any]:
    artist_hours = _artist_hours(conn)
    missing = set(DECISIONS) - set(artist_hours)
    if missing:
        raise ValueError(f"audited artists missing from current play data: {sorted(missing)}")
    before = _risk_snapshot(conn, artist_hours)
    results = []
    for artist_name, decision in DECISIONS.items():
        review_id = _ensure_open_review(
            conn,
            artist_name=artist_name,
            play_hours=artist_hours[artist_name],
            decision=decision,
        )
        if review_id is None:
            results.append({"artist_name": artist_name, "already_resolved": True})
            continue
        result = review_suggestion(
            conn,
            review_id=review_id,
            decision="approve",
            reviewed_by=REVIEWER,
            resolution_note=(
                "Codex evidence audit replaced the unlinked LLM fallback with a reliable "
                "artist-level external source. Genres="
                f"{', '.join(decision['genres'])}. The decision keeps only sustained styles "
                "supported by the cited profile and excludes incidental collaborations or "
                "isolated era influences."
            ),
        )
        results.append(
            {
                "artist_name": artist_name,
                "play_hours": round(artist_hours[artist_name], 3),
                "genres": decision["genres"],
                **result,
            }
        )

    after = _risk_snapshot(conn, artist_hours)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ValueError(f"database integrity check failed: {integrity}")
    open_reviews = conn.execute(
        "SELECT COUNT(*) FROM artist_genre_review_queue WHERE reason=? AND status='open'",
        (REASON,),
    ).fetchone()[0]
    return {
        "reviewer": REVIEWER,
        "audited_count": len(results),
        "approved_count": sum(not row.get("already_resolved") for row in results),
        "results": results,
        "before": before,
        "after": after,
        "remaining_batch_open_reviews": int(open_reviews),
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
            "/tmp/spotify_stats_before_genre_quality_audit_"
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
            report = audit_batch(conn)
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

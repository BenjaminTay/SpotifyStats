#!/usr/bin/env python3
"""Resolve the audited high-impact Genre and Language review batch."""
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
from backend.domains.metadata.artist_genre_review import review_suggestion
from backend.domains.metadata.artist_language_review import (
    decide_review,
    get_review,
    save_review_source,
)

REVIEWER = "codex_evidence_audit_2026_07_16"
LANGUAGE_BATCH_REASON = "codex_language_pre_review_2026_07_15"

GENRE_DECISIONS = {
    "Michael Wong": {
        "genres": ["pop"],
        "confidence": 0.92,
        "evidence_url": "https://music.apple.com/us/artist/michael-wong/152368592",
        "evidence_summary": (
            "Apple Music describes Michael Wong's Mandopop repertoire through authentic "
            "pop melodies and ballad-led arrangements. Pop is the conservative artist-level "
            "style; C-Pop remains a separate scene axis."
        ),
    },
    "Stefanie Sun": {
        "genres": ["pop"],
        "confidence": 0.91,
        "evidence_url": "https://music.apple.com/us/artist/yanzi-sun/83405200",
        "evidence_summary": (
            "Apple Music identifies Stefanie Sun as Mandopop royalty and describes her work "
            "as pop and ballad repertoire. Pop is retained without promoting broad alternative "
            "influences to a second equal-weight style."
        ),
    },
    "A-Mei Chang": {
        "genres": ["pop", "rock"],
        "confidence": 0.93,
        "evidence_url": "https://www.moc.gov.tw/en/News_Content2.aspx?n=489&s=17832",
        "evidence_summary": (
            "Taiwan's Ministry of Culture identifies A-Mei as a pop diva and documents the "
            "Amit alter ego as an experimental rock-and-roll artist. Pop and rock are both "
            "supported, with the artist-level era caveat recorded in the resolution note."
        ),
    },
    "Fish Leong": {
        "genres": ["pop"],
        "confidence": 0.92,
        "evidence_url": "https://music.apple.com/ng/artist/fish-leong/531134701",
        "evidence_summary": (
            "Apple Music describes Fish Leong as a Chinese and Malaysian pop-ballad singer. "
            "Pop is the supported style while Mandopop remains a separate scene label."
        ),
    },
    "JJ Lin": {
        "genres": ["pop", "r&b"],
        "confidence": 0.91,
        "evidence_url": "https://www.allmusic.com/artist/jj-lin-mn0002327509",
        "evidence_summary": (
            "AllMusic describes JJ Lin as an R&B-influenced Mandopop singer-songwriter, and "
            "Apple Music separately documents his pop sensibility and soulful arrangements. "
            "Pop and R&B are recurring artist-level styles; C-Pop and songwriter role remain "
            "separate axes."
        ),
    },
    "G.E.M.": {
        "genres": ["pop"],
        "confidence": 0.91,
        "evidence_url": "https://music.apple.com/us/artist/g-e-m/425208570",
        "evidence_summary": (
            "Apple Music identifies G.E.M. as a versatile pop artist with dance cuts and piano "
            "ballads. Pop is approved as the stable artist-level style. The earlier dance-pop "
            "and R&B candidate is narrowed because the available evidence does not justify "
            "equal lifetime allocation to those secondary styles."
        ),
    },
}

LANGUAGE_DECISIONS = {
    "Fiona Sit": "approve",
    "Wicked Movie Cast": "approve",
    "FIFTY FIFTY": "approve",
    "Terence Lam": "approve",
    "Crowd Lu": "approve",
    "Jacky Cheung": "approve",
    "BLACKPINK": "approve",
    "Karen Mok": "approve",
    "Shakira": "approve",
    "Rema": "insufficient_evidence",
    "Sandy Lam": "approve",
    "LISA": "approve",
    "Ryuichi Sakamoto": "approve",
    "TWICE": "approve",
    "Céline Dion": "approve",
}

# Claims here supplement the original Spotify artist-repertoire evidence. They
# use official artist, label, studio, or established editorial sources.
LANGUAGE_SUPPORT = {
    "Fiona Sit": {
        "url": "https://music.apple.com/us/artist/fiona-sit/201542612",
        "title": "Fiona Sit catalogue and Mandarin-version releases",
        "claims": [("zh", "cantonese"), ("zh", "mandarin")],
        "summary": (
            "The catalogue includes a sustained Cantonese repertoire and explicit Mandarin "
            "releases; the local history contains both the Cantonese song 奇洛李維斯回信 and "
            "蘇州河 - 慕容雪 - Mandarin Version."
        ),
    },
    "Wicked Movie Cast": {
        "url": "https://www.universalmusic.ca/press-releases/wicked-the-soundtrack-shatters-records-to-become-the-film-musical-event-of-the-decade/",
        "title": "Universal Music official Wicked soundtrack release",
        "claims": [("en", None)],
        "summary": (
            "Universal Music's official soundtrack release identifies the English-language "
            "film cast and track programme. The Spotify artist is a stable cast entity rather "
            "than a person, but its credited vocal repertoire is consistently English."
        ),
    },
    "FIFTY FIFTY": {
        "url": "https://www.nme.com/features/music-features/fifty-fifty-the-beginning-cupid-interview-3402970",
        "title": "FIFTY FIFTY interview on Cupid Korean and English versions",
        "claims": [("ko", None), ("en", None)],
        "summary": (
            "The group interview distinguishes the Korean original from the English Twin "
            "Version. Both are formal artist releases, establishing a sustained multilingual "
            "catalogue rather than incidental code-switching."
        ),
    },
    "Terence Lam": {
        "url": "https://music.apple.com/us/artist/terence-lam/1052638496",
        "title": "Apple Music Terence Lam catalogue profile",
        "claims": [("zh", "cantonese")],
        "summary": (
            "Apple Music identifies Terence Lam as a Cantopop vocalist, and the audited local "
            "catalogue consists of Cantonese releases. No sustained second-language vocal "
            "catalogue was established."
        ),
    },
    "Crowd Lu": {
        "url": "https://www.moc.gov.tw/en/News_Content2.aspx?n=489&s=118877&sms=10723",
        "title": "Taiwan Ministry of Culture profile for Crowd Lu",
        "claims": [("zh", "mandarin"), ("zh", "minnan")],
        "summary": (
            "The Ministry of Culture profile documents Crowd Lu's Mandarin catalogue and the "
            "award-winning song 魚仔; the official Spotify recording and vocal audit identify "
            "魚仔 as Minnan/Taiwanese. Both are recurring repertoire languages."
        ),
    },
    "Jacky Cheung": {
        "url": "https://www.jackycheung.com/main/index.php",
        "title": "Jacky Cheung official catalogue",
        "claims": [("zh", "cantonese"), ("zh", "mandarin")],
        "summary": (
            "The official catalogue spans long-running Cantonese and Mandarin album series. "
            "Both languages are substantial artist repertoires, not isolated alternate versions."
        ),
    },
    "BLACKPINK": {
        "url": "https://time.com/5896487/blackpink-the-album/",
        "title": "TIME review of BLACKPINK's Korean-English repertoire",
        "claims": [("ko", None), ("en", None)],
        "summary": (
            "The album review identifies sustained Korean-English performance and several "
            "fully English recordings alongside Korean tracks. The official YG discography "
            "confirms these releases belong to the group."
        ),
    },
    "Karen Mok": {
        "url": "https://karenmok.com/biography",
        "title": "Karen Mok official biography",
        "claims": [("zh", "cantonese"), ("zh", "mandarin"), ("en", None)],
        "summary": (
            "Karen Mok's official biography states that her released repertoire is performed "
            "in Cantonese, Mandarin, and English. English is therefore added to the original "
            "two-language candidate before approval."
        ),
        "raw_language": "zh:cantonese + zh:mandarin + en",
    },
    "Shakira": {
        "url": "https://music.apple.com/us/artist/shakira/889327",
        "title": "Apple Music Shakira catalogue profile",
        "claims": [("es", None), ("en", None)],
        "summary": (
            "The catalogue documents Shakira's Spanish-language career and sustained English "
            "crossover albums and singles. Both languages are prominent in the local history."
        ),
    },
    "Sandy Lam": {
        "url": "https://sandylam.com/history.htm",
        "title": "Sandy Lam official career history",
        "claims": [("zh", "cantonese"), ("zh", "mandarin")],
        "summary": (
            "The official history documents major Cantonese and Mandarin album periods. Minor "
            "Japanese and English projects do not displace the two sustained Chinese vocal "
            "repertoires used by the project classification."
        ),
    },
    "LISA": {
        "url": "https://open.spotify.com/track/7uQZVznj0uQOGC9KhV2Mg6",
        "title": "Official Spotify recording: LALISA",
        "claims": [("ko", None), ("en", None)],
        "summary": (
            "LALISA contains artist vocals in Korean and English, while the subsequent solo "
            "album and local high-play recordings establish a sustained English repertoire. "
            "The classification uses LISA's solo catalogue and does not borrow group metadata."
        ),
    },
    "Ryuichi Sakamoto": {
        "url": "https://www.commmons.com/archive/alp/artists/sakamotoryuichi/index_eng.html",
        "title": "commmons official Ryuichi Sakamoto artist profile",
        "claims": [],
        "summary": (
            "The official profile identifies Sakamoto primarily as a composer and musician "
            "with extensive score work. The entire local play snapshot is the instrumental "
            "Piano Trio version of Merry Christmas Mr. Lawrence."
        ),
        "instrumental": True,
    },
    "TWICE": {
        "url": "https://www.twicejapan.com/discography/",
        "title": "TWICE official Japanese discography",
        "claims": [("ko", None), ("ja", None), ("en", None)],
        "summary": (
            "JYP's Korean and Japanese discographies document sustained Korean and Japanese "
            "catalogues, while formal English singles and versions are also recurring releases. "
            "English is added to the original candidate before approval."
        ),
        "raw_language": "ko + ja + en",
    },
    "Céline Dion": {
        "url": "https://www.celinedion.com/about/biography/",
        "title": "Céline Dion official biography",
        "claims": [("fr", None), ("en", None)],
        "summary": (
            "The official biography separately documents major francophone albums and the "
            "long-running English-language album catalogue. Both are sustained repertoires."
        ),
    },
}

TRACK_EVIDENCE = {
    "Fiona Sit": [
        ("蘇州河 - 慕容雪 - Mandarin Version", "zh", "mandarin"),
        ("奇洛李維斯回信", "zh", "cantonese"),
    ],
    "Wicked Movie Cast": [("No One Mourns the Wicked", "en", None)],
    "FIFTY FIFTY": [("Cupid - Twin Ver.", "en", None), ("Cupid", "ko", None)],
    "Terence Lam": [("第幾位前任", "zh", "cantonese")],
    "Crowd Lu": [
        (
            "刻在我心底的名字 (Your Name Engraved Herein) - 電影<刻在你心底的名字>主題曲",
            "zh",
            "mandarin",
        )
    ],
    "Jacky Cheung": [("她來聽我的演唱會", "zh", "mandarin")],
    "BLACKPINK": [("Pink Venom", "ko", None), ("Ice Cream (with Selena Gomez)", "en", None)],
    "Karen Mok": [("忽然之間", "zh", "mandarin")],
    "Shakira": [("Hips Don't Lie (feat. Wyclef Jean)", "en", None), ("Antologia", "es", None)],
    "Sandy Lam": [("至少還有你", "zh", "mandarin")],
    "LISA": [("Born Again (feat. Doja Cat & RAYE)", "en", None)],
    "Ryuichi Sakamoto": [("Merry Christmas Mr. Lawrence - Version for Piano Trio", None, None)],
    "TWICE": [("I CAN'T STOP ME", "ko", None), ("I CAN'T STOP ME (English Version)", "en", None)],
    "Céline Dion": [("It's All Coming Back to Me Now", "en", None)],
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


def _review_genres(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT q.review_id, q.artist_name, q.play_hours, q.suggested_source_id,
                  q.status AS review_status, s.status AS source_status
           FROM artist_genre_review_queue q
           JOIN artist_genre_sources s ON s.source_id=q.suggested_source_id
           WHERE q.artist_name IN ({})
           ORDER BY q.play_hours DESC""".format(",".join("?" for _ in GENRE_DECISIONS)),
        list(GENRE_DECISIONS),
    ).fetchall()
    if {row["artist_name"] for row in rows} != set(GENRE_DECISIONS):
        raise ValueError("genre audit cohort mismatch")

    results = []
    for row in rows:
        if row["review_status"] == "approved" and row["source_status"] == "approved":
            results.append({"artist_name": row["artist_name"], "already_resolved": True})
            continue
        if row["review_status"] != "open" or row["source_status"] != "suggested":
            raise ValueError(f"unexpected Genre state for {row['artist_name']}")
        decision = GENRE_DECISIONS[row["artist_name"]]
        genres = decision["genres"]
        conn.execute(
            """UPDATE artist_genre_sources
               SET raw_genres_json=?, normalized_genres_json=?, primary_genre=?,
                   confidence=?, evidence_url=?, evidence_summary=?, updated_at=datetime('now')
               WHERE source_id=? AND status='suggested'""",
            (
                json.dumps(genres, ensure_ascii=False),
                json.dumps(genres, ensure_ascii=False),
                genres[0],
                decision["confidence"],
                decision["evidence_url"],
                decision["evidence_summary"],
                row["suggested_source_id"],
            ),
        )
        conn.commit()
        resolution_note = (
            "Codex evidence audit approved the artist-level style fallback: "
            f"{', '.join(genres)}. Spotify supplies only C-Pop market/scene labels for this "
            "artist, so the approved local source fills the missing style axis without "
            "overwriting Spotify. Same-axis multi-style values remain evenly allocated and "
            "must be interpreted with the existing artist-level/era caveat."
        )
        result = review_suggestion(
            conn,
            review_id=int(row["review_id"]),
            decision="approve",
            resolution_note=resolution_note,
            reviewed_by=REVIEWER,
        )
        results.append(
            {
                "artist_name": row["artist_name"],
                "play_hours": float(row["play_hours"]),
                "genres": genres,
                **result,
            }
        )
    return results


def _track_row(conn: sqlite3.Connection, artist_id: int, track_name: str) -> sqlite3.Row:
    row = conn.execute(
        """SELECT track_id, track_name, spotify_track_id
           FROM tracks WHERE artist_id=? AND track_name=?""",
        (artist_id, track_name),
    ).fetchone()
    if row is None or not row["spotify_track_id"]:
        raise ValueError(f"missing local Spotify track: artist={artist_id} track={track_name}")
    return row


def _language_payload(
    conn: sqlite3.Connection,
    review: dict[str, Any],
) -> dict[str, Any]:
    source = review["source"]
    if source is None:
        raise ValueError(f"review {review['review_id']} has no suggested source")
    artist_name = review["artist_name"]
    support = LANGUAGE_SUPPORT[artist_name]
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
    if support.get("instrumental"):
        evidence.append(
            {
                "claimed_language_code": None,
                "claimed_language_variant": None,
                "evidence_kind": "artist_profile",
                "performer_attribution": "artist_instrumental_confirmed",
                "evidence_url": support["url"],
                "evidence_title": support["title"],
                "evidence_summary": support["summary"],
            }
        )
    else:
        for code, variant in support["claims"]:
            evidence.append(
                {
                    "claimed_language_code": code,
                    "claimed_language_variant": variant,
                    "evidence_kind": "editorial_source",
                    "performer_attribution": "artist_vocal_confirmed",
                    "evidence_url": support["url"],
                    "evidence_title": support["title"],
                    "evidence_summary": support["summary"],
                }
            )

    for track_name, code, variant in TRACK_EVIDENCE.get(artist_name, []):
        track = _track_row(conn, int(review["artist_id"]), track_name)
        instrumental = source["classification"] == "instrumental"
        evidence.append(
            {
                "local_track_id": int(track["track_id"]),
                "claimed_language_code": code,
                "claimed_language_variant": variant,
                "evidence_kind": "track_credit" if instrumental else "track_language",
                "performer_attribution": (
                    "artist_instrumental_confirmed" if instrumental else "track_language_only"
                ),
                "evidence_url": f"https://open.spotify.com/track/{track['spotify_track_id']}",
                "evidence_title": f"Audited representative recording: {track_name}",
                "evidence_summary": (
                    "The local Spotify recording was checked during the second-pass audit and "
                    "supports the stated performer attribution and language classification."
                ),
            }
        )

    return {
        "classification": source["classification"],
        "primary_language_code": source["primary_language_code"],
        "language_variant": source["language_variant"],
        "raw_language": support.get("raw_language", source["raw_language"]),
        "origin": source["origin"],
        "source_key": source["source_key"],
        "evidence": evidence,
    }


def _language_resolution_note(artist_name: str, classification: str) -> str:
    support = LANGUAGE_SUPPORT[artist_name]
    claims = [f"{code}:{variant}" if variant else code for code, variant in support["claims"]]
    rendered_claims = ", ".join(claims) if claims else "instrumental"
    return (
        "Codex second-pass evidence audit approved this artist fact after checking the stable "
        f"artist identity, reliable catalogue/profile evidence, and representative recordings. "
        f"Classification={classification}; supported repertoire={rendered_claims}. "
        "The conclusion describes sustained vocal repertoire, not nationality or spoken language."
    )


def _review_languages(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT q.review_id, q.artist_id, q.play_hours_snapshot, a.artist_name,
                  q.status AS review_status, s.status AS source_status, s.classification
           FROM artist_language_review_queue q
           JOIN artists a ON a.artist_id=q.artist_id
           JOIN artist_language_sources s ON s.source_id=q.suggested_source_id
           WHERE q.reason=? AND q.pre_review_recommendation='manual_review'
           ORDER BY q.play_hours_snapshot DESC""",
        (LANGUAGE_BATCH_REASON,),
    ).fetchall()
    if {row["artist_name"] for row in rows} != set(LANGUAGE_DECISIONS):
        raise ValueError("Language audit cohort mismatch")

    results = []
    for row in rows:
        artist_name = str(row["artist_name"])
        action = LANGUAGE_DECISIONS[artist_name]
        expected_terminal = "approved" if action == "approve" else "insufficient_evidence"
        if row["review_status"] == expected_terminal:
            results.append({"artist_name": artist_name, "already_resolved": True})
            continue
        if row["review_status"] != "open" or row["source_status"] != "suggested":
            raise ValueError(f"unexpected Language state for {artist_name}")

        if action == "approve":
            review = get_review(conn, int(row["review_id"]))
            save_review_source(
                conn,
                review_id=int(row["review_id"]),
                payload=_language_payload(conn, review),
            )
            note = _language_resolution_note(artist_name, str(row["classification"]))
        else:
            note = (
                "Codex evidence audit did not approve the English-only candidate. Rema's "
                "representative repertoire consistently uses Nigerian Pidgin alongside English, "
                "while the current registry has no pcm code. Downcasting the catalogue to en "
                "would create false precision; the item is closed as insufficient evidence until "
                "the language taxonomy explicitly supports Nigerian Pidgin."
            )
        result = decide_review(
            conn,
            review_id=int(row["review_id"]),
            action=action,
            resolution_note=note,
            reviewed_by=REVIEWER,
        )
        results.append(
            {
                "artist_name": artist_name,
                "play_hours_snapshot": float(row["play_hours_snapshot"]),
                "action": action,
                **result,
            }
        )
    return results


def review_batch(conn: sqlite3.Connection) -> dict[str, Any]:
    genre = _review_genres(conn)
    language = _review_languages(conn)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ValueError(f"database integrity check failed: {integrity}")
    remaining_genre = conn.execute(
        "SELECT COUNT(*) FROM artist_genre_review_queue WHERE status='open'"
    ).fetchone()[0]
    remaining_language = conn.execute(
        "SELECT COUNT(*) FROM artist_language_review_queue WHERE status='open'"
    ).fetchone()[0]
    return {
        "reviewer": REVIEWER,
        "genre": genre,
        "language": language,
        "genre_approved_count": sum(not item.get("already_resolved") for item in genre),
        "language_approved_count": sum(item.get("action") == "approve" for item in language),
        "language_insufficient_count": sum(
            item.get("action") == "insufficient_evidence" for item in language
        ),
        "remaining_open_genre_reviews": int(remaining_genre),
        "remaining_open_language_reviews": int(remaining_language),
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
            "/tmp/spotify_stats_before_high_impact_metadata_audit_"
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
            report = review_batch(conn)
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

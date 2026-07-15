#!/usr/bin/env python3
"""Import the 2026-07-15 genre/style and language pre-review batch."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db
from backend.domains.metadata.artist_genres import upsert_genre_source
from backend.domains.metadata.artist_language_review import (
    get_or_create_review,
    save_review_source,
)

BATCH_KEY = "codex-pre-review:2026-07-15"

GENRE_ROWS = (
    (
        "Michael Wong",
        435.2,
        ["pop"],
        "https://music.apple.com/us/artist/michael-wong/152368592",
        0.90,
        "Apple Music describes authentic pop melodies and ballad-led arrangements.",
    ),
    (
        "Stefanie Sun",
        184.4,
        ["pop"],
        "https://en.wikipedia.org/wiki/Stefanie_Sun",
        0.86,
        "The artist profile identifies pop as a core style; alternative influence remains too broad to add a second canonical style.",
    ),
    (
        "A-Mei Chang",
        70.5,
        ["pop", "rock"],
        "https://www.moc.gov.tw/en/News_Content2.aspx?n=489&s=17832",
        0.90,
        "Taiwan Ministry of Culture describes A-Mei as a pop diva and her Amit persona as an experimental rock-and-roll artist.",
    ),
    (
        "Fish Leong",
        51.6,
        ["pop"],
        "https://music.apple.com/us/artist/fish-leong/531134701",
        0.88,
        "Apple Music describes her repertoire as Chinese and Malaysian pop ballad music.",
    ),
    (
        "JJ Lin",
        40.1,
        ["pop", "r&b"],
        "https://www.allmusic.com/artist/jj-lin-mn0002327509",
        0.90,
        "AllMusic describes JJ Lin as an R&B- and hip-hop-influenced Mandopop singer-songwriter; pop and R&B are the conservative style labels.",
    ),
    (
        "G.E.M.",
        35.3,
        ["pop", "dance pop", "r&b"],
        "https://en.wikipedia.org/wiki/G.E.M.",
        0.87,
        "The artist profile lists pop, dance-pop, and R&B as repertoire genres.",
    ),
)

# artist_id, name, hours, classification, [(code, variant)], recommendation,
# confidence, note. Claims describe common vocal repertoire, not nationality.
LANGUAGE_ROWS = (
    (
        577,
        "Fiona Sit",
        2.671489,
        "multilingual",
        (("zh", "cantonese"), ("zh", "mandarin")),
        "manual_review",
        0.82,
        "粤语与国语作品并存，建议在最终批准前各抽查一首主唱作品。",
    ),
    (
        559,
        "Gary Chaw",
        2.665046,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.86,
        "公开主流作品以国语演唱为主。",
    ),
    (
        169,
        "Hugh Jackman",
        2.615948,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.90,
        "当前目录中的音乐剧与电影原声主唱作品以英语为主。",
    ),
    (
        9,
        "Ezra Williams",
        2.572486,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.88,
        "公开发行的创作歌手作品以英语演唱。",
    ),
    (
        40,
        "Sam Smith",
        2.572334,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.92,
        "公开主流作品以英语演唱。",
    ),
    (
        118,
        "Keala Settle",
        2.503790,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.90,
        "当前目录中的音乐剧与电影原声主唱作品以英语为主。",
    ),
    (
        217,
        "Ben Platt",
        2.493461,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.90,
        "音乐剧与个人公开作品以英语演唱。",
    ),
    (
        719,
        "Nirvana",
        2.477543,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.93,
        "公开乐队作品以英语演唱。",
    ),
    (
        29,
        "Kate Bush",
        2.452194,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.93,
        "公开主流作品以英语演唱。",
    ),
    (
        780,
        "Cheer Chen",
        2.328618,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.89,
        "公开主流作品以国语演唱。",
    ),
    (
        125,
        "Caroline Polachek",
        2.259822,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.91,
        "公开主流作品以英语演唱。",
    ),
    (
        769,
        "Silence Wang",
        2.139659,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.90,
        "公开主流作品以国语演唱。",
    ),
    (
        273,
        "Luke Combs",
        2.129697,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.93,
        "公开主流作品以英语演唱。",
    ),
    (
        643,
        "Wicked Movie Cast",
        2.101132,
        "single_language",
        (("en", None),),
        "manual_review",
        0.82,
        "当前实体是电影剧组集合而非稳定艺人，语言候选为英语但建议核对归属边界。",
    ),
    (
        539,
        "那英",
        2.035039,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.91,
        "公开主流作品以国语演唱。",
    ),
    (
        79,
        "Thomas Rhett",
        2.011148,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.93,
        "公开主流作品以英语演唱。",
    ),
    (
        252,
        "Alexandra Shipp",
        1.991160,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.88,
        "当前音乐目录中的电影原声主唱作品以英语为主。",
    ),
    (
        741,
        "Billy Joel",
        1.961281,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.94,
        "公开主流作品以英语演唱。",
    ),
    (
        250,
        "FIFTY FIFTY",
        1.950330,
        "multilingual",
        (("ko", None), ("en", None)),
        "manual_review",
        0.87,
        "韩语与英语版本/作品并存，建议核对本地播放对应版本。",
    ),
    (
        673,
        "Terence Lam",
        1.917971,
        "single_language",
        (("zh", "cantonese"),),
        "manual_review",
        0.84,
        "主流目录以粤语为主，但存在跨市场发行，建议抽查国语作品比例。",
    ),
    (
        373,
        "Yisa Yu",
        1.853555,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.90,
        "公开主流作品以国语演唱。",
    ),
    (
        69,
        "Crowd Lu",
        1.827173,
        "multilingual",
        (("zh", "mandarin"), ("zh", "minnan")),
        "manual_review",
        0.83,
        "国语与台语作品并存，需确认当前本地目录是否足以采用多语分类。",
    ),
    (
        13,
        "Orla Gartland",
        1.788623,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.91,
        "公开主流作品以英语演唱。",
    ),
    (
        254,
        "Jacky Cheung",
        1.788158,
        "multilingual",
        (("zh", "cantonese"), ("zh", "mandarin")),
        "manual_review",
        0.93,
        "粤语与国语代表作均较多，应保留多语分类。",
    ),
    (
        573,
        "Earth, Wind & Fire",
        1.779295,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.93,
        "公开主流作品以英语演唱。",
    ),
    (
        64,
        "BLACKPINK",
        1.732699,
        "multilingual",
        (("ko", None), ("en", None)),
        "manual_review",
        0.93,
        "韩语与英语歌词/版本长期并存，应保留多语分类。",
    ),
    (
        195,
        "James Taylor",
        1.728556,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.94,
        "公开主流作品以英语演唱。",
    ),
    (
        756,
        "Niccolò Fabi",
        1.716278,
        "single_language",
        (("it", None),),
        "recommend_approve",
        0.91,
        "公开主流作品以意大利语演唱。",
    ),
    (
        648,
        "Jonathan Bailey",
        1.610109,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.88,
        "当前目录中的音乐剧主唱作品以英语为主。",
    ),
    (
        46,
        "Ms. Lauryn Hill",
        1.521808,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.93,
        "公开主流作品以英语演唱。",
    ),
    (
        7750,
        "Li Jian",
        1.497758,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.91,
        "公开主流作品以国语演唱。",
    ),
    (
        261,
        "The National",
        1.470352,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.93,
        "公开乐队作品以英语演唱。",
    ),
    (
        71,
        "NANON",
        1.420136,
        "single_language",
        (("th", None),),
        "recommend_approve",
        0.86,
        "公开主流歌曲以泰语演唱；英语内容比例较低。",
    ),
    (
        102,
        "Julie Andrews",
        1.386288,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.94,
        "音乐剧与电影原声代表作以英语演唱。",
    ),
    (
        790,
        "Sebastian Croft",
        1.332897,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.86,
        "当前音乐目录中的主唱作品以英语为主。",
    ),
    (
        148,
        "Clairo",
        1.295061,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.92,
        "公开主流作品以英语演唱。",
    ),
    (
        136,
        "Bob Dylan",
        1.265426,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.95,
        "公开主流作品以英语演唱。",
    ),
    (
        387,
        "Karen Mok",
        1.245851,
        "multilingual",
        (("zh", "cantonese"), ("zh", "mandarin")),
        "manual_review",
        0.91,
        "粤语与国语代表作并存，应保留多语分类。",
    ),
    (
        57,
        "Shakira",
        1.243233,
        "multilingual",
        (("es", None), ("en", None)),
        "manual_review",
        0.95,
        "西班牙语与英语录音目录均显著，应保留多语分类。",
    ),
    (
        695,
        "卓文萱",
        1.235600,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.89,
        "公开主流作品以国语演唱。",
    ),
    (
        762,
        "Laura Dreyfuss",
        1.217772,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.88,
        "当前音乐剧与个人目录中的主唱作品以英语为主。",
    ),
    (
        84,
        "Rema",
        1.211256,
        "single_language",
        (("en", None),),
        "manual_review",
        0.72,
        "英语与 Nigerian Pidgin 存在连续谱；当前 registry 未单列 pcm，批准前需确认统计口径。",
    ),
    (
        546,
        "郭顶",
        1.208065,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.90,
        "公开主流作品以国语演唱。",
    ),
    (
        132,
        "Sandy Lam",
        1.199264,
        "multilingual",
        (("zh", "cantonese"), ("zh", "mandarin")),
        "manual_review",
        0.94,
        "粤语与国语录音目录均显著，应保留多语分类。",
    ),
    (
        798,
        "鄭興",
        1.186133,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.88,
        "公开专辑与金曲奖资料显示其主要为国语创作与演唱。",
    ),
    (
        793,
        "Jude Chiu",
        1.144137,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.87,
        "裘德的公开个人作品以国语演唱。",
    ),
    (
        891,
        "Radiohead",
        1.125360,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.94,
        "公开乐队作品以英语演唱。",
    ),
    (
        684,
        "LISA",
        1.121710,
        "multilingual",
        (("ko", None), ("en", None)),
        "manual_review",
        0.90,
        "团体与个人目录包含韩语及英语作品，泰语访谈能力不作为演唱语种证据。",
    ),
    (
        525,
        "光良品冠",
        1.077502,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.88,
        "组合公开主流作品以国语演唱。",
    ),
    (
        845,
        "万能青年旅店",
        1.073783,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.91,
        "公开乐队作品以国语演唱。",
    ),
    (
        692,
        "Norah Jones",
        1.068010,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.93,
        "公开主流作品以英语演唱。",
    ),
    (
        47,
        "Carrie Underwood",
        1.056946,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.94,
        "公开主流作品以英语演唱。",
    ),
    (
        347,
        "Gene Kelly",
        1.051366,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.94,
        "电影歌舞与录音代表作以英语演唱。",
    ),
    (
        777,
        "Ryuichi Sakamoto",
        1.030630,
        "instrumental",
        (),
        "manual_review",
        0.80,
        "个人目录以器乐创作和配乐为主，但存在合作人声曲目，建议核对本地播放曲目。",
    ),
    (
        150,
        "sodagreen",
        1.020549,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.91,
        "公开主流作品以国语演唱。",
    ),
    (
        104,
        "Idina Menzel",
        1.019772,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.94,
        "音乐剧与个人代表作以英语演唱。",
    ),
    (
        736,
        "Janet Jackson",
        0.989515,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.94,
        "公开主流作品以英语演唱。",
    ),
    (
        116,
        "TWICE",
        0.948414,
        "multilingual",
        (("ko", None), ("ja", None)),
        "manual_review",
        0.93,
        "韩语与日语正式录音目录均显著，英语作品也存在。",
    ),
    (
        225,
        "Bonnie Raitt",
        0.942344,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.94,
        "公开主流作品以英语演唱。",
    ),
    (
        786,
        "Ethel Cain",
        0.940260,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.91,
        "公开主流作品以英语演唱。",
    ),
    (
        565,
        "The Beatles",
        0.914074,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.95,
        "绝大多数公开主流作品以英语演唱；少量例外不改变常用语种。",
    ),
    (
        781,
        "Zhao Lei",
        0.908178,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.91,
        "公开主流作品以国语演唱。",
    ),
    (
        738,
        "A-Lin",
        0.899536,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.91,
        "公开主流作品以国语演唱。",
    ),
    (
        359,
        "Dolly Parton",
        0.887223,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.95,
        "公开主流作品以英语演唱。",
    ),
    (
        771,
        "831",
        0.862390,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.89,
        "公开乐队主流作品以国语演唱。",
    ),
    (
        127,
        "陳粒",
        0.860381,
        "single_language",
        (("zh", "mandarin"),),
        "recommend_approve",
        0.90,
        "公开主流作品以国语演唱。",
    ),
    (
        234,
        "PinkPantheress",
        0.857350,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.92,
        "公开主流作品以英语演唱。",
    ),
    (
        682,
        "Céline Dion",
        0.838772,
        "multilingual",
        (("fr", None), ("en", None)),
        "manual_review",
        0.96,
        "法语与英语录音目录均显著，应保留多语分类。",
    ),
    (
        544,
        "Robyn",
        0.835951,
        "single_language",
        (("en", None),),
        "recommend_approve",
        0.91,
        "国际公开主流作品以英语演唱。",
    ),
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args(argv)


def _spotify_evidence_url(conn: sqlite3.Connection, artist_name: str) -> str:
    row = conn.execute(
        """SELECT spotify_artist_id FROM spotify_artist_meta
           WHERE artist_name=? AND spotify_artist_id IS NOT NULL LIMIT 1""",
        (artist_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Spotify artist id missing for {artist_name}")
    return f"https://open.spotify.com/artist/{row[0]}"


def _language_evidence(
    url: str,
    artist_name: str,
    classification: str,
    claims: tuple[tuple[str, str | None], ...],
) -> list[dict[str, Any]]:
    if classification == "instrumental":
        return [
            {
                "claimed_language_code": None,
                "claimed_language_variant": None,
                "evidence_kind": "artist_repertoire",
                "performer_attribution": "artist_instrumental_confirmed",
                "evidence_url": url,
                "evidence_title": f"Spotify official artist repertoire: {artist_name}",
                "evidence_summary": "The published artist repertoire is predominantly instrumental; local tracks still require final spot-checking.",
            }
        ]
    return [
        {
            "claimed_language_code": code,
            "claimed_language_variant": variant,
            "evidence_kind": "artist_repertoire",
            "performer_attribution": "artist_vocal_confirmed",
            "evidence_url": url,
            "evidence_title": f"Spotify official artist repertoire: {artist_name}",
            "evidence_summary": f"The published repertoire contains artist vocals in {code}{f' ({variant})' if variant else ''}; final approval should spot-check representative tracks.",
        }
        for code, variant in claims
    ]


def import_batch(conn: sqlite3.Connection, *, dry_run: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "batch_key": BATCH_KEY,
        "dry_run": dry_run,
        "genre": {"loaded": len(GENRE_ROWS), "created": 0, "updated": 0},
        "language": {"loaded": len(LANGUAGE_ROWS), "created": 0, "updated": 0},
        "recommendations": {},
    }
    conn.execute("BEGIN IMMEDIATE")
    try:
        for artist_name, hours, genres, evidence_url, confidence, summary in GENRE_ROWS:
            upsert_genre_source(
                conn,
                artist_name=artist_name,
                spotify_artist_id=None,
                source="external_consensus",
                source_key=BATCH_KEY,
                raw_genres=genres,
                normalized_genres=genres,
                primary_genre=genres[0],
                language=None,
                region=None,
                confidence=confidence,
                evidence_url=evidence_url,
                evidence_summary=summary,
                status="suggested",
            )
            source_id = int(
                conn.execute(
                    """SELECT source_id FROM artist_genre_sources
                   WHERE artist_name=? AND source='external_consensus' AND source_key=?""",
                    (artist_name, BATCH_KEY),
                ).fetchone()[0]
            )
            existing = conn.execute(
                "SELECT review_id FROM artist_genre_review_queue WHERE suggested_source_id=?",
                (source_id,),
            ).fetchone()
            if existing is None:
                cursor = conn.execute(
                    """INSERT INTO artist_genre_review_queue(
                           artist_name, play_hours, reason, suggested_source_id, status
                       ) VALUES (?, ?, 'style_axis_gap_codex_first_pass', ?, 'open')""",
                    (artist_name, hours, source_id),
                )
                review_id = int(cursor.lastrowid)
                report["genre"]["created"] += 1
            else:
                review_id = int(existing[0])
                report["genre"]["updated"] += 1
            conn.execute(
                """UPDATE artist_genre_review_queue
                   SET play_hours=?, status='open', pre_review_recommendation='manual_review',
                       pre_review_confidence=?, pre_review_note=?,
                       pre_reviewed_by='codex_first_pass', pre_reviewed_at=datetime('now'),
                       updated_at=datetime('now') WHERE review_id=?""",
                (
                    hours,
                    confidence,
                    "证据支持候选 Style，但该艺人对 Style 分布影响较大；建议用户在 Settings 复核后再批准。",
                    review_id,
                ),
            )

        for (
            artist_id,
            artist_name,
            hours,
            classification,
            claims,
            recommendation,
            confidence,
            note,
        ) in LANGUAGE_ROWS:
            db_artist = conn.execute(
                "SELECT artist_name FROM artists WHERE artist_id=?", (artist_id,)
            ).fetchone()
            if db_artist is None or str(db_artist[0]) != artist_name:
                raise ValueError(f"artist identity mismatch: {artist_id} {artist_name}")
            review = get_or_create_review(
                conn,
                artist_id=artist_id,
                play_hours_snapshot=hours,
                reason="codex_language_pre_review_2026_07_15",
            )
            review_id = int(review["review_id"])
            url = _spotify_evidence_url(conn, artist_name)
            payload = {
                "classification": classification,
                "primary_language_code": claims[0][0]
                if classification == "single_language"
                else None,
                "language_variant": claims[0][1] if classification == "single_language" else None,
                "raw_language": " + ".join(
                    f"{code}:{variant}" if variant else code for code, variant in claims
                )
                or "instrumental",
                "origin": "curated_seed",
                "source_key": f"{BATCH_KEY}:{artist_id}",
                "evidence": _language_evidence(url, artist_name, classification, claims),
            }
            existed = review.get("suggested_source_id") is not None
            save_review_source(conn, review_id=review_id, payload=payload)
            conn.execute(
                """UPDATE artist_language_review_queue
                   SET play_hours_snapshot=?, pre_review_recommendation=?,
                       pre_review_confidence=?, pre_review_note=?,
                       pre_reviewed_by='codex_first_pass',
                       pre_reviewed_at=datetime('now'), updated_at=datetime('now')
                   WHERE review_id=? AND status='open'""",
                (hours, recommendation, confidence, note, review_id),
            )
            report["language"]["updated" if existed else "created"] += 1
            recommendations = report["recommendations"]
            recommendations[recommendation] = recommendations.get(recommendation, 0) + 1

        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    conn = get_db(readonly=False)
    try:
        report = import_batch(conn, dry_run=args.dry_run)
    finally:
        conn.close()
    if args.json_output:
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

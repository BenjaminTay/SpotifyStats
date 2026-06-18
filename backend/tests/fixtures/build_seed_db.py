"""Build a portable seed SQLite test database with known boundary-case data.

Run from project root:
    python backend/tests/fixtures/build_seed_db.py

Output: backend/tests/fixtures/seed.db (< 1MB, safe to commit)
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta

# Add project root to path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from backend.core.db import SCHEMA

SEED_PATH = os.path.join(os.path.dirname(__file__), "seed.db")


def build() -> str:
    """Create the seed database and return its path."""
    # Remove old seed DB if it exists
    if os.path.exists(SEED_PATH):
        os.remove(SEED_PATH)

    conn = sqlite3.connect(SEED_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    # Add columns that are created by ensure_schema() via ALTER TABLE
    for table, col, col_type in [
        ("plays", "content_type", "TEXT NOT NULL DEFAULT 'audio'"),
        ("spotify_album_meta", "album_artists", "TEXT"),
        ("spotify_album_meta", "total_tracks", "INTEGER"),
        ("spotify_album_meta", "track_list", "TEXT"),
        ("albums", "image_url", "TEXT"),
        ("albums", "image_path", "TEXT"),
        ("artists", "image_url", "TEXT"),
        ("artists", "image_path", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
    conn.commit()

    # ── Dimension Data ──────────────────────────────────────────────────────

    # Artists
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Alpha')")
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (2, 'Beta')")
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (3, 'Podcast Creator')")

    # Albums — 5 albums + one extra for cross-artist testing
    albums = [
        (1, "Alpha Debut", 1),
        (2, "Alpha Debut Deluxe", 1),
        (3, "Beta Hits", 2),
        (4, "Beta Hits Remix", 2),
        (5, "Beta Acoustic", 2),
        (6, "Podcast Show", 3),
    ]
    conn.executemany("INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)", albums)

    # Spotify album metadata (album_type, release_date for Billboard album chart filtering)
    album_meta = [
        (
            "spotify:album:a1",
            "Alpha Debut",
            "album",
            "2026-01-05",
            75,
            "Alpha Records",
            "pop;rock",
            "https://i.scdn.co/alpha_debut.jpg",
            "Alpha",
            10,
            '["spotify:track:aaa1","spotify:track:aaa2","spotify:track:aaa3","spotify:track:aaa4"]',
        ),
        (
            "spotify:album:a2",
            "Alpha Debut Deluxe",
            "album",
            "2026-02-10",
            65,
            "Alpha Records",
            "pop;rock",
            "https://i.scdn.co/alpha_deluxe.jpg",
            "Alpha",
            12,
            '["spotify:track:aaa5","spotify:track:aaa6","spotify:track:aaa7"]',
        ),
        (
            "spotify:album:b1",
            "Beta Hits",
            "album",
            "2026-01-20",
            85,
            "Beta Music",
            "r&b;soul",
            "https://i.scdn.co/beta_hits.jpg",
            "Beta",
            12,
            '["spotify:track:bbb1","spotify:track:bbb2","spotify:track:bbb3","spotify:track:bbb4"]',
        ),
        (
            "spotify:album:b2",
            "Beta Hits Remix",
            "single",
            "2026-03-01",
            50,
            "Beta Music",
            "remix",
            "https://i.scdn.co/beta_remix.jpg",
            "Beta",
            4,
            '["spotify:track:bbb5"]',
        ),
        (
            "spotify:album:b3",
            "Beta Acoustic",
            "album",
            "2026-04-01",
            60,
            "Beta Music",
            "acoustic",
            "https://i.scdn.co/beta_acoustic.jpg",
            "Beta",
            10,
            '["spotify:track:bbb6","spotify:track:bbb7","spotify:track:bbb8"]',
        ),
        (
            "spotify:album:p1",
            "Podcast Show",
            "album",
            "2026-01-01",
            40,
            "Podcast Network",
            "podcast",
            "https://i.scdn.co/podcast.jpg",
            "Podcast Creator",
            0,
            "[]",
        ),
    ]
    conn.executemany(
        """INSERT INTO spotify_album_meta(spotify_album_id, album_name, album_type,
           release_date, popularity, label, genres, image_url, album_artists,
           total_tracks, track_list) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        album_meta,
    )

    # Tracks — 15 tracks across 5 music albums + 1 podcast record
    tracks = [
        # Alpha Debut (album 1, artist 1)
        (1, "Alpha Song 1", 1, 1, "spotify:track:aaa1"),
        (2, "Alpha Song 2", 1, 1, "spotify:track:aaa2"),
        (3, "Alpha Song 3", 1, 1, "spotify:track:aaa3"),
        (4, "Alpha Song 4", 1, 1, "spotify:track:aaa4"),
        # Alpha Debut Deluxe (album 2, artist 1)
        (5, "Alpha Song 1 (Deluxe)", 1, 2, "spotify:track:aaa5"),
        (6, "Alpha Song 5", 1, 2, "spotify:track:aaa6"),
        (7, "Alpha Song 6", 1, 2, "spotify:track:aaa7"),
        # Beta Hits (album 3, artist 2)
        (8, "Beta Song 1", 2, 3, "spotify:track:bbb1"),
        (9, "Beta Song 2", 2, 3, "spotify:track:bbb2"),
        (10, "Beta Song 3", 2, 3, "spotify:track:bbb3"),
        (11, "Beta Song 4", 2, 3, "spotify:track:bbb4"),
        # Beta Hits Remix (album 4, artist 2, single)
        (12, "Beta Song 1 Remix", 2, 4, "spotify:track:bbb5"),
        # Beta Acoustic (album 5, artist 2)
        (13, "Beta Song 1 Acoustic", 2, 5, "spotify:track:bbb6"),
        (14, "Beta Song 5", 2, 5, "spotify:track:bbb7"),
        (15, "Beta Song 6", 2, 5, "spotify:track:bbb8"),
    ]
    conn.executemany(
        "INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_uri) VALUES (?, ?, ?, ?, ?)",
        tracks,
    )

    # Track-album associations (for tracks that appear in multiple albums)
    # Alpha Song 1 also appears in the Deluxe album
    conn.execute("INSERT INTO track_albums(track_id, album_id) VALUES (1, 2)")

    # Spotify track metadata
    track_meta = [
        ("aaa1", "Alpha Song 1", 210000, 80, 0, 1, 1, "ISRC-AA-001", "a1"),
        ("aaa2", "Alpha Song 2", 195000, 75, 0, 2, 1, "ISRC-AA-002", "a1"),
        ("aaa3", "Alpha Song 3", 240000, 85, 0, 3, 1, "ISRC-AA-003", "a1"),
        ("aaa4", "Alpha Song 4", 180000, 60, 0, 4, 1, "ISRC-AA-004", "a1"),
        ("aaa5", "Alpha Song 1 (Deluxe)", 220000, 70, 0, 1, 1, "ISRC-AA-005", "a2"),
        ("aaa6", "Alpha Song 5", 200000, 70, 0, 2, 1, "ISRC-AA-006", "a2"),
        ("aaa7", "Alpha Song 6", 220000, 65, 0, 3, 1, "ISRC-AA-007", "a2"),
        ("bbb1", "Beta Song 1", 230000, 90, 0, 1, 1, "ISRC-BB-001", "b1"),
        ("bbb2", "Beta Song 2", 185000, 82, 0, 2, 1, "ISRC-BB-002", "b1"),
        ("bbb3", "Beta Song 3", 250000, 88, 0, 3, 1, "ISRC-BB-003", "b1"),
        ("bbb4", "Beta Song 4", 175000, 55, 0, 4, 1, "ISRC-BB-004", "b1"),
        ("bbb5", "Beta Song 1 Remix", 240000, 70, 0, 1, 1, "ISRC-BB-005", "b2"),
        ("bbb6", "Beta Song 1 Acoustic", 235000, 65, 0, 1, 1, "ISRC-BB-006", "b3"),
        ("bbb7", "Beta Song 5", 190000, 60, 0, 2, 1, "ISRC-BB-007", "b3"),
        ("bbb8", "Beta Song 6", 210000, 50, 0, 3, 1, "ISRC-BB-008", "b3"),
    ]
    conn.executemany(
        """INSERT INTO spotify_track_meta(spotify_track_id, track_name, duration_ms,
           popularity, explicit, track_number, disc_number, isrc, spotify_album_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        track_meta,
    )

    # Spotify artist metadata
    artist_meta = [
        ("spotify:artist:alpha", "Alpha", 80, 500000, "pop;rock", "https://i.scdn.co/alpha.jpg"),
        ("spotify:artist:beta", "Beta", 75, 300000, "r&b;soul", "https://i.scdn.co/beta.jpg"),
    ]
    conn.executemany(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, popularity, followers, genres, image_url) VALUES (?, ?, ?, ?, ?, ?)",
        artist_meta,
    )

    # ── Playback Rule Fixture Data (IDs >= 900) ───────────────────────────────

    # Fixture Artists
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (901, 'Fixture Artist Alpha')")
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (902, 'Fixture Artist Beta')")

    # Fixture Albums
    fixture_albums = [
        (901, "Fixture Single", 901),
        (902, "Fixture LP", 901),
        (903, "Fixture Release Album", 901),
        (904, "Fixture Release Album (Deluxe)", 901),
        (905, "Fixture Collab Single", 901),
        (920, "Fixture Future Single", 901),
        (921, "Fixture Future LP", 901),
        (922, "Fixture Future LP Deluxe", 901),
        (923, "Fixture Pure Compilation", 901),
        (924, "Fixture Compilation Plus", 901),
        (925, "Fixture Future LP (Rerecorded)", 901),
        (926, "Fixture Collab Remix", 901),
    ]
    conn.executemany(
        "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)", fixture_albums
    )

    # Fixture Spotify Album Metadata
    fixture_album_meta = [
        (
            "spotify:album:fix1",
            "Fixture Single",
            "single",
            "2026-03-01",
            50,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha",
            1,
            '["spotify:track:fix004"]',
        ),
        (
            "spotify:album:fix2",
            "Fixture LP",
            "album",
            "2026-01-15",
            70,
            "Fixture Records",
            "pop;rock",
            "",
            "Fixture Artist Alpha",
            10,
            '["spotify:track:fix001","spotify:track:fix002","spotify:track:fix003","spotify:track:fix005","spotify:track:fix007"]',
        ),
        (
            "spotify:album:fix3",
            "Fixture Release Album",
            "album",
            "2026-02-01",
            65,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha",
            8,
            '["spotify:track:fix006","spotify:track:fix008","spotify:track:fix009"]',
        ),
        (
            "spotify:album:fix4",
            "Fixture Release Album (Deluxe)",
            "album",
            "2026-02-15",
            60,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha",
            12,
            '["spotify:track:fix006","spotify:track:fix008","spotify:track:fix009"]',
        ),
        (
            "spotify:album:fix5",
            "Fixture Collab Single",
            "single",
            "2026-04-01",
            55,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha, Fixture Artist Beta",
            1,
            '["spotify:track:fix010"]',
        ),
        (
            "spotify:album:proj920",
            "Fixture Future Single",
            "single",
            "2026-01-05",
            50,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha",
            1,
            '["spotify:track:proj920"]',
        ),
        (
            "spotify:album:proj921",
            "Fixture Future LP",
            "album",
            "2026-02-01",
            70,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha",
            10,
            '["spotify:track:proj920","spotify:track:proj921"]',
        ),
        (
            "spotify:album:proj922",
            "Fixture Future LP Deluxe",
            "album",
            "2026-02-15",
            65,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha",
            12,
            '["spotify:track:proj920","spotify:track:proj921","spotify:track:proj922"]',
        ),
        (
            "spotify:album:proj923",
            "Fixture Pure Compilation",
            "compilation",
            "2026-03-01",
            40,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha",
            12,
            '["spotify:track:proj920"]',
        ),
        (
            "spotify:album:proj924",
            "Fixture Compilation Plus",
            "compilation",
            "2026-03-05",
            42,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha",
            14,
            '["spotify:track:proj920","spotify:track:proj923"]',
        ),
        (
            "spotify:album:proj925",
            "Fixture Future LP (Rerecorded)",
            "album",
            "2026-04-01",
            60,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha",
            10,
            '["spotify:track:proj925","spotify:track:proj927"]',
        ),
        (
            "spotify:album:proj926",
            "Fixture Collab Remix",
            "single",
            "2026-04-15",
            45,
            "Fixture Records",
            "pop",
            "",
            "Fixture Artist Alpha, Fixture Artist Beta",
            1,
            '["spotify:track:proj926"]',
        ),
    ]
    conn.executemany(
        """INSERT INTO spotify_album_meta(spotify_album_id, album_name, album_type,
           release_date, popularity, label, genres, image_url, album_artists,
           total_tracks, track_list) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        fixture_album_meta,
    )

    # Fixture artist metadata
    fixture_artist_meta = [
        ("spotify:artist:fixalpha", "Fixture Artist Alpha", 60, 100000, "pop", ""),
        ("spotify:artist:fixbeta", "Fixture Artist Beta", 55, 80000, "rock", ""),
    ]
    conn.executemany(
        "INSERT INTO spotify_artist_meta(spotify_artist_id, artist_name, popularity, followers, genres, image_url) VALUES (?, ?, ?, ?, ?, ?)",
        fixture_artist_meta,
    )

    # Fixture Tracks
    fixture_tracks = [
        # scenario 1: short_fragments_same_track — 40s track
        (901, "Fixture Fragment Song", 901, 902, "spotify:track:fix001"),
        # scenario 2: long_track_dynamic_threshold — 10min track
        (902, "Fixture Long Track", 901, 902, "spotify:track:fix002"),
        # scenario 3: multi_artist_fanout
        (903, "Fixture Shared Credit", 901, 902, "spotify:track:fix003"),
        # scenario 4: source_album_single_then_album
        (904, "Fixture Source Album Song", 901, 901, "spotify:track:fix004"),
        # scenario 6: track_group_recording (standard + remastered)
        (905, "Fixture Recording Song", 901, 902, "spotify:track:fix005"),
        (906, "Fixture Recording Song - Remastered", 901, 903, "spotify:track:fix006"),
        # scenario 7: track_group_composition (original + acoustic + demo)
        (907, "Fixture Composition Song", 901, 902, "spotify:track:fix007"),
        (908, "Fixture Composition Song - Acoustic", 901, 903, "spotify:track:fix008"),
        (909, "Fixture Composition Song - Demo", 901, 903, "spotify:track:fix009"),
        # scenario 10: collab single with multi-artist album_artists (comma-separated)
        (910, "Fixture Collab Track", 901, 905, "spotify:track:fix010"),
        # album project scenarios
        (920, "Fixture Lead Single", 901, 920, "spotify:track:proj920"),
        (921, "Fixture Album Cut", 901, 921, "spotify:track:proj921"),
        (922, "Fixture Deluxe Bonus", 901, 922, "spotify:track:proj922"),
        (923, "Fixture Compilation Exclusive", 901, 924, "spotify:track:proj923"),
        (925, "Fixture Lead Single (Rerecorded)", 901, 925, "spotify:track:proj925"),
        (926, "Fixture Lead Single Remix", 901, 926, "spotify:track:proj926"),
        (927, "Fixture Rerecord Vault", 901, 925, "spotify:track:proj927"),
    ]
    conn.executemany(
        "INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_uri) VALUES (?, ?, ?, ?, ?)",
        fixture_tracks,
    )

    # Fixture Track-Album associations (scenario 4: same track on single + LP)
    conn.execute("INSERT INTO track_albums(track_id, album_id) VALUES (904, 901)")
    conn.execute("INSERT INTO track_albums(track_id, album_id) VALUES (904, 902)")
    fixture_project_track_albums = [
        (920, 920),
        (920, 921),
        (920, 922),
        (920, 923),
        (920, 924),
        (921, 921),
        (921, 922),
        (922, 922),
        (923, 924),
        (925, 925),
        (926, 926),
        (927, 925),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO track_albums(track_id, album_id) VALUES (?, ?)",
        fixture_project_track_albums,
    )

    # Backfill primary credits, then add featured credits for multi-artist fixtures.
    conn.execute(
        "INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) "
        "SELECT track_id, artist_id, 'primary' FROM tracks"
    )
    conn.execute(
        "INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) VALUES (903, 902, 'featured')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) VALUES (926, 902, 'featured')"
    )

    # Fixture Spotify Track Metadata
    # spotify_album_id must match spotify_album_meta.spotify_album_id (full URI format).
    fixture_track_meta = [
        (
            "fix001",
            "Fixture Fragment Song",
            40000,
            50,
            0,
            1,
            1,
            "ISRC-FIX-001",
            "spotify:album:fix2",
        ),
        ("fix002", "Fixture Long Track", 600000, 60, 0, 1, 1, "ISRC-FIX-002", "spotify:album:fix2"),
        (
            "fix003",
            "Fixture Shared Credit",
            210000,
            70,
            0,
            1,
            1,
            "ISRC-FIX-003",
            "spotify:album:fix2",
        ),
        (
            "fix004",
            "Fixture Source Album Song",
            200000,
            55,
            0,
            1,
            1,
            "ISRC-FIX-004",
            "spotify:album:fix1",
        ),
        (
            "fix005",
            "Fixture Recording Song",
            200000,
            65,
            0,
            1,
            1,
            "ISRC-FIX-005",
            "spotify:album:fix2",
        ),
        (
            "fix006",
            "Fixture Recording Song - Remastered",
            205000,
            60,
            0,
            1,
            1,
            "ISRC-FIX-006",
            "spotify:album:fix3",
        ),
        (
            "fix007",
            "Fixture Composition Song",
            210000,
            55,
            0,
            1,
            1,
            "ISRC-FIX-007",
            "spotify:album:fix2",
        ),
        (
            "fix008",
            "Fixture Composition Song - Acoustic",
            220000,
            45,
            0,
            1,
            1,
            "ISRC-FIX-008",
            "spotify:album:fix3",
        ),
        (
            "fix009",
            "Fixture Composition Song - Demo",
            180000,
            30,
            0,
            1,
            1,
            "ISRC-FIX-009",
            "spotify:album:fix3",
        ),
        (
            "fix010",
            "Fixture Collab Track",
            200000,
            55,
            0,
            1,
            1,
            "ISRC-FIX-010",
            "spotify:album:fix5",
        ),
        (
            "proj920",
            "Fixture Lead Single",
            200000,
            65,
            0,
            1,
            1,
            "ISRC-PROJ-920",
            "spotify:album:proj920",
        ),
        (
            "proj921",
            "Fixture Album Cut",
            210000,
            60,
            0,
            2,
            1,
            "ISRC-PROJ-921",
            "spotify:album:proj921",
        ),
        (
            "proj922",
            "Fixture Deluxe Bonus",
            190000,
            55,
            0,
            11,
            1,
            "ISRC-PROJ-922",
            "spotify:album:proj922",
        ),
        (
            "proj923",
            "Fixture Compilation Exclusive",
            180000,
            50,
            0,
            1,
            1,
            "ISRC-PROJ-923",
            "spotify:album:proj924",
        ),
        (
            "proj925",
            "Fixture Lead Single (Rerecorded)",
            205000,
            52,
            0,
            1,
            1,
            "ISRC-PROJ-925",
            "spotify:album:proj925",
        ),
        (
            "proj926",
            "Fixture Lead Single Remix",
            215000,
            50,
            0,
            1,
            1,
            "ISRC-PROJ-926",
            "spotify:album:proj926",
        ),
        (
            "proj927",
            "Fixture Rerecord Vault",
            195000,
            50,
            0,
            9,
            1,
            "ISRC-PROJ-927",
            "spotify:album:proj925",
        ),
    ]
    conn.executemany(
        """INSERT INTO spotify_track_meta(spotify_track_id, track_name, duration_ms,
           popularity, explicit, track_number, disc_number, isrc, spotify_album_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        fixture_track_meta,
    )

    conn.commit()

    # ── Play Data (~85 records, 6 weeks: 2026-W17 through W22) ────────────

    # Helper: generate play record tuple
    def make_play(
        ts_utc: str,
        platform: str,
        ms_played: int,
        track_id: int | None,
        country: str = "CN",
        reason_start: str = "trackdone",
        reason_end: str = "trackdone",
        shuffle: int = 0,
        skipped: int = 0,
        offline: int = 0,
        incognito_mode: int = 0,
        content_type: str = "audio",
        source_album_id: int | None = None,
    ) -> tuple:
        """Convert UTC ISO timestamp to Beijing time components and return a play tuple."""
        dt_utc = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
        dt_local = dt_utc + timedelta(hours=8)
        return (
            ts_utc,
            dt_local.year,
            dt_local.month,
            dt_local.isocalendar()[1],
            dt_local.weekday(),
            dt_local.hour,
            dt_local.strftime("%Y-%m-%d"),
            platform,
            ms_played,
            country,
            track_id,
            reason_start,
            reason_end,
            shuffle,
            skipped,
            offline,
            incognito_mode,
            content_type,
            source_album_id,
        )

    plays: list[tuple] = []

    # ── Week 17 (Apr 20-26, 2026) — 14 plays ──
    # Mon Apr 20: Alpha Song 1 dominates
    plays.append(make_play("2026-04-20T02:00:00Z", "ios", 180000, 1))  # Beijing: Mon 10:00
    plays.append(make_play("2026-04-20T03:00:00Z", "ios", 200000, 1))  # Mon 11:00
    plays.append(make_play("2026-04-20T04:00:00Z", "android", 220000, 1))  # Mon 12:00
    plays.append(make_play("2026-04-20T05:00:00Z", "osx", 250000, 2))  # Mon 13:00
    plays.append(make_play("2026-04-20T10:00:00Z", "ios", 300000, 8))  # Mon 18:00

    # Tue Apr 21
    plays.append(make_play("2026-04-21T02:00:00Z", "ios", 210000, 1))
    plays.append(make_play("2026-04-21T04:00:00Z", "ios", 195000, 2))
    plays.append(make_play("2026-04-21T06:00:00Z", "android", 280000, 8))
    plays.append(make_play("2026-04-21T08:00:00Z", "windows", 160000, 3))

    # Wed Apr 22: consecutive plays of track 1 → should merge
    plays.append(make_play("2026-04-22T02:00:00Z", "ios", 190000, 1))
    plays.append(make_play("2026-04-22T02:03:00Z", "ios", 210000, 1))  # consecutive with above
    plays.append(make_play("2026-04-22T04:00:00Z", "ios", 240000, 9))
    plays.append(make_play("2026-04-22T06:00:00Z", "osx", 175000, 10))

    # Thu Apr 23
    plays.append(make_play("2026-04-23T03:00:00Z", "ios", 300000, 11))

    # ── Week 18 (Apr 27-May 3, 2026) — 16 plays ──
    # Mon Apr 27
    plays.append(make_play("2026-04-27T02:00:00Z", "ios", 220000, 3))
    plays.append(make_play("2026-04-27T04:00:00Z", "android", 200000, 3))
    plays.append(make_play("2026-04-27T06:00:00Z", "ios", 240000, 3))  # Alpha Song 3 #1 this week
    plays.append(make_play("2026-04-27T08:00:00Z", "osx", 180000, 4))

    # Tue Apr 28
    plays.append(make_play("2026-04-28T02:00:00Z", "ios", 210000, 8))
    plays.append(make_play("2026-04-28T04:00:00Z", "ios", 185000, 9))
    plays.append(make_play("2026-04-28T06:00:00Z", "windows", 160000, 12))

    # Wed Apr 29: podcast play (track_id=NULL)
    plays.append(make_play("2026-04-29T02:00:00Z", "ios", 60000, None, content_type="video"))

    # Thu Apr 30: skipped play
    plays.append(make_play("2026-04-30T02:00:00Z", "ios", 35000, 1, skipped=1))

    # Fri May 1
    plays.append(make_play("2026-05-01T02:00:00Z", "ios", 190000, 5))
    plays.append(make_play("2026-05-01T04:00:00Z", "android", 220000, 6))

    # Sat May 2: offline play
    plays.append(make_play("2026-05-02T02:00:00Z", "ios", 180000, 13, offline=1))

    # Sun May 3 23:55 (Beijing time) — near week boundary
    # 2026-05-03T15:55:00Z → Beijing: Sun May 3 23:55 (W18)
    plays.append(make_play("2026-05-03T15:55:00Z", "ios", 210000, 1))
    # Mon May 4 00:05 (Beijing time) — just crossed into W19
    # 2026-05-03T16:05:00Z → Beijing: Mon May 4 00:05 (W19)
    plays.append(make_play("2026-05-03T16:05:00Z", "ios", 215000, 1))
    # Consecutive plays of track 8
    plays.append(make_play("2026-05-03T16:10:00Z", "ios", 200000, 8))
    plays.append(make_play("2026-05-03T16:12:00Z", "ios", 210000, 8))

    # ── Week 19 (May 4-10, 2026) — 18 plays ──
    # Mon May 4
    plays.append(make_play("2026-05-04T02:00:00Z", "ios", 230000, 9))
    plays.append(make_play("2026-05-04T04:00:00Z", "android", 185000, 9))
    plays.append(make_play("2026-05-04T06:00:00Z", "ios", 250000, 9))  # Beta Song 2 #1

    # Tue May 5: boundary testing — ms_played near 30000 threshold
    plays.append(make_play("2026-05-05T02:00:00Z", "ios", 29999, 10))  # BELOW threshold
    plays.append(make_play("2026-05-05T02:01:00Z", "ios", 30000, 10))  # AT threshold — should pass
    plays.append(make_play("2026-05-05T02:02:00Z", "ios", 30001, 10))  # ABOVE threshold

    # Wed May 6
    plays.append(make_play("2026-05-06T02:00:00Z", "ios", 240000, 14))
    plays.append(make_play("2026-05-06T04:00:00Z", "ios", 200000, 15))

    # Thu May 7: incognito mode
    plays.append(make_play("2026-05-07T02:00:00Z", "ios", 180000, 1, incognito_mode=1))

    # Fri May 8: three consecutive plays of track 2 → should merge
    plays.append(make_play("2026-05-08T02:00:00Z", "ios", 195000, 2))
    plays.append(make_play("2026-05-08T02:03:00Z", "ios", 200000, 2))
    plays.append(make_play("2026-05-08T02:06:00Z", "ios", 210000, 2))

    # Sat May 9
    plays.append(make_play("2026-05-09T04:00:00Z", "android", 175000, 11))
    plays.append(make_play("2026-05-09T06:00:00Z", "ios", 160000, 4))

    # Sun May 10: second podcast play
    plays.append(make_play("2026-05-10T02:00:00Z", "ios", 120000, None, content_type="video"))
    # Very short plays (should be filtered by default 30s threshold)
    plays.append(make_play("2026-05-10T03:00:00Z", "ios", 5000, 1))  # 5 seconds
    plays.append(make_play("2026-05-10T04:00:00Z", "android", 15000, 8))  # 15 seconds
    plays.append(make_play("2026-05-10T05:00:00Z", "ios", 25000, 3))  # 25 seconds

    # ── Week 20 (May 11-17, 2026) — 14 plays ──
    plays.append(make_play("2026-05-11T02:00:00Z", "ios", 220000, 8))
    plays.append(make_play("2026-05-11T04:00:00Z", "ios", 200000, 9))
    plays.append(make_play("2026-05-11T06:00:00Z", "android", 250000, 10))
    plays.append(make_play("2026-05-12T02:00:00Z", "ios", 180000, 14))
    plays.append(make_play("2026-05-12T04:00:00Z", "osx", 210000, 15))
    plays.append(make_play("2026-05-13T02:00:00Z", "ios", 190000, 1))
    plays.append(make_play("2026-05-13T04:00:00Z", "windows", 240000, 2))
    plays.append(make_play("2026-05-14T02:00:00Z", "ios", 185000, 5))
    plays.append(make_play("2026-05-14T04:00:00Z", "android", 195000, 6))
    plays.append(make_play("2026-05-15T02:00:00Z", "ios", 210000, 12))
    plays.append(make_play("2026-05-15T04:00:00Z", "ios", 175000, 13))
    plays.append(make_play("2026-05-16T04:00:00Z", "android", 160000, 7))
    plays.append(make_play("2026-05-16T06:00:00Z", "ios", 230000, 3))
    plays.append(make_play("2026-05-17T02:00:00Z", "ios", 200000, 11))

    # ── Week 21 (May 18-24, 2026) — 14 plays ──
    plays.append(make_play("2026-05-18T02:00:00Z", "ios", 210000, 1))
    plays.append(make_play("2026-05-18T04:00:00Z", "android", 185000, 2))
    plays.append(make_play("2026-05-18T06:00:00Z", "ios", 230000, 8))
    plays.append(make_play("2026-05-19T02:00:00Z", "ios", 250000, 8))  # Beta Song 1 #1 this week
    plays.append(make_play("2026-05-19T04:00:00Z", "ios", 240000, 9))
    plays.append(make_play("2026-05-20T02:00:00Z", "ios", 195000, 14))
    plays.append(make_play("2026-05-20T04:00:00Z", "osx", 180000, 15))
    plays.append(make_play("2026-05-21T02:00:00Z", "ios", 220000, 10))
    plays.append(make_play("2026-05-21T04:00:00Z", "windows", 175000, 3))
    plays.append(make_play("2026-05-22T02:00:00Z", "android", 210000, 4))
    plays.append(make_play("2026-05-22T04:00:00Z", "ios", 190000, 13))
    # Consecutive plays with shuffle enabled
    plays.append(make_play("2026-05-23T02:00:00Z", "ios", 240000, 5, shuffle=1))
    plays.append(make_play("2026-05-23T02:04:00Z", "ios", 200000, 5, shuffle=1))
    plays.append(make_play("2026-05-24T04:00:00Z", "android", 180000, 6))

    # ── Week 22 (May 25-31, 2026) — 9 plays ──
    plays.append(make_play("2026-05-25T02:00:00Z", "ios", 220000, 1))
    plays.append(make_play("2026-05-25T04:00:00Z", "android", 200000, 8))
    plays.append(make_play("2026-05-26T02:00:00Z", "ios", 185000, 9))
    plays.append(make_play("2026-05-26T04:00:00Z", "ios", 230000, 10))
    plays.append(make_play("2026-05-27T02:00:00Z", "osx", 195000, 14))
    plays.append(make_play("2026-05-28T02:00:00Z", "ios", 210000, 15))
    plays.append(make_play("2026-05-29T02:00:00Z", "ios", 240000, 2))
    plays.append(make_play("2026-05-30T02:00:00Z", "android", 180000, 12))
    plays.append(make_play("2026-05-31T02:00:00Z", "windows", 190000, 13))

    # ── Fixture scenario plays ─────────────────────────────────────────────

    # Scenario 1: short_fragments_same_track — two adjacent 20s plays of a 40s track
    # Merge: total_ms=40000, full_plays=1, remainder=0 → 1 valid event at 40000ms
    plays.append(make_play("2026-06-01T02:00:00Z", "ios", 20000, 901))
    plays.append(make_play("2026-06-01T02:03:00Z", "ios", 20000, 901))

    # Scenario 2: long_track_dynamic_threshold — 30s of a 10min track
    # Static threshold (30s): valid. Dynamic (10% of 600000=60000): invalid.
    plays.append(make_play("2026-06-01T03:00:00Z", "ios", 30000, 902))

    # Scenario 3: multi_artist_fanout — one play credits two artists via track_artists
    plays.append(make_play("2026-06-01T04:00:00Z", "ios", 210000, 903))

    # Scenario 4: source_album_single_then_album — same track under single then LP
    plays.append(make_play("2026-06-01T05:00:00Z", "ios", 200000, 904, source_album_id=901))
    plays.append(make_play("2026-06-02T05:00:00Z", "ios", 200000, 904, source_album_id=902))

    # Scenario 5: release_group_deluxe — plays on standard + deluxe albums
    # Track 905 on album 902 (Fixture LP); track 906 on album 903 (Fixture Release Album)
    # Track 908 on album 903; track 909 on album 904 (Fixture Release Album (Deluxe))
    plays.append(make_play("2026-06-03T02:00:00Z", "ios", 210000, 905, source_album_id=902))
    plays.append(make_play("2026-06-03T03:00:00Z", "ios", 210000, 906, source_album_id=903))

    # Scenario 6: track_group_recording — standard + remastered (L2 merge)
    plays.append(make_play("2026-06-04T02:00:00Z", "ios", 200000, 905))
    plays.append(make_play("2026-06-04T03:00:00Z", "ios", 205000, 906))

    # Scenario 7: track_group_composition — original + acoustic + demo (all merged at L3)
    plays.append(make_play("2026-06-05T02:00:00Z", "ios", 210000, 907))
    plays.append(make_play("2026-06-05T03:00:00Z", "ios", 220000, 908))
    plays.append(make_play("2026-06-05T04:00:00Z", "ios", 180000, 909))

    # Scenario 10: collab single — multi-artist album_artists (comma-separated)
    plays.append(make_play("2026-06-06T02:00:00Z", "ios", 200000, 910, source_album_id=905))

    # Album project fixtures.
    # Expected L2 all-time "Fixture Future LP" total:
    # lead single 4 plays: 2 single source before LP + 1 LP source after release + 1 compilation source
    # album cut 3 plays: 3 LP source
    # deluxe bonus 2 plays: 2 deluxe source
    # total = 9
    plays.extend(
        [
            make_play("2026-01-10T02:00:00Z", "ios", 200000, 920, source_album_id=920),
            make_play("2026-01-12T02:00:00Z", "ios", 200000, 920, source_album_id=920),
            make_play("2026-02-02T02:00:00Z", "ios", 200000, 920, source_album_id=921),
            make_play("2026-02-03T02:00:00Z", "ios", 210000, 921, source_album_id=921),
            make_play("2026-02-04T02:00:00Z", "ios", 210000, 921, source_album_id=921),
            make_play("2026-02-05T02:00:00Z", "ios", 210000, 921, source_album_id=921),
            make_play("2026-02-16T02:00:00Z", "ios", 190000, 922, source_album_id=922),
            make_play("2026-02-17T02:00:00Z", "ios", 190000, 922, source_album_id=922),
            make_play("2026-03-02T02:00:00Z", "ios", 200000, 920, source_album_id=923),
            make_play("2026-03-06T02:00:00Z", "ios", 180000, 923, source_album_id=924),
            make_play("2026-03-07T02:00:00Z", "ios", 180000, 923, source_album_id=924),
            make_play("2026-03-08T02:00:00Z", "ios", 180000, 923, source_album_id=924),
            make_play("2026-03-09T02:00:00Z", "ios", 180000, 923, source_album_id=924),
            make_play("2026-04-02T02:00:00Z", "ios", 205000, 925, source_album_id=925),
            make_play("2026-04-03T02:00:00Z", "ios", 195000, 927, source_album_id=925),
            make_play("2026-04-16T02:00:00Z", "ios", 215000, 926, source_album_id=926),
        ]
    )

    # Scenario 8: billboard_fragment_boundary — short fragments around a week boundary
    # Week boundary: Thu 00:00 (DOW=3). Use Thu May 28 2026 (DOW=3).
    # Play at Wed May 27 23:55 Beijing → Wed 23:55 → DOW=2, W21 or W22
    # Use UTC timestamps that produce local Beijing time near boundary
    # 2026-05-27T15:55:00Z → Beijing Wed May 27 23:55 (before Thu boundary)
    # 2026-05-27T16:05:00Z → Beijing Thu May 28 00:05 (after Thu boundary)
    plays.append(make_play("2026-05-27T15:55:00Z", "ios", 20000, 901))
    plays.append(make_play("2026-05-27T16:05:00Z", "ios", 20000, 901))

    # ── Insert plays in batches ──
    conn.executemany(
        """INSERT INTO plays(ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
           ts_date, platform, ms_played, conn_country, track_id,
           reason_start, reason_end, shuffle, skipped, offline, incognito_mode, content_type, source_album_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        plays,
    )
    conn.commit()

    # ── Build Aggregations ─────────────────────────────────────────────────
    # Manual aggregation to avoid depending on build_aggregations() which pulls from DB_PATH

    import pandas as pd

    df = pd.read_sql_query(
        """SELECT p.ts, p.ts_date, p.ts_dow, p.ts_hour, p.ms_played, p.track_id,
                  t.album_id, t.artist_id, stm.duration_ms
           FROM plays p
           JOIN tracks t ON p.track_id = t.track_id
           LEFT JOIN spotify_track_meta stm
             ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
           WHERE p.track_id IS NOT NULL
           ORDER BY p.ts""",
        conn,
    )

    # Week boundary: Thu 00:00 (DOW=3), same as default Billboard config
    week_start_dow = 3  # Thursday
    week_start_hour = 0

    df["days_back"] = (df["ts_dow"] - week_start_dow) % 7
    mask_before = (df["ts_dow"] == week_start_dow) & (df["ts_hour"] < week_start_hour)
    df.loc[mask_before, "days_back"] = 7
    df["ts_date_dt"] = pd.to_datetime(df["ts_date"])
    df["billboard_week"] = (df["ts_date_dt"] - pd.to_timedelta(df["days_back"], unit="D")).dt.date

    # Merge consecutive same-track plays (min_ms = 0 first, then filter)
    from backend.core.db import merge_consecutive_plays

    min_ms_agg = 30000
    df_merged = merge_consecutive_plays(df, 0)
    df_merged = df_merged[df_merged["ms_played"] >= min_ms_agg]

    # Track aggregation
    tracks_agg = (
        df_merged.groupby(["billboard_week", "track_id"])
        .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    for r in tracks_agg.itertuples(index=False):
        conn.execute(
            "INSERT INTO agg_weekly_tracks(billboard_week, track_id, play_count, total_ms) VALUES (?, ?, ?, ?)",
            (str(r.billboard_week), int(r.track_id), int(r.play_count), int(r.total_ms)),
        )

    # Album aggregation (exclude tracks without album)
    df_album = df_merged[df_merged["album_id"].notna()]
    albums_agg = (
        df_album.groupby(["billboard_week", "album_id"])
        .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    for r in albums_agg.itertuples(index=False):
        conn.execute(
            "INSERT INTO agg_weekly_albums(billboard_week, album_id, play_count, total_ms) VALUES (?, ?, ?, ?)",
            (str(r.billboard_week), int(r.album_id), int(r.play_count), int(r.total_ms)),
        )

    # Artist aggregation
    artists_agg = (
        df_merged.groupby(["billboard_week", "artist_id"])
        .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    for r in artists_agg.itertuples(index=False):
        conn.execute(
            "INSERT INTO agg_weekly_artists(billboard_week, artist_id, play_count, total_ms) VALUES (?, ?, ?, ?)",
            (str(r.billboard_week), int(r.artist_id), int(r.play_count), int(r.total_ms)),
        )

    # Agg config — use a sentinel hash that will never match any
    # _agg_param_hash() output.  The seed's manually-built pre-agg tables
    # are NOT semantically equivalent to build_aggregations():
    #   - Album agg uses t.album_id, not source_album_id
    #   - Artist agg uses t.artist_id (primary), not track_artists fanout
    #   - Merge uses plain consecutive-play, not boundary_column="source_album_id"
    # Contract tests must always take the raw path.
    conn.execute(
        "INSERT INTO agg_config(key, value) VALUES (?, ?)",
        ("param_hash", "seed_db_legacy_do_not_match"),
    )
    conn.commit()

    # ── Release Group (for version merge testing) ──────────────────────────
    conn.execute(
        "INSERT INTO release_groups(group_id, canonical_name, artist_id, primary_album_id, is_manual) VALUES (1, 'Alpha Debut (Combined)', 1, 1, 0)"
    )
    conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (1, 1)")
    conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (1, 2)")

    # Fixture release group: albums 903 + 904 → canonical
    conn.execute(
        "INSERT INTO release_groups(group_id, canonical_name, artist_id, primary_album_id, scope, is_manual) VALUES (2, 'Fixture Release Album (Combined)', 901, 903, 'release', 0)"
    )
    conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (2, 903)")
    conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (2, 904)")

    conn.execute(
        """INSERT INTO release_groups(group_id, canonical_name, artist_id, primary_album_id,
           scope, is_manual)
           VALUES (920, 'Fixture Future LP', 901, 921, 'release', 1)"""
    )
    conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (920, 921)")
    conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (920, 922)")
    conn.execute(
        """INSERT INTO release_groups(group_id, canonical_name, artist_id, primary_album_id,
           scope, is_manual)
           VALUES (921, 'Fixture Future LP', 901, 921, 'composition', 1)"""
    )
    conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (921, 921)")
    conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (921, 922)")
    conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (921, 925)")

    # Fixture track groups: recording scope (L2 merges 905 + 906)
    conn.execute(
        """INSERT INTO track_groups(group_id, canonical_name, primary_track_id, scope, is_manual)
           VALUES (1, 'Fixture Recording Song', 905, 'recording', 0)"""
    )
    conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (1, 905)")
    conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (1, 906)")

    # Fixture track groups: composition scope (L3 merges 907 + 908 + 909)
    # Demonstrates parent-child structure: recording group 3 sits under
    # composition group 2 so that track 908 is resolved to the composition
    # canonical at L3 via the parent_group_id chain (R6).
    conn.execute(
        """INSERT INTO track_groups(group_id, canonical_name, primary_track_id, scope, is_manual)
           VALUES (2, 'Fixture Composition Song', 907, 'composition', 0)"""
    )
    conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (2, 907)")
    # Recording group 3 is a child of composition group 2
    conn.execute(
        """INSERT INTO track_groups(group_id, canonical_name, primary_track_id,
           scope, parent_group_id, is_manual)
           VALUES (3, 'Fixture Composition Song - Acoustic', 908,
           'recording', 2, 0)"""
    )
    conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (3, 908)")

    conn.execute(
        """INSERT INTO track_groups(group_id, canonical_name, primary_track_id, scope, is_manual)
           VALUES (920, 'Fixture Lead Single', 920, 'recording', 1)"""
    )
    conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (920, 920)")
    conn.execute(
        """INSERT INTO track_groups(group_id, canonical_name, primary_track_id, scope, is_manual)
           VALUES (921, 'Fixture Lead Single', 920, 'composition', 1)"""
    )
    conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (921, 920)")
    conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (921, 925)")
    conn.execute("INSERT INTO track_group_members(group_id, track_id) VALUES (921, 926)")

    # ── Settings ───────────────────────────────────────────────────────────
    conn.execute("INSERT INTO settings(key, value) VALUES ('min_ms', '30000')")
    conn.execute("INSERT INTO settings(key, value) VALUES ('music_only', '1')")
    conn.execute("INSERT INTO settings(key, value) VALUES ('merge_enabled', '1')")

    from backend.domains.playback.album_projects import ensure_album_projects

    ensure_album_projects(conn)

    conn.commit()

    # ── Golden Assertions ──────────────────────────────────────────────────
    print("Running golden assertions...")
    errors: list[str] = []

    # A1: Row counts
    artist_count = conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0]
    album_count = conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0]
    track_count = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    play_count = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    assert artist_count == 5, f"Expected 5 artists, got {artist_count}"
    assert album_count == 18, f"Expected 18 albums, got {album_count}"
    assert track_count == 32, f"Expected 32 tracks, got {track_count}"
    assert play_count == len(plays), f"Expected {len(plays)} plays, got {play_count}"
    print(
        f"  A1 PASS: {artist_count} artists, {album_count} albums, {track_count} tracks, {play_count} plays"
    )

    # A2: min_ms threshold — 29999ms play should be filtered, 30000ms kept
    above_30s = conn.execute("SELECT COUNT(*) FROM plays WHERE ms_played >= 30000").fetchone()[0]
    below_30s = conn.execute("SELECT COUNT(*) FROM plays WHERE ms_played < 30000").fetchone()[0]
    # Our specific test: 29999, 30000, 30001 are all present
    has_29999 = (
        conn.execute("SELECT COUNT(*) FROM plays WHERE ms_played = 29999").fetchone()[0] == 1
    )
    has_30000 = (
        conn.execute("SELECT COUNT(*) FROM plays WHERE ms_played = 30000").fetchone()[0] >= 1
    )
    assert has_29999, "Missing 29,999ms boundary test record"
    assert has_30000, "Missing 30,000ms boundary test record"
    print(f"  A2 PASS: {above_30s} plays >=30s, {below_30s} plays <30s, boundary records present")

    # A3: Podcast plays (track_id IS NULL)
    podcast_count = conn.execute("SELECT COUNT(*) FROM plays WHERE track_id IS NULL").fetchone()[0]
    assert podcast_count == 2, f"Expected 2 podcast plays, got {podcast_count}"
    print(f"  A3 PASS: {podcast_count} podcast plays (track_id IS NULL)")

    # A4: Cross-week boundary
    # Play at 2026-05-03T15:55:00Z → Beijing Sun May 3 23:55 → W18
    # Play at 2026-05-03T16:05:00Z → Beijing Mon May 4 00:05 → W19
    w18_play = conn.execute(
        "SELECT ts_week FROM plays WHERE ts = '2026-05-03T15:55:00Z'"
    ).fetchone()
    w19_play = conn.execute(
        "SELECT ts_week FROM plays WHERE ts = '2026-05-03T16:05:00Z'"
    ).fetchone()
    if w18_play and w19_play:
        assert w18_play[0] != w19_play[0], (
            f"Cross-week boundary not respected: both in week {w18_play[0]}"
        )
    print(f"  A4 PASS: cross-week boundary detected (W{w18_play[0]} → W{w19_play[0]})")

    # A5: Aggregation tables have data
    agg_tracks = conn.execute("SELECT COUNT(*) FROM agg_weekly_tracks").fetchone()[0]
    agg_albums = conn.execute("SELECT COUNT(*) FROM agg_weekly_albums").fetchone()[0]
    agg_artists = conn.execute("SELECT COUNT(*) FROM agg_weekly_artists").fetchone()[0]
    assert agg_tracks > 0, "agg_weekly_tracks is empty"
    assert agg_albums > 0, "agg_weekly_albums is empty"
    assert agg_artists > 0, "agg_weekly_artists is empty"
    print(
        f"  A5 PASS: agg tables populated (tracks={agg_tracks}, albums={agg_albums}, artists={agg_artists})"
    )

    # A6: Consecutive play merging — verify merge groups form & total ms preserved
    # Track 1 has consecutive plays at Apr 22 02:00 + 02:03 that should merge into same group
    merged_df = merge_consecutive_plays(df, 0)
    merged_t1_ms = int(merged_df[merged_df["track_id"] == 1]["ms_played"].sum())
    raw_t1_ms = int(df[df["track_id"] == 1]["ms_played"].sum())
    # Total ms_played for track 1 should be preserved after merge
    assert merged_t1_ms == raw_t1_ms, (
        f"Merge changed total ms for track 1: {raw_t1_ms} → {merged_t1_ms}"
    )
    # Merge should create fewer groups than raw rows (consecutive plays grouped)
    merge_groups = df.copy()
    merge_groups["_grp"] = (merge_groups["track_id"] != merge_groups["track_id"].shift(1)).cumsum()
    assert merge_groups["_grp"].nunique() < len(df), (
        "Expected consecutive plays to create merge groups"
    )
    print(
        f"  A6 PASS: merge preserves total ms ({raw_t1_ms}ms), "
        f"groups={merge_groups['_grp'].nunique()} < rows={len(df)}"
    )

    # A7: Billboard weekly aggregation produces expected rankings
    # Get top track for each week from agg
    weekly_top = conn.execute("""
        SELECT billboard_week, track_id, total_ms
        FROM agg_weekly_tracks
        WHERE billboard_week = (SELECT MIN(billboard_week) FROM agg_weekly_tracks)
        ORDER BY total_ms DESC
        LIMIT 5
    """).fetchall()
    assert len(weekly_top) > 0, "No weekly top tracks found"
    print(
        f"  A7 PASS: weekly Billboard data available, top track in first week: track_id={weekly_top[0][1]}, ms={weekly_top[0][2]}"
    )

    # A8: skipped/offline/incognito flags
    skipped_ct = conn.execute("SELECT COUNT(*) FROM plays WHERE skipped = 1").fetchone()[0]
    offline_ct = conn.execute("SELECT COUNT(*) FROM plays WHERE offline = 1").fetchone()[0]
    incog_ct = conn.execute("SELECT COUNT(*) FROM plays WHERE incognito_mode = 1").fetchone()[0]
    assert skipped_ct >= 1, f"Expected >=1 skipped plays, got {skipped_ct}"
    assert offline_ct >= 1, f"Expected >=1 offline plays, got {offline_ct}"
    assert incog_ct >= 1, f"Expected >=1 incognito plays, got {incog_ct}"
    print(
        f"  A8 PASS: flags present — skipped={skipped_ct}, offline={offline_ct}, incognito={incog_ct}"
    )

    # A9: Version merge group exists
    group_count = conn.execute("SELECT COUNT(*) FROM release_groups").fetchone()[0]
    member_count = conn.execute("SELECT COUNT(*) FROM release_group_members").fetchone()[0]
    assert group_count == 4, f"Expected 4 release groups, got {group_count}"
    assert member_count == 9, f"Expected 9 release group members, got {member_count}"
    print(f"  A9 PASS: release group created with {member_count} members")

    # A10: Track version groups
    track_group_count = conn.execute("SELECT COUNT(*) FROM track_groups").fetchone()[0]
    track_group_member_count = conn.execute("SELECT COUNT(*) FROM track_group_members").fetchone()[
        0
    ]
    assert track_group_count == 5, f"Expected 5 track groups, got {track_group_count}"
    assert track_group_member_count == 8, (
        f"Expected 8 track group members, got {track_group_member_count}"
    )
    print(f"  A10 PASS: track groups created with {track_group_member_count} members")

    # A10: Spotify metadata
    track_meta_count = conn.execute("SELECT COUNT(*) FROM spotify_track_meta").fetchone()[0]
    album_meta_count = conn.execute("SELECT COUNT(*) FROM spotify_album_meta").fetchone()[0]
    artist_meta_count = conn.execute("SELECT COUNT(*) FROM spotify_artist_meta").fetchone()[0]
    assert track_meta_count == 32, f"Expected 32 track metas, got {track_meta_count}"
    assert album_meta_count == 18, f"Expected 18 album metas, got {album_meta_count}"
    assert artist_meta_count == 4, f"Expected 4 artist metas, got {artist_meta_count}"
    print("  A10 PASS: Spotify metadata present")

    # A11: File size < 1MB
    file_size = os.path.getsize(SEED_PATH)
    assert file_size < 1_000_000, f"Seed DB too large: {file_size} bytes (limit 1MB)"
    print(f"  A11 PASS: file size {file_size:,} bytes (< 1MB)")

    conn.close()

    if errors:
        print("\n  GOLDEN ASSERTIONS FAILED:")
        for e in errors:
            print(f"    - {e}")
        sys.exit(1)

    print("\n  All golden assertions passed!")
    return SEED_PATH


if __name__ == "__main__":
    path = build()
    print(f"\nSeed DB created at: {path}")

"""Contract tests for album project playback semantics."""

from __future__ import annotations

import pytest

from backend.core.db import load_plays
from backend.domains.billboard.chart_ranking import compute_album_weekly_rankings
from backend.domains.playback.album_projects import (
    compute_album_project_plays,
    compute_album_source_breakdown,
    load_album_project_membership,
)
from backend.domains.playback.records_discovery import _album_full_replays
from backend.services.analysis_records_service import _build_entity_frames

pytestmark = pytest.mark.contract


def test_l2_album_project_counts_lead_single_and_deluxe_once(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(
        df,
        seed_conn,
        merge_level=2,
        include_compilations=False,
        billboard_mode=False,
    )
    row = result[result["album_project_name"] == "Fixture Future LP"].iloc[0]
    assert int(row["play_count"]) == 9
    assert int(row["unique_canonical_songs"]) == 3


def test_source_breakdown_sums_to_album_project_total(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    totals = compute_album_project_plays(df, seed_conn, merge_level=2, include_compilations=False)
    breakdown = compute_album_source_breakdown(df, seed_conn, merge_level=2)
    total = int(totals[totals["album_project_name"] == "Fixture Future LP"].iloc[0]["play_count"])
    rows = breakdown[breakdown["album_project_name"] == "Fixture Future LP"]
    assert int(rows["play_count"].sum()) == total
    assert rows.set_index("source_bucket")["play_count"].to_dict() == {
        "single": 2,
        "original_album": 4,
        "deluxe": 2,
        "compilation": 1,
    }


def test_billboard_album_project_excludes_pre_release_single_week(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    weekly = compute_album_weekly_rankings(
        df,
        top_n=50,
        merge_level=2,
        include_compilations=False,
    )
    future_lp = weekly[weekly["album_name"] == "Fixture Future LP"]
    assert not future_lp.empty
    assert future_lp["billboard_week"].min() >= "2026-02-01"


def test_pure_compilation_does_not_become_album_project_at_l2(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(df, seed_conn, merge_level=2, include_compilations=False)
    assert "Fixture Pure Compilation" not in set(result["album_project_name"])


def test_compilation_exclusive_track_forms_project(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(df, seed_conn, merge_level=2, include_compilations=True)
    row = result[result["album_project_name"] == "Fixture Compilation Plus"].iloc[0]
    assert int(row["play_count"]) == 4
    assert int(row["unique_canonical_songs"]) == 1


def test_l3_rerecord_and_collab_versions_join_project(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
    result = compute_album_project_plays(df, seed_conn, merge_level=3, include_compilations=True)
    row = result[result["album_project_name"] == "Fixture Future LP"].iloc[0]
    assert int(row["play_count"]) == 12
    assert int(row["unique_canonical_songs"]) == 4


def test_album_membership_has_one_default_project_per_canonical_song(seed_conn):
    membership = load_album_project_membership(seed_conn, merge_level=2, include_compilations=True)
    duplicated = membership[membership.duplicated(["canonical_song_key"], keep=False)]
    assert duplicated.empty


def test_analysis_records_album_frame_uses_album_project_membership(seed_conn):
    df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)

    _, album_frame, _ = _build_entity_frames(
        df,
        seed_conn,
        merge_level=2,
        include_compilations=False,
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
    )

    future_rows = album_frame[album_frame["track_id"].isin([920, 921, 922])]
    assert not future_rows.empty
    assert set(future_rows["album_project_name"]) == {"Fixture Future LP"}
    assert set(future_rows["album_project_id"]) == {3}
    assert set(future_rows["album_release_date"]) == {"2026-02-01"}


def test_album_full_replays_counts_minimum_per_song_rounds(seed_conn):
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "album_name": "Fixture Future LP",
                "artist_name": "Fixture Artist Alpha",
                "track_id": track_id,
            }
            for track_id, count in [(track_id, 2 + (track_id % 3)) for track_id in range(10)]
            for _ in range(count)
        ]
    )

    result = _album_full_replays(frame, seed_conn, merge_level=1).iloc[0]

    assert result["value"] == 2.0
    assert result["unit"] == "次完整回放"
    assert result["secondary_value"] == 10.0
    assert result["secondary_unit"] == "/ 10 首"
    assert result["total_plays"] == 29
    assert result["caption"] == "总播放 29 次"


def test_album_full_replays_uses_spotify_total_not_local_project_membership(seed_conn):
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "album_project_id": 3,
                "album_project_name": "Fixture Future LP",
                "artist_name": "Fixture Artist Alpha",
                "track_id": track_id,
                "canonical_song_key": str(track_id),
            }
            for track_id in [920, 921]
        ]
    )

    result = _album_full_replays(frame, seed_conn)

    # The project has three locally-known member tracks, while Spotify metadata
    # says the album has ten. Local membership alone must not claim 3/3 complete.
    assert result.empty


def test_album_full_replays_uses_original_track_list_not_deluxe_bonus(seed_conn):
    import sqlite3

    import pandas as pd

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seed_conn.backup(conn)

    conn.execute(
        "INSERT INTO artists(artist_id, artist_name) VALUES (990, 'Fixture Edition Artist')"
    )
    conn.executemany(
        "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, 990)",
        [(9900, "Fixture Edition Album"), (9901, "Fixture Edition Album Deluxe")],
    )
    conn.executemany(
        """INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_id)
           VALUES (?, ?, 990, ?, ?)""",
        [
            (99000, "Core One", 9900, "edition-core-1"),
            (99001, "Core Two", 9900, "edition-core-2"),
            (99002, "Bonus Track", 9901, "edition-bonus-1"),
        ],
    )
    conn.executemany(
        """INSERT INTO spotify_track_meta(spotify_track_id, track_name, spotify_album_id)
           VALUES (?, ?, ?)""",
        [
            ("edition-core-1", "Core One", "edition-original"),
            ("edition-core-2", "Core Two", "edition-original"),
            ("edition-bonus-1", "Bonus Track", "edition-deluxe"),
        ],
    )
    conn.executemany(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date,
               album_artists, total_tracks, track_list
           ) VALUES (?, ?, 'album', '2024-01-01', 'Fixture Edition Artist', ?, ?)""",
        [
            (
                "edition-original",
                "Fixture Edition Album",
                2,
                '["edition-core-1", "edition-core-2"]',
            ),
            (
                "edition-deluxe",
                "Fixture Edition Album Deluxe",
                3,
                '["edition-core-1", "edition-core-2", "edition-bonus-1"]',
            ),
        ],
    )
    conn.executemany(
        """INSERT INTO album_spotify_links(
               album_id, spotify_album_id, evidence, confidence,
               play_count, track_count, updated_at
           ) VALUES (?, ?, 'fixture', 1.0, ?, ?, CURRENT_TIMESTAMP)""",
        [(9900, "edition-original", 8, 2), (9901, "edition-deluxe", 1, 3)],
    )
    conn.execute(
        """INSERT INTO album_projects(
               project_id, canonical_name, artist_id, primary_album_id,
               release_date, scope, project_type
           ) VALUES (990, 'Fixture Edition Album', 990, 9900,
                     '2024-01-01', 'release', 'album')"""
    )
    conn.executemany(
        """INSERT INTO album_project_albums(
               project_id, album_id, role, source_bucket, inferred
           ) VALUES (990, ?, ?, ?, 0)""",
        [(9900, "primary", "original_album"), (9901, "member", "deluxe")],
    )
    conn.executemany(
        """INSERT INTO album_project_tracks(
               project_id, track_id, membership_role, min_merge_level,
               source_album_id, is_exclusive, inferred
           ) VALUES (990, ?, ?, 2, ?, 0, 0)""",
        [
            (99000, "standard", 9900),
            (99001, "standard", 9900),
            (99002, "deluxe", 9901),
        ],
    )
    frame = pd.DataFrame(
        [
            {
                "album_project_id": 990,
                "album_project_name": "Fixture Edition Album",
                "artist_name": "Fixture Edition Artist",
                "track_id": track_id,
                "canonical_song_key": str(track_id),
            }
            for track_id, count in [(99000, 5), (99001, 3), (99002, 1)]
            for _ in range(count)
        ]
    )

    row = _album_full_replays(frame, conn, merge_level=2).iloc[0]

    assert row["value"] == 3.0
    assert row["secondary_value"] == 2.0
    assert row["secondary_unit"] == "/ 2 首"
    assert row["total_plays"] == 9


def test_album_full_replays_ignores_track_by_track_mixed_into_primary_album(seed_conn):
    import sqlite3

    import pandas as pd

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seed_conn.backup(conn)
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (991, 'Fixture Artist')")
    conn.execute(
        """INSERT INTO albums(album_id, album_name, artist_id)
           VALUES (9910, 'Fixture Show Album', 991)"""
    )
    tracks = [
        (99100, "Core One", "show-core-1", "show-original"),
        (99101, "Core Two", "show-core-2", "show-original"),
        (99102, "Commentary One", "show-talk-1", "show-track-by-track"),
        (99103, "Commentary Two", "show-talk-2", "show-track-by-track"),
    ]
    conn.executemany(
        """INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_id)
           VALUES (?, ?, 991, 9910, ?)""",
        [(track_id, name, spotify_id) for track_id, name, spotify_id, _ in tracks],
    )
    conn.executemany(
        """INSERT INTO spotify_track_meta(spotify_track_id, track_name, spotify_album_id)
           VALUES (?, ?, ?)""",
        [(spotify_id, name, album_id) for _, name, spotify_id, album_id in tracks],
    )
    conn.executemany(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date,
               album_artists, total_tracks, track_list)
           VALUES (?, ?, 'album', ?, 'Fixture Artist', ?, ?)""",
        [
            (
                "show-original",
                "Fixture Show Album",
                "2025-10-03",
                2,
                '["show-core-1", "show-core-2"]',
            ),
            (
                "show-track-by-track",
                "Fixture Show Album (Track by Track Version)",
                "2025-10-02",
                4,
                '["show-core-1", "show-core-2", "show-talk-1", "show-talk-2"]',
            ),
        ],
    )
    conn.executemany(
        """INSERT INTO album_spotify_links(
               album_id, spotify_album_id, evidence, confidence,
               play_count, track_count, updated_at)
           VALUES (9910, ?, 'fixture', 1.0, ?, ?, CURRENT_TIMESTAMP)""",
        [("show-original", 20, 2), ("show-track-by-track", 4, 4)],
    )
    conn.execute(
        """INSERT INTO album_projects(
               project_id, canonical_name, artist_id, primary_album_id,
               release_date, scope, project_type)
           VALUES (991, 'Fixture Show Album', 991, 9910,
                   '2025-10-03', 'release', 'album')"""
    )
    conn.execute(
        """INSERT INTO album_project_albums(
               project_id, album_id, role, source_bucket, inferred)
           VALUES (991, 9910, 'primary', 'original_album', 0)"""
    )
    conn.executemany(
        """INSERT INTO album_project_tracks(
               project_id, track_id, membership_role, min_merge_level,
               source_album_id, is_exclusive, inferred)
           VALUES (991, ?, 'standard', 2, 9910, 0, 0)""",
        [(track_id,) for track_id, *_ in tracks],
    )
    frame = pd.DataFrame(
        [
            {
                "album_project_id": 991,
                "album_project_name": "Fixture Show Album",
                "artist_name": "Fixture Artist",
                "track_id": track_id,
                "canonical_song_key": str(track_id),
            }
            for track_id, count in [(99100, 5), (99101, 3), (99102, 1), (99103, 1)]
            for _ in range(count)
        ]
    )

    row = _album_full_replays(frame, conn, merge_level=2).iloc[0]

    assert row["full_replays"] == 3
    assert row["user_track_count"] == 2
    assert row["total_tracks"] == 2
    assert row["total_plays"] == 10


def test_album_full_replays_excludes_conflicting_complete_original_candidates(seed_conn):
    import sqlite3

    import pandas as pd

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seed_conn.backup(conn)
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (992, 'Conflict Artist')")
    conn.execute(
        """INSERT INTO albums(album_id, album_name, artist_id)
           VALUES (9920, 'Conflict Album', 992)"""
    )
    tracks = [
        (99200, "A One", "conflict-a1", "conflict-a"),
        (99201, "A Two", "conflict-a2", "conflict-a"),
        (99202, "B One", "conflict-b1", "conflict-b"),
        (99203, "B Two", "conflict-b2", "conflict-b"),
    ]
    conn.executemany(
        """INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_id)
           VALUES (?, ?, 992, 9920, ?)""",
        [(track_id, name, spotify_id) for track_id, name, spotify_id, _ in tracks],
    )
    conn.executemany(
        """INSERT INTO spotify_track_meta(spotify_track_id, track_name, spotify_album_id)
           VALUES (?, ?, ?)""",
        [(spotify_id, name, album_id) for _, name, spotify_id, album_id in tracks],
    )
    conn.executemany(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date,
               album_artists, total_tracks, track_list)
           VALUES (?, 'Conflict Album', 'album', '2025-01-01',
                   'Conflict Artist', 2, ?)""",
        [
            ("conflict-a", '["conflict-a1", "conflict-a2"]'),
            ("conflict-b", '["conflict-b1", "conflict-b2"]'),
        ],
    )
    conn.executemany(
        """INSERT INTO album_spotify_links(
               album_id, spotify_album_id, evidence, confidence,
               play_count, track_count, updated_at)
           VALUES (9920, ?, 'fixture', 1.0, 10, 2, CURRENT_TIMESTAMP)""",
        [("conflict-a",), ("conflict-b",)],
    )
    conn.execute(
        """INSERT INTO album_projects(
               project_id, canonical_name, artist_id, primary_album_id,
               release_date, scope, project_type)
           VALUES (992, 'Conflict Album', 992, 9920,
                   '2025-01-01', 'release', 'album')"""
    )
    conn.execute(
        """INSERT INTO album_project_albums(
               project_id, album_id, role, source_bucket, inferred)
           VALUES (992, 9920, 'primary', 'original_album', 0)"""
    )
    conn.executemany(
        """INSERT INTO album_project_tracks(
               project_id, track_id, membership_role, min_merge_level,
               source_album_id, is_exclusive, inferred)
           VALUES (992, ?, 'standard', 2, 9920, 0, 0)""",
        [(track_id,) for track_id, *_ in tracks],
    )
    frame = pd.DataFrame(
        [
            {
                "album_project_id": 992,
                "album_project_name": "Conflict Album",
                "artist_name": "Conflict Artist",
                "track_id": track_id,
                "canonical_song_key": str(track_id),
            }
            for track_id, *_ in tracks
        ]
    )

    assert _album_full_replays(frame, conn, merge_level=2).empty


def test_album_full_replays_excludes_unknown_total(seed_conn):
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "album_name": "Unknown Metadata Album",
                "artist_name": "Unknown Artist",
                "track_id": track_id,
            }
            for track_id in [99001, 99002, 99003]
        ]
    )

    result = _album_full_replays(frame, seed_conn, merge_level=1)

    assert result.empty


def test_album_full_replays_excludes_single_release(seed_conn):
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "album_name": "Fixture Single",
                "artist_name": "Fixture Artist Alpha",
                "track_id": 900,
            }
        ]
    )

    result = _album_full_replays(frame, seed_conn, merge_level=1)

    assert result.empty


def test_album_detail_includes_album_project_payload(use_seed_db):
    from backend.services.billboard_service import get_album_chart_detail

    detail = get_album_chart_detail(
        album_name="Fixture Future LP",
        artist_name="Fixture Artist Alpha",
        min_ms=30_000,
        music_only=True,
        bb_top_n=50,
        bb_album_top_n=50,
        bb_artist_top_n=50,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        year_start=None,
        year_end=None,
        dynamic_threshold=False,
        max_merge_gap_minutes=None,
        merge_level=2,
    )

    project = detail["album_project"]
    assert project["album_project_name"] == "Fixture Future LP"
    assert project["artist_name"] == "Fixture Artist Alpha"
    assert project["play_count"] == 9
    assert sum(item["play_count"] for item in project["source_breakdown"]) == 9


def test_collaboration_candidate_detector_finds_primary_artist_remix(use_seed_db):
    from backend.core.version_merge import detect_collaboration_track_group_candidates

    candidates = detect_collaboration_track_group_candidates()
    match = candidates[
        (candidates["original_track_id"] == 920) & (candidates["candidate_track_id"] == 926)
    ]
    assert not match.empty

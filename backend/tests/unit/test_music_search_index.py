from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_032
from backend.domains.music_search.index import (
    get_music_search_index_state,
    rebuild_music_search_index,
)
from backend.domains.music_search.repository import search_music_index

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER
        );
        CREATE TABLE track_artists (
            track_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT NOT NULL
        );
        CREATE TABLE track_groups (
            group_id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            primary_track_id INTEGER NOT NULL,
            scope TEXT NOT NULL,
            parent_group_id INTEGER
        );
        CREATE TABLE track_group_members (
            group_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER,
            ms_played INTEGER,
            source_album_id INTEGER
        );
        INSERT INTO artists VALUES (1, 'Taylor Swift'), (2, 'Bon Iver');
        INSERT INTO albums VALUES (10, 'folklore', 1), (20, 'evermore', 1);
        INSERT INTO tracks VALUES
            (100, 'cardigan', 1, 10),
            (101, 'exile', 1, 10),
            (102, 'willow', 1, 20);
        INSERT INTO track_artists VALUES
            (100, 1, 'primary'),
            (101, 1, 'primary'),
            (101, 2, 'featured'),
            (102, 1, 'primary');
        INSERT INTO plays VALUES
            (1, 100, 200000, 10),
            (2, 100, 190000, 10),
            (3, 101, 210000, 10),
            (4, 102, 210000, 20);
        """
    )
    migrate_032(conn)
    conn.commit()
    return conn


def test_rebuild_publishes_one_valid_generation_with_fts_or_fallback() -> None:
    conn = _conn()
    report = rebuild_music_search_index(conn)
    state = get_music_search_index_state(conn)

    assert report["status"] in {"ready", "degraded"}
    assert report["document_count"] == (3 * 3) + 2 + 2
    assert state["active_generation_id"] == report["generation_id"]
    assert state["normalization_version"] == "nfkc_casefold_ws_punctuation_v1"
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM music_search_documents WHERE generation_id=?",
            (report["generation_id"],),
        ).fetchone()[0]
        == 13
    )


def test_track_candidates_follow_l1_l2_merge_semantics_and_keep_version_aliases() -> None:
    conn = _conn()
    conn.execute("INSERT INTO tracks VALUES (103, 'cardigan remaster', 1, 10)")
    conn.execute("INSERT INTO track_artists VALUES (103, 1, 'primary')")
    conn.execute("INSERT INTO plays VALUES (5, 103, 180000, 10)")
    conn.execute("INSERT INTO track_groups VALUES (1, 'cardigan', 100, 'recording', NULL)")
    conn.executemany(
        "INSERT INTO track_group_members VALUES (1, ?)",
        [(100,), (103,)],
    )
    rebuild_music_search_index(conn)

    l1 = search_music_index(
        conn,
        query="cardigan remaster",
        kind="track",
        page=1,
        page_size=20,
        merge_level=1,
    )
    l2 = search_music_index(
        conn,
        query="cardigan remaster",
        kind="track",
        page=1,
        page_size=20,
        merge_level=2,
    )

    assert [item.entity_key for item in l1.tracks] == ["track:103"]
    assert [item.entity_key for item in l2.tracks] == ["track:100"]
    assert l2.tracks[0].match_field == "alias"


def test_repository_ranks_primary_prefix_and_cross_field_tokens() -> None:
    conn = _conn()
    rebuild_music_search_index(conn)

    prefix = search_music_index(
        conn,
        query="card",
        kind="track",
        page=1,
        page_size=20,
        merge_level=2,
    )
    assert [item.entity_key for item in prefix.tracks] == ["track:100"]
    assert prefix.tracks[0].match_quality == "prefix"

    cross_field = search_music_index(
        conn,
        query="exile bon",
        kind="track",
        page=1,
        page_size=20,
        merge_level=2,
    )
    assert [item.entity_key for item in cross_field.tracks] == ["track:101"]
    assert cross_field.tracks[0].match_quality == "token"


def test_repository_returns_exact_totals_and_stable_pages() -> None:
    conn = _conn()
    rebuild_music_search_index(conn)

    first = search_music_index(
        conn,
        query="taylor",
        kind="track",
        page=1,
        page_size=2,
        merge_level=2,
    )
    second = search_music_index(
        conn,
        query="taylor",
        kind="track",
        page=2,
        page_size=2,
        merge_level=2,
    )

    assert first.total_by_kind.track == 3
    assert len(first.tracks) == 2
    assert len(second.tracks) == 1
    assert {item.entity_key for item in [*first.tracks, *second.tracks]} == {
        "track:100",
        "track:101",
        "track:102",
    }


def test_repository_joins_exact_snapshot_instead_of_loading_all_eligible_keys() -> None:
    conn = _conn()
    rebuild_music_search_index(conn)
    conn.execute(
        """INSERT INTO music_search_snapshot_meta(
               snapshot_key, filter_fingerprint, source_revision, status
           ) VALUES ('snapshot-one', 'snapshot-one', 'source-one', 'ready')"""
    )
    conn.execute(
        """INSERT INTO music_search_entity_context(
               snapshot_key, entity_key, play_events, total_ms
           ) VALUES ('snapshot-one', 'track:100', 2, 390000)"""
    )

    result = search_music_index(
        conn,
        query="taylor",
        kind="track",
        page=1,
        page_size=20,
        merge_level=2,
        snapshot_key="snapshot-one",
    )

    assert result.total_by_kind.track == 1
    assert [item.entity_key for item in result.tracks] == ["track:100"]


def test_repository_hot_path_never_reads_raw_play_or_aggregate_tables() -> None:
    conn = _conn()
    rebuild_music_search_index(conn)
    statements: list[str] = []
    conn.set_trace_callback(statements.append)

    result = search_music_index(
        conn,
        query="taylor",
        kind="track",
        page=2,
        page_size=2,
        merge_level=2,
    )
    conn.set_trace_callback(None)

    assert result.total_by_kind.track == 3
    forbidden_tables = (
        " plays",
        "agg_track_wks",
        "agg_album_wks",
        "agg_artist_wks",
        "agg_weekly_track_sources",
    )
    assert not any(
        table in statement.lower() for statement in statements for table in forbidden_tables
    )


def test_repository_treats_like_wildcards_as_literal_query_text() -> None:
    conn = _conn()
    rebuild_music_search_index(conn)

    result = search_music_index(
        conn,
        query="%%",
        kind="track",
        page=1,
        page_size=20,
        merge_level=2,
    )

    assert result.total_by_kind.track == 0
    assert result.tracks == []


def test_two_character_query_is_prefix_only_but_three_character_fallback_is_bounded() -> None:
    conn = _conn()
    rebuild_music_search_index(conn)
    conn.execute("DROP TABLE music_search_documents_fts")
    conn.execute(
        "UPDATE music_search_index_state SET status='degraded', tokenizer='bounded_like_fallback'"
    )

    two_chars = search_music_index(
        conn,
        query="lo",
        kind="track",
        page=1,
        page_size=20,
        merge_level=2,
    )
    substring = search_music_index(
        conn,
        query="ill",
        kind="track",
        page=1,
        page_size=20,
        merge_level=2,
    )

    assert two_chars.tracks == []
    assert [item.entity_key for item in substring.tracks] == ["track:102"]
    assert substring.tracks[0].match_quality == "substring"


def test_atomic_publish_retains_only_active_and_previous_generation() -> None:
    conn = _conn()
    first = rebuild_music_search_index(conn)
    conn.execute("INSERT INTO tracks VALUES (103, 'august', 1, 10)")
    conn.execute("INSERT INTO track_artists VALUES (103, 1, 'primary')")
    second = rebuild_music_search_index(conn)
    conn.execute("INSERT INTO tracks VALUES (104, 'betty', 1, 10)")
    conn.execute("INSERT INTO track_artists VALUES (104, 1, 'primary')")
    third = rebuild_music_search_index(conn)

    generations = {
        str(row[0])
        for row in conn.execute(
            "SELECT DISTINCT generation_id FROM music_search_documents"
        ).fetchall()
    }
    assert generations == {second["generation_id"], third["generation_id"]}
    assert first["generation_id"] not in generations
    assert third["previous_generation_id"] == second["generation_id"]

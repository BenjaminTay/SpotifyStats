from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.core.access_surface import reset_public_readonly_db_guard, set_public_readonly_db_guard
from backend.core.migrations import migrate_090
from backend.domains.music_search.detail_projection import (
    SCHEMA,
    load_detail_overlays,
    load_detail_project_membership,
    load_detail_source_facts,
    publish_detail_projection,
    source_rows_from_frame,
)
from scripts.prepare_music_detail_projection import verify_payload_rows

pytestmark = pytest.mark.unit


def fixture():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE music_search_snapshot_meta(snapshot_key TEXT PRIMARY KEY,source_revision TEXT,status TEXT);
    CREATE TABLE track_l1_identities(l1_id INTEGER PRIMARY KEY,representative_track_id INTEGER);
    CREATE TABLE tracks(track_id INTEGER PRIMARY KEY,track_name TEXT,artist_id INTEGER);
    CREATE TABLE artists(artist_id INTEGER PRIMARY KEY,artist_name TEXT);
    CREATE TABLE albums(album_id INTEGER PRIMARY KEY,album_name TEXT);
    CREATE TABLE album_projects(project_id INTEGER PRIMARY KEY);
    CREATE TABLE music_search_weekly_chart_context(snapshot_key TEXT,family TEXT,week TEXT,entity_key TEXT,rank INTEGER,play_count INTEGER,total_ms INTEGER,stable_sort_key TEXT);
    INSERT INTO music_search_snapshot_meta VALUES ('exact','revision','ready');
    INSERT INTO track_l1_identities VALUES (11,101),(12,102);
    INSERT INTO tracks VALUES (101,'Song',1),(102,'No Plays',1);
    INSERT INTO artists VALUES (1,'Artist');
    INSERT INTO albums VALUES (21,'Album'),(22,'Empty');
    INSERT INTO album_projects VALUES (31);
    """)
    conn.executescript(SCHEMA)
    payload = json.dumps({"entity_id": 11, "track_name": "Song", "artist_name": "Artist"})
    conn.execute(
        "INSERT INTO music_search_weekly_chart_context VALUES (?,?,?,?,?,?,?,?)",
        ("exact", "track", "2026-01-02", "track:11", 1, 2, 90000, payload),
    )
    context = SimpleNamespace(filter_fingerprint="exact", source_revision="revision")
    entities = [
        (
            "membership",
            31,
            json.dumps([{"track_id": 11, "l1_ids": [11], "canonical_song_key": "11"}]),
        ),
        ("album_track_keys", 31, "[11]"),
        ("artist_track_keys", 1, "[11]"),
        ("artist_album_keys", 1, "[]"),
    ]
    rows = [(11, 21, 21, "2026-01-02", "2026-01-03", 2, 90000)]
    publish_detail_projection(conn, context, rows, entities)
    return conn, context, rows, entities


def test_day_projection_keeps_both_tracks_and_coverage_edges():
    frame = pd.DataFrame(
        [
            {
                "track_id": 11,
                "source_album_id": 21,
                "track_album_id": 21,
                "billboard_week": "2026-01-02",
                "ts_date": "2026-01-03",
                "play_count": 1,
                "total_ms": 30000,
            },
            {
                "track_id": 11,
                "source_album_id": 21,
                "track_album_id": 21,
                "billboard_week": "2026-01-02",
                "ts_date": "2026-01-03",
                "play_count": 0,
                "total_ms": 9999,
            },
            {
                "track_id": 11,
                "source_album_id": 21,
                "track_album_id": 21,
                "billboard_week": "2026-01-09",
                "ts_date": "2026-01-09",
                "play_count": 1,
                "total_ms": 40000,
            },
        ]
    )
    assert source_rows_from_frame(frame) == [
        (11, 21, 21, "2026-01-02", "2026-01-03", 1, 39999),
        (11, 21, 21, "2026-01-09", "2026-01-09", 1, 40000),
    ]


def test_target_source_empty_is_distinct_from_missing_or_corrupt(monkeypatch):
    conn, _, _, _ = fixture()
    monkeypatch.setattr(
        "backend.domains.metadata.artist_identity.canonicalize_artist_frame",
        lambda frame, conn, dedupe=False: frame,
    )
    assert load_detail_source_facts(conn, "exact", l1_ids=[11])["play_count"].sum() == 2
    assert load_detail_source_facts(conn, "exact", l1_ids=[12]).empty
    assert load_detail_source_facts(conn, "missing", l1_ids=[11]) is None
    conn.execute("DELETE FROM music_search_detail_source_facts WHERE l1_id=11")
    assert load_detail_source_facts(conn, "exact", l1_ids=[11]) is None


def test_target_source_changed_weight_is_rejected(monkeypatch):
    conn, _, _, _ = fixture()
    monkeypatch.setattr(
        "backend.domains.metadata.artist_identity.canonicalize_artist_frame",
        lambda frame, conn, dedupe=False: frame,
    )
    conn.execute("UPDATE music_search_detail_source_facts SET total_ms=90001")
    assert load_detail_source_facts(conn, "exact", source_album_ids=[21]) is None


def test_membership_removed_and_mutated_are_unavailable():
    conn, _, _, _ = fixture()
    assert load_detail_project_membership(conn, "exact", 31)["l1_ids"].iloc[0] == [11]
    conn.execute(
        "UPDATE music_search_detail_entity_projection SET payload_json='[]' WHERE kind='membership'"
    )
    assert load_detail_project_membership(conn, "exact", 31) is None
    conn.execute("DELETE FROM music_search_detail_entity_projection WHERE kind='membership'")
    assert load_detail_project_membership(conn, "exact", 31) is None


def test_overlay_target_rows_are_validated_and_no1_is_preserved():
    conn, _, _, _ = fixture()
    document = {"artist_id": 1, "artist_name": "Artist"}
    result = load_detail_overlays(conn, "exact", entity="artist", document=document, values={})
    assert result["best_singles_overlay"] == [
        {"week": "2026-01-02", "rank": 1, "track_name": "Song"}
    ]
    assert result["artist_no1_by_week"][0]["no1_track_id"] == 11
    conn.execute("DELETE FROM music_search_weekly_chart_context WHERE entity_key='track:11'")
    assert (
        load_detail_overlays(conn, "exact", entity="artist", document=document, values={}) is None
    )


def test_public_guard_blocks_projection_publication():
    conn, context, rows, entities = fixture()
    token = set_public_readonly_db_guard(True)
    try:
        with pytest.raises(RuntimeError, match="public GET"):
            publish_detail_projection(conn, context, rows, entities)
    finally:
        reset_public_readonly_db_guard(token)


def test_schema90_is_additive_and_idempotent():
    conn, _, _, _ = fixture()
    before = conn.execute("SELECT * FROM tracks").fetchall()
    migrate_090(conn)
    migrate_090(conn)
    assert conn.execute("SELECT * FROM tracks").fetchall() == before
    assert conn.execute("SELECT COUNT(*) FROM music_search_detail_source_facts").fetchone()[0] == 1


def test_manifest_rejects_negative_and_duplicate_source_rows():
    conn, _, rows, _ = fixture()
    with pytest.raises(RuntimeError, match="duplicate"):
        verify_payload_rows(conn, [*rows, *rows], [])
    negative = [(*rows[0][:5], -1, 90000)]
    with pytest.raises(RuntimeError, match="metrics"):
        verify_payload_rows(conn, negative, [])


def test_clone_and_bounded_week_replacement_publish_complete_checks(monkeypatch):
    from backend.domains.music_search.detail_projection import (
        clone_detail_projection,
        replace_detail_projection_weeks,
    )

    conn, _, _, entities = fixture()
    conn.execute("INSERT INTO music_search_snapshot_meta VALUES ('next','next-revision','ready')")
    context = SimpleNamespace(filter_fingerprint="next", source_revision="next-revision")
    clone_detail_projection(conn, context, "exact")
    monkeypatch.setattr(
        "backend.domains.metadata.artist_identity.canonicalize_artist_frame",
        lambda frame, conn, dedupe=False: frame,
    )
    assert load_detail_source_facts(conn, "next", l1_ids=[11])["play_count"].sum() == 2
    rows = [(11, 21, 21, "2026-01-02", "2026-01-03", 3, 100000)]
    replace_detail_projection_weeks(conn, context, "exact", {"2026-01-02"}, rows, entities)
    assert load_detail_source_facts(conn, "next", l1_ids=[11])["play_count"].sum() == 3
    assert load_detail_project_membership(conn, "next", 31)["l1_ids"].iloc[0] == [11]


def test_export_validate_import_and_reject_source_fence_drift(tmp_path, monkeypatch):
    from scripts.prepare_music_detail_projection import (
        export_projection,
        import_projection,
        validate_manifest,
    )

    conn, context, _, _ = fixture()
    conn.commit()
    fence = {"source": "exact"}
    monkeypatch.setattr(
        "scripts.prepare_music_detail_projection.publication_fence",
        lambda conn, contexts: dict(fence),
    )
    path = tmp_path / "manifest.json"
    assert export_projection(conn, (context,), path)["status"] == "exported"
    validate_manifest(conn, (context,), path)
    conn.execute("DELETE FROM music_search_detail_projection_state")
    conn.commit()
    assert import_projection(conn, (context,), path)["status"] == "imported"
    fence["source"] = "changed"
    with pytest.raises(RuntimeError, match="fence mismatch"):
        import_projection(conn, (context,), path)
    assert load_detail_project_membership(conn, "exact", 31) is not None


def test_entity_summary_checksum_detects_exact_target_mutation():
    from backend.domains.music_search.detail_projection import validate_detail_entity_context

    conn, context, rows, entities = fixture()
    conn.execute("""CREATE TABLE music_search_entity_context(snapshot_key TEXT, entity_key TEXT,
        play_events INTEGER,total_ms INTEGER,peak_position INTEGER,peak_weeks INTEGER,
        weeks_on_chart INTEGER,weeks_at_no1 INTEGER,power_score INTEGER,power_rank INTEGER,
        first_week TEXT,latest_week TEXT,first_peak_week TEXT)""")
    conn.execute(
        "INSERT INTO music_search_entity_context VALUES ('exact','track:11',2,90000,1,1,1,1,100,1,'2026-01-02','2026-01-02','2026-01-02')"
    )
    publish_detail_projection(conn, context, rows, entities)
    assert validate_detail_entity_context(conn, "exact", "track:11")
    conn.execute("UPDATE music_search_entity_context SET power_rank=2")
    assert not validate_detail_entity_context(conn, "exact", "track:11")


def test_stale_publication_is_only_usable_as_private_delta_base():
    from backend.domains.music_search.detail_projection import projection_available

    conn, _, _, _ = fixture()
    conn.execute("UPDATE music_search_snapshot_meta SET status='stale'")
    assert not projection_available(conn, "exact")
    assert projection_available(conn, "exact", allow_stale=True)
    assert load_detail_project_membership(conn, "exact", 31) is None


def test_explicit_empty_artist_history_is_valid():
    from backend.domains.music_search.detail_projection import validate_detail_entity_ledger

    conn, _, _, _ = fixture()
    assert validate_detail_entity_ledger(conn, "exact", "artist", "artist:1")

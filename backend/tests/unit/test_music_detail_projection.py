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
    _target_ledger,
    ledger_check,
    load_detail_overlays,
    load_detail_project_membership,
    load_detail_source_facts,
    load_detail_source_l1_ids,
    payload_digest,
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


def _count_oracle(conn, key, document, values):
    from backend.domains.billboard.detail_project import _components

    project_id, _, source = _components(conn, key, document, values)
    return (
        int(source["canonical_song_key"].nunique())
        if project_id is not None and not source.empty
        else 0
    )


@pytest.mark.parametrize("level,dynamic", [(2, True), (2, False), (3, True), (3, False)])
@pytest.mark.parametrize("same_song", [True, False])
def test_lightweight_project_count_matches_source_frame_oracle(
    monkeypatch, level, dynamic, same_song
):
    from backend.domains.billboard.detail_project import project_unique_song_count

    conn, context, rows, entities = fixture()
    # A second version contributes duration only, with a different source album.
    # Count canonical songs, never raw versions, source albums or only play_count>0.
    rows += [(12, 0, 22, "2026-01-09", "2026-01-09", 0, 9999)]
    members = [
        {"track_id": 11, "l1_ids": [11], "canonical_song_key": "song"},
        {"track_id": 12, "l1_ids": [12], "canonical_song_key": "song" if same_song else "other"},
    ]
    entities = [
        (kind, entity_id, json.dumps(members) if kind == "membership" else payload)
        for kind, entity_id, payload in entities
    ]
    publish_detail_projection(conn, context, rows, entities)
    monkeypatch.setattr(
        "backend.domains.metadata.artist_identity.canonicalize_artist_frame",
        lambda frame, conn, dedupe=False: frame,
    )
    document = {"album_project_id": 31}
    values = {"merge_level": level, "dynamic_threshold": dynamic}
    expected = _count_oracle(conn, "exact", document, values)
    assert expected == (1 if same_song else 2)
    monkeypatch.setattr(pd, "read_sql_query", lambda *a, **k: pytest.fail("source frame assembled"))
    before = conn.total_changes
    assert project_unique_song_count(conn, "exact", document, values) == expected
    assert conn.total_changes == before


@pytest.mark.parametrize("missing", ["identity", "track", "artist"])
def test_lightweight_source_ids_keep_metadata_inner_join_filter(monkeypatch, missing):
    conn, _, _, _ = fixture()
    table, column, value = {
        "identity": ("track_l1_identities", "l1_id", 11),
        "track": ("tracks", "track_id", 101),
        "artist": ("artists", "artist_id", 1),
    }[missing]
    conn.execute(f"DELETE FROM {table} WHERE {column}=?", (value,))
    monkeypatch.setattr(
        "backend.domains.metadata.artist_identity.canonicalize_artist_frame",
        lambda frame, conn, dedupe=False: frame,
    )
    old = load_detail_source_facts(conn, "exact", l1_ids=[11])
    assert old.empty
    assert load_detail_source_l1_ids(conn, "exact", [11]) == set()


@pytest.mark.parametrize(
    "mutation",
    [
        "remove_row",
        "change_weight",
        "change_source",
        "missing_check",
        "bad_digest",
        "bad_json",
        "wrong_check",
        "stale",
        "source_drift",
        "version_drift",
    ],
)
def test_lightweight_source_ids_reject_same_unavailable_sources(monkeypatch, mutation):
    from fastapi import HTTPException

    from backend.domains.billboard.detail_project import project_unique_song_count

    conn, _, _, _ = fixture()
    edits = {
        "remove_row": "DELETE FROM music_search_detail_source_facts WHERE l1_id=11",
        "change_weight": "UPDATE music_search_detail_source_facts SET total_ms=90001",
        "change_source": "UPDATE music_search_detail_source_facts SET source_album_id=22",
        "missing_check": "DELETE FROM music_search_detail_entity_projection WHERE kind='source_check_l1' AND entity_id=11",
        "bad_digest": "UPDATE music_search_detail_entity_projection SET payload_digest='bad' WHERE kind='source_check_l1' AND entity_id=11",
        "stale": "UPDATE music_search_snapshot_meta SET status='stale'",
        "source_drift": "UPDATE music_search_snapshot_meta SET source_revision='next'",
        "version_drift": "UPDATE music_search_detail_projection_state SET projection_version='next'",
    }
    if mutation in edits:
        conn.execute(edits[mutation])
    else:
        payload = {"bad_json": "{", "wrong_check": "{}"}[mutation]
        conn.execute(
            "UPDATE music_search_detail_entity_projection SET payload_json=?,payload_digest=? "
            "WHERE kind='source_check_l1' AND entity_id=11",
            (payload, payload_digest(payload)),
        )
    monkeypatch.setattr(
        "backend.domains.metadata.artist_identity.canonicalize_artist_frame",
        lambda frame, conn, dedupe=False: frame,
    )
    assert load_detail_source_facts(conn, "exact", l1_ids=[11]) is None
    assert load_detail_source_l1_ids(conn, "exact", [11]) is None
    with pytest.raises(HTTPException) as error:
        project_unique_song_count(conn, "exact", {"album_project_id": 31}, {"merge_level": 3})
    assert error.value.status_code == 503


def test_lightweight_source_ids_check_every_selected_target_and_empty_compatibility():
    conn, _, _, _ = fixture()
    assert load_detail_source_l1_ids(conn, "missing", []) is None
    assert load_detail_source_l1_ids(conn, "exact", []) == set()
    assert load_detail_source_l1_ids(conn, "exact", [12]) == set()
    assert load_detail_source_l1_ids(conn, "exact", [11, 11, 12]) == {11}
    conn.execute(
        "DELETE FROM music_search_detail_entity_projection WHERE kind='source_check_l1' AND entity_id=12"
    )
    assert load_detail_source_l1_ids(conn, "exact", [11, 12]) is None


def test_lightweight_source_ids_preserve_legacy_empty_check_and_target_scope():
    conn, _, _, _ = fixture()
    conn.execute(
        "UPDATE music_search_detail_entity_projection SET payload_json='[]',payload_digest=? "
        "WHERE kind='source_check_l1' AND entity_id=12",
        (payload_digest("[]"),),
    )
    assert load_detail_source_l1_ids(conn, "exact", [11, 12]) == {11}
    conn.execute(
        "UPDATE music_search_detail_entity_projection SET payload_digest='bad' "
        "WHERE kind='source_check_l1' AND entity_id=12"
    )
    assert load_detail_source_l1_ids(conn, "exact", [11]) == {11}
    assert load_detail_source_l1_ids(conn, "exact", [11, 12]) is None


def test_lightweight_project_count_preserves_empty_membership_and_missing_publication():
    from fastapi import HTTPException

    from backend.domains.billboard.detail_project import project_unique_song_count

    conn, _, _, _ = fixture()
    document = {"album_project_id": 31}
    values = {"merge_level": 3}
    conn.execute(
        "UPDATE music_search_detail_entity_projection SET payload_json='[]',payload_digest=? "
        "WHERE kind='membership'",
        (payload_digest("[]"),),
    )
    assert project_unique_song_count(conn, "exact", document, values) == 0
    assert project_unique_song_count(conn, "missing", {"album_project_id": None}, values) == 0
    assert project_unique_song_count(conn, "missing", document, {"merge_level": 1}) == 0
    with pytest.raises(HTTPException) as error:
        project_unique_song_count(conn, "missing", document, values)
    assert error.value.status_code == 503


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


def test_large_target_ledger_reads_checks_in_one_batch_and_preserves_rows():
    conn, _, _, _ = fixture()
    empty = json.dumps(ledger_check([]), separators=(",", ":"))
    ids = list(range(1000, 2200))
    conn.executemany(
        "INSERT INTO music_search_detail_entity_projection VALUES (?,?,?,?,?)",
        [
            ("exact", "ledger_check_track", identity, empty, payload_digest(empty))
            for identity in ids
        ],
    )
    # Unrelated corrupt facts must not invalidate this target's publication.
    conn.execute(
        "INSERT INTO music_search_detail_entity_projection VALUES ('exact','ledger_check_track',999,'{}','bad')"
    )
    expected = [
        list(row)
        for row in conn.execute(
            "SELECT week,rank,entity_key,play_count,total_ms,stable_sort_key FROM music_search_weekly_chart_context WHERE entity_key='track:11'"
        )
    ]
    statements = []
    conn.set_trace_callback(statements.append)
    actual = _target_ledger(conn, "exact", "track", ["track:11", *(f"track:{i}" for i in ids)])
    conn.set_trace_callback(None)
    assert actual == expected
    assert len(statements) == 3


@pytest.mark.parametrize(
    "fault", ["missing_check", "corrupt_check", "changed_ledger", "missing_state"]
)
def test_batched_target_ledger_rejects_incomplete_or_changed_facts(fault):
    conn, _, _, _ = fixture()
    if fault == "missing_check":
        conn.execute(
            "DELETE FROM music_search_detail_entity_projection WHERE kind='ledger_check_track' AND entity_id=11"
        )
    elif fault == "corrupt_check":
        conn.execute(
            "UPDATE music_search_detail_entity_projection SET payload_json='{}' WHERE kind='ledger_check_track' AND entity_id=11"
        )
    elif fault == "changed_ledger":
        conn.execute(
            "UPDATE music_search_weekly_chart_context SET play_count=99 WHERE entity_key='track:11'"
        )
    else:
        conn.execute("DELETE FROM music_search_detail_projection_state")
    assert _target_ledger(conn, "exact", "track", ["track:11", "track:12"]) is None


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

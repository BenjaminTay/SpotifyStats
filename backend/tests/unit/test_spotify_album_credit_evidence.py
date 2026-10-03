"""Album evidence and real consumer regressions, with only test-owned databases."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.domains.metadata.spotify_album_credits import (
    AlbumArtistResolver,
    album_credit_revision,
    create_schema,
    persist_album_artists,
)
from backend.domains.metadata.spotify_refresh import upsert_album_batch
from scripts.backfill_spotify_album_artist_credits import run_backfill

pytestmark = pytest.mark.unit


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "album-evidence.db"
    source = sqlite3.connect(
        f"file:{Path(__file__).parents[1] / 'fixtures' / 'seed.db'}?mode=ro&immutable=1", uri=True
    )
    conn = sqlite3.connect(path)
    source.backup(conn)
    for column in [
        "spotify_artist_id TEXT",
        "genres TEXT",
        "popularity INTEGER",
        "followers INTEGER",
    ]:
        conn.execute(f"ALTER TABLE artists ADD COLUMN {column}")
    from backend.domains.metadata.governance_revision import (
        install_revision_tracking as install_health,
    )
    from backend.services.analysis_snapshot_revision import install_revision_tracking

    install_revision_tracking(conn)
    install_health(conn)
    conn.commit()
    source.close()
    conn.close()
    return path


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def artists(conn):
    conn.executemany(
        "INSERT INTO artists(artist_id,artist_name,spotify_artist_id) VALUES(?,?,?)",
        [
            (10000, "Earth, Wind & Fire", "id-a"),
            (10001, "Other", "id-b"),
            (10002, "Same", "id-c"),
        ],
    )


def album(credits=None):
    return {
        "id": "album-test",
        "name": "Album Test",
        "album_type": "album",
        "release_date": "2020-01-01",
        "total_tracks": 2,
        "artists": credits
        if credits is not None
        else [{"id": "id-a", "name": "Earth, Wind & Fire"}, {"id": "id-b", "name": "Other"}],
    }


def snapshot(conn):
    tables = (
        "plays",
        "tracks",
        "track_artists",
        "spotify_auto_track_credits",
        "track_credit_overrides",
    )
    return {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
        for table in tables
    }


def test_ordered_multicredit_source_idempotency_and_immutable_track_facts(database):
    conn = connect(database)
    artists(conn)
    before = snapshot(conn)
    upsert_album_batch(conn, [album()], source_run_id="run-1")
    rows = AlbumArtistResolver(conn).read("album-test")
    assert [
        (c["spotify_artist_id"], c["credit_order"], c["canonical_artist_id"]) for c in rows
    ] == [("id-a", 0, 10000), ("id-b", 1, 10001)]
    assert all("role" not in row for row in rows)
    rev = album_credit_revision(conn)
    upsert_album_batch(conn, [album()], source_run_id="run-2")
    assert album_credit_revision(conn) == rev
    assert conn.execute("SELECT count(*) FROM spotify_album_credit_events").fetchone()[0] == 1
    assert (
        conn.execute("SELECT source_run_id FROM spotify_album_credit_sets").fetchone()[0] == "run-2"
    )
    assert snapshot(conn) == before
    conn.close()


def test_same_name_different_id_rename_and_comma_name(database):
    conn = connect(database)
    artists(conn)
    upsert_album_batch(conn, [album([{"id": "id-c", "name": "Earth, Wind & Fire"}])])
    resolver = AlbumArtistResolver(conn)
    assert resolver.match("album-test", 10000) == "id_mismatch"
    assert resolver.match("album-test", 10002) == "verified_id"
    upsert_album_batch(conn, [album([{"id": "id-c", "name": "New, Name"}])])
    assert AlbumArtistResolver(conn).match("album-test", 10002) == "verified_id"
    assert AlbumArtistResolver(conn).read("album-test")[0]["credited_name"] == "New, Name"
    assert (
        conn.execute(
            "SELECT event_type FROM spotify_album_credit_events ORDER BY event_id DESC"
        ).fetchone()[0]
        == "changed"
    )
    conn.close()


@pytest.mark.parametrize(
    "bad",
    [
        [],
        [{"name": "Earth, Wind & Fire"}],
        [{"id": "id-x", "name": "Wrong"}],
        [{"id": "id-a", "name": "A"}, {"id": "id-a", "name": "B"}],
    ],
)
def test_bad_or_conflicting_refresh_keeps_reliable_evidence(database, bad):
    conn = connect(database)
    artists(conn)
    upsert_album_batch(conn, [album()])
    before, rev = AlbumArtistResolver(conn).read("album-test"), album_credit_revision(conn)
    upsert_album_batch(conn, [album(bad)])
    upsert_album_batch(conn, [album(bad)])
    assert AlbumArtistResolver(conn).read("album-test") == before
    assert album_credit_revision(conn) == rev
    assert (
        conn.execute(
            "SELECT album_artists FROM spotify_album_meta WHERE spotify_album_id='album-test'"
        ).fetchone()[0]
        == "Earth, Wind & Fire, Other"
    )
    assert (
        conn.execute(
            "SELECT count(*) FROM spotify_album_credit_events WHERE event_type='rejected'"
        ).fetchone()[0]
        == 1
    )
    conn.close()


def test_missing_id_and_ambiguous_local_mapping_require_review(database):
    conn = connect(database)
    artists(conn)
    upsert_album_batch(conn, [album([{"name": "Earth, Wind & Fire"}])])
    assert AlbumArtistResolver(conn).match("album-test", 10000) == "unresolved"
    upsert_album_batch(conn, [album([{"id": "id-a", "name": "Earth, Wind & Fire"}])])
    conn.execute(
        "INSERT INTO artist_identity_external_ids(artist_id,provider,external_id,evidence_type,verified) VALUES(10001,'spotify','id-a','user_confirmed',1)"
    )
    assert AlbumArtistResolver(conn).match("album-test", 10000) == "ambiguous"
    conn.close()


def test_manual_canonical_governance_and_undo_take_precedence(database):
    from backend.domains.metadata.artist_identity import (
        create_artist_identity_group,
        get_identity_revision,
        undo_artist_identity_event,
    )

    conn = connect(database)
    artists(conn)
    upsert_album_batch(conn, [album([{"id": "id-a", "name": "Provider Name"}])])
    event = create_artist_identity_group(
        conn,
        artist_ids=[10000, 10001],
        canonical_artist_id=10001,
        display_name="Manual Display",
        expected_revision=get_identity_revision(conn),
        idempotency_key="album-identity-test",
        reason="test",
        confirm_external_id_conflict=True,
    )
    resolver = AlbumArtistResolver(conn)
    assert resolver.read("album-test")[0]["canonical_artist_id"] == 10001
    assert resolver.match("album-test", artist_name="Manual Display") == "verified_id"
    undo_artist_identity_event(
        conn,
        event_id=event["event_id"],
        reason="test undo",
        expected_revision=get_identity_revision(conn),
        idempotency_key="album-identity-undo",
    )
    assert AlbumArtistResolver(conn).read("album-test")[0]["canonical_artist_id"] == 10000
    conn.close()


def test_release_cycle_id_verification_and_failure_do_not_pass_legacy(database, monkeypatch):
    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )
    from backend.services import release_cycle_service as svc

    conn = connect(database)
    artists(conn)
    upsert_album_batch(conn, [album([{"id": "id-a", "name": "Renamed, Artist"}])])
    conn.close()
    monkeypatch.setattr(svc, "get_db", lambda *args, **kwargs: connect(database))
    token = set_public_readonly_db_guard(True)
    try:
        assert svc._verify_album_artists(["album-test"], "Earth, Wind & Fire") == {"album-test"}
        assert svc._verify_album_artists(["album-test"], "Other") == set()
        assert svc._verify_album_artists(["a1"], "Fixture Artist Alpha") == set()
    finally:
        reset_public_readonly_db_guard(token)
    monkeypatch.setattr(svc, "_get_spotify_token", lambda: None)
    assert svc._fetch_album_artists_from_api(["album-test"], "Other") == set()


def test_legacy_migration_preserves_string_and_is_not_id_verified():
    from backend.core.migrations import migrate_088

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE artists(artist_id INTEGER,artist_name TEXT); INSERT INTO artists VALUES(1,'Earth, Wind & Fire'); CREATE TABLE spotify_album_meta(spotify_album_id TEXT PRIMARY KEY,album_artists TEXT); INSERT INTO spotify_album_meta VALUES('old','Earth, Wind & Fire');"
    )
    migrate_088(conn)
    migrate_088(conn)
    resolver = AlbumArtistResolver(conn)
    assert (
        resolver.match("old", 1, "Earth, Wind & Fire", "Earth, Wind & Fire") == "legacy_name_match"
    )
    assert resolver.read("old") == []
    assert (
        conn.execute("SELECT album_artists FROM spotify_album_meta").fetchone()[0]
        == "Earth, Wind & Fire"
    )
    conn.close()


def test_records_consumer_uses_ids_after_rename_and_rejects_same_name_wrong_id():
    from backend.domains.playback.records_album_facts import load_original_memberships
    from backend.tests.unit.test_records_build_optimization import _album_fixture

    conn = _album_fixture(1)
    create_schema(conn)
    conn.execute("ALTER TABLE artists ADD COLUMN spotify_artist_id TEXT")
    conn.execute("UPDATE artists SET spotify_artist_id='id-a'")
    conn.execute("INSERT INTO artists VALUES(2,'same-name','id-b')")
    persist_album_artists(conn, {"id": "0", "artists": [{"id": "id-a", "name": "Renamed, Artist"}]})
    assert load_original_memberships(conn, 1) == {0: ({"0", "1"}, 2)}
    conn.execute("UPDATE album_projects SET artist_id=2")
    conn.execute("UPDATE artists SET artist_name='Renamed, Artist' WHERE artist_id=2")
    assert load_original_memberships(conn, 1).get(0) is None
    conn.close()


def test_billboard_metadata_fence_updates_without_manual_cache_clear(database, monkeypatch):
    from backend.domains.billboard import data_loader

    conn = connect(database)
    artists(conn)
    conn.execute(
        "INSERT INTO albums(album_id,album_name,artist_id) VALUES(10000,'Album Test',10000)"
    )
    upsert_album_batch(conn, [album([{"id": "id-c", "name": "Earth, Wind & Fire"}])])
    conn.close()
    monkeypatch.setattr(data_loader, "get_db", lambda: connect(database))
    data_loader._load_album_metadata.cache_clear()
    assert "Album Test" not in set(data_loader._load_album_metadata()["type"]["album_name"])
    conn = connect(database)
    conn.execute("UPDATE artists SET spotify_artist_id='id-c' WHERE artist_id=10000")
    # Duplicate ID remains ambiguous until manual governance resolves it.
    conn.execute("UPDATE artists SET spotify_artist_id=NULL WHERE artist_id=10002")
    conn.commit()
    conn.close()
    assert "Album Test" in set(data_loader._load_album_metadata()["type"]["album_name"])
    data_loader._load_album_metadata.cache_clear()


def test_backfill_api_failure_and_duplicate_refresh_only_write_album_evidence(database):
    conn = connect(database)
    artists(conn)
    before = snapshot(conn)

    class Provider:
        def get_cc_token(self):
            return "test-token"

        def get_albums(self, ids, token):
            return {"albums": [album()]}

    assert run_backfill(conn, Provider(), ["album-test"], run_id="one")["observed"] == 1
    rev = album_credit_revision(conn)
    assert run_backfill(conn, Provider(), ["album-test"], run_id="two")["unchanged"] == 1

    class Failed(Provider):
        def get_albums(self, ids, token):
            raise RuntimeError("request failed")

    assert run_backfill(conn, Failed(), ["album-test"], run_id="failed")["failed"] == 1

    class MissingBatch(Provider):
        def get_albums(self, ids, token):
            return {"albums": None}

    assert run_backfill(conn, MissingBatch(), ["album-test"], run_id="missing")["failed"] == 1
    assert album_credit_revision(conn) == rev
    assert snapshot(conn) == before
    conn.close()


def test_evidence_write_rolls_back_atomically(database):
    conn = connect(database)
    artists(conn)
    upsert_album_batch(conn, [album()])
    before = AlbumArtistResolver(conn).read("album-test")
    conn.execute(
        "CREATE TRIGGER reject_album_credit BEFORE INSERT ON spotify_album_artist_credits BEGIN SELECT RAISE(ABORT,'test'); END"
    )
    changed = album([{"id": "id-b", "name": "Other"}, {"id": "id-a", "name": "Renamed"}])
    with pytest.raises(sqlite3.IntegrityError):
        persist_album_artists(conn, changed)
    assert AlbumArtistResolver(conn).read("album-test") == before
    assert conn.execute("SELECT count(*) FROM spotify_album_credit_events").fetchone()[0] == 1
    conn.close()


def test_supplementary_writers_share_album_evidence_and_preserve_parent(database, monkeypatch):
    from backend.core import version_merge
    from backend.services import release_cycle_service
    from scripts.fetch_covers import _upsert_album_meta

    conn = connect(database)
    artists(conn)
    raw_before = snapshot(conn)
    conn.commit()
    conn.close()

    class Provider:
        def get_cc_token(self):
            return "test-token"

        def get_albums(self, ids, token):
            return {"albums": [album()]}

        def search_albums(self, *args, **kwargs):
            return {"albums": {"items": [album()]}}

    monkeypatch.setattr(version_merge, "get_db", lambda **kwargs: connect(database))
    monkeypatch.setattr("backend.providers.spotify.client.SpotifyProvider", Provider)
    version_merge._fetch_album_tracks_from_api(["album-test"])
    conn = connect(database)
    assert len(AlbumArtistResolver(conn).read("album-test")) == 2
    conn.execute(
        "UPDATE spotify_album_meta SET track_list='[\"kept\"]' WHERE spotify_album_id='album-test'"
    )
    conn.commit()
    _upsert_album_meta(
        conn,
        "album-test",
        "Album Test",
        "album",
        "2020-01-01",
        1,
        None,
        [],
        None,
        [{"id": "id-a", "name": "Renamed, Name"}, {"id": "id-b", "name": "Other"}],
    )
    conn.commit()
    assert AlbumArtistResolver(conn).read("album-test")[0]["credited_name"] == "Renamed, Name"
    assert (
        conn.execute(
            "SELECT track_list FROM spotify_album_meta WHERE spotify_album_id='album-test'"
        ).fetchone()[0]
        == '["kept"]'
    )
    conn.close()
    monkeypatch.setattr(release_cycle_service, "get_db", lambda **kwargs: connect(database))
    monkeypatch.setattr(release_cycle_service, "SpotifyProvider", Provider)
    monkeypatch.setattr(release_cycle_service, "_get_spotify_token", lambda: "test-token")
    release_cycle_service._spotify_search_album.cache_clear()
    assert release_cycle_service._spotify_search_album(
        "Album Test", "Earth, Wind & Fire", skip_db_check=True
    )
    conn = connect(database)
    assert AlbumArtistResolver(conn).read("album-test")[0]["credited_name"] == "Earth, Wind & Fire"
    assert snapshot(conn) == raw_before
    conn.close()
    release_cycle_service._spotify_search_album.cache_clear()


def test_analysis_and_health_revisions_follow_accepted_evidence_only(database):
    from backend.domains.metadata.governance_revision import family_revision
    from backend.services.analysis_snapshot_revision import source_revision

    conn = connect(database)
    artists(conn)
    conn.commit()
    before = source_revision(conn, "analysis_records")
    health = family_revision(conn, "import_health")
    upsert_album_batch(conn, [album()])
    assert source_revision(conn, "analysis_records") != before
    assert family_revision(conn, "import_health") != health
    stable = (source_revision(conn, "analysis_records"), family_revision(conn, "import_health"))
    upsert_album_batch(conn, [album()])
    upsert_album_batch(conn, [album([])])
    assert (
        source_revision(conn, "analysis_records"),
        family_revision(conn, "import_health"),
    ) == stable
    conn.close()


def test_release_search_cache_prefers_identity_over_same_name(database, monkeypatch):
    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )
    from backend.services import release_cycle_service as svc

    conn = connect(database)
    artists(conn)
    upsert_album_batch(conn, [album([{"id": "id-c", "name": "Earth, Wind & Fire"}])])
    conn.close()
    monkeypatch.setattr(svc, "get_db", lambda **kwargs: connect(database))
    svc._spotify_search_album.cache_clear()
    guard = set_public_readonly_db_guard(True)
    try:
        assert svc._spotify_search_album("Album Test", "Earth, Wind & Fire") is None
        conn = connect(database)
        conn.execute("UPDATE artists SET spotify_artist_id='id-c' WHERE artist_id=10000")
        conn.execute("UPDATE artists SET spotify_artist_id=NULL WHERE artist_id=10002")
        conn.commit()
        conn.close()
        assert (
            svc._spotify_search_album("Album Test", "Earth, Wind & Fire")["spotify_album_id"]
            == "album-test"
        )
    finally:
        reset_public_readonly_db_guard(guard)
        svc._spotify_search_album.cache_clear()


def test_yearly_preparation_registry_has_album_revision_fence(database, monkeypatch):
    from backend.services import yearly_review_service as svc

    conn = connect(database)
    artists(conn)
    conn.commit()
    monkeypatch.setattr(svc, "get_db", lambda **kwargs: connect(database))
    monkeypatch.setattr(svc, "database_revision", lambda year: "playback-unchanged")
    before = svc._report_source_revision(2024)
    upsert_album_batch(conn, [album()])
    changed = svc._report_source_revision(2024)
    assert before != changed
    upsert_album_batch(conn, [album()])
    upsert_album_batch(conn, [album([])])
    assert svc._report_source_revision(2024) == changed
    conn.close()


def test_auto_merge_does_not_group_identical_names_with_different_album_artist_ids():
    from backend.domains.playback.album_project_auto_merge import plan_album_project_auto_merges
    from backend.tests.unit.test_album_project_auto_merge import (
        _add_local_album,
        _add_spotify_release,
        _connection,
        _prepare_standalone_projects,
    )

    conn = _connection()
    for number, sid, name in [(1, "id-a", "Local A"), (2, "id-b", "Local B")]:
        conn.execute("INSERT INTO artists(artist_id,artist_name) VALUES(?,?)", (number, name))
        conn.execute(
            "INSERT INTO artist_identity_external_ids(artist_id,provider,external_id,evidence_type) VALUES(?,'spotify',?,'user_confirmed')",
            (number, sid),
        )
        _add_spotify_release(
            conn,
            spotify_album_id=f"release-{number}",
            album_name="Same Album",
            album_artists="Same Provider Name",
            release_date="2020-01-01",
            track_ids=["track-a", "track-b"],
        )
        _add_local_album(
            conn,
            album_id=10 + number,
            album_name="Same Album",
            artist_id=number,
            artist_name=name,
            spotify_album_id=f"release-{number}",
            spotify_track_id="track-a" if number == 1 else "track-b",
        )
        persist_album_artists(
            conn,
            {"id": f"release-{number}", "artists": [{"id": sid, "name": "Same Provider Name"}]},
        )
    _prepare_standalone_projects(conn)
    assert plan_album_project_auto_merges(conn).candidates == ()
    conn.close()


def test_auto_merge_persists_canonical_artist_key_after_provider_rename():
    from backend.domains.playback.album_project_auto_merge import (
        apply_album_project_auto_merge_plan,
        plan_album_project_auto_merges,
    )
    from backend.tests.unit.test_album_project_auto_merge import (
        _add_local_album,
        _add_spotify_release,
        _connection,
        _prepare_standalone_projects,
    )

    conn = _connection()
    _add_spotify_release(
        conn,
        spotify_album_id="release",
        album_name="Bad Boy",
        album_artists="A-Mei",
        release_date="1997-06-07",
        track_ids=["track-a", "track-b"],
    )
    for number, name, tid in [(10, "Bad Boy", "track-a"), (11, "BAD BOY", "track-b")]:
        _add_local_album(
            conn,
            album_id=number,
            album_name=name,
            artist_id=1,
            artist_name="A-Mei",
            spotify_album_id="release",
            spotify_track_id=tid,
        )
    conn.execute(
        "INSERT INTO artist_identity_external_ids(artist_id,provider,external_id,evidence_type) VALUES(1,'spotify','stable-id','user_confirmed')"
    )
    persist_album_artists(
        conn, {"id": "release", "artists": [{"id": "stable-id", "name": "Renamed, Artist"}]}
    )
    _prepare_standalone_projects(conn)
    raw = {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
        for table in ("plays", "tracks", "track_artists")
    }
    plan = plan_album_project_auto_merges(conn)
    assert len(plan.candidates) == 1
    apply_album_project_auto_merge_plan(conn, plan)
    assert (
        conn.execute(
            "SELECT album_artist_key FROM album_projects WHERE primary_album_id=?",
            (plan.candidates[0].primary_album_id,),
        ).fetchone()[0]
        == "canonical:1"
    )
    assert {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
        for table in raw
    } == raw
    conn.close()


def test_track_comparison_display_never_substitutes_album_artists(database):
    from backend.core.version_merge import _lookup_track_names

    conn = connect(database)
    artists(conn)
    conn.execute(
        "INSERT INTO tracks(track_id,track_name,artist_id,spotify_track_id) VALUES(10000,'Local Track',10000,'local-track')"
    )
    conn.execute("INSERT INTO track_artists(track_id,artist_id,role) VALUES(10000,10000,'primary')")
    conn.execute(
        "INSERT INTO spotify_track_owners(spotify_track_id,track_id) VALUES('local-track',10000)"
    )
    upsert_album_batch(conn, [album()])
    conn.executemany(
        "INSERT INTO spotify_track_meta(spotify_track_id,track_name,spotify_album_id) VALUES(?,?,?)",
        [
            ("local-track", "Local Track", "album-test"),
            ("unknown-track", "Unknown Track", "album-test"),
        ],
    )
    result = _lookup_track_names(conn, {"local-track", "unknown-track"})
    assert result["local-track"][1] == "Earth, Wind & Fire"
    assert "Other" not in result["local-track"][1]
    assert result["unknown-track"][1] == ""
    conn.close()

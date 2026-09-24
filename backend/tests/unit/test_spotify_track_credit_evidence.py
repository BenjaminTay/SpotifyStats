from __future__ import annotations

import sqlite3

import pytest

from backend.core.db import SCHEMA
from backend.core.migrations import migrate_080
from backend.domains.metadata.spotify_refresh import (
    refresh_missing_spotify_metadata,
    upsert_track_batch,
)
from backend.domains.metadata.spotify_track_credits import (
    InvalidSpotifyCreditsError,
    audit_track_credit_evidence,
    credit_evidence_coverage,
    save_track_credit_evidence,
    select_missing_credit_evidence,
)
from scripts.backfill_spotify_track_artist_credits import _eligible_ids, run_backfill

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def _track(artists: list[dict] | None = None) -> dict:
    return {
        "id": "spotify-track-1",
        "name": "合作歌曲",
        "duration_ms": 180000,
        "artists": artists
        or [
            {"id": "spotify-artist-1", "name": "主艺人"},
            {"id": "spotify-artist-2", "name": "合作艺人"},
        ],
        "album": {"id": "spotify-album-1"},
    }


def _seed_track(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, '主艺人')")
    conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (2, '合作艺人')")
    conn.execute(
        """INSERT INTO tracks(track_id, track_name, artist_id, spotify_track_id)
           VALUES (1, '合作歌曲', 1, 'spotify-track-1')"""
    )
    conn.execute(
        """INSERT INTO spotify_track_owners(spotify_track_id, track_id)
           VALUES ('spotify-track-1', 1)"""
    )
    conn.execute(
        """INSERT INTO spotify_track_meta(spotify_track_id, track_name)
           VALUES ('spotify-track-1', '合作歌曲')"""
    )


def test_evidence_round_trip_idempotence_change_and_invalid_lkg() -> None:
    conn = _conn()
    _seed_track(conn)
    assert save_track_credit_evidence(conn, _track()) == "observed"
    assert save_track_credit_evidence(conn, _track()) == "unchanged"
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_credit_events").fetchone()[0] == 1
    rows = conn.execute(
        """SELECT spotify_artist_id, credited_name, credit_order
           FROM spotify_track_artist_credits ORDER BY credit_order"""
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("spotify-artist-1", "主艺人", 0),
        ("spotify-artist-2", "合作艺人", 1),
    ]
    changed = _track(
        [
            {"id": "spotify-artist-2", "name": "合作艺人"},
            {"id": "spotify-artist-1", "name": "主艺人"},
        ]
    )
    assert save_track_credit_evidence(conn, changed) == "changed"
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_credit_events").fetchone()[0] == 2
    with pytest.raises(InvalidSpotifyCreditsError, match="artist_id_duplicate"):
        save_track_credit_evidence(
            conn,
            _track(
                [
                    {"id": "spotify-artist-1", "name": "主艺人"},
                    {"id": "spotify-artist-1", "name": "重复"},
                ]
            ),
        )
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_artist_credits").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_credit_events").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM track_artists").fetchone()[0] == 0
    conn.close()


def test_meta_upsert_keeps_child_evidence_and_reports_invalid_response() -> None:
    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track())
    outcomes: list[tuple[str, str, str | None]] = []
    assert upsert_track_batch(conn, [{**_track(), "artists": []}], credit_outcomes=outcomes) == 1
    assert outcomes == [("spotify-track-1", "failed", "artists_missing_or_empty")]
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_artist_credits").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_credit_events").fetchone()[0] == 1
    conn.close()


def test_database_failure_rolls_back_changed_evidence_and_metadata() -> None:
    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track())
    conn.commit()
    old_signature = conn.execute(
        "SELECT credit_signature FROM spotify_track_credit_sets"
    ).fetchone()[0]
    conn.execute(
        """CREATE TRIGGER reject_credit_update
           BEFORE INSERT ON spotify_track_artist_credits
           WHEN NEW.credited_name='注入失败'
           BEGIN SELECT RAISE(ABORT, 'injected_credit_failure'); END"""
    )
    conn.commit()
    changed = _track([{"id": "spotify-artist-1", "name": "注入失败"}])
    changed["name"] = "不应提交的歌曲名"
    with pytest.raises(sqlite3.IntegrityError, match="injected_credit_failure"):
        upsert_track_batch(conn, [changed], credit_outcomes=[])
    assert (
        conn.execute("SELECT credit_signature FROM spotify_track_credit_sets").fetchone()[0]
        == old_signature
    )
    assert conn.execute("SELECT track_name FROM spotify_track_meta").fetchone()[0] == "合作歌曲"
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_artist_credits").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_credit_events").fetchone()[0] == 1
    conn.close()


def test_missing_selector_coverage_and_owner_comparison() -> None:
    conn = _conn()
    _seed_track(conn)
    assert select_missing_credit_evidence(conn) == ["spotify-track-1"]
    assert credit_evidence_coverage(conn) == {
        "status": "missing",
        "eligible": 1,
        "stored": 0,
        "missing": 1,
    }
    save_track_credit_evidence(conn, _track())
    conn.execute(
        """INSERT INTO artist_identity_external_ids(
               artist_id, provider, external_id, evidence_type, verified)
           VALUES (1, 'spotify', 'spotify-artist-1', 'test', 1),
                  (2, 'spotify', 'spotify-artist-2', 'test', 1)"""
    )
    report = audit_track_credit_evidence(conn)
    assert report["eligible"] == sum(report["counts"].values()) == 1
    assert report["counts"] == {"provider_additions": 1}
    assert report["rows"][0]["provider_only_artist_ids"] == [2]
    assert report["rows"][0]["local_only_artist_ids"] == []
    assert credit_evidence_coverage(conn)["status"] == "ready"
    conn.close()


def test_migration_80_is_additive_and_repeatable() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE spotify_track_meta(spotify_track_id TEXT PRIMARY KEY)")
    migrate_080(conn)
    migrate_080(conn)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "spotify_track_credit_sets",
        "spotify_track_artist_credits",
        "spotify_track_credit_events",
    } <= tables
    conn.close()


def test_backfill_retries_missing_and_repeat_fetch_has_no_new_event() -> None:
    conn = _conn()
    _seed_track(conn)

    class Provider:
        def get_cc_token(self) -> str:
            return "test-token"

        def get_tracks(self, ids: list[str], token: str) -> dict:
            assert ids == ["spotify-track-1"]
            assert token == "test-token"
            return {"tracks": [_track()]}

    provider = Provider()
    assert _eligible_ids(conn, "", 0) == ["spotify-track-1"]
    first = run_backfill(conn, provider, ["spotify-track-1"], run_id="first")
    assert first["counts"] == {
        "requested": 1,
        "observed": 1,
        "changed": 0,
        "unchanged": 0,
        "failed": 0,
    }
    assert _eligible_ids(conn, "", 0) == []
    assert _eligible_ids(conn, "", 0, refresh_existing=True) == ["spotify-track-1"]
    second = run_backfill(conn, provider, ["spotify-track-1"], run_id="repeat")
    assert second["counts"]["unchanged"] == 1
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_credit_events").fetchone()[0] == 1
    conn.close()


def test_backfill_invalid_response_keeps_last_good_evidence() -> None:
    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track())
    conn.commit()

    class Provider:
        def get_cc_token(self) -> str:
            return "test-token"

        def get_tracks(self, ids: list[str], token: str) -> dict:
            return {"tracks": [{**_track(), "artists": []}]}

    result = run_backfill(conn, Provider(), ["spotify-track-1"], run_id="bad")
    assert result["counts"]["failed"] == 1
    assert result["failures"] == [
        {"spotify_track_id": "spotify-track-1", "reason": "artists_missing_or_empty"}
    ]
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_artist_credits").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_credit_events").fetchone()[0] == 1
    conn.close()


def test_backfill_missing_credentials_does_not_write_evidence() -> None:
    conn = _conn()
    _seed_track(conn)

    class Provider:
        def get_cc_token(self) -> None:
            return None

        def get_tracks(self, ids: list[str], token: str) -> dict:
            raise AssertionError("missing credentials must not fetch tracks")

    result = run_backfill(conn, Provider(), ["spotify-track-1"], run_id="no-token")
    assert result["counts"]["failed"] == 1
    assert result["failures"][0]["reason"] == "spotify_credentials_missing"
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_credit_sets").fetchone()[0] == 0
    conn.close()


def test_provider_artist_name_only_remains_unresolved() -> None:
    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track())
    report = audit_track_credit_evidence(conn)
    assert report["counts"] == {"unresolved_provider_artist": 1}
    assert report["rows"][0]["link_candidates"] == {
        "spotify-artist-1": [1],
        "spotify-artist-2": [2],
    }
    assert report["rows"][0]["provider_only_artist_ids"] is None
    assert report["rows"][0]["local_only_artist_ids"] is None
    assert conn.execute("SELECT COUNT(*) FROM track_credit_overrides").fetchone()[0] == 0
    conn.close()


def test_provider_artist_identity_conflict_has_no_member_difference() -> None:
    conn = _conn()
    _seed_track(conn)
    save_track_credit_evidence(conn, _track())
    conn.execute(
        """INSERT INTO artist_identity_external_ids(
               artist_id, provider, external_id, evidence_type, verified)
           VALUES (1, 'spotify', 'spotify-artist-1', 'test', 1),
                  (2, 'spotify', 'spotify-artist-1', 'test', 1)"""
    )
    report = audit_track_credit_evidence(conn)
    assert report["counts"] == {"artist_identity_conflict": 1}
    assert report["rows"][0]["provider_only_artist_ids"] is None
    assert report["rows"][0]["local_only_artist_ids"] is None
    conn.close()


@pytest.mark.parametrize(
    ("drop_owner", "skip_evidence", "expected_status"),
    [
        (True, False, "owner_conflict"),
        (False, True, "provider_incomplete"),
    ],
)
def test_incomplete_owner_or_evidence_has_no_member_difference(
    drop_owner: bool, skip_evidence: bool, expected_status: str
) -> None:
    conn = _conn()
    _seed_track(conn)
    if drop_owner:
        conn.execute("DELETE FROM spotify_track_owners WHERE spotify_track_id='spotify-track-1'")
    if not skip_evidence:
        save_track_credit_evidence(conn, _track())
    report = audit_track_credit_evidence(conn)
    assert report["counts"] == {expected_status: 1}
    assert report["rows"][0]["provider_only_artist_ids"] is None
    assert report["rows"][0]["local_only_artist_ids"] is None
    conn.close()


def test_refresh_partial_track_batch_reports_missing_evidence() -> None:
    conn = _conn()
    conn.execute("ALTER TABLE artists ADD COLUMN spotify_artist_id TEXT")
    conn.execute("ALTER TABLE artists ADD COLUMN image_url TEXT")
    conn.execute("ALTER TABLE albums ADD COLUMN spotify_album_id TEXT")
    conn.execute("ALTER TABLE albums ADD COLUMN image_url TEXT")
    _seed_track(conn)
    conn.execute(
        "INSERT INTO tracks(track_id, track_name, artist_id, spotify_track_id) "
        "VALUES (2, '缺失响应', 1, 'spotify-track-2')"
    )

    class Provider:
        def get_tracks(self, ids: list[str], token: str) -> dict:
            assert set(ids) == {"spotify-track-1", "spotify-track-2"}
            return {"tracks": [{**_track(), "album": {}}, None]}

        def get_albums(self, ids: list[str], token: str) -> dict:
            return {"albums": []}

        def get_artists_by_ids(self, ids: list[str], token: str) -> dict:
            return {"artists": []}

    report = refresh_missing_spotify_metadata(conn, Provider(), "test-token")
    assert report.credit_evidence_requested == 2
    assert report.credit_evidence_observed == 1
    assert report.credit_evidence_failed == 1
    assert report.credit_evidence_missing == 1
    assert "track_credit_evidence_partial" in report.errors
    assert credit_evidence_coverage(conn)["stored"] == 1
    conn.close()

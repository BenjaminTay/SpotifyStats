"""Historical release-evidence recovery and maintenance use one Album response."""

import sqlite3

import pytest

from backend.core.db import SCHEMA
from backend.domains.metadata.release_dates import (
    release_evidence_inventory,
    select_missing_release_evidence_ids,
    sync_project_release_precisions,
)
from backend.domains.metadata.spotify_album_credits import persist_album_artists
from scripts.backfill_spotify_release_dates import (
    apply_observations,
    build_manifest,
    evidence_fingerprint,
    fetch_observations,
    online_backup,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA)
    yield c
    c.close()


def album(sid="s", raw="2024-02-29", precision="day", artists=None):
    return {
        "id": sid,
        "name": "Synthetic",
        "album_type": "album",
        "release_date": raw,
        "release_date_precision": precision,
        "artists": artists if artists is not None else [{"id": "a", "name": "Artist"}],
    }


def seed(c, sid="s", raw="2024-01-01", precision=None, name="Synthetic", referenced=True):
    c.execute(
        "INSERT INTO spotify_album_meta(spotify_album_id,album_name,release_date,release_date_precision,image_url,total_tracks,track_list) VALUES (?,?,?,?, 'cover',1,'[\"track\"]')",
        (sid, name, raw, precision),
    )
    if referenced:
        c.execute(
            "INSERT INTO spotify_track_meta(spotify_track_id,spotify_album_id,track_name) VALUES (?,?,'Track')",
            ("track-" + sid, sid),
        )


def project(c, manual=0, raw="2024-01-01", precision=None):
    c.execute("INSERT INTO artists(artist_id,artist_name) VALUES(1,'Artist')")
    c.execute("INSERT INTO albums(album_id,album_name,artist_id) VALUES(1,'Synthetic',1)")
    c.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES(1,'s','synthetic',1)"
    )
    c.execute(
        "INSERT INTO album_projects(project_id,canonical_name,artist_id,primary_album_id,release_date,release_date_precision,is_manual) VALUES(1,'Synthetic',1,1,?,?,?)",
        (raw, precision, manual),
    )


def test_selector_recovers_legacy_but_coarse_confirmed_and_review_are_terminal(conn):
    for sid, raw, precision in [
        ("legacy", "2024-01-01", None),
        ("year", "2024", "year"),
        ("month", "2024-02", "month"),
        ("conflict", "2024-01-01", None),
        ("artist_review", "2024-02-29", "day"),
        ("unresolved", "2024", "year"),
    ]:
        seed(conn, sid, raw, precision)
        if sid != "legacy":
            persist_album_artists(conn, album(sid))
    seed(conn, "orphan", referenced=False)
    apply_observations(conn, [album("conflict", "2025-01-01")], album_ids=["conflict"])
    persist_album_artists(
        conn, album("artist_review", artists=[{"id": "different", "name": "Artist"}])
    )
    conn.execute(
        "UPDATE spotify_album_artist_credits SET spotify_artist_id=NULL WHERE spotify_album_id='unresolved'"
    )
    assert select_missing_release_evidence_ids(conn) == ["legacy"]
    inventory = release_evidence_inventory(conn)
    reasons = {r["id"]: r["reasons"] for r in inventory["items"]}
    assert reasons["year"] == ["date_precision_year"]
    assert reasons["conflict"] == ["date_review_required"]
    assert reasons["artist_review"] == ["artist_review_required"]
    assert reasons["unresolved"] == ["date_precision_year", "artist_ids_unconfirmed"]
    assert inventory["orphan_cached_ids"] == ["orphan"]


def test_missing_album_selector_includes_semantic_gap_without_structural_refetch(conn):
    from backend.domains.metadata.spotify_refresh import select_missing_album_ids

    seed(conn)
    assert select_missing_album_ids(conn) == ["s"]
    assert select_missing_album_ids(conn, include_release_evidence=False) == []
    apply_observations(conn, [album()], album_ids=["s"])
    assert select_missing_album_ids(conn) == []


def test_same_response_recovers_legacy_project_anchor_without_track_or_membership_change(conn):
    seed(conn)
    project(conn)
    seed(conn, "side", raw="2024-03-01", precision="day", name="Synthetic (Track by Track)")
    conn.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES(1,'side','synthetic',1)"
    )
    report = apply_observations(conn, [album()], album_ids=["s"])
    assert report["evidence_outcomes"] == {"s": {"date": "accepted", "artists": "observed"}}
    assert report["project_precision_changes"] == 1
    assert conn.execute(
        "SELECT release_date,release_date_precision FROM album_projects"
    ).fetchone() == ("2024-02-29", "day")
    assert conn.execute("SELECT COUNT(*) FROM spotify_track_meta").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM album_spotify_links").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM album_project_tracks").fetchone()[0] == 0
    repeat = apply_observations(conn, [album()], album_ids=["s"])
    assert repeat["evidence_outcomes"] == {"s": {"date": "unchanged", "artists": "unchanged"}}
    assert repeat["project_precision_changes"] == 0
    assert conn.execute("SELECT COUNT(*) FROM spotify_album_date_observations").fetchone()[0] == 1


@pytest.mark.parametrize(
    "manual,raw,precision", [(1, "2024-01-01", None), (0, "2024-01-01", "day")]
)
def test_manual_or_previously_confirmed_project_anchor_is_not_corrected(
    conn, manual, raw, precision
):
    seed(conn)
    project(conn, manual, raw, precision)
    apply_observations(conn, [album()], album_ids=["s"])
    assert conn.execute("SELECT release_date FROM album_projects").fetchone()[0] == raw


def test_multiple_same_name_sources_never_choose_a_project_anchor(conn):
    seed(conn)
    project(conn)
    seed(conn, "other", raw="2024-03-01", precision="day")
    conn.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES(1,'other','synthetic',1)"
    )
    apply_observations(conn, [album()], album_ids=["s"])
    assert conn.execute(
        "SELECT release_date,release_date_precision FROM album_projects"
    ).fetchone() == ("2024-01-01", None)


def test_evidence_only_regular_refresh_does_not_fetch_track_pages_and_invalidates(
    conn, monkeypatch
):
    import backend.providers.spotify.album_tracks as tracks
    from backend.core import cache_manager
    from backend.domains.metadata.spotify_refresh import upsert_album_batch

    seed(conn)
    project(conn)
    conn.commit()
    monkeypatch.setattr(
        tracks, "fetch_complete_album_tracks", lambda *_: pytest.fail("no catalogue fetch")
    )
    invalidated = []
    monkeypatch.setattr(cache_manager, "invalidate_many", lambda *args: invalidated.extend(args))
    assert upsert_album_batch(conn, [album()], evidence_only=True) == 1
    assert {"billboard", "analysis", "db", "search"} <= set(invalidated)
    assert conn.execute(
        "SELECT release_date,release_date_precision FROM album_projects"
    ).fetchone() == ("2024-02-29", "day")


def test_date_and_artist_rejections_are_separate_and_whole_batch_rolls_back(conn):
    seed(conn)
    report = apply_observations(conn, [album(artists=[])], album_ids=["s"])
    assert report["evidence_outcomes"]["s"] == {"date": "accepted", "artists": "rejected"}
    conn.commit()
    seed(conn, "other")
    conn.commit()
    conn.execute(
        "CREATE TRIGGER reject_artist BEFORE INSERT ON spotify_album_artist_credits BEGIN SELECT RAISE(ABORT,'storage failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="storage failure"):
        apply_observations(conn, [album("other")], album_ids=["other"])
    assert (
        conn.execute(
            "SELECT release_date_precision FROM spotify_album_meta WHERE spotify_album_id='other'"
        ).fetchone()[0]
        is None
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM spotify_album_credit_sets WHERE spotify_album_id='other'"
        ).fetchone()[0]
        == 0
    )


def test_manifest_batches_and_drift_fence(conn):
    for index in range(201):
        seed(conn, f"s{index:03}")
    manifest = build_manifest(conn)
    assert [len(b["album_ids"]) for b in manifest["batches"]] == [200, 1]
    batch = manifest["batches"][0]
    conn.execute("UPDATE spotify_album_meta SET release_date='2025' WHERE spotify_album_id='s000'")
    with pytest.raises(ValueError, match="drifted"):
        apply_observations(
            conn,
            [album("s000")],
            album_ids=batch["album_ids"],
            expected_fingerprint=batch["input_fingerprint"],
        )
    # An explicit rebase follows review of changed evidence, never automatic bypass.
    expected = evidence_fingerprint(conn, batch["album_ids"])
    report = apply_observations(
        conn,
        [album("s000", "2025-02-28")],
        album_ids=batch["album_ids"],
        expected_fingerprint=expected,
    )
    assert report["outcomes"]["s000"] == "accepted"
    assert len(report["missing_ids"]) == 199


def test_fetch_reports_partial_failure_and_resume_never_refetches_successful_ids():
    class Provider:
        def __init__(self):
            self.calls = []

        def get_albums(self, ids, token):
            self.calls.append(ids)
            return {"albums": [album(sid) for sid in ids if sid != "failed"]}

    provider = Provider()
    first = fetch_observations(provider, "redacted", ["s", "failed"])
    assert first["failures"] == {"failed": "album_missing_from_response"}
    assert list(first["observations"][0]) == [
        "id",
        "name",
        "album_type",
        "release_date",
        "release_date_precision",
        "artists",
    ]
    second = fetch_observations(provider, "redacted", ["s", "failed"], existing=first)
    assert provider.calls == [["failed", "s"], ["failed"]]
    assert second["observations"] == first["observations"]
    with pytest.raises(ValueError, match="different explicit batch"):
        fetch_observations(provider, "redacted", ["s"], existing=first)


def test_online_backup_retains_live_wal_data_and_never_overwrites(tmp_path):
    source, destination = tmp_path / "live.db", tmp_path / "copy.db"
    conn = sqlite3.connect(source)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE evidence(id TEXT)")
    conn.execute("INSERT INTO evidence VALUES('committed-in-wal')")
    conn.commit()
    online_backup(source, destination)
    with sqlite3.connect(destination) as copy:
        assert copy.execute("SELECT * FROM evidence").fetchone() == ("committed-in-wal",)
    with pytest.raises(ValueError, match="not already exist"):
        online_backup(source, destination)
    conn.close()


def bind(c, sid="s", *, primary=1, confidence=1, evidence="content_superset"):
    c.execute(
        """INSERT INTO album_project_external_ids(provider,external_album_id,project_id,
           evidence_type,confidence,is_primary) VALUES('spotify',?,1,?,?,?)""",
        (sid, evidence, confidence, primary),
    )


def test_project_primary_binding_wins_over_container_and_does_not_require_same_name(conn):
    from backend.domains.metadata.release_dates import release_anchor_sources

    seed(conn)
    project(conn)
    seed(conn, "official", raw="2024-02-29", precision="day", name="Synthetic (Official Superset)")
    bind(conn, "official")
    before = conn.execute("SELECT * FROM album_project_external_ids").fetchall()
    rows = release_anchor_sources(conn, 1, project_id=1)
    assert len(rows) == 1
    assert rows[0] == {
        "spotify_album_id": "official",
        "album_name": "Synthetic (Official Superset)",
        "release_date": "2024-02-29",
        "release_date_precision": "day",
        "confidence": 1.0,
        "project_bound": True,
    }
    assert sync_project_release_precisions(conn, ["official"]) == 1
    assert conn.execute(
        "SELECT release_date,release_date_precision FROM album_projects"
    ).fetchone() == ("2024-02-29", "day")
    assert conn.execute("SELECT * FROM album_project_external_ids").fetchall() == before
    assert conn.execute("SELECT COUNT(*) FROM album_spotify_links").fetchone()[0] == 1


def test_explicit_edition_never_borrows_project_primary_source(conn):
    from backend.domains.metadata.release_dates import release_anchor_sources

    seed(conn, raw="2024-02-29", precision="day")
    project(conn)
    seed(conn, "primary", raw="2024-03-01", precision="day", name="Synthetic (Expanded)")
    bind(conn, "primary")
    ordinary = release_anchor_sources(conn, 1, project_id=1)
    edition = release_anchor_sources(conn, 1, project_id=1, explicit_edition=True)
    assert [r["spotify_album_id"] for r in ordinary] == ["primary"]
    assert [(r["spotify_album_id"], r["project_bound"]) for r in edition] == [("s", False)]
    # The member's existing binding can authenticate a compilation source,
    # without making a differently named primary source its release anchor.
    bind(conn, "s", primary=0, evidence="multi_artist_compilation")
    assert release_anchor_sources(conn, 1, project_id=1, explicit_edition=True)[0]["project_bound"]


def test_nonprimary_bindings_select_matching_name_or_unique_binding_and_keep_ambiguity(conn):
    from backend.domains.metadata.release_dates import release_anchor_sources

    seed(conn)
    project(conn)
    seed(conn, "different", name="Synthetic (Different Version)")
    bind(conn, "different", primary=0, evidence="soundtrack_catalog")
    assert release_anchor_sources(conn, 1, project_id=1)[0]["spotify_album_id"] == "different"
    bind(conn, "s", primary=0)
    assert [r["spotify_album_id"] for r in release_anchor_sources(conn, 1, project_id=1)] == ["s"]
    conn.execute(
        "UPDATE spotify_album_meta SET album_name='Another Version' WHERE spotify_album_id='s'"
    )
    assert release_anchor_sources(conn, 1, project_id=1) == []


def test_low_confidence_binding_does_not_approve_a_new_source(conn):
    from backend.domains.metadata.release_dates import release_anchor_sources

    seed(conn)
    project(conn)
    seed(conn, "unapproved", name="Different")
    bind(conn, "unapproved", confidence=0.5)
    assert [
        (r["spotify_album_id"], r["project_bound"])
        for r in release_anchor_sources(conn, 1, project_id=1)
    ] == [("s", False)]


def test_multiple_consistent_sources_can_correct_legacy_but_conflicting_pair_never_votes(conn):
    seed(conn, raw="2024-02-29", precision="day")
    project(conn)
    seed(conn, "other", raw="2024-02-29", precision="day")
    conn.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES(1,'other','synthetic',1)"
    )
    assert sync_project_release_precisions(conn, ["s"]) == 1
    assert conn.execute(
        "SELECT release_date,release_date_precision FROM album_projects"
    ).fetchone() == ("2024-02-29", "day")
    conn.execute("UPDATE album_projects SET release_date='2024-01-01',release_date_precision=NULL")
    conn.execute(
        "UPDATE spotify_album_meta SET release_date='2024-03-01' WHERE spotify_album_id='other'"
    )
    assert sync_project_release_precisions(conn, ["s"]) == 0
    assert conn.execute(
        "SELECT release_date,release_date_precision FROM album_projects"
    ).fetchone() == ("2024-01-01", None)


def test_inventory_includes_bound_and_native_ids_and_ignores_other_providers(conn):
    seed(conn)
    project(conn)
    conn.execute("ALTER TABLE albums ADD COLUMN spotify_album_id TEXT")
    conn.execute("UPDATE albums SET spotify_album_id='native-only' WHERE album_id=1")
    bind(conn, "bound-only")
    conn.execute(
        "INSERT INTO album_project_external_ids(provider,external_album_id,project_id) VALUES('other','not-a-spotify-id',1)"
    )
    items = {r["id"]: r for r in release_evidence_inventory(conn)["items"]}
    assert set(items) == {"s", "native-only", "bound-only"}
    assert items["native-only"]["references"] == ["albums"]
    assert items["bound-only"]["references"] == ["album_project_external_ids"]
    assert "cache_missing" in items["bound-only"]["retryable_reasons"]
    manifest = build_manifest(conn)
    assert manifest["batches"][0]["album_ids"] == ["bound-only", "native-only", "s"]


def test_project_binding_changes_are_included_in_replay_fence(conn):
    seed(conn)
    project(conn)
    seed(conn, "official", name="Expanded")
    bind(conn, "official")
    before = evidence_fingerprint(conn, ["official"])
    conn.execute(
        "UPDATE album_project_external_ids SET confidence=.5 WHERE external_album_id='official'"
    )
    assert evidence_fingerprint(conn, ["official"]) != before
    with pytest.raises(ValueError, match="drifted"):
        apply_observations(
            conn, [album("official")], album_ids=["official"], expected_fingerprint=before
        )

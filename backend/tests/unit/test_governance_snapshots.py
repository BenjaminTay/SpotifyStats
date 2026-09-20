"""Governance duration equivalence, precise invalidation and read boundaries."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.core import config, db
from backend.domains.metadata import governance_facts
from backend.domains.metadata import governance_store as store
from backend.domains.metadata.artist_languages import build_primary_artist_ms
from backend.domains.metadata.governance_revision import (
    GovernanceRevisionUnavailableError,
    family_revision,
    install_revision_tracking,
)
from backend.services import governance_snapshot_service as service

pytestmark = pytest.mark.unit


@pytest.fixture
def governance(tmp_path, monkeypatch):
    from backend.core.migrations import run_migrations

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "source.db"))
    monkeypatch.setattr(config, "SPOTIFY_STATS_GOVERNANCE_CACHE_PATH", str(tmp_path / "cache.db"))
    db.init_db()
    run_migrations()
    conn = db.get_db(readonly=False)
    conn.executemany(
        "INSERT INTO artists(artist_id,artist_name) VALUES(?,?)", [(1, "A"), (2, "Unknown")]
    )
    conn.executemany(
        "INSERT INTO tracks(track_id,track_name,artist_id) VALUES(?,?,?)",
        [(1, "Song", 1), (2, "Other", 2)],
    )
    for n, (track, ms) in enumerate([(1, 120000), (1, 12000), (2, 60000), (None, 30000)], 1):
        conn.execute(
            "INSERT INTO plays(ts,ts_date,ms_played,track_id,content_type,ts_year,ts_month,ts_week,ts_dow,ts_hour,platform) VALUES(?,?,?,?, 'audio',2024,1,1,0,0,'test')",
            (f"2024-01-01T00:0{n}:00Z", "2024-01-01", ms, track),
        )
    conn.commit()
    db._load_plays_cached.cache_clear()
    yield conn
    conn.close()
    db._load_plays_cached.cache_clear()


@pytest.mark.parametrize(
    "case",
    [
        "default",
        "empty",
        "unknown",
        "unattributed",
        "identity",
        "credit",
        "no_genre",
        "no_language",
        "all_media",
        "no_merge",
        "threshold",
    ],
)
def test_duration_matches_original_every_artist(governance, case):
    conn = governance
    filters = {}
    if case == "empty":
        conn.execute("DELETE FROM plays")
    if case == "unknown":
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM artists WHERE artist_id=2")
    if case == "unattributed":
        conn.execute(
            "INSERT INTO artist_metadata_attribution_overrides(track_id,artist_id,reason) VALUES(1,NULL,?)",
            ("test",),
        )
    if case == "identity":
        conn.execute(
            "INSERT INTO artist_identity_aliases(alias_artist_id,canonical_artist_id,reason) VALUES(1,2,'manual')"
        )
    if case == "credit":
        conn.execute("INSERT INTO track_artists(track_id,artist_id,role) VALUES(1,2,'featured')")
    if case == "all_media":
        filters["music_only"] = False
    if case == "no_merge":
        filters["merge_enabled"] = False
    if case == "threshold":
        filters.update(min_ms=150000, dynamic_threshold=False, max_merge_gap_minutes=1)
    conn.commit()
    params = service.parameters(conn, filters)
    old, excluded = build_primary_artist_ms(conn, db.load_plays(conn, **params))
    new = governance_facts.build_facts(conn, params)
    assert new == {"artist_ms": {str(k): v for k, v in old.items()}, "excluded_ms": excluded}


def test_joint_build_and_four_concurrent_exact(governance, monkeypatch):
    calls = []
    original = governance_facts.build_facts
    monkeypatch.setattr(governance_facts, "build_facts", lambda *a: calls.append(1) or original(*a))

    def build(_):
        c = db.get_db()
        try:
            return service.ensure(c, families=["genre_coverage", "language_coverage"])
        finally:
            c.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(build, range(4)))
    assert len(calls) == 1
    assert sum(r["primary_artist_ms_builds"] for r in results) == 1
    assert service.read(governance, "genre_coverage")["snapshot"]["status"] == "ready"
    assert service.read(governance, "language_coverage")["unknown_pct"] == 100
    assert db._load_plays_cached.cache_info().currsize == 0


def test_precise_revision_and_rollback(governance):
    c = governance

    def revisions():
        return {
            f: family_revision(c, f)
            for f in ("primary_artist_ms", "genre_coverage", "language_coverage", "import_health")
        }

    before = revisions()
    c.execute(
        "INSERT INTO artist_genre_overrides(artist_name,normalized_genres_json) VALUES('A','[\"pop\"]')"
    )
    assert revisions()["genre_coverage"] != before["genre_coverage"]
    assert revisions()["language_coverage"] == before["language_coverage"]
    assert revisions()["primary_artist_ms"] == before["primary_artist_ms"]
    c.rollback()
    assert revisions() == before
    c.execute(
        "INSERT INTO artist_language_sources(artist_id,classification,origin,source_key,status) VALUES(1,'instrumental','manual','test','approved')"
    )
    assert revisions()["genre_coverage"] == before["genre_coverage"]
    assert revisions()["language_coverage"] != before["language_coverage"]
    c.rollback()
    c.execute("UPDATE artists SET artist_name='Renamed' WHERE artist_id=1")
    assert revisions()["primary_artist_ms"] == before["primary_artist_ms"]
    c.rollback()
    c.execute("UPDATE plays SET ms_played=ms_played+1")
    assert all(revisions()[f] != before[f] for f in before)
    c.rollback()
    assert revisions() == before


@pytest.mark.parametrize("damage", ["counter", "marker", "schema"])
def test_missing_revision_requires_explicit_backfill(governance, damage):
    c = governance
    if damage == "counter":
        c.execute("DELETE FROM governance_source_revisions WHERE domain='plays'")
    elif damage == "marker":
        c.execute("DELETE FROM governance_revision_schema")
    else:
        c.execute("CREATE TABLE extra_schema(x)")
    c.commit()
    with pytest.raises(GovernanceRevisionUnavailableError):
        family_revision(c, "genre_coverage")
    with c:
        install_revision_tracking(c)
    assert family_revision(c, "genre_coverage")


def test_failed_build_keeps_lkg_and_no_lkg_is_unavailable(governance, monkeypatch):
    from fastapi import HTTPException

    service.ensure(governance, families=["genre_coverage"])
    before = service.read(governance, "genre_coverage")
    governance.execute("UPDATE plays SET ms_played=ms_played+1")
    governance.commit()

    def fail(*a):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(governance_facts, "build_facts", fail)
    with pytest.raises(RuntimeError):
        service.ensure(governance, families=["genre_coverage", "language_coverage"])
    stale = service.read(governance, "genre_coverage")
    assert stale["snapshot"]["freshness"] == "last_known_good"
    assert stale["snapshot"]["build_status"] == "failed"
    assert stale["snapshot"]["checked_at"] == before["snapshot"]["checked_at"]
    assert stale["known_pct"] == before["known_pct"]
    with pytest.raises(HTTPException) as e:
        service.read(governance, "language_coverage")
    assert e.value.status_code == 503 and e.value.detail["build_status"] == "failed"


def test_source_drift_rejects_publication(governance, monkeypatch):
    original = governance_facts.build_facts

    def drift(*a):
        result = original(*a)
        governance.execute("UPDATE plays SET ms_played=ms_played+1")
        governance.commit()
        return result

    monkeypatch.setattr(governance_facts, "build_facts", drift)
    with pytest.raises(ValueError, match="changed"):
        service.ensure(governance, families=["genre_coverage"])
    assert (
        store.read(
            "genre_coverage",
            service.request_key(governance, "genre_coverage", service.parameters(governance)),
        )
        is None
    )


def test_read_never_builds_writes_or_enqueues(governance, monkeypatch):
    from fastapi import HTTPException

    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )

    def forbidden(*a, **k):
        raise AssertionError("read side effect")

    monkeypatch.setattr(governance_facts, "build_facts", forbidden)
    monkeypatch.setattr(service, "enqueue_defaults", forbidden)
    monkeypatch.setattr(store, "publish", forbidden)
    before = governance.total_changes
    for public in (False, True):
        token = set_public_readonly_db_guard(public)
        try:
            with pytest.raises(HTTPException) as e:
                service.read(governance, "genre_coverage")
            assert e.value.detail["status"] == "unavailable"
        finally:
            reset_public_readonly_db_guard(token)
    assert governance.total_changes == before
    assert not store.path().exists()


def test_import_report_exact_and_live_failure(governance):
    from backend.domains.metadata.import_health import build_import_health_report

    expected = build_import_health_report(governance)
    service.ensure(governance, families=["import_health"])
    actual = service.read(governance, "import_health")
    for key in expected:
        assert actual[key] == expected[key]
    governance.execute(
        "UPDATE artist_identity_state SET rebuild_status='failed',last_error='current failure' WHERE state_id=1"
    )
    governance.commit()
    actual = service.read(governance, "import_health")
    assert actual["status"] == "failed" and not actual["summary"]["safe_to_use"]
    assert actual["runtime"]["errors"] == ["current failure"]


@pytest.mark.parametrize(
    "case",
    [
        "default",
        "empty",
        "unattributed",
        "genre_override",
        "language_override",
        "l3",
        "import_revision",
    ],
)
def test_all_result_fields_match_original_computations(governance, case):
    from types import SimpleNamespace

    from backend.api.artist_genre_metadata import _load_artist_play_hours
    from backend.domains.metadata.artist_genres import (
        AXIS_ORDER,
        compute_genre_axis_gaps,
        compute_genre_coverage,
        compute_genre_taxonomy_audit,
    )
    from backend.domains.metadata.artist_languages import compute_artist_language_distribution
    from backend.domains.metadata.import_health import build_import_health_report

    c = governance
    if case == "empty":
        c.execute("DELETE FROM plays")
    if case == "unattributed":
        c.execute(
            "INSERT INTO artist_metadata_attribution_overrides(track_id,artist_id,reason) VALUES(1,NULL,'test')"
        )
    if case == "genre_override":
        c.execute(
            "INSERT INTO artist_genre_overrides(artist_name,normalized_genres_json) VALUES('A','[\"pop\"]')"
        )
    if case == "language_override":
        c.execute(
            "INSERT INTO artist_language_sources(artist_id,classification,origin,source_key,status) VALUES(1,'instrumental','manual','test','approved')"
        )
    if case == "l3":
        c.execute(
            "UPDATE l3_album_attribution_revision_state SET status='building' WHERE state_id=1"
        )
    if case == "import_revision":
        c.execute("UPDATE plays SET ms_played=ms_played+123")
    c.commit()
    params = service.parameters(c)
    hours, excluded = _load_artist_play_hours(c, SimpleNamespace(**params))
    artist_ms, excluded_ms = build_primary_artist_ms(c, db.load_plays(c, **params))
    expected = {
        "genre_coverage": {
            **compute_genre_coverage(c, hours),
            "artist_count": len(hours),
            "total_hours": round(sum(hours.values()), 1),
            "excluded_unattributed_hours": excluded,
        },
        "genre_taxonomy": compute_genre_taxonomy_audit(c, hours),
        "genre_axis_gaps": {
            "axes": {a: compute_genre_axis_gaps(c, hours, axis=a) for a in AXIS_ORDER}
        },
        "language_coverage": compute_artist_language_distribution(
            c, artist_ms, excluded_ms=excluded_ms
        ),
        "import_health": build_import_health_report(c),
    }
    service.ensure(c)
    for family, payload in expected.items():
        actual = service.read(c, family)
        assert {
            k: v for k, v in actual.items() if k not in ("snapshot", "checked_at", "runtime")
        } == payload, (case, family)


def test_health_album_link_change_and_display_only_changes(governance):
    c = governance
    before = {
        f: family_revision(c, f)
        for f in ("primary_artist_ms", "genre_coverage", "language_coverage", "import_health")
    }
    c.execute("UPDATE artists SET image_url='local-image' WHERE artist_id=1")
    assert before == {f: family_revision(c, f) for f in before}
    c.rollback()
    c.execute("INSERT INTO albums(album_id,album_name,artist_id) VALUES(1,'Album',1)")
    c.execute(
        "INSERT INTO spotify_album_meta(spotify_album_id,album_name,album_type) VALUES('a','Album','single')"
    )
    c.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,play_count,evidence) VALUES(1,'a',1,'test')"
    )
    assert family_revision(c, "import_health") != before["import_health"]
    assert family_revision(c, "primary_artist_ms") == before["primary_artist_ms"]


def test_realtime_import_failure_not_overwritten_by_snapshot(governance):
    service.ensure(governance, families=["import_health"])
    governance.execute(
        "INSERT INTO playback_import_runs(run_id,requested_mode,status,error_code) VALUES('current','auto','recovery_blocked','source_missing')"
    )
    governance.commit()
    result = service.read(governance, "import_health")
    assert result["status"] == "failed"
    assert result["runtime"]["errors"] == ["source_missing"]


@pytest.mark.parametrize("state", ["exact", "lkg"])
def test_existing_publications_are_readonly_even_on_public_surface(governance, monkeypatch, state):
    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )

    service.ensure(governance, families=["genre_coverage", "language_coverage"])
    if state == "lkg":
        governance.execute("UPDATE plays SET ms_played=ms_played+1")
        governance.commit()

    def forbidden(*a, **k):
        raise AssertionError("read side effect")

    monkeypatch.setattr(governance_facts, "build_facts", forbidden)
    monkeypatch.setattr(service, "enqueue_defaults", forbidden)
    monkeypatch.setattr(store, "publish", forbidden)
    # Query-only connections reject accidental writes; sentinels reject maintenance.
    changes = governance.total_changes
    governance.execute("PRAGMA query_only=ON")
    token = set_public_readonly_db_guard(True)
    try:
        for family in ("genre_coverage", "language_coverage"):
            value = service.read(governance, family)
            assert value["snapshot"]["status"] == ("ready" if state == "exact" else "warming")
    finally:
        reset_public_readonly_db_guard(token)
    assert governance.total_changes == changes


def test_schema_backfill_refreshes_existing_table_foreign_key_dependencies(governance):
    from backend.domains.metadata.governance_revision import (
        family_revision,
        install_revision_tracking,
    )

    governance.execute("CREATE TABLE extra_parent(id INTEGER PRIMARY KEY)")
    governance.execute("CREATE TABLE extra_child(id INTEGER PRIMARY KEY)")
    governance.execute("INSERT INTO extra_child(id) VALUES(1)")
    with governance:
        install_revision_tracking(governance)
    governance.execute(
        "ALTER TABLE extra_child ADD COLUMN parent_id INTEGER REFERENCES extra_parent(id)"
    )
    with governance:
        install_revision_tracking(governance)
    before = family_revision(governance, "import_health")
    governance.execute("INSERT INTO extra_parent(id) VALUES(999)")
    before = family_revision(governance, "import_health")
    governance.execute("UPDATE extra_child SET parent_id=999 WHERE id=1")
    governance.commit()
    assert family_revision(governance, "import_health") != before

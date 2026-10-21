"""Project anchors use installed edition evidence, never a namesake's date."""

import sqlite3

import pytest

from backend.services.release_cycle_resolution import resolve_release_targets

pytestmark = pytest.mark.unit


@pytest.fixture
def source():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE artists(artist_id INTEGER,artist_name TEXT,spotify_artist_id TEXT);
        CREATE TABLE albums(album_id INTEGER,album_name TEXT,artist_id INTEGER);
        CREATE TABLE album_projects(project_id INTEGER,canonical_name TEXT,artist_id INTEGER,
          primary_album_id INTEGER,scope TEXT,release_date TEXT,release_date_precision TEXT,is_manual INTEGER);
        CREATE TABLE album_project_albums(project_id INTEGER,album_id INTEGER);
        CREATE TABLE spotify_album_meta(spotify_album_id TEXT,album_name TEXT,release_date TEXT,release_date_precision TEXT);
        CREATE TABLE album_spotify_links(album_id INTEGER,spotify_album_id TEXT,confidence REAL);
        CREATE TABLE spotify_album_credit_sets(spotify_album_id TEXT);
        CREATE TABLE spotify_album_artist_credits(spotify_album_id TEXT,spotify_artist_id TEXT,credited_name TEXT,credit_order INTEGER);
        INSERT INTO artists VALUES(1,'Main','main');
        INSERT INTO albums VALUES(10,'Album',1),(11,'Album Deluxe',1);
        INSERT INTO album_projects VALUES(100,'Album',1,10,'release','2026-01-02',NULL,0),
          (101,'Album',1,10,'composition','2026-01-02',NULL,0);
        INSERT INTO album_project_albums VALUES(100,10),(100,11),(101,10),(101,11);
        INSERT INTO spotify_album_meta VALUES('original','Album','2026-01-02','day'),
          ('deluxe','Album Deluxe','2026-02-06','day');
        INSERT INTO album_spotify_links VALUES(10,'original',1),(10,'deluxe',1),(11,'deluxe',1);
        INSERT INTO spotify_album_artist_credits VALUES('original','main','Main',0),('deluxe','main','Main',0);
    """)
    yield conn
    conn.close()


def resolve(conn, name="Album", level=2):
    return resolve_release_targets(conn, [{"artist_name": "Main", "album_name": name}], level)[0]


def test_primary_anchor_does_not_use_track_container_or_other_edition(source):
    target = resolve(source)
    assert target.reason is None
    assert (target.identity.project_id, target.release_date, target.source_album_id) == (
        100,
        "2026-01-02",
        "original",
    )
    assert resolve(source, level=3).identity.project_id == 101
    edition = resolve(source, "Album Deluxe")
    assert (edition.identity.project_id, edition.release_date, edition.source_album_id) == (
        100,
        "2026-02-06",
        "deluxe",
    )


@pytest.mark.parametrize(
    "raw,precision,reason",
    [
        ("2026-01-02", None, "release_day_unconfirmed"),
        ("2026", "year", "release_date_coarse"),
        ("2026-01", "month", "release_date_coarse"),
        ("2026-02-30", "day", "release_date_invalid"),
        ("2026", "day", "release_date_invalid"),
    ],
)
def test_precision_and_calendar_are_explicit(source, raw, precision, reason):
    source.execute(
        "UPDATE spotify_album_meta SET release_date=?,release_date_precision=? WHERE spotify_album_id='original'",
        (raw, precision),
    )
    assert resolve(source).reason == reason


def test_date_only_maintenance_does_not_bypass_artist_evidence(source):
    source.execute("DELETE FROM spotify_album_artist_credits WHERE spotify_album_id='original'")
    assert resolve(source).reason == "artist_identity_unconfirmed"


def test_known_day_from_unconfirmed_edition_is_a_source_failure(source):
    source.execute("DELETE FROM album_spotify_links WHERE spotify_album_id='original'")
    # The remaining Deluxe has a confirmed day, but cannot establish the
    # canonical edition's release anchor.
    assert resolve(source).reason == "release_source_unconfirmed"


def test_conflicting_same_edition_sources_are_not_chosen_by_order(source):
    source.execute("INSERT INTO spotify_album_meta VALUES('regional','Album','2026-01-01','day')")
    source.execute("INSERT INTO album_spotify_links VALUES(10,'regional',1)")
    source.execute("INSERT INTO spotify_album_artist_credits VALUES('regional','main','Main',0)")
    assert resolve(source).reason == "release_date_conflict"


def test_confirmed_or_manual_project_anchor_is_not_silently_changed(source):
    source.execute(
        "UPDATE album_projects SET release_date='2026-01-01',release_date_precision='day'"
    )
    assert resolve(source).reason == "release_date_conflict"
    source.execute("UPDATE album_projects SET release_date_precision=NULL,is_manual=1")
    assert resolve(source).reason == "release_date_conflict"


def test_unknown_entity_is_not_reported_as_a_date_failure(source):
    assert resolve(source, "Unknown").reason == "entity_not_found"


def test_ambiguous_member_alias_is_not_reported_as_missing_entity(source):
    source.execute(
        "INSERT INTO album_projects VALUES(102,'Different Project',1,11,'release',NULL,NULL,0)"
    )
    source.execute("INSERT INTO album_project_albums VALUES(102,11)")
    assert resolve(source, "Album Deluxe").reason == "release_ambiguous"


def test_existing_project_source_proof_supports_ensemble_without_artist_fanout(source):
    source.execute("UPDATE artists SET spotify_artist_id=NULL")
    assert resolve(source).reason == "artist_identity_unconfirmed"
    source.executescript("""
        CREATE TABLE album_project_external_ids(provider TEXT, external_album_id TEXT,
          project_id INTEGER,evidence_type TEXT,confidence REAL,is_primary INTEGER);
        INSERT INTO album_project_external_ids VALUES('spotify','original',100,'soundtrack_catalog',1,1);
    """)
    target = resolve(source)
    assert target.reason is None and target.source_album_id == "original"
    assert source.execute("SELECT spotify_artist_id FROM artists").fetchone()[0] is None
    source.execute("DELETE FROM spotify_album_artist_credits WHERE spotify_album_id='original'")
    assert resolve(source).reason == "artist_identity_unconfirmed"


@pytest.fixture
def advance_source(source):
    """Shared songs, provider releases and project membership are independent proofs."""
    source.execute("ALTER TABLE spotify_album_meta ADD COLUMN album_type TEXT")
    source.execute("UPDATE spotify_album_meta SET album_type='album'")
    source.executescript("""
        CREATE TABLE track_albums(track_id INTEGER,album_id INTEGER);
        INSERT INTO artists VALUES(2,'Other','other');
        INSERT INTO albums VALUES(20,'Lead Single',1),(21,'Lead Single',2);
        INSERT INTO album_projects VALUES(200,'Lead Single',1,20,'release','2025-12-01',NULL,0),
          (201,'Lead Single',2,21,'release','2024-01-01',NULL,0);
        INSERT INTO album_project_albums VALUES(200,20),(201,21);
        INSERT INTO track_albums VALUES(500,10),(500,20),(500,21);
        -- The globally first title match belongs to another artist. SQL LIMIT 1
        -- would silently put it into Main's clean-baseline calculation.
        INSERT INTO spotify_album_meta VALUES('lead-other','Lead Single','2024-01-01','day','single'),
          ('lead-main','Lead Single','2025-12-01','day','single');
        INSERT INTO spotify_album_artist_credits VALUES('lead-other','other','Other',0),
          ('lead-main','main','Main',0);
        INSERT INTO album_spotify_links VALUES(20,'lead-main',1),(21,'lead-other',1);
    """)
    source.commit()
    return source


def advance(conn, source_track_ids=(500,)):
    from backend.services.release_cycle_resolution import resolve_advance_singles

    return resolve_advance_singles(conn, resolve(conn), source_track_ids)


def test_advance_single_ignores_global_first_title_match_from_another_artist(advance_source):
    first = advance_source.execute(
        "SELECT spotify_album_id FROM spotify_album_meta WHERE album_name='Lead Single' LIMIT 1"
    ).fetchone()
    assert first[0] == "lead-other"
    assert advance(advance_source) == [
        {
            "single_name": "Lead Single",
            "release_date": "2025-12-01",
            "source_album_id": "lead-main",
        }
    ]


def test_advance_single_recovers_only_after_high_confidence_source_is_installed(advance_source):
    advance_source.execute(
        "UPDATE album_spotify_links SET confidence=.5 WHERE spotify_album_id='lead-main'"
    )
    assert advance(advance_source) == []
    advance_source.execute(
        "UPDATE album_spotify_links SET confidence=1 WHERE spotify_album_id='lead-main'"
    )
    assert [item["source_album_id"] for item in advance(advance_source)] == ["lead-main"]


def test_same_artist_single_date_conflict_is_not_decided_by_source_order(advance_source):
    advance_source.executescript("""
        INSERT INTO spotify_album_meta VALUES('lead-regional','Lead Single','2025-12-15','day','single');
        INSERT INTO spotify_album_artist_credits VALUES('lead-regional','main','Main',0);
        INSERT INTO album_spotify_links VALUES(20,'lead-regional',1);
    """)
    assert advance(advance_source) == []


@pytest.mark.parametrize(
    "raw,precision,album_type",
    [
        ("2025", "year", "single"),
        ("2025-12", "month", "single"),
        ("2025-12-01", None, "single"),
        ("2025-12-32", "day", "single"),
        ("2026-01-02", "day", "single"),
        ("2026-01-03", "day", "single"),
        ("2025-12-01", "day", "album"),
    ],
)
def test_advance_single_requires_a_confirmed_earlier_single_day(
    advance_source, raw, precision, album_type
):
    advance_source.execute(
        "UPDATE spotify_album_meta SET release_date=?,release_date_precision=?,album_type=? "
        "WHERE spotify_album_id='lead-main'",
        (raw, precision, album_type),
    )
    assert advance(advance_source) == []


def test_unshared_or_unowned_single_is_not_part_of_the_project_baseline(advance_source):
    advance_source.execute("DELETE FROM track_albums WHERE album_id=20")
    assert advance(advance_source) == []
    advance_source.execute("INSERT INTO track_albums VALUES(500,20)")
    assert len(advance(advance_source)) == 1
    # A same-name resolved project must actually own this shared local album.
    # The primary_album_id/title by itself is insufficient membership proof.
    advance_source.execute("DELETE FROM album_project_albums WHERE project_id=200 AND album_id=20")
    assert advance(advance_source) == []


def test_compare_readonly_chain_passes_installed_singles_and_never_calls_legacy_helper(
    advance_source, monkeypatch
):
    from types import SimpleNamespace

    import pandas as pd

    from backend.api.billboard import release_cycle as api
    from backend.core.access_surface import public_readonly_db_guard_active
    from backend.providers.spotify.client import SpotifyProvider
    from backend.services import analysis_snapshot_revision
    from backend.services import release_cycle_service as cycles

    advance_source.commit()
    reads = []

    def reader(*, readonly):
        assert readonly is True and public_readonly_db_guard_active()
        reads.append(readonly)
        connection = sqlite3.connect(":memory:")
        advance_source.backup(connection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection

    def installed_revision(connection, family):
        assert family == "analysis_records" and public_readonly_db_guard_active()
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        return "installed-fixture-revision"

    def forbidden(*_args, **_kwargs):
        pytest.fail("comparison must not use legacy enrichment/name-LIMIT-1 helpers")

    empty = pd.DataFrame(columns=["artist_name", "album_name", "ts_date_dt", "ms_played"])
    artist_ranks = pd.DataFrame(columns=["artist_name", "billboard_week", "rank", "play_count"])
    album_ranks = pd.DataFrame(columns=["billboard_week", "rank", "play_count"])

    def installed_projection(*_args, **kwargs):
        assert public_readonly_db_guard_active() and kwargs["include_selections"] is True
        return (
            empty,
            artist_ranks,
            pd.Series(index=pd.DatetimeIndex([]), dtype="float64"),
            [empty.copy(), empty.copy()],
            [album_ranks.copy(), album_ranks.copy()],
            [SimpleNamespace(track_ids=(500,)), SimpleNamespace(track_ids=(500,))],
        )

    computations = []
    compute = api.compute_release_cycle

    def compute_installed(*args, **kwargs):
        assert public_readonly_db_guard_active()
        assert [single["source_album_id"] for single in kwargs["advance_singles"]] == ["lead-main"]
        result = compute(*args, **kwargs)
        computations.append(result)
        return result

    monkeypatch.setattr(api, "get_db", reader)
    monkeypatch.setattr(analysis_snapshot_revision, "source_revision", installed_revision)
    monkeypatch.setattr(api, "prepare_project_comparison_data", installed_projection)
    monkeypatch.setattr(api, "compute_release_cycle", compute_installed)
    monkeypatch.setattr(api, "get_advance_singles", forbidden)
    monkeypatch.setattr(cycles, "get_advance_singles", forbidden)
    monkeypatch.setattr(SpotifyProvider, "get_cc_token", forbidden)
    result = api.compare_releases(
        api.CompareRequest(
            items=[
                {"artist_name": "Main", "album_name": "Album"},
                {"artist_name": "Main", "album_name": "Album Deluxe"},
            ]
        ),
        filters=None,
        merge_cfg=SimpleNamespace(merge_level=2),
        include_compilations=False,
    )
    assert len(reads) == 3
    assert len(result["comparisons"]) == 2 and result["unavailable"] == []
    assert computations[0]["clean_baseline_start"] == -9
    assert not public_readonly_db_guard_active()


def test_advance_single_uses_only_current_selection_source_tracks(advance_source):
    advance_source.executescript("""
        INSERT INTO albums VALUES(22,'Unselected Single',1);
        INSERT INTO album_projects VALUES(202,'Unselected Single',1,22,'release','2025-11-01',NULL,0);
        INSERT INTO album_project_albums VALUES(202,22);
        INSERT INTO track_albums VALUES(501,10),(501,22);
        INSERT INTO spotify_album_meta VALUES('lead-unselected','Unselected Single','2025-11-01','day','single');
        INSERT INTO spotify_album_artist_credits VALUES('lead-unselected','main','Main',0);
        INSERT INTO album_spotify_links VALUES(22,'lead-unselected',1);
    """)
    # Both songs are raw members of the target local album, but the resolved
    # L2/L3 membership can retain only one. The unselected song cannot move the
    # artist-impact baseline merely because track_albums still records it.
    assert [row["source_album_id"] for row in advance(advance_source, (500,))] == ["lead-main"]
    assert [row["source_album_id"] for row in advance(advance_source, (501,))] == [
        "lead-unselected"
    ]
    assert advance(advance_source, ()) == []


def test_advance_single_candidate_queries_are_bounded_and_deduplicate_shared_albums(advance_source):
    from backend.services.release_cycle_resolution import resolve_advance_singles

    query_sizes = []

    class RecordingConnection:
        def __getattr__(self, name):
            return getattr(advance_source, name)

        def execute(self, sql, parameters=()):
            if "FROM track_albums shared" in sql:
                query_sizes.append(len(parameters))
                assert len(parameters) <= 900
            return advance_source.execute(sql, parameters)

    # The same real shared track appears in separate chunks; it must not create
    # duplicate candidate releases. The remaining IDs have no local relation.
    ids = tuple(range(1800)) + (500,)
    rows = resolve_advance_singles(RecordingConnection(), resolve(advance_source), ids)
    assert query_sizes and max(query_sizes) <= 900
    assert [row["source_album_id"] for row in rows] == ["lead-main"]

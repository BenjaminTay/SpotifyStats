"""Date evidence regression contracts. All observations here are synthetic."""

import sqlite3
from datetime import date

import pandas as pd
import pytest

from backend.core.db import SCHEMA
from backend.core.migrations import migrate_089
from backend.domains.metadata.release_dates import (
    compare_release_dates,
    parse_release_date,
    persist_release_date,
    release_sort_key,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "raw,precision,expected",
    [
        ("2024", "year", ("2024-01-01", "2024-12-31")),
        ("2024-02", "month", ("2024-02-01", "2024-02-29")),
        ("2024-02-29", "day", ("2024-02-29", "2024-02-29")),
        ("2000-02-29", "day", ("2000-02-29", "2000-02-29")),
    ],
)
def test_calendar_ranges(raw, precision, expected):
    result = parse_release_date(raw, precision)
    assert result.status == "confirmed"
    assert (result.start.isoformat(), result.end.isoformat()) == expected
    assert result.display == raw
    assert (result.exact_day is not None) == (precision == "day")


@pytest.mark.parametrize(
    "raw,precision,status",
    [
        (None, None, "missing"),
        ("", "day", "missing"),
        ("1900-02-29", "day", "invalid"),
        ("2023-02-29", "day", "invalid"),
        ("2024-13", "month", "invalid"),
        ("0000", "year", "invalid"),
        ("2024-01-32", "day", "invalid"),
        ("2024-1-1", "day", "invalid"),
        ("2024-02", "day", "inconsistent"),
        ("2024", "month", "inconsistent"),
        ("2024-01-01", "year", "inconsistent"),
        ("2024", "week", "inconsistent"),
    ],
)
def test_unusable_dates(raw, precision, status):
    result = parse_release_date(raw, precision)
    assert result.status == status
    assert result.exact_day is None
    assert result.display is None


@pytest.mark.parametrize("raw", ["2024", "2024-02", "2024-01-01", "2024-02-01"])
def test_legacy_has_format_but_no_source_day(raw):
    value = parse_release_date(raw)
    assert value.status == "legacy" and value.precision is None
    assert value.format_precision in {"year", "month", "day"}
    assert value.exact_day is None and value.display == "2024"


@pytest.mark.parametrize(
    "left,lp,right,rp,expected",
    [
        ("2024", "year", "2024-02-29", "day", "compatible"),
        ("2024-02", "month", "2024-02-29", "day", "compatible"),
        ("2024", "year", "2024", "year", "compatible"),
        ("2024-02-29", "day", "2024-02-29", "day", "same"),
        ("2024-02-29", None, "2024-02-29", "day", "compatible"),
        ("2024", "year", "2025", "year", "conflict"),
        ("2024-02", "month", "2024-03-01", "day", "conflict"),
        ("invalid", None, "2024", "year", "unknown"),
    ],
)
def test_comparison_contract(left, lp, right, rp, expected):
    assert (
        compare_release_dates(parse_release_date(left, lp), parse_release_date(right, rp))
        == expected
    )


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.execute("INSERT INTO spotify_album_meta(spotify_album_id,album_name) VALUES('s','Synthetic')")
    yield c
    c.close()


def observe(c, raw, precision):
    return persist_release_date(
        c, {"id": "s", "release_date": raw, "release_date_precision": precision}
    )


def pair(c):
    return tuple(
        c.execute(
            "SELECT release_date,release_date_precision FROM spotify_album_meta WHERE spotify_album_id='s'"
        ).fetchone()
    )


def test_refresh_upgrade_conflict_failure_regression_and_idempotence(conn):
    assert observe(conn, "2024", "year") == "accepted"
    assert observe(conn, "2024-02", "month") == "accepted"
    assert observe(conn, "2024-02-29", "day") == "accepted"
    assert observe(conn, "2024-03-01", "day") == "conflict"
    assert pair(conn) == ("2024-02-29", "day")
    count = conn.execute("SELECT COUNT(*) FROM spotify_album_date_observations").fetchone()[0]
    observe(conn, "2024-03-01", "day")
    assert (
        conn.execute("SELECT COUNT(*) FROM spotify_album_date_observations").fetchone()[0] == count
    )
    assert observe(conn, "2024", "year") == "precision_regression"
    assert observe(conn, None, None) == "missing"
    assert observe(conn, "2024-02-29", None) == "legacy"
    assert observe(conn, "2024-02-30", "day") == "invalid"
    assert pair(conn) == ("2024-02-29", "day")
    assert observe(conn, "2024-02-29", "day") == "unchanged"


def test_legacy_raw_pair_is_preserved_until_source_confirmation(conn):
    assert observe(conn, "2024-01-01", None) == "legacy"
    assert pair(conn) == ("2024-01-01", None)
    assert observe(conn, "2024-01-01", "day") == "accepted"
    assert pair(conn) == ("2024-01-01", "day")


def test_upgrade_is_additive_idempotent_and_does_not_infer_dates():
    c = sqlite3.connect(":memory:")
    c.executescript(
        "CREATE TABLE spotify_album_meta(spotify_album_id TEXT,release_date TEXT); INSERT INTO spotify_album_meta VALUES('old','2000-01-01'); CREATE TABLE album_projects(project_id INTEGER,release_date TEXT); INSERT INTO album_projects VALUES(1,'2000');"
    )
    migrate_089(c)
    migrate_089(c)
    assert c.execute(
        "SELECT release_date,release_date_precision FROM spotify_album_meta"
    ).fetchone() == ("2000-01-01", None)
    assert c.execute(
        "SELECT release_date,release_date_precision FROM album_projects"
    ).fetchone() == ("2000", None)
    c.close()


def test_alignment_requires_source_day_and_cycle_degrades_without_build(monkeypatch):
    from backend.services import release_cycle_service as svc

    frame = pd.DataFrame({"billboard_week": ["2024-02-29", "2024-03-07"], "play_count": [1, 2]})
    for raw, prec in [
        ("2024", "year"),
        ("2024-02", "month"),
        ("2024-02-29", None),
        ("2024-02-30", "day"),
    ]:
        with pytest.raises(ValueError, match="release_day_unconfirmed"):
            svc.align_to_release(frame, raw, release_date_precision=prec)
    assert svc.align_to_release(
        frame, "2024-02-29", release_date_precision="day"
    ).week_offset.tolist() == [0, 1]
    monkeypatch.setattr(
        svc, "_resolve_album_group", lambda *_: pytest.fail("unavailable must not build")
    )
    result = svc.compute_release_cycle(pd.DataFrame(), "Synthetic", "Synthetic", "2024")
    assert result["status"] == "unavailable" and result["reason"] == "release_day_unconfirmed"


def test_sorting_uses_ranges_not_claimed_release_days():
    items = ["invalid", "2024-02", "2024-01-30", "2024", "2023-12-31"]
    assert sorted(items, key=release_sort_key) == [
        "2023-12-31",
        "2024",
        "2024-01-30",
        "2024-02",
        "invalid",
    ]
    assert parse_release_date("2024-02", "month").end == date(2024, 2, 29)


def test_precision_only_change_invalidates_revision_and_identical_refresh_does_not(tmp_path):
    from pathlib import Path

    from backend.services.analysis_snapshot_revision import (
        install_revision_tracking,
        source_revision,
    )

    seed = Path(__file__).parents[1] / "fixtures" / "seed.db"
    source = sqlite3.connect(f"file:{seed}?mode=ro&immutable=1", uri=True)
    conn = sqlite3.connect(tmp_path / "revision.db")
    source.backup(conn)
    source.close()
    conn.execute(
        "INSERT INTO spotify_album_meta(spotify_album_id,album_name) VALUES('s','Synthetic')"
    )
    install_revision_tracking(conn)
    conn.commit()
    before = source_revision(conn, "analysis_records")
    observe(conn, "2024", "year")
    conn.commit()
    after = source_revision(conn, "analysis_records")
    assert before != after
    observe(conn, "2024", "year")
    conn.commit()
    assert source_revision(conn, "analysis_records") == after


def test_bounded_date_only_maintenance_is_atomic_and_keeps_manual_project(conn):
    from scripts.backfill_spotify_release_dates import apply_observations

    conn.execute("INSERT INTO artists(artist_id,artist_name) VALUES(1,'Synthetic')")
    conn.execute("INSERT INTO albums(album_id,album_name,artist_id) VALUES(1,'Synthetic',1)")
    conn.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES(1,'s','synthetic',1)"
    )
    conn.execute(
        "INSERT INTO album_projects(project_id,canonical_name,artist_id,primary_album_id,release_date,is_manual) VALUES(1,'Synthetic',1,1,'2024',1)"
    )
    result = apply_observations(
        conn,
        [{"id": "s", "release_date": "2024", "release_date_precision": "year"}],
        album_ids=["s"],
    )
    assert result["outcomes"] == {"s": "accepted"}
    assert result["project_precision_changes"] == 0
    assert tuple(
        conn.execute(
            "SELECT release_date,release_date_precision,is_manual FROM album_projects"
        ).fetchone()
    ) == ("2024", None, 1)
    with pytest.raises(ValueError, match="unrequested"):
        apply_observations(conn, [{"id": "foreign"}], album_ids=["s"])
    assert pair(conn) == ("2024", "year")


def test_date_update_and_observation_rollback_with_album_transaction(conn):
    from backend.domains.metadata.spotify_refresh import upsert_album_batch

    conn.commit()
    conn.execute(
        "CREATE TRIGGER reject_date BEFORE UPDATE OF release_date ON spotify_album_meta BEGIN SELECT RAISE(ABORT,'synthetic storage failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="synthetic storage failure"):
        upsert_album_batch(
            conn,
            [
                {
                    "id": "s",
                    "name": "Changed Synthetic",
                    "release_date": "2024-02-29",
                    "release_date_precision": "day",
                }
            ],
        )
    assert pair(conn) == (None, None)
    assert (
        conn.execute(
            "SELECT album_name FROM spotify_album_meta WHERE spotify_album_id='s'"
        ).fetchone()[0]
        == "Synthetic"
    )
    assert conn.execute("SELECT COUNT(*) FROM spotify_album_date_observations").fetchone()[0] == 0


def test_public_compatibility_reader_never_fetches_missing_date(monkeypatch):
    from backend.core.access_surface import (
        reset_public_readonly_db_guard,
        set_public_readonly_db_guard,
    )
    from backend.services import release_cycle_service as svc

    svc._spotify_search_album.cache_clear()
    monkeypatch.setattr(svc, "_album_identity_cache_revision", lambda: ("synthetic",))
    monkeypatch.setattr(svc, "_get_spotify_token", lambda: pytest.fail("public GET must not fetch"))
    token = set_public_readonly_db_guard(True)
    try:
        assert svc._spotify_search_album("Synthetic", "Synthetic", skip_db_check=True) is None
    finally:
        reset_public_readonly_db_guard(token)
        svc._spotify_search_album.cache_clear()


def test_coarse_range_filter_never_adds_play_contributions():
    from backend.domains.playback.album_projects import _filter_to_project_release_date

    frame = pd.DataFrame(
        {
            "ts_date": ["2024-01-01", "2024-02-10", "2024-02-29", "2024-03-01"],
            "release_date": ["2024-02"] * 4,
            "release_date_precision": ["month"] * 4,
        }
    )
    assert _filter_to_project_release_date(frame)["ts_date"].tolist() == [
        "2024-02-29",
        "2024-03-01",
    ]


def test_current_detail_precision_display_for_source_and_legacy():
    from backend.domains.metadata.album_detail_meta import resolve_album_detail_meta
    from backend.tests.unit.test_album_detail_meta import _fixture_conn

    for raw, precision, display, status in [
        ("2024", "year", "2024", "confirmed"),
        ("2024-02", "month", "2024-02", "confirmed"),
        ("2024-02-29", "day", "2024-02-29", "confirmed"),
        ("2024-01-01", None, "2024", "legacy"),
    ]:
        c = _fixture_conn(raw)
        c.execute("ALTER TABLE album_projects ADD COLUMN release_date_precision TEXT")
        c.execute("UPDATE album_projects SET release_date_precision=?", (precision,))
        meta = resolve_album_detail_meta(c, "Fixture Album", "Fixture Artist", album_project_id=100)
        assert (
            meta["release_date"],
            meta["release_date_precision"],
            meta["release_date_display"],
            meta["release_date_status"],
        ) == (raw, precision, display, status)
        c.close()


def test_unconfirmed_cycle_api_surfaces_do_not_build(monkeypatch):
    from backend.api.billboard import release_cycle as api

    monkeypatch.setattr(
        api, "load_artist_releases", lambda *_: pd.DataFrame(columns=["album_name"])
    )
    monkeypatch.setattr(
        api,
        "_get_weekly_data",
        lambda *_args, **_kwargs: pytest.fail("unconfirmed day must not build"),
    )
    artist = api.get_artist_overview("Synthetic", filters=None, merge_cfg=None)
    assert artist["status"] == "unavailable" and artist["reason"] == "release_day_unconfirmed"
    album = api.get_album_detail("Synthetic", "Synthetic Album", filters=None, merge_cfg=None)
    assert album["status"] == "unavailable" and album["reason"] == "release_day_unconfirmed"
    request = api.CompareRequest(
        items=[
            {"artist_name": "Synthetic", "album_name": "A"},
            {"artist_name": "Synthetic", "album_name": "B"},
        ]
    )
    compared = api.compare_releases(request, filters=None, merge_cfg=None)
    assert compared["comparisons"] == []
    assert [item["album_name"] for item in compared["unavailable"]] == ["A", "B"]
    assert all(item["reason"] == "release_day_unconfirmed" for item in compared["unavailable"])

"""Default track details reuse exact ranks while preserving every detail fact."""

import sqlite3

import pytest
from fastapi import HTTPException

from backend.core import db
from backend.services import entity_stats_service as stats
from backend.services import versus_rank_context_service as ranks
from backend.tests.unit import test_versus_rank_context

base_isolated = test_versus_rank_context.base_isolated
isolated = test_versus_rank_context.isolated

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("level,dynamic", [(2, True), (2, False), (3, True), (3, False)])
def test_default_track_full_payload_matches_legacy_without_global_materialisation(
    isolated, monkeypatch, level, dynamic
):
    conn = db.get_db(readonly=True)
    try:
        filters, _, _, _ = ranks.request_context(
            conn, {"merge_level": level, "dynamic_threshold": dynamic}
        )
        args = {k: filters[k] for k in (*ranks.LOAD_FILTERS, "merge_level")}
        track_id = conn.execute(
            "SELECT l1_id FROM track_l1_identities ORDER BY l1_id LIMIT 1"
        ).fetchone()[0]
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: False)
        expected = stats._build_track_stats(conn, track_id, **args)
        assert expected["found"]
        ranks.ensure(conn, filters)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        load = stats.load_plays

        def target_only(*a, **kw):
            assert kw.get("extra_where") and kw.get("extra_params"), "global plays loaded"
            return load(*a, **kw)

        monkeypatch.setattr(stats, "load_plays", target_only)
        monkeypatch.setattr(
            stats, "_ranks", lambda *a, **kw: pytest.fail("global ranks calculated")
        )
        assert stats._build_track_stats(conn, track_id, **args) == expected
    finally:
        conn.close()


def test_missing_or_drifted_track_rank_publication_fails_without_building(isolated, monkeypatch):
    conn = db.get_db(readonly=True)
    try:
        filters, _, _, _ = ranks.request_context(conn)
        args = {k: filters[k] for k in (*ranks.LOAD_FILTERS, "merge_level")}
        track_id = conn.execute(
            "SELECT l1_id FROM track_l1_identities ORDER BY l1_id LIMIT 1"
        ).fetchone()[0]
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        with pytest.raises(HTTPException) as missing:
            stats._build_track_stats(conn, track_id, **args)
        assert missing.value.status_code == 503
        ranks.ensure(conn, filters)
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
            )
        monkeypatch.setattr(
            ranks, "ensure", lambda *a, **kw: pytest.fail("GET rebuilt rank publication")
        )
        with pytest.raises(HTTPException) as drift:
            stats._build_track_stats(conn, track_id, **args)
        assert drift.value.status_code == 503
    finally:
        conn.close()


def test_existing_track_with_zero_millisecond_rows_has_empty_stats(isolated, monkeypatch):
    with sqlite3.connect(isolated[0]) as writer:
        writer.execute("UPDATE plays SET ms_played=0")
    monkeypatch.setattr(stats, "_is_primary_connection", lambda _: False)
    conn = db.get_db(readonly=True)
    try:
        track_id = conn.execute(
            "SELECT l1_id FROM track_l1_identities ORDER BY l1_id LIMIT 1"
        ).fetchone()[0]
        result = stats._build_track_stats(
            conn,
            track_id,
            30000,
            True,
            True,
            merge_level=2,
            dynamic_threshold=True,
            include_rank_context=False,
        )
        assert result["found"] is True
        assert result["summary"]["total_plays"] == 0
        assert result["summary"]["total_hours"] == 0
        assert result["first_played"] is None and result["last_played"] is None
        assert result["recent_plays"] == []
        assert not stats._build_track_stats(
            conn,
            999999,
            30000,
            True,
            True,
            include_rank_context=False,
        )["found"]
    finally:
        conn.close()

"""Shared rank publications preserve complete detail facts and fail closed."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from backend.core import db
from backend.services import entity_rank_context_service as ranks
from backend.services import entity_stats_service as stats
from backend.services.analysis_snapshot_service import default_params
from backend.tests.unit import test_analysis_snapshots

isolated = test_analysis_snapshots.isolated

pytestmark = pytest.mark.unit


def test_published_rank_context_matches_full_artist_builder(isolated, monkeypatch):
    conn = db.get_db(readonly=True)
    try:
        params = default_params(conn, "analysis_stats")
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _conn: False)
        before = stats._build_artist_stats(conn, "Fixture Artist Alpha", **params)
        ranking = stats.get_artist_personal_ranking(
            conn, "Fixture Artist Alpha", "track", "plays", 20, 0, **params
        )
        ranks.ensure(conn)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _conn: True)
        assert stats._build_artist_stats(conn, "Fixture Artist Alpha", **params) == before
        assert (
            stats.get_artist_personal_ranking(
                conn, "Fixture Artist Alpha", "track", "plays", 20, 0, **params
            )
            == ranking
        )
        assert stats._build_artist_stats(conn, "____not_found____", **params) == {"found": False}
    finally:
        conn.close()


def test_rank_publication_singleflight_missing_and_source_drift(isolated, monkeypatch):
    conn = db.get_db(readonly=True)
    try:
        params = default_params(conn, "analysis_stats")
        with pytest.raises(HTTPException) as missing:
            ranks.read(conn, params)
        assert missing.value.status_code == 503

        def build():
            owned = db.get_db(readonly=True)
            try:
                return ranks.ensure(owned)
            finally:
                owned.close()

        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda _: build(), range(4)))
        assert sum(result["published"] for result in results) == 1
        before = ranks.read(conn, params)
        monkeypatch.setattr(ranks, "ensure", lambda *_args: pytest.fail("GET built ranks"))
        assert ranks.read(conn, params) == before
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
            )
        with pytest.raises(HTTPException) as drift:
            ranks.read(conn, params)
        assert drift.value.status_code == 503
    finally:
        conn.close()


@pytest.mark.parametrize("table", ["artist_identity_state", "track_credit_state"])
def test_rank_context_tracks_identity_and_credit_revision(isolated, table):
    conn = db.get_db(readonly=True)
    try:
        before = ranks.context(conn)
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(f"UPDATE {table} SET current_revision=current_revision+1")
        after = ranks.context(conn)
        assert before[:2] == after[:2]
        assert before[2] != after[2]
    finally:
        conn.close()

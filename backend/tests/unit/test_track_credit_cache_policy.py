"""Code-only credit changes must reject old aggregates and display cache keys."""

import sqlite3

import pytest

from backend.core import db
from backend.domains.metadata import track_credits

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("published_policy", [None, "previous-credit-policy"])
def test_legacy_aggregate_cannot_be_relabelled_without_current_credit_policy(published_policy):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE agg_config(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
    if published_policy:
        conn.execute("INSERT INTO agg_config VALUES ('track_credit_policy',?)", (published_policy,))
    values = dict(
        min_ms=30_000,
        music_only=True,
        week_start_dow=4,
        week_start_hour=0,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        identity_revision=0,
        track_credit_revision=0,
        track_identity_revision=0,
    )
    current_hash = db._agg_param_hash(**values)
    conn.execute("INSERT INTO agg_config VALUES ('param_hash',?)", (current_hash,))
    assert not db.check_agg_valid(conn, current_hash)
    assert not db.aggregation_partial_base_is_compatible(
        conn, **values, mutable_dependency_keys=frozenset({"track_credit_revision"})
    )
    conn.close()


def test_policy_change_invalidates_aggregate_proof_without_source_revision_write(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE agg_config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE plays(track_id INTEGER);
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY,spotify_track_id TEXT);
        CREATE TABLE spotify_track_meta(spotify_track_id TEXT,duration_ms INTEGER);
        """
    )
    values = dict(
        min_ms=30_000,
        music_only=True,
        week_start_dow=4,
        week_start_hour=0,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        identity_revision=0,
        track_credit_revision=0,
        track_identity_revision=0,
    )
    old_hash, old_dependencies = db.build_aggregation_semantic_proof(conn, **values)
    conn.executemany("INSERT INTO agg_config VALUES (?,?)", old_dependencies.items())
    conn.execute("INSERT INTO agg_config VALUES ('param_hash',?)", (old_hash,))
    conn.commit()
    assert db.check_agg_valid(conn, old_hash)
    writes = conn.total_changes

    monkeypatch.setattr(track_credits, "TRACK_CREDIT_POLICY_VERSION", "new-credit-policy")
    new_hash, new_dependencies = db.build_aggregation_semantic_proof(conn, **values)
    assert new_hash != old_hash
    assert new_dependencies["track_credit_policy"] != old_dependencies["track_credit_policy"]
    assert not db.check_agg_valid(conn, old_hash)
    assert not db.check_agg_valid(conn, new_hash)
    assert not db.aggregation_partial_base_is_compatible(
        conn,
        **values,
        mutable_dependency_keys=frozenset({"track_credit_revision", "credit_membership_revision"}),
    )
    assert conn.total_changes == writes
    conn.close()


def test_policy_change_invalidates_display_and_artist_fanout_memory_keys(monkeypatch):
    before = db._track_display_cache_key()
    captured = []
    monkeypatch.setattr(
        db, "_load_plays_for_artists_cached", lambda **kwargs: _frame(captured, kwargs)
    )
    conn = db.get_db(readonly=True)
    try:
        db.load_plays_for_artists(conn)
        monkeypatch.setattr(track_credits, "TRACK_CREDIT_POLICY_VERSION", "new-credit-policy")
        db.load_plays_for_artists(conn)
    finally:
        conn.close()
    assert db._track_display_cache_key() != before
    assert captured[0]["track_credit_policy"] != captured[1]["track_credit_policy"]
    assert captured[0]["track_credit_revision"] == captured[1]["track_credit_revision"]


def _frame(captured, kwargs):
    import pandas as pd

    captured.append(kwargs)
    return pd.DataFrame()

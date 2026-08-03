from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from backend.core.job_queue import Job
from backend.services import track_credit_rebuild_service as rebuild


def _database(path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE track_credit_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL,
            active_aggregate_revision INTEGER NOT NULL,
            rebuild_status TEXT NOT NULL,
            last_error TEXT,
            updated_at TEXT
        );
        INSERT INTO track_credit_state VALUES (1, 4, 3, 'pending', NULL, NULL);
        CREATE TABLE artist_identity_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL
        );
        INSERT INTO artist_identity_state VALUES (1, 9);
        CREATE TABLE agg_weekly_artists (
            billboard_week TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            play_count INTEGER NOT NULL,
            total_ms INTEGER NOT NULL,
            PRIMARY KEY (billboard_week, artist_id)
        );
        INSERT INTO agg_weekly_artists VALUES ('2026-01-02', 99, 7, 7000);
        CREATE TABLE agg_config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    conn.commit()
    conn.close()


def _connection_factory(path):
    def connect(*, readonly=False):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    return connect


class _Settings:
    def __init__(self, _conn):
        pass

    def load_all(self):
        return {
            "min_ms": 30_000,
            "music_only": True,
            "bb_week_start_dow": 4,
            "bb_week_start_hour": 0,
        }


def test_track_credit_shadow_rebuild_atomically_switches_artist_aggregates(tmp_path, monkeypatch):
    path = tmp_path / "track-credit.db"
    _database(path)
    monkeypatch.setattr(rebuild, "get_db", _connection_factory(path))
    monkeypatch.setattr(rebuild, "SettingsRepository", _Settings)
    monkeypatch.setattr(
        rebuild,
        "load_billboard_raw_for_artists",
        lambda *_args: pd.DataFrame(
            [
                {"billboard_week": "2026-02-06", "artist_id": 53, "ms_played": 1000},
                {"billboard_week": "2026-02-06", "artist_id": 53, "ms_played": 2000},
            ]
        ),
    )

    rebuild.handle_track_credit_rebuild(
        Job.create("track_credit_rebuild", "track_credit", "global", revision=4)
    )

    conn = _connection_factory(path)()
    assert [tuple(row) for row in conn.execute("SELECT * FROM agg_weekly_artists")] == [
        ("2026-02-06", 53, 2, 3000)
    ]
    state = conn.execute("SELECT * FROM track_credit_state").fetchone()
    assert state["active_aggregate_revision"] == 4
    assert state["rebuild_status"] == "ready"
    conn.close()


def test_track_credit_failed_rebuild_keeps_old_aggregate_and_realtime_revision(
    tmp_path, monkeypatch
):
    path = tmp_path / "track-credit-failure.db"
    _database(path)
    monkeypatch.setattr(rebuild, "get_db", _connection_factory(path))
    monkeypatch.setattr(rebuild, "SettingsRepository", _Settings)

    def fail(*_args):
        raise RuntimeError("simulated credit rebuild failure")

    monkeypatch.setattr(rebuild, "load_billboard_raw_for_artists", fail)
    with pytest.raises(RuntimeError, match="simulated credit"):
        rebuild.handle_track_credit_rebuild(
            Job.create("track_credit_rebuild", "track_credit", "global", revision=4)
        )

    conn = _connection_factory(path)()
    assert [tuple(row) for row in conn.execute("SELECT * FROM agg_weekly_artists")] == [
        ("2026-01-02", 99, 7, 7000)
    ]
    state = conn.execute("SELECT * FROM track_credit_state").fetchone()
    assert state["active_aggregate_revision"] == 3
    assert state["rebuild_status"] == "failed"
    assert "simulated credit rebuild failure" in state["last_error"]
    conn.close()

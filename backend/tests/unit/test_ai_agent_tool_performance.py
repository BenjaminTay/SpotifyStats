from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from backend.domains.ai_agent import entity_comparison_service, tool_registry, tools
from backend.domains.ai_agent.tool_cache import clear_agent_tool_cache, make_cache_key

pytestmark = pytest.mark.unit


def _revision_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE music_search_revision_state (
            state_id INTEGER PRIMARY KEY,
            playback_revision INTEGER NOT NULL,
            billboard_revision INTEGER NOT NULL,
            metadata_revision INTEGER NOT NULL,
            settings_revision INTEGER NOT NULL,
            candidate_revision INTEGER NOT NULL,
            updated_at TEXT
        );
        INSERT INTO music_search_revision_state VALUES (1, 1, 2, 3, 4, 5, NULL);
        CREATE TABLE track_identity_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL
        );
        INSERT INTO track_identity_state VALUES (1, 6);
        CREATE TABLE artist_identity_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL
        );
        INSERT INTO artist_identity_state VALUES (1, 8);
        CREATE TABLE track_credit_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL
        );
        INSERT INTO track_credit_state VALUES (1, 9);
        CREATE TABLE album_project_revision_state (
            state_id INTEGER PRIMARY KEY,
            current_revision INTEGER NOT NULL
        );
        INSERT INTO album_project_revision_state VALUES (1, 7);
        """
    )
    conn.commit()
    conn.close()


def _factory(path: Path):
    def get_db(readonly: bool = True) -> sqlite3.Connection:
        del readonly
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    return get_db


def test_revision_cache_reuses_result_and_invalidates_after_revision_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "agent-cache.db"
    _revision_db(database)
    clear_agent_tool_cache()
    monkeypatch.setattr(tools, "get_db", _factory(database))
    calls = 0

    def stats(_conn: sqlite3.Connection, **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {
            "period": {"period": "lifetime", "start_date": "2020-01-01", "end_date": "2026-01-01"},
            "summary": {
                "total_plays": calls,
                "total_hours": 1,
                "unique_tracks": 1,
                "unique_artists": 1,
            },
        }

    monkeypatch.setattr(tools.analysis_stats_service, "get_analysis_stats", stats)
    params = tools.AnalysisStatsParams()

    first = tools.analysis_stats_handler(params)
    first.data["summary"]["total_plays"] = 999
    second = tools.analysis_stats_handler(params)

    assert calls == 1
    assert second.data["summary"]["total_plays"] == 1

    conn = sqlite3.connect(database)
    conn.execute("UPDATE music_search_revision_state SET playback_revision=playback_revision+1")
    conn.commit()
    conn.close()

    third = tools.analysis_stats_handler(params)
    assert calls == 2
    assert third.data["summary"]["total_plays"] == 2


def test_cache_key_tracks_metadata_revisions_and_normalized_filters(tmp_path: Path) -> None:
    database = tmp_path / "agent-cache-metadata.db"
    _revision_db(database)
    conn = sqlite3.connect(database)
    base_params = tools.AnalysisChartsParams(entity="artist", period="this_year")
    base = make_cache_key(conn, tool_name="analysis_charts", params=base_params)
    same = make_cache_key(
        conn,
        tool_name="analysis_charts",
        params=tools.AnalysisChartsParams(period="this_year", entity="artist"),
    )
    different_filter = make_cache_key(
        conn,
        tool_name="analysis_charts",
        params=tools.AnalysisChartsParams(entity="artist", period="this_year", min_ms=45_000),
    )

    assert base is not None
    assert base == same
    assert different_filter is not None
    assert base.normalized_params != different_filter.normalized_params

    conn.execute("UPDATE artist_identity_state SET current_revision=current_revision+1")
    artist_identity_changed = make_cache_key(
        conn,
        tool_name="analysis_charts",
        params=base_params,
    )
    conn.execute("UPDATE track_credit_state SET current_revision=current_revision+1")
    track_credit_changed = make_cache_key(
        conn,
        tool_name="analysis_charts",
        params=base_params,
    )
    conn.close()

    assert artist_identity_changed is not None
    assert track_credit_changed is not None
    assert artist_identity_changed.revision != base.revision
    assert track_credit_changed.revision != artist_identity_changed.revision


def test_cache_key_does_not_cross_same_path_database_replacement(tmp_path: Path) -> None:
    database = tmp_path / "agent-cache-replaced.db"
    replacement = tmp_path / "agent-cache-new.db"
    _revision_db(database)
    _revision_db(replacement)
    params = tools.AnalysisStatsParams()
    conn = sqlite3.connect(database)
    before = make_cache_key(conn, tool_name="analysis_stats", params=params)
    conn.close()

    os.replace(replacement, database)
    conn = sqlite3.connect(database)
    after = make_cache_key(conn, tool_name="analysis_stats", params=params)
    conn.close()

    assert before is not None
    assert after is not None
    assert (before.database_device, before.database_inode) != (
        after.database_device,
        after.database_inode,
    )


def test_comparison_batches_playback_and_billboard_sources_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"playback": 0, "billboard": 0, "resolve": 0}
    frame = pd.DataFrame(
        [
            {"artist_name": "Artist A", "track_id": 1, "ts": "2026-01-01", "ms_played": 100},
            {"artist_name": "Artist A", "track_id": 2, "ts": "2026-01-02", "ms_played": 100},
            {"artist_name": "Artist B", "track_id": 3, "ts": "2026-01-03", "ms_played": 100},
        ]
    )

    def load(*_args: Any, **_kwargs: Any):
        calls["playback"] += 1
        return (
            frame,
            frame,
            {
                "period": "lifetime",
                "start_date": "2026-01-01",
                "end_date": "2026-01-03",
            },
        )

    def resolve(_conn: sqlite3.Connection, *, query: str, entity_type: str, limit: int):
        calls["resolve"] += 1
        return {
            "found": True,
            "candidates": [{"name": query, "artist_name": query}],
            "entity_type": entity_type,
            "limit": limit,
        }

    def compute(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls["billboard"] += 1
        return {
            "weekly_artist": [
                {"artist_name": "Artist A", "billboard_week": "2026-01-02", "rank": 1},
                {"artist_name": "Artist B", "billboard_week": "2026-01-02", "rank": 2},
            ],
            "artist_power_scores": [
                {"artist_name": "Artist A", "power_score": 20},
                {"artist_name": "Artist B", "power_score": 10},
            ],
        }

    monkeypatch.setattr(entity_comparison_service, "load_period_plays", load)
    monkeypatch.setattr(entity_comparison_service, "resolve_entities", resolve)
    monkeypatch.setattr(entity_comparison_service, "compute_billboard_data", compute)
    monkeypatch.setattr(
        entity_comparison_service,
        "_filter_entity_rows",
        lambda data, _entity, _track, _album, artist, **_kwargs: data[
            data["artist_name"] == artist
        ],
    )
    monkeypatch.setattr(
        entity_comparison_service,
        "build_duration_frame",
        lambda entity_all, _resolved: entity_all,
    )
    monkeypatch.setattr(
        entity_comparison_service,
        "_summary",
        lambda entity_current, _duration: {
            "total_plays": len(entity_current),
            "total_hours": len(entity_current) / 10,
        },
    )
    conn = sqlite3.connect(":memory:")
    rows = entity_comparison_service.build_entity_comparison_rows(
        conn,
        entity_type="artist",
        names=["Artist A", "Artist B"],
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        period="lifetime",
        start_date=None,
        end_date=None,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        merge_level=2,
        include_billboard=True,
    )
    conn.close()

    assert calls == {"playback": 1, "billboard": 1, "resolve": 2}
    assert [row["plays"] for row in rows] == [2, 1]
    assert rows[0]["power_rank"] == 1
    assert rows[1]["peak_position"] == 2


def test_registry_exposes_runtime_scheduling_metadata() -> None:
    metadata = tool_registry.get_default_registry().runtime_metadata("compare_entities")

    assert metadata == {
        "cost": "high",
        "timeout_seconds": 120,
        "cacheability": "revision",
        "supports_parallel": True,
    }
    listed = {item["name"]: item for item in tool_registry.list_tools()}
    assert listed["analysis_stats"]["runtime"]["cacheability"] == "revision"
    routing = listed["compare_entities"]["routing"]
    assert routing["cost"] == "high"
    assert routing["parallel_safe"] is True
    assert routing["cold_build_risk"] == "medium"
    assert "比较 2-4 个同类实体" in routing["best_for"]
    assert {"cumulative", "recency", "intensity", "fairness"}.issubset(routing["covers"])
    assert routing["fallback"] == ["entity_stats", "resolve_entity"]

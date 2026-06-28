from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from backend.domains.ai_agent import tool_registry, tools

pytestmark = pytest.mark.unit


class FakeReadonlyConn:
    def __init__(self, *, album_projects_ready: bool = True) -> None:
        self.album_projects_ready = album_projects_ready
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def execute(self, sql: str, params: tuple[Any, ...] = ()):
        del params
        if "sqlite_master" in sql:
            rows = (
                [
                    {"name": "album_projects"},
                    {"name": "album_project_albums"},
                    {"name": "album_project_tracks"},
                ]
                if self.album_projects_ready
                else []
            )
            return FakeCursor(rows)
        if "COUNT(*) FROM album_projects" in sql:
            return FakeCursor([(1 if self.album_projects_ready else 0,)])
        raise AssertionError(f"unexpected SQL in fake readonly connection: {sql}")


class FakeCursor:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def fetchall(self) -> list[Any]:
        return self.rows

    def fetchone(self) -> Any | None:
        return self.rows[0] if self.rows else None


def _patch_readonly_db(
    monkeypatch: pytest.MonkeyPatch,
    *,
    album_projects_ready: bool = True,
) -> dict[str, Any]:
    observed: dict[str, Any] = {"readonly_flags": [], "connections": []}

    def fake_get_db(readonly: bool = True) -> FakeReadonlyConn:
        observed["readonly_flags"].append(readonly)
        conn = FakeReadonlyConn(album_projects_ready=album_projects_ready)
        observed["connections"].append(conn)
        return conn

    monkeypatch.setattr(tools, "get_db", fake_get_db)
    return observed


def test_default_registry_exposes_backend_defined_readonly_tool_allowlist() -> None:
    tool_registry.get_default_registry.cache_clear()

    registered = tool_registry.list_tools()
    names = {item["name"] for item in registered}

    assert {
        "analysis_stats",
        "analysis_charts",
        "playback_records",
        "wrapped_yearly",
        "entity_stats",
        "billboard_entity_detail",
        "listening_hours",
    }.issubset(names)
    assert all(item["read_only"] is True for item in registered)
    assert (
        registered[
            next(
                index
                for index, item in enumerate(registered)
                if item["name"] == "billboard_entity_detail"
            )
        ]["params_schema"]["properties"]["merge_level"]["maximum"]
        == 3
    )


def test_unknown_tool_is_rejected() -> None:
    with pytest.raises(tool_registry.UnknownAgentToolError, match="unknown_tool"):
        tool_registry.dispatch_tool("unknown_tool", {})


def test_registering_non_read_only_tool_is_rejected() -> None:
    registry = tool_registry.AgentToolRegistry()
    unsafe_tool = tool_registry.AgentToolDefinition(
        name="unsafe_writer",
        description="writes to the database",
        read_only=False,
        params_model=tools.AnalysisStatsParams,
        handler=lambda params: tool_registry.AgentToolResult(
            data={}, result_summary="", source_range=""
        ),
    )

    with pytest.raises(ValueError, match="read-only"):
        registry.register(unsafe_tool)


def test_analysis_tool_params_are_schema_validated() -> None:
    with pytest.raises(ValidationError):
        tool_registry.dispatch_tool(
            "analysis_charts",
            {
                "limit": 1000,
                "offset": -1,
                "entity": "playlist",
            },
        )


def test_analysis_stats_dispatches_to_service_with_readonly_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_observed = _patch_readonly_db(monkeypatch)
    service_observed: dict[str, Any] = {}

    def fake_get_analysis_stats(conn: FakeReadonlyConn, **kwargs: Any) -> dict[str, Any]:
        service_observed["conn"] = conn
        service_observed["kwargs"] = kwargs
        return {
            "period": {
                "period": "custom",
                "label": "自定义",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            "summary": {
                "total_plays": 42,
                "total_hours": 3.5,
                "unique_tracks": 12,
                "unique_albums": 5,
                "unique_artists": 4,
                "active_days": 9,
            },
            "daily_trend": [{"date": "2026-01-01", "plays": 3}],
        }

    monkeypatch.setattr(
        tools.analysis_stats_service,
        "get_analysis_stats",
        fake_get_analysis_stats,
    )

    result = tool_registry.dispatch_tool(
        "analysis_stats",
        {
            "min_ms": 45000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": 45,
            "period": "custom",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )

    assert result["tool_name"] == "analysis_stats"
    assert "min_ms=45000" in result["params_summary"]
    assert "plays=42" in result["result_summary"]
    assert result["source_range"] == "2026-01-01..2026-01-31"
    assert result["data"]["summary"]["total_plays"] == 42
    assert db_observed["readonly_flags"] == [True]
    assert db_observed["connections"][0].closed is True
    assert service_observed["conn"] is db_observed["connections"][0]
    assert service_observed["kwargs"] == {
        "min_ms": 45000,
        "music_only": False,
        "merge_enabled": False,
        "period": "custom",
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 45,
    }


def test_analysis_charts_dispatches_to_service_with_bounded_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_observed = _patch_readonly_db(monkeypatch)
    service_observed: dict[str, Any] = {}

    def fake_get_analysis_charts(conn: FakeReadonlyConn, **kwargs: Any) -> dict[str, Any]:
        service_observed["conn"] = conn
        service_observed["kwargs"] = kwargs
        return {
            "period": {
                "period": "this_year",
                "label": "今年",
                "start_date": "2026-01-01",
                "end_date": "2026-06-28",
            },
            "entity": "artist",
            "metric": "hours",
            "total": 20,
            "limit": 25,
            "offset": 5,
            "rows": [{"artist_name": "Test Artist", "hours": 12.3}],
        }

    monkeypatch.setattr(
        tools.analysis_stats_service,
        "get_analysis_charts",
        fake_get_analysis_charts,
    )

    result = tool_registry.dispatch_tool(
        "analysis_charts",
        {
            "period": "this_year",
            "entity": "artist",
            "metric": "hours",
            "limit": 25,
            "offset": 5,
            "merge_level": 3,
            "include_compilations": True,
        },
    )

    assert result["tool_name"] == "analysis_charts"
    assert "entity=artist" in result["params_summary"]
    assert "rows=1/20" in result["result_summary"]
    assert result["source_range"] == "2026-01-01..2026-06-28"
    assert result["data"]["rows"][0]["artist_name"] == "Test Artist"
    assert db_observed["readonly_flags"] == [True]
    assert db_observed["connections"][0].closed is True
    assert service_observed["conn"] is db_observed["connections"][0]
    assert service_observed["kwargs"] == {
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "period": "this_year",
        "start_date": None,
        "end_date": None,
        "entity": "artist",
        "metric": "hours",
        "limit": 25,
        "offset": 5,
        "merge_level": 3,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": None,
        "include_compilations": True,
    }


def test_playback_records_dispatches_to_readonly_records_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_observed = _patch_readonly_db(monkeypatch)
    service_observed: dict[str, Any] = {}

    def fake_get_analysis_records(conn: FakeReadonlyConn, **kwargs: Any) -> dict[str, Any]:
        service_observed["conn"] = conn
        service_observed["kwargs"] = kwargs
        return {
            "period": {
                "period": "custom",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            },
            "meta": {"total_plays": 88, "total_hours": 7.25},
            "records": {"champions": []},
        }

    monkeypatch.setattr(
        tools.analysis_records_service,
        "get_analysis_records",
        fake_get_analysis_records,
    )

    result = tool_registry.dispatch_tool(
        "playback_records",
        {
            "period": "custom",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "merge_level": 3,
            "include_compilations": True,
        },
    )

    assert result["tool_name"] == "playback_records"
    assert "merge_level=3" in result["params_summary"]
    assert "records=1" in result["result_summary"]
    assert result["source_range"] == "2026-01-01..2026-12-31"
    assert db_observed["readonly_flags"] == [True]
    assert db_observed["connections"][0].closed is True
    assert service_observed["conn"] is db_observed["connections"][0]
    assert service_observed["kwargs"] == {
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "period": "custom",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "merge_level": 3,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": None,
        "include_compilations": True,
    }


def test_wrapped_yearly_dispatches_to_readonly_wrapped_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_observed = _patch_readonly_db(monkeypatch)
    service_observed: dict[str, Any] = {}

    def fake_build_wrapped_full(
        conn: FakeReadonlyConn,
        min_ms: int,
        music_only: bool,
        merge_enabled: bool,
        year: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        service_observed["conn"] = conn
        service_observed["args"] = (min_ms, music_only, merge_enabled, year)
        service_observed["kwargs"] = kwargs
        return {
            "year": 2026,
            "summary": {"total_plays": 77, "total_hours": 9.5},
            "top_tracks": [{"name": "Song A"}],
        }

    monkeypatch.setattr(
        tools.wrapped_service,
        "get_wrapped_full",
        lambda *args, **kwargs: pytest.fail("wrapped_yearly must not reopen cached DB"),
    )
    monkeypatch.setattr(tools.wrapped_service, "_build_wrapped_full", fake_build_wrapped_full)

    result = tool_registry.dispatch_tool(
        "wrapped_yearly",
        {
            "year": 2026,
            "min_ms": 45000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": False,
            "max_merge_gap_minutes": 45,
            "merge_level": 2,
        },
    )

    assert result["tool_name"] == "wrapped_yearly"
    assert "year=2026" in result["params_summary"]
    assert "plays=77" in result["result_summary"]
    assert result["source_range"] == "2026"
    assert db_observed["readonly_flags"] == [True]
    assert db_observed["connections"][0].closed is True
    assert service_observed["conn"] is db_observed["connections"][0]
    assert service_observed["args"] == (45000, False, False, 2026)
    assert service_observed["kwargs"] == {
        "dynamic_threshold": False,
        "max_merge_gap_minutes": 45,
        "merge_level": 2,
    }


def test_entity_stats_dispatches_to_entity_specific_readonly_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_observed = _patch_readonly_db(monkeypatch)
    service_observed: dict[str, Any] = {}

    def fake_get_album_stats(conn: FakeReadonlyConn, **kwargs: Any) -> dict[str, Any]:
        service_observed["conn"] = conn
        service_observed["kwargs"] = kwargs
        return {
            "found": True,
            "period": {
                "period": "this_year",
                "start_date": "2026-01-01",
                "end_date": "2026-06-28",
            },
            "summary": {"total_plays": 31, "total_hours": 4.2},
            "entity": {"album_name": "Album A", "artist_name": "Artist A"},
        }

    monkeypatch.setattr(tools.entity_stats_service, "get_album_stats", fake_get_album_stats)

    result = tool_registry.dispatch_tool(
        "entity_stats",
        {
            "entity": "album",
            "album_name": "Album A",
            "artist_name": "Artist A",
            "period": "this_year",
            "merge_level": 3,
        },
    )

    assert result["tool_name"] == "entity_stats"
    assert "entity=album" in result["params_summary"]
    assert "found=true" in result["result_summary"]
    assert result["source_range"] == "2026-01-01..2026-06-28"
    assert db_observed["readonly_flags"] == [True]
    assert db_observed["connections"][0].closed is True
    assert service_observed["conn"] is db_observed["connections"][0]
    assert service_observed["kwargs"] == {
        "album_name": "Album A",
        "artist": "Artist A",
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "period": "this_year",
        "start_date": None,
        "end_date": None,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": None,
        "merge_level": 3,
    }


def test_entity_stats_rejects_missing_entity_identifier() -> None:
    with pytest.raises(ValidationError, match="track_id is required"):
        tool_registry.dispatch_tool("entity_stats", {"entity": "track"})


def test_album_project_tools_return_unavailable_without_bootstrapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_readonly_db(monkeypatch, album_projects_ready=False)
    monkeypatch.setattr(
        tools.entity_stats_service,
        "get_album_stats",
        lambda *args, **kwargs: pytest.fail("read-only Agent tool must not bootstrap albums"),
    )

    result = tool_registry.dispatch_tool(
        "entity_stats",
        {"entity": "album", "album_name": "Album A", "artist_name": "Artist A"},
    )

    assert result["tool_name"] == "entity_stats"
    assert result["result_summary"] == "album_project_data_unavailable"
    assert result["source_range"] == "album_projects:not_ready"
    assert result["data"]["found"] is False


def test_billboard_entity_detail_dispatches_with_default_billboard_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_observed = _patch_readonly_db(monkeypatch)
    service_observed: dict[str, Any] = {}

    def fake_get_album_chart_detail(*args: Any, **kwargs: Any) -> dict[str, Any]:
        service_observed["args"] = args
        service_observed["kwargs"] = kwargs
        return {
            "found": True,
            "album_name": "Album A",
            "artist_name": "Artist A",
            "summary": {"weeks_on_chart": 8, "peak_position": 2},
            "history": [{"week": "2026-01-02", "rank": 2}],
        }

    monkeypatch.setattr(
        tools.billboard_details,
        "get_album_chart_detail",
        fake_get_album_chart_detail,
    )

    result = tool_registry.dispatch_tool(
        "billboard_entity_detail",
        {
            "entity": "album",
            "album_name": "Album A",
            "artist_name": "Artist A",
            "year_start": 2026,
            "year_end": 2026,
            "merge_level": 3,
        },
    )

    assert result["tool_name"] == "billboard_entity_detail"
    assert "entity=album" in result["params_summary"]
    assert "weeks=8" in result["result_summary"]
    assert result["source_range"] == "2026..2026"
    assert db_observed["readonly_flags"] == [True]
    assert db_observed["connections"][0].closed is True
    assert service_observed["args"][0:2] == ("Album A", "Artist A")
    assert service_observed["args"][2:11] == (
        30000,
        True,
        30,
        20,
        20,
        4,
        0,
        2026,
        2026,
    )
    assert service_observed["kwargs"] == {
        "dynamic_threshold": True,
        "max_merge_gap_minutes": None,
        "merge_level": 3,
    }


def test_billboard_album_detail_summary_uses_album_chart_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_readonly_db(monkeypatch)

    def fake_get_album_chart_detail(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        return {
            "found": True,
            "album_name": "The Life of a Showgirl",
            "artist_name": "Taylor Swift",
            "chart_summary": {
                "peak_position": 1,
                "weeks_on_chart": 34,
                "no1_weeks": 13,
                "power_score": 10087,
                "power_rank": 9,
            },
            "album_weekly_history": [
                {"week": "2025-10-03", "rank": 1},
                {"week": "2025-10-10", "rank": 1},
            ],
        }

    monkeypatch.setattr(
        tools.billboard_details,
        "get_album_chart_detail",
        fake_get_album_chart_detail,
    )

    result = tool_registry.dispatch_tool(
        "billboard_entity_detail",
        {
            "entity": "album",
            "album_name": "The Life of a Showgirl",
            "artist_name": "Taylor Swift",
            "merge_level": 2,
        },
    )

    assert "album=The Life of a Showgirl" in result["result_summary"]
    assert "weeks=34" in result["result_summary"]
    assert "peak=1" in result["result_summary"]
    assert "no1_weeks=13" in result["result_summary"]
    assert "power_score=10087" in result["result_summary"]
    assert "power_rank=9" in result["result_summary"]


def test_listening_hours_dispatches_selected_readonly_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_observed = _patch_readonly_db(monkeypatch)
    service_observed: dict[str, Any] = {}

    def fake_get_late_night_ratio(conn: FakeReadonlyConn, **kwargs: Any) -> list[dict[str, Any]]:
        service_observed["conn"] = conn
        service_observed["kwargs"] = kwargs
        return [{"year": 2026, "rate": 12.5}]

    monkeypatch.setattr(
        tools.play_service,
        "get_late_night_ratio",
        fake_get_late_night_ratio,
    )

    result = tool_registry.dispatch_tool(
        "listening_hours",
        {
            "view": "late_night_ratio",
            "min_ms": 60000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": False,
            "max_merge_gap_minutes": 30,
        },
    )

    assert result["tool_name"] == "listening_hours"
    assert "view=late_night_ratio" in result["params_summary"]
    assert "items=1" in result["result_summary"]
    assert result["source_range"] == "late_night_ratio"
    assert db_observed["readonly_flags"] == [True]
    assert db_observed["connections"][0].closed is True
    assert service_observed["conn"] is db_observed["connections"][0]
    assert service_observed["kwargs"] == {
        "min_ms": 60000,
        "music_only": False,
        "merge_enabled": False,
        "dynamic_threshold": False,
        "max_merge_gap_minutes": 30,
    }


def test_listening_hours_rejects_unknown_view() -> None:
    with pytest.raises(ValidationError):
        tool_registry.dispatch_tool("listening_hours", {"view": "raw_sql"})

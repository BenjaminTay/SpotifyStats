from __future__ import annotations

import pytest

from backend.domains.ai_reports.agentic_tools import (
    REPORT_TOOL_NAMES,
    execute_report_tool,
    list_report_tools,
)

pytestmark = pytest.mark.unit


def test_report_tool_registry_is_read_only_and_report_scoped():
    tools = list_report_tools()
    names = {tool["name"] for tool in tools}

    assert REPORT_TOOL_NAMES <= names
    assert all(tool["read_only"] is True for tool in tools)
    assert "arbitrary_sql" not in names
    assert "fetch_url" not in names
    assert "settings_update" not in names


def test_report_period_context_tool_uses_supplied_latest_play_date():
    result = execute_report_tool(
        "report_period_context",
        {"year": 2026, "latest_play_date": "2026-06-23"},
    )

    assert result["ok"] is True
    assert result["data"]["year"] == 2026
    assert result["data"]["is_partial_year"] is True
    assert result["data"]["start_date"] == "2026-01-01"
    assert result["data"]["end_date"] == "2026-06-23"
    assert "2025-06-23" in result["summary"]


def test_report_period_context_tool_uses_real_reporting_period_when_latest_missing(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "reporting_period": {
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-06-23",
                "is_partial_year": True,
            }
        },
    )

    result = execute_report_tool("report_period_context", {"year": 2026})

    assert result["ok"] is True
    assert result["data"]["end_date"] == "2026-06-23"
    assert result["data"]["is_partial_year"] is True
    assert "2026-06-23" in result["summary"]
    assert "2025-06-23" in result["summary"]


def test_unknown_report_tool_is_rejected():
    with pytest.raises(ValueError, match="Unknown report tool"):
        execute_report_tool("arbitrary_sql", {"sql": "select * from plays"})


def test_yearly_overview_tool_summarizes_wrapped_payload(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "reporting_period": {
                "year": 2026,
                "start_date": "2026-01-01",
                "end_date": "2026-06-23",
                "is_partial_year": True,
            },
            "hero": {
                "total_plays": 7860,
                "total_minutes": 29882,
                "unique_tracks": 2060,
                "unique_artists": 328,
                "active_days": 174,
            },
        },
    )

    result = execute_report_tool("yearly_overview", {"year": 2026})

    assert result["ok"] is True
    assert result["data"]["hero"]["total_plays"] == 7860
    assert "7,860" in result["summary"]
    assert "498" in result["summary"]


def test_yearly_top_entities_tool_returns_artists_tracks_and_albums(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "top_artists": [{"name": "Taylor Swift", "plays": 1115}],
            "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
            "top_albums": [
                {"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}
            ],
        },
    )

    result = execute_report_tool("yearly_top_entities", {"year": 2026})

    assert result["ok"] is True
    assert result["data"]["top_albums"][0]["name"] == "The Life of a Showgirl"
    assert "Taylor Swift" in result["summary"]
    assert "The Life of a Showgirl" in result["summary"]


def test_personal_billboard_year_end_tool_returns_caveat(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "billboard_year_end": {
                "available": True,
                "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
                "albums": [
                    {
                        "name": "The Life of a Showgirl",
                        "rank": 1,
                        "weeks_on_chart": 24,
                    }
                ],
                "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
                "caveat": "这是本地个人 Billboard Year-End，不是外部官方 Billboard 榜单。",
            }
        },
    )

    result = execute_report_tool("personal_billboard_year_end", {"year": 2026})

    assert result["ok"] is True
    assert result["data"]["available"] is True
    assert "不是外部官方" in result["data"]["caveat"]
    assert "Opalite" in result["summary"]


def test_billboard_yearly_diagnostics_extracts_dominance_and_alignment(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "billboard_year_end": {
                "available": True,
                "tracks": [
                    {
                        "name": "Opalite",
                        "artist": "Taylor Swift",
                        "rank": 1,
                        "weeks_on_chart": 19,
                        "weeks_at_no1": 6,
                    }
                ],
                "albums": [
                    {
                        "name": "The Life of a Showgirl",
                        "artist": "Taylor Swift",
                        "rank": 1,
                        "weeks_on_chart": 24,
                        "weeks_at_no1": 5,
                    }
                ],
                "artists": [
                    {
                        "name": "Taylor Swift",
                        "rank": 1,
                        "weeks_on_chart": 25,
                        "weeks_at_no1": 9,
                    }
                ],
            },
            "new_artists": [{"name": "Zhang Zhen Yue", "plays": 574, "first_date": "2026-03-09"}],
        },
    )

    result = execute_report_tool("billboard_yearly_diagnostics", {"year": 2026})

    assert result["ok"] is True
    assert result["data"]["dominance"]["artist"] == "Taylor Swift"
    assert result["data"]["cross_chart_alignment"][0]["entity"] == "Taylor Swift"
    assert (
        "artist_album_track_all_strong" in result["data"]["cross_chart_alignment"][0]["alignment"]
    )
    assert result["data"]["breakout_leaders"][0]["entity"] == "Zhang Zhen Yue"


def test_report_supporting_tools_return_real_yearly_fragments(monkeypatch):
    from backend.domains.ai_reports import agentic_tools

    monkeypatch.setattr(
        agentic_tools,
        "_gather_yearly_data_for_tool",
        lambda params: {
            "year_over_year": {
                "comparison_basis": "same_period_ytd",
                "same_period": {"available": True, "changes": {"plays_change": -10.0}},
            },
            "genre_summary": {
                "top_genres": [{"name": "mandopop", "share": 14.4}],
                "caveat": "Spotify 流派标签可能重叠。",
            },
            "new_artists": [{"name": "Zhang Zhen Yue", "plays": 574}],
            "longest_love": {"track_name": "Nothing New", "days": 1450},
            "most_active_day": {
                "date": "2026-04-03",
                "plays": 143,
                "interpretation_guidance": "多曲目活跃日",
            },
        },
    )

    comparison = execute_report_tool("yearly_same_period_comparison", {"year": 2026})
    genres = execute_report_tool("genre_distribution", {"year": 2026})
    discovery = execute_report_tool("discovery_and_returns", {"year": 2026})
    highlight = execute_report_tool("highlight_day_detail", {"year": 2026})

    assert comparison["data"]["comparison_basis"] == "same_period_ytd"
    assert "同比" in comparison["summary"]
    assert genres["data"]["top_genres"][0]["name"] == "mandopop"
    assert "mandopop" in genres["summary"]
    assert discovery["data"]["new_artists"][0]["name"] == "Zhang Zhen Yue"
    assert "Zhang Zhen Yue" in discovery["summary"]
    assert highlight["data"]["date"] == "2026-04-03"
    assert "多曲目活跃日" in highlight["summary"]

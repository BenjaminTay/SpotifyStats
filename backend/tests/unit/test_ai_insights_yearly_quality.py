from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from backend.core.migrations import migrate_024
from backend.services import ai_insights_service as svc

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _isolated_metadata_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep report cache-key tests independent from the user's production DB."""
    db_path = tmp_path / "report_metadata.db"
    conn = sqlite3.connect(db_path)
    try:
        migrate_024(conn)
    finally:
        conn.close()

    def get_test_db(readonly: bool = False) -> sqlite3.Connection:
        del readonly
        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        return test_conn

    monkeypatch.setattr(svc, "get_db", get_test_db)


def _conn_with_play_dates(tmp_path: Path, dates: list[str]) -> sqlite3.Connection:
    db_path = tmp_path / "yearly_quality.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE plays (play_id INTEGER PRIMARY KEY, ts_date TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO plays (play_id, ts_date) VALUES (?, ?)",
        [(index + 1, date) for index, date in enumerate(dates)],
    )
    conn.commit()
    return conn


def _wrapped_payload() -> dict[str, Any]:
    return {
        "empty": False,
        "hero": {
            "total_minutes": 29882.0,
            "total_plays": 7860,
            "unique_tracks": 2060,
            "unique_artists": 328,
            "active_days": 174,
            "avg_minutes_per_day": 171.7,
        },
        "personality": {
            "primary": "binger",
            "primary_label": "能量引擎",
            "dimensions": {
                "explorer": {"score": 65.5},
                "loyalist": {"score": 70.9},
                "binger": {"score": 71.6},
                "night_owl": {"score": 24.0},
                "collector": {"score": 11.7},
                "trend_chaser": {"score": 26.8},
                "globetrotter": {"score": 68.3},
            },
        },
        "top_lists": {
            "artists": [
                {"rank": 1, "name": "Taylor Swift", "plays": 1115, "hours": 68.8},
                {"rank": 2, "name": "Olivia Rodrigo", "plays": 769, "hours": 45.8},
            ],
            "tracks": [
                {
                    "rank": 1,
                    "name": "Opalite",
                    "artist_name": "Taylor Swift",
                    "plays": 123,
                    "hours": 7.9,
                },
                {
                    "rank": 2,
                    "name": "drop dead",
                    "artist_name": "Olivia Rodrigo",
                    "plays": 110,
                    "hours": 6.7,
                },
            ],
            "albums": [
                {
                    "rank": 1,
                    "name": "The Life of a Showgirl",
                    "artist_name": "Taylor Swift",
                    "plays": 500,
                    "hours": 29.9,
                },
                {
                    "rank": 2,
                    "name": "you seem pretty sad for a girl so in love",
                    "artist_name": "Olivia Rodrigo",
                    "plays": 396,
                    "hours": 25.9,
                },
                {
                    "rank": 3,
                    "name": "GUTS",
                    "artist_name": "Olivia Rodrigo",
                    "plays": 265,
                    "hours": 14.0,
                },
                {
                    "rank": 4,
                    "name": "跟著感覺走",
                    "artist_name": "Zhang Zhen Yue",
                    "plays": 221,
                    "hours": 14.8,
                },
            ],
        },
        "genre_panorama": {
            "top_genres": [
                {"name": "其他流派", "play_share": 19.1},
                {"name": "mandopop", "play_share": 14.4},
                {"name": "c-pop", "play_share": 14.4},
            ],
            "coverage": {
                "known_pct": 80.9,
                "unknown_pct": 19.1,
                "known_hours": 420.0,
                "unknown_hours": 99.2,
                "source_hours": {"spotify": 310.0, "curated_seed": 110.0},
            },
            "caveat": "Spotify 与本地补全流派标签可能重叠，百分比不互斥。",
        },
        "time_story": {"late_night": {"ratio": 12.0}},
        "discovery_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "plays": 574, "first_date": "2026-03-09"}],
            "longest_love": {
                "name": "Nothing New (feat. Phoebe Bridgers) (Taylor's Version)",
                "artist_name": "Taylor Swift",
                "span_days": 1450,
            },
        },
        "special_moments": {
            "most_active_day": {
                "date": "2026-04-03",
                "plays": 143,
                "top_track": {"name": "Changes", "artist_name": "Charlie Puth", "plays": 4},
            }
        },
        "comparison": {
            "last_year": {
                "total_hours_change": -56.1,
                "plays_change": -55.3,
                "tracks_change": -25.3,
                "artists_change": -28.0,
                "active_days_change": -52.2,
            }
        },
    }


def _year_end_payload() -> dict[str, Any]:
    return {
        "meta": {
            "year": 2026,
            "total_weeks": 25,
            "score_label": "Year-End Score",
            "semantics_version": "year_end_v4",
            "coverage_status": "year_to_date",
            "is_complete_year": False,
            "period_start": "2026-01-02T00:00:00",
            "period_end": "2026-06-19T00:00:00",
            "observed_weeks": 25,
            "expected_weeks": 52,
            "weekly_top_n": 25,
            "weekly_album_top_n": 15,
            "weekly_artist_top_n": 15,
        },
        "tracks": [
            {
                "year_end_rank": 1,
                "year_end_score": 3348,
                "peak_position": 1,
                "weeks_on_chart": 19,
                "weeks_at_no1": 6,
                "chart_plays": 117,
                "annual_plays": 126,
                "track_name": "Opalite",
                "artist_name": "Taylor Swift",
            },
            {
                "year_end_rank": 3,
                "year_end_score": 1936,
                "peak_position": 1,
                "weeks_on_chart": 9,
                "weeks_at_no1": 2,
                "chart_plays": 110,
                "track_name": "drop dead",
                "artist_name": "Olivia Rodrigo",
            },
        ],
        "albums": [
            {
                "year_end_rank": 1,
                "year_end_score": 5352,
                "peak_position": 1,
                "weeks_on_chart": 24,
                "weeks_at_no1": 5,
                "chart_plays": 494,
                "album_name": "The Life of a Showgirl",
                "artist_name": "Taylor Swift",
            },
            {
                "year_end_rank": 3,
                "year_end_score": 2435,
                "peak_position": 2,
                "weeks_on_chart": 16,
                "weeks_at_no1": 0,
                "chart_plays": 221,
                "album_name": "跟著感覺走",
                "artist_name": "Zhang Zhen Yue",
            },
        ],
        "artists": [
            {
                "year_end_rank": 1,
                "year_end_score": 7149,
                "peak_position": 1,
                "weeks_on_chart": 25,
                "weeks_at_no1": 9,
                "chart_plays": 1108,
                "artist_name": "Taylor Swift",
            },
            {
                "year_end_rank": 4,
                "year_end_score": 3722,
                "peak_position": 1,
                "weeks_on_chart": 16,
                "weeks_at_no1": 4,
                "chart_plays": 574,
                "artist_name": "Zhang Zhen Yue",
            },
        ],
        "honors": {},
    }


def test_gather_yearly_data_preserves_names_and_marks_partial_year(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(
        wrapped_service, "get_wrapped_full", lambda *args, **kwargs: _wrapped_payload()
    )
    monkeypatch.setattr(
        svc,
        "build_same_period_comparison",
        lambda *args, **kwargs: {"mode": "same_period_ytd", "available": True},
        raising=False,
    )

    data = svc._gather_yearly_data(
        conn,
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        year=2026,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
    )

    assert data["reporting_period"]["start_date"] == "2026-01-01"
    assert data["reporting_period"]["end_date"] == "2026-06-23"
    assert data["reporting_period"]["is_partial_year"] is True
    assert data["reporting_period"]["label"] == "2026 年截至 2026-06-23"
    assert data["top_artists"][0]["name"] == "Taylor Swift"
    assert data["top_tracks"][0]["name"] == "Opalite"
    assert data["top_tracks"][0]["artist"] == "Taylor Swift"
    assert data["new_artists"][0]["name"] == "Zhang Zhen Yue"
    assert svc._extract_entities(data) == {
        "artists": ["Taylor Swift", "Olivia Rodrigo"],
        "tracks": ["Opalite", "drop dead"],
    }


def test_gather_yearly_data_normalizes_personality_and_genres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(
        wrapped_service, "get_wrapped_full", lambda *args, **kwargs: _wrapped_payload()
    )
    monkeypatch.setattr(
        svc,
        "build_same_period_comparison",
        lambda *args, **kwargs: {"mode": "same_period_ytd", "available": True},
        raising=False,
    )

    data = svc._gather_yearly_data(conn, 30000, True, True, 2026)

    top_dimensions = data["personality_summary"]["top_dimensions"]
    assert top_dimensions[0] == {"key": "binger", "label": "能量引擎", "score": 71.6}
    assert {"key": "loyalist", "label": "专一者", "score": 70.9} in top_dimensions
    assert data["genre_summary"]["top_genres"][0] == {"name": "其他流派", "share": 19.1}
    assert data["genre_summary"]["has_other_bucket"] is True
    assert "可能重叠" in data["genre_summary"]["caveat"]
    assert data["genre_summary"]["coverage"]["known_pct"] == 80.9
    assert data["genre_summary"]["coverage"]["unknown_pct"] == 19.1
    assert data["genre_summary"]["source_hours"] == {"spotify": 310.0, "curated_seed": 110.0}


def test_gather_yearly_data_includes_albums_billboard_and_editorial_brief(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(
        wrapped_service,
        "get_wrapped_full",
        lambda *args, **kwargs: _wrapped_payload(),
    )
    monkeypatch.setattr(
        svc,
        "build_same_period_comparison",
        lambda *args, **kwargs: {"mode": "same_period_ytd", "available": True},
        raising=False,
    )
    monkeypatch.setattr(
        svc,
        "_compute_year_end_for_yearly_report",
        lambda *args, **kwargs: _year_end_payload(),
        raising=False,
    )

    data = svc._gather_yearly_data(
        conn,
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        year=2026,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
    )

    assert data["top_albums"][0]["name"] == "The Life of a Showgirl"
    assert data["top_albums"][3]["artist"] == "Zhang Zhen Yue"
    assert data["billboard_year_end"]["tracks"][0]["name"] == "Opalite"
    assert data["billboard_year_end"]["tracks"][0]["plays"] == 126
    assert data["billboard_year_end"]["tracks"][0]["chart_plays"] == 117
    assert data["billboard_year_end"]["meta"]["coverage_status"] == "year_to_date"
    assert data["billboard_year_end"]["albums"][0]["name"] == "The Life of a Showgirl"
    assert data["billboard_year_end"]["artists"][0]["name"] == "Taylor Swift"
    assert data["editorial_brief"]["thesis"]
    assert "Taylor Swift" in data["editorial_brief"]["thesis"]
    assert "Olivia Rodrigo" in data["editorial_brief"]["thesis"]
    assert "Zhang Zhen Yue" in data["editorial_brief"]["thesis"]
    assert "album" in data["editorial_brief"]["required_angles"]
    assert "personal_billboard" in data["editorial_brief"]["required_angles"]


def test_reporting_period_can_be_derived_from_effective_yearly_frame():
    import pandas as pd

    from backend.domains.ai_reports.yearly_contract import build_reporting_period_from_frame

    year_df = pd.DataFrame(
        [
            {"ts_date": "2026-01-01"},
            {"ts_date": "2026-06-20"},
            {"ts_date": "2026-06-20"},
        ]
    )

    period = build_reporting_period_from_frame(year_df, 2026)

    assert period["start_date"] == "2026-01-01"
    assert period["end_date"] == "2026-06-20"
    assert period["active_days"] == 2
    assert period["days_covered"] == 171
    assert period["is_partial_year"] is True
    assert "截至 2026-06-20" in period["label"]


def test_generate_yearly_story_retries_invalid_partial_year_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(
        wrapped_service, "get_wrapped_full", lambda *args, **kwargs: _wrapped_payload()
    )
    monkeypatch.setattr(
        svc,
        "build_same_period_comparison",
        lambda *args, **kwargs: {"mode": "same_period_ytd", "available": True},
        raising=False,
    )
    monkeypatch.setattr(svc, "_get_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr(svc, "_get_llm", lambda *args, **kwargs: object())

    cached: list[str] = []
    monkeypatch.setattr(svc, "_set_cache", lambda _conn, _key, report: cached.append(report))

    calls: list[str] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        calls.append(user_content)
        if len(calls) == 1:
            return "## 来年寄语\n这一年你少听了 55%，也许某个下雨夜晚改变了你。"
        return "## 2026 年中总结\n截至 2026-06-23，你最常听 Taylor Swift，Opalite 是最突出的歌曲；The Life of a Showgirl 是最突出的专辑；新艺人 Zhang Zhen Yue 很突出；其他流派也是重要类别之一；流派标签可能重叠，不应视为互斥；同期比较需要按 YTD 口径理解。"

    monkeypatch.setattr(svc, "_llm_chat", fake_llm_chat)

    result = svc.generate_yearly_story(conn, 30000, True, True, 2026, dynamic_threshold=True)

    assert result["success"] is True
    assert "截至 2026-06-23" in result["report"]
    assert "下雨夜晚" not in result["report"]
    assert len(calls) == 2
    assert "VALIDATION_FEEDBACK" in calls[1]
    assert "missing_partial_year_cutoff" in calls[1]
    assert "unsupported_scene" in calls[1]
    assert cached == [result["report"]]


def test_generate_yearly_story_allows_second_validation_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(
        wrapped_service, "get_wrapped_full", lambda *args, **kwargs: _wrapped_payload()
    )
    monkeypatch.setattr(
        svc,
        "build_same_period_comparison",
        lambda *args, **kwargs: {"mode": "same_period_ytd", "available": True},
        raising=False,
    )
    monkeypatch.setattr(svc, "_get_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr(svc, "_get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(svc, "_set_cache", lambda *args, **kwargs: None)

    calls: list[float] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        calls.append(temperature)
        if len(calls) == 1:
            return "## 来年寄语\n这一年已经结束，Taylor Swift 和 Opalite 陪你走过雨夜。"
        if len(calls) == 2:
            return "## 2026 年中总结\n截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、Zhang Zhen Yue 和其他流派都很突出。Spotify 流派标签可能重叠。Zhang Zhen Yue 的歌词中充满都市漂泊感，她的播放量也很突出。"
        return "## 2026 年中总结\n截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、Zhang Zhen Yue 和其他流派都很突出。Spotify 流派标签可能重叠。同期比较按 YTD 口径理解，报告直接基于播放记录描述。"

    monkeypatch.setattr(svc, "_llm_chat", fake_llm_chat)

    result = svc.generate_yearly_story(conn, 30000, True, True, 2026, dynamic_threshold=True)

    assert result["success"] is True
    assert len(calls) == 3
    assert calls == [0.2, 0.15, 0.1]
    assert "歌词中" not in result["report"]
    assert "她的播放量" not in result["report"]


def test_yearly_prompt_contains_partial_year_and_grounding_rules():
    prompt = svc.YEARLY_STORY_SYSTEM

    assert "reporting_period" in prompt
    assert "is_partial_year=true" in prompt
    assert "year_over_year.same_period" in prompt
    assert "top_albums" in prompt
    assert "billboard_year_end.available=true" in prompt
    assert "editorial_brief.thesis" in prompt
    assert "只允许集中写一次" in prompt
    assert "有意识地" in prompt
    assert "不要解读歌词" in prompt
    assert "不要推断艺人性别" in prompt
    assert "不要翻译或添加别名" in prompt
    assert "不要把日均写成夜晚" in prompt
    assert "不要使用第一人称" in prompt
    assert "不要使用“前者/后者”" in prompt
    assert "personality_summary.top_dimensions" in prompt
    assert "不要编造" in prompt


def test_yearly_validator_flags_required_severe_issues():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {
            "is_partial_year": True,
            "end_date": "2026-06-23",
        },
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "genre_summary": {"has_other_bucket": True},
    }

    validation = validate_yearly_report(
        "## 全年总结\n这一年已经结束。来年寄语：某个下雨夜晚改变了你。",
        data,
    )

    assert validation.ok is False
    codes = {issue.code for issue in validation.issues}
    assert {
        "missing_partial_year_cutoff",
        "partial_year_written_as_full_year",
        "missing_top_artist",
        "missing_top_track",
        "unsupported_scene",
        "missing_other_genre_bucket",
    } <= codes


def test_yearly_validator_requires_album_and_billboard_evidence_when_available():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "new_artists": [{"name": "Zhang Zhen Yue"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
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
        },
    }

    validation = validate_yearly_report(
        "## 2026 年中总结\n截至 2026-06-23，Taylor Swift 和 Opalite 领先，Zhang Zhen Yue 是新发现，其他流派也很重要。流派标签可能重叠。",
        data,
    )

    assert validation.ok is False
    codes = {issue.code for issue in validation.issues}
    assert "missing_top_album" in codes
    assert "missing_billboard_year_end_evidence" in codes


def test_yearly_validator_rejects_official_billboard_misstatement():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "new_artists": [{"name": "Zhang Zhen Yue"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
        "billboard_year_end": {
            "available": True,
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、Zhang Zhen Yue 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。外部官方 Billboard 年榜里 Opalite 排名第 1，19 周在榜。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is False
    assert "billboard_scope_misstatement" in {issue.code for issue in validation.issues}


def test_yearly_validator_requires_personal_billboard_caveat_when_available():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "new_artists": [{"name": "Zhang Zhen Yue"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
        "billboard_year_end": {
            "available": True,
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、Zhang Zhen Yue 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。Billboard 年榜里 Opalite 排名第 1，19 周在榜。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is False
    assert "missing_personal_billboard_caveat" in {issue.code for issue in validation.issues}


def test_yearly_validator_allows_negated_official_billboard_caveat():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "new_artists": [{"name": "Zhang Zhen Yue"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
        "billboard_year_end": {
            "available": True,
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、Zhang Zhen Yue 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。个人 Billboard 年榜里 Opalite 排名第 1，19 周在榜；"
        "这是基于本地播放记录计算的个人榜，不是外部官方 Billboard。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is True


def test_yearly_validator_rejects_full_year_partial_year_phrasing():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": False, "end_date": "2025-12-31"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "genre_summary": {"has_other_bucket": False},
    }
    report = (
        "## 2025 年中音乐报告\n"
        "Taylor Swift、Opalite 与 The Life of a Showgirl 是这一年的核心。"
        "下半年观察：后续可以继续关注这些主线。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is False
    assert "full_year_written_as_partial_year" in {issue.code for issue in validation.issues}


def test_yearly_validator_rejects_repeated_comparison_and_unsupported_intent():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "new_artists": [{"name": "Zhang Zhen Yue"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
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
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，与去年同期相比播放下降 10%，曲目增长 23.3%。"
        "Taylor Swift、Opalite、The Life of a Showgirl、Zhang Zhen Yue 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。个人 Billboard 年榜里 Opalite 排名第 1，19 周在榜。"
        "## 时间之外\n"
        "与去年同期相比，你播放下降 10%，曲目增长 23.3%，说明你有意识地拓宽音乐版图。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is False
    codes = {issue.code for issue in validation.issues}
    assert "duplicated_same_period_comparison" in codes
    assert "unsupported_intent_claim" in codes


def test_yearly_validator_rejects_unsupported_lyric_and_gender_claims():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "new_artists": [{"name": "Zhang Zhen Yue"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
        "billboard_year_end": {
            "available": True,
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、Zhang Zhen Yue 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。个人 Billboard 年榜里 Opalite 排名第 1，19 周在榜。"
        "Zhang Zhen Yue 的歌词中充满都市漂泊感，她的播放量也很突出。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is False
    codes = {issue.code for issue in validation.issues}
    assert "unsupported_lyric_claim" in codes
    assert "unsupported_gender_claim" in codes


def test_yearly_validator_rejects_unprovided_entity_aliases():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "new_artists": [{"name": "Zhang Zhen Yue"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、张真源（Zhang Zhen Yue）和其他流派都很突出。"
        "Spotify 流派标签可能重叠。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is False
    assert "unsupported_entity_alias" in {issue.code for issue in validation.issues}


def test_yearly_validator_allows_generic_parenthesized_context_before_entity_name():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "new_artists": [{"name": "Zhang Zhen Yue"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、Zhang Zhen Yue 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。今年形成了稳定中心和一条新入口（Zhang Zhen Yue）。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is True


def test_yearly_report_sanitizer_neutralizes_gender_pronouns():
    report = "Zhang Zhen Yue 以 574 次播放进入前三，他无疑是新发现；她的专辑也进入前五。"

    sanitized = svc._sanitize_yearly_report_text(report)

    assert "他无疑" not in sanitized
    assert "她的专辑" not in sanitized
    assert "该艺人无疑" in sanitized
    assert "该艺人的专辑" in sanitized


def test_yearly_fallback_uses_full_year_labels_for_complete_period():
    data = {
        "year": 2025,
        "reporting_period": {
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "active_days": 365,
            "is_partial_year": False,
        },
        "hero": {
            "total_minutes": 60000,
            "total_plays": 10000,
            "unique_tracks": 2000,
            "unique_artists": 300,
        },
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1000},
            {"name": "Olivia Rodrigo", "plays": 800},
        ],
        "top_tracks": [{"name": "Opalite", "plays": 100}],
        "top_albums": [{"name": "The Life of a Showgirl", "plays": 400}],
        "new_artists": [{"name": "Zhang Zhen Yue", "plays": 100, "first_date": "2025-03-01"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 20.0}],
        },
        "personality_summary": {
            "top_dimensions": [{"label": "能量引擎", "score": 70.0}],
        },
        "billboard_year_end": {"available": False},
    }

    report = svc._build_yearly_report_fallback(data)

    assert "年中" not in report
    assert "下半年观察" not in report
    assert "2025 年音乐报告" in report
    assert "后续观察" in report


def test_yearly_fallback_omits_missing_sparse_entities_cleanly():
    data = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "end_date": "2026-06-23",
            "active_days": 1,
            "is_partial_year": True,
        },
        "hero": {
            "total_minutes": 12,
            "total_plays": 3,
            "unique_tracks": 1,
            "unique_artists": 1,
        },
        "top_artists": [{"name": "Taylor Swift", "plays": 3}],
        "top_tracks": [{"name": "Opalite", "plays": 3}],
        "top_albums": [],
        "new_artists": [],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 100.0}],
        },
        "personality_summary": {"top_dimensions": []},
        "billboard_year_end": {"available": False},
    }

    report = svc._build_yearly_report_fallback(data)

    assert "贡献另一条主线" not in report
    assert "首次出现于 " not in report
    assert "以  次播放" not in report
    assert "专辑榜首是 （" not in report
    assert "Taylor Swift" in report
    assert "Opalite" in report


def test_yearly_fallback_handles_artist_only_billboard_evidence():
    data = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "end_date": "2026-06-23",
            "active_days": 10,
            "is_partial_year": True,
        },
        "hero": {
            "total_minutes": 120,
            "total_plays": 50,
            "unique_tracks": 20,
            "unique_artists": 5,
        },
        "top_artists": [{"name": "Taylor Swift", "plays": 30}],
        "top_tracks": [{"name": "Opalite", "plays": 10}],
        "top_albums": [{"name": "The Life of a Showgirl", "plays": 12}],
        "new_artists": [],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
        "personality_summary": {"top_dimensions": []},
        "billboard_year_end": {
            "available": True,
            "tracks": [],
            "albums": [],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 10}],
        },
    }

    report = svc._build_yearly_report_fallback(data)

    assert "Taylor Swift 位列艺人年榜第 1" in report
    assert " 位列单曲年榜第 " not in report
    assert " 位列专辑年榜第 " not in report


def test_yearly_validator_rejects_unsupported_time_of_day_claims():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。每晚平均 171.7 分钟的音乐陪伴让日常更丰盈。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is False
    assert "unsupported_time_of_day_claim" in {issue.code for issue in validation.issues}


def test_yearly_validator_rejects_first_person_and_flowery_intent_claims():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "new_artists": [{"name": "Zhang Zhen Yue"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl、Zhang Zhen Yue 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。Zhang Zhen Yue 是今年最让我惊喜的新发现，你不再重播旧爱，而是转身拥抱更广阔的声音世界。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is False
    codes = {issue.code for issue in validation.issues}
    assert "unsupported_first_person_claim" in codes
    assert "unsupported_intent_claim" in codes


def test_yearly_validator_rejects_overlong_and_ambiguous_reference_reports():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。前者在个人专辑年榜上排名第 3 和第 4。" + "补充说明。" * 300
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is False
    codes = {issue.code for issue in validation.issues}
    assert "yearly_report_too_long" in codes
    assert "ambiguous_entity_reference" in codes


def test_yearly_validator_allows_negated_low_confidence_looping_phrase():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {"is_partial_year": True, "end_date": "2026-06-23"},
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
        "most_active_day": {
            "date": "2026-04-03",
            "plays": 143,
            "top_track": {"name": "Changes", "plays": 4},
        },
    }
    report = (
        "## 2026 年中总结\n"
        "截至 2026-06-23，Taylor Swift、Opalite、The Life of a Showgirl 和其他流派都很突出。"
        "Spotify 流派标签可能重叠。4 月 3 日是高度多样化的一天，而非单曲循环日。"
    )

    validation = validate_yearly_report(report, data)

    assert validation.ok is True


def test_yearly_validator_accepts_chinese_cutoff_date_format():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {
            "is_partial_year": True,
            "end_date": "2026-06-23",
        },
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "genre_summary": {"has_other_bucket": True},
    }

    validation = validate_yearly_report(
        "## 2026 年中总结\n截至 2026 年 6 月 23 日，Taylor Swift 和 Opalite 是重点；其他流派也很重要。",
        data,
    )

    assert validation.ok is True


def test_yearly_validator_rejects_synonym_full_year_and_scene_claims():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {
            "is_partial_year": True,
            "end_date": "2026-06-23",
        },
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "genre_summary": {"has_other_bucket": True},
    }

    validation = validate_yearly_report(
        "## 2026 年中总结\n截至 2026 年 6 月 23 日，回望过去一年，Taylor Swift 和 Opalite 陪你走过某个雨夜，其他流派也很重要。",
        data,
    )

    assert validation.ok is False
    codes = {issue.code for issue in validation.issues}
    assert "partial_year_written_as_full_year" in codes
    assert "unsupported_scene" in codes


def test_yearly_validator_rejects_partial_year_annual_entity_labels():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {
            "is_partial_year": True,
            "end_date": "2026-06-23",
        },
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
    }

    validation = validate_yearly_report(
        "## 阶段性音乐总结\n截至 2026-06-23，Taylor Swift、Opalite 和 The Life of a Showgirl 领先，其他流派也很重要。Spotify 流派标签可能重叠。年度专辑榜前三已经形成。",
        data,
    )

    assert validation.ok is False
    assert "partial_year_written_as_full_year" in {issue.code for issue in validation.issues}


def test_yearly_validator_rejects_partial_year_full_year_comparison():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {
            "is_partial_year": True,
            "end_date": "2026-06-23",
        },
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "genre_summary": {
            "has_other_bucket": True,
            "top_genres": [{"name": "其他流派", "share": 19.1}],
        },
    }

    validation = validate_yearly_report(
        "## 2026 年中总结\n截至 2026-06-23，Taylor Swift 和 Opalite 领先，其他流派也很重要。流派标签可能重叠。和去年全年相比，你少听了 55%。",
        data,
    )

    assert validation.ok is False
    codes = {issue.code for issue in validation.issues}
    assert "partial_year_uses_full_year_comparison" in codes


def test_yearly_validator_allows_non_personality_numeric_collision():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {
            "is_partial_year": True,
            "end_date": "2026-06-23",
        },
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "personality_summary": {
            "top_dimensions": [{"label": "专一者", "score": 70.9}],
        },
        "genre_summary": {"has_other_bucket": True},
    }

    validation = validate_yearly_report(
        "## 2026 年中总结\n截至 2026-06-23，Taylor Swift 播放约 70.9 小时，Opalite 领先，其他流派也很重要。",
        data,
    )

    assert validation.ok is True


def test_yearly_validator_rejects_mismatched_personality_score_label():
    from backend.domains.ai_reports.yearly_validator import validate_yearly_report

    data = {
        "reporting_period": {
            "is_partial_year": True,
            "end_date": "2026-06-23",
        },
        "top_artists": [{"name": "Taylor Swift"}],
        "top_tracks": [{"name": "Opalite"}],
        "personality_summary": {
            "top_dimensions": [{"label": "能量引擎", "score": 71.6}],
        },
        "genre_summary": {"has_other_bucket": True},
    }

    validation = validate_yearly_report(
        "## 2026 年中总结\n截至 2026-06-23，专一者得分 71.6，Taylor Swift 和 Opalite 领先，其他流派也很重要。",
        data,
    )

    assert validation.ok is False
    assert "personality_score_without_label" in {issue.code for issue in validation.issues}


def test_same_period_comparison_uses_reporting_period_start_date():
    import pandas as pd

    from backend.domains.ai_reports.yearly_contract import build_same_period_comparison_from_frame

    plays = pd.DataFrame(
        [
            {
                "ts_date": "2025-01-15",
                "ms_played": 180000,
                "track_name": "old ignored",
                "artist_name": "A",
            },
            {
                "ts_date": "2025-05-10",
                "ms_played": 180000,
                "track_name": "old in range",
                "artist_name": "A",
            },
            {
                "ts_date": "2026-01-15",
                "ms_played": 180000,
                "track_name": "current ignored",
                "artist_name": "B",
            },
            {
                "ts_date": "2026-05-10",
                "ms_played": 360000,
                "track_name": "current in range",
                "artist_name": "B",
            },
            {
                "ts_date": "2026-06-20",
                "ms_played": 360000,
                "track_name": "current in range 2",
                "artist_name": "C",
            },
        ]
    )

    comparison = build_same_period_comparison_from_frame(
        plays,
        year=2026,
        start_date="2026-05-01",
        end_date="2026-06-23",
    )

    assert comparison is not None
    assert comparison["current_period"] == {
        "start_date": "2026-05-01",
        "end_date": "2026-06-23",
    }
    assert comparison["previous_period"] == {
        "start_date": "2025-05-01",
        "end_date": "2025-06-23",
    }
    assert comparison["current"]["plays"] == 2
    assert comparison["previous"]["plays"] == 1


def test_generate_yearly_story_uses_fallback_after_failed_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.wrapped_service as wrapped_service

    conn = _conn_with_play_dates(tmp_path, ["2026-01-01", "2026-06-23"])
    monkeypatch.setattr(
        wrapped_service,
        "get_wrapped_full",
        lambda *args, **kwargs: _wrapped_payload(),
    )
    monkeypatch.setattr(
        svc,
        "build_same_period_comparison",
        lambda *args, **kwargs: {"mode": "same_period_ytd", "available": True},
        raising=False,
    )
    monkeypatch.setattr(svc, "_get_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr(svc, "_get_llm", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        svc,
        "_llm_chat",
        lambda *args, **kwargs: "## 来年寄语\n这一年已经结束，你在某个失眠夜晚完成了转折。",
    )
    cached: list[str] = []
    monkeypatch.setattr(svc, "_set_cache", lambda _conn, _key, report: cached.append(report))

    result = svc.generate_yearly_story(
        conn,
        30000,
        True,
        True,
        2026,
        dynamic_threshold=True,
    )

    assert result["success"] is True
    assert result["error"] is None
    assert "Taylor Swift" in result["report"]
    assert "Opalite" in result["report"]
    assert "The Life of a Showgirl" in result["report"]
    assert "Zhang Zhen Yue" in result["report"]
    assert "来年寄语" not in result["report"]
    assert cached == [result["report"]]


def test_yearly_report_cache_key_includes_contract_version():
    key = svc._report_cache_key(
        "yearly",
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        year=2026,
    )

    assert key is not None
    assert "contract_v13" in key
    assert "year_end_v4" in key


def test_yearly_report_year_end_uses_persisted_billboard_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    import backend.services.billboard_service as billboard_service

    conn = sqlite3.connect(tmp_path / "settings.db")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.executemany(
        "INSERT INTO settings(key, value) VALUES (?, ?)",
        [
            ("bb_top_n", "17"),
            ("bb_album_top_n", "11"),
            ("bb_artist_top_n", "9"),
            ("bb_week_start_dow", "2"),
            ("bb_week_start_hour", "6"),
            ("include_compilations", "true"),
        ],
    )
    captured: dict[str, Any] = {}

    monkeypatch.setattr(svc, "_connection_uses_default_database", lambda _conn: True)
    monkeypatch.setattr(
        billboard_service,
        "compute_year_end_staged",
        lambda **kwargs: captured.update(kwargs) or {"meta": {"year": 2026}},
    )

    svc._compute_year_end_for_yearly_report(
        conn,
        min_ms=30000,
        music_only=True,
        year=2026,
        dynamic_threshold=True,
        max_merge_gap_minutes=45,
    )

    assert captured["bb_top_n"] == 17
    assert captured["bb_album_top_n"] == 11
    assert captured["bb_artist_top_n"] == 9
    assert captured["bb_week_start_dow"] == 2
    assert captured["bb_week_start_hour"] == 6
    assert captured["include_compilations"] is True

from __future__ import annotations

import pytest

from backend.domains.ai_agent.temporal_context import (
    apply_temporal_guard,
    build_temporal_context,
    temporal_answer_issues,
)

pytestmark = pytest.mark.unit


def test_temporal_context_uses_question_time_and_data_range() -> None:
    context = build_temporal_context(
        {
            "question_time": "2026-07-02T16:06:01+08:00",
            "timezone": "Asia/Shanghai",
        },
        data_range={"data_start_date": "2022-06-30", "data_end_date": "2026-06-22"},
    )

    assert context["question_time"] == "2026-07-02T16:06:01+08:00"
    assert context["timezone"] == "Asia/Shanghai"
    assert context["today"] == "2026-07-02"
    assert context["latest_play_date"] == "2026-06-22"
    assert context["data_start_date"] == "2022-06-30"
    assert "相对时间以 question_time 为准" in context["relative_time_policy"]


def test_temporal_guard_corrects_wrong_last_summer_tool_range() -> None:
    context = build_temporal_context(
        {
            "question_time": "2026-07-02T16:06:01+08:00",
            "timezone": "Asia/Shanghai",
        },
        data_range={"data_start_date": "2022-06-30", "data_end_date": "2026-06-22"},
    )

    guarded_plan, guard = apply_temporal_guard(
        "去年夏天我最常听什么类型的音乐？",
        context,
        [
            {
                "tool_name": "analysis_charts",
                "params": {
                    "period": "custom",
                    "start_date": "2024-06-01",
                    "end_date": "2024-08-31",
                    "entity": "artist",
                    "metric": "plays",
                },
            },
            {"tool_name": "wrapped_yearly", "params": {"year": 2024}},
        ],
    )

    assert guard["time_interpretation"]["label"] == "去年夏天"
    assert guard["time_interpretation"]["anchor_date"] == "2026-07-02"
    assert guard["time_interpretation"]["start_date"] == "2025-06-01"
    assert guard["time_interpretation"]["end_date"] == "2025-08-31"
    assert guard["time_interpretation"]["expected_year"] == 2025
    assert guard["time_interpretation"]["confidence"] == "high"
    assert guard["had_corrections"] is True
    assert guarded_plan[0]["params"]["period"] == "custom"
    assert guarded_plan[0]["params"]["start_date"] == "2025-06-01"
    assert guarded_plan[0]["params"]["end_date"] == "2025-08-31"
    assert guarded_plan[1]["params"]["year"] == 2025


def test_temporal_guard_leaves_explicit_year_question_unchanged() -> None:
    context = build_temporal_context(
        {
            "question_time": "2026-07-02T16:06:01+08:00",
            "timezone": "Asia/Shanghai",
        }
    )

    guarded_plan, guard = apply_temporal_guard(
        "2024年夏天我最常听什么类型的音乐？",
        context,
        [
            {
                "tool_name": "analysis_charts",
                "params": {
                    "period": "custom",
                    "start_date": "2024-06-01",
                    "end_date": "2024-08-31",
                    "entity": "artist",
                    "metric": "plays",
                },
            }
        ],
    )

    assert guard["time_interpretation"] is None
    assert guard["had_corrections"] is False
    assert guarded_plan[0]["params"]["start_date"] == "2024-06-01"


def test_temporal_answer_issues_only_flags_conflicting_relative_time_sentence() -> None:
    _, guard = apply_temporal_guard(
        "去年夏天我最常听什么类型的音乐？",
        build_temporal_context({"question_time": "2026-07-02T16:06:01+08:00"}),
        [],
    )


def test_last_winter_uses_cross_year_display_label_without_false_conflict() -> None:
    _, guard = apply_temporal_guard(
        "去年冬天我最常听什么歌？",
        build_temporal_context({"question_time": "2026-07-02T16:06:01+08:00"}),
        [],
    )

    interpretation = guard["time_interpretation"]
    assert interpretation["label"] == "去年冬天"
    assert interpretation["display_label"] == "2025-2026 冬天"
    assert interpretation["start_date"] == "2025-12-01"
    assert interpretation["end_date"] == "2026-02-28"
    assert interpretation["is_cross_year_season"] is True
    assert (
        temporal_answer_issues(
            "去年冬天（2025-2026 冬天，2025-12-01 至 2026-02-28）你最常听的是 Santa Tell Me。",
            guard,
        )
        == []
    )


def test_temporal_answer_issues_still_flags_wrong_last_winter_year() -> None:
    _, guard = apply_temporal_guard(
        "去年冬天我最常听什么歌？",
        build_temporal_context({"question_time": "2026-07-02T16:06:01+08:00"}),
        [],
    )

    assert temporal_answer_issues("去年冬天（2024年12月到2025年2月）你听得最多。", guard)

    assert temporal_answer_issues("去年夏天（2024年6月-8月）你听得最多。", guard)
    assert (
        temporal_answer_issues(
            "去年夏天（2025年6月-8月）你听得最多。数据截止到 2026-06-22。",
            guard,
        )
        == []
    )

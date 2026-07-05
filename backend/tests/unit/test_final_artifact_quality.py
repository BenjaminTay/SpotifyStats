from __future__ import annotations

import pytest

from backend.domains.ai_reports.final_artifact_quality import (
    evaluate_final_artifact_quality,
    final_visible_artifact_text,
)

pytestmark = pytest.mark.unit


def _artifact() -> dict:
    return {
        "title": "AI 音乐年报",
        "subtitle": "2026 · 截至 2026-06-23",
        "sections": [
            {
                "id": "stable_return",
                "heading": "最稳定的回访对象",
                "deck": "Taylor Swift 是年度重心。",
                "prose": (
                    "Taylor Swift 以 1115 次播放位列艺人榜第一。"
                    "这让年度第一不只是一个名次，而是一条你持续回到的声音。"
                ),
                "pull_quote": "Taylor Swift 以 1115 次播放位列艺人榜第一",
                "chart_refs": ["listening_calendar"],
            },
            {
                "id": "monthly_turning",
                "heading": "月度反超点",
                "deck": "Olivia Rodrigo 在 5 月短暂变亮。",
                "prose": (
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                    "这说明累计第一之外还存在阶段性变化。"
                ),
                "chart_refs": ["artist_monthly_trend"],
            },
            {
                "id": "album_longevity",
                "heading": "专辑的双重验证",
                "deck": "The Life of a Showgirl 同时具有播放热度和长留信号。",
                "prose": (
                    "The Life of a Showgirl 的播放量和个人 Billboard 专辑表现对齐，"
                    "个人榜在榜 24 周。"
                ),
                "chart_refs": ["album_duality_compare"],
            },
            {
                "id": "highlight_day",
                "heading": "高光日",
                "deck": "2026-04-03 是播放密度异常高的一天。",
                "prose": "2026-04-03 有 143 次播放，最高单曲只有 4 次，更像多曲目密集漫游。",
                "chart_refs": ["highlight_day_timeline"],
            },
            {
                "id": "new_voice",
                "heading": "新声音",
                "deck": "Zhang Zhen Yue 是今年清楚进入记录的新艺人。",
                "prose": "Zhang Zhen Yue 首次出现于 2026-03-09，累计 574 次播放。",
                "chart_refs": ["discovery_timeline"],
            },
            {
                "id": "closing",
                "heading": "这一年最终留下什么",
                "deck": "把前面的线索收束成一份可回看的音乐年记。",
                "prose": "这份年记记录的是你如何在熟悉和新鲜之间分配注意力。",
                "chart_refs": [],
            },
        ],
        "chart_specs": [
            {
                "id": "listening_calendar",
                "title": "音乐铺满当前统计期",
                "data_key": "listening_calendar",
            },
            {
                "id": "artist_monthly_trend",
                "title": "艺人月度趋势",
                "data_key": "artist_monthly_trend",
            },
            {
                "id": "album_duality_compare",
                "title": "专辑热度与长留关系",
                "data_key": "album_duality_compare",
            },
            {
                "id": "highlight_day_timeline",
                "title": "阶段高光日拆解",
                "data_key": "highlight_day_timeline",
            },
            {
                "id": "discovery_timeline",
                "title": "Zhang Zhen Yue 出现以后",
                "data_key": "discovery_timeline",
            },
        ],
        "chart_data": {
            "listening_calendar": {"observations": ["活跃 174 天。"]},
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ]
            },
            "album_duality_compare": {"observations": ["播放量和持续在榜指向同一张专辑。"]},
            "highlight_day_timeline": {"observations": ["最高单曲只有 4 次，更像多曲目密集漫游。"]},
            "discovery_timeline": {"observations": ["Zhang Zhen Yue 首次出现于 2026-03-09。"]},
        },
        "metadata": {
            "writer_pipeline_status": "accepted",
            "critic_passed": True,
            "taste_score": {"ok": True, "total": 35},
        },
    }


def test_final_visible_text_includes_user_visible_deck_and_chart_observations():
    text = final_visible_artifact_text(_artifact())

    assert "Taylor Swift 是年度重心。" in text
    assert "音乐铺满当前统计期" in text
    assert "活跃 174 天。" in text
    assert "Zhang Zhen Yue 首次出现于 2026-03-09。" in text


def test_final_quality_rejects_internal_deck_language():
    artifact = _artifact()
    artifact["sections"][1]["deck"] = (
        "展示Olivia Rodrigo在5月超越Taylor Swift的播放量，说明偏好会在特定月份发生转向。"
    )

    result = evaluate_final_artifact_quality(artifact)

    assert result["ok"] is False
    assert any(issue["code"] == "internal_brief_leakage" for issue in result["issues"])


def test_final_quality_rejects_duplicate_section_prose():
    artifact = _artifact()
    artifact["sections"][5]["heading"] = "Taylor Swift 是最稳定的回访对象"
    artifact["sections"][5]["prose"] = artifact["sections"][0]["prose"]

    result = evaluate_final_artifact_quality(artifact)

    assert result["ok"] is False
    assert any(issue["code"] == "duplicate_section_text" for issue in result["issues"])


def test_final_quality_rejects_duplicate_chart_refs():
    artifact = _artifact()
    artifact["sections"][1]["chart_refs"] = ["listening_calendar", "artist_monthly_trend"]

    result = evaluate_final_artifact_quality(artifact)

    assert result["ok"] is False
    assert any(issue["code"] == "duplicate_chart_ref" for issue in result["issues"])


def test_final_quality_rejects_misleading_accepted_metadata_when_visible_text_fails():
    artifact = _artifact()
    artifact["sections"][0]["deck"] = "解释播放领先专辑和个人榜单领先专辑的关系。"
    artifact["metadata"]["writer_pipeline_status"] = "accepted"
    artifact["metadata"]["taste_score"] = {"ok": True, "total": 35}

    result = evaluate_final_artifact_quality(artifact)

    assert result["ok"] is False
    assert any(issue["code"] == "misleading_quality_metadata" for issue in result["issues"])


def test_final_visible_text_includes_insight_cards():
    artifact = _artifact()
    artifact["insight_cards"] = [
        {
            "id": "album_axis",
            "label": "专辑重心",
            "value": "The Life of a Showgirl",
            "caption": "解释播放领先专辑和个人榜单领先专辑的关系。",
        }
    ]

    text = final_visible_artifact_text(artifact)
    result = evaluate_final_artifact_quality(artifact)

    assert "专辑重心" in text
    assert "The Life of a Showgirl" in text
    assert "解释播放领先专辑和个人榜单领先专辑的关系。" in text
    assert result["ok"] is False
    assert any(issue["code"] == "internal_brief_leakage" for issue in result["issues"])


def test_final_quality_accepts_normal_user_facing_explanatory_sentence():
    artifact = _artifact()
    artifact["sections"][1]["deck"] = "说明这段偏好变化并不来自单一歌曲循环。"

    result = evaluate_final_artifact_quality(artifact)

    assert result["ok"] is True

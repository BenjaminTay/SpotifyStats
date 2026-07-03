from __future__ import annotations

import pytest

from backend.domains.ai_reports.visual_yearly_critic import critique_visual_yearly_artifact
from scripts import probe_visual_yearly_report_artifact as visual_probe

pytestmark = pytest.mark.unit


def _artifact(prose: str, chart_count: int = 4) -> dict:
    chart_specs = [
        {"id": f"chart_{i}", "chart_type": "listening_calendar_heatmap", "data_key": f"chart_{i}"}
        for i in range(chart_count)
    ]
    return {
        "sections": [
            {
                "id": "opening",
                "heading": "几乎没有离开音乐的一年",
                "prose": prose,
                "chart_refs": ["chart_0"],
            },
            {
                "id": "companionship",
                "heading": "反复回到的声音",
                "prose": prose,
                "chart_refs": ["chart_1"],
            },
            {
                "id": "album_story",
                "heading": "两种不同的喜欢",
                "prose": prose,
                "chart_refs": ["chart_2"],
            },
            {
                "id": "discovery",
                "heading": "新声音留下痕迹",
                "prose": prose,
                "chart_refs": ["chart_3"],
            },
            {"id": "closing", "heading": "这一年留下什么", "prose": prose, "chart_refs": []},
            {"id": "rhythm", "heading": "生活里的节奏", "prose": prose, "chart_refs": []},
        ],
        "chart_specs": chart_specs,
        "chart_data": {f"chart_{i}": {"ok": True} for i in range(chart_count)},
        "insight_cards": [
            {"id": "activity", "caption": "音乐几乎每天都在场。"},
            {"id": "companion", "caption": "Taylor Swift 是反复回到的声音。"},
            {"id": "discovery", "caption": "JOLIN 是新出现的入口。"},
        ],
    }


def test_visual_critic_rejects_business_report_terms():
    artifact = _artifact("Taylor Swift 是稳定中心，形成三榜联动，提供第二层证据。" * 80)

    critique = critique_visual_yearly_artifact(artifact, {"is_partial_year": False})

    codes = {issue["code"] for issue in critique["issues"]}
    assert "business_report_tone" in codes
    assert critique["ok"] is False


def test_visual_critic_rejects_missing_charts():
    artifact = _artifact("Taylor Swift 更像你反复回到的声音。" * 100, chart_count=1)

    critique = critique_visual_yearly_artifact(artifact, {"is_partial_year": False})

    codes = {issue["code"] for issue in critique["issues"]}
    assert "not_enough_charts" in codes


def test_visual_critic_accepts_story_rich_artifact():
    prose = (
        "Taylor Swift 更像你这一年反复回到的声音。"
        "Michael Wong 则把华语记忆和现场感带进来。"
        "这些数字不是冷冰冰的排名，而是在说明音乐如何留在日常节奏里。"
        "JOLIN 的出现更像一次新发现，但还需要时间证明它会不会继续留下。"
        "播放量领先和个人榜单长留并不完全相同，这让两张专辑讲出了两种喜欢。"
    ) * 30
    artifact = _artifact(prose, chart_count=4)

    critique = critique_visual_yearly_artifact(artifact, {"is_partial_year": False})

    assert critique["ok"] is True
    assert critique["issues"] == []


def test_visual_critic_rejects_internal_guidance_leakage():
    artifact = _artifact(
        (
            "Zhang Zhen Yue 是新声音，证据强度可以先放在 high。"
            "confidence high，而且 confidence=medium，但不要写成重度单曲循环。"
            "这些播放量和个人榜单关系也说明音乐有陪伴感和新发现。"
        )
        * 20
    )

    result = critique_visual_yearly_artifact(artifact, {"is_partial_year": True})

    assert result["ok"] is False
    assert any(issue["code"] == "internal_guidance_leakage" for issue in result["issues"])


def test_visual_critic_rejects_repeated_meta_prose():
    repeated = (
        "图表负责回答发生了什么，正文负责回答为什么值得被记住。"
        "陪伴和新发现都在这里，播放量和个人榜单也有关系。"
    )
    artifact = _artifact("\n".join([repeated, repeated, repeated]) * 10)

    result = critique_visual_yearly_artifact(artifact, {"is_partial_year": True})

    assert result["ok"] is False
    assert any(issue["code"] == "repeated_template_prose" for issue in result["issues"])


def test_visual_critic_includes_narrative_quality_gate_issues():
    prose = (
        "播放记录里有 174 个活跃日、7860 次播放和约 498 小时聆听。"
        "174 个活跃日、7860 次播放和约 498 小时聆听构成时间侧证据。"
        "Taylor Swift 是反复回到的陪伴坐标，"
        "JOLIN 是新发现，播放量和个人榜单关系也留在日常节奏里。"
    ) * 20
    artifact = _artifact(prose)

    result = critique_visual_yearly_artifact(artifact, {"is_partial_year": True})

    assert result["ok"] is False
    assert any(issue["code"] == "repeated_core_fact" for issue in result["issues"])


def test_visual_critic_passes_editorial_plan_to_quality_gate():
    prose = (
        "Taylor Swift 是你反复回到的陪伴声音。"
        "JOLIN 是新发现，播放量和个人榜单关系也留在日常节奏里。"
    ) * 30
    artifact = _artifact(prose)
    context = {
        "is_partial_year": True,
        "editorial_plan": {"facts": [], "language_budget": {"陪伴": 0}},
    }

    result = critique_visual_yearly_artifact(artifact, context)

    assert result["ok"] is False
    assert any(issue["code"] == "generic_language_overuse" for issue in result["issues"])
    assert (
        "减少入口、坐标、地图、声音线、陪伴等抽象词，改成具体实体和证据。"
        in result["repair_instructions"]
    )


def test_visual_critic_rejects_same_album_false_contrast():
    artifact = _artifact(
        (
            "The Life of a Showgirl 和 The Life of a Showgirl 说明了两种不同的喜欢，"
            "一边是播放量，一边是个人榜单。"
            "这份年记仍然有陪伴、新发现和日常节奏。"
        )
        * 20
    )
    context = {
        "is_partial_year": True,
        "top_albums": [{"name": "The Life of a Showgirl"}],
        "personal_billboard_year_end": {"albums": [{"name": "The Life of a Showgirl"}]},
    }

    result = critique_visual_yearly_artifact(artifact, context)

    assert result["ok"] is False
    assert any(issue["code"] == "same_entity_false_contrast" for issue in result["issues"])


def test_visual_critic_rejects_unsupported_olivia_regional_or_live_claims():
    artifact = _artifact(
        (
            "Olivia Rodrigo 把华语、现场感和回望带进年度第二条声音线。"
            "这份年记仍然写到陪伴、新发现、播放量和个人榜单关系。"
        )
        * 20
    )
    context = {
        "is_partial_year": True,
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
    }

    result = critique_visual_yearly_artifact(artifact, context)

    assert result["ok"] is False
    assert any(issue["code"] == "unsupported_entity_claim" for issue in result["issues"])


def test_visual_critic_rejects_unsupported_olivia_claim_in_following_sentence():
    artifact = _artifact(
        (
            "Olivia Rodrigo 让年度画像多了一条不同的情绪线。"
            "它把华语、现场感和回望带进年度第二条声音线。"
            "这份年记仍然写到陪伴、新发现、播放量和个人榜单关系。"
        )
        * 20
    )
    context = {
        "is_partial_year": True,
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
    }

    result = critique_visual_yearly_artifact(artifact, context)

    assert result["ok"] is False
    assert any(issue["code"] == "unsupported_entity_claim" for issue in result["issues"])


def test_visual_critic_accepts_plain_olivia_second_thread():
    prose = (
        "Taylor Swift 是你反复回到的坐标。"
        "Olivia Rodrigo 提供了另一条不同听感，但报告只把它写成第二个声音重心。"
        "Zhang Zhen Yue 是这一年的新发现，播放量和个人榜单关系也说明音乐如何留在日常节奏里。"
    ) * 30
    artifact = _artifact(prose)
    context = {
        "is_partial_year": True,
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
    }

    result = critique_visual_yearly_artifact(artifact, context)

    assert result["ok"] is True
    assert result["issues"] == []


def _probe_artifact(prose: str, *, include_observation: bool = True) -> dict:
    observation = "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
    observation_reading = (
        observation + " 这说明 Olivia Rodrigo 这条线不是平均铺开，而是在 2026-06 明显变亮。"
    )
    section_prose = prose + (observation_reading if include_observation else "")
    sections = [
        {
            "id": "opening",
            "heading": "截至 2026-06-23 的年度序章",
            "deck": "Taylor Swift 和 Olivia Rodrigo 构成主线。",
            "prose": section_prose,
            "chart_refs": ["artist_monthly_trend"],
        },
        {
            "id": "rhythm",
            "heading": "日常节奏",
            "prose": prose,
            "chart_refs": ["highlight_day_timeline"],
        },
        {"id": "companionship", "heading": "陪伴坐标", "prose": prose, "chart_refs": []},
        {"id": "album_story", "heading": "专辑故事", "prose": prose, "chart_refs": []},
        {"id": "discovery", "heading": "新声音", "prose": prose, "chart_refs": []},
        {"id": "closing", "heading": "收束", "prose": prose, "chart_refs": []},
    ]
    chart_specs = [
        {"id": "artist_monthly_trend", "chart_type": "line", "data_key": "artist_monthly_trend"},
        {
            "id": "highlight_day_timeline",
            "chart_type": "timeline",
            "data_key": "highlight_day_timeline",
        },
        {
            "id": "playback_billboard_matrix",
            "chart_type": "matrix",
            "data_key": "playback_billboard_matrix",
        },
        {"id": "top_albums", "chart_type": "bar", "data_key": "top_albums"},
    ]
    return {
        "title": "2026 音乐年记",
        "subtitle": "截至 2026-06-23",
        "contract_version": "visual_yearly_v1",
        "sections": sections,
        "chart_specs": chart_specs,
        "chart_data": {
            "artist_monthly_trend": {"observations": [observation]},
            "highlight_day_timeline": {"observations": []},
            "playback_billboard_matrix": {"observations": []},
            "top_albums": {"observations": []},
        },
        "insight_cards": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "visual_brief": {
            "outline_sections": [
                {"id": "opening", "role": "opening_scene"},
                {"id": "artist", "role": "artist_turning_point"},
            ]
        },
        "metadata": {
            "critic_passed": True,
            "fact_validation_passed": True,
            "editorial_plan_version": "yearly_editorial_v1",
            "section_roles": ["opening", "turning_point", "album_story", "closing"],
            "fact_count": 6,
        },
    }


def _probe_result(artifact: dict) -> dict:
    return {
        "artifact": artifact,
        "metadata": {
            "report_mode": "visual_yearly_artifact",
            "contract_version": "visual_yearly_v1",
        },
        "critic": {"ok": True},
        "fact_validation": {"ok": True},
        "report": "",
    }


def test_visual_probe_summary_includes_quality_checks_and_outline_roles():
    prose = (
        "Taylor Swift、Olivia Rodrigo、Zhang Zhen Yue 和 The Life of a Showgirl 留在年记里。" * 45
    )
    artifact = _probe_artifact(prose)
    result = _probe_result(artifact)

    summary = visual_probe._build_summary(
        year=2026,
        task_id="task-visual",
        detail={"status": "done"},
        result=result,
    )

    assert summary["ok"] is True
    assert summary["quality_checks"]["artifact_metadata"]["critic_passed"] is True
    assert summary["quality_checks"]["artifact_metadata"]["fact_validation_passed"] is True
    assert summary["quality_checks"]["min_article_length"] == 1800
    assert summary["quality_checks"]["article_length"] >= 1800
    assert summary["quality_checks"]["visual_brief_outline_roles"] == [
        "opening_scene",
        "artist_turning_point",
    ]


def test_visual_probe_rejects_failed_metadata_short_text_missing_observation_and_bad_tokens():
    prose = (
        "截至 2026-06-23，Taylor Swift、Olivia Rodrigo、Zhang Zhen Yue 和 "
        "The Life of a Showgirl 仍在报告里，但 undefined null NaN unknown、"
        "Dynamic Outline 和 Evidence Ledger 泄漏出来。"
    )
    artifact = _probe_artifact(prose, include_observation=False)
    artifact["metadata"] = {"critic_passed": False, "fact_validation_passed": False}
    result = _probe_result(artifact)
    probe_text = visual_probe._artifact_text(result, artifact, artifact["sections"])

    issues = visual_probe._validate(
        year=2026,
        detail={"status": "done"},
        result=result,
        artifact=artifact,
        metadata=result["metadata"],
        sections=artifact["sections"],
        chart_specs=artifact["chart_specs"],
        chart_data=artifact["chart_data"],
        prose=probe_text,
    )

    assert "artifact.metadata.critic_passed is not true" in issues
    assert "artifact.metadata.fact_validation_passed is not true" in issues
    assert "partial-year prose length < 1800" in issues
    assert "missing chart observations: opening -> artist_monthly_trend" in issues
    assert "forbidden terms: evidence ledger, dynamic outline" in issues
    assert "invalid placeholder tokens: NaN, null, undefined, unknown" in issues

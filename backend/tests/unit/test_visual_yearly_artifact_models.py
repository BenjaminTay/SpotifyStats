from __future__ import annotations

import pytest

from backend.domains.ai_reports.visual_artifact_models import (
    VISUAL_YEARLY_CONTRACT_VERSION,
    VISUAL_YEARLY_REPORT_MODE,
    VisualYearlyArtifact,
    YearlyArtifactMetadata,
    YearlyArtifactSection,
    YearlyChartSpec,
    YearlyInsightCard,
)

pytestmark = pytest.mark.unit


def test_visual_yearly_artifact_serializes_stable_shape():
    artifact = VisualYearlyArtifact(
        report_mode=VISUAL_YEARLY_REPORT_MODE,
        contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
        title="你的 2025 音乐年记",
        subtitle="几乎没有离开音乐的一年",
        period={
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "is_partial_year": False,
        },
        narrative_brief={"main_story": "稳定陪伴与华语情绪线并行的一年。"},
        visual_brief={"required_chart_ids": ["listening_calendar"]},
        sections=(
            YearlyArtifactSection(
                id="opening",
                role="opening",
                heading="几乎没有离开音乐的一年",
                deck="364 个活跃日说明音乐几乎每天都在场。",
                prose="这一年，音乐几乎没有从你的日常里退场。",
                chart_refs=("listening_calendar",),
                insight_refs=("activity_density",),
                evidence_refs=("yearly_overview",),
                pull_quote="音乐不是偶尔打开的背景。",
            ),
        ),
        insight_cards=(
            YearlyInsightCard(
                id="activity_density",
                label="全年陪伴密度",
                value="364 天",
                caption="这一年几乎每天都有音乐在场。",
                tone="warm",
                evidence_refs=("yearly_overview",),
            ),
        ),
        chart_specs=(
            YearlyChartSpec(
                id="listening_calendar",
                chart_type="listening_calendar_heatmap",
                title="音乐铺满这一年",
                narrative_question="音乐是否几乎每天都在场？",
                entities=(),
                data_key="listening_calendar",
                insight="364 个活跃日让音乐成为全年背景。",
                fallback="数据不足时展示活跃日数字卡。",
            ),
        ),
        chart_data={"listening_calendar": {"days": [], "active_days": 364}},
        metadata=YearlyArtifactMetadata(
            report_mode=VISUAL_YEARLY_REPORT_MODE,
            contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
            fallback_level=None,
            section_count=1,
            chart_count=1,
            insight_card_count=1,
            article_length=23,
            critic_passed=True,
            fact_validation_passed=True,
        ),
    )

    payload = artifact.to_dict()

    assert payload["report_mode"] == "visual_yearly_artifact"
    assert payload["contract_version"] == "visual_yearly_v1"
    assert payload["sections"][0]["chart_refs"] == ["listening_calendar"]
    assert payload["metadata"]["section_count"] == 1
    assert payload["chart_data"]["listening_calendar"]["active_days"] == 364


def test_visual_artifact_reports_missing_chart_refs():
    artifact = VisualYearlyArtifact(
        report_mode=VISUAL_YEARLY_REPORT_MODE,
        contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
        title="你的 2025 音乐年记",
        subtitle="测试",
        period={"year": 2025},
        narrative_brief={},
        visual_brief={},
        sections=(
            YearlyArtifactSection(
                id="opening",
                role="opening",
                heading="开场",
                deck="",
                prose="文字",
                chart_refs=("missing_chart",),
                insight_refs=(),
                evidence_refs=(),
                pull_quote=None,
            ),
        ),
        insight_cards=(),
        chart_specs=(),
        chart_data={},
        metadata=YearlyArtifactMetadata(
            report_mode=VISUAL_YEARLY_REPORT_MODE,
            contract_version=VISUAL_YEARLY_CONTRACT_VERSION,
            fallback_level=None,
            section_count=1,
            chart_count=0,
            insight_card_count=0,
            article_length=2,
            critic_passed=False,
            fact_validation_passed=False,
        ),
    )

    assert artifact.missing_chart_refs() == ["missing_chart"]

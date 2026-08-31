from __future__ import annotations

import pytest

from backend.domains.ai_reports.report_section_protocol import (
    audit_report_sections,
    strip_unsupported_numeric_sentences,
)

pytestmark = pytest.mark.unit


def _tool_results() -> list[dict]:
    return [
        {
            "_tool_name": "analysis_charts",
            "_params": {
                "entity": "artist",
                "metric": "plays",
                "period": "custom",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
            },
            "status": "ok",
            "result_summary": "artist plays rows=2/18",
            "source_range": "2025-01-01..2025-12-31",
            "data": {
                "rows": [
                    {"rank": 1, "artist_name": "Olivia Rodrigo", "plays": 321},
                    {"rank": 2, "artist_name": "Taylor Swift", "plays": 210},
                ]
            },
        }
    ]


def test_section_checkpoint_passes_grounded_numbers_and_resolves_tool_name_ref() -> None:
    sections, checkpoints, evidence = audit_report_sections(
        [
            {
                "heading": "年度核心",
                "prose": (
                    "Olivia Rodrigo 以 321 次播放位居第 1，Taylor Swift 以 210 次位居第 2。"
                    "两者共同构成了这一年的主要艺人线索。"
                ),
                "chart_refs": ["artist_monthly_trend"],
                "evidence_refs": ["analysis_charts"],
            }
        ],
        tool_results=_tool_results(),
        chart_data={"artist_monthly_trend": {"observations": ["年度艺人趋势"]}},
        chart_specs=[{"id": "artist_monthly_trend"}],
        year=2025,
        end_date="2025-12-31",
    )

    assert checkpoints[0]["status"] == "pass"
    assert sections[0]["evidence_refs"] == [
        "report:0:analysis_charts",
        "chart:artist_monthly_trend",
    ]
    assert evidence[0]["schema_version"] == "tool_evidence_v2"


def test_section_checkpoint_rejects_unsupported_number_and_safety_net_removes_sentence() -> None:
    sections, checkpoints, _ = audit_report_sections(
        [
            {
                "heading": "年度核心",
                "prose": (
                    "Olivia Rodrigo 有 9999 次播放。"
                    "已有本地排行证据显示该艺人位居年度前列，这一结论可以保留。"
                ),
                "chart_refs": [],
                "evidence_refs": ["analysis_charts"],
            }
        ],
        tool_results=_tool_results(),
        chart_data={},
        chart_specs=[],
        year=2025,
        end_date="2025-12-31",
    )

    assert checkpoints[0]["status"] == "fail"
    assert checkpoints[0]["unsupported_numbers"] == ["9999"]
    cleaned = strip_unsupported_numeric_sentences(
        sections[0]["prose"],
        checkpoints[0]["unsupported_numbers"],
    )
    assert "9999" not in cleaned
    assert "结论可以保留" in cleaned

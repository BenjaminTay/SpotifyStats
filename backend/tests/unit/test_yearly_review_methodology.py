from __future__ import annotations

from backend.domains.yearly_review.methodology import build_methodology
from backend.models.yearly_review import (
    YearlyBillboardCoverage,
    YearlyComparisonCoverage,
    YearlyPlayCoverage,
    YearlyReviewCoverage,
    YearlyTasteComparison,
    YearlyTasteCoverage,
)


def test_methodology_discloses_unknown_coverage_ytd_and_distribution_only() -> None:
    coverage = YearlyReviewCoverage(
        status="year_to_date",
        play=YearlyPlayCoverage(
            status="year_to_date",
            observed_start="2026-01-01",
            observed_end="2026-04-15",
        ),
        billboard=YearlyBillboardCoverage(status="year_to_date", source_status="year_to_date"),
        comparison=YearlyComparisonCoverage(comparable=False),
        taste=YearlyTasteCoverage(),
    )

    result = build_methodology(coverage, YearlyTasteComparison())
    text = " ".join(result["coverage_caveats"])

    assert "尚未核验 Spotify 导出" in text
    assert "无法区分无播放日期" in text
    assert "年内阶段结果" in text
    assert "不展示年度同比" in text
    assert "没有两个完整的可比品味阶段" in text
    assert all("section_unavailable" not in item for item in result["limitations"])


def test_methodology_discloses_common_period_comparison() -> None:
    coverage = YearlyReviewCoverage(
        status="complete",
        play=YearlyPlayCoverage(
            status="complete",
            observed_start="2023-01-01",
            observed_end="2023-12-31",
        ),
        billboard=YearlyBillboardCoverage(status="complete", source_status="complete"),
        comparison=YearlyComparisonCoverage(
            baseline_year=2022,
            mode="common_period",
            current_start="2023-07-01",
            current_end="2023-12-31",
            baseline_start="2022-07-01",
            baseline_end="2022-12-31",
            comparable=True,
        ),
        taste=YearlyTasteCoverage(),
    )

    result = build_methodology(coverage, YearlyTasteComparison())

    assert any("共同的观察区间" in item for item in result["coverage_caveats"])
    assert result["comparison_periods"] == {
        "current_start": "2023-01-01",
        "current_end": "2023-12-31",
        "comparison_mode": "common_period",
        "comparison_current_start": "2023-07-01",
        "comparison_current_end": "2023-12-31",
        "baseline_start": "2022-07-01",
        "baseline_end": "2022-12-31",
    }

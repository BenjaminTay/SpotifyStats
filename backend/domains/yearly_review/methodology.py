"""Human-readable methodology and automatic coverage disclosures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.domains.yearly_review.policies import (
    HIGHLIGHT_POLICY_VERSION,
    RELATIONSHIP_POLICY_VERSION,
    SEASON_STAGE_POLICY_VERSION,
)
from backend.domains.yearly_review.versions import YEARLY_REVIEW_CONTENT_VERSION
from backend.models.yearly_review import YearlyReviewCoverage, YearlyTasteComparison


def build_methodology(
    coverage: YearlyReviewCoverage,
    taste_comparison: YearlyTasteComparison,
    *,
    billboard_record_semantics: Mapping[str, Any] | None = None,
    internal_diagnostics: Sequence[str] = (),
) -> dict[str, Any]:
    caveats: list[str] = []
    play = coverage.play
    if play.import_coverage_status == "unknown":
        caveats.append("尚未核验 Spotify 导出是否完整覆盖整个观察区间。")
    elif play.import_coverage_status == "verified_partial":
        caveats.append("Spotify 导入数据已确认只覆盖部分观察区间。")
    if play.internal_gap_status == "unknown":
        caveats.append("尚无法区分无播放日期与导入记录缺失。")
    elif play.internal_gap_status == "verified_gaps":
        caveats.append("观察区间内存在已确认的数据缺口。")
    if coverage.status == "year_to_date":
        caveats.append("本报告为年内阶段结果；总量、冠军和榜单位置仍可能继续变化。")
    elif coverage.status == "observed_range":
        caveats.append("本报告只描述已观察到的日期范围，不代表完整自然年。")
    if not coverage.comparison.comparable:
        caveats.append("上一年缺少完整同期数据，因此不展示年度同比。")
    if coverage.billboard.status in {"year_to_date", "observed_range"}:
        caveats.append("个人 Billboard 仅覆盖当前已观察榜周，年榜结论属于阶段结果。")
    if coverage.billboard.has_internal_gaps:
        caveats.append("个人 Billboard 榜周存在缺口，连续性纪录需谨慎解读。")
    axis_labels = {
        "style": "主曲风",
        "scene": "地区流行",
        "language": "语言",
        "release_era": "发行年代",
    }
    for axis, label in axis_labels.items():
        axis_coverage = getattr(coverage.taste, axis)
        if axis_coverage.caveat_required:
            detail = f"{label}已知覆盖率为 {axis_coverage.known_pct:.1f}%"
            if axis_coverage.unknown_hours > 0:
                detail += f"，另有 {axis_coverage.unknown_hours:.1f} 小时尚未归类"
            caveats.append(f"{detail}；该维度不用于强结论。")
    if taste_comparison.status != "available":
        caveats.append("当前没有两个完整的可比品味阶段，仅展示年度分布。")
    semantics = dict(billboard_record_semantics or {})
    if semantics.get("limitation"):
        caveats.append("个人 Billboard 纪录暂不支持将精选集合并设置纳入同一口径。")
    for diagnostic in internal_diagnostics:
        if diagnostic.startswith("section_unavailable:"):
            section = diagnostic.split(":", 2)[1]
            label = {
                "honors": "年度荣誉",
                "season": "年度时间线",
                "relationships": "收听关系",
                "listening_life": "收听生活",
                "records": "年度纪录",
                "taste_migration": "品味迁移",
                "appendix": "附录",
                "epilogue": "年度结语",
            }.get(section, "部分内容")
            caveats.append(f"“{label}”章节本次生成失败，报告已保留其余可验证内容。")

    return {
        "content_version": YEARLY_REVIEW_CONTENT_VERSION,
        "relationship_policy_version": RELATIONSHIP_POLICY_VERSION,
        "highlight_policy_version": HIGHLIGHT_POLICY_VERSION,
        "season_stage_policy_version": SEASON_STAGE_POLICY_VERSION,
        "metric_definitions": {
            "有效播放": "按当前有效阈值与连续播放归并设置保留下来的播放事件。",
            "播放榜": "按有效播放次数或有效时长累计排序。",
            "个人 Billboard": "按周榜表现汇总的个人年榜，不是外部官方 Billboard。",
        },
        "comparison_periods": {
            "current_start": play.observed_start,
            "current_end": play.observed_end,
            "baseline_start": coverage.comparison.aligned_start,
            "baseline_end": coverage.comparison.aligned_end,
        },
        "entity_grains": {
            "规范曲目": "按当前曲目归并级别统计，同一录音或作品版本可被合并。",
            "专辑项目": "按专辑项目身份聚合，不直接按同名专辑字符串计数。",
            "署名艺人": "按有效曲目署名展开并规范化艺人身份。",
        },
        "coverage_caveats": list(dict.fromkeys(caveats)),
        "internal_versions": {
            "relationship": RELATIONSHIP_POLICY_VERSION,
            "highlight": HIGHLIGHT_POLICY_VERSION,
            "season": SEASON_STAGE_POLICY_VERSION,
        },
        "internal_diagnostics": list(internal_diagnostics),
        "notes": [
            "所有章节共享同一套有效播放口径。",
            "播放排行与个人 Billboard 分别回答总量和榜单赛季表现。",
        ],
        "limitations": list(dict.fromkeys(caveats)),
    }

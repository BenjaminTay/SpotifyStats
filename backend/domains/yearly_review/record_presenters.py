"""Deterministic public copy for qualified Yearly Review record facts."""

from __future__ import annotations

from typing import Any

from backend.models.yearly_review import (
    YearlyFeaturedRecord,
    YearlyHighlightCandidate,
    YearlyMetric,
)


def _format_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    if isinstance(value, (int, float)):
        return f"{value:,}"
    return str(value)


def _date(candidate: YearlyHighlightCandidate) -> str | None:
    value = (
        candidate.raw_values.get("date")
        or candidate.raw_values.get("billboard_week")
        or candidate.raw_values.get("first_week")
        or candidate.raw_values.get("month")
    )
    return str(value)[:10] if value is not None else None


def _subject(candidate: YearlyHighlightCandidate) -> str:
    metric = candidate.primary_metric
    label = str(metric.label).strip() if metric else ""
    if label and label not in {"记录值", "value"}:
        return label
    if candidate.entity_refs:
        return candidate.entity_refs[0].name
    return str(candidate.raw_values.get("name") or _date(candidate) or "这项纪录")


def _metric_phrase(candidate: YearlyHighlightCandidate) -> str | None:
    metric = candidate.primary_metric
    if metric is None:
        return None
    return f"{_format_value(metric.value)}{metric.unit or ''}"


def _metric_value(candidate: YearlyHighlightCandidate) -> str | None:
    return _format_value(candidate.primary_metric.value) if candidate.primary_metric else None


def _public_metric(metric: YearlyMetric) -> YearlyMetric:
    unit = metric.unit
    if unit:
        unit = unit.replace("後", "后").replace("歸", "归").replace("冠軍", "冠军")
    return metric.model_copy(update={"unit": unit})


def _copy(candidate: YearlyHighlightCandidate) -> tuple[str, str] | None:
    key = candidate.record_key.casefold()
    subject = _subject(candidate)
    metric = _metric_phrase(candidate)
    value = _metric_value(candidate)
    date = _date(candidate)
    entity_label = {"track": "歌曲", "album": "专辑", "artist": "艺人"}.get(
        candidate.fact_type, "对象"
    )

    if "obsession.daily_binge" in key and value:
        return (
            f"单日沉迷最高{entity_label}",
            f"{subject} 单日被播放 {value} 次，创下这一年的沉迷峰值。",
        )
    if "obsession.daily_total_record" in key and value and date:
        return "全年最密集的一天", f"{date} 共记录 {value} 次有效播放，是全年播放最密集的一天。"
    if "obsession.consecutive_marathon" in key and value:
        return "连续播放马拉松", f"{subject} 连续播放达到 {value} 次，形成年度最长的一段集中收听。"
    if "reigns.daily_champion" in key and value:
        return (
            f"日榜冠军最多{entity_label}",
            f"{subject} 共成为日榜冠军 {value} 天，是全年最常占据日榜首位的{entity_label}。",
        )
    if "longest_streak" in key and value:
        return (
            "最长连续收听",
            f"{subject} 连续收听达到 {value} 天，是这一年持续时间最长的同类纪录。",
        )
    if "user_active_streak" in key and value:
        return "最长连续活跃", f"全年最长连续活跃达到 {value} 天。"
    if "longest_span" in key and value:
        return "贯穿全年的陪伴", f"{subject} 的首末次收听相隔 {value} 天，贯穿了这一年的多个阶段。"
    if ("comeback" in key or "return" in key) and value:
        return "沉寂后的回归", f"{subject} 沉寂 {value} 天后重新出现，构成一次清晰的旧爱回归。"
    if "discovery.discovery_day" in key and metric and date:
        return "发现最密集的一天", f"{date} 新发现达到 {metric}，是全年探索最集中的一天。"
    if "discovery.same_name_diff_artist" in key and metric:
        return "同名歌曲巧合", f"名为 {subject} 的作品来自 {metric}，形成一次少见的同名相遇。"
    if "time_patterns.hourly_dominance" in key and value:
        return (
            "高峰时段主角",
            f"{subject} 在个人高峰时段累计 {value} 次，是该时段最常出现的{entity_label}。",
        )
    if "late_night_peak_day" in key and value and date:
        return "深夜浓度最高的一天", f"{date} 的深夜播放占比达到 {value}%，为全年最高。"
    if "late_night_trajectory.monthly" in key and metric:
        return "深夜月份", f"{subject} 的深夜播放占比为 {metric}。"
    if "late_night_trajectory.quarterly" in key and metric:
        return "深夜季度", f"{subject} 的深夜播放占比为 {metric}。"
    if "weekday_preference" in key and value:
        return "一周中的收听高峰", f"{subject} 累计 {value} 次有效播放，是一周中播放最多的一天。"
    if "new_year_eve" in key and metric:
        return "跨年播放", f"{subject} 跨年时段记录了 {metric}。"
    if "behavior.playback_milestones" in key and value:
        return "播放里程碑", f"{subject} 在这一年推动个人历史累计播放达到 {value} 次。"
    if "behavior.skip_storm" in key and value:
        return (
            "快进率最高",
            f"{subject} 的快进率达到 {value}%；该纪录仅描述播放行为，不代表喜爱程度。",
        )
    if "triple_no1" in key and date:
        return "三榜同时登顶", f"{subject} 在 {date} 所在榜周触发歌曲、专辑与艺人三榜联动冠军。"
    if "album_simul_list" in key and date:
        return "专辑同时占榜", f"{subject} 在 {date} 所在榜周有多首作品同时进入个人 Billboard。"
    if "artist_simul_list" in key and date:
        return "艺人同时占榜", f"{subject} 在 {date} 所在榜周以多首作品同时进入个人 Billboard。"
    if "biggest_jump" in key and metric:
        return "年度最大上升", f"{subject} 单周上升 {metric}，创下这一年最大的榜单跃升。"
    if "biggest_drop" in key and metric:
        return "年度最大回落", f"{subject} 单周回落 {metric}，是这一年幅度最大的排名变化。"
    return None


def present_record_candidate(
    candidate: YearlyHighlightCandidate,
) -> YearlyFeaturedRecord | None:
    copy = _copy(candidate)
    if copy is None:
        return None
    title, statement = copy
    source_metrics = ([candidate.primary_metric] if candidate.primary_metric else []) + list(
        candidate.secondary_metrics
    )
    metrics = [_public_metric(metric) for metric in source_metrics]
    return YearlyFeaturedRecord(
        record_id=candidate.candidate_id,
        category=candidate.source_family,
        fact_type=candidate.fact_type,
        title=title,
        statement=statement,
        evidence_grade=candidate.evidence_grade,
        entity_refs=list(candidate.entity_refs),
        metrics=metrics,
        source_refs=list(candidate.source_refs),
        deep_link=candidate.deep_link,
    )


def has_public_record_copy(candidate: YearlyHighlightCandidate) -> bool:
    return present_record_candidate(candidate) is not None

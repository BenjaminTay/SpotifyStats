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
    unit = metric.unit or ""
    separator = "" if unit in {"%", "倍"} else " " if unit else ""
    return f"{_format_value(metric.value)}{separator}{unit}"


def _metric_value(candidate: YearlyHighlightCandidate) -> str | None:
    return _format_value(candidate.primary_metric.value) if candidate.primary_metric else None


def _positive_integer(candidate: YearlyHighlightCandidate, key: str) -> int | None:
    value = candidate.raw_values.get(key)
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _rank(candidate: YearlyHighlightCandidate) -> int | None:
    return candidate.semantics.rank


def _top_prefix(candidate: YearlyHighlightCandidate) -> str:
    return "并列" if candidate.semantics.is_tied_top else ""


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
    entity_type = (
        candidate.entity_refs[0].entity_type if candidate.entity_refs else candidate.fact_type
    )
    entity_label = {"track": "歌曲", "album": "专辑", "artist": "艺人"}.get(entity_type, "对象")

    if "obsession.daily_binge" in key and value:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"单日沉迷第 {rank} 高{entity_label}",
                f"{subject} 在同一天被播放 {value} 次，排在今年同类纪录第 {rank} 位。",
            )
        return (
            f"单日沉迷{_top_prefix(candidate)}最高{entity_label}",
            f"{subject} 在同一天被播放 {value} 次，"
            f"是今年{_top_prefix(candidate)}最集中的一次沉迷。",
        )
    if "obsession.daily_total_plays" in key and value and date:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"年度播放次数第 {rank} 高的一天",
                f"{date} 一共播放了 {value} 次，排在今年单日播放次数第 {rank} 位。",
            )
        tied = _top_prefix(candidate)
        return (
            f"{tied}听歌次数最多的一天",
            f"{date} 一共播放了 {value} 次，{tied}成为今年播放次数最多的一天。",
        )
    if "obsession.daily_total_hours" in key and value and date:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"年度收听时长第 {rank} 高的一天",
                f"{date} 一共听了 {value} 小时，排在今年单日收听时长第 {rank} 位。",
            )
        tied = _top_prefix(candidate)
        return (
            f"{tied}听歌时间最长的一天",
            f"{date} 一共听了 {value} 小时，{tied}成为今年收听时间最长的一天。",
        )
    if "obsession.daily_total_record" in key and value and date:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"年度播放次数第 {rank} 高的一天",
                f"{date} 一共播放了 {value} 次，排在今年单日播放次数第 {rank} 位。",
            )
        tied = _top_prefix(candidate)
        return (
            f"{tied}听歌次数最多的一天",
            f"{date} 一共播放了 {value} 次，{tied}成为今年播放次数最多的一天。",
        )
    if "obsession.consecutive_marathon" in key and value:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"连续播放马拉松第 {rank} 名",
                f"{subject} 连续播放了 {value} 次，排在今年同类纪录第 {rank} 位。",
            )
        tied = _top_prefix(candidate)
        return (
            f"{tied}最长连续播放马拉松",
            f"{subject} 连续播放了 {value} 次，是今年{tied}最长的一段集中收听。",
        )
    if "reigns.daily_champion" in key and value:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"日榜冠军天数第 {rank} 名{entity_label}",
                f"{subject} 一共成为日榜冠军 {value} 天，排在今年同类纪录第 {rank} 位。",
            )
        return (
            f"日榜冠军{_top_prefix(candidate)}最多{entity_label}",
            f"{subject} 一共成为日榜冠军 {value} 天，是今年"
            f"{_top_prefix(candidate)}最常占据日榜首位的{entity_label}。",
        )
    if "longest_streak" in key and value:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"连续收听第 {rank} 长",
                f"{subject} 连续收听达到 {value} 天，排在今年同类纪录第 {rank} 位。",
            )
        return (
            f"{_top_prefix(candidate)}最长连续收听",
            f"{subject} 连续收听达到 {value} 天，是这一年"
            f"{_top_prefix(candidate)}持续时间最长的同类纪录。",
        )
    if "user_active_streak" in key and value:
        return "最长连续活跃", f"最长的一段连续活跃达到 {value} 天。"
    if "longest_span" in key and value:
        return "一路陪伴", f"第一次和最后一次听到 {subject} 相隔 {value} 天。"
    if ("comeback" in key or "return" in key) and value:
        display_subject = (
            f"{entity_label}《{subject}》" if entity_type != "artist" else f"艺人 {subject}"
        )
        return (
            "沉寂后的回归",
            f"{display_subject}沉寂 {value} 天后重新出现，构成一次清晰的旧爱回归。",
        )
    if "discovery.discovery_day" in key and metric and date:
        rank = _rank(candidate)
        discovery_label = {
            "track": "新歌",
            "album": "新专辑",
            "artist": "新艺人",
        }.get(candidate.fact_type, "新音乐")
        if rank and rank > 1:
            return (
                f"认识{discovery_label}第 {rank} 多的一天",
                f"{date} 第一次听到 {metric}，排在今年个人新发现第 {rank} 位。",
            )
        tied = _top_prefix(candidate)
        return (
            f"{tied}认识{discovery_label}最多的一天",
            f"{date} 第一次听到 {metric}，{tied}成为今年个人新发现最多的一天。",
        )
    if "discovery.same_name_diff_artist" in key and metric:
        return "同名歌曲巧合", f"名为 {subject} 的作品来自 {metric}，形成一次少见的同名相遇。"
    if "time_patterns.hourly_dominance" in key and value:
        return (
            "高峰时段主角",
            f"{subject} 在个人高峰时段累计 {value} 次，是该时段最常出现的{entity_label}。",
        )
    if "late_night_peak_day" in key and value and date:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"深夜播放占比第 {rank} 高的一天",
                f"{date} 的深夜播放占比达到 {value}%，排在今年第 {rank} 位。",
            )
        tied = _top_prefix(candidate)
        return (
            f"{tied}深夜播放占比最高的一天",
            f"{date} 的深夜播放占比达到 {value}%，是今年{tied}最高的一天。",
        )
    if "late_night_trajectory.monthly" in key and metric:
        return "深夜月份", f"{subject} 的深夜播放占比为 {metric}。"
    if "late_night_trajectory.quarterly" in key and metric:
        return "深夜季度", f"{subject} 的深夜播放占比为 {metric}。"
    if "weekday_preference" in key and value:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"一周播放次数第 {rank} 高的日子",
                f"{subject} 一共播放了 {value} 次，排在一周七天中的第 {rank} 位。",
            )
        tied = _top_prefix(candidate)
        return (
            f"一周中{tied}最常听歌的日子",
            f"{subject} 一共播放了 {value} 次，是一周中{tied}听歌最多的一天。",
        )
    if "new_year_eve" in key and metric:
        return "跨年播放", f"{subject} 跨年时段记录了 {metric}。"
    if "behavior.playback_milestones" in key and value:
        if candidate.semantics.scope == "lifetime":
            return (
                "播放里程碑",
                f"听到 {subject} 时，你的个人历史总播放数在今年跨过了 {value} 次。",
            )
        return "年度播放进度", f"因为 {subject}，这一年的有效播放累计达到 {value} 次。"
    if "behavior.skip_storm" in key and value:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"快进率第 {rank} 高",
                f"{subject} 的快进率达到 {value}%，排在今年同类纪录第 {rank} 位；"
                "该纪录仅描述播放行为，不代表喜爱程度。",
            )
        tied = _top_prefix(candidate)
        return (
            f"快进率{tied}最高",
            f"{subject} 的快进率达到 {value}%，是今年{tied}最高；"
            "该纪录仅描述播放行为，不代表喜爱程度。",
        )
    if "triple_no1" in key and date:
        return "三榜同时登顶", f"{subject} 在 {date} 这一周同时带动歌曲、专辑和艺人登上冠军。"
    if (
        "album_simul_list" in key
        and date
        and (track_count := _positive_integer(candidate, "track_count"))
    ):
        return (
            "同一张专辑多首入榜",
            f"{subject} 在 {date} 这一周共有 {track_count} 首歌曲同时进入个人榜单。",
        )
    if (
        "artist_simul_list" in key
        and date
        and (track_count := _positive_integer(candidate, "track_count"))
    ):
        return (
            "同一位艺人多首入榜",
            f"{subject} 在 {date} 这一周共有 {track_count} 首歌曲同时进入个人榜单。",
        )
    if "biggest_jump" in key and metric:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"年度榜单上升第 {rank} 名",
                f"{subject} 单周上升 {metric}，排在这一年的第 {rank} 位。",
            )
        tied = _top_prefix(candidate)
        return (
            f"年度{tied}最大上升",
            f"{subject} 单周上升 {metric}，创下这一年{tied}最大的榜单跃升。",
        )
    if "biggest_drop" in key and metric:
        rank = _rank(candidate)
        if rank and rank > 1:
            return (
                f"年度榜单回落第 {rank} 名",
                f"{subject} 单周回落 {metric}，排在这一年的第 {rank} 位。",
            )
        tied = _top_prefix(candidate)
        return (
            f"年度{tied}最大回落",
            f"{subject} 单周回落 {metric}，是这一年{tied}幅度最大的排名变化。",
        )
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

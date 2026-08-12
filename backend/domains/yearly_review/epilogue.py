"""Deterministic closing synthesis written for the listener, not the audit trail."""

from __future__ import annotations

from collections.abc import Sequence

from backend.models.yearly_review import YearlyEntityRef, YearlyEpilogue, YearlyHeadline


def _by_id(candidates: Sequence[YearlyHeadline]) -> dict[str, YearlyHeadline]:
    return {headline.headline_id: headline for headline in candidates}


def _volume_conclusion(by_id: dict[str, YearlyHeadline]) -> YearlyHeadline | None:
    volume = by_id.get("listening_time_change")
    discovery = by_id.get("discovery_pattern")
    replay = by_id.get("replay_pattern")
    if volume is None or volume.primary_metric is None:
        return None
    change = float(volume.primary_metric.value)
    direction = "多" if change >= 0 else "少"
    comparison = volume.primary_metric.comparison_label or "比去年"
    if discovery and discovery.primary_metric:
        detail = f"同时第一次听到了 {int(float(discovery.primary_metric.value)):,} 首歌"
        sources = [*volume.source_refs, *discovery.source_refs]
    elif replay and replay.primary_metric:
        detail = f"其中 {float(replay.primary_metric.value):.1f}% 的播放是在重听熟悉的歌"
        sources = [*volume.source_refs, *replay.source_refs]
    else:
        detail = "这一年的听歌节奏也有了新的变化"
        sources = list(volume.source_refs)
    return volume.model_copy(
        update={
            "headline_id": "epilogue_listening_shape",
            "title": "这一年的听歌节奏",
            "statement": f"{comparison}{direction}听了 {abs(change):.1f}%，{detail}。",
            "source_refs": sources,
        }
    )


def _artist_conclusion(by_id: dict[str, YearlyHeadline]) -> YearlyHeadline | None:
    leader = by_id.get("most_played_artist")
    concentration = by_id.get("artist_concentration")
    if leader is None or not leader.entity_refs:
        return None
    artist = leader.entity_refs[0]
    if concentration and concentration.primary_metric:
        share = float(concentration.primary_metric.value)
        statement = f"{artist.name} 占了今年播放的 {share:.1f}%，是最稳定的陪伴主线。"
        sources = [*leader.source_refs, *concentration.source_refs]
    else:
        statement = f"{artist.name} 不只是某一次高峰，而是这一年最常回到的名字。"
        sources = list(leader.source_refs)
    return leader.model_copy(
        update={
            "headline_id": "epilogue_artist_companion",
            "title": "一直陪着你的声音",
            "statement": statement,
            "source_refs": sources,
        }
    )


def _taste_conclusion(candidates: Sequence[YearlyHeadline]) -> YearlyHeadline | None:
    taste = next(
        (item for item in candidates if item.headline_id.startswith("taste_migration_")),
        None,
    )
    if taste is None or taste.primary_metric is None:
        return None
    entity = taste.entity_refs[0] if taste.entity_refs else None
    direction = "上升" if float(taste.primary_metric.value) >= 0 else "下降"
    statement = (
        f"最明显的品味变化{direction}了 {abs(float(taste.primary_metric.value)):.1f} 个百分点"
        + (f"，{entity.name} 最能代表这次转向。" if entity else "。")
    )
    return taste.model_copy(
        update={
            "headline_id": "epilogue_taste_direction",
            "title": "最后留下的品味方向",
            "statement": statement,
        }
    )


def build_epilogue(
    headline_candidates: Sequence[YearlyHeadline],
    *,
    new_history_tops: Sequence[YearlyEntityRef] = (),
    next_year_carryovers: Sequence[YearlyEntityRef] = (),
) -> YearlyEpilogue:
    by_id = _by_id(headline_candidates)
    conclusions = [
        conclusion
        for conclusion in (
            _volume_conclusion(by_id),
            _artist_conclusion(by_id),
            _taste_conclusion(headline_candidates),
        )
        if conclusion is not None
    ]
    return YearlyEpilogue(
        conclusions=conclusions,
        new_history_tops=list(new_history_tops)[:6],
        next_year_carryovers=list(next_year_carryovers)[:6],
    )

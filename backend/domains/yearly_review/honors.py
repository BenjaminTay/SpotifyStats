"""Dual-view annual honors and ranking-divergence stories."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.domains.yearly_review.entity_links import entity_ref_from_row
from backend.domains.yearly_review.policies import DIVERGENCE_RANK_GAPS
from backend.models.yearly_review import (
    YearlyDivergenceStory,
    YearlyEntityRef,
    YearlyHonorItem,
    YearlyHonorsChapter,
    YearlyMetric,
)

HONOR_TITLES = {
    "year_end_no1_track": "个人 Billboard 年度 #1 曲目",
    "year_end_no1_album": "个人 Billboard 年度 #1 专辑",
    "year_end_no1_artist": "个人 Billboard 年度 #1 艺人",
    "longest_charting_track": "最长在榜曲目",
    "longest_charting_album": "最长在榜专辑",
    "longest_charting_artist": "最长在榜艺人",
    "biggest_no1_run_track": "最长冠军统治曲目",
    "biggest_no1_run_album": "最长冠军统治专辑",
    "biggest_no1_run_artist": "最长冠军统治艺人",
    "top_new_entry_track": "最高新进曲目",
    "breakthrough_artist": "突破艺人",
    "album_era_of_the_year": "年度专辑时代",
}


def _entity_type(row: Mapping[str, Any]) -> str | None:
    if row.get("track_name") or row.get("track_id") is not None:
        return "track"
    if row.get("album_name"):
        return "album"
    if row.get("artist_name"):
        return "artist"
    return None


def entity_ref(row: Mapping[str, Any], entity_type: str | None = None) -> YearlyEntityRef | None:
    return entity_ref_from_row(row, entity_type or _entity_type(row))


def identity_key(row: Mapping[str, Any], entity_type: str) -> str:
    if row.get("identity_key"):
        return str(row["identity_key"]).casefold()
    if entity_type == "track":
        return f"track:{row.get('track_id')}".casefold()
    if entity_type == "album":
        if row.get("album_project_id") is not None:
            return f"album-project:{row['album_project_id']}".casefold()
        return f"album:{row.get('artist_name', '')}\u241f{row.get('album_name', '')}".casefold()
    return f"artist:{row.get('artist_name', '')}".casefold()


def _play_honor(entity_type: str, row: Mapping[str, Any]) -> YearlyHonorItem:
    ref = entity_ref(row, entity_type)
    return YearlyHonorItem(
        honor_id=f"play_leader_{entity_type}",
        title={"track": "播放冠军曲目", "album": "播放冠军专辑", "artist": "播放冠军艺人"}[
            entity_type
        ],
        entity=ref,
        metrics=[
            YearlyMetric(key="plays", label="有效播放", value=int(row.get("plays", 0)), unit="次"),
            YearlyMetric(
                key="hours",
                label="有效时长",
                value=round(float(row.get("hours", 0)), 2),
                unit="小时",
            ),
            YearlyMetric(
                key="active_months",
                label="活跃月份",
                value=int(row.get("active_months", 0)),
                unit="个月",
            ),
            YearlyMetric(
                key="share_pct",
                label="年度份额",
                value=round(float(row.get("share_pct", 0)), 2),
                unit="%",
            ),
        ],
        evidence_grade="A",
    )


def _billboard_honor(
    entity_type: str,
    row: Mapping[str, Any],
    *,
    complete: bool,
) -> YearlyHonorItem:
    ref = entity_ref(row, entity_type)
    title = {
        "track": "个人 Billboard 曲目年度冠军",
        "album": "个人 Billboard 专辑年度冠军",
        "artist": "个人 Billboard 艺人年度冠军",
    }[entity_type]
    if not complete:
        title = title.replace("年度冠军", "阶段领先")
    return YearlyHonorItem(
        honor_id=f"billboard_leader_{entity_type}",
        title=title,
        entity=ref,
        metrics=[
            YearlyMetric(
                key="year_end_score",
                label="Year-End Score",
                value=int(row.get("year_end_score", 0)),
            ),
            YearlyMetric(
                key="peak_position",
                label="最高排名",
                value=int(row.get("peak_position", 0)),
                unit="名",
            ),
            YearlyMetric(
                key="weeks_on_chart",
                label="在榜周数",
                value=int(row.get("weeks_on_chart", 0)),
                unit="周",
            ),
            YearlyMetric(
                key="weeks_at_no1",
                label="冠军周数",
                value=int(row.get("weeks_at_no1", 0)),
                unit="周",
            ),
        ],
        evidence_grade="A",
    )


def _annual_honor_item(
    key: str,
    row: Mapping[str, Any],
    *,
    complete: bool,
) -> YearlyHonorItem | None:
    entity_type = _entity_type(row)
    ref = entity_ref(row, entity_type) if entity_type else None
    if ref is None:
        return None
    title = HONOR_TITLES.get(key, key.replace("_", " "))
    if not complete and "年度" in title:
        title = title.replace("年度", "阶段")
    metrics: list[YearlyMetric] = []
    for metric_key, label, unit in (
        ("year_end_rank", "年榜排名", "名"),
        ("year_end_score", "Year-End Score", None),
        ("weeks_on_chart", "在榜周数", "周"),
        ("weeks_at_no1", "冠军周数", "周"),
        ("peak_position", "最高排名", "名"),
    ):
        if row.get(metric_key) is not None:
            metrics.append(
                YearlyMetric(key=metric_key, label=label, value=int(row[metric_key]), unit=unit)
            )
    return YearlyHonorItem(
        honor_id=key,
        title=title,
        entity=ref,
        metrics=metrics,
        evidence_grade="A",
    )


def build_honors(
    play_rankings: Mapping[str, Any],
    billboard: Mapping[str, Any],
) -> YearlyHonorsChapter:
    charts = dict(play_rankings.get("charts", {}))
    billboard_charts = dict(billboard.get("charts", {}))
    coverage = billboard.get("coverage")
    complete = getattr(coverage, "status", None) == "complete"

    play_leaders: dict[str, YearlyHonorItem] = {}
    billboard_leaders: dict[str, YearlyHonorItem] = {}
    divergence: list[YearlyDivergenceStory] = []
    for entity_type in ("track", "album", "artist"):
        play_rows = dict(charts.get(entity_type, {})).get("by_plays", [])
        season_rows = list(billboard_charts.get(entity_type, []))
        if play_rows:
            play_leaders[entity_type] = _play_honor(entity_type, play_rows[0])
        if season_rows:
            billboard_leaders[entity_type] = _billboard_honor(
                entity_type, season_rows[0], complete=complete
            )

        play_positions = {
            identity_key(row, entity_type): int(row.get("rank", index))
            for index, row in enumerate(play_rows, start=1)
        }
        for season_row in season_rows:
            key = identity_key(season_row, entity_type)
            if key not in play_positions:
                continue
            play_rank = play_positions[key]
            season_rank = int(season_row.get("year_end_rank", 0))
            if season_rank <= 0 or play_rank == season_rank:
                continue
            gap = play_rank - season_rank
            if abs(gap) < DIVERGENCE_RANK_GAPS[entity_type]:
                continue
            ref = entity_ref(season_row, entity_type)
            if ref is None:
                continue
            divergence.append(
                YearlyDivergenceStory(
                    entity=ref,
                    play_rank=play_rank,
                    billboard_year_end_rank=season_rank,
                    rank_gap=gap,
                    interpretation=(
                        "season_more_persistent"
                        if season_rank < play_rank
                        else "volume_more_concentrated"
                    ),
                    evidence_grade="B",
                )
            )

    annual_honors = []
    for key in HONOR_TITLES:
        raw = dict(billboard.get("honors", {})).get(key)
        if not raw:
            continue
        item = _annual_honor_item(key, raw, complete=complete)
        if item:
            annual_honors.append(item)
    divergence.sort(
        key=lambda item: (-abs(item.rank_gap), item.entity.entity_type, item.entity.name)
    )
    return YearlyHonorsChapter(
        play_leaders=play_leaders,
        billboard_leaders=billboard_leaders,
        divergence_stories=divergence[:6],
        annual_honors=annual_honors,
    )

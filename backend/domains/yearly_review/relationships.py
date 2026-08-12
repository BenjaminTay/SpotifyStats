"""Evidence-backed user-to-music relationship stories."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.domains.yearly_review.honors import entity_ref
from backend.domains.yearly_review.policies import (
    MIN_RELATIONSHIP_SPAN_DAYS,
    RELATIONSHIP_ENTITY_CAP,
    RELATIONSHIP_PER_TYPE_CAP,
    RELATIONSHIP_POLICY_VERSION,
    RELATIONSHIP_THRESHOLDS,
)
from backend.models.yearly_review import (
    YearlyDivergenceStory,
    YearlyMetric,
    YearlyRelationshipStory,
    YearlyReviewCoverage,
)


@dataclass
class _RelationshipCandidate:
    score: float
    relationship_type: str
    row: dict[str, Any]
    metrics: list[YearlyMetric]
    title: str
    statement: str
    source_refs: list[str]


def _longest_consecutive_months(months: Sequence[int]) -> int:
    longest = current = 0
    previous = None
    for month in sorted(set(months)):
        current = current + 1 if previous is not None and month == previous + 1 else 1
        longest = max(longest, current)
        previous = month
    return longest


def _entity_summary(
    frame: pd.DataFrame,
    entity_type: str,
    id_column: str,
    name_column: str,
) -> list[dict[str, Any]]:
    if frame.empty or id_column not in frame.columns or name_column not in frame.columns:
        return []
    work = frame.copy()
    if "ts_month" not in work.columns:
        work["ts_month"] = pd.to_datetime(work["ts_date"], errors="coerce").dt.month
    work["_date"] = pd.to_datetime(work["ts_date"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for identity, group in work.dropna(subset=[id_column, name_column]).groupby(id_column):
        dates = group["_date"].dropna()
        if dates.empty:
            continue
        months = [int(value) for value in group["ts_month"].dropna().tolist()]
        monthly = group.groupby("ts_month").size()
        plays = int(len(group))
        peak_plays = int(monthly.max()) if not monthly.empty else 0
        row = {
            "entity_type": entity_type,
            "identity": str(identity),
            "plays": plays,
            "active_days": int(group["ts_date"].nunique()),
            "active_months": int(group["ts_month"].nunique()),
            "consecutive_months": _longest_consecutive_months(months),
            "span_days": int((dates.max() - dates.min()).days),
            "peak_month_share_pct": round(peak_plays / plays * 100, 1) if plays else 0.0,
            "first_date": dates.min().date().isoformat(),
            "last_date": dates.max().date().isoformat(),
            "unique_tracks": int(group["track_id"].nunique()) if "track_id" in group else 0,
        }
        if entity_type == "track":
            row.update(
                track_id=identity,
                track_name=str(group[name_column].iloc[0]),
                artist_name=(str(group["artist_name"].iloc[0]) if "artist_name" in group else None),
            )
        elif entity_type == "album":
            row.update(
                album_project_id=identity,
                album_name=str(group[name_column].iloc[0]),
                artist_name=(str(group["artist_name"].iloc[0]) if "artist_name" in group else None),
            )
        else:
            row.update(artist_name=str(group[name_column].iloc[0]))
        rows.append(row)
    return rows


def _summaries(
    entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> dict[str, list[dict[str, Any]]]:
    track_frame, album_frame, artist_frame = entity_frames
    return {
        "track": _entity_summary(
            track_frame,
            "track",
            "canonical_track_id" if "canonical_track_id" in track_frame else "track_id",
            "canonical_track_name" if "canonical_track_name" in track_frame else "track_name",
        ),
        "album": _entity_summary(
            album_frame,
            "album",
            "album_project_id",
            "album_project_name" if "album_project_name" in album_frame else "album_name",
        ),
        "artist": _entity_summary(artist_frame, "artist", "artist_name", "artist_name"),
    }


def _metric(
    key: str, label: str, value: int | float | str, unit: str | None = None
) -> YearlyMetric:
    return YearlyMetric(key=key, label=label, value=value, unit=unit)


def _threshold_candidates(
    summaries: Mapping[str, Sequence[dict[str, Any]]],
) -> list[_RelationshipCandidate]:
    candidates: list[_RelationshipCandidate] = []
    long_rule = RELATIONSHIP_THRESHOLDS["long_companion"]
    short_rule = RELATIONSHIP_THRESHOLDS["short_obsession"]
    for entity_type, rows in summaries.items():
        for row in rows:
            if (
                row["plays"] >= long_rule["plays"]
                and row["active_months"] >= long_rule["active_months"]
                and row["consecutive_months"] >= long_rule["consecutive_months"]
                and row["span_days"] >= long_rule["span_days"]
            ):
                candidates.append(
                    _RelationshipCandidate(
                        score=row["active_months"] * 20 + row["span_days"] + row["plays"],
                        relationship_type="long_companion",
                        row=row,
                        metrics=[
                            _metric("active_months", "活跃月份", row["active_months"], "个月"),
                            _metric("span_days", "首末跨度", row["span_days"], "天"),
                            _metric(
                                "consecutive_months",
                                "最长连续活跃",
                                row["consecutive_months"],
                                "个月",
                            ),
                        ],
                        title="长期陪伴",
                        statement=(
                            f"全年在 {row['active_months']} 个月出现，首末播放相隔 {row['span_days']} 天。"
                        ),
                        source_refs=[f"relationship_summary:{entity_type}:{row['identity']}"],
                    )
                )
            if (
                row["plays"] >= short_rule["plays"]
                and row["peak_month_share_pct"] >= short_rule["peak_month_share_pct"]
                and row["active_months"] <= short_rule["max_active_months"]
            ):
                candidates.append(
                    _RelationshipCandidate(
                        score=row["peak_month_share_pct"] * 5 + row["plays"],
                        relationship_type="short_obsession",
                        row=row,
                        metrics=[
                            _metric(
                                "peak_month_share_pct",
                                "峰值月占比",
                                row["peak_month_share_pct"],
                                "%",
                            ),
                            _metric("active_months", "活跃月份", row["active_months"], "个月"),
                            _metric("plays", "有效播放", row["plays"], "次"),
                        ],
                        title="短期着迷",
                        statement=(
                            f"{row['peak_month_share_pct']:.1f}% 的年度播放集中在同一个月，全年只活跃于 {row['active_months']} 个月。"
                        ),
                        source_refs=[f"relationship_summary:{entity_type}:{row['identity']}"],
                    )
                )

    album_rule = RELATIONSHIP_THRESHOLDS["deep_album"]
    for row in summaries.get("album", []):
        if (
            row["plays"] >= album_rule["plays"]
            and row["unique_tracks"] >= album_rule["unique_tracks"]
            and row["active_days"] >= album_rule["active_days"]
        ):
            candidates.append(
                _RelationshipCandidate(
                    score=row["unique_tracks"] * 20 + row["active_days"] + row["plays"],
                    relationship_type="deep_album",
                    row=row,
                    metrics=[
                        _metric("unique_tracks", "独立曲目", row["unique_tracks"], "首"),
                        _metric("active_days", "活跃天数", row["active_days"], "天"),
                        _metric("plays", "有效播放", row["plays"], "次"),
                    ],
                    title="深度专辑聆听",
                    statement=(
                        f"覆盖 {row['unique_tracks']} 首曲目，并在 {row['active_days']} 个不同日期持续播放。"
                    ),
                    source_refs=[f"relationship_summary:album:{row['identity']}"],
                )
            )

    artist_rule = RELATIONSHIP_THRESHOLDS["broad_artist"]
    for row in summaries.get("artist", []):
        if (
            row["plays"] >= artist_rule["plays"]
            and row["unique_tracks"] >= artist_rule["unique_tracks"]
            and row["active_months"] >= artist_rule["active_months"]
        ):
            candidates.append(
                _RelationshipCandidate(
                    score=row["unique_tracks"] * 15 + row["active_months"] * 10 + row["plays"],
                    relationship_type="broad_artist",
                    row=row,
                    metrics=[
                        _metric("unique_tracks", "目录覆盖", row["unique_tracks"], "首"),
                        _metric("active_months", "活跃月份", row["active_months"], "个月"),
                        _metric("plays", "有效播放", row["plays"], "次"),
                    ],
                    title="广泛艺人聆听",
                    statement=(
                        f"全年听过其 {row['unique_tracks']} 首不同曲目，并分布在 {row['active_months']} 个月。"
                    ),
                    source_refs=[f"relationship_summary:artist:{row['identity']}"],
                )
            )
    return candidates


def _history_candidates(
    year: int,
    summaries: Mapping[str, Sequence[dict[str, Any]]],
    history_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None,
) -> list[_RelationshipCandidate]:
    if history_frames is None:
        return []
    result: list[_RelationshipCandidate] = []
    year_start = pd.Timestamp(year=year, month=1, day=1)
    new_rule = RELATIONSHIP_THRESHOLDS["new_relationship"]
    return_rule = RELATIONSHIP_THRESHOLDS["return"]
    frame_index = {"track": 0, "album": 1, "artist": 2}
    for entity_type, rows in summaries.items():
        history_frame = history_frames[frame_index[entity_type]]
        id_column = {
            "track": (
                "canonical_track_id" if "canonical_track_id" in history_frame else "track_id"
            ),
            "album": "album_project_id",
            "artist": "artist_name",
        }[entity_type]
        if history_frame.empty or id_column not in history_frame or "ts_date" not in history_frame:
            continue

        # Resolve historical date bounds once per entity type.  The previous
        # implementation filtered the entire history frame and reparsed every
        # date once for every annual entity, which made this chapter quadratic
        # in the number of entities (and dominated V2 cold starts).
        history_dates = history_frame.loc[:, [id_column, "ts_date"]].dropna(subset=[id_column])
        identities = history_dates[id_column].astype(str)
        dates = pd.to_datetime(history_dates["ts_date"], errors="coerce")
        valid = dates.notna()
        if not valid.any():
            continue
        identities = identities[valid]
        dates = dates[valid]
        first_dates = dates.groupby(identities, sort=False).min().to_dict()
        prior_mask = dates < year_start
        prior_last_dates = (
            dates[prior_mask].groupby(identities[prior_mask], sort=False).max().to_dict()
        )

        for row in rows:
            first_ever = first_dates.get(row["identity"])
            if first_ever is None:
                continue
            if (
                first_ever >= year_start
                and row["plays"] >= new_rule["plays"]
                and row["active_days"] >= new_rule["active_days"]
                and row["span_days"] >= new_rule["span_days"]
            ):
                result.append(
                    _RelationshipCandidate(
                        score=row["plays"] + row["span_days"] + row["active_days"] * 10,
                        relationship_type="new_relationship",
                        row=row,
                        metrics=[
                            _metric("first_date", "首次播放", row["first_date"]),
                            _metric("span_days", "留存跨度", row["span_days"], "天"),
                            _metric("plays", "有效播放", row["plays"], "次"),
                        ],
                        title="新关系",
                        statement=f"首次播放发生在报告年，并在此后 {row['span_days']} 天内累计 {row['plays']} 次有效播放。",
                        source_refs=[f"history:{entity_type}:{row['identity']}"],
                    )
                )
                continue
            prior_last = prior_last_dates.get(row["identity"])
            if prior_last is None:
                continue
            sleep_days = int((pd.Timestamp(row["first_date"]) - prior_last).days)
            if (
                sleep_days >= return_rule["sleep_days"]
                and row["plays"] >= return_rule["plays"]
                and row["active_days"] >= return_rule["active_days"]
            ):
                result.append(
                    _RelationshipCandidate(
                        score=sleep_days + row["plays"] + row["active_days"] * 10,
                        relationship_type="return",
                        row=row,
                        metrics=[
                            _metric("sleep_days", "沉寂跨度", sleep_days, "天"),
                            _metric("plays", "回归后播放", row["plays"], "次"),
                            _metric("active_days", "回归后活跃", row["active_days"], "天"),
                        ],
                        title="旧爱回归",
                        statement=f"相隔 {sleep_days} 天后重新播放，并在报告年累计 {row['plays']} 次有效播放。",
                        source_refs=[f"history:{entity_type}:{row['identity']}"],
                    )
                )
    return result


def _mainline_candidates(
    billboard: Mapping[str, Any],
    coverage: YearlyReviewCoverage,
) -> list[_RelationshipCandidate]:
    if coverage.billboard.status != "complete":
        return []
    result: list[_RelationshipCandidate] = []
    for key, relationship_type, title in (
        ("year_end_no1_artist", "mainline_artist", "年度主线艺人"),
        ("album_era_of_the_year", "album_era", "年度专辑时代"),
    ):
        row = dict(billboard.get("honors", {})).get(key)
        if not row:
            continue
        result.append(
            _RelationshipCandidate(
                score=10_000 + int(row.get("year_end_score", 0)),
                relationship_type=relationship_type,
                row=dict(row),
                metrics=[
                    _metric("year_end_rank", "年榜排名", int(row.get("year_end_rank", 1)), "名"),
                    _metric("weeks_on_chart", "在榜周数", int(row.get("weeks_on_chart", 0)), "周"),
                    _metric("weeks_at_no1", "冠军周数", int(row.get("weeks_at_no1", 0)), "周"),
                ],
                title=title,
                statement=(
                    f"个人 Billboard 年榜第 {int(row.get('year_end_rank', 1))}，在榜 {int(row.get('weeks_on_chart', 0))} 周，其中 {int(row.get('weeks_at_no1', 0))} 周位居冠军。"
                ),
                source_refs=[f"billboard.honors.{key}"],
            )
        )
    return result


def _divergence_candidates(
    divergence_stories: Sequence[YearlyDivergenceStory],
) -> list[_RelationshipCandidate]:
    result = []
    for item in divergence_stories:
        row: dict[str, Any] = {
            "entity_type": item.entity.entity_type,
            "identity": str(item.entity.entity_id or item.entity.name),
        }
        if item.entity.entity_type == "track":
            row.update(track_id=item.entity.entity_id, track_name=item.entity.name)
        elif item.entity.entity_type == "album":
            row.update(
                album_project_id=item.entity.entity_id,
                album_name=item.entity.name,
                artist_name=item.entity.artist_name,
            )
        else:
            row.update(artist_name=item.entity.name)
        result.append(
            _RelationshipCandidate(
                score=5_000 + abs(item.rank_gap) * 100,
                relationship_type="season_divergence",
                row=row,
                metrics=[
                    _metric("play_rank", "播放排名", item.play_rank, "名"),
                    _metric(
                        "billboard_year_end_rank",
                        "个人 Billboard 年榜排名",
                        item.billboard_year_end_rank,
                        "名",
                    ),
                ],
                title=(
                    "赛季更持久"
                    if item.interpretation == "season_more_persistent"
                    else "总量更集中"
                ),
                statement=(
                    f"播放榜第 {item.play_rank}，个人 Billboard 年榜第 {item.billboard_year_end_rank}，两种视角相差 {abs(item.rank_gap)} 位。"
                ),
                source_refs=["honors.divergence_stories"],
            )
        )
    return result


def build_relationships(
    year: int,
    coverage: YearlyReviewCoverage,
    entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    billboard: Mapping[str, Any],
    *,
    divergence_stories: Sequence[YearlyDivergenceStory] = (),
    history_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None = None,
) -> list[YearlyRelationshipStory]:
    """Select relationship stories under the frozen caps and evidence rules."""
    if coverage.play.natural_days_span < MIN_RELATIONSHIP_SPAN_DAYS:
        return []
    summaries = _summaries(entity_frames)
    candidates = [
        *_mainline_candidates(billboard, coverage),
        *_divergence_candidates(divergence_stories),
        *_threshold_candidates(summaries),
        *_history_candidates(year, summaries, history_frames),
    ]
    candidates.sort(
        key=lambda item: (-item.score, item.relationship_type, item.row.get("identity", ""))
    )
    entity_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    selected: list[YearlyRelationshipStory] = []
    for index, candidate in enumerate(candidates, start=1):
        entity_type = str(candidate.row.get("entity_type") or "")
        ref = entity_ref(candidate.row, entity_type or None)
        if ref is None or len(candidate.metrics) < 2:
            continue
        identity = f"{ref.entity_type}:{ref.entity_id or ref.name}".casefold()
        if entity_counts[identity] >= RELATIONSHIP_ENTITY_CAP:
            continue
        if type_counts[candidate.relationship_type] >= RELATIONSHIP_PER_TYPE_CAP:
            continue
        selected.append(
            YearlyRelationshipStory(
                story_id=f"{RELATIONSHIP_POLICY_VERSION}-{candidate.relationship_type}-{index}",
                relationship_type=candidate.relationship_type,
                title=candidate.title,
                statement=candidate.statement,
                entity=ref,
                evidence_grade="C",
                evidence_status="sufficient",
                metrics=candidate.metrics,
                source_refs=candidate.source_refs,
            )
        )
        entity_counts[identity] += 1
        type_counts[candidate.relationship_type] += 1
    return selected

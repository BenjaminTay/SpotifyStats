"""長線陪伴：連續天數、跨度、回歸和長期陪伴記錄（P0 核心 section）。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.domains.playback.records_helpers import (
    grouped_records_duration,
    safe_groupby_cols,
    safe_rename,
    unique_cols,
)
from backend.domains.playback.records_sorting import sort_and_limit


def _duration_totals(frame: pd.DataFrame, group_col: str) -> dict[object, float]:
    grouped = grouped_records_duration(frame, [group_col])
    if grouped.empty:
        return {}
    return dict(zip(grouped[group_col], grouped["total_ms"].astype(float)))


def _event_totals(frame: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Precompute per-entity counts and raw durations without repeated full-frame scans."""
    return frame.groupby(group_col, sort=False).agg(
        total_plays=("play_id", "count"),
        event_total_ms=("ms_played", "sum"),
    )


@dataclass(frozen=True)
class _PresenceFacts:
    entity_id: object
    name: str
    artist: str
    dates: tuple
    first_date: object
    last_date: object
    total_plays: int
    total_ms: float
    total_hours: float


@dataclass(frozen=True)
class _LongevityFacts:
    presence: tuple[_PresenceFacts, ...]
    named_totals: pd.DataFrame
    group_cols: tuple[str, ...]


def _build_longevity_facts(frame, group_col, name_col, artist_col):
    """Read-only per-frame facts; entity-only and named grains stay distinct."""
    cols = unique_cols(group_col, name_col, artist_col, "ts_date")
    presence = frame[cols].drop_duplicates().sort_values(unique_cols(group_col, "ts_date"))
    presence["ts_date"] = pd.to_datetime(presence["ts_date"])
    presence["_record_date"] = presence["ts_date"].dt.date
    duration_totals = _duration_totals(frame, group_col)
    event_totals = _event_totals(frame, group_col)
    # Presence is already sorted by entity/date. Iterate its compact tuples
    # once instead of constructing thousands of DataFrames and Series lookups.
    from itertools import groupby

    entities = []
    column_index = {column: index for index, column in enumerate(presence.columns)}
    group_index = column_index[group_col]
    date_index = column_index["_record_date"]
    totals_by_entity = event_totals.to_dict("index")
    duration_by_entity = duration_totals
    for entity_id, group in groupby(
        presence.itertuples(index=False, name=None), lambda row: row[group_index]
    ):
        if pd.isna(entity_id):
            continue  # Same null exclusion as pandas groupby.
        rows = list(group)
        dates = tuple(sorted({row[date_index] for row in rows if pd.notna(row[date_index])}))
        totals = totals_by_entity[entity_id]
        total_ms = duration_by_entity.get(entity_id)
        if total_ms is None:
            total_ms = float(totals["event_total_ms"])
        entities.append(
            _PresenceFacts(
                entity_id=entity_id,
                name=str(rows[0][column_index[name_col]])
                if name_col in column_index
                else str(entity_id),
                artist=str(rows[0][column_index[artist_col]]) if artist_col in column_index else "",
                dates=dates,
                first_date=rows[0][date_index],
                last_date=rows[-1][date_index],
                total_plays=int(totals["total_plays"]),
                total_ms=total_ms,
                total_hours=round(total_ms / 3_600_000, 1),
            )
        )

    # Span/month records retain the original name-sensitive grouping, including
    # pandas' null exclusion. Do not derive these from entity-only totals.
    gb_cols = safe_groupby_cols([], group_col, name_col, artist_col)
    named = frame[unique_cols(*gb_cols, "ts_date", "play_id")].copy()
    named["_ym"] = named["ts_date"].astype(str).str[:7]
    named["ts_date"] = pd.to_datetime(named["ts_date"])
    named = (
        named.groupby(gb_cols)
        .agg(
            first_date=("ts_date", "min"),
            last_date=("ts_date", "max"),
            total_plays=("play_id", "count"),
            active_months=("_ym", "nunique"),
        )
        .reset_index()
    )
    named = named.merge(grouped_records_duration(frame, gb_cols), on=gb_cols, how="left")
    named["total_ms"] = named["total_ms"].fillna(0)
    named["first_date"] = pd.to_datetime(named["first_date"])
    named["last_date"] = pd.to_datetime(named["last_date"])
    return _LongevityFacts(tuple(entities), named, tuple(gb_cols))


def _longest_streak_days(
    frame, group_col, name_col, artist_col, entity_type="track", *, facts=None
):
    """最長連續播放天數。"""
    if frame.empty:
        return pd.DataFrame()

    facts = facts or _build_longevity_facts(frame, group_col, name_col, artist_col)

    results = []
    for item in facts.presence:
        entity_id, name, artist, dates = item.entity_id, item.name, item.artist, item.dates
        if not dates:
            continue

        total_plays, total_ms, total_hours = item.total_plays, item.total_ms, item.total_hours

        if len(dates) < 2:
            results.append(
                {
                    "entity_id": str(entity_id),
                    "name": name,
                    "artist_name": artist,
                    "streak_days": 1,
                    "start_date": str(item.first_date),
                    "end_date": str(item.last_date),
                    "total_plays": total_plays,
                    "total_ms": total_ms,
                    "total_hours": total_hours,
                }
            )
            continue

        max_streak = 1
        current_streak = 1
        streak_start = dates[0]
        best_start = dates[0]
        best_end = dates[0]

        for i in range(1, len(dates)):
            diff = (dates[i] - dates[i - 1]).days
            if diff == 1:
                current_streak += 1
                if current_streak > max_streak:
                    max_streak = current_streak
                    best_start = streak_start
                    best_end = dates[i]
            elif diff > 1:
                current_streak = 1
                streak_start = dates[i]

        results.append(
            {
                "entity_id": str(entity_id),
                "name": name,
                "artist_name": artist,
                "streak_days": max_streak,
                "start_date": str(best_start),
                "end_date": str(best_end),
                "total_plays": total_plays,
                "total_ms": total_ms,
                "total_hours": total_hours,
            }
        )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = sort_and_limit(
        df,
        ["streak_days", "total_plays", "total_ms", "end_date", "entity_id"],
        [False, False, False, False, True],
    )
    df["entity_type"] = entity_type
    df["value"] = df["streak_days"].astype(float)
    df["unit"] = "天連續播放"
    df["secondary_value"] = df["total_hours"].astype(float)
    df["secondary_unit"] = "小時"
    return df


def _longest_span(frame, group_col, name_col, artist_col, entity_type="track", *, facts=None):
    """最長陪伴跨度。"""
    if frame.empty:
        return pd.DataFrame()

    facts = facts or _build_longevity_facts(frame, group_col, name_col, artist_col)
    span = facts.named_totals[
        [*facts.group_cols, "first_date", "last_date", "total_plays", "total_ms"]
    ].copy()
    span["span_days"] = (span["last_date"] - span["first_date"]).dt.days + 1
    span["entity_id"] = span[group_col].astype(str)
    span = sort_and_limit(
        span,
        ["span_days", "total_plays", "total_ms", "last_date", "entity_id"],
        [False, False, False, False, True],
    )
    span["entity_type"] = entity_type
    span["value"] = span["span_days"].astype(float)
    span["unit"] = "天跨度"
    span["start_date"] = span["first_date"].dt.strftime("%Y-%m-%d")
    span["end_date"] = span["last_date"].dt.strftime("%Y-%m-%d")
    span["total_hours"] = (span["total_ms"] / 3_600_000).round(1)
    span["secondary_value"] = span["total_hours"].astype(float)
    span["secondary_unit"] = "小時"
    span = safe_rename(span, name_col, artist_col)
    return span


def _comeback_after_sleep(
    frame, group_col, name_col, artist_col, entity_type="track", *, facts=None
):
    """沉睡後回歸。"""
    if frame.empty:
        return pd.DataFrame()

    facts = facts or _build_longevity_facts(frame, group_col, name_col, artist_col)

    results = []
    for item in facts.presence:
        entity_id, dates = item.entity_id, item.dates
        if len(dates) < 2:
            continue
        max_gap = 0
        gap_before = None
        gap_after = None
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i - 1]).days
            if gap > max_gap:
                max_gap = gap
                gap_before = dates[i - 1]
                gap_after = dates[i]

        if max_gap >= 7:
            name, artist = item.name, item.artist
            total_plays, total_ms, total_hours = item.total_plays, item.total_ms, item.total_hours
            results.append(
                {
                    "entity_id": str(entity_id),
                    "name": name,
                    "artist_name": artist,
                    "gap_days": max_gap,
                    "sleep_start": str(gap_before),
                    "wake_date": str(gap_after),
                    "total_plays": total_plays,
                    "total_ms": total_ms,
                    "total_hours": total_hours,
                }
            )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = sort_and_limit(
        df,
        ["gap_days", "total_plays", "total_ms", "wake_date", "entity_id"],
        [False, False, False, False, True],
    )
    df["entity_type"] = entity_type
    df["value"] = df["gap_days"].astype(float)
    df["unit"] = "天後回歸"
    df["start_date"] = df["sleep_start"]
    df["end_date"] = df["wake_date"]
    df["secondary_value"] = df["total_hours"].astype(float)
    df["secondary_unit"] = "小時"
    return df


def _most_active_months(frame, group_col, name_col, artist_col, entity_type="track", *, facts=None):
    """最活躍月份。"""
    if frame.empty:
        return pd.DataFrame()
    facts = facts or _build_longevity_facts(frame, group_col, name_col, artist_col)
    active = facts.named_totals[
        [*facts.group_cols, "active_months", "total_plays", "total_ms"]
    ].copy()
    active["entity_id"] = active[group_col].astype(str)
    active = sort_and_limit(
        active,
        ["active_months", "total_plays", "total_ms", "entity_id"],
        [False, False, False, True],
    )
    active["entity_type"] = entity_type
    active["entity_id"] = active[group_col].astype(str)
    active["value"] = active["active_months"].astype(float)
    active["unit"] = "個活躍月份"
    active["total_hours"] = (active["total_ms"] / 3_600_000).round(1)
    active = safe_rename(active, name_col, artist_col)
    return active


def _user_active_streak(event_frame):
    """用戶連續活躍天數。"""
    if event_frame.empty:
        return pd.DataFrame()
    dates = sorted(pd.to_datetime(event_frame["ts_date"].drop_duplicates()).dt.date.tolist())
    if not dates:
        return pd.DataFrame()

    max_streak = 1
    current_streak = 1
    best_start = dates[0]
    best_end = dates[0]
    streak_start = dates[0]

    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current_streak += 1
        else:
            if current_streak > max_streak:
                max_streak = current_streak
                best_start = streak_start
                best_end = dates[i - 1]
            current_streak = 1
            streak_start = dates[i]

    if current_streak > max_streak:
        max_streak = current_streak
        best_start = streak_start
        best_end = dates[-1]

    return pd.DataFrame(
        [
            {
                "rank": 1,
                "name": "最長連續活躍",
                "value": float(max_streak),
                "unit": "天連續活躍",
                "start_date": str(best_start),
                "end_date": str(best_end),
                "secondary_value": float(len(dates)),
                "secondary_unit": "天活躍總數",
                "caption": f"從 {dates[0]} 到 {dates[-1]}，共 {len(dates)} 天有播放記錄",
            }
        ]
    )


def _entity_longevity_records(frame, group_col, name_col, artist_col, entity_type):
    if frame.empty:
        return {
            "longest_streak_days": pd.DataFrame(),
            "longest_span": pd.DataFrame(),
            "comeback_after_sleep": pd.DataFrame(),
            "most_active_months": pd.DataFrame(),
        }
    facts = _build_longevity_facts(frame, group_col, name_col, artist_col)
    return {
        "longest_streak_days": _longest_streak_days(
            frame, group_col, name_col, artist_col, entity_type, facts=facts
        ),
        "longest_span": _longest_span(
            frame, group_col, name_col, artist_col, entity_type, facts=facts
        ),
        "comeback_after_sleep": _comeback_after_sleep(
            frame, group_col, name_col, artist_col, entity_type, facts=facts
        ),
        "most_active_months": _most_active_months(
            frame, group_col, name_col, artist_col, entity_type, facts=facts
        ),
    }


def _group_col_for(frame, entity_type):
    if entity_type == "track":
        return (
            "canonical_track_id" if "canonical_track_id" in frame.columns else "track_id",
            "canonical_track_name" if "canonical_track_name" in frame.columns else "track_name",
            "artist_name",
        )
    elif entity_type == "album":
        return (
            "album_project_id" if "album_project_id" in frame.columns else "album_name",
            "album_project_name" if "album_project_name" in frame.columns else "album_name",
            "artist_name",
        )
    else:
        return "artist_name", "artist_name", "artist_name"


def compute_longevity_records(
    records: dict,
    event_frame: pd.DataFrame,
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
):
    """Populate longevity records."""
    for entity_type, frame in [
        ("track", track_frame),
        ("album", album_frame),
        ("artist", artist_frame),
    ]:
        if frame.empty:
            tr = {
                "longest_streak_days": pd.DataFrame(),
                "longest_span": pd.DataFrame(),
                "comeback_after_sleep": pd.DataFrame(),
                "most_active_months": pd.DataFrame(),
            }
        else:
            gcol, ncol, acol = _group_col_for(frame, entity_type)
            tr = _entity_longevity_records(frame, gcol, ncol, acol, entity_type)

        records[f"longevity_streak_{entity_type}"] = tr["longest_streak_days"]
        records[f"longevity_span_{entity_type}"] = tr["longest_span"]
        records[f"longevity_comeback_{entity_type}"] = tr["comeback_after_sleep"]
        records[f"longevity_active_months_{entity_type}"] = tr["most_active_months"]

    records["longevity_user_streak"] = _user_active_streak(event_frame)

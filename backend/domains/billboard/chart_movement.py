"""Movement facts for the lightweight personal Billboard home preview."""

from __future__ import annotations

from typing import Any

import pandas as pd


def _scalar_value(row: pd.Series, column: str) -> Any:
    value = row.get(column)
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _identity_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        try:
            if float(value).is_integer():
                return str(int(value))
        except (TypeError, ValueError, OverflowError):
            pass
    return str(value)


def _identity(row: pd.Series, entity_type: str) -> tuple[str, ...]:
    stable_columns: tuple[str, ...]
    name_columns: tuple[str, ...]
    if entity_type == "track":
        stable_columns = ("track_id", "l1_id")
        name_columns = ("track_name", "artist_name")
    elif entity_type == "album":
        stable_columns = ("album_project_id", "album_id")
        name_columns = ("album_name", "artist_name")
    else:
        stable_columns = ("artist_id",)
        name_columns = ("artist_name",)

    for column in stable_columns:
        value = _scalar_value(row, column)
        if value is not None:
            return ("stable", column, _identity_value(value))
    return ("name",) + tuple(
        _identity_value(_scalar_value(row, column) or "") for column in name_columns
    )


def _week_key(value: Any) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _rows_for_week(frame: pd.DataFrame, week: str) -> pd.DataFrame:
    if frame.empty or "billboard_week" not in frame.columns:
        return frame.iloc[0:0]
    mask = frame["billboard_week"].map(_week_key) == week
    return frame.loc[mask]


def _rank(row: pd.Series) -> int | None:
    value = _scalar_value(row, "rank")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_entity_row_for_type(
    frame: pd.DataFrame,
    identity: tuple[str, ...],
    entity_type: str,
) -> pd.Series | None:
    for _, row in frame.iterrows():
        if _identity(row, entity_type) == identity:
            return row
    return None


def _movement_for(
    frame: pd.DataFrame,
    *,
    latest_week: str,
    previous_week: str | None,
    historical_weeks: list[str],
    entity_type: str,
    top_n: int,
) -> dict[str, Any] | None:
    current_rows = _rows_for_week(frame, latest_week)
    current = None
    for _, row in current_rows.iterrows():
        if _rank(row) == 1:
            current = row
            break
    if current is None:
        return None

    identity = _identity(current, entity_type)
    previous = (
        _find_entity_row_for_type(_rows_for_week(frame, previous_week), identity, entity_type)
        if previous_week
        else None
    )
    previous_rank = _rank(previous) if previous is not None else None
    if previous_rank is not None and previous_rank <= top_n:
        delta = previous_rank - 1
        if delta > 0:
            movement = "up"
        elif delta < 0:
            movement = "down"
        else:
            movement = "same"
        return {
            "movement": movement,
            "previous_rank": previous_rank,
            "rank_change": delta,
        }

    for week in historical_weeks:
        historical = _find_entity_row_for_type(_rows_for_week(frame, week), identity, entity_type)
        historical_rank = _rank(historical) if historical is not None else None
        if historical_rank is not None and historical_rank <= top_n:
            return {
                "movement": "re",
                "previous_rank": None,
                "rank_change": None,
            }

    return {
        "movement": "new",
        "previous_rank": None,
        "rank_change": None,
    }


def build_home_billboard_movement(
    weekly: pd.DataFrame,
    weekly_album: pd.DataFrame,
    weekly_artist: pd.DataFrame,
    all_weeks_desc: list[Any],
    *,
    bb_top_n: int,
    bb_album_top_n: int,
    bb_artist_top_n: int,
) -> dict[str, dict[str, Any] | None]:
    """Build movement for the current champion against the published Top N.

    The ranking frames retain the published Top-N boundary.  That is enough
    to distinguish a current champion's prior-week movement from re-entry:
    absence in the prior week means it was outside Top N, while any older
    Top-N row proves that it charted before.
    """
    weeks = [key for value in all_weeks_desc if (key := _week_key(value)) is not None]
    latest_week = weeks[0] if weeks else None
    previous_week = weeks[1] if len(weeks) > 1 else None
    if latest_week is None:
        return {"track": None, "album": None, "artist": None}

    historical_weeks = weeks[2:]
    return {
        "track": _movement_for(
            weekly,
            latest_week=latest_week,
            previous_week=previous_week,
            historical_weeks=historical_weeks,
            entity_type="track",
            top_n=bb_top_n,
        ),
        "album": _movement_for(
            weekly_album,
            latest_week=latest_week,
            previous_week=previous_week,
            historical_weeks=historical_weeks,
            entity_type="album",
            top_n=bb_album_top_n,
        ),
        "artist": _movement_for(
            weekly_artist,
            latest_week=latest_week,
            previous_week=previous_week,
            historical_weeks=historical_weeks,
            entity_type="artist",
            top_n=bb_artist_top_n,
        ),
    }

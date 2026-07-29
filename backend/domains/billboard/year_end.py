"""Billboard Year-End annual chart scoring."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from backend.domains.billboard.chart_power_score import (
    _aggregate_scored_rows,
    _score_ranked_rows,
)

YEAR_END_TRACK_TOP_N = 50
YEAR_END_ALBUM_TOP_N = 30
YEAR_END_ARTIST_TOP_N = 30
YEAR_END_SEMANTICS_VERSION = "year_end_v3"

EMPTY_HONORS: dict[str, Any] = {
    "year_end_no1_track": None,
    "year_end_no1_album": None,
    "year_end_no1_artist": None,
    "longest_charting_track": None,
    "longest_charting_album": None,
    "longest_charting_artist": None,
    "biggest_no1_run_track": None,
    "biggest_no1_run_album": None,
    "biggest_no1_run_artist": None,
    "top_new_entry_track": None,
    "breakthrough_artist": None,
    "album_era_of_the_year": None,
}


def _ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "billboard_week" in out.columns:
        out["billboard_week"] = pd.to_datetime(out["billboard_week"])
    return out


def _ensure_artist_names(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "track_id" not in df.columns or "artist_name" not in df.columns:
        return df
    if "artist_names" in df.columns:
        return df

    out = df.copy()
    out["artist_names"] = out["artist_name"].apply(lambda value: [value] if pd.notna(value) else [])
    return out


def _annual_window(df: pd.DataFrame, year: int) -> pd.DataFrame:
    if df.empty or "billboard_week" not in df.columns:
        return df.copy()
    out = _ensure_datetime(df)
    return out[out["billboard_week"].dt.year == year].copy()


def available_years_from_weekly(*frames: pd.DataFrame) -> list[int]:
    years: set[int] = set()
    for frame in frames:
        if frame.empty or "billboard_week" not in frame.columns:
            continue
        weeks = pd.to_datetime(frame["billboard_week"], errors="coerce")
        years.update(int(year) for year in weeks.dt.year.dropna().unique())
    return sorted(years)


def _all_week_count(*frames: pd.DataFrame) -> int:
    weeks: set[pd.Timestamp] = set()
    for frame in frames:
        if frame.empty or "billboard_week" not in frame.columns:
            continue
        parsed = pd.to_datetime(frame["billboard_week"], errors="coerce").dropna()
        weeks.update(parsed)
    return len(weeks)


def _expected_billboard_weeks(year: int, week_start_dow: int) -> pd.DatetimeIndex:
    year_start = pd.Timestamp(year=year, month=1, day=1)
    year_end = pd.Timestamp(year=year, month=12, day=31)
    offset = (week_start_dow - year_start.dayofweek) % 7
    first_week = year_start + pd.Timedelta(days=offset)
    return pd.date_range(first_week, year_end, freq="7D")


def _coverage_meta(
    year: int,
    week_start_dow: int,
    *frames: pd.DataFrame,
    coverage_source: pd.DataFrame | None = None,
) -> dict[str, Any]:
    observed: set[pd.Timestamp] = set()
    for frame in frames:
        if frame.empty or "billboard_week" not in frame.columns:
            continue
        weeks = pd.to_datetime(frame["billboard_week"], errors="coerce").dropna().dt.normalize()
        observed.update(weeks)

    expected = _expected_billboard_weeks(year, week_start_dow)
    observed_weeks = sorted(observed)
    expected_weeks = list(expected)
    if not observed_weeks:
        return {
            "coverage_status": "empty",
            "is_complete_year": False,
            "period_start": None,
            "period_end": None,
            "first_billboard_week": None,
            "last_billboard_week": None,
            "observed_weeks": 0,
            "expected_weeks": len(expected_weeks),
            "has_internal_gaps": False,
        }

    first_observed = observed_weeks[0]
    last_observed = observed_weeks[-1]
    expected_between = {week for week in expected_weeks if first_observed <= week <= last_observed}
    has_internal_gaps = not expected_between.issubset(observed)
    starts_at_year_boundary = bool(expected_weeks and first_observed == expected_weeks[0])
    ends_at_year_boundary = bool(expected_weeks and last_observed == expected_weeks[-1])
    is_complete = (
        starts_at_year_boundary
        and ends_at_year_boundary
        and not has_internal_gaps
        and len(observed_weeks) == len(expected_weeks)
    )
    if is_complete:
        status = "complete"
    elif has_internal_gaps:
        status = "incomplete"
    elif not starts_at_year_boundary and ends_at_year_boundary:
        status = "partial_start"
    elif starts_at_year_boundary and not ends_at_year_boundary:
        status = "year_to_date"
    else:
        status = "partial_range"

    period_start = first_observed
    period_end = last_observed
    if coverage_source is not None and not coverage_source.empty:
        date_column = next(
            (column for column in ("ts_date", "ts") if column in coverage_source.columns),
            None,
        )
        if date_column is not None:
            source_dates = pd.to_datetime(
                coverage_source[date_column],
                errors="coerce",
                utc=True,
            ).dropna()
            if not source_dates.empty:
                period_start = source_dates.min()
                period_end = source_dates.max()
        else:
            bounds = coverage_source.attrs.get("coverage_periods", {}).get(year)
            if bounds:
                period_start, period_end = bounds

    return {
        "coverage_status": status,
        "is_complete_year": is_complete,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "first_billboard_week": first_observed.isoformat(),
        "last_billboard_week": last_observed.isoformat(),
        "observed_weeks": len(observed_weeks),
        "expected_weeks": len(expected_weeks),
        "has_internal_gaps": has_internal_gaps,
    }


def _first_chart_map(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=group_cols + ["true_first_week", "true_first_rank"])

    sorted_df = _ensure_datetime(df).sort_values(group_cols + ["billboard_week"], kind="stable")
    return (
        sorted_df.drop_duplicates(group_cols, keep="first")[group_cols + ["billboard_week", "rank"]]
        .rename(columns={"billboard_week": "true_first_week", "rank": "true_first_rank"})
        .reset_index(drop=True)
    )


def _first_last_map(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=group_cols + ["first_week", "last_week"])
    return (
        _ensure_datetime(df)
        .groupby(group_cols, sort=False)
        .agg(first_week=("billboard_week", "min"), last_week=("billboard_week", "max"))
        .reset_index()
    )


def _weeks_at_no1(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=group_cols + ["weeks_at_no1"])
    return (
        df[df["rank"] == 1]
        .groupby(group_cols, sort=False)["billboard_week"]
        .nunique()
        .reset_index(name="weeks_at_no1")
    )


def _cover_map(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty or "cover_url" not in df.columns:
        return pd.DataFrame(columns=group_cols + ["cover_url"])

    covers = df.dropna(subset=["cover_url"])
    if covers.empty:
        return pd.DataFrame(columns=group_cols + ["cover_url"])
    return covers.drop_duplicates(group_cols, keep="first")[group_cols + ["cover_url"]]


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _clean(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _int_value(value: Any, default: int = 0) -> int:
    value = _clean(value)
    if value is None:
        return default
    return int(value)


def _year_matches(value: Any, year: int) -> bool:
    if value is None:
        return False
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return False
    return int(parsed.year) == year


def sort_year_end_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            -_int_value(row.get("year_end_score")),
            -_int_value(row.get("weeks_at_no1")),
            _int_value(row.get("peak_position"), 9999),
            -_int_value(row.get("weeks_top10")),
            -_int_value(row.get("chart_plays")),
        ),
    )
    for index, row in enumerate(sorted_rows, start=1):
        row["year_end_rank"] = index
    return sorted_rows


def _add_year_end_score(scores: pd.DataFrame) -> pd.DataFrame:
    """V3: 年度积分只累计现有周积分，不重复叠加年度奖励。"""
    out = scores.copy()
    out["year_end_score"] = out["raw_score"].round().astype(int)
    return out


def _track_rows(
    full_weekly: pd.DataFrame,
    annual_weekly: pd.DataFrame,
    annual_all_weekly: pd.DataFrame,
    year: int,
) -> list[dict[str, Any]]:
    if annual_weekly.empty:
        return []

    annual_weekly = _ensure_artist_names(annual_weekly)
    scored = _score_ranked_rows(annual_weekly)
    scores = _add_year_end_score(_aggregate_scored_rows(scored, "track_id"))
    scores = scores.merge(_first_chart_map(full_weekly, ["track_id"]), on="track_id", how="left")

    scores["is_true_debut_no1"] = scores.apply(
        lambda row: (
            _year_matches(row.get("true_first_week"), year)
            and _int_value(row.get("true_first_rank")) == 1
        ),
        axis=1,
    )
    scores = scores.merge(_weeks_at_no1(annual_weekly, ["track_id"]), on="track_id", how="left")
    scores["weeks_at_no1"] = scores["weeks_at_no1"].fillna(0).astype(int)

    dim_cols = [
        col
        for col in ["track_id", "track_name", "artist_name", "artist_names", "album_name"]
        if col in annual_weekly.columns
    ]
    dims = annual_weekly.drop_duplicates("track_id", keep="first")[dim_cols]
    rows = scores.merge(dims, on="track_id", how="left")
    rows = rows.merge(_first_last_map(annual_weekly, ["track_id"]), on="track_id", how="left")
    rows = rows.merge(_cover_map(annual_weekly, ["track_id"]), on="track_id", how="left")
    plays = annual_weekly.groupby("track_id", sort=False)["play_count"].sum()
    rows = rows.merge(plays.reset_index(name="chart_plays"), on="track_id", how="left")
    annual_plays = annual_all_weekly.groupby("track_id", sort=False)["play_count"].sum()
    rows = rows.merge(annual_plays.reset_index(name="annual_plays"), on="track_id", how="left")
    rows["weeks_at_no1"] = rows["weeks_at_no1"].fillna(0).astype(int)

    result = []
    for row in rows.to_dict("records"):
        result.append(
            {
                "track_id": _int_value(row.get("track_id")),
                "track_name": _clean(row.get("track_name")),
                "artist_name": _clean(row.get("artist_name")),
                "artist_names": row.get("artist_names")
                if isinstance(row.get("artist_names"), list)
                else [],
                "album_name": _clean(row.get("album_name")),
                "cover_url": _clean(row.get("cover_url")),
                "year_end_score": _int_value(row.get("year_end_score")),
                "year_end_rank": 0,
                "peak_position": _int_value(row.get("peak_position")),
                "weeks_on_chart": _int_value(row.get("weeks_on_chart")),
                "weeks_at_peak": _int_value(row.get("weeks_at_peak")),
                "weeks_at_no1": _int_value(row.get("weeks_at_no1")),
                "weeks_top5": _int_value(row.get("weeks_top5")),
                "weeks_top10": _int_value(row.get("weeks_top10")),
                "chart_plays": _int_value(row.get("chart_plays")),
                "annual_plays": _int_value(row.get("annual_plays")),
                "first_week": _iso(row.get("first_week")),
                "last_week": _iso(row.get("last_week")),
                "true_first_week": _iso(row.get("true_first_week")),
                "is_true_debut_no1": bool(row.get("is_true_debut_no1", False)),
            }
        )
    return sort_year_end_rows(result)


def _album_or_artist_rows(
    full_df: pd.DataFrame,
    annual_df: pd.DataFrame,
    annual_all_df: pd.DataFrame,
    year: int,
    group_cols: list[str],
) -> list[dict[str, Any]]:
    if annual_df.empty:
        return []

    scored = _score_ranked_rows(annual_df)
    scores = _add_year_end_score(_aggregate_scored_rows(scored, group_cols))
    scores = scores.merge(_weeks_at_no1(annual_df, group_cols), on=group_cols, how="left")
    scores["weeks_at_no1"] = scores["weeks_at_no1"].fillna(0).astype(int)

    scores = scores.merge(_first_chart_map(full_df, group_cols), on=group_cols, how="left")
    scores = scores.merge(_first_last_map(annual_df, group_cols), on=group_cols, how="left")
    scores = scores.merge(_cover_map(annual_df, group_cols), on=group_cols, how="left")
    plays = (
        annual_df.groupby(group_cols, sort=False)["play_count"]
        .sum()
        .reset_index(name="chart_plays")
    )
    scores = scores.merge(plays, on=group_cols, how="left")
    annual_plays = (
        annual_all_df.groupby(group_cols, sort=False)["play_count"]
        .sum()
        .reset_index(name="annual_plays")
    )
    scores = scores.merge(annual_plays, on=group_cols, how="left")

    optional_cols = [col for col in ["release_date", "album_type"] if col in annual_df.columns]
    if optional_cols:
        dims = annual_df.drop_duplicates(group_cols, keep="first")[group_cols + optional_cols]
        scores = scores.merge(dims, on=group_cols, how="left")

    result = []
    for row in scores.to_dict("records"):
        item = {
            "year_end_score": _int_value(row.get("year_end_score")),
            "year_end_rank": 0,
            "peak_position": _int_value(row.get("peak_position")),
            "weeks_on_chart": _int_value(row.get("weeks_on_chart")),
            "weeks_at_peak": _int_value(row.get("weeks_at_peak")),
            "weeks_at_no1": _int_value(row.get("weeks_at_no1")),
            "weeks_top5": _int_value(row.get("weeks_top5")),
            "weeks_top10": _int_value(row.get("weeks_top10")),
            "chart_plays": _int_value(row.get("chart_plays")),
            "annual_plays": _int_value(row.get("annual_plays")),
            "first_week": _iso(row.get("first_week")),
            "last_week": _iso(row.get("last_week")),
            "true_first_week": _iso(row.get("true_first_week")),
            "is_new_entry": _year_matches(row.get("true_first_week"), year),
            "cover_url": _clean(row.get("cover_url")),
        }
        for col in group_cols + optional_cols:
            item[col] = _iso(row.get(col)) if col == "release_date" else _clean(row.get(col))
        result.append(item)
    return sort_year_end_rows(result)


def _best_by_metric(
    rows: list[dict[str, Any]],
    key: str,
    *,
    score_tie_break: bool = False,
) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda row: (
            -_int_value(row.get(key)),
            -_int_value(row.get("year_end_score")) if score_tie_break else 0,
            _int_value(row.get("year_end_rank")),
        ),
    )[0]


def build_honors(
    tracks: list[dict[str, Any]],
    albums: list[dict[str, Any]],
    artists: list[dict[str, Any]],
) -> dict[str, Any]:
    honors = dict(EMPTY_HONORS)
    honors["year_end_no1_track"] = tracks[0] if tracks else None
    honors["year_end_no1_album"] = albums[0] if albums else None
    honors["year_end_no1_artist"] = artists[0] if artists else None
    honors["longest_charting_track"] = _best_by_metric(tracks, "weeks_on_chart")
    honors["longest_charting_album"] = _best_by_metric(albums, "weeks_on_chart")
    honors["longest_charting_artist"] = _best_by_metric(artists, "weeks_on_chart")
    honors["biggest_no1_run_track"] = _best_by_metric(
        tracks,
        "weeks_at_no1",
        score_tie_break=True,
    )
    honors["biggest_no1_run_album"] = _best_by_metric(
        albums,
        "weeks_at_no1",
        score_tie_break=True,
    )
    honors["biggest_no1_run_artist"] = _best_by_metric(
        artists,
        "weeks_at_no1",
        score_tie_break=True,
    )
    honors["top_new_entry_track"] = next(
        (row for row in tracks if row.get("true_first_week") == row.get("first_week")),
        None,
    )
    honors["breakthrough_artist"] = next((row for row in artists if row.get("is_new_entry")), None)
    honors["album_era_of_the_year"] = albums[0] if albums else None
    return honors


def _empty_response(
    top_n: int,
    album_top_n: int,
    artist_top_n: int,
    weekly_top_n: int,
    weekly_album_top_n: int,
    weekly_artist_top_n: int,
    week_start_dow: int,
    week_start_hour: int,
) -> dict[str, Any]:
    return {
        "meta": {
            "year": None,
            "available_years": [],
            "total_weeks": 0,
            "top_n": top_n,
            "album_top_n": album_top_n,
            "artist_top_n": artist_top_n,
            "year_end_top_n": top_n,
            "year_end_album_top_n": album_top_n,
            "year_end_artist_top_n": artist_top_n,
            "weekly_top_n": weekly_top_n,
            "weekly_album_top_n": weekly_album_top_n,
            "weekly_artist_top_n": weekly_artist_top_n,
            "week_start_dow": week_start_dow,
            "week_start_hour": week_start_hour,
            "score_label": "Year-End Score",
            "semantics_version": YEAR_END_SEMANTICS_VERSION,
            "coverage_status": "empty",
            "is_complete_year": False,
            "period_start": None,
            "period_end": None,
            "first_billboard_week": None,
            "last_billboard_week": None,
            "observed_weeks": 0,
            "expected_weeks": 0,
            "has_internal_gaps": False,
        },
        "tracks": [],
        "albums": [],
        "artists": [],
        "honors": dict(EMPTY_HONORS),
    }


def build_year_end_response(
    weekly: pd.DataFrame,
    weekly_album: pd.DataFrame,
    weekly_artist: pd.DataFrame,
    year: int | None,
    top_n: int,
    album_top_n: int,
    artist_top_n: int,
    week_start_dow: int,
    week_start_hour: int,
    *,
    weekly_top_n: int | None = None,
    weekly_album_top_n: int | None = None,
    weekly_artist_top_n: int | None = None,
    all_weekly: pd.DataFrame | None = None,
    all_weekly_album: pd.DataFrame | None = None,
    all_weekly_artist: pd.DataFrame | None = None,
    coverage_source: pd.DataFrame | None = None,
) -> dict[str, Any]:
    weekly_top_n = top_n if weekly_top_n is None else weekly_top_n
    weekly_album_top_n = album_top_n if weekly_album_top_n is None else weekly_album_top_n
    weekly_artist_top_n = artist_top_n if weekly_artist_top_n is None else weekly_artist_top_n
    all_weekly = weekly if all_weekly is None else all_weekly
    all_weekly_album = weekly_album if all_weekly_album is None else all_weekly_album
    all_weekly_artist = weekly_artist if all_weekly_artist is None else all_weekly_artist

    years = available_years_from_weekly(weekly, weekly_album, weekly_artist)
    selected_year = year if year is not None else (years[-1] if years else None)
    if selected_year is None:
        return _empty_response(
            top_n=top_n,
            album_top_n=album_top_n,
            artist_top_n=artist_top_n,
            weekly_top_n=weekly_top_n,
            weekly_album_top_n=weekly_album_top_n,
            weekly_artist_top_n=weekly_artist_top_n,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
        )
    if selected_year not in years:
        raise ValueError(f"Year {selected_year} is outside available Billboard years: {years}")

    full_weekly = _ensure_datetime(_ensure_artist_names(weekly))
    full_weekly_album = _ensure_datetime(weekly_album)
    full_weekly_artist = _ensure_datetime(weekly_artist)
    annual_weekly = _annual_window(full_weekly, selected_year)
    annual_weekly_album = _annual_window(full_weekly_album, selected_year)
    annual_weekly_artist = _annual_window(full_weekly_artist, selected_year)
    annual_all_weekly = _annual_window(_ensure_datetime(all_weekly), selected_year)
    annual_all_weekly_album = _annual_window(_ensure_datetime(all_weekly_album), selected_year)
    annual_all_weekly_artist = _annual_window(_ensure_datetime(all_weekly_artist), selected_year)
    annual_coverage_source = (
        _annual_window(_ensure_datetime(coverage_source), selected_year)
        if coverage_source is not None
        else None
    )

    tracks = _track_rows(
        full_weekly,
        annual_weekly,
        annual_all_weekly,
        selected_year,
    )[:top_n]
    albums = _album_or_artist_rows(
        full_weekly_album,
        annual_weekly_album,
        annual_all_weekly_album,
        selected_year,
        ["album_name", "artist_name"],
    )[:album_top_n]
    artists = _album_or_artist_rows(
        full_weekly_artist,
        annual_weekly_artist,
        annual_all_weekly_artist,
        selected_year,
        ["artist_name"],
    )[:artist_top_n]
    coverage = _coverage_meta(
        selected_year,
        week_start_dow,
        annual_weekly,
        annual_weekly_album,
        annual_weekly_artist,
        coverage_source=annual_coverage_source,
    )

    return {
        "meta": {
            "year": selected_year,
            "available_years": years,
            "total_weeks": _all_week_count(
                annual_weekly,
                annual_weekly_album,
                annual_weekly_artist,
            ),
            "top_n": top_n,
            "album_top_n": album_top_n,
            "artist_top_n": artist_top_n,
            "year_end_top_n": top_n,
            "year_end_album_top_n": album_top_n,
            "year_end_artist_top_n": artist_top_n,
            "weekly_top_n": weekly_top_n,
            "weekly_album_top_n": weekly_album_top_n,
            "weekly_artist_top_n": weekly_artist_top_n,
            "week_start_dow": week_start_dow,
            "week_start_hour": week_start_hour,
            "score_label": "Year-End Score",
            "semantics_version": YEAR_END_SEMANTICS_VERSION,
            **coverage,
        },
        "tracks": tracks,
        "albums": albums,
        "artists": artists,
        "honors": build_honors(tracks, albums, artists),
    }

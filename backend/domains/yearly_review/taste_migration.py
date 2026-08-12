"""Coverage-gated style, scene, language, and release-era migration."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote

import pandas as pd

from backend.domains.metadata.artist_genres import resolve_artist_genres_map
from backend.domains.metadata.artist_languages import (
    build_primary_artist_ms,
    resolve_artist_languages_map,
)
from backend.domains.metadata.genre_display_taxonomy import display_scene_keys, display_style_keys
from backend.domains.yearly_review.policies import TASTE_CHANGE_MIN_PCT
from backend.models.yearly_review import (
    YearlyEntityRef,
    YearlyHeadline,
    YearlyMetric,
    YearlyReviewCoverage,
    YearlyTasteAxisCoverage,
    YearlyTasteComparison,
    YearlyTasteMigrationChapter,
)
from backend.services.play_service import _track_cover_urls
from backend.services.wrapped_service import _fetch_track_release_years

AXIS_SOURCE_KEYS = {
    "style": "primary_styles",
    "scene": "regional_pop",
    "language": "language_dist",
    "release_era": "release_era",
}
SLICE_PERIODS: dict[str, tuple[str, tuple[int, ...]]] = {
    "q1": ("第一季度", (1, 2, 3)),
    "q2": ("第二季度", (4, 5, 6)),
    "q3": ("第三季度", (7, 8, 9)),
    "q4": ("第四季度", (10, 11, 12)),
    "first_half": ("上半年", (1, 2, 3, 4, 5, 6)),
    "second_half": ("下半年", (7, 8, 9, 10, 11, 12)),
}


def resolve_taste_comparison(
    stats: Mapping[str, Any], coverage: YearlyReviewCoverage
) -> YearlyTasteComparison:
    observed_start = coverage.play.observed_start
    year = int(stats.get("year") or (observed_start[:4] if observed_start else 2000))
    if coverage.status == "complete":
        from_key, to_key, mode = "first_half", "second_half", "half_years"
    elif coverage.status == "year_to_date" and coverage.play.observed_end:
        observed_end = pd.Timestamp(coverage.play.observed_end).date()
        completed = [
            quarter
            for quarter in range(1, 5)
            if (pd.Timestamp(year=year, month=quarter * 3, day=1) + pd.offsets.MonthEnd(0)).date()
            <= observed_end
        ]
        if len(completed) < 2:
            return YearlyTasteComparison()
        from_key, to_key, mode = f"q{completed[-2]}", f"q{completed[-1]}", "completed_quarters"
    else:
        return YearlyTasteComparison()

    from_label, from_months = SLICE_PERIODS[from_key]
    to_label, to_months = SLICE_PERIODS[to_key]

    def month_end(month: int) -> str:
        return (
            (pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0))
            .date()
            .isoformat()
        )

    return YearlyTasteComparison(
        mode=mode,
        status="available",
        from_slice_key=from_key,
        to_slice_key=to_key,
        from_label=from_label,
        to_label=to_label,
        from_start=f"{year}-{from_months[0]:02d}-01",
        from_end=month_end(from_months[-1]),
        to_start=f"{year}-{to_months[0]:02d}-01",
        to_end=month_end(to_months[-1]),
    )


def taste_comparison_frames(
    frame: pd.DataFrame, comparison: YearlyTasteComparison
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if (
        comparison.status != "available"
        or not comparison.from_slice_key
        or not comparison.to_slice_key
    ):
        empty = frame.iloc[0:0].copy()
        return empty, empty
    months = (
        pd.to_numeric(frame["ts_month"], errors="coerce")
        if "ts_month" in frame.columns
        else pd.to_datetime(frame["ts_date"], errors="coerce").dt.month
    )
    return (
        frame[months.isin(SLICE_PERIODS[comparison.from_slice_key][1])].copy(),
        frame[months.isin(SLICE_PERIODS[comparison.to_slice_key][1])].copy(),
    )


def _artist_hours(conn: sqlite3.Connection, frame: pd.DataFrame) -> dict[int, float]:
    if frame.empty or not {"track_id", "ms_played"}.issubset(frame.columns):
        return {}
    artist_ms, _ = build_primary_artist_ms(conn, frame.loc[:, ["track_id", "ms_played"]])
    return {artist_id: value / 3_600_000 for artist_id, value in artist_ms.items()}


def build_taste_drivers(
    conn: sqlite3.Connection,
    first_half: pd.DataFrame,
    second_half: pd.DataFrame,
    *,
    top_n: int = 3,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Attribute half-year share changes through governed artist facts only."""
    early = _artist_hours(conn, first_half)
    late = _artist_hours(conn, second_half)
    artist_ids = sorted(set(early) | set(late))
    names: dict[int, str] = {}
    artist_covers: dict[int, str] = {}
    for offset in range(0, len(artist_ids), 500):
        chunk = artist_ids[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        try:
            rows = conn.execute(
                f"SELECT artist_id, artist_name, image_path, image_url FROM artists WHERE artist_id IN ({placeholders})",
                chunk,
            ).fetchall()
        except sqlite3.Error:
            rows = conn.execute(
                f"SELECT artist_id, artist_name FROM artists WHERE artist_id IN ({placeholders})",
                chunk,
            ).fetchall()
        names.update({int(row[0]): str(row[1]) for row in rows})
        artist_covers.update(
            {
                int(row[0]): f"/covers/artists/{int(row[0])}.jpg"
                for row in rows
                if len(row) > 3 and (row[2] or row[3])
            }
        )
    genre_facts = resolve_artist_genres_map(conn, list(names.values())) if names else {}
    language_facts = resolve_artist_languages_map(conn, artist_ids) if artist_ids else {}
    early_total = sum(early.values()) or 1.0
    late_total = sum(late.values()) or 1.0
    contributions: dict[str, dict[str, list[dict[str, Any]]]] = {
        "style": defaultdict(list),
        "scene": defaultdict(list),
        "language": defaultdict(list),
        "release_era": defaultdict(list),
    }
    for artist_id in artist_ids:
        name = names.get(artist_id)
        if not name:
            continue
        delta = (
            late.get(artist_id, 0) / late_total * 100 - early.get(artist_id, 0) / early_total * 100
        )
        genre = genre_facts.get(name)
        style_keys = display_style_keys(genre)
        scene_keys = display_scene_keys(genre)
        language = language_facts.get(artist_id)
        if language is None or language.classification == "unknown":
            language_key = "unknown"
        elif language.classification == "single_language":
            language_key = str(language.primary_language_code or "unknown")
        else:
            language_key = language.classification
        axes = {"style": style_keys, "scene": scene_keys, "language": [language_key]}
        for axis, keys in axes.items():
            for key in keys:
                contribution = delta / max(len(keys), 1)
                contributions[axis][key].append(
                    {
                        "entity_type": "artist",
                        "entity_id": artist_id,
                        "name": name,
                        "cover_url": artist_covers.get(artist_id),
                        "delta_share_pct": round(contribution, 3),
                        "deep_link": f"/music/artists/{quote(name, safe='')}",
                    }
                )
    if {"track_name", "artist_name", "track_id", "ms_played"}.issubset(first_half.columns) and {
        "track_name",
        "artist_name",
        "track_id",
        "ms_played",
    }.issubset(second_half.columns):
        combined = pd.concat([first_half, second_half], ignore_index=True)
        try:
            track_covers = _track_cover_urls(conn, combined["track_id"])
        except sqlite3.Error:
            track_covers = {}
        pairs = [
            (str(track), str(artist))
            for track, artist in combined[["track_name", "artist_name"]]
            .dropna()
            .drop_duplicates()
            .itertuples(index=False, name=None)
        ]
        try:
            release_years = _fetch_track_release_years(conn, pairs)
        except Exception:
            release_years = {}
        early_track = (
            first_half.groupby(["track_id", "track_name", "artist_name"])["ms_played"]
            .sum()
            .to_dict()
        )
        late_track = (
            second_half.groupby(["track_id", "track_name", "artist_name"])["ms_played"]
            .sum()
            .to_dict()
        )
        early_ms_total = sum(early_track.values()) or 1
        late_ms_total = sum(late_track.values()) or 1
        for track_key in set(early_track) | set(late_track):
            track_id, track_name, artist_name = track_key
            release_year = release_years.get((str(track_name), str(artist_name)))
            if release_year is None or release_year < 1900:
                continue
            delta = (
                late_track.get(track_key, 0) / late_ms_total * 100
                - early_track.get(track_key, 0) / early_ms_total * 100
            )
            contributions["release_era"][f"{release_year // 10 * 10}s"].append(
                {
                    "entity_type": "track",
                    "entity_id": int(track_id),
                    "track_id": int(track_id),
                    "name": str(track_name),
                    "artist_name": str(artist_name),
                    "cover_url": track_covers.get(int(track_id)),
                    "delta_share_pct": round(delta, 3),
                    "deep_link": f"/music/tracks/{int(track_id)}",
                }
            )
    result: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for axis, buckets in contributions.items():
        result[axis] = {}
        for key, rows in buckets.items():
            rows.sort(key=lambda row: (-abs(float(row["delta_share_pct"])), str(row["name"])))
            total = sum(abs(float(row["delta_share_pct"])) for row in rows) or 1.0
            result[axis][key] = [
                {
                    **row,
                    "driver_share_pct": round(abs(float(row["delta_share_pct"])) / total * 100, 1),
                }
                for row in rows[:top_n]
            ]
    return result


def _buckets(profile: Mapping[str, Any] | None, axis: str) -> list[dict[str, Any]]:
    if not profile:
        return []
    source = profile.get(AXIS_SOURCE_KEYS[axis], {})
    if isinstance(source, Mapping):
        rows = source.get("buckets", [])
    else:
        rows = source
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _shares(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    return {str(row.get("key") or row.get("label")): float(row.get("share_pct", 0)) for row in rows}


def _labels(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {
        str(row.get("key") or row.get("label")): str(row.get("label") or row.get("key"))
        for row in rows
    }


def _slice_profile(stats: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    return next(
        (
            row.get("taste_profile")
            for row in stats.get("taste_slices", [])
            if row.get("slice_key") == key
        ),
        None,
    )


def _slice_release_era(stats: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    return next(
        (
            row.get("release_era")
            for row in stats.get("taste_slices", [])
            if row.get("slice_key") == key
        ),
        None,
    )


def _axis_coverage(coverage: YearlyReviewCoverage, axis: str) -> YearlyTasteAxisCoverage:
    return getattr(coverage.taste, axis)


def _driver_ref(driver: Mapping[str, Any]) -> YearlyEntityRef | None:
    entity_type = str(driver.get("entity_type") or "artist")
    name = driver.get("name") or driver.get("artist_name") or driver.get("track_name")
    if entity_type not in {"track", "album", "artist"} or not name:
        return None
    return YearlyEntityRef(
        entity_type=entity_type,
        entity_id=driver.get("entity_id")
        or driver.get("track_id")
        or driver.get("album_project_id"),
        name=str(name),
        artist_name=driver.get("artist_name") if entity_type != "artist" else None,
        cover_url=driver.get("cover_url"),
        deep_link=driver.get("deep_link"),
    )


def build_taste_migration(
    stats: Mapping[str, Any],
    coverage: YearlyReviewCoverage,
    *,
    drivers: Mapping[str, Mapping[str, Sequence[Mapping[str, Any]]]] | None = None,
    release_era_profiles: Mapping[str, Mapping[str, Any]] | None = None,
    comparison: YearlyTasteComparison | None = None,
) -> YearlyTasteMigrationChapter:
    annual_profile = dict(stats.get("taste_profile", {}))
    comparison = comparison or resolve_taste_comparison(stats, coverage)
    early_profile = _slice_profile(stats, comparison.from_slice_key or "") or {}
    late_profile = _slice_profile(stats, comparison.to_slice_key or "") or {}
    release_era_profiles = release_era_profiles or {}

    distributions: dict[str, list[dict[str, Any]]] = {}
    changes: dict[str, list[dict[str, Any]]] = {}
    coverage_notes: dict[str, str] = {}
    observations: list[YearlyHeadline] = []

    for axis in ("style", "scene", "language", "release_era"):
        axis_coverage = _axis_coverage(coverage, axis)
        if axis == "release_era":
            annual_source = release_era_profiles.get("annual") or {
                "release_era": stats.get("release_era_profile", {})
            }
            early_source = release_era_profiles.get(comparison.from_slice_key or "") or {
                "release_era": _slice_release_era(stats, comparison.from_slice_key or "") or {}
            }
            late_source = release_era_profiles.get(comparison.to_slice_key or "") or {
                "release_era": _slice_release_era(stats, comparison.to_slice_key or "") or {}
            }
            annual_rows = _buckets(annual_source, axis)
            early_rows = _buckets(early_source, axis)
            late_rows = _buckets(late_source, axis)
        else:
            annual_rows = _buckets(annual_profile, axis)
            early_rows = _buckets(early_profile, axis)
            late_rows = _buckets(late_profile, axis)
        distributions[axis] = annual_rows
        early = _shares(early_rows)
        late = _shares(late_rows)
        labels = {**_labels(early_rows), **_labels(late_rows)}
        axis_changes: list[dict[str, float | str]] = [
            {
                "key": key,
                "label": labels.get(key, key),
                "from_pct": round(early.get(key, 0), 1),
                "to_pct": round(late.get(key, 0), 1),
                "delta_pct": round(late.get(key, 0) - early.get(key, 0), 1),
            }
            for key in sorted(set(early) | set(late))
            if key != "unknown"
        ]
        axis_changes.sort(key=lambda row: (-abs(float(row["delta_pct"])), str(row["key"])))
        changes[axis] = axis_changes
        coverage_notes[axis] = (
            "数据充分"
            if axis_coverage.level == "core"
            else "样本有限"
            if axis_coverage.level == "secondary"
            else "暂无法判断"
        )
        if (
            comparison.status != "available"
            or not axis_coverage.conclusion_allowed
            or not axis_changes
        ):
            continue
        strongest = next(
            (row for row in axis_changes if (drivers or {}).get(axis, {}).get(str(row["key"]), [])),
            axis_changes[0],
        )
        if abs(float(strongest["delta_pct"])) < TASTE_CHANGE_MIN_PCT:
            continue
        delta_pct = float(strongest["delta_pct"])
        bucket_drivers = [
            driver
            for driver in (drivers or {}).get(axis, {}).get(str(strongest["key"]), [])
            if float(driver.get("delta_share_pct", delta_pct)) * delta_pct > 0
        ]
        if not bucket_drivers:
            continue
        top_driver = bucket_drivers[0]
        ref = _driver_ref(top_driver)
        if ref is None:
            continue
        from_pct = float(strongest["from_pct"])
        to_pct = float(strongest["to_pct"])
        direction = "上升" if delta_pct > 0 else "下降"
        observations.append(
            YearlyHeadline(
                headline_id=f"taste_migration_{axis}",
                title={
                    "style": "今年的曲风变化",
                    "scene": "今年听歌地域的变化",
                    "language": "今年常听语言的变化",
                    "release_era": "发行年代变化",
                }[axis],
                statement=(
                    f"{strongest['label']} 从{comparison.from_label}的 {from_pct:.1f}% 变为"
                    f"{comparison.to_label}的 {to_pct:.1f}%，{direction} {abs(delta_pct):.1f} 个百分点。"
                    f"这一变化最明显地体现在 {ref.name} 身上。"
                ),
                evidence_grade="C",
                primary_metric=YearlyMetric(
                    key="share_delta_pct",
                    label="份额变化",
                    value=delta_pct,
                    unit="个百分点",
                ),
                entity_refs=[ref],
                source_refs=[
                    f"stats.taste_slices.{comparison.from_slice_key}.{axis}",
                    f"stats.taste_slices.{comparison.to_slice_key}.{axis}",
                    f"taste_drivers.{axis}.{strongest['key']}",
                ],
            )
        )
    return YearlyTasteMigrationChapter(
        comparison=comparison,
        observations=observations,
        distributions=distributions,
        changes=changes,
        coverage_notes=coverage_notes,
    )

"""Release Cycle API — endpoints for the 发行周期分析 (Tab 12)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.core.json_helpers import df_to_json, py_val
from backend.dependencies import BillboardFilters, MergeConfig
from backend.services.billboard_service import (
    compute_album_weekly_rankings,
    compute_artist_weekly_rankings,
    compute_weekly_rankings,
    load_billboard_raw,
    load_billboard_raw_for_artists,
)
from backend.services.release_cycle_service import (
    _resolve_album_group,
    compute_artist_play_timeline,
    compute_artist_summary,
    compute_release_cycle,
    compute_release_metrics,
    detect_catalog_reentries,
    fill_summary_from_cycles,
    format_artist_impact,
    format_market_impact,
    get_advance_singles,
    get_bonus_tracks,
    get_chart_ranks_for_tracks,
    get_single_track_ids,
    load_artist_list,
    load_artist_releases,
)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════


def _filter_billboard_years(df: pd.DataFrame, filters: BillboardFilters) -> pd.DataFrame:
    if df.empty or (filters.year_start is None and filters.year_end is None):
        return df
    out = df.copy()
    years = pd.to_datetime(out["billboard_week"]).dt.year
    mask = pd.Series(True, index=out.index)
    if filters.year_start is not None:
        mask = mask & (years >= filters.year_start)
    if filters.year_end is not None:
        mask = mask & (years <= filters.year_end)
    return out.loc[mask]


def _get_weekly_data(
    filters: BillboardFilters,
    merge_level: int = 2,
    include_compilations: bool = False,
):
    """Load raw data and compute all weekly rankings (cached upstream)."""
    df_raw = load_billboard_raw(
        filters.min_ms,
        filters.music_only,
        filters.bb_week_start_dow,
        filters.bb_week_start_hour,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
    df_raw = _filter_billboard_years(df_raw, filters)

    df_artists = load_billboard_raw_for_artists(
        filters.min_ms,
        filters.music_only,
        filters.bb_week_start_dow,
        filters.bb_week_start_hour,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
    df_artists = _filter_billboard_years(df_artists, filters)

    weekly = compute_weekly_rankings(df_raw, filters.bb_top_n, merge_level=merge_level)
    weekly_artist = compute_artist_weekly_rankings(df_artists, filters.bb_artist_top_n)
    weekly_album = compute_album_weekly_rankings(
        df_raw,
        filters.bb_album_top_n,
        merge_level=merge_level,
        include_compilations=include_compilations,
    )

    return df_raw, weekly, weekly_artist, weekly_album


def _precompute_artist_context(df_raw, artist_name):
    """Precompute shared data for all releases of an artist."""
    artist_df = df_raw[df_raw["artist_name"] == artist_name]

    artist_median = None
    if not artist_df.empty:
        dow = artist_df["ts_date_dt"].dt.dayofweek
        week_start = artist_df["ts_date_dt"] - pd.to_timedelta(dow, unit="D")
        agg = artist_df.groupby(week_start).agg(play_count=("ms_played", "count"))
        if not agg.empty:
            artist_median = float(agg["play_count"].median())

    total_daily = df_raw.groupby("ts_date_dt")["ms_played"].count()
    total_daily.name = "play_count"

    return artist_df, artist_median, total_daily


def _album_cover_url(album_id):
    """Build the local cover endpoint for an album row."""
    album_id = py_val(album_id)
    if album_id is None:
        return None
    try:
        album_id_int = int(album_id)
    except (TypeError, ValueError):
        return None

    from backend.core.db import get_db

    conn = get_db()
    row = conn.execute(
        """SELECT 1
           FROM (
               SELECT 1 AS hit, 0 AS priority
               FROM albums
               WHERE album_id = ?
                 AND (
                     image_path IS NOT NULL AND image_path != ''
                     OR image_url IS NOT NULL AND image_url != ''
                 )

               UNION ALL

               SELECT 1 AS hit, 1 AS priority
               FROM albums al
               JOIN track_albums ta ON ta.album_id = al.album_id
               JOIN tracks t ON t.track_id = ta.track_id
               JOIN spotify_track_meta stm
                 ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
               JOIN spotify_album_meta sam
                 ON sam.spotify_album_id = stm.spotify_album_id
               WHERE al.album_id = ?
                 AND sam.image_url IS NOT NULL
                 AND sam.image_url != ''
           )
           ORDER BY priority
           LIMIT 1""",
        [album_id_int, album_id_int],
    ).fetchone()
    conn.close()
    if not row:
        return None
    return f"/covers/albums/{album_id_int}.jpg"


def _find_release_row(releases: pd.DataFrame, album_name: str):
    """Find a release by canonical album name or merged sub-album name."""
    rel_row = releases[releases["album_name"] == album_name]
    if not rel_row.empty:
        return rel_row.iloc[0], album_name, rel_row.iloc[0]["release_date"]

    for _, row in releases.iterrows():
        raw_subs = row.get("sub_albums")
        if pd.isna(raw_subs) or not raw_subs:
            continue
        try:
            sub_albums = json.loads(raw_subs)
        except (TypeError, json.JSONDecodeError):
            continue
        for sub in sub_albums:
            if sub.get("album_name") == album_name:
                release_date = pd.to_datetime(sub.get("release_date"), errors="coerce")
                if pd.isna(release_date):
                    release_date = row["release_date"]
                return row, row["album_name"], release_date

    return None, album_name, None


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints — album detail MUST be registered before artist overview
# because both use :path params; the more specific route wins first.
# ═══════════════════════════════════════════════════════════════════════════


class ArtistListItem(BaseModel):
    artist_name: str
    track_count: int


class ReleaseCycleAlbumDetailResponse(BaseModel):
    model_config = {"extra": "allow"}
    album_name: str | None = None
    artist_name: str | None = None
    error: str | None = None
    album_type: str | None = None
    release_date: str | None = None
    release_date_iso: str | None = None
    canonical_name: str | None = None
    primary_name: str | None = None
    group_albums: list[str] | None = None
    is_grouped: bool | None = None
    advance_singles: list[dict] | None = None
    metrics: dict | None = None
    artist_timeline: list[dict] | None = None
    album_timeline: list[dict] | None = None
    track_timelines: list[dict] | None = None
    artist_ranks: list[dict] | None = None
    album_ranks: list[dict] | None = None
    total_timeline: list[dict] | None = None
    artist_all_time_median: float | None = None
    clean_baseline_start: float | None = None
    advance_single_ranks: list[dict] | None = None
    best_track_ranks: dict | None = None
    catalog_reentries: list[dict] | None = None
    bonus_tracks: list[dict] | None = None
    track_matrix: dict | None = None


class ReleaseCycleArtistOverviewResponse(BaseModel):
    model_config = {"extra": "allow"}
    artist_name: str | None = None
    summary: dict | None = None
    releases: list[dict] | None = None
    rank_trend: list[dict] | None = None
    release_events: list[dict] | None = None
    first_play_week: str | None = None
    last_play_week: str | None = None
    cycles: list[dict] | None = None


@router.get("/artist-list", response_model=list[ArtistListItem])
def get_artist_list(filters: BillboardFilters = Depends()):
    """Sorted list of artists with track counts from current filter."""
    df_raw = load_billboard_raw_for_artists(
        filters.min_ms,
        filters.music_only,
        filters.bb_week_start_dow,
        filters.bb_week_start_hour,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
    df_raw = _filter_billboard_years(df_raw, filters)
    return load_artist_list(df_raw)


@router.get(
    "/artist/{artist_name:path}/album/{album_name:path}",
    response_model=ReleaseCycleAlbumDetailResponse,
)
def get_album_detail(
    artist_name: str,
    album_name: str,
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(default=False, description="专辑榜是否包含精选集"),
    weeks_before: int = Query(default=12, ge=1, le=52),
    weeks_after: int = Query(default=24, ge=4, le=104),
):
    """Album detail: cycle chart data, advance singles, track matrix, reentries, bonus tracks."""
    df_raw, weekly, weekly_artist, weekly_album = _get_weekly_data(
        filters,
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )

    releases = load_artist_releases(artist_name)
    album_releases = releases[releases["album_name"] == album_name]
    if album_releases.empty:
        return {"error": f"未找到专辑「{album_name}」的发行信息"}

    rel = album_releases.iloc[0]
    release_date = rel["release_date"]
    album_type = rel["album_type"]

    group_albums, canonical, primary_name = _resolve_album_group(artist_name, album_name)
    is_grouped = len(group_albums) > 1

    advance_singles = []
    if album_type == "album":
        advance_singles = get_advance_singles(artist_name, album_name)

    cycle = compute_release_cycle(
        df_raw,
        artist_name,
        album_name,
        release_date,
        weekly_artist=weekly_artist,
        weekly_album=weekly_album,
        weeks_before=weeks_before,
        weeks_after=weeks_after,
    )
    metrics = compute_release_metrics(cycle, album_type)

    advance_single_ranks = []
    advance_single_track_ids = set()
    if advance_singles:
        for s in advance_singles:
            track_ids = get_single_track_ids(artist_name, s["single_name"])
            advance_single_track_ids.update(track_ids)
            ranks = get_chart_ranks_for_tracks(
                weekly,
                artist_name,
                track_ids,
                release_date,
                weeks_before=weeks_before,
                weeks_after=weeks_after,
            )
            if not ranks.empty:
                advance_single_ranks.append(
                    {
                        "name": s["single_name"],
                        "release_date": py_val(s.get("release_date")),
                        "ranks": df_to_json(ranks),
                    }
                )

    best_track_ranks = None
    track_tl = cycle.get("track_timelines", pd.DataFrame())
    if not track_tl.empty and weekly is not None:
        track_totals = (
            track_tl.groupby(["track_id", "track_name"])["play_count"]
            .sum()
            .reset_index()
            .sort_values("play_count", ascending=False)
        )
        for _, tr in track_totals.iterrows():
            if tr["track_id"] not in advance_single_track_ids:
                ranks = get_chart_ranks_for_tracks(
                    weekly,
                    artist_name,
                    [tr["track_id"]],
                    release_date,
                    weeks_before=weeks_before,
                    weeks_after=weeks_after,
                )
                if not ranks.empty:
                    best_track_ranks = {"name": tr["track_name"], "ranks": df_to_json(ranks)}
                break

    catalog = detect_catalog_reentries(df_raw, artist_name, release_date, album_name)

    bonus_tracks = []
    if is_grouped:
        bonus_tracks = get_bonus_tracks(df_raw, artist_name, group_albums, primary_name)

    track_matrix = None
    if not track_tl.empty:
        top_tracks = (
            track_tl.groupby("track_name")["play_count"]
            .sum()
            .sort_values(ascending=False)
            .head(20)
            .index.tolist()
        )
        matrix_data = track_tl[track_tl["track_name"].isin(top_tracks)]
        if not matrix_data.empty:
            pivot = matrix_data.pivot_table(
                index="track_name",
                columns="week_offset",
                values="play_count",
                fill_value=0,
            )
            if not pivot.empty and not pivot.columns.empty:
                track_first_week = (pivot > 0).idxmax(axis=1)
                pivot = pivot.loc[track_first_week.sort_values().index]
                track_matrix = {
                    "tracks": list(pivot.index),
                    "weeks": [int(c) for c in pivot.columns],
                    "data": [[int(v) for v in row] for row in pivot.values],
                }

    metrics_out = dict(metrics)
    metrics_out["artist_impact_fmt"] = format_artist_impact(metrics["artist_impact"])
    metrics_out["market_impact_fmt"] = format_market_impact(metrics["market_impact"])

    return {
        "album_name": album_name,
        "artist_name": artist_name,
        "album_type": album_type,
        "release_date": release_date.isoformat()
        if hasattr(release_date, "isoformat")
        else str(release_date),
        "canonical_name": canonical,
        "primary_name": primary_name,
        "group_albums": group_albums,
        "is_grouped": is_grouped,
        "advance_singles": advance_singles,
        "metrics": metrics_out,
        "artist_timeline": df_to_json(cycle.get("artist_timeline")),
        "album_timeline": df_to_json(cycle.get("album_timeline")),
        "track_timelines": df_to_json(cycle.get("track_timelines")),
        "artist_ranks": df_to_json(cycle.get("artist_ranks")),
        "album_ranks": df_to_json(cycle.get("album_ranks")),
        "total_timeline": df_to_json(cycle.get("total_timeline")),
        "artist_all_time_median": py_val(cycle.get("artist_all_time_median")),
        "clean_baseline_start": py_val(cycle.get("clean_baseline_start")),
        "advance_single_ranks": advance_single_ranks,
        "best_track_ranks": best_track_ranks,
        "catalog_reentries": catalog,
        "bonus_tracks": bonus_tracks,
        "track_matrix": track_matrix,
        "release_date_iso": release_date.isoformat()
        if hasattr(release_date, "isoformat")
        else str(release_date),
    }


@router.get("/artist/{artist_name:path}", response_model=ReleaseCycleArtistOverviewResponse)
def get_artist_overview(
    artist_name: str,
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(default=False, description="专辑榜是否包含精选集"),
    weeks_before: int = Query(default=4, ge=1, le=24),
    weeks_after: int = Query(default=24, ge=4, le=52),
):
    """Full artist overview: KPIs, releases, cycles, metrics, rank trend data."""
    df_raw, weekly, weekly_artist, weekly_album = _get_weekly_data(
        filters,
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )

    releases = load_artist_releases(artist_name)
    if releases.empty:
        return {
            "artist_name": artist_name,
            "releases": [],
            "summary": None,
            "rank_trend": [],
            "release_events": [],
            "cycles": [],
        }

    artist_df, artist_median, total_daily = _precompute_artist_context(df_raw, artist_name)

    cycles_out = []
    all_cycles_map = {}
    for _, rel in releases.iterrows():
        cycle = compute_release_cycle(
            df_raw,
            artist_name,
            rel["album_name"],
            rel["release_date"],
            weekly_artist=weekly_artist,
            weekly_album=weekly_album,
            weeks_before=weeks_before,
            weeks_after=weeks_after,
            artist_df=artist_df,
            artist_median=artist_median,
            total_daily=total_daily,
        )
        all_cycles_map[rel["album_name"]] = cycle
        metrics = compute_release_metrics(cycle, rel["album_type"])
        cycles_out.append(
            {
                "album_name": rel["album_name"],
                "album_type": rel["album_type"],
                "release_date": rel["release_date"].isoformat()
                if hasattr(rel["release_date"], "isoformat")
                else str(rel["release_date"]),
                "db_album_id": py_val(rel.get("db_album_id")),
                "spotify_album_id": py_val(rel.get("spotify_album_id")),
                "canonical_name": py_val(rel.get("canonical_name")),
                "sub_albums": rel.get("sub_albums"),
                "cover_url": _album_cover_url(rel.get("db_album_id")),
                "metrics": metrics,
                "artist_timeline": df_to_json(cycle.get("artist_timeline")),
                "album_timeline": df_to_json(cycle.get("album_timeline")),
                "artist_ranks": df_to_json(cycle.get("artist_ranks")),
                "album_ranks": df_to_json(cycle.get("album_ranks")),
                "total_timeline": df_to_json(cycle.get("total_timeline")),
                "artist_all_time_median": py_val(cycle.get("artist_all_time_median")),
            }
        )

    summary = compute_artist_summary(artist_name, releases, weekly, weekly_artist, weekly_album)
    fill_summary_from_cycles(summary, artist_name, releases, all_cycles_map, df_raw)

    artist_timeline = compute_artist_play_timeline(df_raw, artist_name)
    artist_timeline["billboard_week"] = pd.to_datetime(artist_timeline["billboard_week"])
    if weekly_artist is not None and not weekly_artist.empty:
        art_ranks = weekly_artist[weekly_artist["artist_name"] == artist_name][
            ["billboard_week", "rank"]
        ].copy()
        art_ranks["billboard_week"] = pd.to_datetime(art_ranks["billboard_week"])
        artist_timeline = artist_timeline.merge(art_ranks, on="billboard_week", how="left")
    else:
        artist_timeline["rank"] = None

    rank_trend = df_to_json(artist_timeline, date_cols=["billboard_week"])

    if not artist_timeline.empty:
        first_play = artist_timeline["billboard_week"].min()
        release_events = []
        for _, rel in releases.iterrows():
            rd = rel["release_date"]
            if rd < first_play - pd.Timedelta(weeks=4):
                continue
            release_events.append(
                {
                    "album_name": rel["album_name"],
                    "album_type": rel["album_type"],
                    "release_date": rd.isoformat() if hasattr(rd, "isoformat") else str(rd),
                    "db_album_id": py_val(rel.get("db_album_id")),
                    "cover_url": _album_cover_url(rel.get("db_album_id")),
                }
            )
    else:
        release_events = []

    releases_out = df_to_json(releases, date_cols=["release_date"])
    for row in releases_out:
        row["cover_url"] = _album_cover_url(row.get("db_album_id"))

    summary["max_artist_impact_fmt"] = format_artist_impact(summary["max_artist_impact"])
    summary["max_market_impact_fmt"] = format_market_impact(summary["max_market_impact"])

    return {
        "artist_name": artist_name,
        "summary": summary,
        "releases": releases_out,
        "rank_trend": rank_trend,
        "release_events": release_events,
        "first_play_week": artist_timeline["billboard_week"].min().isoformat()
        if not artist_timeline.empty
        else None,
        "last_play_week": artist_timeline["billboard_week"].max().isoformat()
        if not artist_timeline.empty
        else None,
        "cycles": cycles_out,
    }


class CompareItem(BaseModel):
    artist_name: str
    album_name: str


class CompareRequest(BaseModel):
    items: list[CompareItem]
    weeks_before: int = 12
    weeks_after: int = 24


class CompareReleaseResult(BaseModel):
    artist_name: str
    album_name: str
    release_date: str
    label: str
    metrics: dict[str, Any]
    album_timeline: list[dict[str, Any]]
    album_ranks: list[dict[str, Any]]


class CompareReleasesResponse(BaseModel):
    error: str | None = None
    comparisons: list[CompareReleaseResult] = Field(default_factory=list)


@router.post("/compare", response_model=CompareReleasesResponse, response_model_exclude_unset=True)
def compare_releases(
    body: CompareRequest,
    filters: BillboardFilters = Depends(),
    merge_cfg: MergeConfig = Depends(),
    include_compilations: bool = Query(default=False, description="专辑榜是否包含精选集"),
):
    """Compare multiple releases: rank/play curves + metrics table."""
    if len(body.items) < 2:
        return {"error": "至少需要 2 张发行进行对比"}

    df_raw, weekly, weekly_artist, weekly_album = _get_weekly_data(
        filters,
        merge_level=merge_cfg.merge_level,
        include_compilations=include_compilations,
    )

    result = []
    for item in body.items:
        releases = load_artist_releases(item.artist_name)
        rel_row, cycle_album_name, release_date = _find_release_row(releases, item.album_name)
        if rel_row is None:
            continue

        cycle = compute_release_cycle(
            df_raw,
            item.artist_name,
            cycle_album_name,
            release_date,
            weekly_artist=weekly_artist,
            weekly_album=weekly_album,
            weeks_before=body.weeks_before,
            weeks_after=body.weeks_after,
        )
        metrics = compute_release_metrics(cycle, "album")

        result.append(
            {
                "artist_name": item.artist_name,
                "album_name": item.album_name,
                "release_date": release_date.isoformat()
                if hasattr(release_date, "isoformat")
                else str(release_date),
                "label": f"{item.album_name} ({release_date.strftime('%Y') if hasattr(release_date, 'strftime') else ''})",
                "metrics": {
                    **metrics,
                    "artist_impact_fmt": format_artist_impact(metrics["artist_impact"]),
                    "market_impact_fmt": format_market_impact(metrics["market_impact"]),
                },
                "album_timeline": df_to_json(cycle.get("album_timeline")),
                "album_ranks": df_to_json(cycle.get("album_ranks")),
            }
        )

    return {"comparisons": result}

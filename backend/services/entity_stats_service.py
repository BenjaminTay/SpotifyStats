"""Personal listening statistics for tracks, albums, and artists."""

from __future__ import annotations

import os
import sqlite3
from functools import lru_cache, partial
from typing import Any

import pandas as pd

from backend.core.cache import singleflight
from backend.core.db import (
    DB_PATH,
    get_db,
    get_track_artist_names_map,
    load_plays,
    load_plays_for_artists,
)
from backend.domains.music_search.revisions import get_music_search_revision_state
from backend.domains.playback.track_groups import resolve_track_aggregation_scope
from backend.services.analysis_stats_service import (
    PERIOD_LABELS,
    _cumulative_trend,
    _daily_metrics,
    _daily_trend,
    _hourly_distribution,
    _month_distribution,
    _summary,
    _weekday_distribution,
    _year_distribution,
    build_duration_frame,
    chart_rows,
    filter_period_events,
    load_period_plays,
    recent_plays,
    resolve_period,
)
from backend.services.play_service import (
    _album_cover_lookup,
    _artist_cover_lookup,
    _track_cover_urls,
)


def _entity_base(
    df: pd.DataFrame,
    entity_df: pd.DataFrame,
    resolved: dict,
    duration_frame: pd.DataFrame | None = None,
) -> dict:
    duration_frame = (
        duration_frame if duration_frame is not None else build_duration_frame(df, resolved)
    )
    summary = _summary(entity_df, duration_frame)
    daily = _daily_trend(entity_df, duration_frame)
    return {
        "summary": summary,
        "daily_metrics": _daily_metrics(summary),
        "hourly_distribution": _hourly_distribution(entity_df, duration_frame),
        "daily_trend": daily,
        "cumulative_trend": _cumulative_trend(daily),
        "weekday_distribution": _weekday_distribution(entity_df, duration_frame),
        "month_distribution": _month_distribution(entity_df, duration_frame),
        "year_distribution": _year_distribution(entity_df, duration_frame),
    }


def _scoped_play_loader(
    conn: sqlite3.Connection,
    track_ids: list[int],
    *,
    music_only: bool,
    ids_are_l1: bool = False,
):
    """Load target rows plus the preceding eligible row for exact merging.

    Logical-event reconstruction happens after SQL selection. Selecting only
    target tracks can therefore merge two target plays that were separated by
    another track in the real timeline. The one-row left context preserves the
    same run boundaries as the full-library loader without materialising the
    whole library.
    """

    if not track_ids:
        return partial(load_plays, extra_where="0")
    has_l1 = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_source_links'"
    ).fetchone()
    source_track_ids = track_ids
    if has_l1 and ids_are_l1:
        placeholders = ",".join("?" for _ in track_ids)
        source_track_ids = [
            int(row[0])
            for row in conn.execute(
                f"""SELECT DISTINCT track_id FROM track_l1_source_links
                     WHERE l1_id IN ({placeholders}) ORDER BY track_id""",
                track_ids,
            ).fetchall()
        ]
    if not source_track_ids:
        return partial(load_plays, extra_where="0")
    placeholders = ",".join("?" for _ in source_track_ids)
    eligible_where = "WHERE track_id IS NOT NULL" if music_only else ""
    selector = f"""p.play_id IN (
        WITH ordered AS (
            SELECT play_id, track_id,
                   LAG(play_id) OVER (ORDER BY ts, play_id) AS previous_play_id
            FROM plays {eligible_where}
        ), target AS (
            SELECT play_id, previous_play_id FROM ordered
            WHERE track_id IN ({placeholders})
        )
        SELECT play_id FROM target
        UNION
        SELECT previous_play_id FROM target WHERE previous_play_id IS NOT NULL
    )"""
    return partial(load_plays, extra_where=selector, extra_params=source_track_ids)


def _global_period_bounds(
    conn: sqlite3.Connection,
    *,
    period: str,
    start_date: str | None,
    end_date: str | None,
    music_only: bool,
) -> dict:
    if period == "custom":
        return {
            "period": "custom",
            "label": PERIOD_LABELS["custom"],
            "start_date": start_date,
            "end_date": end_date,
        }
    where = "WHERE track_id IS NOT NULL" if music_only else ""
    row = conn.execute(
        f"SELECT MIN(date(ts, 'localtime')), MAX(date(ts, 'localtime')) FROM plays {where}"
    ).fetchone()
    return {
        "period": "lifetime",
        "label": PERIOD_LABELS["lifetime"],
        "start_date": str(row[0]) if row and row[0] is not None else None,
        "end_date": str(row[1]) if row and row[1] is not None else None,
    }


def _rank_for(
    rows: list[dict],
    entity: str,
    *,
    track_id=None,
    album_name=None,
    album_names: list[str] | None = None,
    artist_name=None,
) -> int | None:
    for row in rows:
        if entity == "track" and row.get("track_id") == track_id:
            return row["rank"]
        if entity == "album":
            if album_names:
                if row.get("album_name") in album_names and row.get("artist_name") == artist_name:
                    return row["rank"]
            elif row.get("album_name") == album_name and row.get("artist_name") == artist_name:
                return row["rank"]
        if entity == "artist" and row.get("artist_name") == artist_name:
            return row["rank"]
    return None


def _ranks(
    conn: sqlite3.Connection,
    all_df: pd.DataFrame,
    current_df: pd.DataFrame,
    current_resolved: dict,
    entity: str,
    track_id=None,
    album_name=None,
    album_names: list[str] | None = None,
    artist_name=None,
    merge_level: int = 2,
) -> dict:
    periods = {
        "lifetime": resolve_period(all_df, "lifetime", None, None),
        "last_6_months": resolve_period(all_df, "last_6_months", None, None),
        "last_4_weeks": resolve_period(all_df, "last_4_weeks", None, None),
    }
    rows_by_scope: dict[tuple[str | None, str | None], list[dict]] = {}
    empty_duration = pd.DataFrame(columns=["ms_played", "ts_date"])

    def rows_for(resolved: dict, frame: pd.DataFrame | None = None) -> list[dict]:
        scope = (resolved.get("start_date"), resolved.get("end_date"))
        if scope not in rows_by_scope:
            scoped = frame if frame is not None else filter_period_events(all_df, resolved)
            _, rows_by_scope[scope] = chart_rows(
                conn,
                scoped,
                entity,
                "plays",
                None,
                0,
                merge_level=merge_level,
                duration_frame=empty_duration,
            )
        return rows_by_scope[scope]

    result = {}
    for key, resolved in periods.items():
        rows = rows_for(resolved)
        result[key] = _rank_for(
            rows,
            entity,
            track_id=track_id,
            album_name=album_name,
            album_names=album_names,
            artist_name=artist_name,
        )
    rows = rows_for(current_resolved, current_df)
    result["current_period"] = _rank_for(
        rows,
        entity,
        track_id=track_id,
        album_name=album_name,
        album_names=album_names,
        artist_name=artist_name,
    )
    return result


def _top250_count(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    *,
    album_name: str | None = None,
    album_names: list[str] | None = None,
    artist_name: str | None = None,
) -> int:
    # This helper only consumes play rank and entity identity.  Supplying an
    # explicit empty duration frame avoids an otherwise-unused full timeline
    # slice expansion while preserving the counted-event ordering.
    _, rows = chart_rows(
        conn,
        df,
        "track",
        "plays",
        250,
        0,
        duration_frame=pd.DataFrame(columns=["ms_played", "ts_date"]),
    )
    count = 0
    for row in rows:
        row_album = row.get("album_name")
        row_artist = row.get("artist_name")
        if album_names is not None:
            if row_album in album_names and row_artist == artist_name:
                count += 1
        elif album_name is not None:
            if row_album == album_name and row_artist == artist_name:
                count += 1
        elif row_artist == artist_name:
            count += 1
    return count


def _top250_counts(
    conn: sqlite3.Connection,
    all_df: pd.DataFrame,
    *,
    album_name=None,
    album_names: list[str] | None = None,
    artist_name=None,
) -> dict:
    return {
        "lifetime": _top250_count(
            conn, all_df, album_name=album_name, album_names=album_names, artist_name=artist_name
        ),
        "last_6_months": _top250_count(
            conn,
            filter_period_events(all_df, resolve_period(all_df, "last_6_months", None, None)),
            album_name=album_name,
            album_names=album_names,
            artist_name=artist_name,
        ),
        "last_4_weeks": _top250_count(
            conn,
            filter_period_events(all_df, resolve_period(all_df, "last_4_weeks", None, None)),
            album_name=album_name,
            album_names=album_names,
            artist_name=artist_name,
        ),
    }


def _build_track_stats(
    conn: sqlite3.Connection,
    track_id: int,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    merge_level: int = 2,
    include_rank_context: bool = True,
) -> dict:
    aggregation_scope = resolve_track_aggregation_scope(conn, track_id, merge_level)
    member_track_ids = list(aggregation_scope.member_track_ids)
    scoped = not include_rank_context and period in {"lifetime", "custom"}
    loader = (
        _scoped_play_loader(
            conn,
            member_track_ids,
            music_only=music_only,
            ids_are_l1=True,
        )
        if scoped
        else None
    )
    all_df, current_df, resolved = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        attach_duration_slices=False,
        _loader=loader,
    )
    if scoped:
        resolved = _global_period_bounds(
            conn,
            period=period,
            start_date=start_date,
            end_date=end_date,
            music_only=music_only,
        )
        current_df = filter_period_events(all_df, resolved)
    entity_all = all_df[all_df["track_id"].isin(member_track_ids)]
    entity_df = current_df[current_df["track_id"].isin(member_track_ids)]
    if entity_all.empty:
        return {"found": False}
    primary_track_id = aggregation_scope.primary_track_id
    info = conn.execute(
        """SELECT t.track_name, a.artist_name, al.album_name,
                  COALESCE(identity.representative_track_id, t.track_id)
                     AS representative_track_id
             FROM tracks t
             LEFT JOIN artists a ON a.artist_id=t.artist_id
             LEFT JOIN albums al ON al.album_id=t.album_id
             LEFT JOIN track_l1_identities identity ON identity.l1_id=t.track_id
            WHERE t.track_id=?""",
        (primary_track_id,),
    ).fetchone()
    if info is None:
        return {"found": False}
    representative_track_id = int(info["representative_track_id"])
    primary_artist = info["artist_name"]
    all_artists = get_track_artist_names_map()
    artist_names = all_artists.get(primary_track_id, [primary_artist])
    display_artist = ", ".join(artist_names) if len(artist_names) > 1 else primary_artist
    entity_duration = build_duration_frame(entity_all, resolved)
    data = _entity_base(all_df, entity_df, resolved, entity_duration)
    data.update(
        {
            "found": True,
            "period": resolved,
            "entity": {
                "track_id": primary_track_id,
                "l1_id": primary_track_id,
                "representative_track_id": representative_track_id,
                "track_name": info["track_name"],
                "artist_name": display_artist,
                "artist_names": artist_names,
                "album_name": info["album_name"],
                "cover_url": _track_cover_urls(conn, [primary_track_id]).get(primary_track_id),
            },
            "first_played": str(entity_all["ts"].min()),
            "last_played": str(entity_all["ts"].max()),
            "ranks": (
                _ranks(
                    conn,
                    all_df,
                    current_df,
                    resolved,
                    "track",
                    track_id=primary_track_id,
                    merge_level=merge_level,
                )
                if include_rank_context
                else None
            ),
            "recent_plays": recent_plays(conn, entity_df, 50) if include_rank_context else [],
        }
    )
    return data


def _resolve_album_project_id(
    conn: sqlite3.Connection, album_name: str, artist_name: str, merge_level: int
) -> int | None:
    preferred_scope = "composition" if merge_level >= 3 else "release"
    row = conn.execute(
        """SELECT ap.project_id
           FROM album_projects ap
           JOIN artists ar ON ar.artist_id = ap.artist_id
           WHERE ap.canonical_name = ? AND ar.artist_name = ?
           ORDER BY CASE WHEN ap.scope = ? THEN 0 ELSE 1 END, ap.project_id
           LIMIT 1""",
        (album_name, artist_name, preferred_scope),
    ).fetchone()
    return int(row["project_id"]) if row else None


def _resolve_album_project_song_keys(
    conn: sqlite3.Connection, album_name: str, artist_name: str, merge_level: int = 2
) -> set[str]:
    """Return canonical_song_keys belonging to the album project.

    Uses ``album_project_tracks`` membership so that plays from every source
    (standard, deluxe, single, compilation, …) contribute to the project-scoped
    statistics — matching the rule in domains/playback/album_projects.py.
    """
    from backend.domains.playback.album_projects import (
        apply_canonical_song_keys,
        ensure_album_projects,
    )

    ensure_album_projects(conn)

    project_id = _resolve_album_project_id(conn, album_name, artist_name, merge_level)
    if project_id is None:
        return set()

    rows = conn.execute(
        """SELECT DISTINCT COALESCE(links.l1_id, apt.track_id) AS track_id,
                  COALESCE(rep.track_name, t.track_name) AS track_name
           FROM album_project_tracks apt
           JOIN tracks t ON t.track_id = apt.track_id
           LEFT JOIN track_l1_source_links links ON links.track_id=apt.track_id
           LEFT JOIN track_l1_identities li ON li.l1_id=links.l1_id
           LEFT JOIN tracks rep ON rep.track_id=li.representative_track_id
           WHERE apt.project_id = ? AND apt.min_merge_level <= ?""",
        (project_id, merge_level),
    ).fetchall()
    if not rows:
        return set()

    mini_df = pd.DataFrame(
        [{"track_id": r["track_id"], "track_name": r["track_name"]} for r in rows]
    )
    keyed = apply_canonical_song_keys(mini_df, conn, merge_level)
    return set(keyed["canonical_song_key"].tolist())


def _resolve_album_project_track_ids(
    conn: sqlite3.Connection, album_name: str, artist_name: str, merge_level: int = 2
) -> list[int]:
    from backend.domains.playback.album_projects import ensure_album_projects

    ensure_album_projects(conn)
    project_id = _resolve_album_project_id(conn, album_name, artist_name, merge_level)
    if project_id is not None:
        rows = conn.execute(
            """SELECT DISTINCT track_id FROM album_project_tracks
               WHERE project_id=? AND min_merge_level<=? ORDER BY track_id""",
            (project_id, merge_level),
        ).fetchall()
        if rows:
            return [int(row[0]) for row in rows]
    rows = conn.execute(
        """SELECT t.track_id FROM tracks t
           JOIN albums al ON al.album_id=t.album_id
           JOIN artists ar ON ar.artist_id=al.artist_id
           WHERE al.album_name=? AND ar.artist_name=? ORDER BY t.track_id""",
        (album_name, artist_name),
    ).fetchall()
    return [int(row[0]) for row in rows]


def _resolve_album_project_album_names(
    conn: sqlite3.Connection, album_name: str, artist_name: str, merge_level: int = 2
) -> list[str]:
    """Return all source album names that contribute tracks to this album project.

    Used for ``chart_rows()`` ranking and Top-250 counting, where the chart is
    still grouped by raw album_name.  Matching against this expanded list means
    the ranking picks up plays from every source (standard, deluxe, single, …).
    """
    from backend.domains.playback.album_projects import ensure_album_projects

    ensure_album_projects(conn)

    project_id = _resolve_album_project_id(conn, album_name, artist_name, merge_level)
    if project_id is None:
        return [album_name]

    rows = conn.execute(
        """SELECT DISTINCT COALESCE(sa.album_name, al.album_name) AS album_name
           FROM album_project_tracks apt
           JOIN tracks t ON t.track_id = apt.track_id
           JOIN albums al ON al.album_id = t.album_id
           LEFT JOIN albums sa ON sa.album_id = apt.source_album_id
           WHERE apt.project_id = ? AND apt.min_merge_level <= ?""",
        (project_id, merge_level),
    ).fetchall()

    names = list({r["album_name"] for r in rows if r["album_name"]})
    if album_name not in names:
        names.append(album_name)
    return names


def _build_album_stats(
    conn: sqlite3.Connection,
    album_name: str,
    artist: str | None,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    merge_level: int = 2,
    include_rank_context: bool = True,
) -> dict:
    from backend.domains.playback.album_projects import apply_canonical_song_keys

    artist_name = artist
    if not artist_name:
        row = conn.execute(
            """SELECT ar.artist_name FROM albums al
               JOIN artists ar ON ar.artist_id=al.artist_id
               WHERE al.album_name=? ORDER BY al.album_id LIMIT 1""",
            (album_name,),
        ).fetchone()
        artist_name = str(row[0]) if row else None
    scoped = not include_rank_context and period in {"lifetime", "custom"}
    track_ids = (
        _resolve_album_project_track_ids(conn, album_name, artist_name, merge_level)
        if scoped and artist_name
        else []
    )
    loader = _scoped_play_loader(conn, track_ids, music_only=music_only) if scoped else None

    all_df, current_df, resolved = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        attach_duration_slices=False,
        _loader=loader,
    )
    if scoped:
        resolved = _global_period_bounds(
            conn,
            period=period,
            start_date=start_date,
            end_date=end_date,
            music_only=music_only,
        )
        current_df = filter_period_events(all_df, resolved)
    if not artist_name:
        matches = all_df[all_df["album_name"] == album_name]
        if not matches.empty:
            artist_name = str(matches.iloc[0]["artist_name"])

    # Resolve album project track membership — canonical_song_key attribution
    # replaces the old release_group album_name string matching.
    if artist_name:
        project_keys = _resolve_album_project_song_keys(conn, album_name, artist_name, merge_level)
    else:
        project_keys = set()

    if project_keys:
        all_df = apply_canonical_song_keys(all_df, conn, merge_level)
        current_df = apply_canonical_song_keys(current_df, conn, merge_level)
        entity_all = all_df[all_df["canonical_song_key"].isin(project_keys)]
        entity_df = current_df[current_df["canonical_song_key"].isin(project_keys)]
        # Expand album_names to all source albums in the project so that
        # ranking/top250 lookups match any contributing version.
        album_names = _resolve_album_project_album_names(conn, album_name, artist_name, merge_level)
    else:
        # Fallback: no album project found — filter by album_name string match
        # (preserves behaviour for albums that haven't been bootstrapped yet).
        album_names = [album_name]
        entity_all = all_df[
            (all_df["album_name"].isin(album_names)) & (all_df["artist_name"] == artist_name)
        ]
        entity_df = current_df[
            (current_df["album_name"].isin(album_names))
            & (current_df["artist_name"] == artist_name)
        ]
    if entity_all.empty:
        return {"found": False}
    entity_duration = build_duration_frame(entity_all, resolved)
    data = _entity_base(all_df, entity_df, resolved, entity_duration)
    # Keep the legacy summary payload bounded; the detail UI uses the dedicated
    # rankings endpoint for every page instead of downloading the full project.
    if include_rank_context:
        _, breakdown = chart_rows(
            conn,
            entity_df,
            "track",
            "plays",
            20,
            0,
            duration_frame=entity_duration,
        )
    else:
        breakdown = []
    data.update(
        {
            "found": True,
            "period": resolved,
            "entity": {
                "album_name": album_name,
                "artist_name": artist_name,
                "cover_url": _album_cover_lookup(conn).get((album_name, artist_name)),
            },
            "first_played": str(entity_all["ts"].min()),
            "last_played": str(entity_all["ts"].max()),
            "ranks": (
                _ranks(
                    conn,
                    all_df,
                    current_df,
                    resolved,
                    "album",
                    album_name=album_name,
                    album_names=album_names,
                    artist_name=artist_name,
                )
                if include_rank_context
                else None
            ),
            "top250_counts": (
                _top250_counts(
                    conn,
                    all_df,
                    album_name=album_name,
                    album_names=album_names,
                    artist_name=artist_name,
                )
                if include_rank_context
                else None
            ),
            "track_breakdown": breakdown,
            "recent_plays": recent_plays(conn, entity_df, 50) if include_rank_context else [],
        }
    )
    return data


def get_album_personal_ranking(
    conn: sqlite3.Connection,
    album_name: str,
    artist: str | None,
    metric: str,
    limit: int,
    offset: int,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    merge_level: int = 2,
) -> dict:
    """Return a stable server-paginated track ranking for one album project."""
    from backend.domains.playback.album_projects import apply_canonical_song_keys

    all_df, current_df, resolved = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        attach_duration_slices=False,
    )
    artist_name = artist
    if not artist_name:
        matches = all_df[all_df["album_name"] == album_name]
        if not matches.empty:
            artist_name = str(matches.iloc[0]["artist_name"])

    project_keys = (
        _resolve_album_project_song_keys(conn, album_name, artist_name, merge_level)
        if artist_name
        else set()
    )
    if project_keys:
        all_df = apply_canonical_song_keys(all_df, conn, merge_level)
        current_df = apply_canonical_song_keys(current_df, conn, merge_level)
        entity_all = all_df[all_df["canonical_song_key"].isin(project_keys)]
        entity_df = current_df[current_df["canonical_song_key"].isin(project_keys)]
    else:
        entity_all = all_df[
            (all_df["album_name"] == album_name) & (all_df["artist_name"] == artist_name)
        ]
        entity_df = current_df[
            (current_df["album_name"] == album_name) & (current_df["artist_name"] == artist_name)
        ]

    if entity_all.empty:
        return {
            "found": False,
            "entity": "track",
            "total": 0,
            "limit": limit,
            "offset": offset,
            "rows": [],
        }
    total, rows = chart_rows(
        conn,
        entity_df,
        "track",
        metric,
        limit,
        offset,
        duration_frame=build_duration_frame(entity_all, resolved),
    )
    return {
        "found": True,
        "album_name": album_name,
        "artist_name": artist_name,
        "period": resolved,
        "entity": "track",
        "metric": metric,
        "total": total,
        "limit": limit,
        "offset": offset,
        "rows": rows,
    }


def _filter_artist_owned_album_events(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    artist_name: str,
    *,
    merge_level: int = 2,
) -> pd.DataFrame:
    """Keep only events whose canonical album project belongs to the artist.

    Artist play frames are intentionally fanned out to every effective credited
    artist so collaborations remain in track rankings. Album rankings have a
    narrower ownership rule: a featured credit must not make the source album
    part of the featured artist's discography.
    """
    if df.empty:
        return df

    from backend.domains.playback.album_projects import (
        apply_canonical_song_keys,
        load_album_project_membership,
    )

    keyed = apply_canonical_song_keys(df, conn, merge_level)
    membership = load_album_project_membership(conn, merge_level=merge_level)
    if membership.empty:
        return keyed.iloc[0:0].copy()

    owned_song_keys = set(
        membership.loc[
            membership["artist_name"] == artist_name,
            "canonical_song_key",
        ].dropna()
    )
    if not owned_song_keys:
        return keyed.iloc[0:0].copy()
    return keyed[keyed["canonical_song_key"].isin(owned_song_keys)].copy()


def _build_artist_stats(
    conn: sqlite3.Connection,
    artist_name: str,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    include_rank_context: bool = True,
) -> dict:
    from backend.domains.metadata.artist_identity import resolve_artist_name

    identity = resolve_artist_name(conn, artist_name)
    if identity is not None:
        artist_name = identity.display_name
    scoped = not include_rank_context and period in {"lifetime", "custom"}
    if scoped:
        from backend.domains.metadata.track_credits import get_effective_track_credits

        track_ids = sorted(
            {
                int(row["track_id"])
                for row in get_effective_track_credits(conn)
                if str(row["artist_name"]) == artist_name
            }
        )
        loader = _scoped_play_loader(conn, track_ids, music_only=music_only)
    else:
        loader = load_plays_for_artists
    all_df, current_df, resolved = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        attach_duration_slices=False,
        _loader=loader,
    )
    if scoped:
        resolved = _global_period_bounds(
            conn,
            period=period,
            start_date=start_date,
            end_date=end_date,
            music_only=music_only,
        )
        current_df = filter_period_events(all_df, resolved)
        placeholders = ",".join("?" for _ in track_ids)
        target_ids = (
            {
                int(row[0])
                for row in conn.execute(
                    f"""SELECT DISTINCT l1_id FROM track_l1_source_links
                         WHERE track_id IN ({placeholders})""",
                    track_ids,
                ).fetchall()
            }
            if track_ids
            else set()
        )
        if not target_ids:
            target_ids = set(track_ids)
        all_df = all_df[all_df["track_id"].isin(target_ids)].copy()
        current_df = current_df[current_df["track_id"].isin(target_ids)].copy()
        all_df["artist_name"] = artist_name
        current_df["artist_name"] = artist_name
    entity_all = all_df[all_df["artist_name"] == artist_name]
    entity_df = current_df[current_df["artist_name"] == artist_name]
    if entity_all.empty:
        return {"found": False}
    entity_duration = build_duration_frame(entity_all, resolved)
    if include_rank_context:
        _, top_tracks = chart_rows(
            conn,
            entity_df,
            "track",
            "plays",
            20,
            0,
            duration_frame=entity_duration,
        )
        owned_album_all = _filter_artist_owned_album_events(conn, entity_all, artist_name)
        owned_album_df = _filter_artist_owned_album_events(conn, entity_df, artist_name)
        owned_album_duration = build_duration_frame(owned_album_all, resolved)
        _, top_albums = chart_rows(
            conn,
            owned_album_df,
            "album",
            "plays",
            20,
            0,
            duration_frame=owned_album_duration,
        )
    else:
        top_tracks, top_albums = [], []
    if include_rank_context and "_logical_event_id" in all_df.columns:
        recent_ids = (
            all_df.sort_values("ts", ascending=False)
            .drop_duplicates("_logical_event_id")
            .head(50)["_logical_event_id"]
        )
        recent_50_all = all_df[all_df["_logical_event_id"].isin(set(recent_ids))]
    elif include_rank_context:
        recent_50_all = all_df.sort_values("ts", ascending=False).head(50)
    else:
        recent_50_all = all_df.iloc[0:0]
    recent_50_artist_rows = recent_50_all[recent_50_all["artist_name"] == artist_name]
    if include_rank_context and "_logical_event_id" in recent_50_artist_rows.columns:
        recent_50_count: int | None = int(recent_50_artist_rows["_logical_event_id"].nunique())
    elif include_rank_context:
        recent_50_count = int(len(recent_50_artist_rows))
    else:
        recent_50_count = None
    data = _entity_base(all_df, entity_df, resolved, entity_duration)
    data.update(
        {
            "found": True,
            "period": resolved,
            "entity": {
                "artist_name": artist_name,
                "cover_url": _artist_cover_lookup(conn).get(artist_name),
            },
            "first_played": str(entity_all["ts"].min()),
            "last_played": str(entity_all["ts"].max()),
            "ranks": (
                _ranks(
                    conn,
                    all_df,
                    current_df,
                    resolved,
                    "artist",
                    artist_name=artist_name,
                )
                if include_rank_context
                else None
            ),
            "top250_counts": (
                _top250_counts(conn, all_df, artist_name=artist_name)
                if include_rank_context
                else None
            ),
            "recent_50_count": recent_50_count,
            "top_tracks": top_tracks,
            "top_albums": top_albums,
            "recent_plays": recent_plays(conn, entity_df, 50) if include_rank_context else [],
        }
    )
    return data


def get_artist_personal_ranking(
    conn: sqlite3.Connection,
    artist_name: str,
    entity: str,
    metric: str,
    limit: int,
    offset: int,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
) -> dict:
    """Return a stable server-paginated personal track/album ranking for an artist."""
    from backend.domains.metadata.artist_identity import resolve_artist_name

    identity = resolve_artist_name(conn, artist_name)
    if identity is not None:
        artist_name = identity.display_name
    all_df, current_df, resolved = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        attach_duration_slices=False,
        _loader=load_plays_for_artists,
    )
    if all_df[all_df["artist_name"] == artist_name].empty:
        return {
            "found": False,
            "entity": entity,
            "total": 0,
            "limit": limit,
            "offset": offset,
            "rows": [],
        }
    artist_all = all_df[all_df["artist_name"] == artist_name]
    artist_df = current_df[current_df["artist_name"] == artist_name]
    if entity == "album":
        artist_all = _filter_artist_owned_album_events(conn, artist_all, artist_name)
        artist_df = _filter_artist_owned_album_events(conn, artist_df, artist_name)
    total, rows = chart_rows(
        conn,
        artist_df,
        entity,
        metric,
        limit,
        offset,
        duration_frame=build_duration_frame(artist_all, resolved),
    )
    return {
        "found": True,
        "artist_name": artist_name,
        "period": resolved,
        "entity": entity,
        "metric": metric,
        "total": total,
        "limit": limit,
        "offset": offset,
        "rows": rows,
    }


def get_entity_plays(
    conn: sqlite3.Connection,
    entity: str,
    track_id: int | None = None,
    album_name: str | None = None,
    artist_name: str | None = None,
    min_ms: int = 30000,
    music_only: bool = True,
    merge_enabled: bool = True,
    merge_level: int = 2,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    search: str | None = None,
    date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return paginated play records for a specific entity using the shared rules pipeline."""
    loader = None
    if entity == "track" and track_id is not None and period in {"lifetime", "custom"}:
        scope = resolve_track_aggregation_scope(conn, track_id, merge_level)
        loader = _scoped_play_loader(
            conn,
            list(scope.member_track_ids),
            music_only=music_only,
            ids_are_l1=True,
        )
    _, df, _ = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        _loader=load_plays_for_artists if entity == "artist" else loader,
        attach_duration_slices=False,
    )
    df = _filter_entity_rows(
        df, entity, track_id, album_name, artist_name, conn=conn, merge_level=merge_level
    )

    if date is not None and not df.empty:
        df = df[df["ts_date"].astype(str) == date]

    if search is not None and not df.empty:
        search_lower = search.casefold()
        mask = (
            df["track_name"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .str.contains(search_lower, regex=False)
            | df["artist_name"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .str.contains(search_lower, regex=False)
            | df["album_name"]
            .fillna("")
            .astype(str)
            .str.casefold()
            .str.contains(search_lower, regex=False)
        )
        df = df[mask]

    df = df.sort_values("ts", ascending=False)
    total = int(len(df))
    page = df.iloc[offset : offset + limit]

    track_ids = [int(v) for v in page["track_id"].dropna().unique().tolist()]
    cover_map = _track_cover_urls(conn, track_ids) if track_ids else {}
    from backend.core.db import get_track_artist_names_map

    names_map = get_track_artist_names_map()

    result = []
    for r in page.itertuples(index=False):
        tid = int(r.track_id) if pd.notna(r.track_id) else None
        representative_value = getattr(r, "representative_track_id", tid)
        representative_track_id = (
            int(representative_value)
            if representative_value is not None and pd.notna(representative_value)
            else tid
        )
        entry = {
            "play_id": int(r.play_id),
            "ts": str(r.ts),
            "date": str(r.ts_date),
            "track_id": tid,
            "l1_id": tid,
            "representative_track_id": representative_track_id,
            "track_name": "" if pd.isna(r.track_name) else r.track_name,
            "artist_name": "" if pd.isna(r.artist_name) else r.artist_name,
            "album_name": None if pd.isna(r.album_name) else r.album_name,
            "ms_played": int(r.ms_played),
            "hours": round(float(r.ms_played) / 3_600_000, 3),
            "platform": "" if pd.isna(r.platform) else r.platform,
            "cover_url": cover_map.get(tid) if tid is not None else None,
        }
        if tid is not None and tid in names_map:
            entry["artist_names"] = names_map[tid]
        result.append(entry)

    return {"total": total, "limit": limit, "offset": offset, "rows": result}


def _filter_entity_rows(
    df: pd.DataFrame,
    entity: str,
    track_id: int | None,
    album_name: str | None,
    artist_name: str | None,
    conn: sqlite3.Connection | None = None,
    merge_level: int = 2,
) -> pd.DataFrame:
    if df.empty:
        return df
    if entity == "track" and track_id is not None:
        scope = resolve_track_aggregation_scope(conn, track_id, merge_level) if conn else None
        member_ids = scope.member_track_ids if scope is not None else (track_id,)
        return df[df["track_id"].isin(member_ids)]
    if entity == "album" and album_name is not None:
        # Try album project canonical_song_key attribution first
        if conn is not None and artist_name is not None:
            project_keys = _resolve_album_project_song_keys(
                conn, album_name, artist_name, merge_level
            )
            if project_keys:
                from backend.domains.playback.album_projects import apply_canonical_song_keys

                df = apply_canonical_song_keys(df, conn, merge_level)
                return df[df["canonical_song_key"].isin(project_keys)]
        # Fallback: string match on album_name
        out = df[df["album_name"] == album_name]
        if artist_name is not None:
            out = out[out["artist_name"] == artist_name]
        return out
    if entity == "artist" and artist_name is not None:
        if conn is not None:
            from backend.domains.metadata.artist_identity import resolve_artist_name

            identity = resolve_artist_name(conn, artist_name)
            if identity is not None:
                artist_name = identity.display_name
        return df[df["artist_name"] == artist_name]
    return df.iloc[0:0]


def get_entity_play_dates(
    conn: sqlite3.Connection,
    entity: str,
    track_id: int | None = None,
    album_name: str | None = None,
    artist_name: str | None = None,
    min_ms: int = 30000,
    music_only: bool = True,
    merge_enabled: bool = True,
    merge_level: int = 2,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
) -> list[dict[str, Any]]:
    """Return [{date, count}] for calendar highlighting."""
    loader = None
    if entity == "track" and track_id is not None and period in {"lifetime", "custom"}:
        scope = resolve_track_aggregation_scope(conn, track_id, merge_level)
        loader = _scoped_play_loader(
            conn,
            list(scope.member_track_ids),
            music_only=music_only,
            ids_are_l1=True,
        )
    _, df, _ = load_period_plays(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        _loader=load_plays_for_artists if entity == "artist" else loader,
        attach_duration_slices=False,
    )
    df = _filter_entity_rows(
        df, entity, track_id, album_name, artist_name, conn=conn, merge_level=merge_level
    )
    if df.empty:
        return []
    counts = df.groupby("ts_date").size().reset_index(name="count").sort_values("ts_date")
    return [{"date": str(r.ts_date), "count": int(r.count)} for r in counts.itertuples(index=False)]


# Keep the builders directly callable for in-memory/unit-test databases, while
# primary-database API reads use bounded revision-keyed response caches.
def _is_primary_connection(conn: sqlite3.Connection) -> bool:
    row = conn.execute("PRAGMA database_list").fetchone()
    path = str(row[2] or "") if row is not None else ""
    return bool(path) and os.path.realpath(path) == os.path.realpath(DB_PATH)


def _entity_stats_revision_state(conn: sqlite3.Connection) -> tuple[int, int, int, int, int]:
    from backend.domains.metadata.track_identity import get_track_identity_revision

    state = get_music_search_revision_state(conn)
    return (
        state.playback_revision,
        state.metadata_revision,
        state.settings_revision,
        state.candidate_revision,
        get_track_identity_revision(conn),
    )


@singleflight
@lru_cache(maxsize=128)
def _track_stats_cached(args: tuple, _revision_state: tuple) -> dict:
    conn = get_db(readonly=True)
    try:
        return _build_track_stats(conn, *args)
    finally:
        conn.close()


@singleflight
@lru_cache(maxsize=64)
def _album_stats_cached(args: tuple, _revision_state: tuple) -> dict:
    conn = get_db(readonly=True)
    try:
        return _build_album_stats(conn, *args)
    finally:
        conn.close()


@singleflight
@lru_cache(maxsize=64)
def _artist_stats_cached(args: tuple, _revision_state: tuple) -> dict:
    conn = get_db(readonly=True)
    try:
        return _build_artist_stats(conn, *args)
    finally:
        conn.close()


def get_track_stats(
    conn: sqlite3.Connection,
    track_id: int,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    merge_level: int = 2,
    include_rank_context: bool = True,
) -> dict:
    args = (
        track_id,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold,
        max_merge_gap_minutes,
        merge_level,
        include_rank_context,
    )
    if _is_primary_connection(conn):
        return _track_stats_cached(args, _entity_stats_revision_state(conn))
    return _build_track_stats(conn, *args)


def get_album_stats(
    conn: sqlite3.Connection,
    album_name: str,
    artist: str | None,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    merge_level: int = 2,
    include_rank_context: bool = True,
) -> dict:
    args = (
        album_name,
        artist,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold,
        max_merge_gap_minutes,
        merge_level,
        include_rank_context,
    )
    if _is_primary_connection(conn):
        return _album_stats_cached(args, _entity_stats_revision_state(conn))
    return _build_album_stats(
        conn,
        *args[:-2],
        merge_level=merge_level,
        include_rank_context=include_rank_context,
    )


def get_artist_stats(
    conn: sqlite3.Connection,
    artist_name: str,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    period: str = "lifetime",
    start_date: str | None = None,
    end_date: str | None = None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    include_rank_context: bool = True,
) -> dict:
    args = (
        artist_name,
        min_ms,
        music_only,
        merge_enabled,
        period,
        start_date,
        end_date,
        dynamic_threshold,
        max_merge_gap_minutes,
        include_rank_context,
    )
    if _is_primary_connection(conn):
        return _artist_stats_cached(args, _entity_stats_revision_state(conn))
    return _build_artist_stats(conn, *args)


from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("analysis", "track_entity_stats", _track_stats_cached)
register_lru("analysis", "album_entity_stats", _album_stats_cached)
register_lru("analysis", "artist_entity_stats", _artist_stats_cached)

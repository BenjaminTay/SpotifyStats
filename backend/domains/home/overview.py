"""Deterministic personal music front-page computation."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import pandas as pd

from backend.core.db import load_plays, load_plays_for_artists
from backend.domains.playback.track_groups import load_track_group_keys
from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services.analysis_stats_service import chart_rows
from backend.services.play_service import _track_cover_urls
from backend.services.yearly_review_service import (
    get_cached_yearly_review_artifact,
    get_yearly_review_available_years,
)

EMPTY_SUMMARY = {
    "plays": 0,
    "hours": 0.0,
    "active_days": 0,
    "plays_delta_pct": None,
    "hours_delta_pct": None,
    "late_night_pct": 0.0,
    "weekend_pct": 0.0,
}


def _today() -> date:
    return date.today()


def _round_hours(value: float | int) -> float:
    return round(float(value) / 3_600_000, 1)


def _pct_delta(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _period(start: date, end: date) -> dict[str, str]:
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "label": f"截至 {end.isoformat()} 的最近4周",
    }


def _track_frame(conn: sqlite3.Connection, df: pd.DataFrame, merge_level: int) -> pd.DataFrame:
    result = df.copy()
    result["home_track_id"] = result["track_id"]
    result["home_track_name"] = result["track_name"]
    if merge_level <= 1 or result.empty:
        return result
    keys = load_track_group_keys(conn, merge_level)
    if keys.empty:
        return result
    keys = keys.copy()
    keys["_scope_rank"] = keys["track_group_scope"].map(
        {"composition": 0, "recording": 1} if merge_level >= 3 else {"recording": 0}
    )
    key_map = (
        keys.sort_values(["track_id", "_scope_rank", "track_agg_id"])
        .drop_duplicates("track_id")
        .set_index("track_id")
    )
    mapped_ids = result["track_id"].map(key_map["track_agg_id"])
    mapped_names = result["track_id"].map(key_map["track_agg_name"])
    result["home_track_id"] = mapped_ids.fillna(result["track_id"]).astype(int)
    result["home_track_name"] = mapped_names.fillna(result["track_name"])
    return result


def _track_entity(
    track_id: int, name: str, artist_name: str, cover_url: str | None
) -> dict[str, Any]:
    return {
        "entity_type": "track",
        "entity_id": int(track_id),
        "name": str(name),
        "artist_name": str(artist_name),
        "cover_url": cover_url,
        "deep_link": f"/music/tracks/{int(track_id)}",
    }


def _album_entity(
    entity_id: int | str | None, name: str, artist_name: str, cover_url: str | None
) -> dict[str, Any]:
    return {
        "entity_type": "album",
        "entity_id": entity_id,
        "name": str(name),
        "artist_name": str(artist_name),
        "cover_url": cover_url,
        "deep_link": (
            f"/music/albums/{quote(str(name), safe='')}?artist={quote(str(artist_name), safe='')}"
        ),
    }


def _artist_entity(entity_id: int | str | None, name: str, cover_url: str | None) -> dict[str, Any]:
    return {
        "entity_type": "artist",
        "entity_id": entity_id,
        "name": str(name),
        "artist_name": None,
        "cover_url": cover_url,
        "deep_link": f"/music/artists/{quote(str(name), safe='')}",
    }


def _account_data_exists(conn: sqlite3.Connection) -> bool:
    for table in ("saved_tracks", "playlists", "search_queries"):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if exists and conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            return True
    return False


def _source_dates(conn: sqlite3.Connection) -> tuple[date | None, date | None]:
    row = conn.execute(
        """SELECT MIN(ts_date), MAX(ts_date)
           FROM plays WHERE track_id IS NOT NULL"""
    ).fetchone()
    if row is None or row[0] is None or row[1] is None:
        return None, None
    return date.fromisoformat(str(row[0])), date.fromisoformat(str(row[1]))


def _recent_track_leader(
    conn: sqlite3.Connection, frame: pd.DataFrame, merge_level: int
) -> dict[str, Any] | None:
    if frame.empty:
        return None
    _total, rows = chart_rows(conn, frame, "track", "plays", 1, 0, merge_level)
    if not rows:
        return None
    row = rows[0]
    track_id = int(row["track_id"])
    return {
        "entity": _track_entity(
            track_id,
            str(row["track_name"]),
            str(row["artist_name"]),
            row.get("cover_url"),
        ),
        "plays": int(row["plays"]),
        "hours": round(float(row["hours"]), 1),
    }


def _recent_artist_leader(conn: sqlite3.Connection, frame: pd.DataFrame) -> dict[str, Any] | None:
    if frame.empty:
        return None
    _total, rows = chart_rows(conn, frame, "artist", "plays", 1)
    if not rows:
        return None
    row = rows[0]
    name = str(row["artist_name"])
    artist_row = conn.execute(
        "SELECT artist_id FROM artists WHERE artist_name=?", (name,)
    ).fetchone()
    artist_id = int(artist_row[0]) if artist_row else None
    return {
        "entity": _artist_entity(artist_id, name, row.get("cover_url")),
        "plays": int(row["plays"]),
        "hours": round(float(row["hours"]), 1),
    }


def _recent_album_leader(
    conn: sqlite3.Connection,
    frame: pd.DataFrame,
    context: YearlyReviewFilterContext,
) -> dict[str, Any] | None:
    if frame.empty:
        return None
    _total, rows = chart_rows(
        conn,
        frame,
        "album",
        "plays",
        1,
        0,
        context.merge_level,
        context.include_compilations,
    )
    if not rows:
        return None
    row = rows[0]
    name = str(row["album_name"])
    artist = str(row["artist_name"])
    return {
        "entity": _album_entity(row.get("album_project_id"), name, artist, row.get("cover_url")),
        "plays": int(row["plays"]),
        "hours": round(float(row["hours"]), 1),
    }


def _recent_payload(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    artist_df: pd.DataFrame,
    context: YearlyReviewFilterContext,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    latest = pd.to_datetime(df["ts_date"]).max().date()
    current_start = latest - timedelta(days=27)
    previous_start = latest - timedelta(days=55)
    previous_end = latest - timedelta(days=28)
    dates = pd.to_datetime(df["ts_date"]).dt.date
    current = df[(dates >= current_start) & (dates <= latest)].copy()
    previous = df[(dates >= previous_start) & (dates <= previous_end)].copy()
    artist_dates = pd.to_datetime(artist_df["ts_date"]).dt.date
    current_artists = artist_df[(artist_dates >= current_start) & (artist_dates <= latest)].copy()

    current_tracks = _track_frame(conn, current, context.merge_level)
    previous_tracks = _track_frame(conn, previous, context.merge_level)
    comparison_available = dates.min() <= previous_start and not current.empty
    current_ms = int(current["ms_played"].sum())
    previous_ms = int(previous["ms_played"].sum())
    late_night = current["ts_hour"].isin([23, 0, 1, 2, 3, 4, 5]).mean() * 100
    weekend = (current["ts_dow"] >= 5).mean() * 100
    daily = (
        current.groupby("ts_date")
        .agg(plays=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
        .sort_values("ts_date")
    )
    daily_map = {
        str(row.ts_date): (int(row.plays), _round_hours(row.total_ms))
        for row in daily.itertuples(index=False)
    }
    payload = {
        "period": _period(current_start, latest),
        "comparison_period": _period(previous_start, previous_end),
        "comparison_available": comparison_available,
        "summary": {
            "plays": len(current),
            "hours": _round_hours(current_ms),
            "active_days": int(current["ts_date"].nunique()),
            "plays_delta_pct": _pct_delta(len(current), len(previous))
            if comparison_available
            else None,
            "hours_delta_pct": _pct_delta(current_ms, previous_ms)
            if comparison_available
            else None,
            "late_night_pct": round(float(late_night), 1),
            "weekend_pct": round(float(weekend), 1),
        },
        "trend": [
            {
                "date": day.isoformat(),
                "plays": daily_map.get(day.isoformat(), (0, 0.0))[0],
                "hours": daily_map.get(day.isoformat(), (0, 0.0))[1],
            }
            for day in (current_start + timedelta(days=offset) for offset in range(28))
        ],
        "leaders": {
            "track": _recent_track_leader(conn, current, context.merge_level),
            "album": _recent_album_leader(conn, current, context),
            "artist": _recent_artist_leader(conn, current_artists),
        },
    }
    return payload, current_tracks, previous_tracks, current


def _headline(
    conn: sqlite3.Connection,
    current: pd.DataFrame,
    previous: pd.DataFrame,
    all_tracks: pd.DataFrame,
    recent: dict[str, Any],
) -> dict[str, Any]:
    def aggregate(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["home_track_id", "plays", "total_ms"])
        return (
            frame.groupby("home_track_id")
            .agg(
                name=("home_track_name", "first"),
                artist=("artist_name", "first"),
                plays=("play_id", "count"),
                total_ms=("ms_played", "sum"),
                first_date=("ts_date", "min"),
            )
            .reset_index()
        )

    current_agg = aggregate(current)
    current_top_ids = set(
        current_agg.sort_values(
            ["plays", "total_ms", "home_track_id"], ascending=[False, False, True]
        )
        .head(5)["home_track_id"]
        .tolist()
    )
    previous_counts = aggregate(previous).set_index("home_track_id")["plays"].to_dict()
    history = all_tracks[
        ~all_tracks.index.isin(current.index) & ~all_tracks.index.isin(previous.index)
    ]
    history_counts = aggregate(history).set_index("home_track_id")["plays"].to_dict()
    first_dates = aggregate(all_tracks).set_index("home_track_id")["first_date"].to_dict()
    candidates: list[tuple[int, int, int, str, pd.Series]] = []
    period_start = current["ts_date"].min() if not current.empty else None
    for row in current_agg.itertuples(index=False):
        previous_plays = int(previous_counts.get(row.home_track_id, 0))
        older_plays = int(history_counts.get(row.home_track_id, 0))
        if (
            row.home_track_id in current_top_ids
            and row.plays >= 5
            and previous_plays <= 1
            and older_plays >= 10
        ):
            candidates.append((0, -int(row.plays), int(row.home_track_id), "comeback", row))
        if (
            row.home_track_id in current_top_ids
            and row.plays >= 5
            and str(first_dates.get(row.home_track_id)) >= str(period_start)
        ):
            candidates.append((1, -int(row.plays), int(row.home_track_id), "discovery", row))
        if row.plays >= 8 and row.plays - previous_plays >= 5 and row.plays >= previous_plays * 2:
            candidates.append((2, -int(row.plays), int(row.home_track_id), "surge", row))
    if candidates:
        _, _, _, kind, row = min(candidates)
        track_id = int(row.home_track_id)
        cover = _track_cover_urls(conn, [track_id]).get(track_id)
        entity = _track_entity(track_id, row.name, row.artist, cover)
        if kind == "comeback":
            return {
                "kind": kind,
                "title": f"最近，你重新回到了《{row.name}》",
                "statement": f"最近4周播放了 {int(row.plays)} 次。",
                "entity": entity,
            }
        if kind == "discovery":
            return {
                "kind": kind,
                "title": f"《{row.name}》成为这一阶段的新发现",
                "statement": f"首次播放后，最近4周已播放 {int(row.plays)} 次。",
                "entity": entity,
            }
        return {
            "kind": kind,
            "title": f"《{row.name}》在最近明显升温",
            "statement": f"最近4周播放了 {int(row.plays)} 次。",
            "entity": entity,
        }

    if len(current) >= 50 and not previous.empty:
        current_late = current["ts_hour"].isin([23, 0, 1, 2, 3, 4, 5]).mean() * 100
        previous_late = previous["ts_hour"].isin([23, 0, 1, 2, 3, 4, 5]).mean() * 100
        current_weekend = (current["ts_dow"] >= 5).mean() * 100
        previous_weekend = (previous["ts_dow"] >= 5).mean() * 100
        shifts = [
            (abs(current_late - previous_late), "深夜", current_late - previous_late),
            (
                abs(current_weekend - previous_weekend),
                "周末",
                current_weekend - previous_weekend,
            ),
        ]
        magnitude, label, signed_change = max(shifts, key=lambda value: (value[0], value[1]))
        if magnitude >= 10:
            direction = "更多" if signed_change > 0 else "更少"
            return {
                "kind": "habit_shift",
                "title": f"这一阶段，你的音乐{direction}发生在{label}",
                "statement": f"占比较此前4周变化 {abs(signed_change):.1f} 个百分点。",
                "entity": None,
            }

    leader = recent["leaders"]["track"]
    if leader:
        entity = leader["entity"]
        return {
            "kind": "leader",
            "title": f"最近4周的聆听中心是《{entity['name']}》",
            "statement": f"这一阶段共播放 {leader['plays']} 次。",
            "entity": entity,
        }
    return {
        "kind": "archive",
        "title": "你的个人音乐档案",
        "statement": "从播放记录中整理每一段音乐生活。",
        "entity": None,
    }


def _champion(
    rows: list[dict[str, Any]],
    latest_week: str,
    previous_week: str | None,
    entity_type: str,
) -> dict[str, Any] | None:
    row = next(
        (
            item
            for item in rows
            if item.get("billboard_week") == latest_week and item.get("rank") == 1
        ),
        None,
    )
    if row is None:
        return None
    if entity_type == "track":
        identity = row.get("track_id")
        entity = _track_entity(
            identity, row.get("track_name", ""), row.get("artist_name", ""), row.get("cover_url")
        )
        identity_key = "track_id"
    elif entity_type == "album":
        identity = row.get("album_project_id")
        entity = _album_entity(
            identity, row.get("album_name", ""), row.get("artist_name", ""), row.get("cover_url")
        )
        identity_key = "album_project_id"
    else:
        identity = row.get("artist_id")
        entity = _artist_entity(identity, row.get("artist_name", ""), row.get("cover_url"))
        identity_key = "artist_id"
    prior = next(
        (
            item
            for item in rows
            if previous_week
            and item.get("billboard_week") == previous_week
            and item.get(identity_key) == identity
        ),
        None,
    )
    previous_rank = int(prior["rank"]) if prior else None
    return {
        "entity": entity,
        "rank": 1,
        "plays": int(row.get("play_count", 0)),
        "hours": _round_hours(row.get("total_ms", 0)),
        "previous_rank": previous_rank,
        "rank_change": previous_rank - 1 if previous_rank else None,
    }


def _billboard(context: YearlyReviewFilterContext) -> dict[str, Any]:
    try:
        from backend.domains.billboard.latest_snapshot_cache import (
            get_latest_snapshot_if_cached,
            snapshot_key,
        )

        data = get_latest_snapshot_if_cached(
            snapshot_key(
                context.min_ms,
                context.music_only,
                context.bb_top_n,
                context.bb_album_top_n,
                context.bb_artist_top_n,
                context.bb_week_start_dow,
                context.bb_week_start_hour,
                None,
                None,
                context.merge_level,
                context.dynamic_threshold,
                context.max_merge_gap_minutes,
                context.include_compilations,
            )
        )
        if data is None:
            raise ValueError("exact Billboard preview is not warm")
        weeks = data["meta"]["all_weeks_desc"]
        if not weeks:
            raise ValueError("no chart weeks")
        latest = weeks[0]
        previous = weeks[1] if len(weeks) > 1 else None
        return {
            "state": "ready",
            "week": latest,
            "track": _champion(data["weekly"], latest, previous, "track"),
            "album": _champion(data["weekly_album"], latest, previous, "album"),
            "artist": _champion(data["weekly_artist"], latest, previous, "artist"),
        }
    except Exception:
        return {"state": "unavailable", "week": None, "track": None, "album": None, "artist": None}


def _yearly(context: YearlyReviewFilterContext) -> dict[str, Any]:
    try:
        year = get_yearly_review_available_years().latest_year
        if year is None:
            return {
                "state": "unavailable",
                "year": None,
                "headline": None,
                "statement": None,
                "entity": None,
            }
        artifact = get_cached_yearly_review_artifact(year, context)
        if artifact is None:
            return {
                "state": "not_generated",
                "year": year,
                "headline": None,
                "statement": None,
                "entity": None,
            }
        report = artifact["report"]
        headline = next(
            (
                item
                for item in report.get("headlines", [])
                if item.get("evidence_status") != "unavailable"
            ),
            None,
        )
        leaders = report.get("honors", {}).get("play_leaders", {})
        candidate = (leaders.get("artist") or {}).get("entity") or (leaders.get("track") or {}).get(
            "entity"
        )
        entity = candidate if candidate and candidate.get("deep_link") else None
        return {
            "state": "ready",
            "year": year,
            "headline": headline.get("title") if headline else f"{year} 年度音乐年鉴",
            "statement": headline.get("statement") if headline else None,
            "entity": entity,
        }
    except Exception:
        return {
            "state": "unavailable",
            "year": None,
            "headline": None,
            "statement": None,
            "entity": None,
        }


def _rediscovery(
    conn: sqlite3.Connection, all_tracks: pd.DataFrame, latest: date
) -> dict[str, Any] | None:
    cutoff = latest - timedelta(days=90)
    grouped = (
        all_tracks.groupby(["home_track_id", "home_track_name", "artist_name"], dropna=False)
        .agg(
            total_plays=("play_id", "count"),
            last_played=("ts_date", "max"),
            total_ms=("ms_played", "sum"),
        )
        .reset_index()
    )
    grouped["last_played_date"] = pd.to_datetime(grouped["last_played"]).dt.date
    candidates = grouped[
        (grouped["total_plays"] >= 10) & (grouped["last_played_date"] < cutoff)
    ].copy()
    if candidates.empty:
        return None
    candidates = candidates.sort_values(
        ["total_plays", "last_played_date", "home_track_id"], ascending=[False, True, True]
    ).head(20)
    week_key = f"{latest.isocalendar().year}-{latest.isocalendar().week}"
    index = int(hashlib.sha256(week_key.encode()).hexdigest()[:8], 16) % len(candidates)
    row = candidates.iloc[index]
    track_id = int(row["home_track_id"])
    cover = _track_cover_urls(conn, [track_id]).get(track_id)
    last_played = row["last_played_date"]
    return {
        "entity": _track_entity(track_id, row["home_track_name"], row["artist_name"], cover),
        "last_played": last_played.isoformat(),
        "total_plays": int(row["total_plays"]),
        "days_since_last_play": (latest - last_played).days,
    }


def build_home_overview(
    conn: sqlite3.Connection, context: YearlyReviewFilterContext
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    first_source, latest_source = _source_dates(conn)
    source_age = (_today() - latest_source).days if latest_source else None
    freshness = (
        "unknown"
        if source_age is None
        else "recent"
        if source_age <= 7
        else "aging"
        if source_age <= 30
        else "old"
    )
    df = load_plays(
        conn,
        min_ms=context.min_ms,
        music_only=context.music_only,
        merge_enabled=context.merge_enabled,
        dynamic_threshold=context.dynamic_threshold,
        max_merge_gap_minutes=context.max_merge_gap_minutes,
    )
    empty_archive = {
        "total_plays": 0,
        "total_hours": 0.0,
        "unique_tracks": 0,
        "unique_artists": 0,
        "unique_albums": 0,
        "active_days": 0,
    }
    if df.empty:
        has_source = latest_source is not None
        return {
            "schema_version": "home_overview_v1",
            "generated_at": generated_at,
            "filter_fingerprint": context.filter_fingerprint,
            "state": "limited" if has_source else "empty",
            "coverage": {
                "first_source_date": first_source.isoformat() if first_source else None,
                "source_latest_date": latest_source.isoformat() if latest_source else None,
                "first_effective_play_date": None,
                "latest_effective_play_date": None,
                "first_play_date": None,
                "latest_play_date": None,
                "freshness": freshness,
                "has_account_data": _account_data_exists(conn),
            },
            "archive": empty_archive,
            "headline": {
                "kind": "archive",
                "title": (
                    "当前统计口径下暂无有效播放"
                    if has_source
                    else "把 Spotify 历史变成你的个人音乐档案"
                ),
                "statement": (
                    "播放源数据仍在，调整有效播放设置后即可查看。"
                    if has_source
                    else "导入播放记录后，这里会成为你的个人音乐头版。"
                ),
                "entity": None,
            },
            "recent": None,
            "billboard": {
                "state": "unavailable",
                "week": None,
                "track": None,
                "album": None,
                "artist": None,
            },
            "yearly_review": {
                "state": "unavailable",
                "year": None,
                "headline": None,
                "statement": None,
                "entity": None,
            },
            "rediscovery": None,
        }

    artist_df = load_plays_for_artists(
        conn,
        min_ms=context.min_ms,
        music_only=context.music_only,
        merge_enabled=context.merge_enabled,
        dynamic_threshold=context.dynamic_threshold,
        max_merge_gap_minutes=context.max_merge_gap_minutes,
    )
    dates = pd.to_datetime(df["ts_date"]).dt.date
    first, latest = dates.min(), dates.max()
    all_tracks = _track_frame(conn, df, context.merge_level)
    all_artist_count = int(artist_df["artist_id"].nunique()) if not artist_df.empty else 0
    album_count, _album_rows = chart_rows(
        conn,
        df,
        "album",
        "plays",
        None,
        0,
        context.merge_level,
        context.include_compilations,
    )
    recent, current, previous, _raw_current = _recent_payload(conn, df, artist_df, context)
    return {
        "schema_version": "home_overview_v1",
        "generated_at": generated_at,
        "filter_fingerprint": context.filter_fingerprint,
        "state": "ready" if recent["comparison_available"] else "limited",
        "coverage": {
            "first_source_date": first_source.isoformat() if first_source else None,
            "source_latest_date": latest_source.isoformat() if latest_source else None,
            "first_effective_play_date": first.isoformat(),
            "latest_effective_play_date": latest.isoformat(),
            "first_play_date": first.isoformat(),
            "latest_play_date": latest.isoformat(),
            "freshness": freshness,
            "has_account_data": _account_data_exists(conn),
        },
        "archive": {
            "total_plays": len(df),
            "total_hours": _round_hours(df["ms_played"].sum()),
            "unique_tracks": int(all_tracks["home_track_id"].nunique()),
            "unique_artists": all_artist_count,
            "unique_albums": album_count,
            "active_days": int(df["ts_date"].nunique()),
        },
        "headline": _headline(conn, current, previous, all_tracks, recent),
        "recent": recent,
        "billboard": _billboard(context),
        "yearly_review": _yearly(context),
        "rediscovery": _rediscovery(conn, all_tracks, latest),
    }

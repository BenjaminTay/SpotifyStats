"""Read-only report-oriented tools for agentic yearly reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

REPORT_TOOL_NAMES = {
    "report_period_context",
    "yearly_overview",
    "yearly_top_entities",
    "yearly_same_period_comparison",
    "personal_billboard_year_end",
    "billboard_yearly_diagnostics",
    "entity_stats",
    "genre_distribution",
    "discovery_and_returns",
    "highlight_day_detail",
}


@dataclass(frozen=True)
class ReportToolDefinition:
    name: str
    description: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    read_only: bool = True

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "read_only": self.read_only,
        }


def _period_context(params: dict[str, Any]) -> dict[str, Any]:
    year = int(params.get("year") or date.today().year)
    latest = str(params.get("latest_play_date") or "")
    if not latest:
        try:
            period = _gather_yearly_data_for_tool(params).get("reporting_period") or {}
        except Exception:
            period = {}
        latest = str(period.get("end_date") or period.get("latest_play_date") or f"{year}-12-31")
    end_date = latest if latest.startswith(f"{year}-") else f"{year}-12-31"
    is_partial = end_date < f"{year}-12-31"
    previous_end = f"{year - 1}-{end_date[5:]}"
    data = {
        "year": year,
        "start_date": f"{year}-01-01",
        "end_date": end_date,
        "latest_play_date": latest,
        "is_partial_year": is_partial,
        "same_period_previous": {
            "start_date": f"{year - 1}-01-01",
            "end_date": previous_end,
        },
    }
    return {
        "ok": True,
        "data": data,
        "summary": (
            f"{year} report period is {data['start_date']} to {end_date}; "
            f"same-period comparison ends {previous_end}."
        ),
    }


def _not_implemented_summary(tool_name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def handler(params: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "data": {"params": params, "pending_live_implementation": True},
            "summary": f"{tool_name} stub returned no live data in this task.",
        }

    return handler


def _gather_yearly_data_for_tool(params: dict[str, Any]) -> dict[str, Any]:
    from backend.core.db import get_db
    from backend.services.ai_insights_service import _gather_yearly_data

    conn = get_db(readonly=True)
    try:
        return _gather_yearly_data(
            conn,
            min_ms=int(params.get("min_ms") or 30000),
            music_only=bool(params.get("music_only", True)),
            merge_enabled=bool(params.get("merge_enabled", True)),
            year=int(params.get("year") or date.today().year),
            dynamic_threshold=bool(params.get("dynamic_threshold", True)),
            max_merge_gap_minutes=params.get("max_merge_gap_minutes"),
        )
    finally:
        conn.close()


def _yearly_overview(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    period = data.get("reporting_period") or {}
    hero = data.get("hero") or {}
    total_minutes = float(hero.get("total_minutes") or 0)
    summary = (
        f"{period.get('start_date')} to {period.get('end_date')}: "
        f"{int(hero.get('total_plays') or 0):,} plays, "
        f"{round(total_minutes / 60, 1):g} hours, "
        f"{int(hero.get('unique_tracks') or 0):,} tracks, "
        f"{int(hero.get('unique_artists') or 0):,} artists."
    )
    return {"ok": True, "data": {"reporting_period": period, "hero": hero}, "summary": summary}


def _yearly_top_entities(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    payload = {
        "top_artists": data.get("top_artists") or [],
        "top_tracks": data.get("top_tracks") or [],
        "top_albums": data.get("top_albums") or [],
    }
    artist = _name(payload["top_artists"])
    track = _name(payload["top_tracks"])
    album = _name(payload["top_albums"])
    return {
        "ok": True,
        "data": payload,
        "summary": f"Top artist: {artist}; top track: {track}; top album: {album}.",
    }


def _personal_billboard_year_end(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    billboard = data.get("billboard_year_end") or {}
    summary = (
        f"Personal Billboard: track {_name(billboard.get('tracks') or [])}, "
        f"album {_name(billboard.get('albums') or [])}, "
        f"artist {_name(billboard.get('artists') or [])}."
    )
    return {"ok": True, "data": billboard, "summary": summary}


def _billboard_yearly_diagnostics(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    billboard = data.get("billboard_year_end") or {}
    artists = billboard.get("artists") or []
    albums = billboard.get("albums") or []
    tracks = billboard.get("tracks") or []
    top_artist = artists[0] if artists else {}
    artist_name = str(top_artist.get("name") or "")
    diagnostics = {
        "dominance": {
            "artist": artist_name,
            "reason": (
                f"artist rank #{top_artist.get('rank')}, "
                f"{top_artist.get('weeks_on_chart')} weeks on chart, "
                f"{top_artist.get('weeks_at_no1')} weeks at No.1"
            )
            if artist_name
            else "",
        },
        "stability_leaders": _stability_leaders(artists, albums, tracks),
        "breakout_leaders": _breakout_leaders(data.get("new_artists") or []),
        "cross_chart_alignment": _cross_chart_alignment(artists, albums, tracks),
        "playback_billboard_tensions": [],
    }
    return {
        "ok": True,
        "data": diagnostics,
        "summary": (
            "Billboard diagnostics: "
            f"dominance={artist_name or 'none'}; "
            f"alignments={len(diagnostics['cross_chart_alignment'])}."
        ),
    }


def _yearly_same_period_comparison(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    yoy = data.get("year_over_year") if isinstance(data.get("year_over_year"), dict) else {}
    same_period = yoy.get("same_period") if isinstance(yoy.get("same_period"), dict) else {}
    changes = same_period.get("changes") if isinstance(same_period.get("changes"), dict) else {}
    summary = "同比数据不可用。"
    if same_period.get("available"):
        summary = (
            "同比同周期："
            f"播放 {changes.get('plays_change', 0):+.1f}%，"
            f"时长 {changes.get('hours_change', 0):+.1f}%，"
            f"曲目 {changes.get('tracks_change', 0):+.1f}%，"
            f"艺人 {changes.get('artists_change', 0):+.1f}%。"
        )
    return {"ok": True, "data": yoy, "summary": summary}


def _genre_distribution(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    summary_data = data.get("genre_summary") if isinstance(data.get("genre_summary"), dict) else {}
    top_genres = summary_data.get("top_genres") or data.get("top_genres") or []
    leader = _name(top_genres)
    summary = f"Top genre: {leader}." if leader else "No genre distribution available."
    if isinstance(top_genres, list) and top_genres and isinstance(top_genres[0], dict):
        share = top_genres[0].get("share")
        if isinstance(share, (int, float)):
            summary = f"Top genre: {leader} ({share:.1f}%)."
    return {"ok": True, "data": {**summary_data, "top_genres": top_genres}, "summary": summary}


def _discovery_and_returns(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    new_artists = data.get("new_artists") or []
    longest_love = data.get("longest_love")
    leader = _name(new_artists)
    summary_parts = []
    if leader:
        summary_parts.append(f"New artist leader: {leader}.")
    if isinstance(longest_love, dict):
        love_name = longest_love.get("track_name") or longest_love.get("name")
        days = longest_love.get("days") or longest_love.get("span_days")
        if love_name:
            summary_parts.append(f"Longest return: {love_name} ({days} days).")
    return {
        "ok": True,
        "data": {"new_artists": new_artists, "longest_love": longest_love},
        "summary": " ".join(summary_parts) or "No discovery or return signal available.",
    }


def _highlight_day_detail(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    highlight = data.get("most_active_day") if isinstance(data.get("most_active_day"), dict) else {}
    summary = "No highlight day available."
    if highlight:
        guidance = highlight.get("interpretation_guidance") or ""
        summary = (
            f"{highlight.get('date')} had {highlight.get('plays')} plays. {guidance}"
        ).strip()
    return {"ok": True, "data": highlight, "summary": summary}


def _entity_stats(params: dict[str, Any]) -> dict[str, Any]:
    data = _gather_yearly_data_for_tool(params)
    payload = {
        "top_artists": data.get("top_artists") or [],
        "top_tracks": data.get("top_tracks") or [],
        "top_albums": data.get("top_albums") or [],
        "billboard_year_end": data.get("billboard_year_end") or {},
    }
    return {
        "ok": True,
        "data": payload,
        "summary": f"Entity stats loaded for top artist {_name(payload['top_artists'])}.",
    }


def _stability_leaders(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    labels = ("artist", "album", "track")
    for label, group in zip(labels, groups):
        for row in group[:3]:
            rows.append(
                {
                    "entity": row.get("name"),
                    "type": label,
                    "weeks_on_chart": row.get("weeks_on_chart"),
                }
            )
    return sorted(rows, key=lambda row: int(row.get("weeks_on_chart") or 0), reverse=True)[:5]


def _breakout_leaders(new_artists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "entity": row.get("name"),
            "type": "artist",
            "plays": row.get("plays"),
            "first_seen": row.get("first_date"),
        }
        for row in new_artists[:3]
        if row.get("name")
    ]


def _cross_chart_alignment(
    artists: list[dict[str, Any]],
    albums: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    artist_names = {str(row.get("name") or "") for row in artists[:3]}
    album_artists = {str(row.get("artist") or "") for row in albums[:3]}
    track_artists = {str(row.get("artist") or "") for row in tracks[:3]}
    aligned = sorted(name for name in artist_names & album_artists & track_artists if name)
    return [
        {
            "entity": name,
            "alignment": "artist_album_track_all_strong",
            "evidence": ["artist top 3", "album top 3", "track top 3"],
        }
        for name in aligned
    ]


def _name(rows: Any) -> str:
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return str(rows[0].get("name") or "")
    return ""


_TOOLS: dict[str, ReportToolDefinition] = {
    "report_period_context": ReportToolDefinition(
        name="report_period_context",
        description=(
            "Return report year, start/end dates, partial-year status, and same-period "
            "comparison window."
        ),
        handler=_period_context,
    ),
    "yearly_overview": ReportToolDefinition(
        name="yearly_overview",
        description="Return yearly or year-to-date playback overview.",
        handler=_yearly_overview,
    ),
    "yearly_top_entities": ReportToolDefinition(
        name="yearly_top_entities",
        description="Return top artists, tracks, and albums for the report period.",
        handler=_yearly_top_entities,
    ),
    "personal_billboard_year_end": ReportToolDefinition(
        name="personal_billboard_year_end",
        description=(
            "Return local personal Billboard year-end or year-to-date track, album, "
            "and artist charts."
        ),
        handler=_personal_billboard_year_end,
    ),
    "billboard_yearly_diagnostics": ReportToolDefinition(
        name="billboard_yearly_diagnostics",
        description=(
            "Analyze personal Billboard dominance, stability, breakout signals, "
            "and cross-chart alignment."
        ),
        handler=_billboard_yearly_diagnostics,
    ),
    "yearly_same_period_comparison": ReportToolDefinition(
        name="yearly_same_period_comparison",
        description="Return same-period year-over-year comparison for partial-year reports.",
        handler=_yearly_same_period_comparison,
    ),
    "genre_distribution": ReportToolDefinition(
        name="genre_distribution",
        description="Return genre distribution and Spotify genre caveats.",
        handler=_genre_distribution,
    ),
    "discovery_and_returns": ReportToolDefinition(
        name="discovery_and_returns",
        description="Return new-artist discovery and longest-return signals.",
        handler=_discovery_and_returns,
    ),
    "highlight_day_detail": ReportToolDefinition(
        name="highlight_day_detail",
        description="Return the most active day and interpretation guidance.",
        handler=_highlight_day_detail,
    ),
    "entity_stats": ReportToolDefinition(
        name="entity_stats",
        description="Return compact entity statistics for top artists/tracks/albums.",
        handler=_entity_stats,
    ),
}

for _tool_name in sorted(REPORT_TOOL_NAMES - set(_TOOLS)):
    _TOOLS[_tool_name] = ReportToolDefinition(
        name=_tool_name,
        description=f"Read-only yearly report tool: {_tool_name}.",
        handler=_not_implemented_summary(_tool_name),
    )


def list_report_tools() -> list[dict[str, Any]]:
    return [_TOOLS[name].describe() for name in sorted(_TOOLS)]


def execute_report_tool(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        definition = _TOOLS[tool_name]
    except KeyError as exc:
        raise ValueError(f"Unknown report tool: {tool_name}") from exc
    if not definition.read_only:
        raise ValueError(f"Report tool is not read-only: {tool_name}")
    return definition.handler(params or {})

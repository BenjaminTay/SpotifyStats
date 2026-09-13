"""Schema-aware SQL projection for playback duration metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayDurationSql:
    """SQL fragments needed to resolve one play's reference duration."""

    expression: str
    joins: tuple[str, ...]


def build_play_duration_sql(
    *,
    play_columns: set[str],
    track_columns: set[str],
    spotify_meta_columns: set[str],
    play_alias: str = "p",
    track_alias: str = "t",
    event_meta_alias: str = "event_stm",
    primary_meta_alias: str = "primary_stm",
) -> PlayDurationSql:
    """Resolve duration as event provider -> primary provider -> legacy track.

    The returned fragments are deliberately schema-aware so archive readers can
    continue opening pre-migration databases that lack event-level Spotify IDs,
    the provider metadata table, or the legacy ``tracks.duration_ms`` column.
    """

    has_provider_duration = {"spotify_track_id", "duration_ms"}.issubset(spotify_meta_columns)
    candidates: list[str] = []
    joins: list[str] = []

    if has_provider_duration and "spotify_track_id_at_play" in play_columns:
        joins.append(
            f"LEFT JOIN spotify_track_meta {event_meta_alias} "
            f"ON {event_meta_alias}.spotify_track_id = "
            f"NULLIF({play_alias}.spotify_track_id_at_play, '')"
        )
        candidates.append(f"{event_meta_alias}.duration_ms")

    if has_provider_duration and "spotify_track_id" in track_columns:
        joins.append(
            f"LEFT JOIN spotify_track_meta {primary_meta_alias} "
            f"ON {primary_meta_alias}.spotify_track_id = "
            f"NULLIF({track_alias}.spotify_track_id, '')"
        )
        candidates.append(f"{primary_meta_alias}.duration_ms")

    if "duration_ms" in track_columns:
        candidates.append(f"{track_alias}.duration_ms")

    if not candidates:
        expression = "NULL"
    elif len(candidates) == 1:
        expression = candidates[0]
    else:
        expression = f"COALESCE({', '.join(candidates)})"

    return PlayDurationSql(expression=expression, joins=tuple(joins))

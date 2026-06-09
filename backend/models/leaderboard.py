"""Leaderboard response models."""

from __future__ import annotations

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    plays: int
    hours: float
    track_id: int | None = None
    track_name: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    cover_url: str | None = None
    unique_tracks: int | None = None
    artist_names: list[str] | None = None


class LeaderboardResponse(BaseModel):
    time_label: str
    total_records: int
    rows: list[LeaderboardEntry]

"""Leaderboard response models."""

from __future__ import annotations

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    plays: int
    hours: float
    track_id: int | None
    track_name: str
    artist_name: str
    cover_url: str | None
    artist_names: list[str] | None


class LeaderboardResponse(BaseModel):
    time_label: str
    total_records: int
    rows: list[LeaderboardEntry]

"""Leaderboard response models."""

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    entity_name: str  # track_name / artist_name / album_name
    sub_label: str = ""  # artist_name for tracks, album_name for ...
    plays: int = 0
    hours: float = 0.0


class LeaderboardResponse(BaseModel):
    entity: str
    top_n: int
    metric: str
    time_range: str
    rows: list[LeaderboardEntry]

"""Behavior & listening-hours response models."""

from pydantic import BaseModel


class ReasonDist(BaseModel):
    reason: str
    count: int


class FwdbtnByHour(BaseModel):
    hour: int
    count: int


class MostForwarded(BaseModel):
    track_name: str
    artist_name: str
    count: int


class PlatformMonthly(BaseModel):
    period: str
    platform: str
    count: int


class PlatformHourly(BaseModel):
    platform: str
    hour: int
    count: int


class ShufflePlatformRate(BaseModel):
    platform: str
    rate: float


class ShuffleMonthly(BaseModel):
    period: str
    rate: float


class BehaviorResponse(BaseModel):
    reason_end: list[ReasonDist]
    reason_start: list[ReasonDist]
    fwdbtn_by_hour: list[FwdbtnByHour]
    most_forwarded: list[MostForwarded]
    platform_monthly: list[PlatformMonthly]
    platform_hourly: list[PlatformHourly]
    shuffle_rate_by_platform: list[ShufflePlatformRate]
    shuffle_monthly: list[ShuffleMonthly]


class HeatmapResponse(BaseModel):
    z: list[list[int]]
    x: list[int]  # hours 0-23
    y: list[str]  # day labels


class YearlyHeatmapEntry(BaseModel):
    year: int
    z: list[list[int]]


class LateNightEntry(BaseModel):
    year: int
    rate: float


class LateNightResponse(BaseModel):
    by_year: list[LateNightEntry]

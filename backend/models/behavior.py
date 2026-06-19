"""Behavior & listening-hours response models."""

from pydantic import BaseModel, Field


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


class WeekdayWeekendResponse(BaseModel):
    hours: list[str] = Field(default_factory=list)
    weekend: list[int] = Field(default_factory=list)
    weekday: list[int] = Field(default_factory=list)
    comparison: list[dict] = Field(default_factory=list)


class PlatformHourlyListeningEntry(BaseModel):
    platform: str
    hour: int
    count: int


class PlatformPctEntry(BaseModel):
    platform: str
    hour: int
    pct: float


class PlatformPeakEntry(BaseModel):
    platform: str
    peak_hour: int
    peak_count: int
    total_count: int
    total_pct: float


class PlatformHourlyListeningResponse(BaseModel):
    platform_hourly: list[PlatformHourlyListeningEntry] = Field(default_factory=list)
    platform_pct: list[PlatformPctEntry] = Field(default_factory=list)
    platform_peaks: list[PlatformPeakEntry] = Field(default_factory=list)

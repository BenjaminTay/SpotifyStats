"""Utility functions for timezone conversion and platform classification."""

from datetime import datetime, timedelta
from typing import Optional, Union

# Timezone offsets in hours for common countries
COUNTRY_TZ_OFFSETS: dict[str, int] = {
    "CN": 8,
    "HK": 8,
    "TW": 8,
    "SG": 8,
    "MY": 8,
    "JP": 9,
    "KR": 9,
    "US": -5,  # default to EST, imperfect but good enough
    "GB": 0,
    "FR": 1,
    "DE": 1,
}


def convert_to_local_time(iso_str: str, country: Optional[str]) -> dict[str, Union[int, str]]:
    """Parse a UTC ISO 8601 timestamp and convert to local time for the given country.

    Returns a dict with precomputed time components:
        ts (original ISO string),
        ts_year, ts_month, ts_week (ISO week), ts_dow (0=Mon..6=Sun),
        ts_hour (0-23), ts_date (YYYY-MM-DD)
    """
    dt_utc = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    offset_hours = COUNTRY_TZ_OFFSETS.get(country or "", 8)
    dt_local = dt_utc + timedelta(hours=offset_hours)

    return {
        "ts": iso_str,
        "ts_year": dt_local.year,
        "ts_month": dt_local.month,
        "ts_week": dt_local.isocalendar()[1],
        "ts_dow": dt_local.weekday(),  # 0=Mon
        "ts_hour": dt_local.hour,
        "ts_date": dt_local.strftime("%Y-%m-%d"),
    }


def classify_platform(raw: Optional[str]) -> str:
    """Normalize platform string to a short canonical form.

    'iOS 15.5 (iPhone14,5)' -> 'ios'
    'OSX 14.5...' -> 'osx'
    'Windows 10...' -> 'windows'
    'Android ...' -> 'android'
    """
    if not raw:
        return "unknown"
    lower = raw.lower().strip()
    if "ios" in lower:
        return "ios"
    if "osx" in lower or "mac" in lower:
        return "osx"
    if "windows" in lower or "win" in lower:
        return "windows"
    if "android" in lower:
        return "android"
    if "web" in lower or "browser" in lower:
        return "web"
    return "other"


def format_duration(ms: int) -> str:
    """Format milliseconds into a human-readable string."""
    seconds = ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {seconds % 60}s"


def format_hours(total_ms: int) -> str:
    """Format total ms as hours with one decimal."""
    return f"{total_ms / 3_600_000:,.1f}"

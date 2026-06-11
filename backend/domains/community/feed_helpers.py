"""Community feed — Helper utilities for feed generation."""

import hashlib
import random
from datetime import datetime, timedelta

import pandas as pd

from backend.domains.community.accounts import FOLLOWER_MULTIPLIERS
from backend.domains.community.post_types import PostMetrics

# ──────────────────────────────────────────────


def _make_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _fmt_ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _fmt_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1000:.1f}K"
    return str(n)


def _week_end_date(week_val) -> str:
    """Given a billboard_week value (Timestamp, date, or string), return ISO date of
    the week's end (next week's first day) — when posts for this week would appear."""
    if isinstance(week_val, pd.Timestamp):
        dt = week_val.to_pydatetime()
    elif isinstance(week_val, datetime):
        dt = week_val
    elif hasattr(week_val, "strftime"):
        dt = datetime.combine(week_val, datetime.min.time())
    else:
        dt = pd.Timestamp(str(week_val)).to_pydatetime()
    return (dt + timedelta(days=7)).strftime("%Y-%m-%dT12:00:00")


def _pick(*choices: str) -> str:
    """Pick one choice at random — for content variation without logic changes."""
    return random.choice(choices)


def _generate_metrics(significance: float, follower_tier: str) -> PostMetrics:
    tier_mult = FOLLOWER_MULTIPLIERS.get(follower_tier, 0.1)
    base = max(significance * tier_mult, 0.01)
    likes = int(base * random.uniform(800, 12000) * random.uniform(0.7, 1.3))
    retweets = int(likes * random.uniform(0.12, 0.35))
    replies = int(likes * random.uniform(0.02, 0.08))
    views = int(likes * random.uniform(8, 20))
    return PostMetrics(likes=likes, retweets=retweets, replies=replies, views=views)


def _row_to_dict(row) -> dict:
    """Convert a pandas Series or namedtuple row to a plain dict."""
    if hasattr(row, "to_dict"):
        return row.to_dict()
    if hasattr(row, "_asdict"):
        return row._asdict()
    return dict(row)


def _entries_for_week(weekly_df, week_val) -> list[dict]:
    """Filter weekly DataFrame to rows matching the given week, sorted by rank."""
    subset = weekly_df[weekly_df["billboard_week"] == week_val]
    subset = subset.sort_values("rank")
    return [_row_to_dict(row) for _, row in subset.iterrows()]


def _album_entries_for_week(weekly_album, week_val) -> list[dict]:
    """Filter album weekly DataFrame to rows matching the given week, sorted by rank."""
    subset = weekly_album[weekly_album["billboard_week"] == week_val]
    subset = subset.sort_values("rank")
    return [_row_to_dict(row) for _, row in subset.iterrows()]


def _artist_entries_for_week(weekly_artist, week_val) -> list[dict]:
    """Filter artist weekly DataFrame to rows matching the given week, sorted by rank."""
    subset = weekly_artist[weekly_artist["billboard_week"] == week_val]
    subset = subset.sort_values("rank")
    return [_row_to_dict(row) for _, row in subset.iterrows()]


# ──────────────────── data loading ────────────────────

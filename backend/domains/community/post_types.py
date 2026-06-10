"""Post type definitions — templates, triggers, and significance scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PostType(str, Enum):  # noqa: UP042
    # A. Weekly chart dispatches
    NO1_ANNOUNCEMENT = "no1_announcement"
    TOP10_SUMMARY = "top10_summary"
    NEW_ENTRIES_ROUNDUP = "new_entries_roundup"
    BIGGEST_JUMP = "biggest_jump"

    # B. Records & milestones
    RECORD_BROKEN = "record_broken"
    RECORD_TIED = "record_tied"
    RECORD_WATCH = "record_watch"
    ARTIST_MILESTONE = "artist_milestone"

    # C. Historical & statistical
    THROWBACK = "throwback"
    ALL_TIME_STATS = "all_time_stats"
    DECADE_COMPARISON = "decade_comparison"

    # D. Personal playback insights
    WEEKLY_PERSONAL = "weekly_personal"
    MONTHLY_PERSONAL = "monthly_personal"
    YEARLY_PERSONAL = "yearly_personal"
    PLAYBACK_MILESTONE = "playback_milestone"

    # E. Collection insights
    COLLECTION_MILESTONE = "collection_milestone"
    COLLECTION_INSIGHT = "collection_insight"
    FORGOTTEN_GEMS = "forgotten_gems"


# Significance base scores: how "news-worthy" each post type is (0–1)
POST_SIGNIFICANCE: dict[PostType, float] = {
    PostType.NO1_ANNOUNCEMENT: 0.85,
    PostType.TOP10_SUMMARY: 0.55,
    PostType.NEW_ENTRIES_ROUNDUP: 0.40,
    PostType.BIGGEST_JUMP: 0.35,
    PostType.RECORD_BROKEN: 1.0,
    PostType.RECORD_TIED: 0.95,
    PostType.RECORD_WATCH: 0.60,
    PostType.ARTIST_MILESTONE: 0.75,
    PostType.THROWBACK: 0.30,
    PostType.ALL_TIME_STATS: 0.50,
    PostType.DECADE_COMPARISON: 0.25,
    PostType.WEEKLY_PERSONAL: 0.30,
    PostType.MONTHLY_PERSONAL: 0.45,
    PostType.YEARLY_PERSONAL: 0.70,
    PostType.PLAYBACK_MILESTONE: 0.55,
    PostType.COLLECTION_MILESTONE: 0.40,
    PostType.COLLECTION_INSIGHT: 0.35,
    PostType.FORGOTTEN_GEMS: 0.20,
}

# Tags for each post type (used for UI filtering)
POST_TAGS: dict[PostType, list[str]] = {
    PostType.NO1_ANNOUNCEMENT: ["weekly", "no1"],
    PostType.TOP10_SUMMARY: ["weekly", "top10", "summary"],
    PostType.NEW_ENTRIES_ROUNDUP: ["weekly", "debut"],
    PostType.BIGGEST_JUMP: ["weekly", "movement"],
    PostType.RECORD_BROKEN: ["record", "milestone"],
    PostType.RECORD_TIED: ["record", "milestone"],
    PostType.RECORD_WATCH: ["record", "watch"],
    PostType.ARTIST_MILESTONE: ["milestone", "artist"],
    PostType.THROWBACK: ["history", "throwback"],
    PostType.ALL_TIME_STATS: ["history", "stat"],
    PostType.DECADE_COMPARISON: ["history", "stat"],
    PostType.WEEKLY_PERSONAL: ["personal", "weekly"],
    PostType.MONTHLY_PERSONAL: ["personal", "monthly"],
    PostType.YEARLY_PERSONAL: ["personal", "yearly"],
    PostType.PLAYBACK_MILESTONE: ["personal", "milestone"],
    PostType.COLLECTION_MILESTONE: ["collection", "milestone"],
    PostType.COLLECTION_INSIGHT: ["collection", "insight"],
    PostType.FORGOTTEN_GEMS: ["collection", "insight"],
}


@dataclass
class PostMetrics:
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0


@dataclass
class CommunityPost:
    id: str
    account_handle: str
    posted_at: str  # ISO datetime
    content: str
    post_type: str
    attached_list: list | None = None
    linked_entities: list[dict] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    metrics: PostMetrics | None = None
    tags: list[str] = field(default_factory=list)
    significance: float = 0.0

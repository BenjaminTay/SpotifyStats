"""Community feed API endpoint."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import PlayFilters, get_conn
from backend.domains.community.feed_generator import generate_all_posts
from backend.domains.community.post_types import HIGHLIGHT_POST_TYPES

router = APIRouter(prefix="/community", tags=["Community"])


class FeedMeta(BaseModel):
    total: int
    total_all: int
    returned: int
    offset: int
    limit: int


class CommunityFeedResponse(BaseModel):
    model_config = {"extra": "allow"}
    meta: FeedMeta
    posts: list[dict]


@router.get("/feed", response_model=CommunityFeedResponse)
def get_community_feed(
    accounts: str | None = Query(default=None, description="Comma-separated handles to filter by"),
    tags: str | None = Query(default=None, description="Comma-separated tags to filter by"),
    highlights_only: bool = Query(
        default=False, description="Show only newsworthy posts (no routine summaries)"
    ),
    significance_min: float = Query(
        default=0.0, ge=0.0, le=1.0, description="Minimum significance threshold"
    ),
    date_from: str | None = Query(default=None, description="ISO date lower bound"),
    date_to: str | None = Query(default=None, description="ISO date upper bound"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Get the community feed — simulated X-style posts from chart data.

    Posts are generated with historical accuracy: each post only references
    knowledge available at its point in time.

    Filter by accounts, tags, date range, significance threshold,
    or use highlights_only for newsworthy posts only.
    """
    all_posts = generate_all_posts(
        conn=conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
    )

    # Apply filters — track both totals (with and without highlights filter)
    account_set = set(a.strip() for a in accounts.split(",") if a.strip()) if accounts else None
    tag_set = set(t.strip() for t in tags.split(",") if t.strip()) if tags else None

    filtered = []
    total_all = 0
    for p in all_posts:
        if account_set and p.account_handle not in account_set:
            continue
        if tag_set and not tag_set.intersection(p.tags):
            continue
        if date_from and p.posted_at < date_from:
            continue
        if date_to and p.posted_at > date_to:
            continue
        if p.significance < significance_min:
            continue
        total_all += 1
        if not highlights_only or p.post_type in HIGHLIGHT_POST_TYPES:
            filtered.append(p)

    page = filtered[offset : offset + limit]

    # Serialize to dicts (dataclass -> dict, handle nested objects)
    posts_json = []
    for p in page:
        d = {
            "id": p.id,
            "account_handle": p.account_handle,
            "posted_at": p.posted_at,
            "content": p.content,
            "post_type": p.post_type,
            "attached_list": p.attached_list,
            "linked_entities": p.linked_entities,
            "images": p.images,
            "metrics": {
                "likes": p.metrics.likes if p.metrics else 0,
                "retweets": p.metrics.retweets if p.metrics else 0,
                "replies": p.metrics.replies if p.metrics else 0,
                "views": p.metrics.views if p.metrics else 0,
            },
            "tags": p.tags,
            "significance": p.significance,
        }
        posts_json.append(d)

    return CommunityFeedResponse(
        meta=FeedMeta(
            total=len(filtered),
            total_all=total_all,
            returned=len(posts_json),
            offset=offset,
            limit=limit,
        ),
        posts=posts_json,
    )

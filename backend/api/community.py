"""Community feed API endpoint."""

# ruff: noqa: UP045

from __future__ import annotations

from sqlite3 import Connection
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import PlayFilters, get_conn
from backend.domains.community.feed_generator import generate_all_posts
from backend.domains.community.post_types import HIGHLIGHT_POST_TYPES, CommunityPost

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


class TrendingItem(BaseModel):
    name: str
    count: int
    entity_id: Optional[str | int] = None


class TrendingResponse(BaseModel):
    artists: list[TrendingItem]
    tracks: list[TrendingItem]
    latest_no1: Optional[dict] = None
    latest_debut: Optional[dict] = None


# ── Post Detail response models ──────────────────────────────────────────────


class PostMetrics(BaseModel):
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0


class PostItem(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    account_handle: str
    posted_at: str
    content: str
    post_type: str
    metrics: PostMetrics
    tags: list[str] = []
    significance: float = 0.0
    attached_list: Optional[list] = None
    linked_entities: Optional[list] = None
    images: Optional[list] = None


class PostDetailResponse(BaseModel):
    post: PostItem
    replies: list[PostItem]


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
    search: str | None = Query(
        default=None, description="Search post content, handles, and linked entity names"
    ),
    post_types: str | None = Query(
        default=None, description="Comma-separated post type values to filter by"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Get the community feed — simulated X-style posts from chart data.

    Posts are generated with historical accuracy: each post only references
    knowledge available at its point in time.

    Filter by accounts, tags, date range, significance threshold, search keywords,
    post types, or use highlights_only for newsworthy posts only.
    """
    all_posts = generate_all_posts(
        conn=conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
    )

    # Apply filters — track both totals (with and without highlights filter)
    account_set = set(a.strip() for a in accounts.split(",") if a.strip()) if accounts else None
    tag_set = set(t.strip() for t in tags.split(",") if t.strip()) if tags else None
    post_type_set = (
        set(p.strip() for p in post_types.split(",") if p.strip()) if post_types else None
    )
    search_lower = search.lower() if search else None

    filtered = []
    total_all = 0
    for p in all_posts:
        if account_set and p.account_handle not in account_set:
            continue
        if tag_set and not tag_set.intersection(p.tags):
            continue
        if post_type_set and p.post_type not in post_type_set:
            continue
        if date_from and p.posted_at < date_from:
            continue
        if date_to and p.posted_at > date_to:
            continue
        if p.significance < significance_min:
            continue
        if search_lower:
            content_match = search_lower in p.content.lower()
            handle_match = search_lower in p.account_handle.lower()
            entity_match = any(
                search_lower in e.get("name", "").lower() for e in (p.linked_entities or [])
            )
            if not (content_match or handle_match or entity_match):
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


@router.get("/trending", response_model=TrendingResponse)
def get_community_trending(
    date_from: str | None = Query(default=None, description="ISO date lower bound"),
    date_to: str | None = Query(default=None, description="ISO date upper bound"),
    artist_limit: int = Query(default=6, ge=1, le=20),
    track_limit: int = Query(default=3, ge=1, le=20),
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Get trending entities computed over ALL community posts (not just current page).

    Returns top mentioned artists, tracks, latest #1, and latest debut.
    """
    all_posts = generate_all_posts(
        conn=conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
    )

    # Date filter
    if date_from or date_to:
        filtered = []
        for p in all_posts:
            if date_from and p.posted_at < date_from:
                continue
            if date_to and p.posted_at > date_to:
                continue
            filtered.append(p)
        posts = filtered
    else:
        posts = all_posts

    # Count entity mentions
    artist_counts: dict[str, int] = {}
    track_counts: dict[str, int] = {}
    track_to_id: dict[str, str | int] = {}
    latest_no1_post: CommunityPost | None = None
    latest_debut_post: CommunityPost | None = None

    for p in posts:
        # Track latest #1 and debut for quick-reference
        if latest_no1_post is None and p.post_type == "no1_announcement":
            latest_no1_post = p
        if latest_debut_post is None and p.post_type == "debut":
            latest_debut_post = p

        if not p.linked_entities:
            continue
        for e in p.linked_entities:
            name = e.get("name", "")
            if not name:
                continue
            if e.get("type") == "artist":
                artist_counts[name] = artist_counts.get(name, 0) + 1
            elif e.get("type") == "track":
                track_counts[name] = track_counts.get(name, 0) + 1
                if e.get("id") and name not in track_to_id:
                    track_to_id[name] = e["id"]

    # Sort and limit
    top_artists = sorted(artist_counts.items(), key=lambda x: x[1], reverse=True)[:artist_limit]
    top_tracks = sorted(track_counts.items(), key=lambda x: x[1], reverse=True)[:track_limit]

    # Latest #1 info
    latest_no1_data = None
    if latest_no1_post:
        track = next(
            (e for e in (latest_no1_post.linked_entities or []) if e.get("type") == "track"), None
        )
        artist = next(
            (e for e in (latest_no1_post.linked_entities or []) if e.get("type") == "artist"), None
        )
        latest_no1_data = {
            "track": track.get("name") if track else None,
            "artist": artist.get("name") if artist else None,
            "post_id": latest_no1_post.id,
        }

    latest_debut_data = None
    if latest_debut_post:
        track = next(
            (e for e in (latest_debut_post.linked_entities or []) if e.get("type") == "track"), None
        )
        artist = next(
            (e for e in (latest_debut_post.linked_entities or []) if e.get("type") == "artist"),
            None,
        )
        latest_debut_data = {
            "track": track.get("name") if track else None,
            "artist": artist.get("name") if artist else None,
            "post_id": latest_debut_post.id,
        }

    return TrendingResponse(
        artists=[TrendingItem(name=n, count=c) for n, c in top_artists],
        tracks=[TrendingItem(name=n, count=c, entity_id=track_to_id.get(n)) for n, c in top_tracks],
        latest_no1=latest_no1_data,
        latest_debut=latest_debut_data,
    )


@router.get("/post/{post_id}", response_model=PostDetailResponse)
def get_community_post(
    post_id: str,
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Get a single community post by ID, with simulated related replies."""

    all_posts = generate_all_posts(
        conn=conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
    )

    target = None
    for p in all_posts:
        if p.id == post_id:
            target = p
            break

    if not target:
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "Post not found"}, status_code=404)

    # Generate simulated replies: 2-4 posts from other accounts that mention
    # the same entities, posted around the same time
    replies = []
    target_date = target.posted_at[:10]  # YYYY-MM-DD
    seen_handles = {target.account_handle}
    for p in all_posts:
        if p.posted_at[:10] == target_date and p.account_handle not in seen_handles:
            if p.linked_entities and target.linked_entities:
                common = any(
                    any(e2.get("name") == e1.get("name") for e2 in p.linked_entities)
                    for e1 in target.linked_entities
                )
                if common:
                    replies.append(p)
                    seen_handles.add(p.account_handle)
            if len(replies) >= 4:
                break

    # Serialize target
    d = {
        "id": target.id,
        "account_handle": target.account_handle,
        "posted_at": target.posted_at,
        "content": target.content,
        "post_type": target.post_type,
        "attached_list": target.attached_list,
        "linked_entities": target.linked_entities,
        "images": target.images,
        "metrics": {
            "likes": target.metrics.likes if target.metrics else 0,
            "retweets": target.metrics.retweets if target.metrics else 0,
            "replies": target.metrics.replies if target.metrics else 0,
            "views": target.metrics.views if target.metrics else 0,
        },
        "tags": target.tags,
        "significance": target.significance,
    }

    # Serialize replies
    replies_json = []
    for rp in replies:
        replies_json.append(
            {
                "id": rp.id,
                "account_handle": rp.account_handle,
                "posted_at": rp.posted_at,
                "content": rp.content,
                "post_type": rp.post_type,
                "linked_entities": rp.linked_entities,
                "images": rp.images,
                "metrics": {
                    "likes": rp.metrics.likes if rp.metrics else 0,
                    "retweets": rp.metrics.retweets if rp.metrics else 0,
                    "replies": rp.metrics.replies if rp.metrics else 0,
                    "views": rp.metrics.views if rp.metrics else 0,
                },
                "tags": rp.tags,
                "significance": rp.significance,
            }
        )

    return {"post": d, "replies": replies_json}

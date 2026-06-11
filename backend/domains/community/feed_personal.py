"""Community feed — Personal playback and collection posts."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from backend.domains.community.feed_helpers import (
    _make_id,
    _pick,
)
from backend.domains.community.historical_state import HistoricalState
from backend.domains.community.post_types import (
    POST_SIGNIFICANCE,
    POST_TAGS,
    CommunityPost,
    PostType,
)

# ──────────────────────────────────────────────


def _gen_throwback_post(
    state: HistoricalState, all_weeks: list, posted_at: str, week_label: str
) -> CommunityPost | None:
    """@throwbackcharts: on-this-day style post (look back 1 year)."""
    try:
        current_dt = pd.Timestamp(week_label)
    except Exception:
        return None

    # Find the closest week from 1 year ago
    target = current_dt - pd.DateOffset(years=1)
    best_week = None
    for w in all_weeks:
        w_ts = pd.Timestamp(w)
        if w_ts <= target:
            best_week = w
        else:
            break

    if best_week is None:
        return None

    past_entry = state.get_past_no1_at_week(str(best_week))
    if not past_entry:
        return None

    year = pd.Timestamp(best_week).year
    opener = _pick(
        f"On this week in {year}:",
        f"A year ago this week ({year}):",
        f"Throwback to {year}:",
        f"Flashback to this week in {year}:",
    )
    content = (
        f"{opener} '{past_entry['track_name']}' by "
        f"{past_entry['artist_name']} was #1 on the Hot 100."
    )
    return CommunityPost(
        id=_make_id("throwback", week_label, str(year)),
        account_handle="@throwbackcharts",
        posted_at=posted_at,
        content=content,
        post_type=PostType.THROWBACK.value,
        linked_entities=[
            {"type": "track", "id": past_entry.get("track_id"), "name": past_entry["track_name"]},
            {"type": "artist", "name": past_entry["artist_name"]},
        ],
        tags=POST_TAGS[PostType.THROWBACK],
        significance=POST_SIGNIFICANCE[PostType.THROWBACK],
    )


def _gen_weekly_personal(
    week_label: str, personal: dict, state: HistoricalState, posted_at: str
) -> CommunityPost | None:
    """@spotifystats: weekly personal listening summary."""
    if not personal or personal.get("plays", 0) == 0:
        return None

    plays = personal["plays"]
    hours = personal["ms"] / 3600000
    artist_count = len(personal.get("artist_names", set()))
    top_artist = personal.get("top_artist", "")
    top_plays = personal.get("top_artist_plays", 0)
    new_tracks_this_week = len(personal.get("track_ids", set()) - state.cumulative_tracks)

    opener = _pick(
        f"This week you played {plays} songs ({hours:.1f}h) by {artist_count} artists.",
        f"Your week in listening: {plays} songs ({hours:.1f}h) across {artist_count} artists.",
    )
    topper = _pick(
        f"Your top artist was {top_artist} ({top_plays} plays).",
        f"You played {top_artist} the most ({top_plays} spins).",
        f"{top_artist} led your week with {top_plays} plays.",
    )
    parts = [opener, topper]
    if new_tracks_this_week > 5:
        disc = _pick(
            f"You discovered {new_tracks_this_week} new tracks this week.",
            f"{new_tracks_this_week} new tracks entered your rotation.",
        )
        parts.append(disc)

    return CommunityPost(
        id=_make_id("personal", "weekly", week_label),
        account_handle="@spotifystats",
        posted_at=posted_at,
        content=" ".join(parts),
        post_type=PostType.WEEKLY_PERSONAL.value,
        tags=POST_TAGS[PostType.WEEKLY_PERSONAL],
        significance=POST_SIGNIFICANCE[PostType.WEEKLY_PERSONAL],
    )


def _gen_monthly_personal(
    month_label: str, posts_by_month: list, state_snapshot: HistoricalState, posted_at: str
) -> CommunityPost | None:
    """@spotifystats: monthly listening summary."""
    if not posts_by_month:
        return None
    total_plays = state_snapshot.cumulative_plays
    total_hours = state_snapshot.cumulative_ms / 3600000
    track_count = len(state_snapshot.cumulative_tracks)
    artist_count = len(state_snapshot.cumulative_artists)

    opener = _pick(
        f"Your {month_label} in music:",
        f"{month_label} listening recap:",
        f"A look back at {month_label}:",
    )
    content = (
        f"{opener} {total_plays:,} plays, {total_hours:.0f}h listening, "
        f"{track_count} tracks, {artist_count} artists."
    )
    return CommunityPost(
        id=_make_id("personal", "monthly", month_label),
        account_handle="@spotifystats",
        posted_at=posted_at,
        content=content,
        post_type=PostType.MONTHLY_PERSONAL.value,
        tags=POST_TAGS[PostType.MONTHLY_PERSONAL],
        significance=POST_SIGNIFICANCE[PostType.MONTHLY_PERSONAL],
    )


def _gen_quarterly_personal(
    quarter_label: str, state_snapshot: HistoricalState, posted_at: str
) -> CommunityPost:
    """@spotifystats: quarterly listening recap."""
    total_plays = state_snapshot.cumulative_plays
    total_hours = state_snapshot.cumulative_ms / 3600000
    track_count = len(state_snapshot.cumulative_tracks)
    artist_count = len(state_snapshot.cumulative_artists)

    opener = _pick(
        f"Your {quarter_label} in music:",
        f"{quarter_label} recap:",
        f"A look back at {quarter_label}:",
    )
    content = (
        f"{opener} {total_plays:,} plays, {total_hours:.0f}h listening, "
        f"{track_count} tracks, {artist_count} artists."
    )
    return CommunityPost(
        id=_make_id("personal", "quarterly", quarter_label),
        account_handle="@spotifystats",
        posted_at=posted_at,
        content=content,
        post_type=PostType.QUARTERLY_PERSONAL.value,
        tags=POST_TAGS[PostType.QUARTERLY_PERSONAL],
        significance=POST_SIGNIFICANCE[PostType.QUARTERLY_PERSONAL],
    )


def _gen_collection_posts(collection_data: dict, state: HistoricalState) -> list[CommunityPost]:
    """@collectionvault: collection-related insights."""
    posts: list[CommunityPost] = []
    total = collection_data.get("total_saved", 0)
    if total == 0:
        return posts

    # Collection milestone
    if total >= 100:
        first = collection_data.get("first_save")
        first_line = ""
        if first:
            first_line = f" Your first saved track was '{first['track_name']}' by {first['artist_name']} ({first['added_date']})."
        content = (
            f"Your library has {total} saved tracks across {len(state.cumulative_artists)} artists. "
            f"Total listening time: {state.cumulative_ms / 3600000:.0f} hours." + first_line
        )
        posts.append(
            CommunityPost(
                id=_make_id("collection", "overview"),
                account_handle="@collectionvault",
                posted_at=datetime.now().strftime("%Y-%m-%dT12:00:00"),
                content=content,
                post_type=PostType.COLLECTION_INSIGHT.value,
                tags=POST_TAGS[PostType.COLLECTION_INSIGHT],
                significance=POST_SIGNIFICANCE[PostType.COLLECTION_INSIGHT],
            )
        )

    # Forgotten gems
    forgotten = collection_data.get("forgotten", [])
    if len(forgotten) >= 5:
        header = _pick(
            f"You have {len(forgotten)} saved tracks you haven't played yet:",
            f"{len(forgotten)} saved tracks waiting to be discovered:",
            f"Forgotten gems — {len(forgotten)} saved but unplayed tracks:",
        )
        lines = [header, ""]
        for f in forgotten[:10]:
            lines.append(f"'{f['track_name']}' — {f['artist_name']} (saved {f['added_date']})")
        posts.append(
            CommunityPost(
                id=_make_id("collection", "forgotten"),
                account_handle="@collectionvault",
                posted_at=datetime.now().strftime("%Y-%m-%dT12:00:00"),
                content="\n".join(lines),
                post_type=PostType.FORGOTTEN_GEMS.value,
                tags=POST_TAGS[PostType.FORGOTTEN_GEMS],
                significance=POST_SIGNIFICANCE[PostType.FORGOTTEN_GEMS],
            )
        )

    return posts


def _gen_playback_milestone(
    state: HistoricalState,
    prev_plays: int,
    prev_hours: float,
    prev_tracks: int,
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@spotifystats: personal playback milestones (10K plays, 1K hours, etc.).

    Detects when cumulative stats cross a threshold this week by comparing
    current cumulative values against the previous week's values."""
    current_plays = state.cumulative_plays
    current_hours = state.cumulative_ms / 3600000
    current_tracks = len(state.cumulative_tracks)

    hits = []

    for threshold in [5000, 10000, 25000, 50000, 100000]:
        if prev_plays < threshold <= current_plays:
            hits.append(f"{threshold:,} plays")
            break
    for threshold in [500, 1000, 2500, 5000, 10000]:
        if prev_hours < threshold <= current_hours:
            hits.append(f"{threshold:,} hours of listening")
            break
    for threshold in [500, 1000, 2500, 5000]:
        if prev_tracks < threshold <= current_tracks:
            hits.append(f"{threshold:,} unique tracks")
            break

    if not hits:
        return None

    label = _pick("MILESTONE:", "PERSONAL RECORD:", "ACHIEVEMENT UNLOCKED:")
    content = f"{label} You've reached {hits[0]}!"
    if len(hits) > 1:
        content = f"{label} You've reached {', '.join(hits[:-1])} and {hits[-1]}!"

    return CommunityPost(
        id=_make_id("personal", "milestone", week_label),
        account_handle="@spotifystats",
        posted_at=posted_at,
        content=content,
        post_type=PostType.PLAYBACK_MILESTONE.value,
        tags=POST_TAGS[PostType.PLAYBACK_MILESTONE],
        significance=POST_SIGNIFICANCE[PostType.PLAYBACK_MILESTONE],
    )


# ──────────────── @talkofthecharts — deep stats & analysis ────────────────


def _gen_yearly_personal(
    year_label: str,
    state_snapshot: HistoricalState,
    prev_year_snapshot: HistoricalState | None,
    posted_at: str,
) -> CommunityPost | None:
    """@spotifystats: yearly personal listening recap."""
    plays = state_snapshot.cumulative_plays
    hours = state_snapshot.cumulative_ms / 3600000
    tracks = len(state_snapshot.cumulative_tracks)
    artists = len(state_snapshot.cumulative_artists)

    if plays == 0:
        return None

    opener = _pick(
        f"Your {year_label} in music:",
        f"{year_label} wrapped:",
        f"A year in review — {year_label}:",
    )
    parts = [
        opener,
        f"{plays:,} plays across {hours:,.0f} hours.",
        f"{tracks:,} unique tracks by {artists:,} artists.",
    ]

    if prev_year_snapshot and prev_year_snapshot.cumulative_ms > 0:
        prev_hours = prev_year_snapshot.cumulative_ms / 3600000
        delta = hours - prev_hours
        if delta > 0:
            pct = (delta / prev_hours) * 100
            verb = _pick("Listening up", "Listening increased")
            parts.append(f"{verb} {pct:.0f}% vs {int(year_label) - 1}.")
        elif delta < 0:
            pct = (abs(delta) / prev_hours) * 100
            verb = _pick("Listening down", "Listening decreased")
            parts.append(f"{verb} {pct:.0f}% vs {int(year_label) - 1}.")

    return CommunityPost(
        id=_make_id("personal", "yearly", year_label),
        account_handle="@spotifystats",
        posted_at=posted_at,
        content=" ".join(parts),
        post_type=PostType.YEARLY_PERSONAL.value,
        tags=POST_TAGS[PostType.YEARLY_PERSONAL],
        significance=POST_SIGNIFICANCE[PostType.YEARLY_PERSONAL],
    )


def _gen_decade_comparison(
    state: HistoricalState, all_weeks: list, posted_at: str
) -> CommunityPost | None:
    """@chartstats: decade/era comparison post — generated once at the end."""
    if not all_weeks or not state.past_no1s:
        return None

    try:
        first_week = pd.Timestamp(all_weeks[0])
        last_week = pd.Timestamp(all_weeks[-1])
    except Exception:
        return None

    total_no1s = len({p["track_id"] for p in state.past_no1s if p.get("track_id")})
    total_artists_no1 = len({p["artist_name"] for p in state.past_no1s})
    span_years = max((last_week - first_week).days / 365.25, 0.5)

    opener = _pick(
        f"Chart Era in Review ({first_week.strftime('%b %Y')} — {last_week.strftime('%b %Y')}):",
        f"A look back at the chart era ({first_week.strftime('%b %Y')} — {last_week.strftime('%b %Y')}):",
        f"The {first_week.strftime('%b %Y')}–{last_week.strftime('%b %Y')} era by the numbers:",
    )
    content = (
        f"{opener} "
        f"{total_no1s} different #1 hits by {total_artists_no1} artists over {span_years:.1f} years. "
        f"The longest-running #1 was '{state.longest_no1_track_name}' "
        f"by {state.longest_no1_artist_name} ({state.longest_no1_weeks} weeks)."
    )

    return CommunityPost(
        id=_make_id("stat", "decade", "summary"),
        account_handle="@chartstats",
        posted_at=posted_at,
        content=content,
        post_type=PostType.DECADE_COMPARISON.value,
        tags=POST_TAGS[PostType.DECADE_COMPARISON],
        significance=POST_SIGNIFICANCE[PostType.DECADE_COMPARISON],
    )


def _gen_collection_milestone(collection_data: dict, state: HistoricalState) -> list[CommunityPost]:
    """@collectionvault: collection milestone posts."""
    posts: list[CommunityPost] = []
    total = collection_data.get("total_saved", 0)

    milestones = []
    for threshold in [100, 250, 500, 1000, 2000, 5000]:
        if total >= threshold:
            milestones.append(threshold)
    if not milestones:
        return posts

    best = milestones[-1]
    label = _pick("MILESTONE:", "COLLECTION MILESTONE:", "LIBRARY UPDATE:")
    content = (
        f"{label} Your saved tracks library has reached {best:,} tracks! "
        f"That's {best / max(len(state.cumulative_artists), 1):.0f} tracks per artist on average "
        f"across {len(state.cumulative_artists):,} artists."
    )
    posts.append(
        CommunityPost(
            id=_make_id("collection", "milestone", str(best)),
            account_handle="@collectionvault",
            posted_at=datetime.now().strftime("%Y-%m-%dT12:00:00"),
            content=content,
            post_type=PostType.COLLECTION_MILESTONE.value,
            tags=POST_TAGS[PostType.COLLECTION_MILESTONE],
            significance=POST_SIGNIFICANCE[PostType.COLLECTION_MILESTONE],
        )
    )

    return posts

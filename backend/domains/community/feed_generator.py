"""Community feed generator — iterates chart weeks chronologically and generates
simulated X-style posts from real data while maintaining historical accuracy."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta

import pandas as pd

from backend.core.cache import ttl_cached
from backend.domains.billboard.chart_ranking import (
    compute_album_weekly_rankings,
    compute_artist_weekly_rankings,
    compute_weekly_rankings,
)
from backend.domains.billboard.data_loader import (
    _try_load_from_agg,
    load_billboard_raw,
    load_billboard_raw_for_artists,
)
from backend.domains.community.accounts import ACCOUNT_BY_HANDLE, FOLLOWER_MULTIPLIERS
from backend.domains.community.historical_state import HistoricalState
from backend.domains.community.post_types import (
    POST_SIGNIFICANCE,
    POST_TAGS,
    CommunityPost,
    PostMetrics,
    PostType,
)

# ────────────────────────── helpers ──────────────────────────


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


def _load_chart_data(
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Load raw data and compute all three weekly rankings. Returns a 5-tuple."""
    df_raw = load_billboard_raw(min_ms, music_only, bb_week_start_dow, bb_week_start_hour)
    df_raw = df_raw.copy()
    df_raw["_year"] = df_raw["billboard_week"].apply(lambda x: x.year)
    if year_start is not None:
        df_raw = df_raw[df_raw["_year"] >= year_start]
    if year_end is not None:
        df_raw = df_raw[df_raw["_year"] <= year_end]

    all_weeks = sorted(df_raw["billboard_week"].unique().tolist())

    _agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(
        min_ms, music_only, bb_week_start_dow, bb_week_start_hour
    )
    if _agg_tracks is not None:
        _agg_tracks = _agg_tracks[
            pd.to_datetime(_agg_tracks["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_albums = _agg_albums[
            pd.to_datetime(_agg_albums["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_artists = _agg_artists[
            pd.to_datetime(_agg_artists["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]

    weekly = compute_weekly_rankings(df_raw, bb_top_n, pre_agg=_agg_tracks)
    weekly_album = compute_album_weekly_rankings(df_raw, bb_album_top_n, pre_agg=_agg_albums)
    if _agg_artists is not None:
        weekly_artist = compute_artist_weekly_rankings(
            df_raw, bb_artist_top_n, pre_agg=_agg_artists
        )
    else:
        df_artists = load_billboard_raw_for_artists(
            min_ms, music_only, bb_week_start_dow, bb_week_start_hour
        )
        weekly_artist = compute_artist_weekly_rankings(df_artists, bb_artist_top_n)

    return df_raw, weekly, weekly_album, weekly_artist, all_weeks


def _compute_personal_weekly(df_raw) -> dict:
    """Compute per-week personal playback stats from raw plays data.

    Returns dict: {week_val: {plays, ms, track_ids: set, artist_names: set,
                               top_artist, top_artist_plays}}
    """
    personal = {}
    for week_val, grp in df_raw.groupby("billboard_week"):
        artist_counts = grp.groupby("artist_name").size()
        top_artist = artist_counts.idxmax() if len(artist_counts) > 0 else ""
        top_artist_plays = int(artist_counts.max()) if len(artist_counts) > 0 else 0

        personal[week_val] = {
            "plays": len(grp),
            "ms": int(grp["ms_played"].sum()),
            "track_ids": set(grp["track_id"].unique()),
            "artist_names": set(grp["artist_name"].unique()),
            "top_artist": top_artist,
            "top_artist_plays": top_artist_plays,
        }
    return personal


def _load_collection_data(conn) -> dict:
    """Load saved tracks data for collection-related posts."""
    try:
        rows = conn.execute(
            "SELECT track_name, artist_name, added_date FROM saved_tracks ORDER BY added_date"
        ).fetchall()
        saved = [{"track_name": r[0], "artist_name": r[1], "added_date": r[2]} for r in rows]

        total_saved = len(saved)
        first_save = saved[0] if saved else None

        # Count forgotten tracks: saved but never played (check against plays table)
        forgotten_rows = conn.execute("""
            SELECT st.track_name, st.artist_name, st.added_date
            FROM saved_tracks st
            WHERE st.track_name NOT IN (
                SELECT DISTINCT p.track_name FROM plays p WHERE p.track_name IS NOT NULL
            )
            ORDER BY st.added_date
        """).fetchall()
        forgotten = [
            {"track_name": r[0], "artist_name": r[1], "added_date": r[2]} for r in forgotten_rows
        ]

        return {
            "total_saved": total_saved,
            "first_save": first_save,
            "forgotten": forgotten,
            "forgotten_count": len(forgotten),
        }
    except Exception:
        return {"total_saved": 0, "first_save": None, "forgotten": [], "forgotten_count": 0}


# ──────────────── post generators (per type) ────────────────


def _gen_no1_posts(
    week_entries: list[dict], state: HistoricalState, posted_at: str, week_label: str
) -> list[CommunityPost]:
    """Generate #1 announcement posts from @chartdata."""
    posts = []
    no1s = [e for e in week_entries if e.get("rank") == 1]
    for entry in no1s:
        track_name = entry.get("track_name", "")
        artist_name = entry.get("artist_name", "")
        track_id = entry.get("track_id")
        is_new = track_id and state.track_weeks_at_no1.get(track_id, 0) == 0

        if is_new:
            nth = state.artist_ordinal_no1(artist_name)
            content = f"Hot 100: #1(new) {track_name}, {artist_name}."
            if state.artist_no1_count_as_of(artist_name) >= 2:
                content += f" It becomes {artist_name}'s {nth} #1 on the chart."
            else:
                content += f" This is {artist_name}'s first #1 on the Hot 100."
            significance = POST_SIGNIFICANCE[PostType.NO1_ANNOUNCEMENT]
        else:
            consecutive = state.track_weeks_at_no1_as_of(track_id or 0)
            content = f"Hot 100: #1(=) {track_name}, {artist_name} ({_fmt_ordinal(consecutive + 1)} week)."
            significance = POST_SIGNIFICANCE[PostType.NO1_ANNOUNCEMENT] * 0.7

        post = CommunityPost(
            id=_make_id("no1", week_label, str(track_id)),
            account_handle="@chartdata",
            posted_at=posted_at,
            content=content,
            post_type=PostType.NO1_ANNOUNCEMENT.value,
            linked_entities=[
                {"type": "track", "id": track_id, "name": track_name},
                {"type": "artist", "name": artist_name},
            ],
            tags=POST_TAGS[PostType.NO1_ANNOUNCEMENT],
            significance=significance,
        )
        posts.append(post)
    return posts


def _gen_top10_summary(
    week_entries: list[dict], state: HistoricalState, posted_at: str, week_label: str
) -> CommunityPost | None:
    """@billboardcharts: full top 10 list."""
    top10 = [e for e in week_entries if e.get("rank", 999) <= 10]
    if not top10:
        return None

    lines = [f"This week's top 10 on the Hot 100 (chart dated {week_label}):", ""]
    for e in top10:
        rank = e.get("rank", "?")
        track = e.get("track_name", "")
        artist = e.get("artist_name", "")
        lines.append(f"{rank}. {track} — {artist}")

    return CommunityPost(
        id=_make_id("top10", week_label),
        account_handle="@billboardcharts",
        posted_at=posted_at,
        content="\n".join(lines),
        post_type=PostType.TOP10_SUMMARY.value,
        tags=POST_TAGS[PostType.TOP10_SUMMARY],
        significance=POST_SIGNIFICANCE[PostType.TOP10_SUMMARY],
    )


def _gen_debut_posts(
    week_entries: list[dict], state: HistoricalState, posted_at: str, week_label: str
) -> list[CommunityPost]:
    """@debutwatch: high debut announcements (top 20 debuts)."""
    posts = []
    debuts = [
        e
        for e in week_entries
        if e.get("rank", 999) <= 20
        and e.get("track_id")
        and e["track_id"] not in state.track_debut_week
    ]
    if len(debuts) >= 2:
        # Post about multiple notable debuts
        lines = [f"Notable new entries on the Hot 100 this week ({week_label}):", ""]
        entities = []
        seen_artists = set()
        for d in sorted(debuts, key=lambda x: x.get("rank", 999))[:8]:
            lines.append(f"#{d['rank']} {d.get('track_name', '')} — {d.get('artist_name', '')}")
            entities.append(
                {
                    "type": "track",
                    "id": d.get("track_id"),
                    "name": d.get("track_name", ""),
                }
            )
            artist_name = d.get("artist_name", "")
            if artist_name and artist_name not in seen_artists:
                seen_artists.add(artist_name)
                entities.append({"type": "artist", "name": artist_name})
        post = CommunityPost(
            id=_make_id("debuts", week_label),
            account_handle="@debutwatch",
            posted_at=posted_at,
            content="\n".join(lines),
            post_type=PostType.NEW_ENTRIES_ROUNDUP.value,
            linked_entities=entities,
            tags=POST_TAGS[PostType.NEW_ENTRIES_ROUNDUP],
            significance=POST_SIGNIFICANCE[PostType.NEW_ENTRIES_ROUNDUP],
        )
        posts.append(post)
    elif len(debuts) == 1:
        d = debuts[0]
        content = f"Hot 100 debut: #{d['rank']} {d.get('track_name', '')} by {d.get('artist_name', '')} enters the chart this week."
        single_entities = [
            {"type": "track", "id": d.get("track_id"), "name": d.get("track_name", "")},
        ]
        if d.get("artist_name"):
            single_entities.append({"type": "artist", "name": d.get("artist_name", "")})
        post = CommunityPost(
            id=_make_id("debut", week_label),
            account_handle="@debutwatch",
            posted_at=posted_at,
            content=content,
            post_type=PostType.NEW_ENTRIES_ROUNDUP.value,
            linked_entities=single_entities,
            tags=POST_TAGS[PostType.NEW_ENTRIES_ROUNDUP],
            significance=POST_SIGNIFICANCE[PostType.NEW_ENTRIES_ROUNDUP] * 0.6,
        )
        posts.append(post)
    return posts


def _gen_biggest_jump_post(
    week_entries: list[dict], prev_week_entries: list[dict] | None, posted_at: str, week_label: str
) -> CommunityPost | None:
    """@chartdata: biggest rank jump of the week."""
    if not prev_week_entries:
        return None
    prev_map = {
        e.get("track_id"): e.get("rank", 999) for e in prev_week_entries if e.get("track_id")
    }
    best_jump = None
    best_delta = 0
    for e in week_entries:
        tid = e.get("track_id")
        if tid and tid in prev_map:
            delta = prev_map[tid] - e.get("rank", 999)
            if delta > best_delta:
                best_delta = delta
                best_jump = e
    if best_jump and best_delta >= 10:
        content = (
            f"Biggest jump this week: {best_jump.get('track_name', '')} by {best_jump.get('artist_name', '')} "
            f"rockets {prev_map[best_jump['track_id']]}-{best_jump['rank']} (+{best_delta} spots)."
        )
        return CommunityPost(
            id=_make_id("jump", week_label, str(best_jump.get("track_id"))),
            account_handle="@chartdata",
            posted_at=posted_at,
            content=content,
            post_type=PostType.BIGGEST_JUMP.value,
            linked_entities=[
                {
                    "type": "track",
                    "id": best_jump.get("track_id"),
                    "name": best_jump.get("track_name", ""),
                },
                {"type": "artist", "name": best_jump.get("artist_name", "")},
            ],
            tags=POST_TAGS[PostType.BIGGEST_JUMP],
            significance=POST_SIGNIFICANCE[PostType.BIGGEST_JUMP] * min(best_delta / 30, 1.0),
        )
    return None


def _gen_record_posts(
    week_entries: list[dict], state: HistoricalState, posted_at: str, week_label: str
) -> list[CommunityPost]:
    """@recordwatch: record broken or tied posts."""
    posts = []
    # Check for longest #1 record
    for e in week_entries:
        tid = e.get("track_id")
        if tid and e.get("rank") == 1:
            wks = state.track_weeks_at_no1_as_of(tid)
            track_name = e.get("track_name", "")
            artist_name = e.get("artist_name", "")

            # Record just broken
            if wks > 1 and wks == state.longest_no1_weeks and wks > 0:
                prev_record = state.longest_no1_weeks - 1 if state.longest_no1_weeks > 1 else 0
                if prev_record > 0:
                    content = (
                        f"RECORD: {artist_name}'s '{track_name}' now holds the longest #1 run "
                        f"of the current era ({wks} weeks). The previous best was {prev_record} weeks."
                    )
                    posts.append(
                        CommunityPost(
                            id=_make_id("record", "longest_no1", week_label),
                            account_handle="@recordwatch",
                            posted_at=posted_at,
                            content=content,
                            post_type=PostType.RECORD_BROKEN.value,
                            linked_entities=[
                                {"type": "track", "id": tid, "name": track_name},
                                {"type": "artist", "name": artist_name},
                            ],
                            tags=POST_TAGS[PostType.RECORD_BROKEN],
                            significance=POST_SIGNIFICANCE[PostType.RECORD_BROKEN],
                        )
                    )

    # Check for artist career #1 record
    for e in week_entries:
        if e.get("rank") == 1:
            artist_name = e.get("artist_name", "")
            count = state.artist_no1_count_as_of(artist_name)
            if count >= state.most_career_no1s_count and count >= 5:
                # Artist just tied or broke the career #1 record
                pass  # handled by artist_milestone instead

    return posts


def _gen_milestone_posts(
    week_entries: list[dict], state: HistoricalState, posted_at: str, week_label: str
) -> list[CommunityPost]:
    """@popcrave: artist milestone posts."""
    posts = []
    for e in week_entries:
        if e.get("rank") == 1:
            artist_name = e.get("artist_name", "")
            track_name = e.get("track_name", "")
            count = state.artist_no1_count_as_of(artist_name)
            # Significant milestones
            if count in (1, 5, 10, 15, 20):
                if count == 1:
                    content = (
                        f"MILESTONE: {artist_name} earns their first Hot 100 #1 with '{track_name}'. "
                        f"Welcome to the chart-topper club."
                    )
                else:
                    content = (
                        f"MILESTONE: {artist_name} achieves their {_fmt_ordinal(count)} #1 on the "
                        f"Hot 100 with '{track_name}'."
                    )
                significance = 0.95 if count == 1 else POST_SIGNIFICANCE[PostType.ARTIST_MILESTONE]
                posts.append(
                    CommunityPost(
                        id=_make_id("milestone", artist_name, str(count), week_label),
                        account_handle="@popcrave",
                        posted_at=posted_at,
                        content=content,
                        post_type=PostType.ARTIST_MILESTONE.value,
                        linked_entities=[
                            {"type": "track", "id": e.get("track_id"), "name": track_name},
                            {"type": "artist", "name": artist_name},
                        ],
                        tags=POST_TAGS[PostType.ARTIST_MILESTONE],
                        significance=significance,
                    )
                )
    return posts


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
    content = (
        f"On this week in {year}: '{past_entry['track_name']}' by "
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

    parts = [
        f"This week you played {plays} songs ({hours:.1f}h) by {artist_count} artists.",
        f"Your top artist was {top_artist} ({top_plays} plays).",
    ]
    if new_tracks_this_week > 5:
        parts.append(f"You discovered {new_tracks_this_week} new tracks this week.")

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

    content = (
        f"Your {month_label} in music: {total_plays:,} plays, {total_hours:.0f}h listening, "
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


def _gen_alltime_stats(weekly, state: HistoricalState) -> list[CommunityPost]:
    """@chartstats: all-time statistical summaries, generated after full iteration."""
    posts: list[CommunityPost] = []
    if not state.past_no1s:
        return posts

    # Every #1 debut in history
    debut_no1s = []
    seen_tracks = set()
    for p in state.past_no1s:
        tid = p.get("track_id")
        if tid and tid not in seen_tracks:
            seen_tracks.add(tid)
            debut_no1s.append(p)

    if len(debut_no1s) >= 5:
        lines = [f"Every Hot 100 #1 in this chart era ({len(debut_no1s)} tracks):", ""]
        for p in debut_no1s[:50]:  # cap at 50
            lines.append(f"{p['track_name']} — {p['artist_name']}")
        if len(debut_no1s) > 50:
            lines.append(f"... and {len(debut_no1s) - 50} more.")
        posts.append(
            CommunityPost(
                id=_make_id("alltime", "no1s"),
                account_handle="@chartstats",
                posted_at=state.past_no1s[-1]["week"] + "T12:00:00",
                content="\n".join(lines),
                post_type=PostType.ALL_TIME_STATS.value,
                tags=POST_TAGS[PostType.ALL_TIME_STATS],
                significance=POST_SIGNIFICANCE[PostType.ALL_TIME_STATS],
            )
        )

    # Records summary
    if state.most_career_no1s_artist and state.most_career_no1s_count >= 3:
        posts.append(
            CommunityPost(
                id=_make_id("alltime", "career_no1s"),
                account_handle="@chartstats",
                posted_at=state.past_no1s[-1]["week"] + "T12:00:00",
                content=(
                    f"Artist with the most #1s in this chart era: {state.most_career_no1s_artist} "
                    f"({state.most_career_no1s_count} #1s)."
                ),
                post_type=PostType.ALL_TIME_STATS.value,
                linked_entities=[{"type": "artist", "name": state.most_career_no1s_artist}],
                tags=POST_TAGS[PostType.ALL_TIME_STATS],
                significance=0.60,
            )
        )

    return posts


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
        lines = [f"You have {len(forgotten)} saved tracks you haven't played yet:", ""]
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


def _gen_record_tied_posts(
    week_entries: list[dict], state: HistoricalState, posted_at: str, week_label: str
) -> list[CommunityPost]:
    """@recordwatch: record tied (not broken) posts — when a track equals the existing record."""
    posts = []
    for e in week_entries:
        tid = e.get("track_id")
        if not tid or e.get("rank") != 1:
            continue
        track_name = e.get("track_name", "")
        artist_name = e.get("artist_name", "")
        wks = state.track_weeks_at_no1_as_of(tid)

        # Tie detected: matches current longest record but it's a different track
        if (
            wks >= 2
            and wks == state.longest_no1_weeks
            and track_name != state.longest_no1_track_name
            and state.longest_no1_track_name
        ):
            content = (
                f"RECORD TIED: {artist_name}'s '{track_name}' has now tied "
                f"'{state.longest_no1_track_name}' for the longest #1 run of the era "
                f"({wks} weeks each)."
            )
            posts.append(
                CommunityPost(
                    id=_make_id("record", "tied", week_label, str(tid)),
                    account_handle="@recordwatch",
                    posted_at=posted_at,
                    content=content,
                    post_type=PostType.RECORD_TIED.value,
                    linked_entities=[
                        {"type": "track", "id": tid, "name": track_name},
                        {"type": "artist", "name": artist_name},
                    ],
                    tags=POST_TAGS[PostType.RECORD_TIED],
                    significance=POST_SIGNIFICANCE[PostType.RECORD_TIED],
                )
            )
    return posts


def _gen_record_watch_posts(
    week_entries: list[dict], state: HistoricalState, posted_at: str, week_label: str
) -> list[CommunityPost]:
    """@recordwatch: record watch — when a track is approaching a record."""
    posts = []
    for e in week_entries:
        tid = e.get("track_id")
        if not tid or e.get("rank") != 1:
            continue
        wks = state.track_weeks_at_no1_as_of(tid)
        # Only alert if within 2 weeks of breaking the record and track isn't already the record holder
        gap = state.longest_no1_weeks - wks
        if (
            1 <= gap <= 2
            and state.longest_no1_weeks >= 5
            and e.get("track_name", "") != state.longest_no1_track_name
        ):
            track_name = e.get("track_name", "")
            artist_name = e.get("artist_name", "")
            content = (
                f"RECORD WATCH: {artist_name}'s '{track_name}' is now at {wks} weeks at #1 — "
                f"just {gap} week{'s' if gap > 1 else ''} away from tying the record "
                f"({state.longest_no1_weeks} weeks, held by '{state.longest_no1_track_name}')."
            )
            posts.append(
                CommunityPost(
                    id=_make_id("record", "watch", week_label, str(tid)),
                    account_handle="@recordwatch",
                    posted_at=posted_at,
                    content=content,
                    post_type=PostType.RECORD_WATCH.value,
                    linked_entities=[
                        {"type": "track", "id": tid, "name": track_name},
                        {"type": "artist", "name": artist_name},
                    ],
                    tags=POST_TAGS[PostType.RECORD_WATCH],
                    significance=POST_SIGNIFICANCE[PostType.RECORD_WATCH],
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

    content = f"MILESTONE: You've reached {hits[0]}!"
    if len(hits) > 1:
        content = f"MILESTONE: You've reached {', '.join(hits[:-1])} and {hits[-1]}!"

    return CommunityPost(
        id=_make_id("personal", "milestone", week_label),
        account_handle="@spotifystats",
        posted_at=posted_at,
        content=content,
        post_type=PostType.PLAYBACK_MILESTONE.value,
        tags=POST_TAGS[PostType.PLAYBACK_MILESTONE],
        significance=POST_SIGNIFICANCE[PostType.PLAYBACK_MILESTONE],
    )


def _gen_album_no1_post(
    album_entries: list[dict], posted_at: str, week_label: str
) -> CommunityPost | None:
    """@billboardcharts: Billboard 200 #1 album announcement."""
    no1 = next((e for e in album_entries if e.get("rank") == 1), None)
    if not no1:
        return None

    album_name = no1.get("album_name", "")
    artist_name = no1.get("artist_name", "")
    content = f"Billboard 200: #1 {album_name} by {artist_name}."

    return CommunityPost(
        id=_make_id("album", "no1", week_label),
        account_handle="@billboardcharts",
        posted_at=posted_at,
        content=content,
        post_type=PostType.NO1_ANNOUNCEMENT.value,
        linked_entities=[
            {"type": "album", "name": album_name},
            {"type": "artist", "name": artist_name},
        ],
        tags=["weekly", "album", "no1"],
        significance=0.50,
    )


def _gen_artist_no1_post(
    artist_entries: list[dict], posted_at: str, week_label: str
) -> CommunityPost | None:
    """@chartdata: Artist 100 #1 announcement."""
    no1 = next((e for e in artist_entries if e.get("rank") == 1), None)
    if not no1:
        return None

    artist_name = no1.get("artist_name", "")
    play_count = no1.get("play_count", 0)
    content = f"Artist 100: #1 {artist_name} ({play_count:,} plays this week)."

    return CommunityPost(
        id=_make_id("artist", "no1", week_label),
        account_handle="@chartdata",
        posted_at=posted_at,
        content=content,
        post_type=PostType.NO1_ANNOUNCEMENT.value,
        linked_entities=[{"type": "artist", "name": artist_name}],
        tags=["weekly", "artist", "no1"],
        significance=0.45,
    )


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

    parts = [
        f"Your {year_label} in music:",
        f"{plays:,} plays across {hours:,.0f} hours.",
        f"{tracks:,} unique tracks by {artists:,} artists.",
    ]

    if prev_year_snapshot and prev_year_snapshot.cumulative_ms > 0:
        prev_hours = prev_year_snapshot.cumulative_ms / 3600000
        delta = hours - prev_hours
        if delta > 0:
            pct = (delta / prev_hours) * 100
            parts.append(f"Listening up {pct:.0f}% vs {int(year_label) - 1}.")
        elif delta < 0:
            pct = (abs(delta) / prev_hours) * 100
            parts.append(f"Listening down {pct:.0f}% vs {int(year_label) - 1}.")

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

    content = (
        f"Chart Era in Review ({first_week.strftime('%b %Y')} — {last_week.strftime('%b %Y')}): "
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
    content = (
        f"MILESTONE: Your saved tracks library has reached {best:,} tracks! "
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


def _load_cover_maps(conn) -> dict:
    """Build lookup maps for cover URL construction.

    Returns dict with:
      - track_to_album: {track_id: album_id}
      - artist_to_id: {artist_name: artist_id}
      - album_name_to_id: {(album_name, artist_id): album_id}
    """
    track_to_album: dict[int, int] = {}
    artist_to_id: dict[str, int] = {}
    album_name_to_id: dict[tuple[str, int], int] = {}

    try:
        rows = conn.execute(
            "SELECT track_id, album_id FROM tracks WHERE album_id IS NOT NULL"
        ).fetchall()
        track_to_album = {r[0]: r[1] for r in rows}
    except Exception:
        pass

    try:
        rows = conn.execute("SELECT artist_id, artist_name FROM artists").fetchall()
        artist_to_id = {r[1]: r[0] for r in rows}
    except Exception:
        pass

    try:
        rows = conn.execute("SELECT album_id, album_name, artist_id FROM albums").fetchall()
        album_name_to_id = {(r[1], r[2]): r[0] for r in rows}
    except Exception:
        pass

    return {
        "track_to_album": track_to_album,
        "artist_to_id": artist_to_id,
        "album_name_to_id": album_name_to_id,
    }


def _enrich_post_images(post: CommunityPost, cover_maps: dict) -> None:
    """Add cover/artist images to a post based on its linked entities."""
    track_to_album = cover_maps.get("track_to_album", {})
    artist_to_id = cover_maps.get("artist_to_id", {})
    album_name_to_id = cover_maps.get("album_name_to_id", {})

    # Gather artist names from this post's entities (needed for album lookup)
    linked_artist_names = {e["name"] for e in post.linked_entities if e.get("type") == "artist"}

    images: list[str] = []

    # Album cover (for album chart posts)
    for entity in post.linked_entities:
        if entity.get("type") == "album":
            album_name = entity.get("name", "")
            # Try each linked artist to find the matching album
            for artist_name in linked_artist_names:
                aid = artist_to_id.get(artist_name)
                if aid and (album_name, aid) in album_name_to_id:
                    url = f"/covers/albums/{album_name_to_id[(album_name, aid)]}.jpg"
                    if url not in images:
                        images.append(url)
                        break
            if images:
                break

    # Add image for first linked track (via album cover)
    if not images:
        for entity in post.linked_entities:
            if entity.get("type") == "track":
                tid = entity.get("id")
                if tid and tid in track_to_album:
                    url = f"/covers/albums/{track_to_album[tid]}.jpg"
                    if url not in images:
                        images.append(url)
                        break

    # Add image for linked artist
    for entity in post.linked_entities:
        if entity.get("type") == "artist":
            name = entity.get("name", "")
            aid = artist_to_id.get(name)
            if aid:
                url = f"/covers/artists/{aid}.jpg"
                if url not in images:
                    images.append(url)
                    break

    post.images = images


@ttl_cached(ttl_seconds=600, namespace="community")
def _generate_core_posts(
    min_ms: int = 30000,
    music_only: bool = True,
    bb_top_n: int = 30,
    bb_album_top_n: int = 20,
    bb_artist_top_n: int = 20,
    bb_week_start_dow: int = 4,
    bb_week_start_hour: int = 0,
    year_start: int | None = None,
    year_end: int | None = None,
) -> tuple[list[CommunityPost], HistoricalState]:
    """Cached core chart post generation — iterates full chart history.

    Returns (posts, state) where posts excludes collection/cover/metric enrichment
    and state is the final HistoricalState after processing all weeks.
    """
    df_raw, weekly, weekly_album, weekly_artist, all_weeks = _load_chart_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )

    if not all_weeks:
        return [], HistoricalState()

    personal_weekly = _compute_personal_weekly(df_raw)

    state = HistoricalState()
    posts: list[CommunityPost] = []
    prev_week_entries: list[dict] | None = None
    monthly_snapshots: list[tuple[str, str, HistoricalState]] = []
    yearly_snapshots: list[tuple[str, str, HistoricalState, HistoricalState | None]] = []
    prev_cum_plays = 0
    prev_cum_hours = 0.0
    prev_cum_tracks = 0
    prev_year: int | None = None
    year_start_snapshot: HistoricalState | None = None

    for i, week_val in enumerate(all_weeks):
        week_label = str(week_val)[:10]
        entries = _entries_for_week(weekly, week_val)
        if not entries:
            continue

        posted_at = _week_end_date(week_val)
        personal = personal_weekly.get(week_val, {})

        if personal.get("plays", 0) < 3:
            state.update(entries, **personal) if personal else state.update(entries)
            prev_week_entries = entries
            continue

        posts.extend(_gen_no1_posts(entries, state, posted_at, week_label))

        top10 = _gen_top10_summary(entries, state, posted_at, week_label)
        if top10:
            posts.append(top10)

        posts.extend(_gen_debut_posts(entries, state, posted_at, week_label))

        jump = _gen_biggest_jump_post(entries, prev_week_entries, posted_at, week_label)
        if jump:
            posts.append(jump)

        posts.extend(_gen_record_posts(entries, state, posted_at, week_label))
        posts.extend(_gen_milestone_posts(entries, state, posted_at, week_label))

        tb = _gen_throwback_post(state, all_weeks, posted_at, week_label)
        if tb:
            posts.append(tb)

        wp = _gen_weekly_personal(week_label, personal, state, posted_at)
        if wp:
            posts.append(wp)

        posts.extend(_gen_record_tied_posts(entries, state, posted_at, week_label))
        posts.extend(_gen_record_watch_posts(entries, state, posted_at, week_label))

        pm = _gen_playback_milestone(
            state, prev_cum_plays, prev_cum_hours, prev_cum_tracks, posted_at, week_label
        )
        if pm:
            posts.append(pm)

        # Album chart #1
        album_entries = _album_entries_for_week(weekly_album, week_val)
        an1 = _gen_album_no1_post(album_entries, posted_at, week_label)
        if an1:
            posts.append(an1)

        # Artist chart #1
        artist_entries = _artist_entries_for_week(weekly_artist, week_val)
        arn1 = _gen_artist_no1_post(artist_entries, posted_at, week_label)
        if arn1:
            posts.append(arn1)

        state.update(
            entries,
            personal_plays=personal.get("plays", 0),
            personal_ms=personal.get("ms", 0),
            personal_track_ids=personal.get("track_ids", set()),
            personal_artist_names=personal.get("artist_names", set()),
            personal_top_artist=personal.get("top_artist", ""),
            personal_top_artist_plays=personal.get("top_artist_plays", 0),
        )

        prev_cum_plays = state.cumulative_plays
        prev_cum_hours = state.cumulative_ms / 3600000
        prev_cum_tracks = len(state.cumulative_tracks)

        try:
            dt = pd.Timestamp(week_val)
            month_key = dt.strftime("%Y-%m")
            existing = [s for s in monthly_snapshots if s[0] == month_key]
            if not existing:
                snapshot = HistoricalState()
                snapshot.cumulative_plays = state.cumulative_plays
                snapshot.cumulative_ms = state.cumulative_ms
                snapshot.cumulative_tracks = state.cumulative_tracks.copy()
                snapshot.cumulative_artists = state.cumulative_artists.copy()
                monthly_snapshots.append((month_key, posted_at, snapshot))

            year = dt.year
            if year != prev_year:
                if prev_year is not None and year_start_snapshot is not None:
                    year_end_snapshot = HistoricalState()
                    year_end_snapshot.cumulative_plays = state.cumulative_plays
                    year_end_snapshot.cumulative_ms = state.cumulative_ms
                    year_end_snapshot.cumulative_tracks = state.cumulative_tracks.copy()
                    year_end_snapshot.cumulative_artists = state.cumulative_artists.copy()
                    yearly_snapshots.append(
                        (str(prev_year), posted_at, year_end_snapshot, year_start_snapshot)
                    )
                year_start_snapshot = HistoricalState()
                year_start_snapshot.cumulative_plays = state.cumulative_plays
                year_start_snapshot.cumulative_ms = state.cumulative_ms
                year_start_snapshot.cumulative_tracks = state.cumulative_tracks.copy()
                year_start_snapshot.cumulative_artists = state.cumulative_artists.copy()
                prev_year = year
        except Exception:
            pass

        prev_week_entries = entries

    if prev_year is not None and year_start_snapshot is not None:
        year_end_snapshot = HistoricalState()
        year_end_snapshot.cumulative_plays = state.cumulative_plays
        year_end_snapshot.cumulative_ms = state.cumulative_ms
        year_end_snapshot.cumulative_tracks = state.cumulative_tracks.copy()
        year_end_snapshot.cumulative_artists = state.cumulative_artists.copy()
        last_date = posts[-1].posted_at if posts else datetime.now().strftime("%Y-%m-%dT12:00:00")
        yearly_snapshots.append((str(prev_year), last_date, year_end_snapshot, year_start_snapshot))

    for month_key, last_posted_at, snap in monthly_snapshots:
        mp = _gen_monthly_personal(month_key, [], snap, last_posted_at)
        if mp:
            posts.append(mp)

    for year_label, snap_posted_at, year_end_snap, year_start_snap in yearly_snapshots:
        yp = _gen_yearly_personal(year_label, year_end_snap, year_start_snap, snap_posted_at)
        if yp:
            posts.append(yp)

    posts.extend(_gen_alltime_stats(weekly, state))

    end_date = all_weeks[-1]
    try:
        end_dt = pd.Timestamp(end_date)
        era_posted_at = end_dt.strftime("%Y-%m-%dT12:00:00")
    except Exception:
        era_posted_at = datetime.now().strftime("%Y-%m-%dT12:00:00")
    dc = _gen_decade_comparison(state, all_weeks, era_posted_at)
    if dc:
        posts.append(dc)

    return posts, state


def generate_all_posts(
    conn=None,
    min_ms: int = 30000,
    music_only: bool = True,
    bb_top_n: int = 30,
    bb_album_top_n: int = 20,
    bb_artist_top_n: int = 20,
    bb_week_start_dow: int = 4,
    bb_week_start_hour: int = 0,
    year_start: int | None = None,
    year_end: int | None = None,
) -> list[CommunityPost]:
    """Main entry point: generate all community posts by iterating chart history.

    Core chart iteration is cached (TTL 10 min). Collection posts, cover images,
    and engagement metrics are enriched fresh on each call.
    """
    core_posts, state = _generate_core_posts(
        min_ms=min_ms,
        music_only=music_only,
        bb_top_n=bb_top_n,
        bb_album_top_n=bb_album_top_n,
        bb_artist_top_n=bb_artist_top_n,
        bb_week_start_dow=bb_week_start_dow,
        bb_week_start_hour=bb_week_start_hour,
        year_start=year_start,
        year_end=year_end,
    )

    # Shallow copy so we can extend without mutating the cached list
    posts: list[CommunityPost] = list(core_posts)

    # Collection posts (need DB conn)
    if conn is not None:
        collection_data = _load_collection_data(conn)
    else:
        collection_data = {
            "total_saved": 0,
            "first_save": None,
            "forgotten": [],
            "forgotten_count": 0,
        }

    posts.extend(_gen_collection_posts(collection_data, state))
    posts.extend(_gen_collection_milestone(collection_data, state))

    # Cover images (need DB conn)
    cover_maps = _load_cover_maps(conn) if conn else {}
    for post in posts:
        _enrich_post_images(post, cover_maps)

    # Engagement metrics — always fresh (randomized)
    for post in posts:
        acct = ACCOUNT_BY_HANDLE.get(post.account_handle, {})
        post.metrics = _generate_metrics(post.significance, str(acct.get("follower_tier", "mid")))

    posts.sort(key=lambda p: p.posted_at, reverse=True)
    return posts

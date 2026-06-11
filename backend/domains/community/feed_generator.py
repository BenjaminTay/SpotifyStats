"""Community feed generator — iterates chart weeks chronologically and generates
simulated X-style posts from real data while maintaining historical accuracy."""

from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta

import pandas as pd

from backend.core.cache import ttl_cached
from backend.domains.billboard.chart_power_score import (
    _BASE_DECAY,
    _COMP_RANGE,
    _DEBUT_NO1_BONUS,
    _INDIV_GAP_RANGE,
    _INDIV_RANGE,
    _LONGEVITY_FACTOR,
    _PEAK_BONUS,
    _RANK1_BASE,
    _TOP5_BONUS,
    _TOP10_BONUS,
)
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
    week_entries: list[dict],
    prev_week_entries: list[dict] | None,
    state: HistoricalState,
    posted_at: str,
    week_label: str,
) -> list[CommunityPost]:
    """Generate #1 announcement posts from @chartdata.

    Four scenarios based on how the track reached #1:
      - #1(new): track debuts on the chart at #1
      - #1(+N): track climbed N spots from a lower rank to #1
      - #1(re): track re-enters the chart at #1 after falling off
      - #1(=): track stays at #1 for a consecutive week
    """
    posts = []
    no1s = [e for e in week_entries if e.get("rank") == 1]

    prev_rank_map: dict[int, int] = {}
    if prev_week_entries:
        prev_rank_map = {
            e.get("track_id"): e.get("rank", 999) for e in prev_week_entries if e.get("track_id")
        }

    for entry in no1s:
        track_name = entry.get("track_name", "")
        artist_name = entry.get("artist_name", "")
        track_id = entry.get("track_id")

        in_debut_week = track_id and track_id not in state.track_debut_week
        prev_rank = prev_rank_map.get(track_id) if track_id else None
        in_prev_week = prev_rank is not None
        was_no1_last_week = prev_rank == 1

        if in_debut_week:
            nth = state.artist_ordinal_no1(artist_name)
            opener = _pick("Hot 100:", "Hot 100 —")
            content = f"{opener} #1(new) {track_name}, {artist_name}."
            if state.artist_no1_count_as_of(artist_name) >= 1:
                body = _pick(
                    f"It becomes {artist_name}'s {nth} #1 on the chart.",
                    f"Marks {artist_name}'s {nth} chart-topper.",
                    f"Gives {artist_name} their {nth} #1.",
                )
                content += f" {body}"
            else:
                body = _pick(
                    f"This is {artist_name}'s first #1 on the Hot 100.",
                    f"{artist_name} claims their first Hot 100 #1.",
                    f"{artist_name}'s first trip to the top of the Hot 100.",
                )
                content += f" {body}"
            significance = POST_SIGNIFICANCE[PostType.NO1_ANNOUNCEMENT]
        elif was_no1_last_week:
            total_weeks = state.track_weeks_at_no1_as_of(track_id) + 1
            body = _pick(
                f"spends a {_fmt_ordinal(total_weeks)} week at #1.",
                f"holds at #1 for a {_fmt_ordinal(total_weeks)} week.",
                f"notches a {_fmt_ordinal(total_weeks)} week at the top.",
            )
            content = f"Hot 100: #1(=) {track_name}, {artist_name} {body}"
            significance = POST_SIGNIFICANCE[PostType.NO1_ANNOUNCEMENT] * 0.7
        elif in_prev_week:
            jump = prev_rank - 1
            nth = state.artist_ordinal_no1(artist_name)
            was_at_no1_before = track_id and state.track_weeks_at_no1.get(track_id, 0) > 0
            if was_at_no1_before:
                total_weeks = state.track_weeks_at_no1_as_of(track_id) + 1
                verb = _pick(
                    f"returns to #1 for the {_fmt_ordinal(total_weeks)} week",
                    f"reclaims the top spot for the {_fmt_ordinal(total_weeks)} week",
                    f"is back at #1 for the {_fmt_ordinal(total_weeks)} week",
                )
                extra = _pick(
                    f"(jumps {prev_rank}-1).",
                    f"(up from #{prev_rank}).",
                    f"(rises {prev_rank}-1).",
                    "",  # sometimes omit the jump detail
                )
                content = f"Hot 100: #1(+{jump}) {track_name}, {artist_name} {verb}"
                if extra:
                    content += f" {extra}"
            else:
                verb = _pick("climbs", "rises", "jumps", "surges")
                content = f"Hot 100: #1(+{jump}) {track_name}, {artist_name} {verb} {prev_rank}-1."
                if state.artist_no1_count_as_of(artist_name) >= 1:
                    body = _pick(
                        f"It becomes {artist_name}'s {nth} #1 on the chart.",
                        f"Marks {artist_name}'s {nth} chart-topper.",
                        f"Gives {artist_name} their {nth} #1.",
                    )
                    content += f" {body}"
                else:
                    body = _pick(
                        f"This is {artist_name}'s first #1 on the Hot 100.",
                        f"{artist_name} claims their first Hot 100 #1.",
                    )
                    content += f" {body}"
            significance = POST_SIGNIFICANCE[PostType.NO1_ANNOUNCEMENT]
        else:
            nth = state.artist_ordinal_no1(artist_name)
            was_at_no1_before = track_id and state.track_weeks_at_no1.get(track_id, 0) > 0
            if was_at_no1_before:
                total_weeks = state.track_weeks_at_no1_as_of(track_id) + 1
                body = _pick(
                    f"re-enters at #1 for the {_fmt_ordinal(total_weeks)} week.",
                    f"storms back in at #1 for the {_fmt_ordinal(total_weeks)} week.",
                    f"makes a comeback at #1 for the {_fmt_ordinal(total_weeks)} week.",
                )
                content = f"Hot 100: #1(re) {track_name}, {artist_name} {body}"
            else:
                body = _pick(
                    "re-enters the chart at #1.",
                    "returns to the chart at #1.",
                    "makes a surprise return at #1.",
                )
                content = f"Hot 100: #1(re) {track_name}, {artist_name} {body}"
                if state.artist_no1_count_as_of(artist_name) >= 1:
                    sub = _pick(
                        f"It becomes {artist_name}'s {nth} #1 on the chart.",
                        f"Marks {artist_name}'s {nth} chart-topper.",
                    )
                    content += f" {sub}"
                else:
                    sub = _pick(
                        f"This is {artist_name}'s first #1 on the Hot 100.",
                        f"{artist_name} claims their first Hot 100 #1.",
                    )
                    content += f" {sub}"
            significance = POST_SIGNIFICANCE[PostType.NO1_ANNOUNCEMENT]

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

    header = _pick(
        f"This week's top 10 on the Hot 100 (chart dated {week_label}):",
        f"The Hot 100 top 10 — week of {week_label}:",
        f"Your weekly Hot 100 top 10 ({week_label}):",
    )
    lines = [header, ""]
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
        header = _pick(
            f"Notable new entries on the Hot 100 this week ({week_label}):",
            f"Fresh arrivals on the Hot 100 ({week_label}):",
            f"This week's Hot 100 debuts ({week_label}):",
            f"Newcomers to the Hot 100 ({week_label}):",
        )
        lines = [header, ""]
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
        verb = _pick(
            "enters the chart this week.",
            "makes its Hot 100 debut.",
            "arrives on the Hot 100.",
            "cracks the chart this week.",
        )
        content = f"Hot 100 debut: #{d['rank']} {d.get('track_name', '')} by {d.get('artist_name', '')} {verb}"
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
        verb = _pick("rockets", "soars", "leaps", "surges", "skyrockets")
        label = _pick(
            "Biggest jump this week:", "Biggest mover this week:", "Largest leap this week:"
        )
        content = (
            f"{label} {best_jump.get('track_name', '')} by {best_jump.get('artist_name', '')} "
            f"{verb} {prev_map[best_jump['track_id']]}-{best_jump['rank']} (+{best_delta} spots)."
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
    week_entries: list[dict],
    state: HistoricalState,
    posted_at: str,
    week_label: str,
    *,
    track_most_career_weeks: int,
    track_most_career_weeks_artist: str,
    track_most_top10: int,
    track_most_top10_artist: str,
) -> list[CommunityPost]:
    """@recordwatch: Hot 100 record posts — longest #1, career #1 weeks, concurrent top 10.

    Longest #1 run is auto-tracked by HistoricalState (longest_no1_* fields).
    Career weeks and concurrent top 10 are tracked externally and passed in.
    """
    posts = []
    for e in week_entries:
        tid = e.get("track_id")
        if not tid or e.get("rank") != 1:
            continue
        wks = state.track_weeks_at_no1_as_of(tid)
        track_name = e.get("track_name", "")
        artist_name = e.get("artist_name", "")

        # Longest #1 run broken (uses HistoricalState auto-tracked fields)
        if wks == state.longest_no1_weeks and wks > 1:
            prev_record = state.longest_no1_weeks - 1
            if prev_record > 0 and track_name != state.longest_no1_track_name:
                label = _pick("RECORD:", "NEW RECORD:", "HISTORY:")
                verb = _pick("now holds", "now owns", "sets a new mark for")
                content = (
                    f"{label} {artist_name}'s '{track_name}' {verb} the longest #1 run "
                    f"of the era ({wks} weeks). Previous best: {prev_record} weeks "
                    f"(by '{state.longest_no1_track_name}')."
                )
                posts.append(
                    CommunityPost(
                        id=_make_id("record", "track_longest", week_label),
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

    # Artist career #1 weeks record
    for artist, wks in sorted(state.artist_no1_weeks.items(), key=lambda x: x[1], reverse=True):
        if wks > track_most_career_weeks and wks >= 10:
            label = _pick("RECORD:", "MILESTONE RECORD:", "NEW RECORD:")
            body = (
                _pick(
                    f"surpassing {track_most_career_weeks_artist}",
                    f"breaking the previous mark held by {track_most_career_weeks_artist}",
                )
                if track_most_career_weeks_artist
                else ""
            )
            content = f"{label} {artist} has the most cumulative weeks at #1 ({wks} weeks)."
            if body:
                content += f" {body} ({track_most_career_weeks} weeks)."
            posts.append(
                CommunityPost(
                    id=_make_id("record", "career_weeks", week_label, artist),
                    account_handle="@recordwatch",
                    posted_at=posted_at,
                    content=content,
                    post_type=PostType.RECORD_BROKEN.value,
                    linked_entities=[{"type": "artist", "name": artist}],
                    tags=POST_TAGS[PostType.RECORD_BROKEN],
                    significance=POST_SIGNIFICANCE[PostType.RECORD_BROKEN],
                )
            )
            break

    # Most concurrent top 10 entries
    this_week_top10 = [e for e in week_entries if e.get("rank", 999) <= 10]
    concurrent_counts: dict[str, int] = {}
    for e in this_week_top10:
        artist = e.get("artist_name", "")
        concurrent_counts[artist] = concurrent_counts.get(artist, 0) + 1
    for artist, count in sorted(concurrent_counts.items(), key=lambda x: x[1], reverse=True):
        if count > track_most_top10 and count >= 3:
            label = _pick("RECORD:", "NEW RECORD:", "HISTORY:")
            prev = (
                f"(previous best: {track_most_top10} by {track_most_top10_artist})"
                if track_most_top10_artist
                else ""
            )
            content = (
                f"{label} {artist} has {count} songs in the top 10 simultaneously "
                f"— the most of the era. {prev}"
            )
            posts.append(
                CommunityPost(
                    id=_make_id("record", "concurrent_top10", week_label, artist),
                    account_handle="@recordwatch",
                    posted_at=posted_at,
                    content=content,
                    post_type=PostType.RECORD_BROKEN.value,
                    linked_entities=[{"type": "artist", "name": artist}],
                    tags=POST_TAGS[PostType.RECORD_BROKEN],
                    significance=POST_SIGNIFICANCE[PostType.RECORD_BROKEN],
                )
            )
            break

    return posts


def _gen_album_record_posts(
    album_entries: list[dict],
    album_weeks_at_no1: dict[str, int],
    posted_at: str,
    week_label: str,
    *,
    album_longest_no1_weeks: int,
    album_longest_no1_name: str,
    album_longest_no1_artist: str,
    album_most_no1s_count: int,
    album_most_no1s_artist: str,
) -> list[CommunityPost]:
    """@recordwatch: Billboard 200 record posts — longest #1, most #1 albums."""
    posts = []
    for e in album_entries:
        if e.get("rank") != 1:
            continue
        album_name = e.get("album_name", "")
        artist_name = e.get("artist_name", "")
        album_key = f"{album_name}|{artist_name}"
        wks = album_weeks_at_no1.get(album_key, 0) + 1  # current week included

        # Longest #1 run
        if wks > album_longest_no1_weeks and album_longest_no1_weeks >= 2:
            label = _pick("RECORD:", "NEW RECORD:", "HISTORY:")
            verb = _pick("now holds", "now owns", "sets a new mark for")
            content = (
                f"{label} Billboard 200: {artist_name}'s '{album_name}' {verb} the longest #1 run "
                f"of the era ({wks} weeks). Previous best: {album_longest_no1_weeks} weeks "
                f"(by '{album_longest_no1_name}')."
            )
            posts.append(
                CommunityPost(
                    id=_make_id("record", "album_longest", week_label),
                    account_handle="@recordwatch",
                    posted_at=posted_at,
                    content=content,
                    post_type=PostType.RECORD_BROKEN.value,
                    linked_entities=[
                        {"type": "album", "name": album_name},
                        {"type": "artist", "name": artist_name},
                    ],
                    tags=POST_TAGS[PostType.RECORD_BROKEN],
                    significance=POST_SIGNIFICANCE[PostType.RECORD_BROKEN],
                )
            )

    # Most #1 albums by artist
    album_no1_counts: dict[str, int] = {}
    for key, wks_val in album_weeks_at_no1.items():
        # key is "album_name|artist_name", extract artist
        parts = key.rsplit("|", 1)
        artist = parts[1] if len(parts) == 2 else ""
        if wks_val > 0:
            album_no1_counts[artist] = album_no1_counts.get(artist, 0) + 1
    for artist, count in album_no1_counts.items():
        if count > album_most_no1s_count and count >= 3:
            label = _pick("RECORD:", "NEW RECORD:", "HISTORY:")
            content = (
                f"{label} {artist} now has the most #1 albums of the era "
                f"({count} albums). Previous best: {album_most_no1s_artist} ({album_most_no1s_count})."
            )
            posts.append(
                CommunityPost(
                    id=_make_id("record", "album_most_no1s", week_label, artist),
                    account_handle="@recordwatch",
                    posted_at=posted_at,
                    content=content,
                    post_type=PostType.RECORD_BROKEN.value,
                    linked_entities=[{"type": "artist", "name": artist}],
                    tags=POST_TAGS[PostType.RECORD_BROKEN],
                    significance=POST_SIGNIFICANCE[PostType.RECORD_BROKEN],
                )
            )
            break

    return posts


def _gen_artist_chart_record_posts(
    artist_entries: list[dict],
    artist_weeks_at_no1: dict[str, int],
    posted_at: str,
    week_label: str,
    *,
    artist_chart_longest_no1_weeks: int,
    artist_chart_longest_no1_name: str,
    artist_chart_most_no1_weeks_count: int,
    artist_chart_most_no1_weeks_name: str,
) -> list[CommunityPost]:
    """@recordwatch: Artist 100 record posts — longest #1, most weeks at #1."""
    posts = []
    for e in artist_entries:
        if e.get("rank") != 1:
            continue
        artist_name = e.get("artist_name", "")
        wks = artist_weeks_at_no1.get(artist_name, 0) + 1

        # Longest #1 run
        if wks > artist_chart_longest_no1_weeks and artist_chart_longest_no1_weeks >= 2:
            label = _pick("RECORD:", "NEW RECORD:", "HISTORY:")
            verb = _pick("now holds", "now owns", "sets a new mark for")
            content = (
                f"{label} Artist 100: {artist_name} {verb} the longest #1 run "
                f"of the era ({wks} weeks). Previous best: {artist_chart_longest_no1_weeks} weeks "
                f"(by {artist_chart_longest_no1_name})."
            )
            posts.append(
                CommunityPost(
                    id=_make_id("record", "artist_chart_longest", week_label),
                    account_handle="@recordwatch",
                    posted_at=posted_at,
                    content=content,
                    post_type=PostType.RECORD_BROKEN.value,
                    linked_entities=[{"type": "artist", "name": artist_name}],
                    tags=POST_TAGS[PostType.RECORD_BROKEN],
                    significance=POST_SIGNIFICANCE[PostType.RECORD_BROKEN],
                )
            )

    # Most cumulative weeks at #1 on Artist 100
    for artist, wks in sorted(artist_weeks_at_no1.items(), key=lambda x: x[1], reverse=True):
        if (
            wks > artist_chart_most_no1_weeks_count
            and wks >= 5
            and artist != artist_chart_most_no1_weeks_name
        ):
            label = _pick("RECORD:", "NEW RECORD:", "HISTORY:")
            content = (
                f"{label} Artist 100: {artist} has spent the most weeks at #1 "
                f"({wks} weeks). Previous best: {artist_chart_most_no1_weeks_name} "
                f"({artist_chart_most_no1_weeks_count} weeks)."
            )
            posts.append(
                CommunityPost(
                    id=_make_id("record", "artist_chart_most_weeks", week_label, artist),
                    account_handle="@recordwatch",
                    posted_at=posted_at,
                    content=content,
                    post_type=PostType.RECORD_BROKEN.value,
                    linked_entities=[{"type": "artist", "name": artist}],
                    tags=POST_TAGS[PostType.RECORD_BROKEN],
                    significance=POST_SIGNIFICANCE[PostType.RECORD_BROKEN],
                )
            )
            break

    return posts


def _gen_milestone_posts(
    week_entries: list[dict], state: HistoricalState, posted_at: str, week_label: str
) -> list[CommunityPost]:
    """@popcrave: artist milestone posts.

    Generated before state.update(), so the current track hasn't been counted yet.
    We use next_count = current_count + 1 to determine whether this week's #1
    crosses a milestone threshold.

    Deduplication: only one milestone per (artist, next_count) pair to prevent
    duplicate posts when data contains multiple rank-1 entries for the same week.
    """
    posts = []
    seen: set[tuple[str, int]] = set()
    for e in week_entries:
        if e.get("rank") == 1:
            artist_name = e.get("artist_name", "")
            track_name = e.get("track_name", "")
            next_count = state.artist_no1_count_as_of(artist_name) + 1
            dedup_key = (artist_name, next_count)
            if dedup_key in seen:
                continue
            # Significant milestones
            if next_count in (1, 5, 10, 15, 20):
                seen.add(dedup_key)
                if next_count == 1:
                    verb = _pick("earns", "claims", "scores", "lands")
                    closer = _pick(
                        "Welcome to the chart-topper club.",
                        "A first trip to the summit.",
                        "The first of many?",
                    )
                    content = f"MILESTONE: {artist_name} {verb} their first Hot 100 #1 with '{track_name}'. {closer}"
                else:
                    verb = _pick("achieves", "notches", "lands", "collects")
                    content = (
                        f"MILESTONE: {artist_name} {verb} their {_fmt_ordinal(next_count)} #1 on the "
                        f"Hot 100 with '{track_name}'."
                    )
                significance = (
                    0.95 if next_count == 1 else POST_SIGNIFICANCE[PostType.ARTIST_MILESTONE]
                )
                posts.append(
                    CommunityPost(
                        id=_make_id("milestone", artist_name, str(next_count), week_label),
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
        header = _pick(
            f"Every Hot 100 #1 in this chart era ({len(debut_no1s)} tracks):",
            f"All {len(debut_no1s)} Hot 100 #1s of this era:",
            f"The complete list of Hot 100 #1s ({len(debut_no1s)}):",
        )
        lines = [header, ""]
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
                    f"{_pick('Artist with the most #1s in this chart era:', 'The era leader in #1s:', 'Most #1s this era:')} "
                    f"{state.most_career_no1s_artist} "
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
            label = _pick("RECORD TIED:", "TIED:", "RECORD MATCHED:")
            verb = _pick("has now tied", "matches", "equals")
            content = (
                f"{label} {artist_name}'s '{track_name}' {verb} "
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
            label = _pick("RECORD WATCH:", "ON THE BRINK:", "CLOSE TO HISTORY:")
            body = _pick(
                f"is now at {wks} weeks at #1 — just {gap} week{'s' if gap > 1 else ''} away from tying the record",
                f"has now spent {wks} weeks at #1, only {gap} week{'s' if gap > 1 else ''} from matching the record",
                f"sits at {wks} weeks at #1 — {gap} week{'s' if gap > 1 else ''} from tying the mark",
            )
            content = (
                f"{label} {artist_name}'s '{track_name}' {body} "
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


def _gen_talk_weekly_race(
    entries: list[dict], posted_at: str, week_label: str
) -> CommunityPost | None:
    """@talkofthecharts: #1 vs #2 race analysis — tight races and blowouts."""
    no1 = next((e for e in entries if e.get("rank") == 1), None)
    no2 = next((e for e in entries if e.get("rank") == 2), None)
    if not no1 or not no2:
        return None

    no1_plays = no1.get("play_count", 0)
    no2_plays = no2.get("play_count", 0)
    if no1_plays <= 0 or no2_plays <= 0:
        return None

    gap = no1_plays - no2_plays
    gap_pct = (gap / no2_plays) * 100

    # Tight race: gap < 3%
    if gap_pct < 3:
        label = _pick("TIGHT RACE:", "PHOTO FINISH:", "NECK AND NECK:")
        body = _pick(
            f"'{no1['track_name']}' edges out '{no2['track_name']}' by just {gap:,} plays ({gap_pct:.1f}%).",
            f"Only {gap:,} plays ({gap_pct:.1f}%) separate #1 '{no1['track_name']}' from #2 '{no2['track_name']}'.",
            f"'{no1['track_name']}' holds off '{no2['track_name']}' by a razor-thin {gap:,} plays.",
        )
        content = f"{label} {body}"
        sig = 0.48
    # Blowout: gap > 50%
    elif gap_pct > 80:
        label = _pick("DOMINANT:", "LANDSLIDE:", "BLOWOUT:")
        body = _pick(
            f"'{no1['track_name']}' towers over #2 '{no2['track_name']}' with {gap_pct:.0f}% more plays.",
            f"'{no1['track_name']}' more than doubles #2 '{no2['track_name']}' ({gap:,} play lead, +{gap_pct:.0f}%).",
            f"A dominant week: '{no1['track_name']}' leads #2 by {gap:,} plays (+{gap_pct:.0f}%).",
        )
        content = f"{label} {body}"
        sig = 0.40
    else:
        return None

    return CommunityPost(
        id=_make_id("talk", "race", week_label),
        account_handle="@talkofthecharts",
        posted_at=posted_at,
        content=content,
        post_type=PostType.TOP10_SUMMARY.value,
        linked_entities=[
            {"type": "track", "id": no1.get("track_id"), "name": no1.get("track_name", "")},
            {"type": "artist", "name": no1.get("artist_name", "")},
        ],
        tags=["weekly", "analysis"],
        significance=sig,
    )


def _gen_talk_market_overview(
    entries: list[dict],
    prev_entries: list[dict] | None,
    state: HistoricalState,
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@talkofthecharts: weekly chart market overview — turnover, freshness, total volume."""
    if len(entries) < 5:
        return None

    total_plays = sum(e.get("play_count", 0) for e in entries)
    track_count = len(entries)

    prev_ids = (
        {e.get("track_id") for e in prev_entries if e.get("track_id")} if prev_entries else set()
    )
    current_ids = {e.get("track_id") for e in entries if e.get("track_id")}

    new_entries = sum(1 for tid in current_ids if tid and tid not in state.track_debut_week)
    re_entries = sum(
        1 for tid in current_ids if tid and tid in state.track_debut_week and tid not in prev_ids
    )
    exits = len(prev_ids - current_ids) if prev_entries else 0

    # Only post when something notable happens
    if new_entries + re_entries + exits < 3:
        return None

    opener = _pick(
        f"Chart turnover this week ({week_label}):",
        f"Hot 100 movement report — {week_label}:",
        f"This week's chart churn ({week_label}):",
    )

    parts = []
    if new_entries >= 3:
        parts.append(
            _pick(
                f"{new_entries} new entries arrived.",
                f"{new_entries} tracks made their debut.",
                f"Welcome {new_entries} newcomers.",
            )
        )
    if re_entries >= 2:
        parts.append(
            _pick(
                f"{re_entries} tracks returned to the chart.",
                f"{re_entries} re-entries this week.",
            )
        )
    if exits >= 3:
        parts.append(
            _pick(
                f"{exits} tracks dropped out.",
                f"{exits} departures from the chart.",
            )
        )

    if not parts:
        return None

    total_line = _pick(
        f"Total: {total_plays:,} plays across {track_count} tracks.",
        f"{track_count} tracks combined for {total_plays:,} plays.",
    )

    content = f"{opener} {' '.join(parts)} {total_line}"

    return CommunityPost(
        id=_make_id("talk", "market", week_label),
        account_handle="@talkofthecharts",
        posted_at=posted_at,
        content=content,
        post_type=PostType.NEW_ENTRIES_ROUNDUP.value,
        tags=["weekly", "analysis"],
        significance=0.30,
    )


def _gen_talk_longevity_alert(
    entries: list[dict],
    state: HistoricalState,
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@talkofthecharts: notable longevity milestones during iteration."""
    for e in entries:
        tid = e.get("track_id")
        if not tid:
            continue
        total_wks = state.track_total_weeks_as_of(tid) + 1  # include current week
        # Milestone weeks: 20, 30, 40, 52 (1 year), 60, 80, 100
        milestones = [20, 30, 40, 52, 60, 80, 100]
        if total_wks in milestones:
            track_name = e.get("track_name", "")
            artist_name = e.get("artist_name", "")
            if total_wks == 52:
                label = _pick("ONE YEAR ON CHART:", "CHARTSVERSARY:", "52 WEEKS:")
                body = _pick(
                    f"'{track_name}' by {artist_name} marks a full year on the Hot 100.",
                    f"Happy chartiversary: '{track_name}' by {artist_name} has now spent 52 weeks (1 year) on the Hot 100.",
                )
            else:
                label = _pick("LONGEVITY:", "CHART VETERAN:", "MILESTONE:")
                body = _pick(
                    f"'{track_name}' by {artist_name} reaches {total_wks} weeks on the Hot 100.",
                    f"'{track_name}' by {artist_name} hits {total_wks} weeks on the chart.",
                )
            return CommunityPost(
                id=_make_id("talk", "longevity", str(tid), str(total_wks)),
                account_handle="@talkofthecharts",
                posted_at=posted_at,
                content=f"{label} {body}",
                post_type=PostType.ALL_TIME_STATS.value,
                linked_entities=[
                    {"type": "track", "id": tid, "name": track_name},
                    {"type": "artist", "name": artist_name},
                ],
                tags=["milestone", "longevity"],
                significance=0.28,
            )
    return None


# ──────────────── @recordwatch expanded — more record types ────────────────


def _gen_record_self_replacement(
    entries: list[dict],
    prev_entries: list[dict] | None,
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@recordwatch: self-replacement — same artist replaces themselves at #1."""
    if not prev_entries:
        return None

    no1 = next((e for e in entries if e.get("rank") == 1), None)
    prev_no1 = next((e for e in prev_entries if e.get("rank") == 1), None)
    if not no1 or not prev_no1:
        return None

    if no1.get("artist_name") == prev_no1.get("artist_name") and no1.get(
        "track_id"
    ) != prev_no1.get("track_id"):
        artist = no1.get("artist_name", "")
        new_track = no1.get("track_name", "")
        old_track = prev_no1.get("track_name", "")

        label = _pick("SELF-REPLACEMENT:", "PASSING THE TORCH:", "ONE-TWO PUNCH:")
        body = _pick(
            f"{artist} replaces themselves at #1 — '{new_track}' takes over from '{old_track}'.",
            f"{artist} does it again: '{new_track}' succeeds '{old_track}' at #1, keeping the crown in-house.",
            f"A {artist} takeover: '{new_track}' replaces '{old_track}' at the top.",
        )
        return CommunityPost(
            id=_make_id("record", "self_replace", week_label, str(no1.get("track_id"))),
            account_handle="@recordwatch",
            posted_at=posted_at,
            content=f"{label} {body}",
            post_type=PostType.RECORD_BROKEN.value,
            linked_entities=[
                {"type": "track", "id": no1.get("track_id"), "name": new_track},
                {"type": "artist", "name": artist},
            ],
            tags=["record", "milestone"],
            significance=0.62,
        )
    return None


def _gen_record_triple_no1(
    entries: list[dict],
    album_entries: list[dict],
    artist_entries: list[dict],
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@recordwatch: triple #1 — same artist dominates all three charts in one week."""
    track_no1 = next((e for e in entries if e.get("rank") == 1), None)
    album_no1 = next((e for e in album_entries if e.get("rank") == 1), None)
    artist_no1 = next((e for e in artist_entries if e.get("rank") == 1), None)

    if not track_no1 or not album_no1 or not artist_no1:
        return None

    # Check if same artist holds #1 on all 3 charts
    track_artist = track_no1.get("artist_name", "")
    album_artist = album_no1.get("artist_name", "")
    chart_artist = artist_no1.get("artist_name", "")

    if track_artist == album_artist == chart_artist:
        label = _pick("TRIPLE CROWN:", "CLEAN SWEEP:", "TOTAL DOMINANCE:")
        body = _pick(
            f"{track_artist} sweeps all three charts — #1 on Hot 100 ('{track_no1.get('track_name', '')}'), Billboard 200 ('{album_no1.get('album_name', '')}'), and Artist 100.",
            f"Unprecedented: {track_artist} holds #1 on the Hot 100, Billboard 200, and Artist 100 simultaneously.",
            f"A {track_artist} clean sweep: #1 across the Hot 100, Billboard 200, and Artist 100.",
        )
        return CommunityPost(
            id=_make_id("record", "triple_no1", week_label),
            account_handle="@recordwatch",
            posted_at=posted_at,
            content=f"{label} {body}",
            post_type=PostType.RECORD_BROKEN.value,
            linked_entities=[
                {
                    "type": "track",
                    "id": track_no1.get("track_id"),
                    "name": track_no1.get("track_name", ""),
                },
                {"type": "album", "name": album_no1.get("album_name", "")},
                {"type": "artist", "name": track_artist},
            ],
            tags=["record", "milestone"],
            significance=0.85,
        )
    return None


def _gen_record_concurrent_entries(
    entries: list[dict],
    posted_at: str,
    week_label: str,
    *,
    track_most_concurrent: int,
    track_most_concurrent_artist: str,
) -> CommunityPost | None:
    """@recordwatch: most concurrent chart entries by an artist."""
    artist_counts: dict[str, int] = {}
    for e in entries:
        artist = e.get("artist_name", "")
        artist_counts[artist] = artist_counts.get(artist, 0) + 1

    for artist, count in sorted(artist_counts.items(), key=lambda x: x[1], reverse=True):
        if count > track_most_concurrent and count >= 4:
            label = _pick("CHART FLOOD:", "TAKEOVER:", "DOMINANCE:")
            body = _pick(
                f"{artist} has {count} songs on the chart this week — the most by any artist in a single week.",
                f"{artist} floods the Hot 100 with {count} entries this week, a new era record.",
            )
            prev = (
                f" Previous best: {track_most_concurrent_artist} ({track_most_concurrent})."
                if track_most_concurrent_artist
                else ""
            )
            return CommunityPost(
                id=_make_id("record", "concurrent", week_label, artist),
                account_handle="@recordwatch",
                posted_at=posted_at,
                content=f"{label} {body}{prev}",
                post_type=PostType.RECORD_BROKEN.value,
                linked_entities=[{"type": "artist", "name": artist}],
                tags=["record", "milestone"],
                significance=0.58,
            )
    return None


# ──────────────── @chartdata / @popcrave / @debutwatch expanded ────────────────


def _gen_biggest_drop_post(
    entries: list[dict],
    prev_entries: list[dict] | None,
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@chartdata: biggest rank drop of the week."""
    if not prev_entries:
        return None
    prev_map = {e.get("track_id"): e.get("rank", 999) for e in prev_entries if e.get("track_id")}
    worst_drop = None
    worst_delta = 0
    for e in entries:
        tid = e.get("track_id")
        if tid and tid in prev_map:
            delta = e.get("rank", 999) - prev_map[tid]
            if delta > worst_delta:
                worst_delta = delta
                worst_drop = e
    if worst_drop and worst_delta >= 10:
        verb = _pick("plummets", "slides", "drops", "falls", "tumbles")
        label = _pick(
            "Biggest drop this week:", "Biggest fall this week:", "Largest slide this week:"
        )
        content = (
            f"{label} {worst_drop.get('track_name', '')} by {worst_drop.get('artist_name', '')} "
            f"{verb} {prev_map[worst_drop['track_id']]}-{worst_drop['rank']} (-{worst_delta})."
        )
        return CommunityPost(
            id=_make_id("drop", week_label, str(worst_drop.get("track_id"))),
            account_handle="@chartdata",
            posted_at=posted_at,
            content=content,
            post_type=PostType.BIGGEST_JUMP.value,
            linked_entities=[
                {
                    "type": "track",
                    "id": worst_drop.get("track_id"),
                    "name": worst_drop.get("track_name", ""),
                },
                {"type": "artist", "name": worst_drop.get("artist_name", "")},
            ],
            tags=["weekly", "movement"],
            significance=0.25,
        )
    return None


def _gen_artist_first_top10(
    entries: list[dict],
    state: HistoricalState,
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@popcrave: artist achieves first top 10 entry."""
    for e in entries:
        rank = e.get("rank", 999)
        if rank > 10:
            continue
        artist = e.get("artist_name", "")
        if state.artist_top10_count.get(artist, 0) == 0:
            track_name = e.get("track_name", "")
            label = _pick("FIRST TOP 10:", "BREAKTHROUGH:", "WELCOME TO THE TOP 10:")
            body = _pick(
                f"{artist} earns their first Hot 100 top 10 with '{track_name}' (#{rank}).",
                f"'{track_name}' gives {artist} their first top 10 hit (#{rank}).",
                f"{artist} breaks into the top 10 for the first time — '{track_name}' lands at #{rank}.",
            )
            return CommunityPost(
                id=_make_id("first_top10", artist, week_label),
                account_handle="@popcrave",
                posted_at=posted_at,
                content=f"{label} {body}",
                post_type=PostType.ARTIST_MILESTONE.value,
                linked_entities=[
                    {"type": "track", "id": e.get("track_id"), "name": track_name},
                    {"type": "artist", "name": artist},
                ],
                tags=["milestone", "artist"],
                significance=0.52,
            )
    return None


def _gen_top5_debut(
    entries: list[dict],
    state: HistoricalState,
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@debutwatch: top 5 debut highlight — separate from general debut roundup."""
    for e in entries:
        rank = e.get("rank", 999)
        if rank > 5:
            continue
        tid = e.get("track_id")
        if tid and tid not in state.track_debut_week:
            track_name = e.get("track_name", "")
            artist_name = e.get("artist_name", "")
            if rank == 1:
                return None  # Already covered by #1 announcement
            label = _pick("HIGH DEBUT:", "STRONG START:", "TOP 5 ENTRY:")
            body = _pick(
                f"'{track_name}' by {artist_name} enters straight at #{rank}.",
                f"{artist_name}'s '{track_name}' debuts at #{rank} on the Hot 100.",
                f"Impressive debut: '{track_name}' by {artist_name} opens at #{rank}.",
            )
            return CommunityPost(
                id=_make_id("top5_debut", week_label, str(tid)),
                account_handle="@debutwatch",
                posted_at=posted_at,
                content=f"{label} {body}",
                post_type=PostType.NEW_ENTRIES_ROUNDUP.value,
                linked_entities=[
                    {"type": "track", "id": tid, "name": track_name},
                    {"type": "artist", "name": artist_name},
                ],
                tags=["debut", "weekly"],
                significance=0.38,
            )
    return None


# ──────────────── @chartstats / @talkofthecharts — 实时总榜（真实 Power Score）────────────────
#
# Uses chart_power_score's exact formula, computed incrementally during iteration.
# global_baseline is the median of all week-totals seen so far — time-capsule
# correct (posts at week N don't know about weeks N+1 and beyond).
# At the end of the era, scores match the real power_score except for the
# baseline convergence — which is the intended behaviour for historical posts.


def _base_score(rank: int) -> float:
    """Real power score base: max(1, round(RANK1_BASE * DECAY^(rank-1)))."""
    return max(1.0, round(_RANK1_BASE * (_BASE_DECAY ** (rank - 1))))


def _comp_factor(week_total: float, global_baseline: float) -> float:
    """Competition factor: clamp(sqrt(week_total / baseline), 0.7, 1.5)."""
    if not global_baseline or global_baseline <= 0:
        return 1.0
    ratio = week_total / global_baseline
    return max(_COMP_RANGE[0], min(_COMP_RANGE[1], ratio**0.5))


def _indiv_factor(rank: int, plays: float, runner_up: float, week_median: float) -> float:
    """Individual dominance factor — identical to chart_power_score logic."""
    if rank == 1:
        if not runner_up or runner_up <= 0:
            return 1.0 + _INDIV_GAP_RANGE[1]
        ratio = plays / runner_up
        bonus = 0.5 * math.log2(ratio) if ratio > 0 else 0
        return 1.0 + max(_INDIV_GAP_RANGE[0], min(_INDIV_GAP_RANGE[1], bonus))
    else:
        if not week_median or week_median <= 0:
            return 1.0
        ratio = plays / week_median
        bonus = 0.4 * math.log2(ratio) if ratio > 0 else 0
        return 1.0 + max(_INDIV_RANGE[0], min(_INDIV_RANGE[1], bonus))


def _compute_real_power_score(
    track_id: int,
    raw_score_sum: dict[int, float],
    track_weeks_on_chart: dict[int, int],
    track_peak_rank: dict[int, int],
    track_is_debut_no1: dict[int, bool],
    track_top5_weeks: dict[int, int],
    track_top10_weeks: dict[int, int],
) -> float:
    """Compute the real power score from accumulated components."""
    raw = raw_score_sum.get(track_id, 0.0)
    weeks = track_weeks_on_chart.get(track_id, 0)
    peak = track_peak_rank.get(track_id, 999)
    debut_bonus = _DEBUT_NO1_BONUS if track_is_debut_no1.get(track_id, False) else 0
    peak_bonus = _PEAK_BONUS.get(peak, 0)
    longevity = (weeks**0.5) * _LONGEVITY_FACTOR if weeks > 0 else 0.0
    top5_bonus = track_top5_weeks.get(track_id, 0) * _TOP5_BONUS
    top10_bonus = track_top10_weeks.get(track_id, 0) * _TOP10_BONUS
    return raw + longevity + peak_bonus + debut_bonus + top5_bonus + top10_bonus


def _make_alltime_ranking(
    raw_score_sum: dict[int, float],
    track_weeks_on_chart: dict[int, int],
    track_peak_rank: dict[int, int],
    track_is_debut_no1: dict[int, bool],
    track_top5_weeks: dict[int, int],
    track_top10_weeks: dict[int, int],
    top_n: int = 30,
) -> list[tuple[int, float]]:
    """Build sorted all-time ranking from power-score component dicts."""
    all_tids = set(raw_score_sum.keys())
    scored = [
        (
            tid,
            _compute_real_power_score(
                tid,
                raw_score_sum,
                track_weeks_on_chart,
                track_peak_rank,
                track_is_debut_no1,
                track_top5_weeks,
                track_top10_weeks,
            ),
        )
        for tid in all_tids
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def _gen_alltime_ranking_posts(
    entries: list[dict],
    raw_score_sum: dict[int, float],
    track_weeks_on_chart: dict[int, int],
    track_peak_rank: dict[int, int],
    track_is_debut_no1: dict[int, bool],
    track_top5_weeks: dict[int, int],
    track_top10_weeks: dict[int, int],
    prev_top_ids: list[int],
    posted_at: str,
    week_label: str,
) -> tuple[list[CommunityPost], list[int]]:
    """@chartstats / @talkofthecharts: all-time ranking movement posts.

    Uses real power scores computed incrementally each week. Detects:
    new #1, entries to top 10, and big jumps within top 20.
    """
    posts: list[CommunityPost] = []

    new_top = _make_alltime_ranking(
        raw_score_sum,
        track_weeks_on_chart,
        track_peak_rank,
        track_is_debut_no1,
        track_top5_weeks,
        track_top10_weeks,
        30,
    )
    new_top_ids = [tid for tid, _ in new_top]
    new_rank_map = {tid: i + 1 for i, (tid, _) in enumerate(new_top)}
    prev_rank_map = {tid: i + 1 for i, tid in enumerate(prev_top_ids)} if prev_top_ids else {}

    if not prev_top_ids:
        return posts, new_top_ids

    # 1. New #1 on all-time ranking
    if new_top_ids and prev_top_ids and new_top_ids[0] != prev_top_ids[0]:
        new_no1_tid = new_top_ids[0]
        new_no1_score = new_top[0][1]
        for e in entries:
            if e.get("track_id") == new_no1_tid:
                label = _pick("NEW ALL-TIME #1:", "ALL-TIME CROWN CHANGE:", "HISTORIC MOMENT:")
                body = _pick(
                    f"'{e.get('track_name', '')}' by {e.get('artist_name', '')} becomes the #1 track of the era ({new_no1_score:.0f} pts).",
                    f"The era has a new all-time #1: '{e.get('track_name', '')}' by {e.get('artist_name', '')} ({new_no1_score:.0f} pts).",
                )
                posts.append(
                    CommunityPost(
                        id=_make_id("alltime", "new_no1", week_label),
                        account_handle="@talkofthecharts",
                        posted_at=posted_at,
                        content=f"{label} {body}",
                        post_type=PostType.ALL_TIME_STATS.value,
                        linked_entities=[
                            {"type": "track", "id": new_no1_tid, "name": e.get("track_name", "")},
                            {"type": "artist", "name": e.get("artist_name", "")},
                        ],
                        tags=["alltime", "ranking"],
                        significance=0.72,
                    )
                )
                break

    # 2. New entries to top 10 all-time
    for tid, score in new_top[:10]:
        if tid not in prev_rank_map or prev_rank_map[tid] > 10:
            new_rank = new_rank_map[tid]
            track_name = ""
            artist_name = ""
            for e in entries:
                if e.get("track_id") == tid:
                    track_name = e.get("track_name", "")
                    artist_name = e.get("artist_name", "")
                    break
            if not track_name:
                continue
            label = _pick("ALL-TIME TOP 10:", "ENTERS THE ELITE:", "HISTORIC ENTRY:")
            prev_info = f" (up from #{prev_rank_map[tid]})" if tid in prev_rank_map else ""
            body = _pick(
                f"'{track_name}' by {artist_name} breaks into the all-time top 10 at #{new_rank}{prev_info}.",
                f"'{track_name}' by {artist_name} cracks the era's all-time top 10 — now #{new_rank}{prev_info}.",
            )
            posts.append(
                CommunityPost(
                    id=_make_id("alltime", "top10_entry", str(tid), week_label),
                    account_handle="@chartstats",
                    posted_at=posted_at,
                    content=f"{label} {body}",
                    post_type=PostType.ALL_TIME_STATS.value,
                    linked_entities=[
                        {"type": "track", "id": tid, "name": track_name},
                        {"type": "artist", "name": artist_name},
                    ],
                    tags=["alltime", "ranking"],
                    significance=0.48,
                )
            )

    # 3. Big jumps within top 20 (+5 or more spots)
    for tid, _ in new_top[:20]:
        if tid in prev_rank_map and tid in new_rank_map:
            old_r = prev_rank_map[tid]
            new_r = new_rank_map[tid]
            jump = old_r - new_r
            if jump >= 5:
                track_name = ""
                artist_name = ""
                for e in entries:
                    if e.get("track_id") == tid:
                        track_name = e.get("track_name", "")
                        artist_name = e.get("artist_name", "")
                        break
                if not track_name:
                    continue
                label = _pick("ALL-TIME CLIMBER:", "RISING:", "ON THE RISE:")
                body = _pick(
                    f"'{track_name}' by {artist_name} leaps {jump} spots to #{new_r} on the all-time ranking.",
                    f"'{track_name}' by {artist_name} surges from #{old_r} to #{new_r} (+{jump}) on the era's all-time chart.",
                )
                posts.append(
                    CommunityPost(
                        id=_make_id("alltime", "jump", str(tid), str(jump), week_label),
                        account_handle="@chartstats",
                        posted_at=posted_at,
                        content=f"{label} {body}",
                        post_type=PostType.ALL_TIME_STATS.value,
                        linked_entities=[
                            {"type": "track", "id": tid, "name": track_name},
                            {"type": "artist", "name": artist_name},
                        ],
                        tags=["alltime", "ranking"],
                        significance=0.35,
                    )
                )

    return posts, new_top_ids


def _gen_album_no1_post(
    album_entries: list[dict],
    prev_album_entries: list[dict] | None,
    album_debut_set: set[str],
    album_weeks_at_no1: dict[str, int],
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@billboardcharts: Billboard 200 #1 album announcement.

    Same four-category logic as track #1 posts:
      - #1(new): album debuts on the chart at #1
      - #1(+N): album climbs N spots to #1
      - #1(re): album re-enters the chart at #1 after falling off
      - #1(=): album stays at #1 for a consecutive week
    """
    no1 = next((e for e in album_entries if e.get("rank") == 1), None)
    if not no1:
        return None

    album_name = no1.get("album_name", "")
    artist_name = no1.get("artist_name", "")
    album_key = f"{album_name}|{artist_name}"

    in_debut_week = album_key not in album_debut_set

    prev_rank_map: dict[str, int] = {}
    if prev_album_entries:
        prev_rank_map = {
            f"{e.get('album_name', '')}|{e.get('artist_name', '')}": e.get("rank", 999)
            for e in prev_album_entries
        }

    prev_rank = prev_rank_map.get(album_key)
    in_prev_week = prev_rank is not None
    was_no1_last_week = prev_rank == 1

    if in_debut_week:
        verb = _pick(
            "debuts at #1.", "enters straight at #1.", "opens at the top spot.", "arrives at #1."
        )
        content = f"Billboard 200: #1(new) {album_name} by {artist_name} {verb}"
        significance = 0.55
    elif was_no1_last_week:
        total_weeks = album_weeks_at_no1.get(album_key, 0) + 1
        body = _pick(
            f"holds at #1 for a {_fmt_ordinal(total_weeks)} week.",
            f"spends a {_fmt_ordinal(total_weeks)} week atop the chart.",
            f"notches a {_fmt_ordinal(total_weeks)} week at #1.",
        )
        content = f"Billboard 200: #1(=) {album_name} by {artist_name} {body}"
        significance = 0.40
    elif in_prev_week:
        jump = prev_rank - 1
        total_weeks = album_weeks_at_no1.get(album_key, 0) + 1
        verb = _pick("climbs", "rises", "jumps")
        extra = _pick(
            f" ({_fmt_ordinal(total_weeks)} week at #1).",
            f" ({_fmt_ordinal(total_weeks)} wk at #1).",
            ".",
        )
        content = (
            f"Billboard 200: #1(+{jump}) {album_name} by {artist_name} {verb} {prev_rank}-1{extra}"
        )
        significance = 0.50
    else:
        total_weeks = album_weeks_at_no1.get(album_key, 0) + 1
        body = _pick(
            f"re-enters at #1 ({_fmt_ordinal(total_weeks)} week at #1).",
            f"storms back in at #1 ({_fmt_ordinal(total_weeks)} week at #1).",
            f"makes a comeback at #1 ({_fmt_ordinal(total_weeks)} week at #1).",
        )
        content = f"Billboard 200: #1(re) {album_name} by {artist_name} {body}"
        significance = 0.48

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
        significance=significance,
    )


def _gen_artist_no1_post(
    artist_entries: list[dict],
    prev_artist_entries: list[dict] | None,
    artist_debut_set: set[str],
    artist_weeks_at_no1: dict[str, int],
    posted_at: str,
    week_label: str,
) -> CommunityPost | None:
    """@chartdata: Artist 100 #1 announcement.

    Same four-category logic:
      - #1(new): artist appears on the chart for the first time at #1
      - #1(+N): artist climbs N spots to #1
      - #1(re): artist re-enters the chart at #1 after falling off
      - #1(=): artist stays at #1 for a consecutive week
    """
    no1 = next((e for e in artist_entries if e.get("rank") == 1), None)
    if not no1:
        return None

    artist_name = no1.get("artist_name", "")
    play_count = no1.get("play_count", 0)

    in_debut_week = artist_name not in artist_debut_set

    prev_rank_map: dict[str, int] = {}
    if prev_artist_entries:
        prev_rank_map = {e.get("artist_name", ""): e.get("rank", 999) for e in prev_artist_entries}

    prev_rank = prev_rank_map.get(artist_name)
    in_prev_week = prev_rank is not None
    was_no1_last_week = prev_rank == 1

    if in_debut_week:
        verb = _pick(
            "Debuts at #1.", "Opens at the top.", "Arrives at #1.", "Enters straight at #1."
        )
        content = f"Artist 100: #1(new) {artist_name} ({play_count:,} plays this week). {verb}"
        significance = 0.50
    elif was_no1_last_week:
        total_weeks = artist_weeks_at_no1.get(artist_name, 0) + 1
        body = _pick(
            f"— {_fmt_ordinal(total_weeks)} week.",
            f"reigns for a {_fmt_ordinal(total_weeks)} week.",
            f"holds the top spot for a {_fmt_ordinal(total_weeks)} week.",
        )
        content = f"Artist 100: #1(=) {artist_name} ({play_count:,} plays this week) {body}"
        significance = 0.35
    elif in_prev_week:
        jump = prev_rank - 1
        total_weeks = artist_weeks_at_no1.get(artist_name, 0) + 1
        verb = _pick("Climbs", "Rises", "Jumps")
        extra = _pick(
            f" ({_fmt_ordinal(total_weeks)} week at #1).",
            f" ({_fmt_ordinal(total_weeks)} wk at #1).",
            ".",
        )
        content = f"Artist 100: #1(+{jump}) {artist_name} ({play_count:,} plays this week). {verb} {prev_rank}-1{extra}"
        significance = 0.45
    else:
        total_weeks = artist_weeks_at_no1.get(artist_name, 0) + 1
        body = _pick(
            f"Re-enters at #1 ({_fmt_ordinal(total_weeks)} week at #1).",
            f"Storms back in at #1 ({_fmt_ordinal(total_weeks)} week at #1).",
            f"Makes a comeback at #1 ({_fmt_ordinal(total_weeks)} week at #1).",
        )
        content = f"Artist 100: #1(re) {artist_name} ({play_count:,} plays this week). {body}"
        significance = 0.42

    return CommunityPost(
        id=_make_id("artist", "no1", week_label),
        account_handle="@chartdata",
        posted_at=posted_at,
        content=content,
        post_type=PostType.NO1_ANNOUNCEMENT.value,
        linked_entities=[{"type": "artist", "name": artist_name}],
        tags=["weekly", "artist", "no1"],
        significance=significance,
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


def _gen_alltime_ranking_summary(
    raw_score_sum: dict[int, float],
    track_weeks_on_chart: dict[int, int],
    track_peak_rank: dict[int, int],
    track_is_debut_no1: dict[int, bool],
    track_top5_weeks: dict[int, int],
    track_top10_weeks: dict[int, int],
    state: HistoricalState,
    weekly,
    posted_at: str,
) -> list[CommunityPost]:
    """@chartstats: end-of-era all-time ranking summary using real Power Scores."""
    posts: list[CommunityPost] = []
    if not raw_score_sum:
        return posts

    top = _make_alltime_ranking(
        raw_score_sum,
        track_weeks_on_chart,
        track_peak_rank,
        track_is_debut_no1,
        track_top5_weeks,
        track_top10_weeks,
        20,
    )
    if len(top) < 5:
        return posts

    # Build track_id -> (name, artist) lookup from weekly data
    track_info: dict[int, tuple[str, str]] = {}
    if weekly is not None:
        for _, row in weekly.iterrows():
            tid = int(row.get("track_id", 0))
            if tid and tid not in track_info:
                track_info[tid] = (str(row.get("track_name", "")), str(row.get("artist_name", "")))

    # 1. Top 10 all-time tracks
    top10 = []
    for tid, score in top[:10]:
        name, artist = track_info.get(tid, ("?", "?"))
        top10.append(f"{name} — {artist} ({score:.0f} pts)")

    header = _pick(
        "Era All-Time Top 10 (by Power Score):",
        "The era's 10 greatest hits — Power Score ranking:",
        "All-Time Hot 100 — End of Era Top 10:",
    )
    content = f"{header}\n\n" + "\n".join(f"{i + 1}. {line}" for i, line in enumerate(top10))
    posts.append(
        CommunityPost(
            id=_make_id("alltime", "top10_summary"),
            account_handle="@chartstats",
            posted_at=posted_at,
            content=content,
            post_type=PostType.ALL_TIME_STATS.value,
            tags=["alltime", "ranking"],
            significance=0.65,
        )
    )

    # 2. Top 5 artists by combined track Power Scores
    artist_scores: dict[str, float] = {}
    for tid, score in top:
        info = track_info.get(tid)
        if info:
            artist = info[1]
            artist_scores[artist] = artist_scores.get(artist, 0.0) + score

    top_artists = sorted(artist_scores.items(), key=lambda x: x[1], reverse=True)[:5]
    if len(top_artists) >= 3:
        artist_lines = []
        for i, (artist, score) in enumerate(top_artists):
            no1_count = state.artist_no1_count_as_of(artist)
            extra = f" ({no1_count} #1s)" if no1_count > 0 else ""
            artist_lines.append(f"{artist} — {score:.0f} pts{extra}")
        a_header = _pick(
            "Era's Most Dominant Artists (combined Power Score):",
            "Top Artists of the Era — Power Score:",
            "The era's chart powerhouses:",
        )
        posts.append(
            CommunityPost(
                id=_make_id("alltime", "top_artists"),
                account_handle="@chartstats",
                posted_at=posted_at,
                content=f"{a_header}\n\n"
                + "\n".join(f"{i + 1}. {line}" for i, line in enumerate(artist_lines)),
                post_type=PostType.ALL_TIME_STATS.value,
                linked_entities=[{"type": "artist", "name": a} for a, _ in top_artists],
                tags=["alltime", "artist", "ranking"],
                significance=0.55,
            )
        )

    # 3. Efficiency: highest score per week on chart
    efficiency = []
    for tid, score in top[:30]:
        weeks = track_weeks_on_chart.get(tid, 0)
        if weeks >= 5:
            efficiency.append((tid, score / weeks, score, weeks))
    efficiency.sort(key=lambda x: x[1], reverse=True)
    if efficiency:
        top_eff = efficiency[:3]
        names = []
        for tid, rate, score, weeks in top_eff:
            info = track_info.get(tid, ("?", "?"))
            names.append(f"'{info[0]}' by {info[1]} ({rate:.1f} pts/wk, {weeks}wks)")
        eff_header = _pick(
            "Most Efficient Chart Runs (Power Score/wk, min 5 weeks):",
            "Pound-for-Pound Chart Leaders:",
            "Best Per-Week Chart Performances:",
        )
        posts.append(
            CommunityPost(
                id=_make_id("alltime", "efficiency"),
                account_handle="@chartstats",
                posted_at=posted_at,
                content=f"{eff_header}\n\n"
                + "\n".join(f"{i + 1}. {line}" for i, line in enumerate(names)),
                post_type=PostType.ALL_TIME_STATS.value,
                tags=["alltime", "stat"],
                significance=0.42,
            )
        )

    return posts


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
    prev_album_entries: list[dict] | None = None
    prev_artist_entries: list[dict] | None = None
    album_debut_set: set[str] = set()
    artist_debut_set: set[str] = set()
    album_weeks_at_no1: dict[str, int] = {}
    artist_weeks_at_no1: dict[str, int] = {}

    # ── multi-chart record tracking ──
    # Album chart records
    album_longest_no1_weeks: int = 0
    album_longest_no1_name: str = ""
    album_longest_no1_artist: str = ""
    album_most_no1s_count: int = 0
    album_most_no1s_artist: str = ""
    # Artist chart records
    artist_chart_longest_no1_weeks: int = 0
    artist_chart_longest_no1_name: str = ""
    artist_chart_most_no1_weeks_count: int = 0
    artist_chart_most_no1_weeks_name: str = ""
    # Track extra records (longest #1 tracked by HistoricalState)
    track_most_career_no1_weeks: int = 0
    track_most_career_no1_weeks_artist: str = ""
    track_most_concurrent_top10: int = 0
    track_most_concurrent_top10_artist: str = ""
    track_most_concurrent_entries: int = 0
    track_most_concurrent_entries_artist: str = ""
    # All-time ranking tracker (real power score components, computed incrementally)
    raw_score_sum: dict[int, float] = {}
    track_top5_weeks: dict[int, int] = {}
    track_top10_weeks: dict[int, int] = {}
    track_is_debut_no1: dict[int, bool] = {}
    all_week_totals: list[float] = []  # for rolling global_baseline (median)
    prev_alltime_top_ids: list[int] = []
    monthly_snapshots: list[tuple[str, str, HistoricalState]] = []
    quarterly_snapshots: list[tuple[str, str, HistoricalState]] = []
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

        posts.extend(_gen_no1_posts(entries, prev_week_entries, state, posted_at, week_label))

        top10 = _gen_top10_summary(entries, state, posted_at, week_label)
        if top10:
            posts.append(top10)

        posts.extend(_gen_debut_posts(entries, state, posted_at, week_label))

        jump = _gen_biggest_jump_post(entries, prev_week_entries, posted_at, week_label)
        if jump:
            posts.append(jump)

        posts.extend(
            _gen_record_posts(
                entries,
                state,
                posted_at,
                week_label,
                track_most_career_weeks=track_most_career_no1_weeks,
                track_most_career_weeks_artist=track_most_career_no1_weeks_artist,
                track_most_top10=track_most_concurrent_top10,
                track_most_top10_artist=track_most_concurrent_top10_artist,
            )
        )
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

        # @talkofthecharts — deep stats
        tcr = _gen_talk_weekly_race(entries, posted_at, week_label)
        if tcr:
            posts.append(tcr)

        tmo = _gen_talk_market_overview(entries, prev_week_entries, state, posted_at, week_label)
        if tmo:
            posts.append(tmo)

        tla = _gen_talk_longevity_alert(entries, state, posted_at, week_label)
        if tla:
            posts.append(tla)

        # @chartstats / @talkofthecharts — all-time ranking movement (real power scores)
        # 1. Compute this week's power score components
        week_total_plays = sum(e.get("play_count", 0) for e in entries)
        week_median_plays = (
            sorted([e.get("play_count", 0) for e in entries])[len(entries) // 2] if entries else 0.0
        )
        runner_up_plays = next((e.get("play_count", 0) for e in entries if e.get("rank") == 2), 0.0)
        all_week_totals.append(week_total_plays)
        mid = len(all_week_totals) // 2
        global_baseline = sorted(all_week_totals)[mid] if all_week_totals else 1.0
        comp = _comp_factor(week_total_plays, global_baseline)

        for e in entries:
            tid = e.get("track_id")
            if tid is None:
                continue
            rank = e.get("rank", 999)
            plays = e.get("play_count", 0)
            indiv = _indiv_factor(rank, plays, runner_up_plays, week_median_plays)
            raw_score_sum[tid] = raw_score_sum.get(tid, 0.0) + _base_score(rank) * comp * indiv
            if rank <= 5:
                track_top5_weeks[tid] = track_top5_weeks.get(tid, 0) + 1
            if rank <= 10:
                track_top10_weeks[tid] = track_top10_weeks.get(tid, 0) + 1
            if tid not in track_is_debut_no1:
                track_is_debut_no1[tid] = rank == 1

        # 2. Detect ranking changes
        at_posts, new_top_ids = _gen_alltime_ranking_posts(
            entries,
            raw_score_sum,
            state.track_total_weeks,
            state.track_peak_rank,
            track_is_debut_no1,
            track_top5_weeks,
            track_top10_weeks,
            prev_alltime_top_ids,
            posted_at,
            week_label,
        )
        posts.extend(at_posts)
        prev_alltime_top_ids = new_top_ids

        # @recordwatch — self-replacement
        srep = _gen_record_self_replacement(entries, prev_week_entries, posted_at, week_label)
        if srep:
            posts.append(srep)

        # @chartdata — biggest drop
        drop = _gen_biggest_drop_post(entries, prev_week_entries, posted_at, week_label)
        if drop:
            posts.append(drop)

        # @popcrave — first top 10
        ft10 = _gen_artist_first_top10(entries, state, posted_at, week_label)
        if ft10:
            posts.append(ft10)

        # @debutwatch — top 5 debut
        t5d = _gen_top5_debut(entries, state, posted_at, week_label)
        if t5d:
            posts.append(t5d)

        # Album chart #1
        album_entries = _album_entries_for_week(weekly_album, week_val)
        an1 = _gen_album_no1_post(
            album_entries,
            prev_album_entries,
            album_debut_set,
            album_weeks_at_no1,
            posted_at,
            week_label,
        )
        if an1:
            posts.append(an1)

        # Artist chart #1
        artist_entries = _artist_entries_for_week(weekly_artist, week_val)
        arn1 = _gen_artist_no1_post(
            artist_entries,
            prev_artist_entries,
            artist_debut_set,
            artist_weeks_at_no1,
            posted_at,
            week_label,
        )
        if arn1:
            posts.append(arn1)

        # Multi-chart record posts
        posts.extend(
            _gen_album_record_posts(
                album_entries,
                album_weeks_at_no1,
                posted_at,
                week_label,
                album_longest_no1_weeks=album_longest_no1_weeks,
                album_longest_no1_name=album_longest_no1_name,
                album_longest_no1_artist=album_longest_no1_artist,
                album_most_no1s_count=album_most_no1s_count,
                album_most_no1s_artist=album_most_no1s_artist,
            )
        )
        posts.extend(
            _gen_artist_chart_record_posts(
                artist_entries,
                artist_weeks_at_no1,
                posted_at,
                week_label,
                artist_chart_longest_no1_weeks=artist_chart_longest_no1_weeks,
                artist_chart_longest_no1_name=artist_chart_longest_no1_name,
                artist_chart_most_no1_weeks_count=artist_chart_most_no1_weeks_count,
                artist_chart_most_no1_weeks_name=artist_chart_most_no1_weeks_name,
            )
        )

        # @recordwatch — triple #1 (all 3 charts)
        tn1 = _gen_record_triple_no1(entries, album_entries, artist_entries, posted_at, week_label)
        if tn1:
            posts.append(tn1)

        # @recordwatch — concurrent entries
        ce = _gen_record_concurrent_entries(
            entries,
            posted_at,
            week_label,
            track_most_concurrent=track_most_concurrent_entries,
            track_most_concurrent_artist=track_most_concurrent_entries_artist,
        )
        if ce:
            posts.append(ce)

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

            quarter_key = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"
            q_existing = [s for s in quarterly_snapshots if s[0] == quarter_key]
            if not q_existing:
                q_snapshot = HistoricalState()
                q_snapshot.cumulative_plays = state.cumulative_plays
                q_snapshot.cumulative_ms = state.cumulative_ms
                q_snapshot.cumulative_tracks = state.cumulative_tracks.copy()
                q_snapshot.cumulative_artists = state.cumulative_artists.copy()
                quarterly_snapshots.append((quarter_key, posted_at, q_snapshot))

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

        # Update album/artist chart history for next week's comparison
        for e in album_entries:
            album_key = f"{e.get('album_name', '')}|{e.get('artist_name', '')}"
            album_debut_set.add(album_key)
            if e.get("rank") == 1:
                album_weeks_at_no1[album_key] = album_weeks_at_no1.get(album_key, 0) + 1
        for e in artist_entries:
            artist_debut_set.add(e.get("artist_name", ""))
            if e.get("rank") == 1:
                artist_weeks_at_no1[e["artist_name"]] = (
                    artist_weeks_at_no1.get(e["artist_name"], 0) + 1
                )
        prev_album_entries = album_entries
        prev_artist_entries = artist_entries

        # ── Update multi-chart record trackers ──
        # Album chart
        for e in album_entries:
            album_key = f"{e.get('album_name', '')}|{e.get('artist_name', '')}"
            awks = album_weeks_at_no1.get(album_key, 0)
            if awks > album_longest_no1_weeks:
                album_longest_no1_weeks = awks
                album_longest_no1_name = e.get("album_name", "")
                album_longest_no1_artist = e.get("artist_name", "")
        album_no1_counts: dict[str, int] = {}
        for key in album_weeks_at_no1:
            parts = key.rsplit("|", 1)
            artist = parts[1] if len(parts) == 2 else ""
            if album_weeks_at_no1[key] > 0:
                album_no1_counts[artist] = album_no1_counts.get(artist, 0) + 1
        for artist, cnt in album_no1_counts.items():
            if cnt > album_most_no1s_count:
                album_most_no1s_count = cnt
                album_most_no1s_artist = artist
        # Artist chart
        for e in artist_entries:
            awk = artist_weeks_at_no1.get(e.get("artist_name", ""), 0)
            if awk > artist_chart_longest_no1_weeks:
                artist_chart_longest_no1_weeks = awk
                artist_chart_longest_no1_name = e.get("artist_name", "")
        for artist, awk in artist_weeks_at_no1.items():
            if awk > artist_chart_most_no1_weeks_count:
                artist_chart_most_no1_weeks_count = awk
                artist_chart_most_no1_weeks_name = artist
        # Track extra records
        for artist, wks in state.artist_no1_weeks.items():
            if wks > track_most_career_no1_weeks:
                track_most_career_no1_weeks = wks
                track_most_career_no1_weeks_artist = artist
        concurrent: dict[str, int] = {}
        for e in entries:
            if e.get("rank", 999) <= 10:
                a = e.get("artist_name", "")
                concurrent[a] = concurrent.get(a, 0) + 1
        for a, cnt in concurrent.items():
            if cnt > track_most_concurrent_top10:
                track_most_concurrent_top10 = cnt
                track_most_concurrent_top10_artist = a
        # Concurrent entries (all ranks)
        concurrent_all: dict[str, int] = {}
        for e in entries:
            a = e.get("artist_name", "")
            concurrent_all[a] = concurrent_all.get(a, 0) + 1
        for a, cnt in concurrent_all.items():
            if cnt > track_most_concurrent_entries:
                track_most_concurrent_entries = cnt
                track_most_concurrent_entries_artist = a

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

    for quarter_key, q_posted_at, q_snap in quarterly_snapshots:
        qp = _gen_quarterly_personal(quarter_key, q_snap, q_posted_at)
        if qp:
            posts.append(qp)

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

    # @chartstats — all-time ranking summary from accumulated scores
    at_summary = _gen_alltime_ranking_summary(
        raw_score_sum,
        state.track_total_weeks,
        state.track_peak_rank,
        track_is_debut_no1,
        track_top5_weeks,
        track_top10_weeks,
        state,
        weekly,
        era_posted_at,
    )
    posts.extend(at_summary)

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

"""Community feed — Record and milestone posts — broken/tied/watch, self-replacement, triple #1."""

from __future__ import annotations

from backend.domains.community.feed_helpers import (
    _fmt_ordinal,
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
                        {
                            "type": "album",
                            "name": album_name,
                            "id": e.get("album_id"),
                            "artist_name": artist_name,
                        },
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
                {
                    "type": "album",
                    "name": album_no1.get("album_name", ""),
                    "id": album_no1.get("album_id"),
                    "artist_name": album_no1.get("artist_name", ""),
                },
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

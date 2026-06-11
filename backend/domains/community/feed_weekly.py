"""Community feed — Weekly dispatch posts — #1 announcements, top 10, debuts, jumps/drops."""

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

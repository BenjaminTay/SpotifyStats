"""Community feed — @talkofthecharts deep analysis posts."""

from __future__ import annotations

from backend.domains.community.feed_helpers import (
    _make_id,
    _pick,
)
from backend.domains.community.historical_state import HistoricalState
from backend.domains.community.post_types import (
    CommunityPost,
    PostType,
)

# ──────────────────────────────────────────────


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

"""Community feed — All-time ranking and Power Score posts."""

from __future__ import annotations

import math

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

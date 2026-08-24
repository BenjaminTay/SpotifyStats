"""Community feed generator — orchestrates chronological chart iteration and delegates
to sub-module generators for each post type."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from backend.core.cache import singleflight, ttl_cached
from backend.domains.community.accounts import ACCOUNT_BY_HANDLE
from backend.domains.community.feed_data import (
    _compute_personal_weekly,
    _load_chart_data,
    _load_collection_data,
)
from backend.domains.community.feed_helpers import (
    _album_entries_for_week,
    _artist_entries_for_week,
    _entries_for_week,
    _generate_metrics,
    _week_end_date,
)
from backend.domains.community.feed_images import _enrich_post_images, _load_cover_maps
from backend.domains.community.feed_personal import (
    _gen_collection_milestone,
    _gen_collection_posts,
    _gen_decade_comparison,
    _gen_monthly_personal,
    _gen_playback_milestone,
    _gen_quarterly_personal,
    _gen_throwback_post,
    _gen_weekly_personal,
    _gen_yearly_personal,
)
from backend.domains.community.feed_ranking import (
    _base_score,
    _comp_factor,
    _gen_album_no1_post,
    _gen_alltime_ranking_posts,
    _gen_alltime_ranking_summary,
    _gen_alltime_stats,
    _gen_artist_no1_post,
    _indiv_factor,
)
from backend.domains.community.feed_records import (
    _gen_album_record_posts,
    _gen_artist_chart_record_posts,
    _gen_milestone_posts,
    _gen_record_concurrent_entries,
    _gen_record_posts,
    _gen_record_self_replacement,
    _gen_record_tied_posts,
    _gen_record_triple_no1,
    _gen_record_watch_posts,
)
from backend.domains.community.feed_talk import (
    _gen_talk_longevity_alert,
    _gen_talk_market_overview,
    _gen_talk_weekly_race,
)
from backend.domains.community.feed_weekly import (
    _gen_artist_first_top10,
    _gen_biggest_drop_post,
    _gen_biggest_jump_post,
    _gen_debut_posts,
    _gen_no1_posts,
    _gen_top5_debut,
    _gen_top10_summary,
)
from backend.domains.community.historical_state import HistoricalState
from backend.domains.community.post_types import CommunityPost


@singleflight
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
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    merge_level: int = 2,
    include_compilations: bool = False,
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
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_level=merge_level,
        include_compilations=include_compilations,
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
            state.update(
                entries,
                personal_plays=personal.get("plays", 0),
                personal_ms=personal.get("ms", 0),
                personal_track_ids=personal.get("track_ids", set()),
                personal_artist_names=personal.get("artist_names", set()),
                personal_top_artist=personal.get("top_artist", ""),
                personal_top_artist_plays=personal.get("top_artist_plays", 0),
            )
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
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    merge_level: int = 2,
    include_compilations: bool = False,
) -> list[CommunityPost]:
    """Main entry point: generate all community posts by iterating chart history.

    Core chart iteration is cached (TTL 10 min). Collection posts, cover images,
    and engagement metrics are enriched fresh on each call.
    """
    if conn is None:
        return []

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
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_level=merge_level,
        include_compilations=include_compilations,
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

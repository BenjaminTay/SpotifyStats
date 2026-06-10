"""Historical state tracker — maintains cumulative chart knowledge through time.

Iterates through chart weeks chronologically, accumulating state so that
posts generated at each week only reference knowledge available up to that
point in time. This ensures posts are "time-capsule" accurate — a 2024 post
cannot predict 2026 events.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HistoricalState:
    """Cumulative chart knowledge up to the current week being processed."""

    # Track-level (keyed by track_id)
    track_debut_week: dict[int, str] = field(default_factory=dict)  # track_id -> week label
    track_peak_rank: dict[int, int] = field(default_factory=dict)  # track_id -> best rank so far
    track_weeks_at_no1: dict[int, int] = field(
        default_factory=dict
    )  # track_id -> cumulative #1 weeks
    track_total_weeks: dict[int, int] = field(
        default_factory=dict
    )  # track_id -> total weeks on chart

    # Artist-level (keyed by artist_name)
    artist_no1_count: dict[str, int] = field(default_factory=dict)  # artist -> cumulative #1 songs
    artist_top10_count: dict[str, int] = field(
        default_factory=dict
    )  # artist -> songs that reached top 10
    artist_top5_count: dict[str, int] = field(
        default_factory=dict
    )  # artist -> songs that reached top 5
    artist_career_weeks: dict[str, int] = field(default_factory=dict)  # artist -> total chart weeks
    artist_first_no1_date: dict[str, str] = field(default_factory=dict)  # artist -> first #1 date
    artist_no1_weeks: dict[str, int] = field(
        default_factory=dict
    )  # artist -> cumulative weeks at #1

    # Track history snapshots (for throwback posts)
    past_no1s: list[dict] = field(
        default_factory=list
    )  # [{week, track_name, artist_name, track_id}]

    # Global records (best values seen up to current week)
    longest_no1_weeks: int = 0
    longest_no1_track_name: str = ""
    longest_no1_artist_name: str = ""
    most_no1_debuts_count: int = 0
    most_no1_debuts_artist: str = ""
    most_concurrent_top10_count: int = 0
    most_concurrent_top10_artist: str = ""
    most_career_no1s_count: int = 0
    most_career_no1s_artist: str = ""
    most_career_top10s_count: int = 0
    most_career_top10s_artist: str = ""

    # Personal stats (cumulative up to this week)
    cumulative_plays: int = 0
    cumulative_ms: int = 0
    cumulative_tracks: set = field(default_factory=set)
    cumulative_artists: set = field(default_factory=set)
    personal_weekly_top_artist: str = ""
    personal_weekly_top_artist_plays: int = 0

    # Current week context
    current_week: str = ""
    current_week_index: int = 0

    # Helper: ordinal suffix
    @staticmethod
    def _ordinal(n: int) -> str:
        if 11 <= n % 100 <= 13:
            return f"{n}th"
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}"

    def _ensure_artist(self, artist_name: str):
        """Initialise artist counters if not yet seen."""
        if artist_name not in self.artist_no1_count:
            self.artist_no1_count[artist_name] = 0
            self.artist_top10_count[artist_name] = 0
            self.artist_top5_count[artist_name] = 0
            self.artist_career_weeks[artist_name] = 0
            self.artist_no1_weeks[artist_name] = 0

    def update(
        self,
        weekly_tracks: list[dict],
        personal_plays: int = 0,
        personal_ms: int = 0,
        personal_track_ids: set | None = None,
        personal_artist_names: set | None = None,
        personal_top_artist: str = "",
        personal_top_artist_plays: int = 0,
    ):
        """Incorporate one week's chart data into cumulative state."""
        self.current_week_index += 1

        for entry in weekly_tracks:
            tid = entry.get("track_id")
            rank = entry.get("rank", 999)
            artist = entry.get("artist_name", "")
            week = entry.get("billboard_week", "")

            if tid is None:
                continue

            # Track stats
            if tid not in self.track_debut_week:
                self.track_debut_week[tid] = week
            self.track_total_weeks[tid] = self.track_total_weeks.get(tid, 0) + 1
            current_peak = self.track_peak_rank.get(tid, 999)
            if rank < current_peak:
                self.track_peak_rank[tid] = rank
            if rank == 1:
                self.track_weeks_at_no1[tid] = self.track_weeks_at_no1.get(tid, 0) + 1
                if week not in {p["week"] for p in self.past_no1s}:
                    self.past_no1s.append(
                        {
                            "week": str(week),
                            "track_name": entry.get("track_name", ""),
                            "artist_name": artist,
                            "track_id": tid,
                        }
                    )

            # Artist stats
            self._ensure_artist(artist)
            self.artist_career_weeks[artist] += 1
            if rank == 1:
                if self.artist_no1_count[artist] == 0:
                    self.artist_first_no1_date[artist] = str(week)
                self.artist_no1_count[artist] += 1
                self.artist_no1_weeks[artist] += 1
            if rank <= 5:
                self.artist_top5_count[artist] = max(self.artist_top5_count.get(artist, 0), 1)
            if rank <= 10:
                self.artist_top10_count[artist] = max(self.artist_top10_count.get(artist, 0), 1)

            # Update global records
            no1_wks = self.track_weeks_at_no1.get(tid, 0)
            if no1_wks > self.longest_no1_weeks:
                self.longest_no1_weeks = no1_wks
                self.longest_no1_track_name = entry.get("track_name", "")
                self.longest_no1_artist_name = artist

        # Per-artist aggregates for global records
        for name, count in self.artist_no1_count.items():
            if count > self.most_career_no1s_count:
                self.most_career_no1s_count = count
                self.most_career_no1s_artist = name
        for name, count in self.artist_top10_count.items():
            if count > self.most_career_top10s_count:
                self.most_career_top10s_count = count
                self.most_career_top10s_artist = name

        # Personal stats
        self.cumulative_plays += personal_plays
        self.cumulative_ms += personal_ms
        if personal_track_ids:
            self.cumulative_tracks |= personal_track_ids
        if personal_artist_names:
            self.cumulative_artists |= personal_artist_names
        self.personal_weekly_top_artist = personal_top_artist
        self.personal_weekly_top_artist_plays = personal_top_artist_plays

    def artist_no1_count_as_of(self, artist_name: str) -> int:
        """How many #1s this artist had up to the current processing week."""
        return self.artist_no1_count.get(artist_name, 0)

    def artist_ordinal_no1(self, artist_name: str) -> str:
        """'7th' if the artist just got their 7th #1 this week."""
        return self._ordinal(self.artist_no1_count.get(artist_name, 0))

    def artist_top10_count_as_of(self, artist_name: str) -> int:
        return self.artist_top10_count.get(artist_name, 0)

    def track_weeks_at_no1_as_of(self, track_id: int) -> int:
        return self.track_weeks_at_no1.get(track_id, 0)

    def track_total_weeks_as_of(self, track_id: int) -> int:
        return self.track_total_weeks.get(track_id, 0)

    def get_past_no1_at_week(self, target_week: str) -> dict | None:
        """Find the #1 song for a given week in the past."""
        for p in reversed(self.past_no1s):
            if p["week"] == target_week:
                return p
        return None

"""Unit tests for playback counting policy helpers."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from backend.domains.playback.counting import effective_threshold, filter_effective_plays

pytestmark = pytest.mark.unit


class TestEffectiveThreshold:
    def test_keeps_30s_for_typical_pop_song(self):
        assert effective_threshold(210_000, min_ms=30_000, ratio=0.1) == 30_000

    def test_raises_threshold_for_long_tracks(self):
        assert effective_threshold(600_000, min_ms=30_000, ratio=0.1) == 60_000

    def test_falls_back_when_duration_is_none(self):
        assert effective_threshold(None, min_ms=30_000, ratio=0.1) == 30_000

    def test_falls_back_when_duration_is_zero(self):
        assert effective_threshold(0, min_ms=30_000, ratio=0.1) == 30_000

    def test_falls_back_when_duration_is_negative(self):
        assert effective_threshold(-100, min_ms=30_000, ratio=0.1) == 30_000

    def test_respects_custom_min_ms(self):
        assert effective_threshold(600_000, min_ms=20_000, ratio=0.1) == 60_000

    def test_large_duration_produces_high_threshold(self):
        # 30-minute track → 10% = 3 minutes
        assert effective_threshold(1_800_000, min_ms=30_000, ratio=0.1) == 180_000


class TestFilterEffectivePlays:
    def test_legacy_mode_filters_below_min_ms(self):
        df = pd.DataFrame(
            [
                {"track_id": 1, "ms_played": 29_999, "duration_ms": 210_000},
                {"track_id": 1, "ms_played": 30_000, "duration_ms": 210_000},
            ]
        )
        result = filter_effective_plays(df, min_ms=30_000, dynamic_threshold=False)
        assert result["ms_played"].tolist() == [30_000]

    def test_legacy_mode_passes_all_when_no_min_ms(self):
        df = pd.DataFrame([{"track_id": 1, "ms_played": 5_000, "duration_ms": 210_000}])
        result = filter_effective_plays(df, min_ms=0, dynamic_threshold=False)
        assert len(result) == 1

    def test_legacy_mode_handles_empty_df(self):
        df = pd.DataFrame(columns=["track_id", "ms_played", "duration_ms"])
        result = filter_effective_plays(df, min_ms=30_000, dynamic_threshold=False)
        assert len(result) == 0

    def test_dynamic_mode_filters_long_track_snippet(self):
        df = pd.DataFrame(
            [
                {"track_id": 1, "ms_played": 30_000, "duration_ms": 600_000},
                {"track_id": 2, "ms_played": 60_000, "duration_ms": 600_000},
            ]
        )
        result = filter_effective_plays(df, min_ms=30_000, dynamic_threshold=True)
        assert len(result) == 1
        assert int(result.iloc[0]["ms_played"]) == 60_000

    def test_dynamic_mode_keeps_typical_30s_play(self):
        df = pd.DataFrame(
            [
                {"track_id": 1, "ms_played": 30_000, "duration_ms": 210_000},
                {"track_id": 2, "ms_played": 29_999, "duration_ms": 210_000},
            ]
        )
        result = filter_effective_plays(df, min_ms=30_000, dynamic_threshold=True)
        assert len(result) == 1

    def test_dynamic_mode_drops_row_with_missing_duration(self):
        # When duration_ms is NaN, effective_threshold returns min_ms
        df = pd.DataFrame(
            [
                {"track_id": 1, "ms_played": 30_000, "duration_ms": float("nan")},
                {"track_id": 2, "ms_played": 29_999, "duration_ms": float("nan")},
            ]
        )
        result = filter_effective_plays(df, min_ms=30_000, dynamic_threshold=True)
        assert len(result) == 1
        assert int(result.iloc[0]["track_id"]) == 1

    def test_returns_copy_not_view(self):
        df = pd.DataFrame([{"track_id": 1, "ms_played": 30_000, "duration_ms": 210_000}])
        result = filter_effective_plays(df, min_ms=30_000)
        assert result is not df


class TestMergeSessionBoundaries:
    """merge_consecutive_plays max_gap_minutes and boundary_column."""

    def test_does_not_merge_across_large_gap(self):
        from backend.core.db import merge_consecutive_plays

        df = pd.DataFrame(
            [
                {
                    "ts": "2026-01-01T10:00:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                },
                {
                    "ts": "2026-01-01T11:00:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                },
            ]
        )
        result = merge_consecutive_plays(df, min_ms=30_000, max_gap_minutes=30)
        # Gap is 60 minutes > 30 → not merged, both remain as 20s fragments → both dropped
        assert result.empty

    def test_merges_within_gap(self):
        from backend.core.db import merge_consecutive_plays

        df = pd.DataFrame(
            [
                {
                    "ts": "2026-01-01T10:00:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                },
                {
                    "ts": "2026-01-01T10:20:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                },
            ]
        )
        result = merge_consecutive_plays(df, min_ms=30_000, max_gap_minutes=30)
        # Gap is 20 minutes < 30 → merged, 40s total → 1 valid play
        assert len(result) == 1
        assert int(result.iloc[0]["ms_played"]) == 40_000

    def test_does_not_merge_across_boundary_column_change(self):
        from backend.core.db import merge_consecutive_plays

        df = pd.DataFrame(
            [
                {
                    "ts": "2026-01-01T10:00:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                    "source": "A",
                },
                {
                    "ts": "2026-01-01T10:01:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                    "source": "B",
                },
            ]
        )
        result = merge_consecutive_plays(df, min_ms=30_000, boundary_column="source")
        # Different source values → not merged, both dropped
        assert result.empty

    def test_merges_same_boundary_column_value(self):
        from backend.core.db import merge_consecutive_plays

        df = pd.DataFrame(
            [
                {
                    "ts": "2026-01-01T10:00:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                    "source": "A",
                },
                {
                    "ts": "2026-01-01T10:01:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                    "source": "A",
                },
            ]
        )
        result = merge_consecutive_plays(df, min_ms=30_000, boundary_column="source")
        # Same source, same track, small gap → merged → 1 valid play
        assert len(result) == 1
        assert int(result.iloc[0]["ms_played"]) == 40_000

    def test_gap_and_boundary_combined(self):
        from backend.core.db import merge_consecutive_plays

        df = pd.DataFrame(
            [
                {
                    "ts": "2026-01-01T10:00:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                    "source": "A",
                },
                {
                    "ts": "2026-01-01T10:05:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                    "source": "A",
                },
                {
                    "ts": "2026-01-01T11:00:00",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                    "source": "A",
                },
            ]
        )
        result = merge_consecutive_plays(
            df, min_ms=30_000, max_gap_minutes=30, boundary_column="source"
        )
        # First two rows: same source+track, 5min gap < 30 → merged → 1 play of 40s
        # Third row: same source+track but 55min gap > 30 → separate group → 20s → dropped
        assert len(result) == 1
        assert int(result.iloc[0]["ms_played"]) == 40_000

    def test_large_fragmented_sessions_merge_within_performance_guard(self):
        from backend.core.db import merge_consecutive_plays

        group_count = 40_000
        row_count = group_count * 2
        df = pd.DataFrame(
            {
                "ts": pd.Timestamp("2026-01-01")
                + pd.to_timedelta(np.arange(row_count), unit="min"),
                "track_id": np.repeat(np.arange(group_count), 2),
                "ms_played": np.full(row_count, 20_000),
                "duration_ms": np.full(row_count, 40_000),
                "source_album_id": np.repeat(np.arange(group_count), 2),
            }
        )

        start = time.perf_counter()
        result = merge_consecutive_plays(df, min_ms=30_000, boundary_column="source_album_id")
        elapsed = time.perf_counter() - start

        assert len(result) == group_count
        assert result["ms_played"].unique().tolist() == [40_000]
        # Timeline v2 additionally reconstructs per-event counted_at values,
        # stable identities and listened-interval slices. Keep a regression
        # guard for the 80k-row vectorised path while allowing CI load jitter.
        assert elapsed < 8.0

    def test_uses_actual_idle_gap_for_long_seamless_replay(self):
        from backend.core.db import merge_consecutive_plays

        df = pd.DataFrame(
            [
                {
                    "play_id": 1,
                    "ts": "2026-01-01T10:00:00Z",
                    "track_id": 1,
                    "ms_played": 360_000,
                    "duration_ms": 360_000,
                    "source_album_id": 1,
                },
                {
                    "play_id": 2,
                    "ts": "2026-01-01T10:06:00Z",
                    "track_id": 1,
                    "ms_played": 360_000,
                    "duration_ms": 360_000,
                    "source_album_id": 1,
                },
            ]
        )

        result = merge_consecutive_plays(
            df,
            min_ms=30_000,
            max_gap_minutes=5,
            boundary_column="source_album_id",
        )

        assert len(result) == 2
        assert result["_merge_run_id"].nunique() == 1

    @pytest.mark.parametrize(
        ("idle_ms", "expected_runs"),
        [(300_000, 1), (300_001, 2)],
    )
    def test_five_minute_idle_boundary_is_inclusive(self, idle_ms, expected_runs):
        from backend.core.db import merge_consecutive_plays

        first_end = pd.Timestamp("2026-01-01T10:00:00Z")
        second_start = first_end + pd.Timedelta(milliseconds=idle_ms)
        second_end = second_start + pd.Timedelta(seconds=40)
        df = pd.DataFrame(
            [
                {
                    "play_id": 1,
                    "ts": first_end.isoformat(),
                    "track_id": 1,
                    "ms_played": 40_000,
                    "duration_ms": 40_000,
                    "source_album_id": 1,
                },
                {
                    "play_id": 2,
                    "ts": second_end.isoformat(),
                    "track_id": 1,
                    "ms_played": 40_000,
                    "duration_ms": 40_000,
                    "source_album_id": 1,
                },
            ]
        )

        result = merge_consecutive_plays(
            df,
            min_ms=30_000,
            max_gap_minutes=5,
            boundary_column="source_album_id",
        )

        assert result["_merge_run_id"].nunique() == expected_runs

    def test_each_expanded_play_gets_its_own_counted_at(self):
        from backend.core.db import merge_consecutive_plays

        df = pd.DataFrame(
            [
                {
                    "play_id": 10,
                    "ts": "2026-01-01T15:59:50Z",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                    "source_album_id": 1,
                },
                {
                    "play_id": 11,
                    "ts": "2026-01-01T16:00:10Z",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                    "source_album_id": 1,
                },
            ]
        )

        result = merge_consecutive_plays(
            df,
            min_ms=30_000,
            max_gap_minutes=5,
            boundary_column="source_album_id",
        )

        assert len(result) == 1
        # A complete logical play is attributed when the full duration is
        # reached, rather than inheriting the first fragment's stop time.
        assert result.iloc[0]["counted_at"] == "2026-01-01T16:00:10Z"
        assert result.iloc[0]["ts_date"] == "2026-01-02"

    def test_remainder_qualification_point_controls_third_play_time(self):
        from backend.core.db import merge_consecutive_plays

        df = pd.DataFrame(
            [
                {
                    "play_id": 20,
                    "ts": "2026-01-01T00:08:30Z",
                    "track_id": 1,
                    "ms_played": 510_000,
                    "duration_ms": 240_000,
                    "source_album_id": 1,
                }
            ]
        )

        result = merge_consecutive_plays(df, min_ms=30_000, max_gap_minutes=5)

        assert result["ms_played"].tolist() == [240_000, 240_000, 30_000]
        assert result["counted_at"].tolist() == [
            "2026-01-01T00:04:00Z",
            "2026-01-01T00:08:00Z",
            "2026-01-01T00:08:30Z",
        ]

    def test_severe_inferred_overlap_starts_new_run(self):
        from backend.core.db import merge_consecutive_plays

        df = pd.DataFrame(
            [
                {
                    "play_id": 30,
                    "ts": "2026-01-01T10:00:00Z",
                    "track_id": 1,
                    "ms_played": 240_000,
                    "duration_ms": 240_000,
                },
                {
                    "play_id": 31,
                    "ts": "2026-01-01T10:00:01Z",
                    "track_id": 1,
                    "ms_played": 240_000,
                    "duration_ms": 240_000,
                },
            ]
        )

        result = merge_consecutive_plays(df, min_ms=30_000, max_gap_minutes=5)

        assert len(result) == 2
        assert result["_merge_run_id"].nunique() == 2
        assert "overlap_split" in set(result["time_quality"])

    def test_listening_duration_splits_across_local_dates(self):
        from backend.core.db import merge_consecutive_plays
        from backend.domains.playback.logical_timeline import explode_listening_slices

        df = pd.DataFrame(
            [
                {
                    "play_id": 40,
                    "ts": "2026-01-01T15:59:50Z",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                },
                {
                    "play_id": 41,
                    "ts": "2026-01-01T16:00:10Z",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                },
            ]
        )

        events = merge_consecutive_plays(df, min_ms=30_000, max_gap_minutes=5)
        slices = explode_listening_slices(events, granularity="day")

        assert events["ts_date"].tolist() == ["2026-01-02"]
        assert slices.groupby("ts_date")["ms_played"].sum().to_dict() == {
            "2026-01-01": 30_000,
            "2026-01-02": 10_000,
        }

    def test_billboard_weights_separate_event_count_and_duration(self):
        from backend.core.db import merge_consecutive_plays
        from backend.domains.playback.logical_timeline import build_billboard_weighted_frame

        # Asia/Shanghai Thursday 00:00 boundary = Wednesday 16:00 UTC.
        df = pd.DataFrame(
            [
                {
                    "play_id": 50,
                    "ts": "2026-05-27T15:59:50Z",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                },
                {
                    "play_id": 51,
                    "ts": "2026-05-27T16:00:10Z",
                    "track_id": 1,
                    "ms_played": 20_000,
                    "duration_ms": 40_000,
                },
            ]
        )

        events = merge_consecutive_plays(df, min_ms=30_000, max_gap_minutes=5)
        weighted = build_billboard_weighted_frame(
            events,
            week_start_dow=3,
            week_start_hour=0,
        )
        grouped = weighted.groupby("billboard_week")[["play_count", "total_ms"]].sum()

        assert grouped["play_count"].to_dict() == {
            pd.Timestamp("2026-05-28").date(): 1,
            pd.Timestamp("2026-05-21").date(): 0,
        }
        assert grouped["total_ms"].to_dict() == {
            pd.Timestamp("2026-05-28").date(): 10_000,
            pd.Timestamp("2026-05-21").date(): 30_000,
        }

    def test_period_filter_is_invariant_for_cross_midnight_duration(self):
        from backend.core.db import merge_consecutive_plays
        from backend.services.analysis_stats_service import (
            _chart_agg,
            _daily_trend,
            filter_period,
        )

        raw = pd.DataFrame(
            [
                {
                    "play_id": 60,
                    "ts": "2026-01-01T16:02:00Z",
                    "track_id": 1,
                    "track_name": "Boundary Song",
                    "artist_name": "Boundary Artist",
                    "album_name": "Boundary Album",
                    "ms_played": 240_000,
                    "duration_ms": 240_000,
                }
            ]
        )
        events = merge_consecutive_plays(raw, min_ms=30_000, max_gap_minutes=5)
        first_day = filter_period(
            events,
            {"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )
        second_day = filter_period(
            events,
            {"start_date": "2026-01-02", "end_date": "2026-01-02"},
        )

        assert first_day.empty
        assert len(second_day) == 1
        assert first_day.attrs["listening_duration_slices"]["ms_played"].sum() == 120_000
        assert second_day.attrs["listening_duration_slices"]["ms_played"].sum() == 120_000
        assert _daily_trend(first_day) == [{"date": "2026-01-01", "plays": 0, "hours": 0.03}]
        assert _daily_trend(second_day) == [{"date": "2026-01-02", "plays": 1, "hours": 0.03}]
        first_day_chart = _chart_agg(first_day, "track", merge_level=1)
        assert int(first_day_chart.iloc[0]["plays"]) == 0
        assert first_day_chart.iloc[0]["hours"] == pytest.approx(120_000 / 3_600_000)

    def test_entity_duration_does_not_inherit_global_duration_attrs(self):
        from backend.core.db import merge_consecutive_plays
        from backend.services.analysis_stats_service import (
            _summary,
            build_duration_frame,
            filter_period,
        )

        raw = pd.DataFrame(
            [
                {
                    "play_id": 70,
                    "ts": "2026-01-01T01:00:00Z",
                    "track_id": 1,
                    "track_name": "Track One",
                    "artist_name": "Artist",
                    "album_name": "Album",
                    "ms_played": 3_600_000,
                    "duration_ms": 3_600_000,
                },
                {
                    "play_id": 71,
                    "ts": "2026-01-02T01:00:00Z",
                    "track_id": 2,
                    "track_name": "Track Two",
                    "artist_name": "Artist",
                    "album_name": "Album",
                    "ms_played": 7_200_000,
                    "duration_ms": 7_200_000,
                },
            ]
        )
        events = merge_consecutive_plays(raw, min_ms=30_000, max_gap_minutes=5)
        filtered = filter_period(
            events,
            {"start_date": "2026-01-01", "end_date": "2026-01-02"},
        )
        entity = filtered[filtered["track_id"] == 1]

        summary = _summary(entity, build_duration_frame(entity))

        assert summary["total_plays"] == 1
        assert summary["total_hours"] == pytest.approx(1.0)
        assert summary["active_days"] == 1

    def test_relative_periods_anchor_to_latest_data_date(self):
        from backend.services.analysis_stats_service import resolve_period

        df = pd.DataFrame(
            {
                "ts_date": ["2026-07-20", "2026-07-24"],
            }
        )

        assert resolve_period(df, "last_4_weeks", None, None) == {
            "period": "last_4_weeks",
            "label": "最近 4 周",
            "start_date": "2026-06-27",
            "end_date": "2026-07-24",
        }

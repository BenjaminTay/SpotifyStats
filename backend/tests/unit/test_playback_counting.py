"""Unit tests for playback counting policy helpers."""

from __future__ import annotations

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

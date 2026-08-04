from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.billboard.chart_load_rank import _charting_artist_track_counts

pytestmark = pytest.mark.unit


class _Connection:
    def close(self) -> None:
        pass


def test_charting_track_counts_uses_topn_effective_credits_and_group_members(monkeypatch):
    weekly = pd.DataFrame(
        [
            {"billboard_week": "2026-07-17", "track_id": 10},
            {"billboard_week": "2026-07-17", "track_id": 20},
            {"billboard_week": "2026-07-24", "track_id": 10},
        ]
    )
    keys = pd.DataFrame(
        [
            {
                "track_id": 10,
                "track_agg_id": 10,
                "track_agg_name": "Hit",
                "track_group_scope": "recording",
            },
            {
                "track_id": 11,
                "track_agg_id": 10,
                "track_agg_name": "Hit",
                "track_group_scope": "recording",
            },
        ]
    )
    credits = pd.DataFrame(
        [
            {"track_id": 10, "artist_id": 1, "artist_name": "Primary"},
            {"track_id": 10, "artist_id": 2, "artist_name": "Featured"},
            # Alias/member duplicate for the same canonical artist and track.
            {"track_id": 11, "artist_id": 2, "artist_name": "Featured"},
            {"track_id": 20, "artist_id": 2, "artist_name": "Featured"},
        ]
    )
    monkeypatch.setattr("backend.core.db.get_db", lambda: _Connection())
    monkeypatch.setattr(
        "backend.domains.playback.track_groups.load_track_group_keys",
        lambda _conn, merge_level: keys,
    )
    monkeypatch.setattr(
        "backend.domains.metadata.track_credits.get_effective_track_credit_frame",
        lambda _conn, _track_ids: credits,
    )

    result = _charting_artist_track_counts(weekly, merge_level=2)
    counts = {
        (str(row.billboard_week), row.artist_name): int(row.tracks_count)
        for row in result.itertuples()
    }
    assert counts[("2026-07-17", "Primary")] == 1
    assert counts[("2026-07-17", "Featured")] == 2
    assert counts[("2026-07-24", "Featured")] == 1

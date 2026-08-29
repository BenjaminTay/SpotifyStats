from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from backend.domains.billboard import chart_staged_cache, records
from backend.domains.billboard.latest_snapshot_cache import (
    clear_latest_snapshots,
    get_latest_snapshot_if_cached,
    latest_snapshot_revision,
    snapshot_key,
    store_latest_snapshot,
)

pytestmark = pytest.mark.unit


def test_latest_snapshot_requires_an_exact_key_and_keeps_only_two_weeks():
    clear_latest_snapshots()
    key = snapshot_key(dynamic_threshold=True, bb_week_start_hour=12)
    payload = {
        "meta": {"all_weeks_desc": ["2026-08-07", "2026-07-31", "2026-07-24"]},
        "weekly": [
            {"billboard_week": "2026-08-07", "rank": 1},
            {"billboard_week": "2026-07-31", "rank": 2},
            {"billboard_week": "2026-07-24", "rank": 3},
        ],
        "weekly_album": [],
        "weekly_artist": [],
        "home_billboard_movement": {
            "artist": {"movement": "re", "previous_rank": None, "rank_change": None}
        },
    }

    store_latest_snapshot(key, payload)

    snapshot = get_latest_snapshot_if_cached(key)
    assert snapshot is not None
    assert snapshot["meta"]["all_weeks_desc"] == ["2026-08-07", "2026-07-31"]
    assert [row["billboard_week"] for row in snapshot["weekly"]] == [
        "2026-08-07",
        "2026-07-31",
    ]
    assert snapshot["home_billboard_movement"]["artist"]["movement"] == "re"
    assert (
        get_latest_snapshot_if_cached(snapshot_key(dynamic_threshold=True, bb_week_start_hour=0))
        is None
    )


def test_latest_snapshot_invalidation_changes_readiness_revision():
    clear_latest_snapshots()
    before = latest_snapshot_revision()
    key = snapshot_key()
    store_latest_snapshot(
        key,
        {
            "meta": {"all_weeks_desc": []},
            "weekly": [],
            "weekly_album": [],
            "weekly_artist": [],
        },
    )
    stored = latest_snapshot_revision()
    clear_latest_snapshots()

    assert stored > before
    assert latest_snapshot_revision() > stored
    assert get_latest_snapshot_if_cached(key) is None


def test_snapshot_revision_is_scoped_to_the_exact_semantic_key():
    clear_latest_snapshots()
    home_key = snapshot_key(merge_level=2, dynamic_threshold=True)
    other_key = snapshot_key(merge_level=3, dynamic_threshold=False)
    empty = {
        "meta": {"all_weeks_desc": []},
        "weekly": [],
        "weekly_album": [],
        "weekly_artist": [],
    }

    store_latest_snapshot(home_key, empty)
    home_revision = latest_snapshot_revision(home_key)
    store_latest_snapshot(other_key, empty)

    assert latest_snapshot_revision(home_key) == home_revision
    assert latest_snapshot_revision(other_key) == 1


def test_weekly_staged_computation_populates_the_home_snapshot(monkeypatch):
    clear_latest_snapshots()
    chart_staged_cache._compute_weekly_data_cached.cache_clear()
    week = date(2026, 8, 7)
    weekly = pd.DataFrame(
        [{"billboard_week": week, "rank": 1, "track_id": 7, "track_name": "冠军"}]
    )
    filtered = pd.DataFrame([{"play_id": 1}])
    filtered.attrs["home_billboard_movement"] = {
        "artist": {"movement": "re", "previous_rank": None, "rank_change": None}
    }
    monkeypatch.setattr(
        chart_staged_cache,
        "_load_and_rank",
        lambda *_args, **_kwargs: (
            weekly,
            pd.DataFrame(),
            pd.DataFrame(),
            [week],
            [week],
            filtered,
            {},
        ),
    )
    monkeypatch.setattr(records, "_add_cover_urls", lambda *frames: frames)
    monkeypatch.setattr(chart_staged_cache, "enrich_track_artist_names", lambda frame: frame)

    chart_staged_cache._compute_weekly_data_cached(dynamic_threshold=True)

    snapshot = get_latest_snapshot_if_cached(snapshot_key(dynamic_threshold=True))
    assert snapshot is not None
    assert snapshot["meta"]["all_weeks_desc"] == ["2026-08-07"]
    assert snapshot["weekly"][0]["track_id"] == 7
    assert snapshot["home_billboard_movement"]["artist"]["movement"] == "re"

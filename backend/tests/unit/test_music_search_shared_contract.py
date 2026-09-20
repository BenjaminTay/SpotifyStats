"""Search context contract: stable Power order and independent duration facts."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.music_search import snapshot, snapshot_delta
from backend.domains.music_search.snapshot_ledger import rebuild_context_rows_from_weekly_ledger
from backend.services.music_search_service import _album_chart_map, _sorted_power_frame
from backend.tests.unit.test_music_search_snapshot import _conn, _shared_contexts
from backend.tests.unit.test_music_search_snapshot_ledger import _ledger_row

pytestmark = pytest.mark.unit


def test_power_rank_preserves_builder_ties_without_score_only_resort():
    records = [{"track_id": i, "power_score": 100, "power_rank": i} for i in range(1, 41)]
    result = _sorted_power_frame({"power_scores": records}, "power_scores")
    assert result["_detail_power_rank"].tolist() == list(range(1, 41))
    assert result["track_id"].tolist() == list(range(1, 41))


@pytest.mark.parametrize("family,prefix", [("album", "album_project"), ("artist", "artist")])
def test_delta_power_rank_uses_builder_text_ties_before_numeric_identity(family, prefix):
    rows = []
    for week, ids in [("2026-01-02", (1, 2)), ("2026-01-09", (2, 1))]:
        for rank, identity in enumerate((3, *ids), 1):
            names = {"artist_name": {1: "Zulu", 2: "Alpha", 3: "Leader"}[identity]}
            if family == "album":
                names["album_name"] = "Album"
            rows.append(
                _ledger_row(family, week, f"{prefix}:{identity}", rank, 4 - rank, 1000, **names)
            )
    result = rebuild_context_rows_from_weekly_ledger(
        rows,
        {},
        {f"{prefix}:1", f"{prefix}:2", f"{prefix}:3"},
        track_top_n=30,
        album_top_n=20,
        artist_top_n=20,
    )
    by_key = {row[0]: row for row in result}
    assert by_key[f"{prefix}:1"][7] == by_key[f"{prefix}:2"][7]
    assert by_key[f"{prefix}:2"][8] == 2
    assert by_key[f"{prefix}:1"][8] == 3


@pytest.mark.parametrize("dynamic", [False, True])
def test_album_chart_matches_project_across_artist_display_aliases(dynamic):
    conn = _conn()
    context = next(
        c for c in _shared_contexts(conn) if c.merge_level == 3 and c.dynamic_threshold == dynamic
    )
    # Candidate and weekly rows describe the same project with different artist display names.
    conn.execute(
        "UPDATE music_search_documents SET artist_name='Jolin Tsai' WHERE kind='album_project'"
    )
    charts = _album_chart_map(
        {
            "weekly_album": [
                {
                    "album_project_id": 2,
                    "album_name": "Album",
                    "artist_name": "JOLIN",
                    "billboard_week": "2026-01-02",
                    "rank": 1,
                }
            ],
            "album_power_scores": [
                {"album_name": "Album", "artist_name": "JOLIN", "power_score": 123, "power_rank": 1}
            ],
        }
    )
    rows = snapshot._context_rows(
        conn,
        context,
        metric_maps=({}, {2: (0, 10000)}, {}),
        chart_lookup={"track": {}, "album": charts, "artist": {}},
    )
    album = next(row for row in rows if row[0] == "album_project:2")
    assert album[1:9] == (0, 10000, 1, 1, 1, 1, 123, 1)
    assert 999 not in charts


def test_ledger_keeps_duration_only_and_empty_frames():
    assert (
        rebuild_context_rows_from_weekly_ledger(
            [], {}, [], track_top_n=30, album_top_n=20, artist_top_n=20
        )
        == []
    )
    keys = {"track:1", "album_project:2", "artist:3"}
    rows = rebuild_context_rows_from_weekly_ledger(
        [], {key: (0, 1000) for key in keys}, keys, track_top_n=30, album_top_n=20, artist_top_n=20
    )
    assert {row[0] for row in rows} == keys
    assert all(row[1:3] == (0, 1000) and all(v is None for v in row[3:]) for row in rows)


def test_delta_retains_existing_and_new_duration_only_entities(monkeypatch):
    conn = _conn()
    context = _shared_contexts(conn)[0]
    conn.execute(
        "INSERT INTO music_search_entity_context(snapshot_key,entity_key,play_events,total_ms) VALUES ('base','track:1',0,1000)"
    )
    monkeypatch.setattr(snapshot_delta, "_album_delta_map", lambda *_a, **_k: {2: (0, 2000)})
    monkeypatch.setattr(snapshot_delta, "_artist_delta_map", lambda *_a, **_k: {3: (0, 3000)})
    rows = snapshot_delta._clone_and_apply_context_rows(
        conn, context, "base", track_delta=pd.DataFrame(), physical_delta=pd.DataFrame()
    )
    assert {row[0]: row[1:3] for row in rows} == {
        "track:1": (0, 1000),
        "album_project:2": (0, 2000),
        "artist:3": (0, 3000),
    }


def test_delta_returns_physical_and_both_independent_identity_projections(monkeypatch):
    physical = pd.DataFrame({"track_id": [1], "play_events": [0], "total_ms": [1000]})
    monkeypatch.setattr(
        snapshot_delta, "build_tail_track_logical_delta", lambda *_a, **_k: physical
    )
    monkeypatch.setattr(snapshot_delta, "load_track_group_keys", lambda _c, level: level)
    monkeypatch.setattr(
        snapshot_delta,
        "project_track_logical_delta",
        lambda frame, merge_level, **_: frame.assign(track_id=merge_level),
    )
    maps = snapshot_delta._track_delta_maps(
        _conn(),
        generation_id="unit-generation",
        min_ms=30000,
        music_only=True,
        dynamic_threshold=True,
        max_gap_minutes=5,
    )
    assert maps[1] is physical
    assert maps[2]["track_id"].tolist() == [2]
    assert maps[3]["track_id"].tolist() == [3]

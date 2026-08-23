from __future__ import annotations

import sqlite3
from dataclasses import replace

import pandas as pd
import pytest

from backend.domains.music_search.context import MusicSearchFilterContext
from backend.domains.music_search.snapshot_week_delta import (
    MusicSearchWeekDeltaIncompatibleError,
    _complete_week_keys,
    _encode_ledger_rows,
    _rank_track_weekly,
    _utc_week_boundary,
    build_affected_complete_week_ledger_rows,
)


def _context(level: int, dynamic: bool) -> MusicSearchFilterContext:
    return MusicSearchFilterContext(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=dynamic,
        max_merge_gap_minutes=5,
        merge_level=level,
        include_compilations=False,
        bb_top_n=2,
        bb_album_top_n=2,
        bb_artist_top_n=2,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        year_start=None,
        year_end=None,
        playback_revision=2,
        billboard_aggregation_revision=2,
        metadata_revision=2,
        settings_revision=2,
        artist_identity_revision=2,
        track_credit_revision=2,
        semantic_base_key="base",
        filter_fingerprint=f"snapshot-{level}-{int(dynamic)}",
        source_revision="source",
    )


def _contexts() -> tuple[MusicSearchFilterContext, ...]:
    return tuple(_context(level, dynamic) for dynamic in (False, True) for level in (1, 2, 3))


def test_complete_week_keys_excludes_open_week_and_rejects_future() -> None:
    assert _complete_week_keys({"2026-08-14", "2026-08-21"}, "2026-08-21") == {"2026-08-14"}
    with pytest.raises(MusicSearchWeekDeltaIncompatibleError):
        _complete_week_keys({"2026-08-28"}, "2026-08-21")


def test_utc_week_boundary_applies_local_start_hour() -> None:
    boundary = _utc_week_boundary("2026-08-21", 4)

    assert boundary.isoformat() == "2026-08-20T20:00:00+00:00"


def test_rank_track_weekly_ranks_the_complete_population_before_top_n(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot_week_delta.load_track_group_keys",
        lambda _conn, _level: pd.DataFrame(),
    )
    weighted = pd.DataFrame(
        [
            ("2026-08-14", 3, "C", "Artist", 3, 100),
            ("2026-08-14", 1, "A", "Artist", 5, 100),
            ("2026-08-14", 2, "B", "Artist", 5, 200),
        ],
        columns=[
            "billboard_week",
            "track_id",
            "track_name",
            "artist_name",
            "play_count",
            "total_ms",
        ],
    )
    ranked = _rank_track_weekly(sqlite3.connect(":memory:"), weighted, _context(1, False))
    assert ranked[["track_id", "rank"]].to_records(index=False).tolist() == [(2, 1), (1, 2)]


def test_encode_ledger_fails_closed_when_ranked_identity_is_not_a_candidate() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE music_search_documents(
               generation_id TEXT, entity_key TEXT, kind TEXT, merge_level INTEGER)"""
    )
    context = _context(1, False)
    ranked = {
        "track": pd.DataFrame(
            [("2026-08-14", 99, "Missing", "Artist", 1, 1, 1)],
            columns=[
                "billboard_week",
                "track_id",
                "track_name",
                "artist_name",
                "play_count",
                "total_ms",
                "rank",
            ],
        ),
        "album": pd.DataFrame(),
        "artist": pd.DataFrame(),
    }
    with pytest.raises(MusicSearchWeekDeltaIncompatibleError, match="absent"):
        _encode_ledger_rows(conn, context, ranked, candidate_generation="candidate")


def test_builder_passes_only_completed_weeks_to_all_six_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = sqlite3.connect(":memory:")
    contexts = _contexts()
    seen: list[tuple[str, set[str]]] = []
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot_week_delta._assert_tail_scope",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot_week_delta._load_bounded_tail_closure",
        lambda *_a, **_k: pd.DataFrame([{"track_id": 1}]),
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot_week_delta._logical_events",
        lambda *_a, **_k: pd.DataFrame([{"track_id": 1}]),
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot_week_delta.get_music_search_index_state",
        lambda _conn: {"active_generation_id": "candidate"},
    )

    def fake_ranked(_conn, context, _logical, weeks):
        seen.append((context.filter_fingerprint, set(weeks)))
        return {"track": pd.DataFrame(), "album": pd.DataFrame(), "artist": pd.DataFrame()}

    monkeypatch.setattr(
        "backend.domains.music_search.snapshot_week_delta._ranked_rows_for_context", fake_ranked
    )
    monkeypatch.setattr(
        "backend.domains.music_search.snapshot_week_delta._encode_ledger_rows",
        lambda *_a, **_k: [],
    )
    result = build_affected_complete_week_ledger_rows(
        conn,
        contexts,
        change_generation_id="generation",
        affected_weeks={"2026-08-14", "2026-08-21"},
        current_open_week="2026-08-21",
    )
    assert set(result) == {context.filter_fingerprint for context in contexts}
    assert len(seen) == 6
    assert all(weeks == {"2026-08-14"} for _fingerprint, weeks in seen)


def test_builder_rejects_divergent_six_variant_policy() -> None:
    contexts = list(_contexts())
    contexts[-1] = replace(contexts[-1], bb_top_n=99)
    with pytest.raises(MusicSearchWeekDeltaIncompatibleError, match="divergent"):
        build_affected_complete_week_ledger_rows(
            sqlite3.connect(":memory:"),
            tuple(contexts),
            change_generation_id="generation",
            affected_weeks={"2026-08-14"},
            current_open_week="2026-08-21",
        )

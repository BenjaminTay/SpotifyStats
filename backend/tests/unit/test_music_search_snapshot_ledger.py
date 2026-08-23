"""Tests for pure music-search context reconstruction from weekly ledgers."""

from __future__ import annotations

import json
import random

import pytest

from backend.domains.music_search.snapshot_ledger import (
    WeeklyLedgerValidationError,
)
from backend.domains.music_search.snapshot_ledger import (
    rebuild_context_rows_from_weekly_ledger as _rebuild_context_rows_from_weekly_ledger,
)


def rebuild_context_rows_from_weekly_ledger(
    weekly_rows,
    lifetime_metrics,
    candidate_keys,
    *,
    track_top_n: int = 30,
    album_top_n: int = 20,
    artist_top_n: int = 20,
):
    return _rebuild_context_rows_from_weekly_ledger(
        weekly_rows,
        lifetime_metrics,
        candidate_keys,
        track_top_n=track_top_n,
        album_top_n=album_top_n,
        artist_top_n=artist_top_n,
    )


def _ledger_row(
    family: str,
    week: str,
    entity_key: str,
    rank: int,
    play_count: int,
    total_ms: int,
    **identity,
):
    entity_id = int(entity_key.rsplit(":", 1)[1])
    return (
        family,
        week,
        entity_key,
        rank,
        play_count,
        total_ms,
        json.dumps(
            {"entity_id": entity_id, **identity},
            sort_keys=True,
            separators=(",", ":"),
        ),
    )


@pytest.mark.parametrize("album_key", ["album:10", "album_project:10"])
def test_rebuild_preserves_l1_and_project_entity_identities(album_key: str) -> None:
    rows = [
        _ledger_row(
            "track",
            "2026-01-02",
            "track:501",
            1,
            8,
            8000,
            track_name="Track",
            artist_name="Artist",
        ),
        _ledger_row(
            "album",
            "2026-01-02",
            album_key,
            1,
            8,
            8000,
            album_name="Album",
            artist_name="Artist",
        ),
        _ledger_row(
            "artist",
            "2026-01-02",
            "artist:20",
            1,
            8,
            8000,
            artist_name="Artist",
        ),
    ]
    candidates = {"track:501", "album:10", "album_project:10", "artist:20"}
    metrics = {key: (3, 9000) for key in ("track:501", album_key, "artist:20")}

    result = rebuild_context_rows_from_weekly_ledger(rows, metrics, candidates)

    assert [row[0] for row in result] == ["track:501", album_key, "artist:20"]
    assert all(row[1:4] == (3, 9000, 1) for row in result)
    assert all(row[4:7] == (1, 1, 1) for row in result)
    assert all(row[8] == 1 for row in result)
    assert all(row[9:] == ("2026-01-02", "2026-01-02", "2026-01-02") for row in result)


def test_same_display_names_remain_distinct_and_power_ties_use_numeric_ids() -> None:
    rows = []
    for week, first, second in (
        ("2026-01-02", 2, 10),
        ("2026-01-09", 10, 2),
    ):
        rows.extend(
            [
                _ledger_row(
                    "album",
                    week,
                    f"album_project:{first}",
                    1,
                    10,
                    1000,
                    album_name="Same Album",
                    artist_name="Same Artist",
                ),
                _ledger_row(
                    "album",
                    week,
                    f"album_project:{second}",
                    2,
                    5,
                    500,
                    album_name="Same Album",
                    artist_name="Same Artist",
                ),
                _ledger_row(
                    "artist",
                    week,
                    f"artist:{first}",
                    1,
                    10,
                    1000,
                    artist_name="Same Artist",
                ),
                _ledger_row(
                    "artist",
                    week,
                    f"artist:{second}",
                    2,
                    5,
                    500,
                    artist_name="Same Artist",
                ),
            ]
        )
    candidates = {
        "album_project:2",
        "album_project:10",
        "artist:2",
        "artist:10",
    }

    result = rebuild_context_rows_from_weekly_ledger(rows, {}, candidates)
    by_key = {row[0]: row for row in result}

    assert set(by_key) == candidates
    assert all(row[3:6] == (1, 1, 2) for row in by_key.values())
    assert by_key["album_project:2"][7] == by_key["album_project:10"][7]
    assert by_key["album_project:2"][8] == 1
    assert by_key["album_project:10"][8] == 2
    assert by_key["artist:2"][7] == by_key["artist:10"][7]
    assert by_key["artist:2"][8] == 1
    assert by_key["artist:10"][8] == 2


def test_competitor_change_recomputes_other_entities_power_score() -> None:
    def ledger(runner_up_plays: int):
        rows = []
        for week in ("2026-01-02", "2026-01-09"):
            rows.extend(
                [
                    _ledger_row(
                        "track",
                        week,
                        "track:1",
                        1,
                        100,
                        10000,
                        track_name="Champion",
                        artist_name="Artist",
                    ),
                    _ledger_row(
                        "track",
                        week,
                        "track:2",
                        2,
                        runner_up_plays,
                        5000,
                        track_name="Runner-up",
                        artist_name="Artist",
                    ),
                    _ledger_row(
                        "track",
                        week,
                        "track:3",
                        3,
                        5,
                        500,
                        track_name="Later Champion",
                        artist_name="Artist",
                    ),
                ]
            )
        rows.extend(
            [
                _ledger_row(
                    "track",
                    "2026-01-16",
                    "track:3",
                    1,
                    150,
                    15000,
                    track_name="Later Champion",
                    artist_name="Artist",
                ),
                _ledger_row(
                    "track",
                    "2026-01-16",
                    "track:1",
                    2,
                    10,
                    1000,
                    track_name="Champion",
                    artist_name="Artist",
                ),
                _ledger_row(
                    "track",
                    "2026-01-16",
                    "track:2",
                    3,
                    5,
                    500,
                    track_name="Runner-up",
                    artist_name="Artist",
                ),
            ]
        )
        return rows

    candidates = {"track:1", "track:2", "track:3"}
    wide_gap = {
        row[0]: row for row in rebuild_context_rows_from_weekly_ledger(ledger(20), {}, candidates)
    }
    close_gap = {
        row[0]: row for row in rebuild_context_rows_from_weekly_ledger(ledger(80), {}, candidates)
    }

    assert wide_gap["track:1"][7] != close_gap["track:1"][7]
    assert wide_gap["track:1"][8] == 1
    assert close_gap["track:1"][8] == 2
    assert sorted(row[8] for row in close_gap.values()) == [1, 2, 3]


def test_configured_top_n_is_forwarded_when_family_has_fewer_entities(monkeypatch) -> None:
    from backend.domains.music_search import snapshot_ledger as ledger_module

    observed: dict[str, int] = {}
    original_track = ledger_module.compute_power_scores
    original_album = ledger_module.compute_album_power_scores
    original_artist = ledger_module.compute_artist_power_scores

    def track_power(frame, top_n):
        observed["track"] = top_n
        return original_track(frame, top_n)

    def album_power(frame, top_n):
        observed["album"] = top_n
        return original_album(frame, top_n)

    def artist_power(frame, top_n):
        observed["artist"] = top_n
        return original_artist(frame, top_n)

    monkeypatch.setattr(ledger_module, "compute_power_scores", track_power)
    monkeypatch.setattr(ledger_module, "compute_album_power_scores", album_power)
    monkeypatch.setattr(ledger_module, "compute_artist_power_scores", artist_power)
    rows = [
        _ledger_row(
            "track",
            "2026-01-02",
            "track:1",
            1,
            3,
            3000,
            track_name="Track",
            artist_name="Artist",
        ),
        _ledger_row(
            "album",
            "2026-01-02",
            "album_project:2",
            1,
            3,
            3000,
            album_name="Album",
            artist_name="Artist",
        ),
        _ledger_row(
            "artist",
            "2026-01-02",
            "artist:3",
            1,
            3,
            3000,
            artist_name="Artist",
        ),
    ]

    _rebuild_context_rows_from_weekly_ledger(
        rows,
        {},
        {"track:1", "album_project:2", "artist:3"},
        track_top_n=37,
        album_top_n=23,
        artist_top_n=19,
    )

    assert observed == {"track": 37, "album": 23, "artist": 19}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda row: (*row[:6], "{"),
        lambda row: (*row[:6], row[6].replace('"entity_id":1', '"entity_id":2')),
        lambda row: ("artist", *row[1:]),
        lambda row: (*row[:3], 0, *row[4:]),
    ],
)
def test_malformed_ledger_fails_closed(mutate) -> None:
    valid = _ledger_row(
        "track",
        "2026-01-02",
        "track:1",
        1,
        3,
        3000,
        track_name="Track",
        artist_name="Artist",
    )

    with pytest.raises(WeeklyLedgerValidationError):
        rebuild_context_rows_from_weekly_ledger([mutate(valid)], {}, {"track:1"})


def test_duplicate_or_gapped_weekly_ranks_fail_closed() -> None:
    first = _ledger_row(
        "track",
        "2026-01-02",
        "track:1",
        1,
        3,
        3000,
        track_name="One",
        artist_name="Artist",
    )
    duplicate = _ledger_row(
        "track",
        "2026-01-02",
        "track:2",
        1,
        2,
        2000,
        track_name="Two",
        artist_name="Artist",
    )
    gap = (*duplicate[:3], 3, *duplicate[4:])
    inconsistent_first = (*first[:3], 2, *first[4:])
    inconsistent_second = (*duplicate[:3], 1, *duplicate[4:])

    with pytest.raises(WeeklyLedgerValidationError, match="duplicate ledger weekly rank"):
        rebuild_context_rows_from_weekly_ledger([first, duplicate], {}, {"track:1", "track:2"})
    with pytest.raises(WeeklyLedgerValidationError, match="not contiguous"):
        rebuild_context_rows_from_weekly_ledger([first, gap], {}, {"track:1", "track:2"})
    with pytest.raises(WeeklyLedgerValidationError, match="disagrees with ranking facts"):
        rebuild_context_rows_from_weekly_ledger(
            [inconsistent_first, inconsistent_second],
            {},
            {"track:1", "track:2"},
        )
    with pytest.raises(WeeklyLedgerValidationError, match="exceeds configured chart limit"):
        rebuild_context_rows_from_weekly_ledger(
            [first, (*duplicate[:3], 2, *duplicate[4:])],
            {},
            {"track:1", "track:2"},
            track_top_n=1,
        )


def test_result_is_order_stable_and_keeps_lifetime_only_and_chart_only_entities() -> None:
    rows = [
        _ledger_row(
            "track",
            "2026-01-02",
            f"track:{entity_id}",
            rank,
            5,
            5000,
            track_name=f"Track {entity_id}",
            artist_name="Artist",
        )
        for entity_id, rank in ((2, 1), (10, 2))
    ]
    candidates = {"track:2", "track:10", "artist:30"}
    metrics = {"artist:30": (4, 4000)}
    expected = rebuild_context_rows_from_weekly_ledger(rows, metrics, candidates)
    shuffled = list(rows)
    random.Random(1234).shuffle(shuffled)

    assert rebuild_context_rows_from_weekly_ledger(shuffled, metrics, candidates) == expected
    by_key = {row[0]: row for row in expected}
    assert by_key["artist:30"] == (
        "artist:30",
        4,
        4000,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    assert by_key["track:2"][1:3] == (0, 0)


def test_non_candidate_metric_or_ledger_entity_fails_closed() -> None:
    row = _ledger_row(
        "artist",
        "2026-01-02",
        "artist:2",
        1,
        1,
        1000,
        artist_name="Artist",
    )
    with pytest.raises(WeeklyLedgerValidationError, match="not an active candidate"):
        rebuild_context_rows_from_weekly_ledger([row], {}, {"artist:1"})
    with pytest.raises(WeeklyLedgerValidationError, match="not an active candidate"):
        rebuild_context_rows_from_weekly_ledger([], {"artist:2": (1, 1000)}, {"artist:1"})

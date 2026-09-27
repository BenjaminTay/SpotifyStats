from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.domains.billboard import detail_summary, detail_views, details
from backend.domains.music_search.context import MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION

pytestmark = pytest.mark.unit


def _args(
    track_id: int,
    *,
    week_start_hour: int = 12,
    dynamic_threshold: bool = True,
    merge_level: int = 2,
    year_start: int | None = None,
    year_end: int | None = None,
) -> tuple:
    return (
        track_id,
        30_000,
        True,
        30,
        20,
        20,
        4,
        week_start_hour,
        year_start,
        year_end,
        dynamic_threshold,
        5,
        True,
        merge_level,
        False,
    )


def _snapshot_key(values: dict) -> str:
    return (
        f"snapshot-h{values['bb_week_start_hour']}"
        f"-l{values['merge_level']}-d{int(values['dynamic_threshold'])}"
    )


def test_singleton_track_count_uses_logical_weighted_facts_instead_of_chart_fallback(
    monkeypatch,
) -> None:
    class _Connection:
        def close(self) -> None:
            pass

    monkeypatch.setattr(details, "get_db", lambda **_kwargs: _Connection())
    monkeypatch.setattr(
        details,
        "resolve_track_aggregation_scope",
        lambda *_args, **_kwargs: SimpleNamespace(member_track_ids=(1493,)),
    )
    weighted = pd.DataFrame(
        {
            "track_id": [1493, 1493, 48498],
            "play_count": [378, 1, 1],
        }
    )

    assert details._grouped_track_play_count(1493, 2, weighted, fallback=380) == 379


def _published_detail_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        f"""
        CREATE TABLE music_search_snapshot_meta (
            snapshot_key TEXT PRIMARY KEY,
            filter_fingerprint TEXT,
            status TEXT,
            builder_version TEXT
        );
        INSERT INTO music_search_snapshot_meta VALUES
            ('snapshot-h12-l2-d1', 'snapshot-h12-l2-d1', 'ready',
             '{MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION}'),
            ('snapshot-h13-l3-d0', 'snapshot-h13-l3-d0', 'ready',
             '{MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION}');

        CREATE TABLE music_search_index_state (
            state_id INTEGER PRIMARY KEY,
            active_generation_id TEXT
        );
        INSERT INTO music_search_index_state VALUES (1, 'generation-1');

        CREATE TABLE music_search_documents (
            generation_id TEXT,
            entity_key TEXT,
            kind TEXT,
            merge_level INTEGER,
            track_id INTEGER,
            label TEXT,
            artist_name TEXT,
            album_project_id INTEGER,
            album_id INTEGER,
            album_name TEXT,
            membership_role TEXT,
            cover_album_id INTEGER,
            cover_url TEXT,
            cover_source TEXT,
            presentation_status TEXT
        );
        INSERT INTO music_search_documents VALUES
            ('generation-1', 'track:10', 'track', 2, 10, 'Charted', 'Artist',
             NULL, NULL, NULL, NULL, NULL, NULL, 'fallback', 'fallback'),
            ('generation-1', 'track:10', 'track', 3, 10, 'Charted', 'Artist',
             NULL, NULL, NULL, NULL, NULL, NULL, 'fallback', 'fallback'),
            ('generation-1', 'track:20', 'track', 2, 20, 'Uncharted', 'Artist',
             NULL, NULL, NULL, NULL, NULL, NULL, 'fallback', 'fallback'),
            ('generation-1', 'track:30', 'track', 2, 30, 'Zero Count', 'Artist',
             NULL, NULL, NULL, NULL, NULL, NULL, 'fallback', 'fallback');

        CREATE TABLE music_search_entity_context (
            snapshot_key TEXT,
            entity_key TEXT,
            play_events INTEGER,
            total_ms INTEGER,
            peak_position INTEGER,
            peak_weeks INTEGER,
            weeks_on_chart INTEGER,
            weeks_at_no1 INTEGER,
            power_score INTEGER,
            power_rank INTEGER,
            first_week TEXT,
            latest_week TEXT,
            first_peak_week TEXT
        );
        INSERT INTO music_search_entity_context VALUES
            ('snapshot-h12-l2-d1', 'track:10', 20, 2000000,
             1, 1, 3, 1, 500, 7, '2026-01-02', '2026-01-30', '2026-01-09'),
            ('snapshot-h12-l2-d1', 'track:20', 47, 4700000,
             NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
            ('snapshot-h12-l2-d1', 'track:30', 0, 5000,
             NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
            ('snapshot-h13-l3-d0', 'track:10', 31, 3100000,
             2, 1, 2, 0, 300, 11, '2025-12-05', '2025-12-19', '2025-12-05');

        CREATE TABLE music_search_weekly_chart_context (
            snapshot_key TEXT,
            family TEXT,
            week TEXT,
            entity_key TEXT,
            rank INTEGER,
            play_count INTEGER,
            total_ms INTEGER,
            stable_sort_key TEXT
        );
        INSERT INTO music_search_weekly_chart_context VALUES
            ('snapshot-h12-l2-d1', 'track', '2026-01-02', 'track:10', 2, 3, 300000, '{{}}'),
            ('snapshot-h12-l2-d1', 'track', '2026-01-09', 'track:10', 1, 4, 400000, '{{}}'),
            ('snapshot-h12-l2-d1', 'track', '2026-01-30', 'track:10', 3, 5, 500000, '{{}}'),
            ('snapshot-h13-l3-d0', 'track', '2025-12-05', 'track:10', 2, 5, 500000, '{{}}'),
            ('snapshot-h13-l3-d0', 'track', '2025-12-19', 'track:10', 4, 6, 600000, '{{}}');

        CREATE TABLE track_l1_identities (
            l1_id INTEGER PRIMARY KEY,
            representative_track_id INTEGER
        );
        INSERT INTO track_l1_identities VALUES (10, 11), (20, 20), (30, 30);
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT);
        INSERT INTO artists VALUES (1, 'Artist');
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT,
            artist_id INTEGER,
            spotify_track_id TEXT
        );
        INSERT INTO tracks VALUES
            (10, 'Charted shell', 1, NULL),
            (11, 'Charted representative', 1, NULL),
            (20, 'Uncharted', 1, NULL),
            (30, 'Zero Count', 1, NULL);

        -- This deliberately disagrees with the published snapshot. The agent
        -- fast path must never read it for exact ranked totals.
        CREATE TABLE agg_weekly_tracks (
            billboard_week TEXT,
            l1_id INTEGER,
            track_id INTEGER,
            play_count INTEGER,
            total_ms INTEGER
        );
        INSERT INTO agg_weekly_tracks VALUES ('2026-02-06', 10, 10, 999, 999999);
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def published_detail_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    database = tmp_path / "published-detail.db"
    _published_detail_db(database)

    def get_db(readonly: bool = True) -> sqlite3.Connection:
        del readonly
        conn = sqlite3.connect(database)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(detail_summary, "get_db", get_db)
    monkeypatch.setattr(
        detail_summary,
        "build_music_search_filter_context",
        lambda _conn, values: SimpleNamespace(filter_fingerprint=_snapshot_key(values)),
    )
    monkeypatch.setattr(
        detail_summary,
        "canonical_artist_names_for_effective_tracks",
        lambda _conn, track_ids: {track_id: ["Artist"] for track_id in track_ids},
    )
    monkeypatch.setattr(
        detail_summary,
        "resolve_artist_id",
        lambda _conn, _artist_id: SimpleNamespace(display_name="Artist"),
    )
    monkeypatch.setattr(detail_summary, "_track_meta", lambda _conn, _track_id: None)
    monkeypatch.setattr(
        detail_summary,
        "_document_track_attribution",
        lambda _conn, document: {"canonical_track_id": int(document["track_id"])},
    )
    return database


def test_agent_summary_uses_one_exact_ledger_for_history_and_ranked_total(
    published_detail_db: Path,
) -> None:
    del published_detail_db

    result = detail_summary.build_track_detail_summary(_args(10))

    assert result is not None
    assert result["representative_track_id"] == 11
    assert result["effective_play_count"] == 20
    assert result["summary"]["total_plays"] == 20
    assert result["summary"]["total_chart_plays"] == 12
    assert sum(row["play_count"] for row in result["history"]) == 12
    assert [row["change"] for row in result["history"]] == ["NEW", "▲1", "RE"]
    assert result["chart_data"]["x"] == [
        "2026-01-02",
        "2026-01-09",
        None,
        "2026-01-30",
    ]


def test_agent_summary_selects_nondefault_exact_contract_and_rejects_missing_variant(
    published_detail_db: Path,
) -> None:
    del published_detail_db

    result = detail_summary.build_track_detail_summary(
        _args(10, week_start_hour=13, dynamic_threshold=False, merge_level=3)
    )

    assert result is not None
    assert result["effective_play_count"] == 31
    assert result["summary"]["total_chart_plays"] == 11
    assert result["summary"]["power_rank"] == 11
    assert (
        detail_summary.build_track_detail_summary(
            _args(10, week_start_hour=13, dynamic_threshold=True, merge_level=3)
        )
        is None
    )
    assert (
        detail_summary.build_track_detail_summary(_args(10, year_start=2026, year_end=2026)) is None
    )


def test_agent_summary_preserves_uncharted_and_zero_count_playback_facts(
    published_detail_db: Path,
) -> None:
    del published_detail_db

    uncharted = detail_summary.build_track_detail_summary(_args(20))
    zero_count = detail_summary.build_track_detail_summary(_args(30))

    assert uncharted is not None
    assert uncharted["chart_status"] == "not_charted"
    assert uncharted["effective_play_count"] == 47
    assert uncharted["summary"] is None
    assert uncharted["history"] == []
    assert zero_count is not None
    assert zero_count["chart_status"] == "not_charted"
    assert zero_count["effective_play_count"] == 0
    assert zero_count["summary"] is None
    assert detail_summary.build_track_detail_summary(_args(999)) is None


def test_agent_summary_rejects_an_incomplete_published_ledger(
    published_detail_db: Path,
) -> None:
    conn = sqlite3.connect(published_detail_db)
    conn.execute(
        """DELETE FROM music_search_weekly_chart_context
             WHERE snapshot_key='snapshot-h12-l2-d1'
               AND entity_key='track:10' AND week='2026-01-30'"""
    )
    conn.commit()
    conn.close()

    assert detail_summary.build_track_detail_summary(_args(10)) is None


def test_exact_snapshot_miss_uses_the_explicit_full_builder_fallback(
    published_detail_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del published_detail_db
    full = {"found": False, "meta": None, "fallback": True}
    monkeypatch.setattr(detail_views, "get_track_history", lambda *_args, **_kwargs: full)
    monkeypatch.setattr(detail_views, "detail_revision_state", lambda: ("exact-miss",))
    detail_views._track_detail_cached.cache_clear()

    result = detail_views.get_track_detail_view(
        *_args(999, week_start_hour=13, dynamic_threshold=True, merge_level=3),
        view="agent",
    )

    assert result is full


def test_full_builder_keeps_grouped_play_count_and_published_stable_power_rank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    weekly = [
        {
            "track_id": 10,
            "track_name": "Song",
            "artist_name": "Artist",
            "billboard_week": "2026-01-02",
            "rank": 1,
            "play_count": 12,
            "running_peak": 1,
            "running_wks": 1,
            "running_peak_wks": 1,
        }
    ]
    monkeypatch.setattr(
        details,
        "compute_billboard_data",
        lambda *_args, **_kwargs: {
            "weekly": weekly,
            "track_summary": [
                {
                    "track_id": 10,
                    "peak_position": 1,
                    "weeks_on_chart": 1,
                    "weeks_at_peak": 1,
                    "first_week": "2026-01-02",
                    "last_week": "2026-01-02",
                    "first_peak_week": "2026-01-02",
                    "total_chart_plays": 12,
                    "total_plays": 17,
                    "weeks_at_no1": 1,
                }
            ],
            # A score-only re-sort would incorrectly make track 10 rank 1.
            "power_scores": [
                {"track_id": 10, "power_score": 100, "power_rank": 2},
                {"track_id": 9, "power_score": 100, "power_rank": 1},
            ],
        },
    )
    monkeypatch.setattr(
        details,
        "_load_detail_weighted_frame",
        lambda **_kwargs: pd.DataFrame(
            [
                {"track_id": 10, "play_count": 17},
                {"track_id": 11, "play_count": 12},
            ]
        ),
    )
    monkeypatch.setattr(
        details,
        "_get_track_spotify_meta",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        details,
        "get_db",
        lambda readonly=True: SimpleNamespace(close=lambda: None),
    )
    monkeypatch.setattr(
        details,
        "resolve_track_aggregation_scope",
        lambda *_args, **_kwargs: SimpleNamespace(member_track_ids=(10, 11)),
    )
    monkeypatch.setattr(details, "get_track_artist_names_map", lambda: {10: ["Artist"]})
    monkeypatch.setattr(details, "_track_primary_artist_name", lambda *_args: "Artist")
    monkeypatch.setattr(
        details,
        "_get_track_presentation_fields",
        lambda *_args: {"cover_url": None, "album_attribution": None},
    )
    monkeypatch.setattr(
        details,
        "_track_identity_fields",
        lambda track_id: {"l1_id": track_id, "representative_track_id": track_id},
    )

    result = details.get_track_history(*_args(10))

    assert result["effective_play_count"] == 29
    assert result["summary"]["total_plays"] == 29
    assert result["summary"]["power_rank"] == 2

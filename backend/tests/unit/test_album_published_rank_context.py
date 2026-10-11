"""Album details preserve complete legacy facts without global rank builds."""

import json
import sqlite3

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.core import db
from backend.services import analysis_stats_service as analysis
from backend.services import entity_stats_service as stats
from backend.services import versus_rank_context_service as ranks
from backend.tests.unit import test_versus_rank_context

base_isolated = test_versus_rank_context.base_isolated
isolated = test_versus_rank_context.isolated
pytestmark = pytest.mark.unit


def sample(conn):
    row = conn.execute(
        """SELECT ap.canonical_name, ar.artist_name FROM album_projects ap
           JOIN artists ar ON ar.artist_id=ap.artist_id
           JOIN album_project_tracks apt ON apt.project_id=ap.project_id
           JOIN plays p ON p.track_id=apt.track_id
           ORDER BY ap.project_id LIMIT 1"""
    ).fetchone()
    return row[0], row[1]


@pytest.mark.parametrize("level,dynamic", [(2, True), (2, False), (3, True), (3, False)])
def test_complete_payload_matches_legacy_and_never_loads_global_plays(
    isolated, monkeypatch, level, dynamic
):
    conn = db.get_db(readonly=True)
    try:
        filters, _, _, _ = ranks.request_context(
            conn, {"merge_level": level, "dynamic_threshold": dynamic}
        )
        args = {k: filters[k] for k in (*ranks.LOAD_FILTERS, "merge_level")}
        album, artist = sample(conn)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: False)
        expected = stats._build_album_stats(conn, album, artist, **args)
        assert expected["found"]
        for selected in ranks.default_configurations(conn):
            ranks.ensure(conn, selected)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        load = stats.load_plays

        def bounded(*a, **kw):
            assert kw.get("extra_where"), "global playback frame materialised"
            return load(*a, **kw)

        monkeypatch.setattr(stats, "load_plays", bounded)
        monkeypatch.setattr(stats, "_ranks", lambda *a, **kw: pytest.fail("global album ranks"))
        monkeypatch.setattr(
            stats, "_top250_counts", lambda *a, **kw: pytest.fail("global Top250 frame")
        )
        assert stats._build_album_stats(conn, album, artist, **args) == expected
    finally:
        conn.close()


@pytest.mark.parametrize("level", [2, 3])
def test_missing_and_source_drift_fail_without_get_maintenance(isolated, monkeypatch, level):
    conn = db.get_db(readonly=True)
    try:
        filters, _, _, _ = ranks.request_context(conn, {"merge_level": level})
        args = {k: filters[k] for k in (*ranks.LOAD_FILTERS, "merge_level")}
        album, artist = sample(conn)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        with pytest.raises(HTTPException) as missing:
            stats._build_album_stats(conn, album, artist, **args)
        assert missing.value.status_code == 503
        ranks.ensure(conn, filters)
        if level == 3:
            with pytest.raises(HTTPException) as compatibility_missing:
                stats._build_album_stats(conn, album, artist, **args)
            assert compatibility_missing.value.status_code == 503
            ranks.ensure(conn, {**filters, "merge_level": 2})
        with sqlite3.connect(isolated[0]) as writer:
            writer.execute(
                "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
            )
        monkeypatch.setattr(
            ranks, "ensure", lambda *a, **kw: pytest.fail("GET rebuilt publication")
        )
        with pytest.raises(HTTPException) as stale:
            stats._build_album_stats(conn, album, artist, **args)
        assert stale.value.status_code == 503
    finally:
        conn.close()


@pytest.mark.parametrize("level,dynamic", [(2, True), (2, False), (3, True), (3, False)])
@pytest.mark.parametrize("all_short", [False, True])
def test_zero_count_duration_and_global_bounds_match_complete_legacy(
    isolated, monkeypatch, level, dynamic, all_short
):
    conn = db.get_db(readonly=True)
    try:
        album, artist = sample(conn)
        keys = stats._resolve_album_project_song_keys(conn, album, artist, level)
        ids = stats._album_member_l1_ids(conn, keys, level)
        with sqlite3.connect(isolated[0]) as writer:
            if all_short:
                writer.execute("UPDATE plays SET ms_played=1")
            else:
                writer.execute(
                    """UPDATE plays SET ms_played=1000 WHERE track_id IN
                       (SELECT track_id FROM track_l1_source_links
                        WHERE l1_id IN (SELECT value FROM json_each(?)))""",
                    (json.dumps(ids),),
                )
        filters, _, _, _ = ranks.request_context(
            conn, {"merge_level": level, "dynamic_threshold": dynamic}
        )
        args = {k: filters[k] for k in (*ranks.LOAD_FILTERS, "merge_level")}
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: False)
        expected = stats._build_album_stats(conn, album, artist, **args)
        assert expected["found"] and expected["summary"]["total_plays"] == 0
        for selected in ranks.default_configurations(conn):
            ranks.ensure(conn, selected)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        assert stats._build_album_stats(conn, album, artist, **args) == expected
    finally:
        conn.close()


@pytest.mark.parametrize("level", [2, 3])
def test_seed_catalog_complete_payloads_preserve_source_and_project_membership(
    isolated, monkeypatch, level
):
    conn = db.get_db(readonly=True)
    try:
        filters, _, _, _ = ranks.request_context(conn, {"merge_level": level})
        args = {k: filters[k] for k in (*ranks.LOAD_FILTERS, "merge_level")}
        albums = conn.execute(
            """SELECT DISTINCT ap.canonical_name, ar.artist_name FROM album_projects ap
               JOIN artists ar ON ar.artist_id=ap.artist_id ORDER BY ap.project_id"""
        ).fetchall()
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: False)
        expected = [stats._build_album_stats(conn, row[0], row[1], **args) for row in albums]
        for selected in ranks.default_configurations(conn):
            ranks.ensure(conn, selected)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        for row, legacy in zip(albums, expected):
            actual = stats._build_album_stats(conn, row[0], row[1], **args)
            assert actual == legacy, (
                tuple(row),
                stats._resolve_album_project_song_keys(conn, row[0], row[1], level),
            )
    finally:
        conn.close()


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_ms": 60000},
        {"period": "last_4_weeks"},
        {"period": "custom", "start_date": "2020-01-01", "end_date": "2025-12-31"},
    ],
)
def test_unsupported_scope_retains_legacy_path(isolated, monkeypatch, overrides):
    conn = db.get_db(readonly=True)
    try:
        filters, _, _, _ = ranks.request_context(conn)
        args = {k: filters[k] for k in (*ranks.LOAD_FILTERS, "merge_level")}
        args.update(overrides)
        album, artist = sample(conn)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: False)
        expected = stats._build_album_stats(conn, album, artist, **args)
        monkeypatch.setattr(stats, "_is_primary_connection", lambda _: True)
        monkeypatch.setattr(ranks, "read", lambda *a, **kw: pytest.fail("non-default publication"))
        assert stats._build_album_stats(conn, album, artist, **args) == expected
    finally:
        conn.close()


def test_top250_boundary_preserves_multiple_presentations_of_one_id(isolated, monkeypatch):
    conn = db.get_db(readonly=True)
    try:
        events = pd.DataFrame(
            [
                dict(
                    track_id=1000000 + i,
                    track_name=f"Song {i}",
                    artist_name="Other",
                    album_name="Source",
                    ts=pd.Timestamp("2026-03-01T12:00:00Z"),
                    ts_date="2026-03-01",
                    ms_played=90000,
                )
                for i in range(310)
            ]
        )
        duplicate = events.iloc[249].copy()
        duplicate["artist_name"] = "Target"
        events = pd.concat([events, duplicate.to_frame().T], ignore_index=True)
        events["track_id"] = events["track_id"].astype(int)
        events["ms_played"] = events["ms_played"].astype(int)
        periods = {p: analysis.resolve_period(events, p, None, None) for p in ranks.PERIODS}
        duration = analysis.build_duration_frame(events)
        rank_map = ranks._rank_map(
            conn, events, duration, "track", {"merge_level": 2, "include_compilations": False}
        )
        assert rank_map[str(1000249)] == 250
        context = {"periods": periods, "ranks": {"track": {p: rank_map for p in periods}}}
        selected = []
        monkeypatch.setattr(stats, "_album_source_track_ids", lambda _, ids: ids)

        def loader(_, ids, **kwargs):
            selected.extend(ids)
            return ids

        def load(_, **kwargs):
            frame = events[events["track_id"].isin(kwargs["_loader"])].copy()
            return frame, frame, periods["lifetime"]

        monkeypatch.setattr(stats, "_scoped_play_loader", loader)
        monkeypatch.setattr(stats, "load_period_plays", load)
        filters = dict(
            min_ms=30000,
            music_only=True,
            merge_enabled=True,
            dynamic_threshold=True,
            max_merge_gap_minutes=5,
        )
        actual = stats._published_album_top250_counts(conn, context, filters, [""], "Target")
        expected = {
            p: stats._top250_count(
                conn,
                analysis.filter_period_events(events, resolved),
                resolved,
                album_names=[""],
                artist_name="Target",
            )
            for p, resolved in periods.items()
        }
        assert actual == expected == {p: 0 for p in periods}
        assert len(selected) == 250 and 1000249 in selected
    finally:
        conn.close()

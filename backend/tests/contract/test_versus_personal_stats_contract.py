"""Batch personal facts agree with independent complete-library timelines."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest
from fastapi import HTTPException

from backend.core import db
from backend.domains.playback.album_projects import (
    apply_canonical_song_keys,
    load_album_project_membership,
)
from backend.domains.playback.logical_timeline import get_listening_duration_frame
from backend.domains.playback.track_groups import resolve_track_aggregation_scope
from backend.services import entity_stats_service
from backend.services import versus_personal_stats_service as service
from backend.services.analysis_stats_service import (
    _daily_metrics,
    _daily_trend,
    _summary,
    build_duration_frame,
)
from backend.services.versus_personal_context import resolve_selection

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("kind", ["track", "album", "artist"])
@pytest.mark.parametrize("timed", [False, True])
def test_only_artist_batch_skips_unused_primary_projection(seed_conn, monkeypatch, kind, timed):
    calls = []
    original = service.canonicalize_artist_frame

    def counted(frame, conn, **kwargs):
        calls.append(len(frame))
        return original(frame, conn, **kwargs)

    service._RESULT_CACHE.cache_clear()
    monkeypatch.setattr(service, "canonicalize_artist_frame", counted)
    result = service.build_personal_stats(
        seed_conn,
        kind,
        selection(seed_conn, kind, 2, 2),
        {"merge_level": 2},
        timings={} if timed else None,
    )
    assert len(result["entities"]) == 2
    assert len(calls) == (0 if kind == "artist" else 2)


def selection(conn, kind, merge_level, count):
    if kind == "track":
        ids = [
            int(row[0])
            for row in conn.execute("SELECT l1_id FROM track_l1_identities ORDER BY l1_id")
        ]
        unique = {}
        for track_id in ids:
            scope = resolve_track_aggregation_scope(conn, track_id, merge_level)
            unique.setdefault(scope.primary_track_id, track_id)
        return list(unique.values())[:count]
    if kind == "album":
        membership = load_album_project_membership(conn, merge_level, include_compilations=True)
        projects = membership.drop_duplicates("project_id")
        return [
            dict(album_name=row.album_project_name, artist_name=row.artist_name)
            for row in projects.itertuples()
        ][:count]
    from backend.domains.metadata.artist_identity import get_artist_identity_map

    return list(dict.fromkeys(row.display_name for row in get_artist_identity_map(conn).values()))[
        :count
    ]


def oracle(conn, kind, items, params):
    loader = db.load_plays_for_artists if kind == "artist" else db.load_plays
    all_events = loader(
        conn,
        **{
            key: params[key]
            for key in (
                "min_ms",
                "music_only",
                "merge_enabled",
                "dynamic_threshold",
                "max_merge_gap_minutes",
            )
        },
    )
    all_durations = get_listening_duration_frame(all_events)
    assert all_durations is not None
    if kind == "album":
        all_events = apply_canonical_song_keys(all_events, conn, params["merge_level"])
        all_durations = apply_canonical_song_keys(all_durations, conn, params["merge_level"])
    selected = resolve_selection(conn, kind, items, params["merge_level"])
    result = {}
    for entity in selected:
        if kind == "track":
            scope = resolve_track_aggregation_scope(conn, entity.track_id, params["merge_level"])
            events = all_events[all_events["track_id"].isin(scope.member_track_ids)]
            durations = all_durations[all_durations["track_id"].isin(scope.member_track_ids)]
        elif kind == "album":
            # Resolve the full-details project membership independently, rather
            # than validating the batch resolver against its own selected keys.
            expected_keys = entity_stats_service._resolve_album_project_song_keys(
                conn,
                entity.album_name,
                entity.artist_name,
                params["merge_level"],
                entity.project_id,
            )
            events = all_events[all_events["canonical_song_key"].isin(expected_keys)]
            durations = all_durations[all_durations["canonical_song_key"].isin(expected_keys)]
        else:
            events = all_events[all_events["artist_name"] == entity.artist_name]
            durations = all_durations[all_durations["artist_name"] == entity.artist_name]
        slices = build_duration_frame(events, duration_source=durations)
        summary = _summary(events, slices)
        daily_metrics = _daily_metrics(summary)
        daily = _daily_trend(events, slices)
        result[entity.entity_key] = {
            **{name: summary[name] for name in ("total_plays", "total_hours", "active_days")},
            **{name: daily_metrics[name] for name in ("avg_daily_plays", "avg_daily_hours")},
            "max_daily_plays": max((row["plays"] for row in daily), default=0),
        }
    return result


@pytest.mark.parametrize("kind", ["track", "album", "artist"])
@pytest.mark.parametrize("count", [2, 3, 4])
@pytest.mark.parametrize("merge_level,dynamic", [(2, False), (2, True), (3, False), (3, True)])
def test_batch_matches_complete_library_without_global_builder(
    seed_conn, monkeypatch, kind, count, merge_level, dynamic
):
    params = dict(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=dynamic,
        max_merge_gap_minutes=5,
        merge_level=merge_level,
        include_compilations=True,
    )
    items = selection(seed_conn, kind, merge_level, count)
    assert len(items) == count
    expected = oracle(seed_conn, kind, items, params)
    calls = []
    original = service._load_target_timeline

    def bounded(conn, ids, filters, **options):
        calls.append(ids)
        return original(conn, ids, filters, **options)

    def forbidden(*args, **kwargs):
        pytest.fail("batch entered a full detail, global ranking, or full-library loader")

    monkeypatch.setattr(service, "_load_target_timeline", bounded)
    for name in (
        "_ranks",
        "_top250_counts",
        "_build_track_stats",
        "_build_album_stats",
        "_build_artist_stats",
    ):
        monkeypatch.setattr(entity_stats_service, name, forbidden)
    monkeypatch.setattr(db, "load_plays", forbidden)
    monkeypatch.setattr(db, "load_plays_for_artists", forbidden)
    sql = []
    seed_conn.set_trace_callback(sql.append)
    actual = service.build_personal_stats(seed_conn, kind, items, params)
    seed_conn.set_trace_callback(None)
    assert len(calls) == 1
    assert actual["statistics_contract_version"] == "versus_personal_v1"
    assert actual["filter_fingerprint"] and actual["source_revision"]
    assert {row["entity_key"]: row["metrics"] for row in actual["entities"]} == expected
    assert all(
        not query.lstrip()
        .upper()
        .startswith(("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"))
        for query in sql
    )


@pytest.mark.parametrize("kind", ["track", "album", "artist"])
def test_unknown_selection_is_unavailable_without_fabricated_zero(seed_conn, kind):
    known = selection(seed_conn, kind, 2, 2)[0]
    unknown = (
        999_999_999
        if kind == "track"
        else (dict(album_name="missing", artist_name="missing") if kind == "album" else "missing")
    )
    actual = service.build_personal_stats(seed_conn, kind, [known, unknown], {"merge_level": 2})
    assert actual["entities"][1]["status"] == "unavailable"
    assert actual["entities"][1]["metrics"] is None
    assert actual["entities"][0]["status"] != "unavailable"


def test_known_artist_without_history_is_true_zero(seed_conn, use_seed_db):
    known = selection(seed_conn, "artist", 2, 2)[0]
    with sqlite3.connect(use_seed_db) as writer:
        writer.execute("INSERT INTO artists(artist_name) VALUES('Known empty artist')")
    result = service.build_personal_stats(
        seed_conn, "artist", [known, "Known empty artist"], {"merge_level": 2}
    )
    empty = result["entities"][1]
    assert empty["status"] == "empty" and empty["found"] is False
    assert empty["metrics"] == dict(
        total_plays=0,
        total_hours=0.0,
        active_days=0,
        avg_daily_plays=0.0,
        avg_daily_hours=0.0,
        max_daily_plays=0,
    )


def test_source_drift_during_read_refuses_mixed_revision(seed_conn, use_seed_db, monkeypatch):
    items = selection(seed_conn, "track", 2, 2)
    original = service._load_target_timeline

    def drift(conn, ids, filters, **options):
        frames = original(conn, ids, filters, **options)
        with sqlite3.connect(use_seed_db) as writer:
            writer.execute(
                "UPDATE plays SET ms_played=ms_played+1 WHERE play_id=(SELECT MIN(play_id) FROM plays)"
            )
        return frames

    monkeypatch.setattr(service, "_load_target_timeline", drift)
    with pytest.raises(HTTPException) as error:
        service.build_personal_stats(seed_conn, "track", items, {"merge_level": 2})
    assert error.value.status_code == 503
    assert error.value.detail["error"] == "snapshot_unavailable"


def test_identity_drift_during_selection_refuses_mixed_revision(
    seed_conn, use_seed_db, monkeypatch
):
    from backend.services import versus_personal_context

    items = selection(seed_conn, "track", 2, 2)
    original = versus_personal_context.resolve_selection

    def drift(conn, kind, items, level, **kwargs):
        selected = original(conn, kind, items, level, **kwargs)
        with sqlite3.connect(use_seed_db) as writer:
            writer.execute(
                "UPDATE tracks SET track_name=track_name || ' revised' WHERE track_id=(SELECT MIN(track_id) FROM tracks)"
            )
        return selected

    monkeypatch.setattr(versus_personal_context, "resolve_selection", drift)
    with pytest.raises(HTTPException) as error:
        service.build_personal_stats(seed_conn, "track", items, {"merge_level": 2})
    assert error.value.status_code == 503
    assert error.value.detail["error"] == "snapshot_unavailable"


@pytest.mark.parametrize("kind", ["track", "album", "artist"])
def test_all_unknowns_keep_distinct_unavailable_entities(seed_conn, kind):
    items = (
        [999_999_999, 999_999_998]
        if kind == "track"
        else (
            [
                dict(album_name="missing-a", artist_name="missing"),
                dict(album_name="missing-b", artist_name="missing"),
            ]
            if kind == "album"
            else ["missing-a", "missing-b"]
        )
    )
    result = service.build_personal_stats(seed_conn, kind, items, {"merge_level": 2})
    assert len({row["entity_key"] for row in result["entities"]}) == 2
    assert all(
        row["status"] == "unavailable" and row["metrics"] is None for row in result["entities"]
    )


def test_source_timings_do_not_change_or_expand_statistics_facts(seed_conn):
    items = selection(seed_conn, "track", 2, 2)
    service._RESULT_CACHE.cache_clear()
    timings = {}
    expected = service.build_personal_stats(
        seed_conn, "track", items, {"merge_level": 2}, timings=timings
    )
    assert set(timings) == {
        "identity",
        "source_context",
        "target_sql",
        "timeline",
        "attribution",
        "metrics",
        "source_fence",
    }
    assert all(value >= 0 for value in timings.values())
    cached_timings = {}
    actual = service.build_personal_stats(
        seed_conn, "track", items, {"merge_level": 2}, timings=cached_timings
    )
    assert actual == expected
    assert set(cached_timings) == {"identity", "source_context", "source_fence"}


def test_response_cache_is_bounded_and_reordering_reuses_union(seed_conn, monkeypatch):
    items = selection(seed_conn, "track", 2, 4)
    service._RESULT_CACHE.cache_clear()
    before = service.build_personal_stats(seed_conn, "track", items, {"merge_level": 2})

    def forbidden(*a, **kw):
        pytest.fail("Same exact entity set reloaded the source timeline")

    monkeypatch.setattr(service, "_load_target_timeline", forbidden)
    after = service.build_personal_stats(
        seed_conn, "track", list(reversed(items)), {"merge_level": 2}
    )
    assert after["entities"] == list(reversed(before["entities"]))
    after["entities"][0]["metrics"]["total_plays"] = -1
    again = service.build_personal_stats(seed_conn, "track", items, {"merge_level": 2})
    assert again == before
    assert service._RESULT_CACHE.cache_stats()["size"] == 1
    for index in range(150):
        service._RESULT_CACHE.put(("capacity", index), {"entities": []})
    assert service._RESULT_CACHE.cache_stats()["size"] == 128


def test_same_revision_parallel_batch_builds_one_union(seed_conn, monkeypatch):
    items = selection(seed_conn, "track", 2, 4)
    service._RESULT_CACHE.cache_clear()
    original = service._load_target_timeline
    counter = [0]
    lock = Lock()

    def counted(*a, **kw):
        with lock:
            counter[0] += 1
        return original(*a, **kw)

    def build(index):
        conn = db.get_db(readonly=True)
        try:
            queue = items if index % 2 == 0 else list(reversed(items))
            return service.build_personal_stats(conn, "track", queue, {"merge_level": 2})
        finally:
            conn.close()

    monkeypatch.setattr(service, "_load_target_timeline", counted)
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(build, range(4)))
    assert counter[0] == 1
    assert results[0]["entities"] == list(reversed(results[1]["entities"]))


def test_missing_source_tracking_is_unavailable_not_user_validation(seed_conn, monkeypatch):
    from backend.services import versus_personal_context

    def missing(*a, **kw):
        raise ValueError("missing revision tracking")

    items = selection(seed_conn, "track", 2, 2)
    monkeypatch.setattr(versus_personal_context, "_revision_vector", missing)
    with pytest.raises(HTTPException) as error:
        service.build_personal_stats(seed_conn, "track", items, {"merge_level": 2})
    assert error.value.status_code == 503

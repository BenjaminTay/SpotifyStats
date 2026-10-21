"""Release comparison playback and ranks retain stable project identity."""

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.core import db
from backend.core.json_helpers import df_to_json
from backend.domains.billboard import persistent_cache as cache
from backend.services import release_cycle_comparison_service as service
from backend.services.versus_personal_context import resolve_selection
from backend.services.versus_personal_stats_service import (
    _album_song_frames,
    _load_target_timeline,
)
from backend.tests.unit import test_release_cycle_comparison_data as comparison

base_isolated = comparison.base_isolated
rank_isolated = comparison.rank_isolated
isolated = comparison.isolated
pytestmark = pytest.mark.unit


def test_distinct_editions_share_project_playback_without_being_rejected(isolated):
    filters = comparison._filters()
    _, _, weekly_album = comparison._publish_oracle(filters)
    items, params, selections, _ = _selection(filters, weekly_album, 2)
    first = items[0]
    project = selections[0].project_id
    conn = db.get_db(readonly=False)
    try:
        conn.execute(
            "INSERT INTO albums(album_name,artist_id) SELECT 'Explicit Alternate Edition',artist_id FROM album_projects WHERE project_id=?",
            (project,),
        )
        album_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO album_project_albums(project_id,album_id) VALUES(?,?)", (project, album_id)
        )
        conn.commit()
        editions = [
            first,
            {"artist_name": first["artist_name"], "album_name": "Explicit Alternate Edition"},
        ]
        with pytest.raises(ValueError, match="重复"):
            resolve_selection(conn, "album", editions, 2, filters=params)
    finally:
        conn.close()
    comparison._publish_oracle(filters)
    *_, events, ranks = service.prepare_project_comparison_data(filters, editions)
    assert not events[0].empty
    pd.testing.assert_frame_equal(events[0], events[1])
    pd.testing.assert_frame_equal(ranks[0], ranks[1])


def test_compare_api_computes_verified_projects_without_provider_enrichment(isolated, monkeypatch):
    from types import SimpleNamespace

    from backend.api.billboard import release_cycle as api
    from backend.core.access_surface import public_readonly_db_guard_active
    from backend.domains.playback.album_project_identity import resolve_album_project_identities
    from backend.providers.spotify.client import SpotifyProvider
    from backend.services.release_cycle_resolution import ReleaseTarget

    filters = comparison._filters()
    _, _, weekly_album = comparison._publish_oracle(filters)
    items, _, selections, events = _selection(filters, weekly_album, 2)
    anchors = [
        str(events.loc[events["canonical_song_key"].isin(selection.song_keys), "ts_date"].min())
        for selection in selections
    ]

    def installed_targets(conn, requested, level):
        assert public_readonly_db_guard_active()
        identities = resolve_album_project_identities(conn, requested, merge_level=level)
        return [
            ReleaseTarget(
                **item,
                identity=identity,
                artist_display_name=identity.artist_name,
                release_date=anchor,
                source_album_id="installed",
            )
            for item, identity, anchor in zip(requested, identities, anchors)
        ]

    monkeypatch.setattr(api, "resolve_release_targets", installed_targets)
    monkeypatch.setattr(
        SpotifyProvider,
        "get_cc_token",
        lambda *_: pytest.fail("read attempted provider enrichment"),
    )
    result = api.compare_releases(
        api.CompareRequest(items=items), filters, SimpleNamespace(merge_level=2), False
    )
    assert result["unavailable"] == []
    assert [item["project_id"] for item in result["comparisons"]] == [
        item.project_id for item in selections
    ]
    assert all(
        item["status"] == "ready" and item["release_date_precision"] == "day"
        for item in result["comparisons"]
    )
    assert all(item["metrics"]["release_week_plays"] > 0 for item in result["comparisons"])
    assert not public_readonly_db_guard_active()


def _selection(filters, weekly_album, level):
    items = (
        weekly_album.drop_duplicates("album_project_id")
        .head(2)[["artist_name", "album_name"]]
        .to_dict("records")
    )
    assert len(items) == 2
    _, params = service._resolve(
        (), {**vars(filters), "merge_level": level, "include_compilations": False}
    )
    conn = db.get_db(readonly=True)
    try:
        selections = resolve_selection(conn, "album", items, level, filters=params)
        assert all(item.track_ids and item.song_keys for item in selections)
        source_ids = tuple(sorted({track for item in selections for track in item.track_ids}))
        events, _ = _load_target_timeline(conn, source_ids, params, include_duration=False)
        events = events.loc[events["source_track_id"].isin(source_ids)].copy()
        events, _ = _album_song_frames(
            conn, events, pd.DataFrame(columns=["track_id", "track_name"]), level
        )
    finally:
        conn.close()
    return items, params, selections, events


@pytest.mark.parametrize("reason", ["entity_not_found", "release_ambiguous"])
def test_unresolvable_item_does_not_block_verified_release(isolated, monkeypatch, reason):
    from types import SimpleNamespace

    from backend.api.billboard import release_cycle as api
    from backend.domains.playback.album_project_identity import resolve_album_project_identities
    from backend.services.release_cycle_resolution import ReleaseTarget

    filters = comparison._filters()
    _, _, weekly_album = comparison._publish_oracle(filters)
    items, _, selections, events = _selection(filters, weekly_album, 2)
    ready = items[0]
    unknown = {"artist_name": ready["artist_name"], "album_name": "Unresolved release"}
    anchor = str(
        events.loc[events["canonical_song_key"].isin(selections[0].song_keys), "ts_date"].min()
    )

    def installed_targets(conn, requested, level):
        identity = resolve_album_project_identities(conn, [ready], merge_level=level)[0]
        return [
            ReleaseTarget(
                **ready,
                identity=identity,
                artist_display_name=identity.artist_name,
                release_date=anchor,
                source_album_id="installed",
            ),
            ReleaseTarget(**unknown, reason=reason),
        ]

    monkeypatch.setattr(api, "resolve_release_targets", installed_targets)
    result = api.compare_releases(
        api.CompareRequest(items=[ready, unknown]), filters, SimpleNamespace(merge_level=2), False
    )
    assert [row["album_name"] for row in result["comparisons"]] == [ready["album_name"]]
    assert result["comparisons"][0]["metrics"]["release_week_plays"] > 0
    assert result["unavailable"] == [{**unknown, "status": "unavailable", "reason": reason}]


@pytest.mark.parametrize("level", [2, 3])
def test_project_events_match_personal_membership_despite_source_presentation(
    isolated, monkeypatch, level
):
    filters = comparison._filters()
    _, _, weekly_album = comparison._publish_oracle(filters, level)
    items, _, selections, events = _selection(filters, weekly_album, level)
    original_loader = service._load_target_timeline

    def mismatched_source_presentation(*args, **kwargs):
        frame, durations = original_loader(*args, **kwargs)
        # A member may have a different source release and performing artist,
        # as with collaborations or songs played from a single compilation.
        frame = frame.copy()
        frame["artist_name"] = "Different performing artist"
        frame["album_name"] = "Different source release"
        return frame, durations

    monkeypatch.setattr(service, "_load_target_timeline", mismatched_source_presentation)
    *_, project_events, _ = service.prepare_project_comparison_data(filters, items, level)
    columns = ["play_id", "ts_date", "canonical_song_key"]
    for selection, actual in zip(selections, project_events):
        expected = events.loc[events["canonical_song_key"].isin(selection.song_keys)]
        assert not expected.empty
        assert len(actual) == len(expected)
        pd.testing.assert_frame_equal(
            actual[columns].reset_index(drop=True),
            expected[columns].reset_index(drop=True),
            check_dtype=False,
        )
        assert set(actual["artist_name"]) == {"Different performing artist"}
        assert set(actual["album_name"]) == {"Different source release"}


@pytest.mark.parametrize("level", [2, 3])
def test_published_album_ranks_follow_project_id_even_when_names_disagree(isolated, level):
    filters = comparison._filters()
    _, weekly_artist, weekly_album = comparison._publish_oracle(filters, level)
    items, params, selections, _ = _selection(filters, weekly_album, level)
    rows = []
    for index, (item, selection) in enumerate(zip(items, selections)):
        rows.extend(
            [
                {
                    "billboard_week": "2026-01-02",
                    "artist_name": "Unrelated display artist",
                    "album_name": "Unrelated display album",
                    "album_project_id": selection.project_id,
                    "rank": index + 7,
                    "play_count": index + 20,
                },
                {
                    "billboard_week": "2026-01-09",
                    **item,
                    "album_project_id": -selection.project_id,
                    "rank": 1,
                    "play_count": 999,
                },
            ]
        )
    context = cache.build_cache_context("weekly", params)
    cache.store_persisted_snapshot(
        context,
        {
            "weekly_artist": df_to_json(weekly_artist, ["billboard_week"]),
            "weekly_album": rows,
        },
    )
    *_, project_ranks = service.prepare_project_comparison_data(filters, items, level)
    for index, (selection, ranks) in enumerate(zip(selections, project_ranks)):
        assert ranks["album_project_id"].tolist() == [selection.project_id]
        assert ranks["rank"].tolist() == [index + 7]
        assert ranks["play_count"].tolist() == [index + 20]


@pytest.mark.parametrize("level", [2, 3])
def test_published_album_rank_without_project_id_is_unavailable(isolated, level):
    filters = comparison._filters()
    _, weekly_artist, weekly_album = comparison._publish_oracle(filters, level)
    items, params, _, _ = _selection(filters, weekly_album, level)
    rows = df_to_json(weekly_album, ["billboard_week"])
    for row in rows:
        row.pop("album_project_id", None)
    cache.store_persisted_snapshot(
        cache.build_cache_context("weekly", params),
        {
            "weekly_artist": df_to_json(weekly_artist, ["billboard_week"]),
            "weekly_album": rows,
        },
    )

    with pytest.raises(HTTPException) as unavailable:
        service.prepare_project_comparison_data(filters, items, level)
    assert unavailable.value.status_code == 503
    assert unavailable.value.detail["error"] == "snapshot_unavailable"

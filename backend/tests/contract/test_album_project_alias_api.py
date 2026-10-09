from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import run_migrations
from backend.domains.music_search.index import (
    build_music_search_documents,
    rebuild_music_search_index,
)
from backend.domains.music_search.repository import search_music_index

pytestmark = pytest.mark.contract

_FILTERS = {
    "artist": "Fixture Artist Alpha",
    "min_ms": 30000,
    "music_only": True,
    "merge_enabled": True,
    "dynamic_threshold": False,
    "merge_level": 2,
}


def test_member_alias_uses_same_project_for_all_four_detail_surfaces(
    use_seed_db: str, client
) -> None:
    canonical = "Fixture Future LP"
    alias = "ＦＩＸＴＵＲＥ FUTURE LP DELUXE"
    paths: tuple[tuple[str, dict[str, object]], ...] = (
        ("stats", {}),
        ("rankings", {"metric": "plays", "limit": 100}),
        ("plays", {"limit": 200}),
        ("play-dates", {}),
    )

    for suffix, extra in paths:
        expected = client.get(
            f"/api/music/albums/{canonical}/{suffix}", params={**_FILTERS, **extra}
        )
        actual = client.get(f"/api/music/albums/{alias}/{suffix}", params={**_FILTERS, **extra})
        assert expected.status_code == actual.status_code == 200
        expected_payload = expected.json()
        actual_payload = actual.json()
        if suffix == "stats":
            assert actual_payload["summary"] == expected_payload["summary"]
            assert actual_payload["entity"]["album_name"] == canonical
            assert actual_payload["album_project_id"] == 3
            assert actual_payload["album_project_name"] == canonical
            assert actual_payload["requested_album_name"] == alias
            assert actual_payload["album_project_identity"]["matched_by"] == ("member_album_name")
        elif suffix == "rankings":
            assert actual_payload["rows"] == expected_payload["rows"]
            assert actual_payload["album_project_name"] == canonical
        elif suffix == "plays":
            assert actual_payload["total"] == expected_payload["total"]
            assert [row["play_id"] for row in actual_payload["rows"]] == [
                row["play_id"] for row in expected_payload["rows"]
            ]
        else:
            assert actual_payload == expected_payload


def test_stable_project_routes_support_slash_member_and_billboard_detail(
    use_seed_db: str, client, prepare_music_detail_publications
) -> None:
    run_migrations()
    conn = sqlite3.connect(use_seed_db)
    try:
        conn.execute("UPDATE albums SET album_name='Fixture Future / Deluxe' WHERE album_id=922")
        conn.commit()
    finally:
        conn.close()

    for suffix in ("stats", "rankings", "plays", "play-dates"):
        response = client.get(
            f"/api/music/album-projects/3/{suffix}",
            params={**_FILTERS, "limit": 100} if suffix in {"rankings", "plays"} else _FILTERS,
        )
        assert response.status_code == 200
    stats = client.get("/api/music/album-projects/3/stats", params=_FILTERS).json()
    assert stats["found"] is True
    assert stats["album_project_id"] == 3
    assert stats["album_project_name"] == "Fixture Future LP"
    prepare_music_detail_publications()
    billboard = client.get(
        "/api/billboard/album-project/3",
        params={"artist_name": "Fixture Artist Alpha", "merge_level": 2, "view": "summary"},
    )
    assert billboard.status_code == 200
    assert billboard.json()["album_project_id"] == 3


def test_album_project_search_document_contains_member_alias_and_stable_href(
    use_seed_db: str,
) -> None:
    run_migrations()
    conn = sqlite3.connect(use_seed_db)
    conn.row_factory = sqlite3.Row
    try:
        documents = build_music_search_documents(conn)
    finally:
        conn.close()

    project = next(
        item
        for item in documents
        if item["entity_key"] == "album_project:3" and item["kind"] == "album_project"
    )
    assert "Fixture Future LP Deluxe" in project["alias_text"]
    assert project["href"] == "/music/album-projects/3"


@pytest.mark.parametrize(
    "merge_level, expected_key", [(2, "album_project:3"), (3, "album_project:4")]
)
def test_l2_l3_member_alias_search_returns_canonical_project(
    use_seed_db: str,
    merge_level: int,
    expected_key: str,
) -> None:
    run_migrations()
    conn = sqlite3.connect(use_seed_db)
    conn.row_factory = sqlite3.Row
    try:
        rebuild_music_search_index(conn)
        result = search_music_index(
            conn,
            query="Fixture Future LP Deluxe",
            kind="album",
            page=1,
            page_size=5,
            merge_level=merge_level,
        )
    finally:
        conn.close()

    assert result.albums
    assert result.albums[0].entity_key == expected_key
    assert result.albums[0].label == "Fixture Future LP"
    assert result.albums[0].href == f"/music/album-projects/{expected_key.rsplit(':', 1)[1]}"


@pytest.mark.parametrize("merge_level, project_id", [(2, 3), (3, 4)])
@pytest.mark.parametrize("view", ["full", "summary", "overview", "tracks", "project"])
def test_billboard_project_id_reuses_identity_without_name_scan(
    use_seed_db, client, monkeypatch, merge_level, project_id, view
):
    from backend.api.billboard import details
    from backend.domains.playback import album_project_identity

    run_migrations()
    service_calls = []

    def read_detail(*args, **kwargs):
        service_calls.append((args, kwargs))
        return {
            "found": True,
            "album_name": args[0],
            "artist_name": args[1],
            "chart_summary": {"weeks_on_chart": 2},
            "snapshot": {"freshness": "ready", "source_revision": "fixture-revision"},
        }

    monkeypatch.setattr(details, "get_album_detail_view", read_detail)
    params = {
        "artist_name": "Fixture Artist Alpha",
        "merge_level": merge_level,
        "view": view,
        "include_compilations": True,
        "min_ms": 45000,
        "dynamic_threshold": False,
        "bb_top_n": 25,
        "bb_album_top_n": 15,
        "bb_artist_top_n": 10,
        "bb_week_start_dow": 2,
        "bb_week_start_hour": 3,
        "year_start": 2023,
        "year_end": 2025,
        "max_merge_gap_minutes": 8,
        "merge_enabled": False,
    }
    alias = "ＦＩＸＴＵＲＥ FUTURE LP DELUXE"
    named = client.get(f"/api/billboard/album/{alias}", params=params)
    assert named.status_code == 200
    assert named.json()["requested_album_name"] == alias
    assert named.json()["album_project_identity"]["matched_by"] == "member_album_name"
    named_call = service_calls.pop()

    original_rows = album_project_identity._project_rows
    original_resolve = details.resolve_album_project_identity
    project_reads = []
    identities = []

    def target_rows(conn, *, project_id=None):
        assert project_id is not None, "stable ID must not scan all album projects"
        project_reads.append(project_id)
        return original_rows(conn, project_id=project_id)

    def target_identity(conn, **kwargs):
        assert "album_name" not in kwargs, "stable ID must not resolve its name again"
        identity = original_resolve(conn, **kwargs)
        identities.append(identity)
        return identity

    monkeypatch.setattr(album_project_identity, "_project_rows", target_rows)
    monkeypatch.setattr(details, "resolve_album_project_identity", target_identity)
    identified = client.get(f"/api/billboard/album-project/{project_id}", params=params)
    assert identified.status_code == 200
    assert project_reads == [project_id]
    assert service_calls == [named_call]
    payload = identified.json()
    assert payload["requested_album_name"] is None
    assert payload["album_project_identity"] == identities[0].payload()
    assert payload["album_project_identity"]["matched_by"] == "project_id"
    assert payload["album_project_identity"]["requested_project_id"] == project_id
    for response in (named, identified):
        assert "detail_service;dur=" in response.headers["Server-Timing"]
        assert response.headers["X-Snapshot-Freshness"] == "ready"
        assert response.headers["X-Snapshot-Target-Revision"] == "fixture-revision"
    for key in ("requested_album_name", "album_project_identity"):
        payload.pop(key)
    named_payload = named.json()
    for key in ("requested_album_name", "album_project_identity"):
        named_payload.pop(key)
    assert payload == named_payload


@pytest.mark.parametrize(
    "project_id, merge_level, message",
    [
        (999999, 2, "Album project not found"),
        (4, 2, "Album project is not available at this merge level"),
        (3, 3, "Album project is not available at this merge level"),
    ],
)
def test_billboard_project_scope_rejection_does_not_read_detail(
    use_seed_db, client, monkeypatch, project_id, merge_level, message
):
    from backend.api.billboard import details

    run_migrations()

    def unexpected_detail(*args, **kwargs):
        pytest.fail("unavailable project must be rejected before reading detail facts")

    monkeypatch.setattr(details, "get_album_detail_view", unexpected_detail)
    response = client.get(
        f"/api/billboard/album-project/{project_id}", params={"merge_level": merge_level}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == message


def test_billboard_l3_release_without_composition_retains_scope_fallback(
    use_seed_db, client, monkeypatch
):
    from backend.api.billboard import details

    run_migrations()
    conn = sqlite3.connect(use_seed_db)
    try:
        conn.execute(
            "UPDATE album_projects SET canonical_name='Other composition' WHERE project_id=4"
        )
        conn.execute("DELETE FROM album_project_albums WHERE project_id=4")
        conn.commit()
    finally:
        conn.close()
    calls = []
    original = details.resolve_album_project_identity

    def resolve(conn, **kwargs):
        calls.append(kwargs)
        return original(conn, **kwargs)

    monkeypatch.setattr(details, "resolve_album_project_identity", resolve)
    monkeypatch.setattr(details, "get_album_detail_view", lambda *args, **kwargs: {"found": True})
    response = client.get("/api/billboard/album-project/3", params={"merge_level": 3})
    assert response.status_code == 200
    assert len(calls) == 2  # One bounded ID lookup and the existing scope preference check.
    assert calls[0] == {"project_id": 3, "merge_level": 3}
    assert calls[1]["album_name"] == "Fixture Future LP"
    assert response.json()["requested_album_name"] is None
    assert response.json()["album_project_identity"]["matched_by"] == "project_id"

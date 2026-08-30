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
    use_seed_db: str, client
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

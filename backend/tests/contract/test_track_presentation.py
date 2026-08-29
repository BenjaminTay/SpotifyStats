"""Contract coverage for L2 track album attribution and artwork selection."""

from __future__ import annotations

import pytest

from backend.core.db import get_db
from backend.domains.metadata.track_presentation import resolve_track_presentations
from backend.domains.music_search.index import music_search_source_revision
from backend.domains.playback.album_projects import (
    get_album_project_revision,
    rebuild_album_projects,
)

pytestmark = pytest.mark.contract


def test_standard_album_owner_and_single_artwork_are_independent(use_seed_db):
    conn = get_db(readonly=False)
    try:
        conn.execute("UPDATE albums SET image_url='single.jpg' WHERE album_id=920")
        conn.execute("UPDATE albums SET image_url='album.jpg' WHERE album_id=921")
        conn.commit()

        result = resolve_track_presentations(conn, [920], merge_level=2)[920]
    finally:
        conn.close()

    assert result.album_project_name == "Fixture Future LP"
    assert result.display_album_id == 921
    assert result.display_album_name == "Fixture Future LP"
    assert result.membership_role == "standard"
    assert result.cover_album_id == 920
    assert result.cover_url == "/covers/albums/920.jpg"
    assert result.cover_source == "single"
    assert result.resolution_status == "resolved"


def test_deluxe_only_track_uses_deluxe_release_when_no_single_exists(use_seed_db):
    conn = get_db(readonly=False)
    try:
        conn.execute("UPDATE albums SET image_url='deluxe.jpg' WHERE album_id=922")
        conn.commit()

        result = resolve_track_presentations(conn, [922], merge_level=2)[922]
    finally:
        conn.close()

    assert result.album_project_name == "Fixture Future LP"
    assert result.display_album_id == 922
    assert result.display_album_name == "Fixture Future LP Deluxe"
    assert result.membership_role == "deluxe"
    assert result.cover_album_id == 922
    assert result.cover_source == "display_album"


def test_recording_group_members_share_one_l2_presentation(use_seed_db):
    conn = get_db(readonly=False)
    try:
        presentations = resolve_track_presentations(conn, [905, 906], merge_level=2)
    finally:
        conn.close()

    assert presentations[905] == presentations[906]
    assert presentations[905].canonical_track_id == 905
    assert presentations[905].display_album_name == "Fixture LP"


def test_compilation_exclusive_remains_a_last_resort_owner(use_seed_db):
    conn = get_db(readonly=False)
    try:
        result = resolve_track_presentations(conn, [923], merge_level=2)[923]
    finally:
        conn.close()

    assert result.album_project_name == "Fixture Compilation Plus"
    assert result.membership_role == "compilation_exclusive"
    assert result.display_album_id == 924


def test_primary_catalog_uses_one_exact_provider_not_all_cross_links(use_seed_db):
    conn = get_db(readonly=False)
    try:
        conn.executemany(
            """INSERT INTO album_spotify_links(
                   album_id, spotify_album_id, evidence, confidence, play_count, track_count
               ) VALUES (921, ?, 'test', ?, ?, ?)""",
            [
                ("spotify:album:proj921", 0.7, 10, 2),
                ("spotify:album:proj922", 1.0, 999, 3),
            ],
        )
        conn.commit()
        result = resolve_track_presentations(conn, [922], merge_level=2)[922]
    finally:
        conn.close()

    assert result.membership_role == "deluxe"
    assert result.display_album_id == 922


def test_album_project_publish_invalidates_candidate_revision(use_seed_db):
    conn = get_db(readonly=False)
    try:
        before_revision = get_album_project_revision(conn)
        before_source = music_search_source_revision(conn)
        rebuild_album_projects(conn)
        after_revision = get_album_project_revision(conn)
        after_source = music_search_source_revision(conn)
    finally:
        conn.close()

    assert after_revision == before_revision + 1
    assert after_source != before_source


def test_standalone_single_has_explicit_fallback_role(use_seed_db):
    conn = get_db(readonly=True)
    try:
        result = resolve_track_presentations(conn, [926], merge_level=2)[926]
    finally:
        conn.close()

    assert result.album_project_id is None
    assert result.display_album_id == 926
    assert result.membership_role == "single"
    assert result.cover_source == "single"
    assert result.resolution_status == "fallback"

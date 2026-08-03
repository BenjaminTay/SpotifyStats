from __future__ import annotations

import sqlite3

import pytest

from backend.core.db import get_db, load_plays_for_artists
from backend.domains.ai_agent.entity_resolver import resolve_entities
from backend.domains.billboard.details import _get_artist_spotify_meta
from backend.domains.billboard.versus import _vs_spotify_artist_meta
from backend.domains.metadata.artist_identity import (
    get_artist_identity_map,
    get_identity_state,
    list_artist_identity_groups,
    undo_artist_identity_event,
)
from backend.domains.metadata.artist_spotify_meta import resolve_artist_spotify_meta
from backend.services.music_search_service import search_music_entities

pytestmark = pytest.mark.integration


APPROVED_IDENTITIES = [
    ("SZA", 83, 7676, 1_109, "7tYKF4w9nC0nq9CsPZTHyP"),
    ("Charli xcx", 177, 7664, 21, "25uiPmTg16RbhZWAqwLBy5"),
    ("JAY-Z", 613, 7571, 17, "3nFkdlSjzX9mRTtwJOzDYB"),
    ("USHER", 589, 7690, 1, "23zg3TcAtWQy7J6upgbUnj"),
    ("Lily-Rose Depp", 344, 7667, 1, "1pBLC0qVRTB5zVMuteQ9jJ"),
    ("Lana Del Rey", 45, 7616, 1_240, "00FQb4jTyendYWaN8pK0wa"),
    ("A-Mei Chang", 21, 7683, 953, "6noxsCszBEEK04kCehugOp"),
    ("Eric Chou", 255, 7725, 303, "5fEQLwq1BWWQNR8GzhOIvi"),
    ("Kesha", 80, 7627, 242, "6LqNN22kT3074XbTVUrhzX"),
    ("Ms. Lauryn Hill", 46, 7637, 22, "2Mu5NfyYm8n5iTomuKAEHl"),
    ("Kanye West", 176, 7583, 2, "5K4W6rqBFWDnAN6FQUkS6x"),
]


def test_user_approved_identity_groups_have_audit_external_ids_search_and_counts():
    conn = get_db()
    try:
        mapping = get_artist_identity_map(conn)
        groups = {group["display_name"]: group for group in list_artist_identity_groups(conn)}
        frame = load_plays_for_artists(
            conn,
            min_ms=30_000,
            dynamic_threshold=True,
            merge_enabled=True,
        )
        for display, canonical_id, alias_id, expected_plays, spotify_id in APPROVED_IDENTITIES:
            group = groups[display]
            assert group["canonical_artist_id"] == canonical_id
            assert {member["artist_id"] for member in group["members"]} == {
                canonical_id,
                alias_id,
            }
            assert mapping[alias_id].canonical_artist_id == canonical_id
            assert len(frame[frame["artist_id"] == canonical_id]) == expected_plays
            assert not frame[frame["artist_id"] == alias_id].shape[0]
            for artist_id in (canonical_id, alias_id):
                link = conn.execute(
                    """SELECT external_id, verified FROM artist_identity_external_ids
                       WHERE artist_id=? AND provider='spotify'""",
                    (artist_id,),
                ).fetchone()
                assert tuple(link) == (spotify_id, 1)
                raw_name = conn.execute(
                    "SELECT artist_name FROM artists WHERE artist_id=?", (artist_id,)
                ).fetchone()[0]
                search = search_music_entities(conn, query=raw_name, kinds=("artist",))
                assert [
                    (item.artist_id, item.artist_name, item.play_events) for item in search.artists
                ] == [(canonical_id, display, expected_plays)]
            event = conn.execute(
                """SELECT action, reason, before_json, after_json
                   FROM artist_identity_events WHERE identity_id=?
                   ORDER BY event_id DESC LIMIT 1""",
                (group["identity_id"],),
            ).fetchone()
            assert event["action"] == "create_or_merge"
            assert event["reason"]
            assert spotify_id in event["after_json"]
    finally:
        conn.close()


def test_each_user_approved_create_event_can_be_undone_on_isolated_database_copy():
    source = get_db()
    try:
        groups = {group["display_name"]: group for group in list_artist_identity_groups(source)}
        for index, (display, *_rest) in enumerate(APPROVED_IDENTITIES):
            clone = sqlite3.connect(":memory:")
            clone.row_factory = sqlite3.Row
            source.backup(clone)
            group = groups[display]
            event = clone.execute(
                """SELECT event_id FROM artist_identity_events
                   WHERE identity_id=? ORDER BY event_id DESC LIMIT 1""",
                (group["identity_id"],),
            ).fetchone()
            revision = get_identity_state(clone)["current_revision"]
            undo_artist_identity_event(
                clone,
                event_id=event["event_id"],
                expected_revision=revision,
                idempotency_key=f"integration-undo-approved-{index}",
                reason="isolated rollback verification",
            )
            active_ids = {
                row[0]
                for row in clone.execute(
                    """SELECT identity_id FROM artist_identity_groups
                       WHERE status='active'"""
                )
            }
            assert group["identity_id"] not in active_ids
            clone.close()
    finally:
        source.close()


def test_excluded_artist_candidates_remain_independent():
    conn = get_db()
    try:
        mapping = get_artist_identity_map(conn)
        excluded_ids = [
            7587,
            7603,
            803,
            7723,
            315,
            7596,
            107,
            813,
            7735,
            941,
            573,
            7716,
            7717,
            7718,
            923,
        ]
        assert all(
            mapping[artist_id].canonical_artist_id == artist_id for artist_id in excluded_ids
        )
    finally:
        conn.close()


def test_jolin_three_member_identity_is_globally_canonical_and_searchable():
    conn = get_db()
    try:
        mapping = get_artist_identity_map(conn)
        assert mapping[532].canonical_artist_id == 532
        assert mapping[765].canonical_artist_id == 532
        assert mapping[765].display_name == "Jolin Tsai"
        assert mapping[768].canonical_artist_id == 532
        assert mapping[768].display_name == "Jolin Tsai"

        # Disable consecutive-play expansion here so play_id remains the
        # stable source-event key used to assert alias fan-out de-duplication.
        frame = load_plays_for_artists(
            conn,
            min_ms=30_000,
            dynamic_threshold=True,
            merge_enabled=False,
        )
        jolin = frame[frame["artist_id"] == 532]
        assert set(jolin["raw_artist_id"].unique()) == {532, 765, 768}
        assert len(jolin) == 307
        assert not jolin.duplicated(["play_id", "artist_id"]).any()
        assert set(frame[frame["raw_artist_id"] == 768]["artist_id"].unique()) == {532}

        effective = load_plays_for_artists(
            conn,
            min_ms=30_000,
            dynamic_threshold=True,
            merge_enabled=True,
        )
        assert len(effective[effective["artist_id"] == 532]) == 306

        resolved = resolve_entities(conn, query="JOLIN", entity_type="artist", limit=10)
        assert [(item["artist_id"], item["artist_name"]) for item in resolved["candidates"]] == [
            (532, "Jolin Tsai")
        ]
        for query in ("Jolin Tsai", "JOLIN", "JOLIN蔡依林"):
            search = search_music_entities(conn, query=query, kinds=("artist",))
            assert search.total == 1
            assert len(search.artists) == 1
            result = search.artists[0]
            assert result.artist_id == 532
            assert result.artist_name == "Jolin Tsai"
            assert result.play_events == 306
            assert result.href == "/music/artists/Jolin%20Tsai"
        state = get_identity_state(conn)
        assert state["active_aggregate_revision"] == state["current_revision"]
        agg_ids = {
            int(row[0])
            for row in conn.execute(
                "SELECT DISTINCT artist_id FROM agg_weekly_artists WHERE artist_id IN (532,765,768)"
            ).fetchall()
        }
        assert agg_ids == {532}

        membership = conn.execute(
            """SELECT evidence_type, evidence_json FROM artist_identity_members
               WHERE artist_id=768 AND active=1"""
        ).fetchone()
        assert membership["evidence_type"] == "user_confirmed"
        assert "provider" in membership["evidence_json"].lower()
        audit = conn.execute(
            """SELECT reason FROM artist_identity_events
               WHERE reason LIKE '%JOLIN蔡依林%' ORDER BY event_id DESC LIMIT 1"""
        ).fetchone()
        assert audit is not None
    finally:
        conn.close()


def test_jolin_identity_uses_user_selected_provider_metadata_despite_member_conflict():
    conn = get_db()
    try:
        for name in ("Jolin Tsai", "JOLIN", "JOLIN蔡依林"):
            resolved = resolve_artist_spotify_meta(conn, name)
            assert resolved.has_conflict is True
            assert resolved.metadata["spotify_artist_id"] == "1r9DuPTHiQ7hnRRZ99B8nL"
            assert resolved.metadata["popularity"] == 61
            assert resolved.metadata["followers"] == 1_239_003
            assert set(resolved.conflict_external_ids) == {
                "1r9DuPTHiQ7hnRRZ99B8nL",
                "12vIkyEuT8OimFl9i5yCXo",
            }
    finally:
        conn.close()

    detail_meta = _get_artist_spotify_meta("Jolin Tsai")
    alias_meta = _get_artist_spotify_meta("JOLIN")
    localized_alias_meta = _get_artist_spotify_meta("JOLIN蔡依林")
    assert detail_meta == alias_meta == localized_alias_meta
    assert detail_meta["popularity"] == 61
    assert detail_meta["followers"] == 1_239_003
    assert detail_meta["genre_source"] == "spotify"

    popularity, genres, cover, genre_source, confidence = _vs_spotify_artist_meta("JOLIN")
    assert popularity == 61
    assert "mandopop" in genres
    assert cover
    assert genre_source == "spotify"
    assert confidence == 1.0

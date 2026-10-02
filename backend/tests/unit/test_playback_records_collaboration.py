from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from backend.core.migrations import migrate_030
from backend.domains.playback.counting import assign_logical_event_id
from backend.domains.playback.logical_timeline import attach_listening_duration_frame
from backend.domains.playback.records_collaboration import build_collaboration_facts
from backend.domains.playback.records_discovery import (
    _feat_lover_album,
    _feat_lover_artist,
    _feat_lover_track,
)
from backend.domains.playback.records_output import _add_cover_urls_to_records


@pytest.fixture
def credit_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT);
        CREATE TABLE tracks (track_id INTEGER PRIMARY KEY, track_name TEXT, artist_id INTEGER);
        CREATE TABLE track_artists (track_id INTEGER, artist_id INTEGER, role TEXT);
        CREATE TABLE track_l1_identities (l1_id INTEGER PRIMARY KEY, representative_track_id INTEGER);
        CREATE TABLE artist_identity_aliases (alias_artist_id INTEGER, canonical_artist_id INTEGER);
        CREATE TABLE spotify_auto_track_credits (
            track_id INTEGER, artist_id INTEGER, spotify_track_id TEXT, spotify_artist_id TEXT,
            credited_name TEXT, credit_order INTEGER
        );
        INSERT INTO artists VALUES
            (1, 'Rihanna'), (2, 'Calvin Harris'), (3, 'Elton John'), (4, 'Britney Spears'),
            (5, 'Taylor Swift'), (6, 'Ice Spice'), (7, 'Tanya Chua'), (8, '蔡健雅'), (9, 'Guest');
        INSERT INTO tracks VALUES (101, 'We Found Love', 1), (102, 'Hold Me Closer', 3),
            (103, 'Karma', 5), (104, 'Karma (feat. Ice Spice)', 5),
            (105, 'Only Me (feat. Nobody)', 7), (106, 'Same Name', 1), (107, 'Same Name', 3);
        INSERT INTO track_artists VALUES (101, 1, 'primary'),
            (102, 3, 'primary'), (102, 4, 'primary'), (103, 5, 'primary'),
            (104, 5, 'primary'), (104, 6, 'featured'),
            (105, 7, 'primary'), (105, 8, 'featured'),
            (106, 1, 'primary'), (106, 2, 'featured'),
            (107, 3, 'primary'), (107, 4, 'featured');
        INSERT INTO spotify_auto_track_credits VALUES (101, 2, 'spotify101', 'artist2', 'Calvin Harris', 1);
        INSERT INTO artist_identity_aliases VALUES (8, 7);
    """)
    migrate_030(conn)
    yield conn
    conn.close()


def _frames(track_ids, *, canonical=None):
    titles = {
        101: "We Found Love",
        102: "Hold Me Closer",
        103: "Karma",
        104: "Karma (feat. Ice Spice)",
        105: "Only Me (feat. Nobody)",
        106: "Same Name",
        107: "Same Name",
    }
    rows = []
    for index, raw_id in enumerate(track_ids):
        # Deliberately different L1, representative and source IDs.
        rows.append(
            dict(
                play_id=index + 1,
                track_id=raw_id + 1000,
                l1_id=raw_id + 1000,
                representative_track_id=raw_id,
                source_track_id=raw_id + 2000,
                track_name=titles[raw_id],
                artist_name="raw display",
                album_name="Source Album",
                ts=f"2026-01-01T00:{index:02}:00Z",
                ts_date="2026-01-01",
                ms_played=180000,
            )
        )
    events = assign_logical_event_id(pd.DataFrame(rows))
    tracks = events.copy()
    tracks["canonical_track_id"] = canonical if canonical is not None else tracks["track_id"]
    tracks["canonical_track_name"] = "Karma" if canonical is not None else tracks["track_name"]
    albums = events.copy()
    albums["album_project_id"] = 50
    albums["album_project_name"] = "Album Project"
    return events, tracks, albums


def _boards(conn, frames, artists=None):
    facts = build_collaboration_facts(
        *frames, artists if artists is not None else pd.DataFrame(), conn
    )
    return facts, _feat_lover_track(facts), _feat_lover_album(facts), _feat_lover_artist(facts)


def test_spotify_and_two_primary_credits_enter_all_three_boards(credit_conn):
    facts, tracks, albums, artists = _boards(credit_conn, _frames([101, 102]))
    assert len(facts.events) == 2
    assert tracks.iloc[0]["secondary_value"] == 2
    assert tracks.iloc[0]["value"] == 100
    assert set(tracks.iloc[1:]["entity_id"]) == {"1101", "1102"}
    assert tracks.iloc[1]["artist_names"] == ["Rihanna", "Calvin Harris"]
    assert albums.iloc[0]["value"] == 2
    assert set(artists["name"]) == {"Rihanna", "Calvin Harris", "Elton John", "Britney Spears"}
    assert artists["value"].tolist() == [1, 1, 1, 1]


def test_three_participants_count_one_event_and_each_identity_once(credit_conn):
    credit_conn.execute("INSERT INTO track_artists VALUES (101, 9, 'primary')")
    _, tracks, albums, artists = _boards(credit_conn, _frames([101]))
    assert tracks.iloc[0]["secondary_value"] == 1
    assert albums.iloc[0]["value"] == 1
    assert len(artists) == 3
    assert artists["value"].sum() == 3


def test_aliases_do_not_turn_one_person_into_a_collaboration(credit_conn):
    facts, tracks, albums, artists = _boards(credit_conn, _frames([105]))
    assert facts.events.empty
    assert tracks.iloc[0]["rank"] == 0
    assert tracks.iloc[0]["value"] == 0
    assert len(tracks) == 1
    assert albums.empty and artists.empty


def test_manual_remove_wins_over_spotify_and_title_markers(credit_conn):
    credit_conn.execute("""INSERT INTO track_credit_overrides
        (track_id, artist_id, action, role, evidence_type, reason, revision)
        VALUES (104, 6, 'remove', 'featured', 'manual', 'remove', 1)""")
    credit_conn.execute("""INSERT INTO track_credit_overrides
        (track_id, artist_id, action, role, evidence_type, reason, revision)
        VALUES (101, 2, 'remove', 'featured', 'manual', 'remove', 2)""")
    facts, tracks, albums, artists = _boards(credit_conn, _frames([101, 104]))
    assert facts.events.empty
    assert tracks.iloc[0]["value"] == 0
    assert albums.empty and artists.empty


def test_manual_add_without_title_marker_changes_same_event_set(credit_conn):
    frames = _frames([103])
    assert _boards(credit_conn, frames)[0].events.empty
    credit_conn.execute("""INSERT INTO track_credit_overrides
        (track_id, artist_id, action, role, evidence_type, reason, revision)
        VALUES (103, 6, 'add', 'primary', 'manual', 'add', 1)""")
    facts, tracks, albums, artists = _boards(credit_conn, frames)
    assert len(facts.events) == tracks.iloc[0]["secondary_value"] == albums.iloc[0]["value"] == 1
    assert set(artists["name"]) == {"Taylor Swift", "Ice Spice"}


def test_l3_only_actual_collaboration_version_counts_and_receives_duration(credit_conn):
    frames = _frames([103] * 10 + [104] * 3, canonical=999)
    facts, tracks, albums, artists = _boards(credit_conn, frames)
    assert len(facts.events) == 3
    assert tracks.iloc[0]["value"] == 23.1
    assert tracks.iloc[1]["entity_id"] == "999"
    assert tracks.iloc[1]["value"] == albums.iloc[0]["value"] == 3
    assert tracks.iloc[1]["total_ms"] == 540000
    assert artists["value"].tolist() == [3, 3]
    assert artists["total_ms"].tolist() == [540000, 540000]


def test_same_name_is_not_an_identity_and_same_timestamp_not_an_event(credit_conn):
    events, tracks, albums = _frames([106, 107])
    for frame in (events, tracks, albums):
        frame["ts"] = "2026-01-01T00:00:00Z"
    _, ranking, _, artists = _boards(credit_conn, (events, tracks, albums))
    assert ranking.iloc[1:]["entity_id"].tolist() == ["1106", "1107"]
    assert ranking.iloc[1:]["value"].tolist() == [1, 1]
    assert len(artists) == 4


def test_two_logical_events_sharing_source_play_id_still_count_twice(credit_conn):
    events, tracks, albums = _frames([101, 101])
    for frame in (events, tracks, albums):
        frame["play_id"] = 7
        frame["_logical_event_id"] = ["merged:7:0", "merged:7:1"]
    # Repeated project membership and repeated rows cannot fan-out counts.
    albums = pd.concat([albums, albums], ignore_index=True)
    _, ranking, projects, artists = _boards(credit_conn, (events, tracks, albums))
    assert ranking.iloc[0]["secondary_value"] == ranking.iloc[1]["value"] == 2
    assert projects.iloc[0]["value"] == 2
    assert projects.iloc[0]["total_ms"] == 360000
    assert artists["value"].tolist() == [2, 2]


def test_duration_slices_sort_exactly_and_do_not_raise_play_counts(credit_conn):
    events, tracks, albums = _frames([101, 102])
    duration = pd.concat([events.iloc[[0]], events.iloc[[0]], events.iloc[[1]]], ignore_index=True)
    duration["slice_start_at"] = ["2026-01-01T00:00Z", "2026-01-01T01:00Z", "2026-01-01T02:00Z"]
    duration["slice_end_at"] = ["2026-01-01T00:01Z", "2026-01-01T01:01Z", "2026-01-01T02:01Z"]
    duration["ms_played"] = [100001, 100001, 200003]
    track_duration = duration.copy()
    track_duration["canonical_track_id"] = track_duration["track_id"]
    album_duration = duration.copy()
    album_duration["album_project_id"] = 50
    attach_listening_duration_frame(events, duration)
    attach_listening_duration_frame(tracks, track_duration)
    attach_listening_duration_frame(albums, pd.concat([album_duration, album_duration]))
    _, ranking, projects, artists = _boards(credit_conn, (events, tracks, albums))
    assert ranking.iloc[1:]["entity_id"].tolist() == ["1102", "1101"]
    assert ranking.iloc[1:]["value"].tolist() == [1, 1]
    assert ranking.iloc[1:]["total_ms"].tolist() == [200003, 200002]
    assert projects.iloc[0]["total_ms"] == 400005
    assert artists["name"].tolist()[:2] == ["Elton John", "Britney Spears"]


def test_album_projects_preserve_membership_without_adding_guest_ownership(credit_conn):
    events, tracks, albums = _frames([101])
    other = albums.copy()
    other["album_project_id"] = 60
    other["album_project_name"] = "Compilation"
    _, _, projects, _ = _boards(credit_conn, (events, tracks, pd.concat([albums, other, other])))
    assert projects["entity_id"].tolist() == ["50", "60"]
    assert projects["value"].tolist() == [1, 1]
    assert _boards(credit_conn, (events, tracks, albums))[2]["entity_id"].tolist() == ["50"]


def test_no_connection_reuses_canonical_preloaded_identity_not_names(credit_conn):
    frames = _frames([101, 102, 105])
    facts = _boards(credit_conn, frames)[0]
    preloaded = facts.artists.drop(columns=["_credit_track_id"])
    preloaded["raw_artist_id"] = preloaded["artist_id"]
    # Include a second name for the same canonical identity. It is one person.
    alias = frames[0].iloc[[2]].assign(artist_id=7, raw_artist_id=8, artist_name="蔡健雅")
    preloaded = pd.concat([preloaded, alias])
    standalone = _boards(credit_conn, frames)[1:]
    loaded = _boards(None, frames, preloaded)[1:]
    for expected, actual in zip(standalone, loaded):
        pd.testing.assert_frame_equal(expected, actual)


@pytest.mark.parametrize("missing", ["representative_track_id", "raw_artist_id"])
def test_preloaded_missing_reliable_identity_cannot_guess_from_feat_title(missing):
    frames = _frames([104])
    artists = pd.concat([frames[0], frames[0]], ignore_index=True)
    artists["artist_id"] = [5, 6]
    artists["raw_artist_id"] = [5, 6]
    artists["artist_name"] = ["Taylor Swift", "Ice Spice"]
    artists = artists.drop(columns=[missing])
    _, tracks, albums, artists = _boards(None, frames, artists)
    assert tracks.iloc[0]["value"] == 0
    assert albums.empty and artists.empty


def test_zero_events_has_no_percentage_or_division(credit_conn):
    empty = pd.DataFrame()
    facts, tracks, albums, artists = _boards(credit_conn, (empty, empty, empty))
    assert facts.total_events == 0
    assert tracks.empty and albums.empty and artists.empty


def test_collaboration_frames_are_restricted_to_shared_scoped_events(credit_conn):
    events, tracks, albums = _frames([101, 102])
    facts, ranking, projects, artists = _boards(credit_conn, (events.iloc[[1]], tracks, albums))
    assert len(facts.events) == ranking.iloc[0]["secondary_value"] == 1
    assert ranking.iloc[1]["name"] == "Hold Me Closer"
    assert projects.iloc[0]["value"] == 1
    assert set(artists["name"]) == {"Elton John", "Britney Spears"}


def test_album_title_fallback_keeps_different_owners_separate(credit_conn):
    events, tracks, albums = _frames([101, 102])
    albums["album_project_id"] = "Shared Album Title"
    albums["album_project_name"] = "Shared Album Title"
    albums["artist_name"] = ["Rihanna", "Elton John"]
    _, _, projects, _ = _boards(credit_conn, (events, tracks, albums))
    assert len(projects) == 2
    assert projects["value"].tolist() == [1, 1]
    assert projects["entity_id"].nunique() == 2


def test_alias_overlap_with_guest_gives_only_one_participation_per_person(credit_conn):
    credit_conn.execute("INSERT INTO track_artists VALUES (105, 9, 'featured')")
    _, tracks, _, artists = _boards(credit_conn, _frames([105]))
    assert tracks.iloc[0]["secondary_value"] == 1
    assert tracks.iloc[1]["artist_names"] == ["Tanya Chua", "Guest"]
    assert artists["name"].tolist() == ["Tanya Chua", "Guest"]
    assert artists["value"].tolist() == [1, 1]


def test_legacy_membership_projection_does_not_assign_row_ordinals(credit_conn):
    events, tracks, albums = _frames([101, 101])
    # A source play expanded to two logical events; legacy project frames
    # omitted the identity and duplicated membership rows after a join.
    for frame in (events, tracks, albums):
        frame["play_id"] = 7
    events["_logical_event_id"] = ["7:0", "7:1"]
    tracks = tracks.drop(columns=["_logical_event_id"]).iloc[::-1]
    albums = pd.concat([albums, albums]).drop(columns=["_logical_event_id"])
    _, ranking, projects, artists = _boards(credit_conn, (events, tracks, albums))
    assert ranking.iloc[1]["value"] == projects.iloc[0]["value"] == 2
    assert ranking.iloc[1]["total_ms"] == projects.iloc[0]["total_ms"] == 360000
    assert artists["value"].tolist() == [2, 2]


def test_explicit_track_identity_never_borrows_same_name_artwork(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE artists (artist_id INTEGER, artist_name TEXT, image_path TEXT, image_url TEXT);
        CREATE TABLE albums (album_id INTEGER, album_name TEXT, artist_id INTEGER, image_path TEXT, image_url TEXT);
        CREATE TABLE tracks (track_id INTEGER, track_name TEXT, artist_id INTEGER, album_id INTEGER);
        INSERT INTO artists VALUES (1, 'Artist', NULL, NULL);
        INSERT INTO albums VALUES (13, 'Covered Album', 1, '/tmp/cover.jpg', NULL);
        INSERT INTO tracks VALUES (221, 'Shared Name', 1, 13), (222, 'Shared Name', 1, NULL);
    """)
    monkeypatch.setattr("backend.domains.playback.records_output.get_db", lambda: conn)
    records = {
        "discovery_feat_lover_track": pd.DataFrame(
            [
                {"rank": 0, "name": "合作曲播放占比", "value": 50},
                {
                    "rank": 1,
                    "name": "Shared Name",
                    "artist_name": "Artist",
                    "entity_id": "222",
                    "entity_type": "track",
                    "value": 1,
                },
            ]
        )
    }
    _add_cover_urls_to_records(records)
    row = records["discovery_feat_lover_track"].iloc[1]
    assert row["entity_id"] == "222"
    assert pd.isna(row["cover_url"])

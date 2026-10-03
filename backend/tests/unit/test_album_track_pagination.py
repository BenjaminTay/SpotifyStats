from __future__ import annotations

import copy
import json

import pytest

from backend.domains.metadata.spotify_refresh import select_incomplete_album_ids, upsert_album_batch
from backend.providers.spotify.album_tracks import (
    AlbumTracksIncompleteError,
    complete_track_ids,
    fetch_complete_album_tracks,
)
from backend.tests.unit.test_spotify_metadata_refresh import _conn

pytestmark = pytest.mark.unit


def tracks(n):
    return [
        {
            "id": f"t{i}",
            "name": f"Track {i}",
            "disc_number": i // 60 + 1,
            "track_number": i % 60 + 1,
            "duration_ms": 120000,
        }
        for i in range(n)
    ]


class Provider:
    def __init__(self, n, mutate=None):
        self.items = tracks(n)
        self.calls = []
        self.mutate = mutate

    def get_album_tracks_page(self, sid, token, *, offset):
        self.calls.append(offset)
        page = self.page(offset)
        return self.mutate(page, offset) if self.mutate else page

    def page(self, offset=0):
        n = len(self.items)
        return {
            "items": copy.deepcopy(self.items[offset : offset + 50]),
            "offset": offset,
            "limit": 50,
            "total": n,
            "next": "https://untrusted.invalid/" if offset + 50 < n else None,
        }

    def album(self):
        return {
            "id": "album",
            "name": "Album",
            "total_tracks": len(self.items),
            "tracks": self.page(),
        }


def conn():
    c = _conn()
    from backend.core.migrations import _spotify_album_tracklist_evidence

    _spotify_album_tracklist_evidence(c)
    return c


@pytest.mark.parametrize("n", [1, 50, 51, 106, 121])
def test_complete_single_multiple_pages_and_multidisc(n):
    p = Provider(n)
    assert fetch_complete_album_tracks(p, p.album(), "token") == p.items
    assert p.calls == list(range(50, n, 50))


def test_same_id_in_multiple_positions_is_preserved():
    p = Provider(106)
    p.items[95]["id"] = p.items[0]["id"]
    c = conn()
    upsert_album_batch(c, [p.album()], provider=p, access_token="token")
    row = c.execute("SELECT total_tracks, track_list FROM spotify_album_meta").fetchone()
    assert row[0] == 106 and len(json.loads(row[1])) == 106
    assert len(set(json.loads(row[1]))) == 105
    evidence = json.loads(
        c.execute("SELECT tracks_json FROM spotify_album_tracklist_evidence").fetchone()[0]
    )
    assert evidence[95]["disc_number"] == 2 and evidence[95]["track_number"] == 36
    assert complete_track_ids(row[1], row[0]) is not None


@pytest.mark.parametrize(
    "fault", ["empty", "duplicate", "total", "offset", "id", "position", "failure", "end"]
)
def test_bad_pages_never_publish_half_result_and_preserve_complete_cache(fault):
    def mutate(page, offset):
        if fault == "empty":
            page["items"] = []
        if fault == "duplicate":
            page["items"] = tracks(50)
        if fault == "total":
            page["total"] += 1
        if fault == "offset":
            page["offset"] = 0
        if fault == "id":
            page["items"][0]["id"] = None
        if fault == "position":
            page["items"][0]["disc_number"] = 0
        if fault == "failure":
            return None
        if fault == "end":
            page["next"] = None
        return page

    c = conn()
    initial = Provider(2)
    upsert_album_batch(c, [initial.album()], provider=initial, access_token="token")
    p = Provider(121, mutate)
    with pytest.raises(AlbumTracksIncompleteError):
        fetch_complete_album_tracks(p, p.album(), "token")
    outcome = []
    upsert_album_batch(c, [p.album()], provider=p, access_token="token", outcomes=outcome)
    row = c.execute("SELECT total_tracks, track_list FROM spotify_album_meta").fetchone()
    assert tuple(row) == (2, '["t0", "t1"]')
    assert c.execute("SELECT COUNT(*) FROM spotify_track_meta").fetchone()[0] == 2
    evidence = c.execute(
        "SELECT validated_total, last_status, attempted_total FROM spotify_album_tracklist_evidence"
    ).fetchone()
    assert tuple(evidence) == (2, "incomplete", 121)
    assert outcome[0][1] == "incomplete"


def test_old_partial_legacy_cache_identification_and_idempotent_repair():
    c = conn()
    c.execute(
        "INSERT INTO spotify_album_meta(spotify_album_id,total_tracks,track_list) VALUES ('album',106,?)",
        (json.dumps([t["id"] for t in tracks(50)]),),
    )
    assert select_incomplete_album_ids(c) == ["album"]
    p = Provider(106)
    upsert_album_batch(c, [p.album()], provider=p, access_token="token")
    before = [
        tuple(r) for r in c.execute("SELECT * FROM spotify_track_meta ORDER BY spotify_track_id")
    ]
    upsert_album_batch(c, [p.album()], provider=p, access_token="token")
    assert before == [
        tuple(r) for r in c.execute("SELECT * FROM spotify_track_meta ORDER BY spotify_track_id")
    ]
    assert select_incomplete_album_ids(c) == []
    assert complete_track_ids('["a", "a"]', 2) == ("a", "a")
    assert complete_track_ids('["a", null]', 2) is None
    assert complete_track_ids('["a"]', 2) is None


def test_failed_transaction_rolls_back_list_evidence_and_track_metadata():
    c = conn()
    p = Provider(1)
    upsert_album_batch(c, [p.album()], provider=p, access_token="token")
    c.execute(
        "CREATE TRIGGER abort_track BEFORE INSERT ON spotify_track_meta WHEN NEW.spotify_track_id='t1' BEGIN SELECT RAISE(ABORT,'fixture'); END"
    )
    c.commit()
    p = Provider(106)
    with pytest.raises(Exception, match="fixture"):
        upsert_album_batch(c, [p.album()], provider=p, access_token="token")
    assert c.execute("SELECT total_tracks FROM spotify_album_meta").fetchone()[0] == 1
    assert (
        c.execute("SELECT validated_total FROM spotify_album_tracklist_evidence").fetchone()[0] == 1
    )
    assert c.execute("SELECT COUNT(*) FROM spotify_track_meta").fetchone()[0] == 1


def test_provider_uses_only_fixed_endpoint_and_offset(monkeypatch):
    from backend.providers.spotify.client import SpotifyProvider

    p = SpotifyProvider()
    urls = []
    monkeypatch.setattr(p, "api_get", lambda url, token: urls.append(url))
    p.get_album_tracks_page("abc", "secret", offset=50)
    assert urls == ["https://api.spotify.com/v1/albums/abc/tracks?limit=50&offset=50"]


def test_album_comparison_is_readonly_and_fails_closed_for_partial_cache(monkeypatch):
    from backend.core import version_merge

    c = conn()
    c.executescript("CREATE TABLE track_albums(track_id INTEGER,album_id INTEGER);")
    c.execute("INSERT INTO tracks(track_id,spotify_track_id) VALUES (1,'t0')")
    c.execute("INSERT INTO track_albums VALUES (1,1)")
    c.execute(
        "INSERT INTO spotify_track_meta(spotify_track_id,spotify_album_id) VALUES ('t0','album')"
    )
    c.execute(
        "INSERT INTO spotify_album_meta(spotify_album_id,total_tracks,track_list) VALUES ('album',106,'[\"t0\"]')"
    )
    c.commit()
    monkeypatch.setattr(version_merge, "get_db", lambda: c)
    monkeypatch.setattr(
        version_merge,
        "_fetch_album_tracks_from_api",
        lambda _: pytest.fail("GET attempted network"),
    )
    result = version_merge.get_album_track_comparison(1, 1)
    assert result == {
        "shared": [],
        "only_in_a": [],
        "only_in_b": [],
        "incomplete_album_ids": [1],
        "position_incomplete_album_ids": [],
    }


def test_records_distinct_songs_are_separate_from_release_positions():
    from backend.domains.playback.records_album_facts import _trusted_original

    project = dict(
        canonical_name="Album", album_name="Album", artist_name="Artist", release_date="2026-01-01"
    )
    candidate = dict(
        album_name="Album",
        album_artists="Artist",
        release_date="2026-01-01",
        total_tracks=3,
        track_list='["a","b","a"]',
        linked_track_count=2,
        confidence=1,
        play_count=10,
    )
    result = _trusted_original(project, {"a": 1, "b": 2}, [candidate], {1: "song-a", 2: "song-b"})
    assert result == ({"song-a", "song-b"}, 2)
    assert _trusted_original(project, {"a": 1}, [candidate], {1: "song-a"}) is None


def test_comparison_uses_play_release_and_first_duplicate_position(monkeypatch):
    from backend.core import version_merge

    c = conn()
    c.executescript("CREATE TABLE track_albums(track_id INTEGER,album_id INTEGER);")
    c.execute("INSERT INTO albums(album_id,album_name) VALUES (1,'Album')")
    p = Provider(3)
    p.items[2]["id"] = p.items[0]["id"]
    upsert_album_batch(c, [p.album()], provider=p, access_token="token")
    c.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES (1,'album','play',1)"
    )
    c.execute(
        "INSERT INTO spotify_album_meta(spotify_album_id,album_name) VALUES ('wrong','Unrelated Compilation')"
    )
    c.execute(
        "UPDATE spotify_track_meta SET spotify_album_id='wrong',disc_number=9,track_number=99"
    )
    c.commit()
    monkeypatch.setattr(version_merge, "get_db", lambda: c)
    monkeypatch.setattr(
        version_merge,
        "_fetch_album_tracks_from_api",
        lambda _: pytest.fail("GET attempted network"),
    )
    result = version_merge.get_album_track_comparison(1, 1)
    assert result["incomplete_album_ids"] == []
    assert [(r[0], r[2], r[3]) for r in result["shared"]] == [("Track 0", 1, 1), ("Track 1", 1, 2)]


def test_version_merge_explicit_fetch_shares_pagination_and_preserves_lkg(monkeypatch, tmp_path):
    import sqlite3

    from backend.core import version_merge
    from backend.providers.spotify import client

    c = conn()
    path = tmp_path / "explicit-maintenance.db"
    with sqlite3.connect(path) as target:
        c.backup(target)
    c.close()
    p = Provider(106)
    p.get_cc_token = lambda: "fixture"
    p.get_albums = lambda ids, token: {"albums": [p.album()]}
    monkeypatch.setattr(client, "SpotifyProvider", lambda: p)
    monkeypatch.setattr(version_merge, "get_db", lambda readonly=False: sqlite3.connect(path))
    result = version_merge._fetch_album_tracks_from_api(["album"])
    assert len(result["album"]) == 106
    with sqlite3.connect(path) as check:
        assert check.execute("SELECT total_tracks FROM spotify_album_meta").fetchone()[0] == 106
    p.mutate = lambda page, offset: None
    assert version_merge._fetch_album_tracks_from_api(["album"]) == {}
    with sqlite3.connect(path) as check:
        assert check.execute("SELECT total_tracks FROM spotify_album_meta").fetchone()[0] == 106
        assert (
            check.execute("SELECT last_status FROM spotify_album_tracklist_evidence").fetchone()[0]
            == "incomplete"
        )


@pytest.mark.parametrize(
    "fault",
    ["missing", "missing_table", "missing_id", "ids", "total", "invalid_position", "unordered"],
)
def test_complete_directory_with_untrusted_positions_keeps_membership_and_marks_unknown(
    monkeypatch, fault
):
    from backend.core import version_merge
    from backend.domains.metadata.album_tracklist import release_position_evidence

    c = conn()
    c.execute("INSERT INTO albums(album_id,album_name) VALUES (1,'Album')")
    p = Provider(61)  # Includes a second disc; array order is not an official disc number.
    upsert_album_batch(c, [p.album()], provider=p, access_token="token")
    c.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES (1,'album','play',1)"
    )
    c.execute(
        "INSERT INTO spotify_album_meta(spotify_album_id,album_name) VALUES ('single','Other Release')"
    )
    c.execute(
        "UPDATE spotify_track_meta SET spotify_album_id='single',disc_number=9,track_number=99"
    )
    evidence = copy.deepcopy(p.items)
    if fault == "missing":
        c.execute("DELETE FROM spotify_album_tracklist_evidence")
    elif fault == "missing_table":
        c.execute("DROP TABLE spotify_album_tracklist_evidence")
    elif fault == "missing_id":
        evidence[0]["uri"] = "spotify:track:" + evidence[0].pop("id")
    elif fault == "ids":
        evidence[0], evidence[1] = evidence[1], evidence[0]
    elif fault == "total":
        c.execute("UPDATE spotify_album_tracklist_evidence SET validated_total=60")
    elif fault == "invalid_position":
        evidence[-1]["disc_number"] = None
    elif fault == "unordered":
        evidence[-1]["disc_number"] = 1
        evidence[-1]["track_number"] = 1
    if fault not in {"missing", "missing_table", "total"}:
        c.execute(
            "UPDATE spotify_album_tracklist_evidence SET tracks_json=?", (json.dumps(evidence),)
        )
    c.commit()
    assert release_position_evidence(c, "album").status != "complete"
    c.execute("PRAGMA query_only=ON")
    monkeypatch.setattr(version_merge, "get_db", lambda: c)
    monkeypatch.setattr(
        version_merge, "_fetch_album_tracks_from_api", lambda _: pytest.fail("GET network")
    )
    result = version_merge.get_album_track_comparison(1, 1)
    assert result["incomplete_album_ids"] == []
    assert result["position_incomplete_album_ids"] == [1]
    assert len(result["shared"]) == 61
    assert [(r[2], r[3]) for r in result["shared"]] == [(None, None)] * 61


def test_bounded_position_repair_selection_failure_lkg_recovery_and_idempotence():
    from backend.domains.metadata.album_tracklist import (
        release_position_evidence,
        select_missing_position_evidence_ids,
    )
    from scripts.repair_album_tracklists import repair

    c = conn()
    p = Provider(61)
    upsert_album_batch(c, [p.album()], provider=p, access_token="token")
    c.execute("DELETE FROM spotify_album_tracklist_evidence")
    c.execute("INSERT INTO tracks(track_id,spotify_track_id) VALUES (1,'t0')")
    c.execute("INSERT INTO plays(play_id,track_id,source_album_id) VALUES (1,1,1)")
    c.execute(
        "INSERT INTO album_spotify_links(album_id,spotify_album_id,evidence,confidence) VALUES (1,'album','play',1)"
    )
    c.execute(
        "INSERT INTO spotify_album_meta(spotify_album_id,total_tracks,track_list) VALUES ('unplayed',1,'[\"t0\"]')"
    )
    c.commit()
    assert select_incomplete_album_ids(c) == []
    assert select_missing_position_evidence_ids(c, 1) == ["album"]
    before = tuple(
        c.execute(
            "SELECT total_tracks,track_list FROM spotify_album_meta WHERE spotify_album_id='album'"
        ).fetchone()
    )
    p.get_albums = lambda ids, token: {"albums": [p.album()]}
    p.mutate = lambda page, offset: None
    assert repair(c, p, "token", ["album"])[0][1] == "incomplete"
    assert release_position_evidence(c, "album").status == "missing"
    assert (
        tuple(
            c.execute(
                "SELECT total_tracks,track_list FROM spotify_album_meta WHERE spotify_album_id='album'"
            ).fetchone()
        )
        == before
    )
    p.mutate = None
    assert repair(c, p, "token", ["album"])[0][1] == "complete"
    assert select_missing_position_evidence_ids(c, 1) == []
    assert release_position_evidence(c, "album").positions[60]["disc_number"] == 2
    evidence = c.execute(
        "SELECT tracks_json,validated_total FROM spotify_album_tracklist_evidence"
    ).fetchone()
    assert repair(c, p, "token", ["album"])[0][1] == "complete"
    assert tuple(
        c.execute(
            "SELECT tracks_json,validated_total FROM spotify_album_tracklist_evidence"
        ).fetchone()
    ) == tuple(evidence)
    p.mutate = lambda page, offset: None
    assert repair(c, p, "token", ["album"])[0][1] == "incomplete"
    assert release_position_evidence(c, "album").status == "complete"  # Retained LKG remains valid.
    assert c.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 1

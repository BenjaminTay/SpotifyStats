from __future__ import annotations

import sqlite3

import pytest

from backend.services import spotify_auth

pytestmark = pytest.mark.unit


def test_spotify_sync_marks_oauth_provenance_and_bumps_revision(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE saved_tracks (
            track_uri TEXT PRIMARY KEY,
            added_date TEXT,
            added_date_source TEXT CHECK(added_date_source IN ('oauth', 'manual', 'legacy'))
        );
        INSERT INTO saved_tracks(track_uri) VALUES
            ('spotify:track:missing'),
            ('spotify:track:existing');
        UPDATE saved_tracks
        SET added_date = '2020-01-01T00:00:00Z', added_date_source = 'manual'
        WHERE track_uri = 'spotify:track:existing';
        """
    )
    monkeypatch.setattr(spotify_auth, "get_user_access_token", lambda _conn: "token")
    monkeypatch.setattr(
        spotify_auth,
        "spotify_api_get_all_pages",
        lambda _url, _token: [
            {
                "added_at": "2024-02-03T04:05:06Z",
                "track": {"uri": "spotify:track:missing"},
            },
            {
                "added_at": "2025-01-01T00:00:00Z",
                "track": {"uri": "spotify:track:existing"},
            },
        ],
    )
    invalidated: list[str] = []
    monkeypatch.setattr(spotify_auth, "invalidate", invalidated.append)

    result = spotify_auth.fetch_saved_tracks(conn)
    rows = conn.execute(
        "SELECT track_uri, added_date, added_date_source FROM saved_tracks ORDER BY track_uri"
    ).fetchall()
    revision = conn.execute(
        "SELECT collection_date_revision FROM account_archive_state WHERE state_id = 1"
    ).fetchone()[0]
    conn.close()

    assert result["new_dates"] == 1
    assert [tuple(row) for row in rows] == [
        ("spotify:track:existing", "2020-01-01T00:00:00Z", "manual"),
        ("spotify:track:missing", "2024-02-03T04:05:06Z", "oauth"),
    ]
    assert revision == 1
    assert invalidated == ["account", "account_archive"]

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from backend.core import migrations
from backend.core.db import get_db
from backend.domains.metadata.artist_genres import resolve_artist_genres
from backend.services import ai_task_service

pytestmark = pytest.mark.contract


class SyncThread:
    def __init__(
        self,
        *,
        target: Callable[..., None],
        args: tuple[Any, ...] = (),
        daemon: bool | None = None,
    ):
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        self.target(*self.args)


def _seed_artist_genre_backfill_fixture() -> None:
    migrations.run_migrations()
    conn = get_db(readonly=False)
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO artists(artist_id, artist_name) VALUES (?, ?)",
            [
                (990001, "Known Genre Artist"),
                (990002, "Backfill Missing Artist"),
            ],
        )
        conn.executemany(
            """INSERT OR IGNORE INTO tracks(
                   track_id, track_name, artist_id, spotify_track_uri, spotify_track_id
               ) VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    990001,
                    "Known Genre Song",
                    990001,
                    "spotify:track:known-genre",
                    "known-genre-track",
                ),
                (
                    990002,
                    "Backfill Missing Song",
                    990002,
                    "spotify:track:backfill-missing",
                    "backfill-missing-track",
                ),
            ],
        )
        conn.executemany(
            """INSERT OR REPLACE INTO spotify_artist_meta(
                   spotify_artist_id, artist_name, genres
               ) VALUES (?, ?, ?)""",
            [
                ("known-genre-artist", "Known Genre Artist", json.dumps(["known rock"])),
                ("backfill-missing-artist", "Backfill Missing Artist", json.dumps([])),
            ],
        )
        conn.executemany(
            """INSERT OR IGNORE INTO plays(
                   play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
                   ts_date, platform, ms_played, track_id, content_type
               ) VALUES (?, ?, 2026, 1, 1, 1, 12, ?, 'web', ?, ?, 'audio')""",
            [
                (990001, "2026-01-01T12:00:00Z", "2026-01-01", 3_600_000, 990001),
                (990002, "2026-01-02T12:00:00Z", "2026-01-02", 7_200_000, 990002),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _external_evidence(artist_name: str) -> dict[str, Any]:
    assert artist_name == "Backfill Missing Artist"
    return {
        "lastfm": [
            {
                "source": "lastfm",
                "source_key": artist_name,
                "normalized_genres": ["pop", "singer-songwriter"],
                "primary_genre": "pop",
                "confidence": 0.82,
                "evidence_url": "https://www.last.fm/music/Backfill%20Missing%20Artist",
                "evidence_summary": "Last.fm tags: pop, singer-songwriter",
            }
        ],
        "musicbrainz": [
            {
                "source": "musicbrainz",
                "source_key": "mbid-backfill-missing",
                "normalized_genres": ["pop", "folk pop"],
                "primary_genre": "pop",
                "confidence": 0.86,
                "evidence_url": "https://musicbrainz.org/artist/mbid-backfill-missing",
                "evidence_summary": "MusicBrainz genres: pop, folk pop",
            }
        ],
        "wikidata": [],
        "wikipedia_summary": "Backfill Missing Artist is described as a pop artist.",
    }


def _llm_suggestion(_system_prompt: str, user_content: str, temperature: float = 0.1) -> str:
    assert "Backfill Missing Artist" in user_content
    assert temperature == 0.1
    return json.dumps(
        {
            "genres": ["pop", "singer-songwriter"],
            "primary_genre": "pop",
            "language": "english",
            "region": "美国",
            "confidence": 0.82,
            "evidence_summary": "Last.fm and MusicBrainz both support pop.",
        }
    )


def _latest_running_task_id(task_type: str) -> str:
    conn = get_db(readonly=True)
    try:
        row = conn.execute(
            """SELECT task_id FROM ai_task_runs
               WHERE task_type = ? AND status = 'running'
               ORDER BY created_at DESC, task_id DESC
               LIMIT 1""",
            (task_type,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row["task_id"]


def test_artist_genre_backfill_task_persists_suggestions_and_tool_calls(
    client,
    monkeypatch,
):
    from backend.services import artist_genre_backfill_service

    _seed_artist_genre_backfill_fixture()
    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(
        artist_genre_backfill_service,
        "gather_genre_evidence",
        _external_evidence,
    )
    monkeypatch.setattr(artist_genre_backfill_service, "_llm_chat", _llm_suggestion)

    create_response = client.post(
        "/api/ai/tasks/metadata/artist-genres",
        json={
            "limit": 10,
            "min_hours": 0.1,
            "include_ai": True,
            "approve_high_confidence_external": True,
        },
    )

    assert create_response.status_code == 200
    body = create_response.json()
    assert body["task_type"] == "artist_genre_backfill"
    task_id = body["task_id"]

    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()
    events_payload = client.get(f"/api/ai/tasks/{task_id}/events").json()

    assert status_payload["status"] == "done"
    assert status_payload["result"]["selected_count"] == 1
    assert status_payload["result"]["suggested_count"] == 1
    assert status_payload["result"]["approved_count"] == 1
    assert status_payload["result"]["skipped_existing_count"] >= 1

    stages = [event["stage"] for event in events_payload["events"]]
    assert "selecting_artists" in stages
    assert "fetching_external_data" in stages
    assert "calling_llm" in stages
    assert "saving_suggestions" in stages
    assert stages[-1] == "done"
    assert [tool["tool_name"] for tool in events_payload["tool_calls"]] == [
        "artist_genre_external_evidence",
        "artist_genre_llm_suggestion",
    ]

    conn = get_db(readonly=True)
    try:
        rows = conn.execute(
            """SELECT source, status, normalized_genres_json
               FROM artist_genre_sources
               WHERE artist_name = ?
               ORDER BY source""",
            ("Backfill Missing Artist",),
        ).fetchall()
        known_rows = conn.execute(
            "SELECT COUNT(*) FROM artist_genre_sources WHERE artist_name = ?",
            ("Known Genre Artist",),
        ).fetchone()[0]
        queue_count = conn.execute(
            "SELECT COUNT(*) FROM artist_genre_review_queue WHERE artist_name = ?",
            ("Backfill Missing Artist",),
        ).fetchone()[0]
        resolved = resolve_artist_genres(conn, "Backfill Missing Artist")
    finally:
        conn.close()

    assert [(row["source"], row["status"]) for row in rows] == [
        ("external_consensus", "approved"),
        ("llm", "suggested"),
    ]
    assert json.loads(rows[0]["normalized_genres_json"])[0] == "pop"
    assert known_rows == 0
    assert queue_count == 1
    assert resolved.source == "external_consensus"
    assert resolved.genres[0] == "pop"


def test_artist_genre_backfill_task_does_not_append_late_tool_calls_after_cancel(
    client,
    monkeypatch,
):
    from backend.services import artist_genre_backfill_service

    _seed_artist_genre_backfill_fixture()
    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)

    def cancelling_evidence(artist_name: str) -> dict[str, Any]:
        assert artist_name == "Backfill Missing Artist"
        ai_task_service.cancel_task(_latest_running_task_id("artist_genre_backfill"))
        return _external_evidence(artist_name)

    monkeypatch.setattr(
        artist_genre_backfill_service,
        "gather_genre_evidence",
        cancelling_evidence,
    )
    monkeypatch.setattr(
        artist_genre_backfill_service,
        "_llm_chat",
        lambda *args, **kwargs: pytest.fail("cancelled task must not call LLM"),
    )

    create_response = client.post(
        "/api/ai/tasks/metadata/artist-genres",
        json={"limit": 10, "min_hours": 0.1},
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()
    events_payload = client.get(f"/api/ai/tasks/{task_id}/events").json()

    assert status_payload["status"] == "cancelled"
    assert events_payload["tool_calls"] == []
    assert "Backfill Missing Artist" not in [
        tool.get("params_summary", "") for tool in events_payload["tool_calls"]
    ]

    conn = get_db(readonly=True)
    try:
        source_count = conn.execute(
            "SELECT COUNT(*) FROM artist_genre_sources WHERE artist_name = ?",
            ("Backfill Missing Artist",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert source_count == 0


def test_artist_genre_backfill_task_does_not_save_sources_when_cancelled_during_save(
    client,
    monkeypatch,
):
    from backend.domains.ai_tasks.repository import AiTaskRepository
    from backend.services import artist_genre_backfill_service

    _seed_artist_genre_backfill_fixture()
    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(
        artist_genre_backfill_service,
        "gather_genre_evidence",
        _external_evidence,
    )
    monkeypatch.setattr(artist_genre_backfill_service, "_llm_chat", _llm_suggestion)

    original_guarded_update = AiTaskRepository.update_run_if_not_terminal_with_write
    cancelled = False

    def cancelling_guarded_update(self, *args, **kwargs):
        nonlocal cancelled
        if not cancelled and kwargs.get("stage") == "done":
            cancelled = True
            ai_task_service.cancel_task(_latest_running_task_id("artist_genre_backfill"))
        return original_guarded_update(self, *args, **kwargs)

    monkeypatch.setattr(
        AiTaskRepository,
        "update_run_if_not_terminal_with_write",
        cancelling_guarded_update,
    )

    create_response = client.post(
        "/api/ai/tasks/metadata/artist-genres",
        json={"limit": 10, "min_hours": 0.1},
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()

    assert status_payload["status"] == "cancelled"
    assert status_payload.get("result") is None

    conn = get_db(readonly=True)
    try:
        source_count = conn.execute(
            "SELECT COUNT(*) FROM artist_genre_sources WHERE artist_name = ?",
            ("Backfill Missing Artist",),
        ).fetchone()[0]
        review_count = conn.execute(
            "SELECT COUNT(*) FROM artist_genre_review_queue WHERE artist_name = ?",
            ("Backfill Missing Artist",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert source_count == 0
    assert review_count == 0


def test_artist_genre_backfill_task_rejects_invalid_limits(client, monkeypatch):
    monkeypatch.setattr(
        ai_task_service,
        "start_artist_genre_backfill_task",
        lambda request: pytest.fail("invalid genre backfill request must not start a task"),
        raising=False,
    )

    response = client.post(
        "/api/ai/tasks/metadata/artist-genres",
        json={"limit": 0, "min_hours": -1},
    )

    assert response.status_code == 422
    assert response.headers["x-request-id"]

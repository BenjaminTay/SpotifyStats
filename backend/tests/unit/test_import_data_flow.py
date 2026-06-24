from __future__ import annotations

import json
import sqlite3

import pytest

pytestmark = pytest.mark.unit


def _clear_db_caches() -> None:
    from backend.core import db as db_mod

    db_mod._load_plays_cached.cache_clear()
    db_mod._load_plays_for_artists_cached.cache_clear()
    db_mod.get_track_all_artists_map.cache_clear()
    db_mod.get_track_artist_names_map.cache_clear()


def test_import_data_handles_audio_and_video_records_without_metadata(tmp_path, monkeypatch):
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))

    audio_records = [
        {
            "ts": "2026-01-01T00:00:00Z",
            "conn_country": "CN",
            "platform": "ios",
            "ms_played": 210_000,
            "master_metadata_track_name": "Signal Song (feat. Guest Artist)",
            "master_metadata_album_artist_name": "Main Artist",
            "master_metadata_album_album_name": "Signal Album",
            "spotify_track_uri": "spotify:track:signal",
            "reason_start": "trackdone",
            "reason_end": "trackdone",
            "shuffle": True,
        },
        {
            "ts": "2026-01-01T00:05:00Z",
            "conn_country": "CN",
            "platform": "ios",
            "ms_played": 45_000,
            "master_metadata_track_name": None,
            "master_metadata_album_artist_name": None,
            "master_metadata_album_album_name": None,
            "spotify_track_uri": None,
            "skipped": True,
            "offline": True,
        },
    ]
    video_records = [
        {
            "ts": "2026-01-01T00:10:00Z",
            "conn_country": "CN",
            "platform": "web_player",
            "ms_played": 60_000,
            "master_metadata_track_name": None,
            "master_metadata_album_artist_name": None,
            "master_metadata_album_album_name": None,
            "spotify_track_uri": None,
            "incognito_mode": True,
        }
    ]
    (data_dir / "Streaming_History_Audio_2026_0.json").write_text(
        json.dumps(audio_records),
        encoding="utf-8",
    )
    (data_dir / "Streaming_History_Video_2026_0.json").write_text(
        json.dumps(video_records),
        encoding="utf-8",
    )

    try:
        result = import_mod.import_data(str(data_dir))

        assert result["total_records"] == 3
        assert result["audio_records"] == 2
        assert result["video_records"] == 1
        assert result["total_skipped"] == 1
        assert result["unique_tracks"] == 1

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT content_type, track_id, source_album_id, spotify_track_id_at_play, "
                "skipped, offline, incognito_mode FROM plays ORDER BY play_id"
            ).fetchall()
            assert [row["content_type"] for row in rows] == ["audio", "audio", "video"]
            assert rows[0]["track_id"] is not None
            assert rows[0]["source_album_id"] is not None
            assert rows[0]["spotify_track_id_at_play"] == "signal"
            assert rows[1]["track_id"] is None
            assert rows[1]["source_album_id"] is None
            assert rows[1]["spotify_track_id_at_play"] is None
            assert rows[2]["track_id"] is None
            assert rows[2]["source_album_id"] is None
            assert rows[2]["spotify_track_id_at_play"] is None
            assert rows[1]["skipped"] == 1
            assert rows[1]["offline"] == 1
            assert rows[2]["incognito_mode"] == 1

            featured = conn.execute(
                """
                SELECT a.artist_name
                FROM track_artists ta
                JOIN artists a ON a.artist_id = ta.artist_id
                WHERE ta.role = 'featured'
                """
            ).fetchall()
            assert [row["artist_name"] for row in featured] == ["Guest Artist"]

            assert conn.execute("SELECT COUNT(*) FROM agg_weekly_tracks").fetchone()[0] >= 1
        finally:
            conn.close()
    finally:
        _clear_db_caches()


def test_get_db_wal_reader_snapshot_survives_writer_commit(tmp_path, monkeypatch):
    from backend.core import db as db_mod

    db_path = tmp_path / "wal_probe.db"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))

    try:
        db_mod.init_db()
        writer = db_mod.get_db(readonly=False)
        try:
            journal_mode = writer.execute("PRAGMA journal_mode").fetchone()[0].lower()
            assert journal_mode == "wal"
            writer.execute("INSERT INTO artists(artist_name) VALUES ('First Artist')")
            writer.commit()
        finally:
            writer.close()

        reader = db_mod.get_db(readonly=True)
        try:
            reader.execute("BEGIN")
            assert reader.execute("SELECT COUNT(*) FROM artists").fetchone()[0] == 1

            writer = db_mod.get_db(readonly=False)
            try:
                writer.execute("INSERT INTO artists(artist_name) VALUES ('Second Artist')")
                writer.commit()
            finally:
                writer.close()

            assert reader.execute("SELECT COUNT(*) FROM artists").fetchone()[0] == 1
            reader.execute("COMMIT")
        finally:
            reader.close()

        fresh_reader = db_mod.get_db(readonly=True)
        try:
            assert fresh_reader.execute("SELECT COUNT(*) FROM artists").fetchone()[0] == 2
        finally:
            fresh_reader.close()
    finally:
        _clear_db_caches()

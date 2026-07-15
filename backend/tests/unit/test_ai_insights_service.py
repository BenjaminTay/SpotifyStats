"""Unit tests for AI insights service data shaping and cache behavior."""


class TestAiInsightsTopEntities:
    def test_top_entities_supports_albums(self):
        import pandas as pd

        from backend.services.ai_insights_service import _top_entities

        df = pd.DataFrame(
            [
                {
                    "play_id": 1,
                    "artist_name": "Artist A",
                    "album_name": "Album One",
                    "track_name": "Track 1",
                    "ms_played": 180000,
                },
                {
                    "play_id": 2,
                    "artist_name": "Artist A",
                    "album_name": "Album One",
                    "track_name": "Track 2",
                    "ms_played": 240000,
                },
                {
                    "play_id": 3,
                    "artist_name": "Artist B",
                    "album_name": "Album Two",
                    "track_name": "Track 3",
                    "ms_played": 120000,
                },
            ]
        )

        result = _top_entities(df, "album", 2)

        assert result == [
            {"name": "Album One - Artist A", "plays": 2, "hours": 0.1},
            {"name": "Album Two - Artist B", "plays": 1, "hours": 0.0},
        ]


class TestAiInsightsCachedReports:
    def test_weekly_digest_cache_returns_entities(self, monkeypatch):
        from backend.services import ai_insights_service as svc

        weekly_data = {
            "summary": {"total_plays": 5},
            "top_artists": [{"name": "Artist A", "plays": 3, "hours": 0.2}],
            "top_tracks": [{"name": "Song A - Artist A", "plays": 2, "hours": 0.1}],
        }

        monkeypatch.setattr(
            svc,
            "_get_cached",
            lambda conn, key, ttl_hours=0: ("cached report", "2026-06-01T00:00:00"),
        )
        monkeypatch.setattr(svc, "_gather_weekly_data", lambda *args, **kwargs: weekly_data)

        result = svc.generate_weekly_digest(
            conn=None,
            min_ms=30000,
            music_only=True,
            merge_enabled=True,
            week_start="2026-05-01",
            week_end="2026-05-07",
        )

        assert result["success"] is True
        assert result["report"] == "cached report"
        assert result["cached"] is True
        assert result["entities"] == {
            "artists": ["Artist A"],
            "tracks": ["Song A - Artist A"],
        }

    def test_cache_write_uses_write_connection_when_request_connection_is_readonly(
        self, monkeypatch, caplog
    ):
        import sqlite3

        from backend.services import ai_insights_service as svc

        class ReadonlyConn:
            def execute(self, *args, **kwargs):
                raise sqlite3.OperationalError("attempt to write a readonly database")

            def commit(self):
                raise AssertionError("commit should not run after failed execute")

        class WriteConn:
            def __init__(self):
                self.executed = []
                self.committed = False
                self.closed = False

            def execute(self, sql, params):
                self.executed.append((sql, params))

            def commit(self):
                self.committed = True

            def close(self):
                self.closed = True

        write_conn = WriteConn()

        def fake_get_db(readonly=True):
            assert readonly is False
            return write_conn

        monkeypatch.setattr(svc, "get_db", fake_get_db, raising=False)

        svc._set_cache(ReadonlyConn(), "ai:report:weekly:test", "generated report")

        assert write_conn.executed == [
            (
                "INSERT OR REPLACE INTO wikipedia_cache (cache_key, data, fetched_at) VALUES (?, ?, COALESCE(?, datetime('now')))",
                ("ai:report:weekly:test", "generated report", None),
            )
        ]
        assert write_conn.committed is True
        assert write_conn.closed is True
        assert "AI report cache write failed" not in caplog.text

    def test_cache_read_failure_falls_back_to_uncached_generation(self):
        import sqlite3

        from backend.services.ai_insights_service import _get_cached

        class BrokenConn:
            def execute(self, *args, **kwargs):
                raise sqlite3.OperationalError("no such table: wikipedia_cache")

        assert _get_cached(BrokenConn(), "ai:report:weekly:test", 12) is None


class TestAiInsightsNewArtists:
    def test_find_new_artists_uses_normalized_play_schema(self):
        import sqlite3

        import pandas as pd

        from backend.services.ai_insights_service import _find_new_artists

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT);
            CREATE TABLE tracks (track_id INTEGER PRIMARY KEY, track_name TEXT, artist_id INTEGER);
            CREATE TABLE plays (play_id INTEGER PRIMARY KEY, ts_date TEXT, ms_played INTEGER, track_id INTEGER);
            INSERT INTO artists VALUES (1, 'Artist A'), (2, 'Artist B');
            INSERT INTO tracks VALUES (10, 'Old Song', 1), (20, 'New Song', 2);
            INSERT INTO plays VALUES (1, '2026-04-01', 180000, 10);
            """
        )
        period_df = pd.DataFrame(
            [
                {"ts_date": "2026-05-07", "artist_name": "Artist A"},
                {"ts_date": "2026-05-08", "artist_name": "Artist B"},
            ]
        )

        result = _find_new_artists(conn, period_df, 30000, True, True)

        assert result == ["Artist B"]

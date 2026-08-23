from __future__ import annotations

import json
import sqlite3

import pytest

from backend.domains.imports.incremental import FingerprintRecord, dataset_digest
from backend.domains.imports.source_inspector import record_fingerprint

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


def test_import_data_skips_exact_duplicates_per_content_type(tmp_path, monkeypatch):
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))

    record = {
        "ts": "2026-01-01T00:00:00Z",
        "conn_country": "CN",
        "platform": "ios",
        "ms_played": 210_000,
        "master_metadata_track_name": "Signal Song",
        "master_metadata_album_artist_name": "Main Artist",
        "master_metadata_album_album_name": "Signal Album",
        "spotify_track_uri": "spotify:track:signal",
    }
    (data_dir / "Streaming_History_Audio_2026_0.json").write_text(
        json.dumps([record, record]), encoding="utf-8"
    )
    (data_dir / "Streaming_History_Audio_2026_1.json").write_text(
        json.dumps([record]), encoding="utf-8"
    )
    (data_dir / "Streaming_History_Video_2026_0.json").write_text(
        json.dumps([record]), encoding="utf-8"
    )

    try:
        result = import_mod.import_data(str(data_dir), build_preaggregations=False)

        assert result["total_records"] == 2
        assert result["audio_records"] == 1
        assert result["video_records"] == 1
        assert result["duplicate_records_skipped"] == 2
        conn = sqlite3.connect(db_path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 2
        finally:
            conn.close()
    finally:
        _clear_db_caches()


def _streaming_record(
    track_id: str,
    *,
    timestamp: str = "2026-01-01T00:00:00Z",
) -> dict[str, object]:
    return {
        "ts": timestamp,
        "conn_country": "CN",
        "platform": "ios",
        "ms_played": 210_000,
        "master_metadata_track_name": f"Song {track_id}",
        "master_metadata_album_artist_name": "Incremental Artist",
        "master_metadata_album_album_name": "Incremental Album",
        "spotify_track_uri": f"spotify:track:{track_id}",
    }


def _write_audio_records(data_dir, records: list[dict[str, object]]) -> None:
    (data_dir / "Streaming_History_Audio_2026_0.json").write_text(
        json.dumps(records),
        encoding="utf-8",
    )


def test_replace_import_builds_complete_fingerprint_baseline(tmp_path, monkeypatch) -> None:
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    audio = _streaming_record("audio")
    video = _streaming_record("video", timestamp="2026-01-02T00:00:00Z")
    _write_audio_records(data_dir, [audio])
    (data_dir / "Streaming_History_Video_2026_0.json").write_text(
        json.dumps([video]), encoding="utf-8"
    )

    try:
        result = import_mod.import_data(
            str(data_dir),
            build_preaggregations=False,
            generation_id="baseline-generation",
        )

        assert result["strategy"] == "replace"
        assert result["inserted_records"] == 2
        assert result["unchanged_records"] == 0
        assert result["active_records"] == 2
        assert result["generation_id"] == "baseline-generation"
        assert result["first_ts"] == "2026-01-01T00:00:00Z"
        assert result["latest_ts"] == "2026-01-02T00:00:00Z"

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT content_type, source_fingerprint,
                          source_fingerprint_version, import_generation_id
                   FROM plays ORDER BY content_type"""
            ).fetchall()
        finally:
            conn.close()
        assert [(row["content_type"], row["source_fingerprint_version"]) for row in rows] == [
            ("audio", 1),
            ("video", 1),
        ]
        assert {row["import_generation_id"] for row in rows} == {"baseline-generation"}
        expected_digest = dataset_digest(
            [
                FingerprintRecord("audio", record_fingerprint(audio)),
                FingerprintRecord("video", record_fingerprint(video)),
            ]
        )
        assert result["dataset_digest"] == expected_digest
    finally:
        _clear_db_caches()


def test_duplicate_append_is_noop_and_preserves_derived_rows(tmp_path, monkeypatch) -> None:
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    record = _streaming_record("existing")
    _write_audio_records(data_dir, [record])

    try:
        baseline = import_mod.import_data(
            str(data_dir),
            build_preaggregations=False,
            generation_id="generation-1",
        )
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """INSERT INTO agg_weekly_tracks(
                       billboard_week, track_id, play_count, total_ms
                   ) VALUES ('2025-12-26', 1, 1, 210000)"""
            )
            track_album_count = conn.execute("SELECT COUNT(*) FROM track_albums").fetchone()[0]
            conn.commit()
        finally:
            conn.close()

        with pytest.raises(RuntimeError, match="baseline changed"):
            import_mod.import_data(
                str(data_dir),
                build_preaggregations=False,
                mode="append",
                expected_previous_digest="stale-digest",
                before_final_commit=lambda _conn, _result: None,
            )

        result = import_mod.import_data(
            str(data_dir),
            build_preaggregations=False,
            mode="append",
            generation_id="generation-2",
            expected_previous_digest=baseline["dataset_digest"],
            before_final_commit=lambda _conn, _result: None,
        )

        assert result["total_records"] == 0
        assert result["inserted_records"] == 0
        assert result["unchanged_records"] == 1
        assert result["active_records"] == 1
        assert result["dataset_digest"] == baseline["dataset_digest"]
        conn = sqlite3.connect(db_path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM agg_weekly_tracks").fetchone()[0] == 1
            assert (
                conn.execute("SELECT COUNT(*) FROM track_albums").fetchone()[0] == track_album_count
            )
            assert conn.execute("SELECT import_generation_id FROM plays").fetchone()[0] == (
                "generation-1"
            )
        finally:
            conn.close()
    finally:
        _clear_db_caches()


def test_append_inserts_only_new_records_and_reuses_dimensions(tmp_path, monkeypatch) -> None:
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    existing = _streaming_record("existing")
    added = _streaming_record("added", timestamp="2026-01-03T00:00:00Z")
    _write_audio_records(data_dir, [existing])

    try:
        baseline = import_mod.import_data(
            str(data_dir),
            build_preaggregations=False,
            generation_id="generation-1",
        )
        _write_audio_records(data_dir, [existing, added])

        result = import_mod.import_data(
            str(data_dir),
            build_preaggregations=False,
            mode="append",
            generation_id="generation-2",
            expected_previous_digest=baseline["dataset_digest"],
            before_final_commit=lambda _conn, _result: None,
        )

        assert result["inserted_records"] == 1
        assert result["audio_records"] == 1
        assert result["unchanged_records"] == 1
        assert result["active_records"] == 2
        assert result["latest_ts"] == "2026-01-03T00:00:00Z"
        conn = sqlite3.connect(db_path)
        try:
            generations = conn.execute(
                "SELECT import_generation_id FROM plays ORDER BY ts"
            ).fetchall()
            assert generations == [("generation-1",), ("generation-2",)]
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM artists WHERE artist_name='Incremental Artist'"
                ).fetchone()[0]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM albums WHERE album_name='Incremental Album'"
                ).fetchone()[0]
                == 1
            )
        finally:
            conn.close()
    finally:
        _clear_db_caches()


def test_import_mode_and_append_baseline_gates_fail_before_writes(tmp_path, monkeypatch) -> None:
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    _write_audio_records(data_dir, [_streaming_record("new")])

    try:
        with pytest.raises(ValueError, match="mode must be"):
            import_mod.import_data(str(data_dir), mode="merge")  # type: ignore[arg-type]
        assert not db_path.exists()

        with pytest.raises(ValueError, match="generation_id"):
            import_mod.import_data(str(data_dir), generation_id="  ")
        assert not db_path.exists()

        with pytest.raises(ValueError, match="transactional finalizer"):
            import_mod.import_data(str(data_dir), mode="append")
        assert not db_path.exists()

        db_mod.init_db()
        db_mod.ensure_schema()
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """INSERT INTO plays(
                       ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
                       platform, ms_played, conn_country, content_type
                   ) VALUES (
                       '2025-01-01 00:00:00', 2025, 1, 1, 2, 0, '2025-01-01',
                       'other', 1000, 'CN', 'audio'
                   )"""
            )
            conn.commit()
        finally:
            conn.close()

        with pytest.raises(ValueError, match="compatible source fingerprint"):
            import_mod.import_data(
                str(data_dir),
                build_preaggregations=False,
                mode="append",
                expected_previous_digest="missing-baseline",
                before_final_commit=lambda _conn, _result: None,
            )
        conn = sqlite3.connect(db_path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 1
        finally:
            conn.close()
    finally:
        _clear_db_caches()


def test_append_and_clean_replace_are_semantically_equivalent(tmp_path, monkeypatch) -> None:
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod

    incremental_db = tmp_path / "incremental.db"
    replacement_db = tmp_path / "replacement.db"
    incremental_dir = tmp_path / "incremental-streaming"
    replacement_dir = tmp_path / "replacement-streaming"
    incremental_dir.mkdir()
    replacement_dir.mkdir()
    base = [_streaming_record("first", timestamp="2026-01-01T00:00:00Z")]
    final = [
        *base,
        _streaming_record("second", timestamp="2026-01-02T00:00:00Z"),
    ]

    try:
        monkeypatch.setattr(db_mod, "DB_PATH", str(incremental_db))
        _write_audio_records(incremental_dir, base)
        baseline_result = import_mod.import_data(
            str(incremental_dir),
            build_preaggregations=False,
            generation_id="base-generation",
        )
        _write_audio_records(incremental_dir, final)
        incremental_result = import_mod.import_data(
            str(incremental_dir),
            build_preaggregations=False,
            mode="append",
            generation_id="append-generation",
            expected_previous_digest=baseline_result["dataset_digest"],
            before_final_commit=lambda _conn, _result: None,
        )

        _clear_db_caches()
        monkeypatch.setattr(db_mod, "DB_PATH", str(replacement_db))
        _write_audio_records(replacement_dir, final)
        replacement_result = import_mod.import_data(
            str(replacement_dir),
            build_preaggregations=False,
            generation_id="replacement-generation",
        )

        def semantic_snapshot(path) -> dict[str, list[tuple]]:
            conn = sqlite3.connect(path)
            try:
                return {
                    "plays": conn.execute(
                        """SELECT p.ts, p.ms_played, p.content_type,
                                  p.source_fingerprint, p.source_fingerprint_version,
                                  t.track_name, a.album_name, ar.artist_name
                           FROM plays p
                           LEFT JOIN tracks t ON t.track_id=p.track_id
                           LEFT JOIN albums a ON a.album_id=p.source_album_id
                           LEFT JOIN artists ar ON ar.artist_id=t.artist_id
                           ORDER BY p.ts, p.source_fingerprint"""
                    ).fetchall(),
                    "tracks": conn.execute(
                        """SELECT t.track_name, a.artist_name, al.album_name,
                                  t.spotify_track_id
                           FROM tracks t
                           JOIN artists a ON a.artist_id=t.artist_id
                           LEFT JOIN albums al ON al.album_id=t.album_id
                           ORDER BY a.artist_name, t.track_name"""
                    ).fetchall(),
                    "track_albums": conn.execute(
                        """SELECT t.track_name, a.album_name
                           FROM track_albums ta
                           JOIN tracks t ON t.track_id=ta.track_id
                           JOIN albums a ON a.album_id=ta.album_id
                           ORDER BY t.track_name, a.album_name"""
                    ).fetchall(),
                    "track_artists": conn.execute(
                        """SELECT t.track_name, a.artist_name, ta.role
                           FROM track_artists ta
                           JOIN tracks t ON t.track_id=ta.track_id
                           JOIN artists a ON a.artist_id=ta.artist_id
                           ORDER BY t.track_name, a.artist_name, ta.role"""
                    ).fetchall(),
                }
            finally:
                conn.close()

        assert incremental_result["inserted_records"] == 1
        assert replacement_result["inserted_records"] == 2
        assert incremental_result["dataset_digest"] == replacement_result["dataset_digest"]
        assert semantic_snapshot(incremental_db) == semantic_snapshot(replacement_db)
    finally:
        _clear_db_caches()


def test_append_rolls_back_uncommitted_batches_when_processing_fails(tmp_path, monkeypatch) -> None:
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    baseline = _streaming_record("baseline")
    _write_audio_records(data_dir, [baseline])

    try:
        baseline_result = import_mod.import_data(
            str(data_dir),
            build_preaggregations=False,
            generation_id="baseline-generation",
        )
        first = _streaming_record("first", timestamp="2026-01-02T00:00:00Z")
        second = _streaming_record("second", timestamp="2026-01-03T00:00:00Z")
        second["master_metadata_album_artist_name"] = "Break Import"
        _write_audio_records(data_dir, [baseline, first, second])
        original_cache_artist = import_mod._cache_artist

        def fail_on_second_artist(conn, name, cache):
            if name == "Break Import":
                raise RuntimeError("synthetic append failure")
            return original_cache_artist(conn, name, cache)

        monkeypatch.setattr(import_mod, "_PLAY_BATCH_SIZE", 1)
        monkeypatch.setattr(import_mod, "_cache_artist", fail_on_second_artist)

        with pytest.raises(RuntimeError, match="synthetic append failure"):
            import_mod.import_data(
                str(data_dir),
                build_preaggregations=False,
                mode="append",
                generation_id="failed-generation",
                expected_previous_digest=baseline_result["dataset_digest"],
                before_final_commit=lambda _conn, _result: None,
            )

        conn = sqlite3.connect(db_path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 1
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM plays WHERE import_generation_id='failed-generation'"
                ).fetchone()[0]
                == 0
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM artists WHERE artist_name='Break Import'"
                ).fetchone()[0]
                == 0
            )
        finally:
            conn.close()
    finally:
        _clear_db_caches()


def test_replace_rolls_back_clears_and_first_batch_when_second_record_fails(
    tmp_path, monkeypatch
) -> None:
    from backend.core import db as db_mod
    from backend.core import import_data as import_mod

    db_path = tmp_path / "spotify_stats.db"
    data_dir = tmp_path / "streaming"
    data_dir.mkdir()
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))
    baseline = _streaming_record("baseline")
    _write_audio_records(data_dir, [baseline])

    try:
        baseline_result = import_mod.import_data(
            str(data_dir),
            build_preaggregations=False,
            generation_id="baseline-generation",
        )
        conn = sqlite3.connect(db_path)
        try:
            baseline_track_id = conn.execute("SELECT track_id FROM plays").fetchone()[0]
            conn.execute(
                """INSERT INTO agg_weekly_tracks(
                       billboard_week, track_id, play_count, total_ms
                   ) VALUES ('2025-12-26', ?, 1, 210000)""",
                (baseline_track_id,),
            )
            conn.execute(
                """UPDATE playback_import_state
                   SET active_generation_id='baseline-generation',
                       dataset_digest=?, record_count=1, last_strategy='full'
                   WHERE state_id=1""",
                (baseline_result["dataset_digest"],),
            )
            conn.commit()
            before = {
                "plays": conn.execute(
                    """SELECT ts, track_id, source_album_id, source_fingerprint,
                              import_generation_id FROM plays ORDER BY play_id"""
                ).fetchall(),
                "agg": conn.execute(
                    "SELECT * FROM agg_weekly_tracks ORDER BY billboard_week, track_id"
                ).fetchall(),
                "track_albums": conn.execute(
                    "SELECT * FROM track_albums ORDER BY track_id, album_id"
                ).fetchall(),
                "state": conn.execute(
                    """SELECT active_generation_id, dataset_digest, record_count, last_strategy
                       FROM playback_import_state WHERE state_id=1"""
                ).fetchone(),
            }
        finally:
            conn.close()

        first = _streaming_record("replacement-first", timestamp="2026-01-02T00:00:00Z")
        second = _streaming_record("replacement-second", timestamp="2026-01-03T00:00:00Z")
        second["master_metadata_album_artist_name"] = "Break Replace"
        _write_audio_records(data_dir, [first, second])
        original_cache_artist = import_mod._cache_artist

        def fail_on_second_artist(conn, name, cache):
            if name == "Break Replace":
                raise RuntimeError("synthetic replace failure")
            return original_cache_artist(conn, name, cache)

        monkeypatch.setattr(import_mod, "_PLAY_BATCH_SIZE", 1)
        monkeypatch.setattr(import_mod, "_cache_artist", fail_on_second_artist)

        with pytest.raises(RuntimeError, match="synthetic replace failure"):
            import_mod.import_data(
                str(data_dir),
                build_preaggregations=False,
                mode="replace",
                generation_id="failed-replacement",
                before_final_commit=lambda _conn, _result: None,
            )

        conn = sqlite3.connect(db_path)
        try:
            after = {
                "plays": conn.execute(
                    """SELECT ts, track_id, source_album_id, source_fingerprint,
                              import_generation_id FROM plays ORDER BY play_id"""
                ).fetchall(),
                "agg": conn.execute(
                    "SELECT * FROM agg_weekly_tracks ORDER BY billboard_week, track_id"
                ).fetchall(),
                "track_albums": conn.execute(
                    "SELECT * FROM track_albums ORDER BY track_id, album_id"
                ).fetchall(),
                "state": conn.execute(
                    """SELECT active_generation_id, dataset_digest, record_count, last_strategy
                       FROM playback_import_state WHERE state_id=1"""
                ).fetchone(),
            }
            assert after == before
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM plays WHERE import_generation_id='failed-replacement'"
                ).fetchone()[0]
                == 0
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM artists WHERE artist_name='Break Replace'"
                ).fetchone()[0]
                == 0
            )
        finally:
            conn.close()
    finally:
        _clear_db_caches()

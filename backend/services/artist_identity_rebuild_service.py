"""Shadow rebuild for identity-sensitive artist weekly aggregates."""

from __future__ import annotations

from backend.core.cache_manager import invalidate_all
from backend.core.db import _agg_param_hash, get_db
from backend.core.job_queue import Job
from backend.domains.billboard.data_loader import load_billboard_raw_for_artists
from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.settings.repository import SettingsRepository


def handle_artist_identity_rebuild(job: Job) -> None:
    conn = get_db(readonly=False)
    revision = int(job.payload.get("revision") or get_identity_revision(conn))
    try:
        conn.execute(
            """UPDATE artist_identity_state
               SET rebuild_status='running', last_error=NULL, updated_at=datetime('now')
               WHERE state_id=1 AND current_revision=?""",
            (revision,),
        )
        conn.commit()
        settings = SettingsRepository(conn).load_all()
        min_ms = int(settings.get("min_ms", 30_000))
        music_only = bool(settings.get("music_only", True))
        week_start_dow = int(settings.get("bb_week_start_dow", 4))
        week_start_hour = int(settings.get("bb_week_start_hour", 0))
        dynamic_threshold = True
        max_merge_gap_minutes = None

        invalidate_all()
        frame = load_billboard_raw_for_artists(
            min_ms,
            music_only,
            week_start_dow,
            week_start_hour,
            dynamic_threshold,
            max_merge_gap_minutes,
        )
        grouped = (
            frame.groupby(["billboard_week", "artist_id"], as_index=False).agg(
                play_count=("ms_played", "count"), total_ms=("ms_played", "sum")
            )
            if not frame.empty
            else frame
        )
        rows = (
            [
                (
                    str(row.billboard_week),
                    int(row.artist_id),
                    int(row.play_count),
                    int(row.total_ms),
                )
                for row in grouped.itertuples(index=False)
            ]
            if not grouped.empty
            else []
        )
        conn.execute(
            """CREATE TEMP TABLE IF NOT EXISTS agg_weekly_artists_shadow (
                   billboard_week TEXT NOT NULL,
                   artist_id INTEGER NOT NULL,
                   play_count INTEGER NOT NULL,
                   total_ms INTEGER NOT NULL,
                   PRIMARY KEY (billboard_week, artist_id)
               )"""
        )
        conn.execute("DELETE FROM agg_weekly_artists_shadow")
        conn.executemany(
            """INSERT INTO agg_weekly_artists_shadow(
                   billboard_week, artist_id, play_count, total_ms
               ) VALUES (?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        current_revision = get_identity_revision(conn)
        if current_revision != revision:
            conn.rollback()
            return
        conn.execute("DELETE FROM agg_weekly_artists")
        conn.execute(
            """INSERT INTO agg_weekly_artists(
                   billboard_week, artist_id, play_count, total_ms
               ) SELECT billboard_week, artist_id, play_count, total_ms
                 FROM agg_weekly_artists_shadow"""
        )
        param_hash = _agg_param_hash(
            min_ms,
            music_only,
            week_start_dow,
            week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            identity_revision=revision,
        )
        conn.execute(
            "INSERT OR REPLACE INTO agg_config(key, value) VALUES ('param_hash', ?)",
            (param_hash,),
        )
        conn.execute(
            """UPDATE artist_identity_state
               SET active_aggregate_revision=?, rebuild_status='ready', last_error=NULL,
                   updated_at=datetime('now') WHERE state_id=1""",
            (revision,),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        conn.execute(
            """UPDATE artist_identity_state
               SET rebuild_status='failed', last_error=?, updated_at=datetime('now')
               WHERE state_id=1""",
            (str(exc)[:500],),
        )
        conn.commit()
        raise
    finally:
        conn.close()
        invalidate_all()

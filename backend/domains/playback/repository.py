"""Repository for playback domain database queries.

Provides a typed access layer for common playback-related operations,
wrapping db.py functions for consistency.
"""

import sqlite3

import pandas as pd


class PlaybackRepository:
    """Data access for playback/plays domain."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def count_plays(self, where_clause: str = "", params: tuple = ()) -> int:
        sql = "SELECT COUNT(*) AS cnt FROM plays"
        if where_clause:
            sql += f" WHERE {where_clause}"
        row = self.conn.execute(sql, params).fetchone()
        return row["cnt"] if row else 0

    def get_play_years(self) -> list[int]:
        rows = self.conn.execute(
            "SELECT DISTINCT ts_year FROM plays WHERE ts_year IS NOT NULL ORDER BY ts_year"
        ).fetchall()
        return [r["ts_year"] for r in rows]

    def get_play_date_range(self) -> tuple[str | None, str | None]:
        row = self.conn.execute(
            "SELECT MIN(ts_date) AS min_date, MAX(ts_date) AS max_date FROM plays"
        ).fetchone()
        return (row["min_date"], row["max_date"]) if row else (None, None)

    def get_track_play_count(self, track_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM plays WHERE track_id = ?",
            (track_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_artist_play_count(self, artist_name: str) -> int:
        row = self.conn.execute(
            """SELECT COUNT(*) AS cnt FROM plays p
               JOIN tracks t ON p.track_id = t.track_id
               JOIN track_artists ta ON t.track_id = ta.track_id
               JOIN artists a ON ta.artist_id = a.artist_id
               WHERE a.artist_name = ?""",
            (artist_name,),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_album_play_count(self, album_name: str, artist_name: str | None = None) -> int:
        params: tuple = (album_name,)
        sql = """SELECT COUNT(*) AS cnt FROM plays p
                 JOIN tracks t ON p.track_id = t.track_id
                 JOIN track_albums ta ON t.track_id = ta.track_id
                 JOIN albums al ON ta.album_id = al.album_id
                 WHERE al.album_name = ?"""
        if artist_name:
            sql += " AND al.artist_name = ?"
            params = (album_name, artist_name)
        row = self.conn.execute(sql, params).fetchone()
        return row["cnt"] if row else 0

    def get_recent_plays(self, limit: int = 20) -> pd.DataFrame:
        return pd.read_sql_query(
            """SELECT p.ts, p.ms_played, t.track_name, a.artist_name, al.album_name
               FROM plays p
               LEFT JOIN tracks t ON p.track_id = t.track_id
               LEFT JOIN artists a ON t.artist_id = a.artist_id
               LEFT JOIN track_albums ta ON t.track_id = ta.track_id
               LEFT JOIN albums al ON ta.album_id = al.album_id
               ORDER BY p.ts DESC LIMIT ?""",
            self.conn,
            params=(limit,),
        )

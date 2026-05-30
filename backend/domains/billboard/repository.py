"""Repository for Billboard domain database queries.

Encapsulates raw SQL queries against spotify_*_meta tables, agg tables,
and other Billboard-related data stores.
"""

import sqlite3

import pandas as pd


class BillboardRepository:
    """Data access for Billboard domain entities."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── Spotify Meta ──────────────────────────────────────────────────

    def get_track_meta(self, track_id: str) -> dict | None:
        row = self.conn.execute(
            """SELECT stm.*, sam.album_type, sam.release_date, sam.total_tracks,
                      sam.image_url AS album_image_url,
                      sm.artist_name AS primary_artist
               FROM spotify_track_meta stm
               LEFT JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
               LEFT JOIN spotify_artist_meta sm ON sam.spotify_artist_id = sm.spotify_artist_id
               WHERE stm.track_id = ?""",
            (track_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_artist_meta(self, artist_name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM spotify_artist_meta WHERE artist_name = ?",
            (artist_name,),
        ).fetchone()
        return dict(row) if row else None

    def get_album_meta(self, album_name: str, artist_name: str) -> dict | None:
        row = self.conn.execute(
            """SELECT sam.* FROM spotify_album_meta sam
               JOIN spotify_artist_meta sm ON sam.spotify_artist_id = sm.spotify_artist_id
               WHERE sam.album_name = ? AND sm.artist_name = ?""",
            (album_name, artist_name),
        ).fetchone()
        return dict(row) if row else None

    def get_all_album_meta(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM spotify_album_meta", self.conn)

    # ── Agg Tables ────────────────────────────────────────────────────

    def get_agg_param_hash(self) -> str | None:
        row = self.conn.execute(
            "SELECT param_hash FROM agg_config ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row["param_hash"] if row else None

    def check_agg_valid(self, param_hash: str) -> bool:
        row = self.conn.execute(
            "SELECT param_hash FROM agg_config WHERE param_hash = ?", (param_hash,)
        ).fetchone()
        return row is not None

    def load_agg_weekly_tracks(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM agg_weekly_tracks", self.conn)

    def load_agg_weekly_albums(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM agg_weekly_albums", self.conn)

    def load_agg_weekly_artists(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM agg_weekly_artists", self.conn)

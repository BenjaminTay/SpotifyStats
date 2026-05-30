"""Repository for enrichment domain database queries.

Encapsulates lyrics, Wikipedia cache, and LLM translation cache table operations.
"""

import sqlite3
from datetime import UTC, datetime


class EnrichmentRepository:
    """Data access for enrichment entities (lyrics, wiki, translations)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── Lyrics (track_lyrics) ─────────────────────────────────────────

    def get_cached_lyrics(self, track_id: int) -> dict | None:
        row = self.conn.execute(
            """SELECT lyrics_text, genius_url, genius_song_id
               FROM track_lyrics WHERE track_id = ?""",
            (track_id,),
        ).fetchone()
        if row and row["lyrics_text"]:
            return {
                "lyrics": row["lyrics_text"],
                "genius_url": row["genius_url"],
                "genius_song_id": row["genius_song_id"],
            }
        return None

    def get_genius_url(self, track_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT genius_url FROM track_lyrics WHERE track_id = ?",
            (track_id,),
        ).fetchone()
        return row["genius_url"] if row else None

    def upsert_lyrics(
        self, track_id: int, genius_song_id: int, lyrics_text: str, genius_url: str
    ) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO track_lyrics
               (track_id, genius_song_id, lyrics_text, genius_url, fetched_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (track_id, genius_song_id, lyrics_text, genius_url),
        )
        self.conn.commit()

    # ── Wikipedia Cache ───────────────────────────────────────────────

    def get_wikipedia_cache(self, cache_key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT content, fetched_at FROM wikipedia_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if row:
            return {"content": row["content"], "fetched_at": row["fetched_at"]}
        return None

    def set_wikipedia_cache(self, cache_key: str, content: str) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO wikipedia_cache (cache_key, content, fetched_at)
               VALUES (?, ?, ?)""",
            (cache_key, content, datetime.now(UTC).isoformat()),
        )
        self.conn.commit()

    # ── LLM Translation Cache ─────────────────────────────────────────

    def clear_translation_cache(self) -> int:
        """Delete all cached LLM translations. Returns count of deleted rows."""
        cur = self.conn.execute("DELETE FROM wikipedia_cache WHERE cache_key LIKE 'llm:%'")
        self.conn.commit()
        return cur.rowcount

    def get_translation_cache_count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM wikipedia_cache WHERE cache_key LIKE 'llm:%'"
        ).fetchone()
        return row["cnt"] if row else 0

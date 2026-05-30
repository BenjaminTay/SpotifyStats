"""Settings repository — encapsulates SQLite CRUD for the settings table.

This is the first domain repository, establishing the pattern for
playback, billboard, and enrichment repositories to follow.
"""

from __future__ import annotations

import sqlite3

SETTINGS_DEFAULTS = {
    "min_ms": 30000,
    "music_only": True,
    "merge_enabled": True,
    "bb_top_n": 30,
    "bb_album_top_n": 20,
    "bb_artist_top_n": 20,
    "bb_week_start_dow": 4,
    "bb_week_start_hour": 0,
    "llm_enabled": False,
    "llm_provider": "deepseek",
    "llm_model": "",
    "llm_api_key": "",
    "llm_base_url": "",
}

# Keys that need type coercion when loaded from DB (stored as strings)
_SQLITE_TYPE_COERCION = [
    "min_ms",
    "music_only",
    "merge_enabled",
    "bb_top_n",
    "bb_album_top_n",
    "bb_artist_top_n",
    "bb_week_start_dow",
    "bb_week_start_hour",
    "llm_enabled",
]


def _coerce_value(key: str, raw: str, defaults: dict) -> bool | int | str:
    """Coerce a string value from SQLite to the expected Python type."""
    default = defaults.get(key)
    if default is None:
        return raw
    if isinstance(default, bool):
        return raw.lower() in ("true", "1", "yes")
    if isinstance(default, int):
        try:
            return int(raw)
        except (ValueError, TypeError):
            return default
    return raw


class SettingsRepository:
    """CRUD operations for the settings key-value table."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._defaults = SETTINGS_DEFAULTS

    def load_all(self) -> dict:
        """Load all settings from the DB. Falls back to defaults."""
        try:
            rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        except Exception:
            return dict(self._defaults)
        if not rows:
            return dict(self._defaults)
        loaded = dict(self._defaults)
        for row in rows:
            key = row["key"]
            if key in loaded:
                val = row["value"]
                if key in _SQLITE_TYPE_COERCION:
                    val = _coerce_value(key, val, loaded)
                loaded[key] = val
        return loaded

    def update(self, key: str, value) -> None:
        """Upsert a single setting key/value."""
        self.conn.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
            (key, str(value)),
        )
        self.conn.commit()

    def delete(self, key: str) -> None:
        """Remove a setting, reverting it to its default."""
        self.conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        self.conn.commit()

"""Playback records computation facade."""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_behavior import compute_behavior_records
from backend.domains.playback.records_discovery import compute_discovery_records
from backend.domains.playback.records_longevity import compute_longevity_records
from backend.domains.playback.records_obsession import compute_obsession_records
from backend.domains.playback.records_output import _add_cover_urls_to_records, _serialize_records
from backend.domains.playback.records_reigns import compute_reign_records
from backend.domains.playback.records_time import compute_time_pattern_records

__all__ = [
    "_add_cover_urls_to_records",
    "_serialize_records",
    "compute_playback_records",
]


def compute_playback_records(
    event_frame: pd.DataFrame,
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
    merge_level: int = 2,
    conn=None,
):
    """Compute all playback records from entity frames.

    Args:
        event_frame: Raw valid play events with columns:
            ts, ts_date, ts_hour, ts_dow, ts_year, ts_month,
            track_id, track_name, artist_name, album_name, ms_played,
            platform, reason_start, reason_end, shuffle, skipped, offline
        track_frame: event_frame with canonical_track_id added
        album_frame: event_frame with album_project_id/name added
        artist_frame: fan-out frame (one row per contributing artist)
        merge_level: 1-3 merge level for entity attribution
        conn: sqlite3 connection for metadata lookups

    Returns a dict of record DataFrames keyed by record family.
    """
    records: dict = {}

    compute_obsession_records(records, event_frame, track_frame, album_frame, artist_frame)
    compute_time_pattern_records(records, event_frame, track_frame, album_frame, artist_frame)
    compute_reign_records(records, event_frame, track_frame, album_frame, artist_frame)
    compute_longevity_records(records, event_frame, track_frame, album_frame, artist_frame)
    compute_discovery_records(
        records, event_frame, track_frame, album_frame, artist_frame, conn=conn
    )
    compute_behavior_records(records, event_frame, track_frame, album_frame, artist_frame)

    return records

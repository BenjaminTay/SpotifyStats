"""Album type taxonomy — classify LP/EP/compilation/single.

Spotify album_type is not always reliable (some EPs are tagged 'album',
some are tagged 'single'). This module uses track count and duration as
secondary signals per R12.
"""

from __future__ import annotations


def classify_album(
    spotify_album_type: str | None,
    total_tracks: int | None = None,
    total_ms: int | None = None,
) -> str:
    """Classify an album into one of: 'lp', 'ep', 'compilation', 'single'.

    Returns 'unknown' if no classification is possible.
    """
    album_type = (spotify_album_type or "").lower()
    tracks = int(total_tracks or 0)
    duration = int(total_ms or 0)

    if album_type == "compilation":
        return "compilation"

    # Singles: at most 2 tracks
    if tracks <= 2 and duration > 0:
        return "single"

    # EPs: 3-6 tracks and total duration < 25 minutes
    if tracks <= 6 and 0 < duration < 25 * 60 * 1000:
        return "ep"

    # LP: album type with 7+ tracks or 25+ min
    if album_type == "album" and (tracks >= 7 or duration >= 25 * 60 * 1000):
        return "lp"

    # Spotify 'single' with 3-6 tracks → EP
    if album_type == "single" and tracks >= 3:
        return "ep"

    # LP by duration alone (few tracks but long)
    if duration >= 25 * 60 * 1000:
        return "lp"

    if tracks >= 7:
        return "lp"

    return "unknown"


def is_album_chart_eligible(category: str) -> bool:
    """Whether this album category should appear in default album charts.

    Singles are excluded (per R13); LP, EP, and compilations are included.
    """
    return category not in ("single", "unknown")

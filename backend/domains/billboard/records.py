"""Billboard records computation."""

from backend.domains.billboard.records_championship import (
    compute_championship_records,
)
from backend.domains.billboard.records_endurance import (
    compute_endurance_records,
)
from backend.domains.billboard.records_hall_of_fame import (
    compute_hall_of_fame_records,
)
from backend.domains.billboard.records_longevity import (
    compute_longevity_records,
)
from backend.domains.billboard.records_market import (
    compute_market_records,
)
from backend.domains.billboard.records_movement import (
    compute_movement_records,
)
from backend.domains.billboard.records_output import (
    _add_cover_urls,
    _enrich_records_artist_names,
    _serialize_records,
)
from backend.domains.billboard.records_quirky import (
    compute_quirky_records,
)
from backend.domains.billboard.records_self_replacement_blocker import (
    compute_self_replacement_blocker_records,
)

__all__ = [
    "_add_cover_urls",
    "_serialize_records",
    "compute_records",
]


def compute_records(
    weekly,
    track_summary,
    top_n,
    weekly_album=None,
    weekly_artist=None,
    track_power_scores=None,
    album_power_scores=None,
    artist_power_scores=None,
):
    """Compute all-time Billboard records from weekly rankings.

    Returns a dict of record DataFrames and highlight values for the 榜单记录 tab.
    """
    records = {}

    compute_championship_records(records, weekly, track_summary, weekly_album, weekly_artist)
    compute_longevity_records(records, weekly, track_summary, weekly_album, weekly_artist)
    compute_endurance_records(records, weekly, track_summary, weekly_album, weekly_artist)
    compute_movement_records(records, weekly, track_summary, weekly_album)
    compute_hall_of_fame_records(
        records,
        weekly,
        track_summary,
        top_n,
        track_power_scores,
        album_power_scores,
        artist_power_scores,
    )
    compute_quirky_records(records, weekly, weekly_album, weekly_artist)
    compute_market_records(records, weekly, weekly_album, weekly_artist)
    compute_self_replacement_blocker_records(
        records,
        weekly,
        track_summary,
        weekly_album,
        weekly_artist,
        track_power_scores,
        album_power_scores,
        artist_power_scores,
    )

    # Enrich DataFrames with artist_names for frontend multi-artist linking
    _enrich_records_artist_names(records)

    return records


# ═══════════════════════════════════════════════════════════════════════════
# Track History Detail
# ═══════════════════════════════════════════════════════════════════════════

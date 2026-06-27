"""Billboard computation service — facade re-exporting from domain modules.

This module is kept as a thin facade for backward compatibility.
All implementation has been moved to backend/domains/billboard/.
"""

from backend.domains.billboard.chart_compute import (
    _compute_billboard_data_cached,
    compute_album_power_scores,
    compute_album_weekly_rankings,
    compute_artist_power_scores,
    compute_artist_weekly_rankings,
    compute_billboard_data,
    compute_power_scores,
    compute_power_scores_staged,
    compute_records_staged,
    compute_summaries_staged,
    compute_weekly_data,
    compute_weekly_rankings,
)
from backend.domains.billboard.chart_year_end_api import compute_year_end_staged
from backend.domains.billboard.data_loader import (
    DOW_NAMES,
    DOW_SHORT,
    _add_canonical_metadata,
    _get_album_canonical_map,
    _load_album_metadata,
    _try_load_from_agg,
    load_billboard_raw,
    load_billboard_raw_for_artists,  # noqa: F401 — re-exported for API layer
    load_track_album_map,
)
from backend.domains.billboard.details import (
    _build_gapped_chart_data,
    _compute_change_column,
    _get_album_spotify_meta,
    _get_artist_spotify_meta,
    _get_track_spotify_meta,
    get_album_chart_detail,
    get_artist_chart_detail,
    get_track_history,
)
from backend.domains.billboard.entity_lists import (
    get_billboard_entity_lists,
)
from backend.domains.billboard.records import (
    _add_cover_urls,
    _serialize_records,
    compute_records,
)
from backend.domains.billboard.version_merge import (
    _apply_album_release_groups,
    _normalize_album_column,
    _resolve_album_members,
)
from backend.domains.billboard.versus import (
    _get_ps_rank,
    _resolve_album_members_vs,
    get_versus_album,
    get_versus_album_multi,
    get_versus_artist,
    get_versus_artist_multi,
    get_versus_track,
    get_versus_track_multi,
)

__all__ = [
    # data_loader
    "DOW_NAMES",
    "DOW_SHORT",
    "_add_canonical_metadata",
    "_get_album_canonical_map",
    "_load_album_metadata",
    "_try_load_from_agg",
    "load_billboard_raw",
    "load_track_album_map",
    # version_merge
    "_apply_album_release_groups",
    "_normalize_album_column",
    "_resolve_album_members",
    # chart_compute
    "_compute_billboard_data_cached",
    "compute_album_power_scores",
    "compute_album_weekly_rankings",
    "compute_artist_power_scores",
    "compute_artist_weekly_rankings",
    "compute_billboard_data",
    "compute_power_scores",
    "compute_power_scores_staged",
    "compute_records_staged",
    "compute_summaries_staged",
    "compute_weekly_data",
    "compute_weekly_rankings",
    "compute_year_end_staged",
    # records
    "_add_cover_urls",
    "_serialize_records",
    "compute_records",
    # details
    "_build_gapped_chart_data",
    "_compute_change_column",
    "_get_album_spotify_meta",
    "_get_artist_spotify_meta",
    "_get_track_spotify_meta",
    "get_album_chart_detail",
    "get_artist_chart_detail",
    "get_track_history",
    # versus
    "_get_ps_rank",
    "_resolve_album_members_vs",
    "get_versus_album",
    "get_versus_album_multi",
    "get_versus_artist",
    "get_versus_artist_multi",
    "get_versus_track",
    "get_versus_track_multi",
    # entity_lists
    "get_billboard_entity_lists",
]

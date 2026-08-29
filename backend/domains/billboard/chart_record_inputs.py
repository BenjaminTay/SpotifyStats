"""Shared preparation of track inputs consumed by Billboard record builders."""

from __future__ import annotations

import pandas as pd

from backend.core.db import enrich_track_artist_names
from backend.domains.billboard.chart_power_score import compute_power_scores


def prepare_track_record_inputs(
    weekly: pd.DataFrame,
    track_summary: pd.DataFrame,
    bb_top_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Enrich display attribution before computing record-facing Power Scores."""
    enriched_weekly = enrich_track_artist_names(weekly)
    enriched_summary = enrich_track_artist_names(track_summary)
    power_scores = compute_power_scores(enriched_weekly, bb_top_n)
    return enriched_weekly, enriched_summary, power_scores

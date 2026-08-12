from __future__ import annotations

from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services.yearly_review_service import build_yearly_review_cache_key


def _context() -> YearlyReviewFilterContext:
    return YearlyReviewFilterContext(
        min_ms=30_000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=None,
        merge_level=2,
        include_compilations=False,
        bb_top_n=30,
        bb_album_top_n=20,
        bb_artist_top_n=20,
        bb_week_start_dow=4,
        bb_week_start_hour=0,
        display_taxonomy_version="consumer_v1",
        artist_metadata_revision="artist-rev",
        artist_identity_revision=1,
        track_credit_revision=2,
        track_group_revision="track-rev",
        album_project_revision="album-rev",
        filter_fingerprint="fingerprint",
    )


def test_cache_key_changes_with_language_database_and_filter_revisions() -> None:
    context = _context()
    base = build_yearly_review_cache_key(
        2025, context, language_revision="lang-a", db_revision="db-a"
    )

    assert base != build_yearly_review_cache_key(
        2025, context, language_revision="lang-b", db_revision="db-a"
    )
    assert base != build_yearly_review_cache_key(
        2025, context, language_revision="lang-a", db_revision="db-b"
    )
    changed = context.model_copy(update={"filter_fingerprint": "other"})
    assert base != build_yearly_review_cache_key(
        2025, changed, language_revision="lang-a", db_revision="db-a"
    )

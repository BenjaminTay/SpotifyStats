"""Contract tests — Billboard album source_album attribution, single filtering,
and dynamic threshold propagation."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.domains.billboard.chart_ranking import compute_album_weekly_rankings
from backend.domains.billboard.data_loader import load_billboard_raw

pytestmark = pytest.mark.contract


class TestBillboardSourceAlbum:
    def test_load_billboard_raw_uses_source_album_name(self, seed_conn):
        """After fix: album_name in Billboard raw data reflects source_album_id,
        not tracks.album_id. Track 904 is played from Fixture Single (901) and
        Fixture LP (902) — the raw data should show those source albums."""
        raw = load_billboard_raw(30_000, True, 4, 0)
        rows = raw[raw["track_name"] == "Fixture Source Album Song"]
        assert len(rows) > 0, "Track should appear in Billboard raw data"
        album_names = set(rows["album_name"])
        assert "Fixture Single" in album_names
        assert "Fixture LP" in album_names

    def test_track_chart_merges_same_track_across_source_albums(self, seed_conn):
        """Single chart rankings are keyed by track entity, not source album."""
        from backend.domains.billboard.chart_ranking import compute_weekly_rankings

        raw = load_billboard_raw(30_000, True, 4, 0)
        weekly = compute_weekly_rankings(raw, top_n=100, merge_level=1)
        rows = weekly[weekly["track_id"] == 904]

        assert len(rows) == 1
        assert int(rows.iloc[0]["play_count"]) == 2
        assert rows.iloc[0]["album_name"] == "Fixture LP"

    def test_track_summary_uses_full_history_across_source_albums(self, seed_conn):
        """Track summaries must match the full track history, not one album slice."""
        from backend.domains.billboard.chart_ranking import compute_weekly_rankings
        from backend.domains.billboard.chart_summaries import compute_track_summary

        raw = load_billboard_raw(30_000, True, 4, 0)
        weekly = compute_weekly_rankings(raw, top_n=100, merge_level=1)
        summary = compute_track_summary(weekly, raw)
        rows = summary[summary["track_id"] == 904]

        assert len(rows) == 1
        assert int(rows.iloc[0]["total_chart_plays"]) == 2
        assert int(rows.iloc[0]["total_plays"]) == 2
        assert int(rows.iloc[0]["peak_position"]) == int(
            weekly[weekly["track_id"] == 904]["rank"].min()
        )

    def test_track_detail_summary_peak_matches_history_peak(self, client):
        """Detail KPI peak must not ignore pre-album/source-single chart weeks."""
        response = client.get(
            "/api/billboard/track/904",
            params={"bb_top_n": 100, "merge_level": 1},
        )

        assert response.status_code == 200, response.text
        data = response.json()
        history_peak = min(row["rank"] for row in data["history"])
        assert data["summary"]["peak_position"] == history_peak


class TestBillboardSingleFiltering:
    def test_billboard_album_chart_excludes_singles(self, seed_conn):
        """Singles (album_type='single') must not appear in the Billboard album chart.
        Fixture Single has album_type='single' in spotify_album_meta."""
        raw = load_billboard_raw(30_000, True, 4, 0)
        album_weekly = compute_album_weekly_rankings(raw, top_n=100, merge_level=1)
        album_names = set(album_weekly["album_name"])
        assert "Fixture Single" not in album_names, (
            "Singles must be excluded from Billboard album chart"
        )


class TestBillboardDynamicThreshold:
    def test_dynamic_threshold_filters_long_track_in_billboard(self, seed_conn):
        """When dynamic_threshold=True, a 30s play of a 10min track (Fixture Long Track,
        duration_ms=600000) should be filtered out because 30s < 10%*600s=60s."""
        raw_static = load_billboard_raw(30_000, True, 4, 0, dynamic_threshold=False)
        raw_dynamic = load_billboard_raw(30_000, True, 4, 0, dynamic_threshold=True)

        long_static = raw_static[raw_static["track_name"] == "Fixture Long Track"]
        long_dynamic = raw_dynamic[raw_dynamic["track_name"] == "Fixture Long Track"]

        assert len(long_static) > 0, "Fixture Long Track should appear with static threshold"
        assert len(long_dynamic) == 0, (
            "30s of a 10min track should be filtered by dynamic threshold (30 < 60)"
        )


class TestAlbumMetadataDirectLookup:
    def test_fixture_lp_album_type_is_album_not_single(self, seed_conn):
        """After fix: _load_album_metadata() matches directly by album_name +
        artist_name, so Fixture LP gets album_type='album' from its own
        spotify_album_meta row, not 'single' from a co-appearing track's album."""
        from backend.domains.billboard.data_loader import _load_album_metadata

        meta = _load_album_metadata()
        type_df = meta["type"]
        lp_row = type_df[
            (type_df["album_name"] == "Fixture LP")
            & (type_df["artist_name"] == "Fixture Artist Alpha")
        ]
        assert len(lp_row) == 1, "Fixture LP should have metadata"
        assert lp_row.iloc[0]["album_type"] == "album", (
            f"Fixture LP should be 'album', got {lp_row.iloc[0]['album_type']}"
        )

    def test_fixture_lp_appears_in_album_chart(self, seed_conn):
        """Fixture LP (album_type='album') must appear in Billboard album chart.
        Before the fix, it was misclassified as 'single' because _load_album_metadata
        went through a track whose spotify_album_id pointed to Fixture Single."""
        raw = load_billboard_raw(30_000, True, 4, 0)
        album_weekly = compute_album_weekly_rankings(raw, top_n=100, merge_level=1)
        album_names = set(album_weekly["album_name"])
        assert "Fixture LP" in album_names, "Fixture LP must appear in Billboard album chart"

    def test_album_taxonomy_classifies_correctly(self, seed_conn):
        """R13: The album taxonomy (classify_album) should classify
        Fixture Single as 'single' and Fixture LP as 'lp'."""
        from backend.domains.playback.album_type import classify_album, is_album_chart_eligible

        # Fixture Single: 1 track, spotify album_type='single'
        cat_single = classify_album("single", total_tracks=1)
        assert cat_single == "single", f"Expected 'single', got '{cat_single}'"
        assert not is_album_chart_eligible(cat_single)

        # Fixture LP: 10 tracks, spotify album_type='album'
        cat_lp = classify_album("album", total_tracks=10)
        assert cat_lp == "lp", f"Expected 'lp', got '{cat_lp}'"
        assert is_album_chart_eligible(cat_lp)

        # Spotify single with 4 tracks → should upgrade to EP
        cat_upgraded = classify_album("single", total_tracks=4)
        assert cat_upgraded == "ep", f"Expected 'ep' for multi-track single, got '{cat_upgraded}'"
        assert is_album_chart_eligible(cat_upgraded)


class TestAlbumChartUsesTaxonomy:
    def test_album_chart_filtering_uses_taxonomy_not_raw_type_string(self, seed_conn):
        """Verify that the album chart filtering path goes through the taxonomy.
        If the old raw-string filter were still in place, Fixture Single (with
        raw album_type='single') would be excluded — which is correct in this
        case, but multi-track 'single' releases would be wrongly excluded too.

        With the taxonomy: confirmed singles excluded, multi-track singles
        (classified as EP) included."""
        from backend.domains.billboard.data_loader import _load_album_metadata
        from backend.domains.playback.album_type import classify_album

        meta = _load_album_metadata()
        type_df = meta["type"]

        # All albums with metadata should get a taxonomy category
        for _, row in type_df.iterrows():
            cat = classify_album(
                row["album_type"] if pd.notna(row["album_type"]) else None,
                total_tracks=int(row["total_tracks"])
                if pd.notna(row.get("total_tracks"))
                else None,
            )
            assert cat != "unknown", (
                f"Album '{row['album_name']}' got 'unknown' — missing fallback in taxonomy"
            )


class TestArtistChartDynamicThreshold:
    def test_artist_chart_receives_dynamic_threshold(self, seed_conn):
        """When dynamic_threshold=True filters out a long track, the total valid
        play events decrease relative to static threshold."""
        from backend.services.analysis_stats_service import get_analysis_charts

        result_static = get_analysis_charts(
            seed_conn,
            min_ms=30_000,
            music_only=True,
            merge_enabled=True,
            period="lifetime",
            start_date=None,
            end_date=None,
            entity="track",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=1,
            dynamic_threshold=False,
        )
        result_dynamic = get_analysis_charts(
            seed_conn,
            min_ms=30_000,
            music_only=True,
            merge_enabled=True,
            period="lifetime",
            start_date=None,
            end_date=None,
            entity="track",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=1,
            dynamic_threshold=True,
        )

        total_static = sum(row["plays"] for row in result_static["rows"])
        total_dynamic = sum(row["plays"] for row in result_dynamic["rows"])

        assert total_static > total_dynamic, (
            f"Dynamic threshold should reduce total plays: {total_static} > {total_dynamic}"
        )

    def test_artist_chart_with_dynamic_threshold_reflects_reduced_plays(self, seed_conn):
        """Artist chart with dynamic_threshold should reflect the same counting
        as track chart — total plays decrease relative to static threshold."""
        from backend.services.analysis_stats_service import get_analysis_charts

        result_artist_static = get_analysis_charts(
            seed_conn,
            min_ms=30_000,
            music_only=True,
            merge_enabled=True,
            period="lifetime",
            start_date=None,
            end_date=None,
            entity="artist",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=1,
            dynamic_threshold=False,
        )
        result_artist_dynamic = get_analysis_charts(
            seed_conn,
            min_ms=30_000,
            music_only=True,
            merge_enabled=True,
            period="lifetime",
            start_date=None,
            end_date=None,
            entity="artist",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=1,
            dynamic_threshold=True,
        )

        total_static = sum(row["plays"] for row in result_artist_static["rows"])
        total_dynamic = sum(row["plays"] for row in result_artist_dynamic["rows"])

        assert total_static > total_dynamic, (
            f"Artist chart dynamic threshold should reduce plays: {total_static} > {total_dynamic}"
        )


class TestMultiArtistAlbumMetadata:
    def test_collab_single_has_metadata_with_comma_separated_artists(self, seed_conn):
        """Fixture Collab Single has album_artists='Fixture Artist Alpha, Fixture Artist Beta'.
        _match_album_artist must parse this and match Fixture Artist Alpha."""
        from backend.domains.billboard.data_loader import _load_album_metadata, _match_album_artist

        # Unit check: comma-separated matching
        assert _match_album_artist(
            "Fixture Artist Alpha", "Fixture Artist Alpha, Fixture Artist Beta"
        )
        assert not _match_album_artist(
            "Fixture Artist Gamma", "Fixture Artist Alpha, Fixture Artist Beta"
        )

        # Integration: metadata lookup finds the collab single
        meta = _load_album_metadata()
        type_df = meta["type"]
        collab = type_df[type_df["album_name"] == "Fixture Collab Single"]
        assert len(collab) == 1, f"Fixture Collab Single should have metadata, found {len(collab)}"
        assert collab.iloc[0]["album_type"] == "single", (
            f"Expected 'single', got {collab.iloc[0]['album_type']}"
        )

    def test_collab_single_excluded_from_album_chart(self, seed_conn):
        """Fixture Collab Single (album_type='single') must not appear in the
        Billboard album chart, even though its album_artists field uses
        comma-separated format instead of exact artist_name match."""
        raw = load_billboard_raw(30_000, True, 4, 0)
        album_weekly = compute_album_weekly_rankings(raw, top_n=100, merge_level=1)
        album_names = set(album_weekly["album_name"])
        assert "Fixture Collab Single" not in album_names, (
            "Fixture Collab Single must be excluded from Billboard album chart"
        )

    def test_match_album_artist_json_array(self):
        """_match_album_artist handles JSON array format."""
        from backend.domains.billboard.data_loader import _match_album_artist

        assert _match_album_artist("Taylor Swift", '["Taylor Swift"]')
        assert _match_album_artist("Cardi B", '["Cardi B", "Megan Thee Stallion"]')
        assert not _match_album_artist("Taylor Swift", '["Cardi B", "Megan Thee Stallion"]')

    def test_match_album_artist_null_or_empty(self):
        """_match_album_artist treats NULL/empty album_artists as match-all (safety)."""
        from backend.domains.billboard.data_loader import _match_album_artist

        assert _match_album_artist("Any Artist", None)
        assert _match_album_artist("Any Artist", "")
        assert _match_album_artist("Any Artist", "   ")

    def test_match_album_artist_case_insensitive(self):
        """_match_album_artist uses casefold for case-insensitive matching."""
        from backend.domains.billboard.data_loader import _match_album_artist

        assert _match_album_artist("Lady Gaga", "lady gaga")
        assert _match_album_artist("LADY GAGA", "Lady Gaga")
        assert _match_album_artist("Taylor Swift", "TAYLOR SWIFT, Ed Sheeran")

    def test_match_album_artist_diacritic_insensitive(self):
        """_match_album_artist strips combining diacritics via NFKD normalization."""
        from backend.domains.billboard.data_loader import _match_album_artist

        assert _match_album_artist("Beyonce", "Beyoncé")
        assert _match_album_artist("Beyoncé", "Beyoncé, Jay-Z")
        # Different artists despite diacritic stripping
        assert not _match_album_artist("Beyoncé", "Rihanna")


class TestAggParamHash:
    def test_dynamic_threshold_produces_different_hash(self):
        """_agg_param_hash must include dynamic_threshold and max_merge_gap_minutes
        so that static pre-agg tables are never reused for dynamic requests."""
        from backend.core.db import _agg_param_hash

        h_static = _agg_param_hash(30_000, True, 4, 0, dynamic_threshold=False)
        h_dynamic = _agg_param_hash(30_000, True, 4, 0, dynamic_threshold=True)
        assert h_static != h_dynamic, "Static and dynamic thresholds must produce different hashes"

    def test_max_gap_minutes_produces_different_hash(self):
        """max_merge_gap_minutes also affects the hash."""
        from backend.core.db import _agg_param_hash

        h_default = _agg_param_hash(30_000, True, 4, 0)
        h_with_gap = _agg_param_hash(30_000, True, 4, 0, max_merge_gap_minutes=5)
        assert h_default != h_with_gap, (
            "Different max_merge_gap_minutes must produce different hashes"
        )

    def test_seed_preagg_never_matched_by_try_load(self, seed_conn):
        """Seed DB pre-agg tables use a sentinel hash that never matches any
        real _agg_param_hash output.  The seed's manually-built pre-agg tables
        are semantically stale (album agg uses t.album_id not source_album_id,
        artist agg lacks track_artists fanout, merge lacks source_album
        boundary).  _try_load_from_agg must return (None, None, None)."""
        from backend.domains.billboard.data_loader import _try_load_from_agg

        tracks, albums, artists = _try_load_from_agg(
            30_000,
            True,
            4,
            0,
            dynamic_threshold=False,
            max_merge_gap_minutes=None,
        )
        assert tracks is None, "Seed DB pre-agg must never match — album agg is stale"
        assert albums is None, "Seed DB pre-agg must never match — album agg is stale"
        assert artists is None, "Seed DB pre-agg must never match — artist agg is stale"


class TestBillboardWeekBoundary:
    def test_cross_week_fragments_not_merged(self, seed_conn):
        """R23/P2: merge_consecutive_plays must use billboard_week as a boundary
        so that short fragments straddling a week boundary are not merged into
        a single valid play attributed to the earlier week.

        Fixture Fragment Song (track 901, duration=40000) has 4 plays:
        - 2 fragments on Jun 1 (same week) → should still merge → 1 valid play
        - 2 fragments on May 27 23:55 / May 28 00:05 Beijing → straddle Thu
          boundary.  With week_start_dow=3 (Thursday), they land in different
          billboard_weeks.  Without the fix they'd merge to 40000ms (1 play);
          with the fix each stays at 20000ms (below 30s) and both drop.

        Total before fix: 2 valid plays (both pairs merge).
        Total after fix:  1 valid play (only the same-week Jun 1 pair merges).
        """
        from backend.domains.billboard.data_loader import load_billboard_raw

        raw = load_billboard_raw(30_000, True, 3, 0)

        frag_rows = raw[raw["track_name"] == "Fixture Fragment Song"]
        assert len(frag_rows) == 1, (
            f"Expected 1 valid play (same-week Jun 1 pair only), got {len(frag_rows)}. "
            "Cross-week fragments must not merge."
        )
        # The surviving row must be from the same-week Jun 1 pair, NOT from
        # the cross-week boundary pair (which would carry a May billboard_week).
        assert str(frag_rows.iloc[0]["billboard_week"]) == "2026-05-28", (
            "Surviving play should be from the same-week Jun 1 pair "
            "(billboard_week=2026-05-28), not from the cross-week pair"
        )

    def test_same_week_fragments_still_merged(self, seed_conn):
        """Same-week fragments of the same track should still merge normally.
        With default week_start_dow=4 (Friday), both the Jun 1 pair and the
        May 27-28 pair are each within the same billboard_week → both merge."""
        raw = load_billboard_raw(30_000, True, 4, 0)

        frag_rows = raw[raw["track_name"] == "Fixture Fragment Song"]
        assert len(frag_rows) == 2, (
            f"Expected 2 valid plays (both same-week pairs merge), got {len(frag_rows)}"
        )

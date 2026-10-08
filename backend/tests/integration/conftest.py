"""Real-distribution integration tests require their own explicit pytest process."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def require_real_data_integration(request):
    if not request.config.pluginmanager.hasplugin("backend.tests.real_data_integration"):
        pytest.fail(
            "Run integration with -p backend.tests.real_data_integration and SPOTIFY_STATS_TEST_SOURCE_DB"
        )


@pytest.fixture
def published_release_cycle_weekly_snapshot(client, default_params):
    """Prepare the exact real weekly publication before a comparison read."""
    from backend.domains.billboard import persistent_cache
    from backend.services.billboard_service import compute_weekly_data
    from backend.services.billboard_snapshot_service import configured_billboard_filters

    params = {
        **configured_billboard_filters(),
        **default_params,
        "merge_level": 2,
        "include_compilations": False,
    }
    compute_weekly_data(**params, force_rebuild=True)
    context = persistent_cache.build_cache_context("weekly", params)
    publication = persistent_cache.load_persisted_snapshot(context, allow_lkg=False)
    assert publication is not None, "Private fixture maintenance must publish exact weekly facts"
    assert publication["weekly_artist"] and publication["weekly_album"]
    return context


@pytest.fixture(scope="session")
def has_source_release_day():
    """Inspect source evidence independently; never infer precision from ISO length."""
    from datetime import date

    from backend.core.db import get_db

    def check(artist_name, album_name=None):
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT DISTINCT sam.album_name,sam.release_date
                FROM artists a JOIN albums al USING(artist_id)
                JOIN track_albums ta USING(album_id) JOIN tracks t USING(track_id)
                JOIN spotify_track_meta stm ON stm.spotify_track_id=t.spotify_track_id
                JOIN spotify_album_meta sam ON sam.spotify_album_id=stm.spotify_album_id
                WHERE a.artist_name=? AND sam.release_date_precision='day'""",
                (artist_name,),
            ).fetchall()
        finally:
            conn.close()
        for name, raw in rows:
            if album_name is not None and name != album_name:
                continue
            try:
                if date.fromisoformat(raw).isoformat() == raw:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    return check

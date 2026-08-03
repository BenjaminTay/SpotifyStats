from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def _seed_six_low_volume_entities(monkeypatch) -> tuple[int, str, str]:
    """Create six same-week entities so the one-play member falls below Top 5."""
    from backend.core import db as db_mod
    from backend.core.cache_manager import invalidate_all

    conn = db_mod.get_db(readonly=False)
    try:
        for index in range(6):
            artist_id = 88_100 + index
            album_id = 88_200 + index
            track_id = 88_300 + index
            artist_name = f"Uncharted Fixture Artist {index}"
            album_name = f"Uncharted Fixture Album {index}"
            track_name = f"Uncharted Fixture Track {index}"
            conn.execute(
                "INSERT INTO artists(artist_id, artist_name) VALUES (?, ?)",
                (artist_id, artist_name),
            )
            conn.execute(
                "INSERT INTO albums(album_id, album_name, artist_id) VALUES (?, ?, ?)",
                (album_id, album_name, artist_id),
            )
            conn.execute(
                """INSERT INTO tracks(track_id, track_name, artist_id, album_id)
                   VALUES (?, ?, ?, ?)""",
                (track_id, track_name, artist_id, album_id),
            )
            conn.execute(
                "INSERT INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'primary')",
                (track_id, artist_id),
            )
            for play_index in range(index + 1):
                minute = index * 10 + play_index
                conn.execute(
                    """INSERT INTO plays(
                           ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
                           platform, ms_played, track_id, content_type, source_album_id
                       ) VALUES (?, 2026, 7, 27, 0, 12, '2026-07-06',
                                 'contract', 180000, ?, 'audio', ?)""",
                    (f"2026-07-06T12:{minute:02d}:00Z", track_id, album_id),
                )
        conn.commit()
    finally:
        conn.close()

    # The portable seed contains preaggregates. Force this contract through the
    # live effective-play path so the inserted facts are visible to both detail
    # eligibility and Billboard qualification.
    monkeypatch.setattr(
        "backend.domains.billboard.chart_load_rank._try_load_from_agg",
        lambda *args, **kwargs: (None, None, None),
    )
    monkeypatch.setattr(
        "backend.domains.billboard.data_loader._try_load_from_agg",
        lambda *args, **kwargs: (None, None, None),
    )
    db_mod._load_plays_cached.cache_clear()
    db_mod._load_plays_for_artists_cached.cache_clear()
    db_mod.get_track_all_artists_map.cache_clear()
    db_mod.get_track_artist_names_map.cache_clear()
    invalidate_all()
    return 88_300, "Uncharted Fixture Album 0", "Uncharted Fixture Artist 0"


def test_effective_play_entities_remain_accessible_when_not_charted(client, monkeypatch):
    track_id, album_name, artist_name = _seed_six_low_volume_entities(monkeypatch)
    params = {
        "min_ms": 30_000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": False,
        "bb_top_n": 5,
        "bb_album_top_n": 5,
        "bb_artist_top_n": 5,
        "merge_level": 2,
    }

    responses = [
        client.get(f"/api/billboard/track/{track_id}", params=params),
        client.get(
            f"/api/billboard/album/{album_name}",
            params={**params, "artist_name": artist_name},
        ),
        client.get(f"/api/billboard/artist/{artist_name}", params=params),
    ]

    for response in responses:
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["found"] is True
        assert payload["chart_status"] == "not_charted"
        assert payload["effective_play_count"] == 1
        assert payload.get("chart_summary") is None
        assert payload.get("summary") is None

    album_payload = responses[1].json()
    assert album_payload["track_chart_status"] == "not_charted"
    artist_payload = responses[2].json()
    assert artist_payload["track_chart_status"] == "not_charted"
    assert artist_payload["album_chart_status"] == "not_charted"

    # Versus qualification deliberately remains narrower than detail access.
    picker = client.get("/api/billboard/entity-lists", params=params).json()
    assert all(row["track_id"] != track_id for row in picker["tracks"])
    assert all(row["display"] != album_name for row in picker["albums"])
    assert all(row["display"] != artist_name for row in picker["artists"])


def test_effective_play_threshold_controls_detail_eligibility(client, monkeypatch):
    track_id, _, _ = _seed_six_low_volume_entities(monkeypatch)
    valid = client.get(
        f"/api/billboard/track/{track_id}",
        params={"min_ms": 30_000, "dynamic_threshold": False, "bb_top_n": 5},
    )
    filtered = client.get(
        f"/api/billboard/track/{track_id}",
        params={"min_ms": 200_000, "dynamic_threshold": False, "bb_top_n": 5},
    )
    assert valid.status_code == 200
    assert valid.json()["chart_status"] == "not_charted"
    assert filtered.status_code == 404

from __future__ import annotations

from backend.domains.yearly_review.entity_links import entity_ref_from_row


def test_entity_links_cover_track_album_artist_and_normalize_float_id() -> None:
    track = entity_ref_from_row(
        {"track_id": 4454.0, "track_name": "Song", "artist_name": "Artist"}, "track"
    )
    album = entity_ref_from_row(
        {"album_project_id": 12.0, "album_name": "A/B", "artist_name": "A & B"},
        "album",
    )
    artist = entity_ref_from_row({"artist_name": "A & B"}, "artist")

    assert track and track.deep_link == "/music/tracks/4454"
    assert album and album.deep_link == "/music/albums/A%2FB?artist=A%20%26%20B"
    assert artist and artist.deep_link == "/music/artists/A%20%26%20B"


def test_track_without_stable_id_does_not_get_false_deep_link() -> None:
    track = entity_ref_from_row({"track_name": "Song", "artist_name": "Artist"}, "track")

    assert track and track.deep_link is None

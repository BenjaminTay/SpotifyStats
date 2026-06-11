"""Community feed — Cover image loading and post enrichment."""

from __future__ import annotations

from backend.domains.community.post_types import CommunityPost

# ──────────────────────────────────────────────


def _load_cover_maps(conn) -> dict:
    """Build lookup maps for cover URL construction.

    Returns dict with:
      - track_to_album: {track_id: album_id}
      - artist_to_id: {artist_name: artist_id}
      - album_name_to_id: {(album_name, artist_id): album_id}
    """
    track_to_album: dict[int, int] = {}
    artist_to_id: dict[str, int] = {}
    album_name_to_id: dict[tuple[str, int], int] = {}

    try:
        rows = conn.execute(
            "SELECT track_id, album_id FROM tracks WHERE album_id IS NOT NULL"
        ).fetchall()
        track_to_album = {r[0]: r[1] for r in rows}
    except Exception:
        pass

    try:
        rows = conn.execute("SELECT artist_id, artist_name FROM artists").fetchall()
        artist_to_id = {r[1]: r[0] for r in rows}
    except Exception:
        pass

    try:
        rows = conn.execute("SELECT album_id, album_name, artist_id FROM albums").fetchall()
        album_name_to_id = {(r[1], r[2]): r[0] for r in rows}
    except Exception:
        pass

    return {
        "track_to_album": track_to_album,
        "artist_to_id": artist_to_id,
        "album_name_to_id": album_name_to_id,
    }


def _enrich_post_images(post: CommunityPost, cover_maps: dict) -> None:
    """Add cover/artist images to a post based on its linked entities."""
    track_to_album = cover_maps.get("track_to_album", {})
    artist_to_id = cover_maps.get("artist_to_id", {})
    album_name_to_id = cover_maps.get("album_name_to_id", {})

    # Gather artist names from this post's entities (needed for album lookup)
    linked_artist_names = {e["name"] for e in post.linked_entities if e.get("type") == "artist"}

    images: list[str] = []

    # Album cover (for album chart posts)
    for entity in post.linked_entities:
        if entity.get("type") == "album":
            album_name = entity.get("name", "")
            # Try each linked artist to find the matching album
            for artist_name in linked_artist_names:
                aid = artist_to_id.get(artist_name)
                if aid and (album_name, aid) in album_name_to_id:
                    url = f"/covers/albums/{album_name_to_id[(album_name, aid)]}.jpg"
                    if url not in images:
                        images.append(url)
                        break
            if images:
                break

    # Add image for first linked track (via album cover)
    if not images:
        for entity in post.linked_entities:
            if entity.get("type") == "track":
                tid = entity.get("id")
                if tid and tid in track_to_album:
                    url = f"/covers/albums/{track_to_album[tid]}.jpg"
                    if url not in images:
                        images.append(url)
                        break

    # Add image for linked artist
    for entity in post.linked_entities:
        if entity.get("type") == "artist":
            name = entity.get("name", "")
            aid = artist_to_id.get(name)
            if aid:
                url = f"/covers/artists/{aid}.jpg"
                if url not in images:
                    images.append(url)
                    break

    post.images = images

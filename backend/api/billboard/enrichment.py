"""Enrichment API — external data enrichment for detail pages (Wikipedia, Spotify, Genius)."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.providers.base import ProviderError
from backend.services.genius_service import _get_client as get_genius_client
from backend.services.wikipedia_service import (
    get_album_wiki,
    get_artist_wiki,
    get_track_wiki,
)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# Response models
# ═══════════════════════════════════════════════════════════════════════════


class WikiSinglesItem(BaseModel):
    name: str
    date: str | None = None


class AlbumWikiInfobox(BaseModel):
    release_date: str = ""
    recorded: str = ""
    studio: str = ""
    genre: str = ""
    length: str = ""
    label: str = ""
    producer: str = ""
    singles: list[WikiSinglesItem] = []


class AlbumWikiSections(BaseModel):
    background: str = ""
    reception: str = ""
    commercial: str = ""


class AlbumEnrichmentResponse(BaseModel):
    wiki: dict | None = None
    genius: dict | None = None


class ArtistWikiSections(BaseModel):
    early_life: str = ""
    discography: str = ""


class ArtistEnrichmentResponse(BaseModel):
    wiki: dict | None = None
    genius: dict | None = None


class TrackEnrichmentResponse(BaseModel):
    wiki: dict | None = None
    genius: dict | None = None


def _safe_wiki_lookup(lookup, *args):
    """Treat optional wiki enrichment as nullable while preserving provider errors."""
    try:
        return lookup(*args)
    except ProviderError:
        raise
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Album enrichment
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/album/{album_name:path}", response_model=AlbumEnrichmentResponse)
def get_album_enrichment(
    album_name: str,
    artist_name: str = Query(..., description="Artist name for disambiguation"),
    include_genius: bool = Query(False, description="Whether to fetch Genius album info"),
):
    """Get Wikipedia and optionally Genius enrichment data for an album."""
    result: dict = {"wiki": None, "genius": None}

    wiki = _safe_wiki_lookup(get_album_wiki, album_name, artist_name)
    if wiki:
        result["wiki"] = {
            "url": wiki["url"],
            "lang": wiki["lang"],
            "summary": wiki["summary"],
            "summary_zh": wiki.get("summary_zh", ""),
            "description": wiki["description"],
            "description_zh": wiki.get("description_zh", ""),
            "thumbnail": wiki["thumbnail"],
            "infobox": wiki["infobox"],
            "sections": wiki["sections"],
            "sections_zh": wiki.get("sections_zh", {}),
            "structured": wiki.get("structured"),
        }

    if include_genius:
        client = get_genius_client()
        if client:
            try:
                album = client.search_album(album_name, artist_name)
                if album:
                    result["genius"] = {
                        "name": album.name,
                        "artist": album.artist,
                        "cover_url": album.cover_url,
                        "release_date": album.release_date,
                        "url": album.url,
                    }
            except Exception:
                pass

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Artist enrichment
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/artist/{artist_name:path}", response_model=ArtistEnrichmentResponse)
def get_artist_enrichment(
    artist_name: str,
    include_genius: bool = Query(False, description="Whether to fetch Genius artist info"),
):
    """Get Wikipedia and optionally Genius enrichment data for an artist."""
    result: dict = {"wiki": None, "genius": None}

    wiki = _safe_wiki_lookup(get_artist_wiki, artist_name)
    if wiki:
        result["wiki"] = {
            "url": wiki["url"],
            "lang": wiki["lang"],
            "summary": wiki["summary"],
            "summary_zh": wiki.get("summary_zh", ""),
            "description": wiki["description"],
            "description_zh": wiki.get("description_zh", ""),
            "thumbnail": wiki["thumbnail"],
            "sections": wiki["sections"],
            "sections_zh": wiki.get("sections_zh", {}),
            "structured": wiki.get("structured"),
        }

    if include_genius:
        client = get_genius_client()
        if client:
            try:
                songs = client.get_artist_songs(artist_name, max_songs=1)
                if songs:
                    # Genius doesn't have a direct artist info endpoint in the wrapper,
                    # but we can derive some info from the artist's songs
                    result["genius"] = {"artist_name": artist_name, "has_songs": True}
            except Exception:
                pass

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Track enrichment
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/track/{track_name:path}", response_model=TrackEnrichmentResponse)
def get_track_enrichment(
    track_name: str,
    artist_name: str = Query(..., description="Artist name for disambiguation"),
    include_genius: bool = Query(True, description="Whether to fetch Genius song info"),
):
    """Get Wikipedia and optionally Genius enrichment data for a track."""
    result: dict = {"wiki": None, "genius": None}

    wiki = _safe_wiki_lookup(get_track_wiki, track_name, artist_name)
    if wiki:
        result["wiki"] = {
            "url": wiki["url"],
            "lang": wiki["lang"],
            "summary": wiki["summary"],
            "summary_zh": wiki.get("summary_zh", ""),
            "description": wiki["description"],
            "description_zh": wiki.get("description_zh", ""),
            "sections": wiki["sections"],
            "sections_zh": wiki.get("sections_zh", {}),
            "structured": wiki.get("structured"),
        }

    if include_genius:
        client = get_genius_client()
        if client:
            try:
                song = client.get_song(track_name, artist_name)
                if song:
                    result["genius"] = {
                        "title": song.title,
                        "artist": song.artist,
                        "url": song.url,
                        "album_name": song.album_name,
                        "cover_url": song.cover_url,
                        "release_date": song.release_date,
                    }
            except Exception:
                pass

    return result

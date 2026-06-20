"""Spotify OAuth PKCE API endpoints."""

from sqlite3 import Connection
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from backend.core.auth import require_auth
from backend.core.db import get_db
from backend.core.spotify_utils import (
    clear_user_tokens,
    get_followed_artists,
    get_playlists,
    get_recently_played,
    get_top_items,
    get_user_access_token,
    sync_all_spotify_data,
)
from backend.dependencies import get_conn
from backend.models.common import (
    SpotifyAuthUrlResponse,
    SpotifyDataResponse,
    SpotifyDisconnectResponse,
    SpotifyPlaybackResponse,
    SpotifySavedTracksSyncResponse,
    SpotifyStatusResponse,
    SpotifySyncAllResponse,
)
from backend.services.spotify_auth import (
    begin_oauth_flow,
    complete_oauth_flow,
    fetch_saved_tracks,
    get_connection_status,
    get_live_playback,
)

router = APIRouter(prefix="/spotify/auth", tags=["Spotify Auth"])
_DEFAULT_FRONTEND_ORIGIN = "http://localhost:5173"


def _origin_from_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def _get_frontend_origin() -> str:
    from backend.core.config import FRONTEND_ORIGIN, SPOTIFY_REDIRECT_URI

    configured_origin = FRONTEND_ORIGIN.rstrip("/") if FRONTEND_ORIGIN else ""
    if configured_origin and configured_origin != _DEFAULT_FRONTEND_ORIGIN:
        return configured_origin
    return _origin_from_url(SPOTIFY_REDIRECT_URI) or configured_origin or _DEFAULT_FRONTEND_ORIGIN


@router.get("/login", response_model=SpotifyAuthUrlResponse)
def spotify_login():
    """Start OAuth PKCE flow. Returns the Spotify authorization URL."""
    try:
        return begin_oauth_flow()
    except RuntimeError as exc:
        if str(exc) == "SPOTIFY_CLIENT_ID not configured":
            raise HTTPException(
                status_code=503,
                detail="spotify_client_not_configured",
            ) from exc
        raise


@router.get("/callback", response_class=RedirectResponse)
def spotify_callback(code: str, state: str):
    """Handle Spotify OAuth redirect. Exchanges code for tokens, redirects to settings."""
    from backend.core.db import get_db

    write_conn = get_db(readonly=False)
    try:
        result = complete_oauth_flow(write_conn, code, state)
        if not result["success"]:
            return RedirectResponse(
                url=f"{_get_frontend_origin()}/settings?spotify_error={result['error']}"
            )
        return RedirectResponse(url=f"{_get_frontend_origin()}/settings?spotify_connected=true")
    finally:
        write_conn.close()


@router.get("/status", response_model=SpotifyStatusResponse)
def spotify_status(conn: Connection = Depends(get_conn)):
    """Get current Spotify connection status."""
    return get_connection_status(conn)


@router.delete("/disconnect", response_model=SpotifyDisconnectResponse)
def spotify_disconnect(auth: None = Depends(require_auth)):
    """Disconnect Spotify and remove stored tokens."""
    from backend.core.db import get_db

    write_conn = get_db(readonly=False)
    try:
        clear_user_tokens(write_conn)
        return {"status": "disconnected"}
    finally:
        write_conn.close()


@router.post("/sync", response_model=SpotifySavedTracksSyncResponse)
def spotify_sync(auth: None = Depends(require_auth)):
    """Fetch saved tracks from Spotify API and backfill added_date."""
    from backend.core.db import get_db

    write_conn = get_db(readonly=False)
    try:
        result = fetch_saved_tracks(write_conn)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "sync_failed"))
        return result
    finally:
        write_conn.close()


@router.get("/data", response_model=SpotifyDataResponse)
def spotify_data(conn: Connection = Depends(get_conn)):
    """Return all persisted Spotify data."""
    result = {}
    for item_type in ["artists", "tracks"]:
        result[item_type] = {}
        for tr in ["short_term", "medium_term", "long_term"]:
            items = get_top_items(conn, item_type, tr)
            result[item_type][tr] = items if items else []
    result["recently_played"] = get_recently_played(conn) or []
    result["followed_artists"] = get_followed_artists(conn) or []
    result["playlists"] = get_playlists(conn) or []
    return result


@router.get("/playing", response_model=SpotifyPlaybackResponse)
def spotify_playing():
    """Get current playback state (live from Spotify)."""
    write_conn = get_db(readonly=False)
    try:
        return get_live_playback(write_conn)
    finally:
        write_conn.close()


@router.post("/sync-all", response_model=SpotifySyncAllResponse)
def spotify_sync_all(auth: None = Depends(require_auth)):
    """Fetch and persist all available Spotify data (profile, top items, recently played)."""
    from backend.core.db import get_db

    write_conn = get_db(readonly=False)
    try:
        token = get_user_access_token(write_conn)
        if not token:
            raise HTTPException(status_code=401, detail="not_connected")
        result = sync_all_spotify_data(write_conn, token)
        return result
    finally:
        write_conn.close()

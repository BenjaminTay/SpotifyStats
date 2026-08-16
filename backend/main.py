"""Spotify Stats — FastAPI backend entry point."""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from backend.api.router import api_router
from backend.core import db as db_module
from backend.core.access_surface import (
    PRIVATE_ADMIN_SURFACE,
    PUBLIC_READONLY_SURFACE,
    SURFACE_HEADER,
    capabilities_for_request,
    is_public_readonly,
    public_policy_decision,
    reset_public_readonly_db_guard,
    set_public_readonly_db_guard,
    trusted_gateway_required,
    trusted_request_surface,
)
from backend.core.config import FRONTEND_ORIGIN
from backend.core.logging_config import setup_logging
from backend.core.migrations import run_migrations
from backend.core.request_context import REQUEST_ID_HEADER, reset_request_id, set_request_id
from backend.core.warmup import start_warmup_thread
from backend.models.common import HealthResponse, RuntimeCapabilitiesResponse
from backend.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderHTTPError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderRateLimitError,
    ProviderServerError,
)

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_migrations()

    # Start background job queue for async enrichment & cover downloads
    from backend.core.job_queue import get_job_queue
    from backend.jobs.handlers import (
        handle_cover_download,
        handle_genius_lyrics,
        handle_wikipedia_enrich,
    )
    from backend.services.artist_identity_rebuild_service import handle_artist_identity_rebuild
    from backend.services.music_search_maintenance_service import (
        enqueue_music_search_snapshot_rebuild,
        handle_music_search_snapshot_rebuild,
    )
    from backend.services.track_credit_rebuild_service import handle_track_credit_rebuild

    job_queue = get_job_queue()
    job_queue.register("cover_download", handle_cover_download)
    job_queue.register("wikipedia_enrich", handle_wikipedia_enrich)
    job_queue.register("genius_lyrics", handle_genius_lyrics)
    job_queue.register("artist_identity_rebuild", handle_artist_identity_rebuild)
    job_queue.register("track_credit_rebuild", handle_track_credit_rebuild)
    job_queue.register("music_search_snapshot_rebuild", handle_music_search_snapshot_rebuild)
    # Resolve the configured database at lifespan start. Tests and maintenance
    # tools intentionally replace ``db_module.DB_PATH`` with an isolated copy;
    # importing the string at module load would make the persistent JobQueue
    # silently keep targeting the user's real database.
    job_queue.start(db_module.DB_PATH)
    from backend.core.db import get_db
    from backend.core.job_queue import Job
    from backend.domains.metadata.artist_identity import get_identity_state
    from backend.domains.metadata.track_credits import get_track_credit_state

    identity_conn = get_db()
    try:
        identity_state = get_identity_state(identity_conn)
        credit_state = get_track_credit_state(identity_conn)
    finally:
        identity_conn.close()
    if identity_state.get("rebuild_status") in {"pending", "failed"}:
        job_queue.enqueue_if_not_pending(
            Job.create(
                "artist_identity_rebuild",
                "artist_identity",
                "global",
                revision=int(identity_state.get("current_revision") or 0),
            )
        )
    if credit_state.get("rebuild_status") in {"pending", "failed"}:
        job_queue.enqueue_if_not_pending(
            Job.create(
                "track_credit_rebuild",
                "track_credit",
                "global",
                revision=int(credit_state.get("current_revision") or 0),
            )
        )

    if (
        os.environ.get("SPOTIFY_STATS_WARMUP", "1") != "0"
        and "PYTEST_CURRENT_TEST" not in os.environ
    ):
        enqueue_music_search_snapshot_rebuild()
        start_warmup_thread()
    yield
    job_queue.stop()


app = FastAPI(
    title="Spotify Stats API",
    description="Spotify Extended Streaming History 数据分析 API",
    version="1.0.0",
    docs_url=None,
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def public_readonly_surface_middleware(request: Request, call_next):
    """Authenticate the ingress and enforce the public showcase boundary."""

    # Container health checks intentionally bypass gateway authentication.
    # No other route may fall back to a privileged surface when enforcement is
    # enabled and proxy headers are absent, malformed, or forged.
    health_exempt = request.url.path == "/api/health"
    surface = trusted_request_surface(request)
    if surface is None and trusted_gateway_required() and not health_exempt:
        return JSONResponse(
            status_code=403,
            content={
                "detail": {
                    "error": "untrusted_gateway",
                    "message": "This request did not come through a trusted application gateway.",
                }
            },
        )
    if surface is None:
        surface = PRIVATE_ADMIN_SURFACE

    request.state.spotify_stats_surface = surface
    db_guard_token = set_public_readonly_db_guard(surface == PUBLIC_READONLY_SURFACE)
    try:
        if surface == PUBLIC_READONLY_SURFACE:
            decision = public_policy_decision(request.method, request.url.path)
            if decision == "disabled":
                return JSONResponse(status_code=404, content={"detail": "Not found"})
            if decision == "readonly":
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": {
                            "error": "public_readonly",
                            "message": "This operation is unavailable on the public showcase.",
                        }
                    },
                )

        response = await call_next(request)
        response.headers[SURFACE_HEADER] = surface
        return response
    finally:
        reset_public_readonly_db_guard(db_guard_token)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a request id to logs and responses for local observability."""
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    finally:
        reset_request_id(token)


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COVERS_DIR = os.path.join(_PROJECT_ROOT, "data", "covers")


def _provider_error_response(exc: ProviderError) -> tuple[int, str]:
    """Map provider failures to stable API error classes."""
    if isinstance(exc, ProviderRateLimitError):
        return 429, "provider_rate_limited"
    if isinstance(exc, ProviderNetworkError):
        return 503, "provider_network_error"
    if isinstance(exc, ProviderAuthError):
        return 502, "provider_auth_error"
    if isinstance(exc, ProviderServerError):
        return 502, "provider_server_error"
    if isinstance(exc, ProviderParseError):
        return 502, "provider_parse_error"
    if isinstance(exc, ProviderHTTPError):
        return 502, "provider_http_error"
    return 502, "provider_error"


@app.exception_handler(ProviderError)
async def provider_exception_handler(_request: Request, exc: ProviderError):
    """Return structured upstream-provider errors without exposing raw secrets."""
    status_code, error_code = _provider_error_response(exc)
    logger.warning(
        "Provider error handled: provider=%s error=%s upstream_status=%s",
        exc.provider,
        error_code,
        exc.status,
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": {
                "error": error_code,
                "provider": exc.provider,
                "status": exc.status,
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    """Return generic 500 without leaking stack traces to clients."""
    logger.exception("Unhandled exception: %s", str(exc)[:200])
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── 智能封面端点 ───────────────────────────────────────────────────────


_COVER_BROWSER_CACHE_CONTROL = "private, max-age=604800, stale-while-revalidate=2592000"


def _etag_matches(if_none_match: str, etag: str) -> bool:
    """Compare strong or weak validators by their opaque ETag value."""

    expected = etag.removeprefix("W/")
    return any(
        candidate == "*" or candidate.removeprefix("W/") == expected
        for candidate in (part.strip() for part in if_none_match.split(","))
    )


def _local_cover_response(request: Request, filepath: str) -> Response:
    """Return a local cover with explicit browser caching and 304 support."""

    stat_result = os.stat(filepath)
    response = FileResponse(
        filepath,
        media_type="image/jpeg",
        stat_result=stat_result,
        headers={"Cache-Control": _COVER_BROWSER_CACHE_CONTROL},
    )
    etag = response.headers["etag"]
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and _etag_matches(if_none_match, etag):
        return Response(
            status_code=304,
            headers={
                "Cache-Control": _COVER_BROWSER_CACHE_CONTROL,
                "ETag": etag,
                "Last-Modified": response.headers["last-modified"],
            },
        )
    return response


def _get_cover_cdn_url(cover_type: str, entity_id: int) -> str | None:
    """从数据库查询 Spotify CDN URL 作为回退源。"""
    from backend.core.db import get_db

    conn = get_db()
    try:
        if cover_type == "albums":
            row = conn.execute(
                """SELECT image_url FROM (
                       -- ① Local cache in albums table
                       SELECT image_url, 0 AS priority
                       FROM albums
                       WHERE album_id = ?
                         AND image_url IS NOT NULL
                         AND image_url != ''

                       UNION ALL

                       -- ② album_spotify_links (prefer album-type)
                       SELECT image_url, 1 AS priority FROM (
                           SELECT sam.image_url,
                                  CASE sam.album_type WHEN 'album' THEN 0 ELSE 1 END AS _sort,
                                  asl.confidence
                           FROM album_spotify_links asl
                           JOIN spotify_album_meta sam
                             ON sam.spotify_album_id = asl.spotify_album_id
                           WHERE asl.album_id = ?
                             AND sam.image_url IS NOT NULL
                             AND sam.image_url != ''
                           ORDER BY _sort, asl.confidence DESC, sam.release_date DESC
                           LIMIT 1
                       )

                       UNION ALL

                       -- ③ Old track-chain fallback
                       SELECT image_url, 2 AS priority FROM (
                           SELECT sam.image_url,
                                  CASE sam.album_type WHEN 'album' THEN 0 ELSE 1 END AS _sort
                           FROM (
                               SELECT track_id FROM tracks WHERE album_id = ?
                               UNION
                               SELECT track_id FROM track_albums WHERE album_id = ?
                           ) album_tracks
                           JOIN tracks t ON t.track_id = album_tracks.track_id
                           JOIN spotify_track_meta stm
                             ON t.spotify_track_id = stm.spotify_track_id
                           JOIN spotify_album_meta sam
                             ON sam.spotify_album_id = stm.spotify_album_id
                           WHERE sam.image_url IS NOT NULL
                             AND sam.image_url != ''
                           ORDER BY _sort
                           LIMIT 1
                       )
                   )
                   ORDER BY priority
                   LIMIT 1""",
                [entity_id, entity_id, entity_id, entity_id],
            ).fetchone()
        elif cover_type == "artists":
            row = conn.execute(
                "SELECT image_url FROM artists WHERE artist_id = ?", [entity_id]
            ).fetchone()
        else:
            row = None
    finally:
        conn.close()
    return row["image_url"] if row and row["image_url"] else None


def _get_entity_name(cover_type: str, entity_id: int) -> tuple[str | None, str | None]:
    """查询实体名称，用于 Spotify API 搜索。返回 (name, artist_name_or_None)。"""
    from backend.core.db import get_db

    conn = get_db()
    try:
        if cover_type == "albums":
            row = conn.execute(
                "SELECT album_name, artist_name FROM albums "
                "JOIN artists ON artists.artist_id = albums.artist_id "
                "WHERE album_id = ?",
                [entity_id],
            ).fetchone()
            if row:
                return row["album_name"], row["artist_name"]
        elif cover_type == "artists":
            row = conn.execute(
                "SELECT artist_name FROM artists WHERE artist_id = ?", [entity_id]
            ).fetchone()
            if row:
                return row["artist_name"], None
    finally:
        conn.close()
    return None, None


def _store_cover_url(cover_type: str, entity_id: int, image_url: str):
    """将 Spotify API 获取的封面 URL 写回数据库。"""
    from backend.core.db import get_db

    conn = get_db(readonly=False)
    try:
        if cover_type == "albums":
            conn.execute(
                "UPDATE albums SET image_url = ? WHERE album_id = ?",
                [image_url, entity_id],
            )
        elif cover_type == "artists":
            conn.execute(
                "UPDATE artists SET image_url = ? WHERE artist_id = ?",
                [image_url, entity_id],
            )
        conn.commit()
    finally:
        conn.close()


def _search_spotify_cover(cover_type: str, entity_id: int) -> str | None:
    """通过 Spotify API 搜索专辑/艺人封面 URL。

    仅在本地缓存和数据库 CDN URL 均缺失时调用。
    成功后会自动将 URL 写回数据库，后续请求直接命中 DB 缓存。
    """
    from backend.providers.spotify.client import SpotifyProvider

    entity_name, artist_name = _get_entity_name(cover_type, entity_id)
    if not entity_name:
        return None

    provider = SpotifyProvider()
    token = provider.get_cc_token()
    if not token:
        return None

    try:
        if cover_type == "albums" and artist_name:
            url = provider.search_album_cover(entity_name, artist_name, token)
        elif cover_type == "artists":
            url = provider.search_artist_cover(entity_name, token)
        else:
            url = None

        if url:
            _store_cover_url(cover_type, entity_id, url)
        return url
    except Exception:
        logger.exception("Spotify cover search failed: %s/%s", cover_type, entity_id)
        return None


@app.get("/covers/{cover_type}/{entity_id}.jpg")
async def get_cover(request: Request, cover_type: str, entity_id: int):
    """封面图片服务，四级回退链：

    1. 本地缓存命中 → 直接返回文件（最快）
    2. 本地缺失 → 查 DB 获取 Spotify CDN URL → 重定向到 CDN + 后台下载缓存
    3. 无 CDN URL → 通过 Spotify API 搜索封面 → 写回 DB → 重定向 + 后台下载
    4. API 搜索无结果 → 404
    """
    if cover_type not in ("albums", "artists"):
        raise HTTPException(status_code=404)

    filepath = os.path.join(_COVERS_DIR, cover_type, f"{entity_id}.jpg")

    # ① 本地缓存命中
    if os.path.isfile(filepath):
        return _local_cover_response(request, filepath)

    # ② 本地缺失，尝试从 DB CDN URL 获取
    cdn_url = _get_cover_cdn_url(cover_type, entity_id)

    # Public showcase requests may only use already-known cover sources. They
    # must not trigger Spotify lookups, database writes, or background jobs.
    public_readonly = is_public_readonly(request)

    # ③ DB 也无 URL，私有管理入口可尝试通过 Spotify API 搜索
    if not cdn_url and not public_readonly:
        cdn_url = _search_spotify_cover(cover_type, entity_id)

    if cdn_url:
        if not public_readonly:
            from backend.core.job_queue import Job, get_job_queue

            # 后台静默下载到本地，下次请求直接走缓存
            job = Job.create("cover_download", cover_type, str(entity_id), cdn_url=cdn_url)
            get_job_queue().enqueue_if_not_pending(job)
        return RedirectResponse(url=cdn_url)

    # ④ 无数据
    raise HTTPException(status_code=404)


# ── API 路由 ─────────────────────────────────────────────────────────────

app.include_router(api_router, prefix="/api")


@app.get("/api/runtime/capabilities", response_model=RuntimeCapabilitiesResponse)
async def runtime_capabilities(request: Request):
    """Return presentation capabilities for the trusted ingress surface."""
    return capabilities_for_request(request).as_dict()


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Spotify Stats API",
    )


@app.get("/api/health", response_model=HealthResponse)
async def health():
    return {"status": "ok"}

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
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from backend.api.router import api_router
from backend.core.config import FRONTEND_ORIGIN
from backend.core.db import DB_PATH
from backend.core.logging_config import setup_logging
from backend.core.migrations import run_migrations
from backend.core.request_context import REQUEST_ID_HEADER, reset_request_id, set_request_id
from backend.core.warmup import start_warmup_thread
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

    job_queue = get_job_queue()
    job_queue.register("cover_download", handle_cover_download)
    job_queue.register("wikipedia_enrich", handle_wikipedia_enrich)
    job_queue.register("genius_lyrics", handle_genius_lyrics)
    job_queue.start(DB_PATH)

    if (
        os.environ.get("SPOTIFY_STATS_WARMUP", "1") != "0"
        and "PYTEST_CURRENT_TEST" not in os.environ
    ):
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


def _get_cover_cdn_url(cover_type: str, entity_id: int) -> str | None:
    """从数据库查询 Spotify CDN URL 作为回退源。"""
    from backend.core.db import get_db

    conn = get_db()
    if cover_type == "albums":
        row = conn.execute(
            """SELECT image_url
               FROM (
                   SELECT image_url, 0 AS priority
                   FROM albums
                   WHERE album_id = ?
                     AND image_url IS NOT NULL
                     AND image_url != ''

                   UNION ALL

                   SELECT sam.image_url, 1 AS priority
                   FROM albums al
                   JOIN spotify_album_meta sam
                     ON sam.spotify_album_id = al.spotify_album_id
                   WHERE al.album_id = ?
                     AND al.spotify_album_id IS NOT NULL
                     AND sam.image_url IS NOT NULL
                     AND sam.image_url != ''

                   UNION ALL

                   SELECT sam.image_url, 2 AS priority
                   FROM albums al
                   JOIN track_albums ta ON ta.album_id = al.album_id
                   JOIN tracks t ON t.track_id = ta.track_id
                   JOIN spotify_track_meta stm
                     ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
                   JOIN spotify_album_meta sam
                     ON sam.spotify_album_id = stm.spotify_album_id
                   WHERE al.album_id = ?
                     AND sam.image_url IS NOT NULL
                     AND sam.image_url != ''
               )
               ORDER BY priority
               LIMIT 1""",
            [entity_id, entity_id, entity_id],
        ).fetchone()
    elif cover_type == "artists":
        row = conn.execute(
            "SELECT image_url FROM artists WHERE artist_id = ?", [entity_id]
        ).fetchone()
    else:
        row = None
    conn.close()
    return row["image_url"] if row and row["image_url"] else None


@app.get("/covers/{cover_type}/{entity_id}.jpg")
async def get_cover(cover_type: str, entity_id: int):
    """封面图片服务，三级回退链：

    1. 本地缓存命中 → 直接返回文件（最快）
    2. 本地缺失 → 查 DB 获取 Spotify CDN URL → 重定向到 CDN + 后台下载缓存
    3. 无 CDN URL → 404
    """
    if cover_type not in ("albums", "artists"):
        raise HTTPException(status_code=404)

    filepath = os.path.join(_COVERS_DIR, cover_type, f"{entity_id}.jpg")

    # ① 本地缓存命中
    if os.path.isfile(filepath):
        return FileResponse(filepath, media_type="image/jpeg")

    # ② 本地缺失，尝试从 CDN 获取
    cdn_url = _get_cover_cdn_url(cover_type, entity_id)
    if cdn_url:
        from backend.core.job_queue import Job, get_job_queue

        # 后台静默下载到本地，下次请求直接走缓存
        job = Job.create("cover_download", cover_type, str(entity_id), cdn_url=cdn_url)
        get_job_queue().enqueue_if_not_pending(job)
        return RedirectResponse(url=cdn_url)

    # ③ 无数据
    raise HTTPException(status_code=404)


# ── API 路由 ─────────────────────────────────────────────────────────────

app.include_router(api_router, prefix="/api")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Spotify Stats API",
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}

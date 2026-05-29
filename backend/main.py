"""Spotify Stats — FastAPI backend entry point."""

import os
import urllib.request
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, BackgroundTasks
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, RedirectResponse

from backend.api.router import api_router
from backend.core.warmup import start_warmup_thread


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if (
        os.environ.get("SPOTIFY_STATS_WARMUP", "1") != "0"
        and "PYTEST_CURRENT_TEST" not in os.environ
    ):
        start_warmup_thread()
    yield

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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COVERS_DIR = os.path.join(_PROJECT_ROOT, "data", "covers")


# ── 智能封面端点 ───────────────────────────────────────────────────────

def _get_cover_cdn_url(cover_type: str, entity_id: int) -> Optional[str]:
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
            [entity_id, entity_id],
        ).fetchone()
    elif cover_type == "artists":
        row = conn.execute(
            "SELECT image_url FROM artists WHERE artist_id = ?", [entity_id]
        ).fetchone()
    else:
        row = None
    conn.close()
    return row["image_url"] if row and row["image_url"] else None


def _cache_cover_locally(cdn_url: str, filepath: str, cover_type: str, entity_id: int):
    """后台任务：从 Spotify CDN 下载封面并写入本地缓存 + 更新 DB。"""
    try:
        req = urllib.request.Request(cdn_url, headers={"User-Agent": "SpotifyStats/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(data)

        from backend.core.db import get_db
        conn = get_db(readonly=False)
        rel_path = f"covers/{cover_type}/{entity_id}.jpg"
        if cover_type == "albums":
            conn.execute("UPDATE albums SET image_path = ? WHERE album_id = ?", [rel_path, entity_id])
        elif cover_type == "artists":
            conn.execute("UPDATE artists SET image_path = ? WHERE artist_id = ?", [rel_path, entity_id])
        conn.commit()
        conn.close()
    except Exception:
        pass  # 静默失败，CDN 重定向仍然可用


@app.get("/covers/{cover_type}/{entity_id}.jpg")
async def get_cover(cover_type: str, entity_id: int, background_tasks: BackgroundTasks):
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
        # 后台静默下载到本地，下次请求直接走缓存
        background_tasks.add_task(_cache_cover_locally, cdn_url, filepath, cover_type, entity_id)
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

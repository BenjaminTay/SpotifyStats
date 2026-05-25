"""Spotify Stats — FastAPI backend entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html

from backend.api.router import api_router

app = FastAPI(
    title="Spotify Stats API",
    description="Spotify Extended Streaming History 数据分析 API",
    version="1.0.0",
    docs_url=None,  # 手动设置以使用自定义主题
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

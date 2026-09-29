from __future__ import annotations

import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.core.access_surface import PUBLIC_READONLY_SURFACE, SURFACE_HEADER
from backend.main import app
from backend.services.cover_thumbnail_service import ensure_cover_thumbnail, thumbnail_path

pytestmark = pytest.mark.unit


def test_thumbnail_backfill_keeps_original_and_refreshes_stale_variant(tmp_path):
    source = tmp_path / "albums" / "42.jpg"
    source.parent.mkdir()
    Image.new("RGB", (640, 640), "red").save(source, format="JPEG")
    original = source.read_bytes()
    thumbnail = thumbnail_path(tmp_path, "albums", 42)

    assert ensure_cover_thumbnail(source, thumbnail)
    with Image.open(thumbnail) as image:
        assert image.format == "WEBP"
        assert image.size == (160, 160)
    assert source.read_bytes() == original
    assert not ensure_cover_thumbnail(source, thumbnail)

    Image.new("RGB", (640, 640), "blue").save(source, format="JPEG")
    thumbnail_mtime = thumbnail.stat().st_mtime_ns
    source_mtime = source.stat().st_mtime_ns
    os.utime(source, ns=(source_mtime, thumbnail_mtime + 1_000_000_000))
    assert ensure_cover_thumbnail(source, thumbnail)
    with Image.open(thumbnail) as image:
        assert image.getpixel((80, 80))[2] > 150


def test_public_thumbnail_falls_back_briefly_then_serves_cached_webp(monkeypatch, tmp_path):
    import backend.main as main_module

    source = tmp_path / "albums" / "42.jpg"
    source.parent.mkdir()
    Image.new("RGB", (640, 640), "green").save(source, format="JPEG")
    original = source.read_bytes()
    monkeypatch.setattr(main_module, "_COVERS_DIR", str(tmp_path))
    headers = {SURFACE_HEADER: PUBLIC_READONLY_SURFACE}

    with TestClient(app) as client:
        fallback = client.get("/covers/albums/42.thumb.webp", headers=headers)
        assert fallback.status_code == 200
        assert fallback.content == original
        assert fallback.headers["content-type"] == "image/jpeg"
        assert fallback.headers["cache-control"] == "private, max-age=60"
        assert not thumbnail_path(tmp_path, "albums", 42).exists()

        ensure_cover_thumbnail(source, thumbnail_path(tmp_path, "albums", 42))
        ready = client.get("/covers/albums/42.thumb.webp", headers=headers)
        assert ready.status_code == 200
        assert ready.headers["content-type"] == "image/webp"
        assert ready.headers["cache-control"].startswith("private, max-age=604800")
        with Image.open(BytesIO(ready.content)) as image:
            assert image.size == (160, 160)

        revalidated = client.get(
            "/covers/albums/42.thumb.webp",
            headers={**headers, "If-None-Match": ready.headers["etag"]},
        )
        assert revalidated.status_code == 304

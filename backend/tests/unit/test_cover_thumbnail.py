from __future__ import annotations

import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.core.access_surface import PUBLIC_READONLY_SURFACE, SURFACE_HEADER
from backend.main import app
from backend.services.cover_thumbnail_service import (
    COVER_VARIANT_SIZES,
    ensure_cover_thumbnail,
    generate_downloaded_thumbnail,
    thumbnail_is_current,
    thumbnail_path,
)

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
    assert thumbnail_is_current(source, thumbnail)
    assert not ensure_cover_thumbnail(source, thumbnail)


@pytest.mark.parametrize("size", COVER_VARIANT_SIZES)
@pytest.mark.parametrize("cover_type", ["albums", "artists"])
def test_public_thumbnail_falls_back_briefly_then_serves_cached_webp(
    monkeypatch, tmp_path, size, cover_type
):
    import backend.main as main_module

    source = tmp_path / cover_type / "42.jpg"
    source.parent.mkdir()
    Image.new("RGB", (640, 640), "green").save(source, format="JPEG")
    original = source.read_bytes()
    monkeypatch.setattr(main_module, "_COVERS_DIR", str(tmp_path))
    headers = {SURFACE_HEADER: PUBLIC_READONLY_SURFACE}
    suffix = "thumb" if size == 160 else str(size)
    path = f"/covers/{cover_type}/42.{suffix}.webp"
    thumbnail = thumbnail_path(tmp_path, cover_type, 42, size)

    with TestClient(app) as client:
        fallback = client.get(path, headers=headers)
        assert fallback.status_code == 200
        assert fallback.content == original
        assert fallback.headers["content-type"] == "image/jpeg"
        assert fallback.headers["cache-control"] == "private, max-age=60"
        assert not thumbnail.exists()

        ensure_cover_thumbnail(source, thumbnail, size)
        ready = client.get(path, headers=headers)
        assert ready.status_code == 200
        assert ready.headers["content-type"] == "image/webp"
        assert ready.headers["cache-control"].startswith("private, max-age=604800")
        with Image.open(BytesIO(ready.content)) as image:
            assert image.size == (size, size)

        revalidated = client.get(
            path,
            headers={**headers, "If-None-Match": ready.headers["etag"]},
        )
        assert revalidated.status_code == 304

        os.utime(source, ns=(source.stat().st_atime_ns, thumbnail.stat().st_mtime_ns + 1))
        stale = client.get(path, headers=headers)
        assert stale.status_code == 200
        assert stale.content == original
        assert stale.headers["cache-control"] == "private, max-age=60"


@pytest.mark.parametrize("size", COVER_VARIANT_SIZES)
def test_variants_preserve_aspect_ratio_without_upscaling(tmp_path, size):
    source = tmp_path / "42.jpg"
    Image.new("RGB", (100, 50), "red").save(source)
    original = source.read_bytes()
    thumbnail = thumbnail_path(tmp_path, "albums", 42, size)
    assert ensure_cover_thumbnail(source, thumbnail, size)
    with Image.open(thumbnail) as image:
        assert image.size == (100, 50)
    assert source.read_bytes() == original


def test_variant_publication_rejects_source_changed_during_encoding(tmp_path, monkeypatch):
    source = tmp_path / "42.jpg"
    Image.new("RGB", (800, 800), "red").save(source)
    thumbnail = thumbnail_path(tmp_path, "albums", 42, 320)
    thumbnail.parent.mkdir(parents=True)
    thumbnail.write_bytes(b"previous file")
    os.utime(thumbnail, ns=(0, 0))
    original_save = Image.Image.save

    def concurrent_save(image, destination, *args, **kwargs):
        original_save(image, destination, *args, **kwargs)
        replacement = tmp_path / "replacement.jpg"
        original_save(Image.new("RGB", (800, 800), "blue"), replacement)
        os.replace(replacement, source)

    monkeypatch.setattr(Image.Image, "save", concurrent_save)
    assert not ensure_cover_thumbnail(source, thumbnail, 320)
    assert thumbnail.read_bytes() == b"previous file"
    assert list(thumbnail.parent.glob(".*.webp")) == []
    assert not thumbnail_is_current(source, thumbnail)


def test_source_replaced_at_publication_keeps_variant_stale(tmp_path, monkeypatch):
    import backend.services.cover_thumbnail_service as service

    source = tmp_path / "42.jpg"
    Image.new("RGB", (800, 800), "red").save(source)
    thumbnail = thumbnail_path(tmp_path, "albums", 42, 320)
    replace = service.os.replace
    source_mtime = source.stat().st_mtime_ns

    def concurrent_replace(temporary, destination):
        Image.new("RGB", (800, 800), "blue").save(source)
        os.utime(source, ns=(source_mtime, source_mtime + 1_000_000))
        replace(temporary, destination)

    monkeypatch.setattr(service.os, "replace", concurrent_replace)
    assert ensure_cover_thumbnail(source, thumbnail, 320)
    assert not thumbnail_is_current(source, thumbnail)
    with Image.open(thumbnail) as image:
        assert image.getpixel((100, 100))[0] > 150


def test_download_variant_failure_does_not_prevent_other_sizes(tmp_path, monkeypatch):
    import backend.services.cover_thumbnail_service as service

    source = tmp_path / "albums" / "42.jpg"
    source.parent.mkdir()
    Image.new("RGB", (800, 800), "red").save(source)
    original = source.read_bytes()
    ensure = service.ensure_cover_thumbnail

    def fail_one_size(source, thumbnail, size):
        if size == 320:
            raise OSError("encoding failed")
        return ensure(source, thumbnail, size)

    monkeypatch.setattr(service, "ensure_cover_thumbnail", fail_one_size)
    generate_downloaded_thumbnail(tmp_path, "albums", 42)
    assert thumbnail_is_current(source, thumbnail_path(tmp_path, "albums", 42, 160))
    assert thumbnail_is_current(source, thumbnail_path(tmp_path, "albums", 42, 640))
    assert not thumbnail_path(tmp_path, "albums", 42, 320).exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize("suffix", ["thumb", "320", "640"])
def test_missing_original_redirects_briefly_without_encoding(tmp_path, monkeypatch, suffix):
    import backend.main as main_module

    monkeypatch.setattr(main_module, "_COVERS_DIR", str(tmp_path))
    with TestClient(app) as client:
        response = client.get(
            f"/covers/albums/42.{suffix}.webp",
            headers={SURFACE_HEADER: PUBLIC_READONLY_SURFACE},
            follow_redirects=False,
        )
    assert response.status_code == 307
    assert response.headers["location"] == "/covers/albums/42.jpg"
    assert response.headers["cache-control"] == "private, max-age=60"
    assert not (tmp_path / "thumbnails").exists()


def test_only_fixed_sizes_have_routes_and_paths(tmp_path):
    with pytest.raises(ValueError, match="unsupported cover size"):
        thumbnail_path(tmp_path, "albums", 42, 256)
    with TestClient(app) as client:
        assert client.get("/covers/albums/42.256.webp").status_code == 404
        assert client.get("/covers/unknown/42.320.webp").status_code == 404

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.core.access_surface import PUBLIC_READONLY_SURFACE, SURFACE_HEADER
from backend.core.job_queue import JobQueue
from backend.main import app
from backend.services.cover_thumbnail_service import ensure_cover_thumbnail, thumbnail_path

pytestmark = pytest.mark.contract


def test_public_variant_reads_never_encode_enqueue_or_mutate_source(
    use_seed_db, tmp_path, monkeypatch
):
    import backend.main as main_module
    import backend.services.cover_thumbnail_service as service

    covers = tmp_path / "covers"
    source = covers / "albums" / "42.jpg"
    source.parent.mkdir(parents=True)
    Image.new("RGB", (800, 600), "purple").save(source)
    ready = thumbnail_path(covers, "albums", 42, 640)
    ensure_cover_thumbnail(source, ready, 640)
    monkeypatch.setattr(main_module, "_COVERS_DIR", str(covers))

    def forbidden(*_args, **_kwargs):
        pytest.fail("public cover read encoded, searched, or queued a cover")

    monkeypatch.setattr(service, "ensure_cover_thumbnail", forbidden)
    monkeypatch.setattr(main_module, "_search_spotify_cover", forbidden)
    monkeypatch.setattr(JobQueue, "enqueue", forbidden)
    monkeypatch.setattr(JobQueue, "enqueue_if_not_pending", forbidden)

    def state():
        with sqlite3.connect(f"file:{use_seed_db}?mode=ro", uri=True) as conn:
            rows = tuple(conn.iterdump())
        files = {
            str(path.relative_to(covers)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in covers.rglob("*")
            if path.is_file()
        }
        return rows, files

    before = state()
    headers = {SURFACE_HEADER: PUBLIC_READONLY_SURFACE}
    client = TestClient(app)
    try:
        for suffix in ("thumb", "320", "640"):
            response = client.get(f"/covers/albums/42.{suffix}.webp", headers=headers)
            assert response.status_code == 200
            assert response.headers["content-type"] == (
                "image/webp" if suffix == "640" else "image/jpeg"
            )
        response = client.get(
            "/covers/artists/999999999.320.webp", headers=headers, follow_redirects=False
        )
        assert response.status_code == 307
    finally:
        client.close()
    assert state() == before
    assert not thumbnail_path(covers, "albums", 42, 320).exists()
    assert Path(use_seed_db).is_file()

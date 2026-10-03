from __future__ import annotations

import pytest
from PIL import Image

from backend.services.cover_thumbnail_service import thumbnail_path
from scripts.backfill_cover_thumbnails import backfill

pytestmark = pytest.mark.unit


def _cover(root, kind, entity_id):
    source = root / kind / f"{entity_id}.jpg"
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 800), "blue").save(source)
    return source


def test_default_backfill_preserves_160_command_and_originals(tmp_path):
    source = _cover(tmp_path, "albums", 42)
    original = source.read_bytes()
    result = backfill(tmp_path)
    assert (result.scanned, result.processed, result.generated, result.failed) == (1, 1, 1, 0)
    assert thumbnail_path(tmp_path, "albums", 42).exists()
    assert not thumbnail_path(tmp_path, "albums", 42, 320).exists()
    assert source.read_bytes() == original
    again = backfill(tmp_path)
    assert (again.scanned, again.processed, again.generated, again.skipped) == (1, 0, 0, 1)


def test_bounded_batches_advance_past_completed_sources(tmp_path):
    _cover(tmp_path, "albums", 1)
    _cover(tmp_path, "albums", 2)
    _cover(tmp_path, "artists", 3)
    sizes = (320, 640)
    for scanned in (1, 2, 3):
        result = backfill(tmp_path, sizes, limit=1)
        assert (result.scanned, result.processed, result.generated, result.failed) == (
            scanned,
            1,
            2,
            0,
        )
        assert result.skipped == (scanned - 1) * 2
    result = backfill(tmp_path, sizes, limit=1)
    assert (result.scanned, result.processed, result.generated, result.skipped) == (3, 0, 0, 6)


def test_backfill_reports_invalid_source_without_losing_other_work(tmp_path, capsys):
    corrupt = _cover(tmp_path, "albums", 1)
    corrupt.write_bytes(b"not an image")
    _cover(tmp_path, "albums", 2)
    result = backfill(tmp_path, (320, 640))
    assert (result.scanned, result.processed, result.generated, result.failed) == (2, 2, 2, 2)
    errors = capsys.readouterr().err
    assert "albums/1.jpg 320px" in errors
    assert "albums/1.jpg 640px" in errors
    assert not thumbnail_path(tmp_path, "albums", 1, 320).exists()


def test_backfill_rejects_unbounded_size_parameters(tmp_path):
    with pytest.raises(ValueError, match="sizes must"):
        backfill(tmp_path, (256,))
    with pytest.raises(ValueError, match="limit must"):
        backfill(tmp_path, limit=0)

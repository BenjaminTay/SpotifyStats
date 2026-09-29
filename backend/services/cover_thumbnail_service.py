"""Small, persisted cover variants for list artwork."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = 160


def thumbnail_path(covers_root: str | Path, cover_type: str, entity_id: int | str) -> Path:
    return Path(covers_root) / "thumbnails" / cover_type / f"{entity_id}.webp"


def thumbnail_is_current(source: str | Path, thumbnail: str | Path) -> bool:
    try:
        source_stat = Path(source).stat()
        thumbnail_stat = Path(thumbnail).stat()
    except FileNotFoundError:
        return False
    return thumbnail_stat.st_size > 0 and thumbnail_stat.st_mtime_ns >= source_stat.st_mtime_ns


def ensure_cover_thumbnail(source: str | Path, thumbnail: str | Path) -> bool:
    """Build a 160px WebP once; return whether a new variant was published."""
    source = Path(source)
    thumbnail = Path(thumbnail)
    if thumbnail_is_current(source, thumbnail):
        return False

    source_stat = source.stat()
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
        thumbnail.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=thumbnail.parent, prefix=f".{thumbnail.stem}.", suffix=".webp", delete=False
        ) as handle:
            temporary = Path(handle.name)
        try:
            image.save(temporary, format="WEBP", quality=78, method=4)
            current_stat = source.stat()
            if (current_stat.st_mtime_ns, current_stat.st_size) != (
                source_stat.st_mtime_ns,
                source_stat.st_size,
            ):
                return False
            os.replace(temporary, thumbnail)
            return True
        finally:
            temporary.unlink(missing_ok=True)


def generate_downloaded_thumbnail(
    covers_root: str | Path, cover_type: str, entity_id: int | str
) -> None:
    """Keep original cover publication successful if thumbnail encoding fails."""
    source = Path(covers_root) / cover_type / f"{entity_id}.jpg"
    try:
        ensure_cover_thumbnail(source, thumbnail_path(covers_root, cover_type, entity_id))
    except Exception as exc:
        logger.warning("Cover thumbnail unavailable for %s/%s: %s", cover_type, entity_id, exc)

"""Persisted cover variants; HTTP reads never encode images."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = 160
COVER_VARIANT_SIZES = (THUMBNAIL_SIZE, 320, 640)


def _validate_size(size: int) -> None:
    if size not in COVER_VARIANT_SIZES:
        raise ValueError(f"unsupported cover size: {size}")


def thumbnail_path(
    covers_root: str | Path, cover_type: str, entity_id: int | str, size: int = THUMBNAIL_SIZE
) -> Path:
    _validate_size(size)
    suffix = "" if size == THUMBNAIL_SIZE else f".{size}"
    return Path(covers_root) / "thumbnails" / cover_type / f"{entity_id}{suffix}.webp"


def thumbnail_is_current(source: str | Path, thumbnail: str | Path) -> bool:
    try:
        source_stat = Path(source).stat()
        thumbnail_stat = Path(thumbnail).stat()
    except FileNotFoundError:
        return False
    return thumbnail_stat.st_size > 0 and thumbnail_stat.st_mtime_ns >= source_stat.st_mtime_ns


def ensure_cover_thumbnail(
    source: str | Path, thumbnail: str | Path, size: int = THUMBNAIL_SIZE
) -> bool:
    """Build a fixed-size WebP without upscaling; report a newly published variant."""
    _validate_size(size)
    source = Path(source)
    thumbnail = Path(thumbnail)
    if thumbnail_is_current(source, thumbnail):
        return False

    source_stat = source.stat()
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        thumbnail.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=thumbnail.parent, prefix=f".{thumbnail.stem}.", suffix=".webp", delete=False
        ) as handle:
            temporary = Path(handle.name)
        try:
            image.save(temporary, format="WEBP", quality=78, method=4)
            current_stat = source.stat()
            if (current_stat.st_mtime_ns, current_stat.st_size, current_stat.st_ino) != (
                source_stat.st_mtime_ns,
                source_stat.st_size,
                source_stat.st_ino,
            ):
                return False
            # Stamp the exact source revision rather than encoding completion.
            # A source replaced after this check remains newer than this file.
            os.utime(temporary, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
            os.replace(temporary, thumbnail)
            return True
        finally:
            temporary.unlink(missing_ok=True)


def generate_downloaded_thumbnail(
    covers_root: str | Path, cover_type: str, entity_id: int | str
) -> None:
    """Publish all fixed sizes; encoding failure cannot fail the original download."""
    source = Path(covers_root) / cover_type / f"{entity_id}.jpg"
    for size in COVER_VARIANT_SIZES:
        try:
            ensure_cover_thumbnail(
                source, thumbnail_path(covers_root, cover_type, entity_id, size), size
            )
        except Exception as exc:
            logger.warning(
                "Cover variant %spx unavailable for %s/%s: %s", size, cover_type, entity_id, exc
            )

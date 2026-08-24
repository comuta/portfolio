"""Image uploads for post/page media (FA-24).

Whitelisted by *content*, not by client-supplied extension or MIME type:
Pillow actually opens and verifies the bytes. SVG is deliberately excluded
— Pillow can't content-validate it (it's XML, not raster) and it can carry
scripts. The filename is always server-generated; the client's filename is
never used for anything but the initial upload multipart field.
"""

from __future__ import annotations

import io
import secrets
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage

_FORMAT_EXTENSIONS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "GIF": "gif",
}


class UploadError(Exception):
    pass


def validate_image(file_storage: FileStorage) -> tuple[bytes, str]:
    """Validate the upload is actually a whitelisted image format; return (data, extension)."""
    data = file_storage.read()
    if not data:
        raise UploadError("Leere Datei.")

    try:
        Image.open(io.BytesIO(data)).verify()
        # verify() consumes/invalidates the parser state; reopen to read .format.
        image = Image.open(io.BytesIO(data))
        fmt = image.format
    except (UnidentifiedImageError, OSError):
        raise UploadError("Datei ist kein gültiges Bild.")

    ext = _FORMAT_EXTENSIONS.get(fmt or "")
    if ext is None:
        raise UploadError(f"Bildformat nicht erlaubt: {fmt}")
    return data, ext


def _resolve_target(target_dir: Path, filename: str) -> Path:
    target_dir = target_dir.resolve()
    target = (target_dir / filename).resolve()
    if not target.is_relative_to(target_dir):
        raise UploadError("Ungültiger Zielpfad.")
    return target


def save_validated_image(file_storage: FileStorage, target_dir: Path) -> str:
    """Validate, save under target_dir with a generated filename, return that filename."""
    data, ext = validate_image(file_storage)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{secrets.token_hex(8)}.{ext}"
    target = _resolve_target(target_dir, filename)
    target.write_bytes(data)
    return filename


def save_validated_image_as(file_storage: FileStorage, target_dir: Path, stem: str) -> str:
    """Validate, save under target_dir as '<stem>.<ext>' — used for the single-slot
    ueber-mich portrait. Any existing '<stem>.*' files are removed first so stale
    files with a different extension don't linger. Returns the filename."""
    data, ext = validate_image(file_storage)
    target_dir.mkdir(parents=True, exist_ok=True)
    for existing in target_dir.glob(f"{stem}.*"):
        existing.unlink()
    filename = f"{stem}.{ext}"
    target = _resolve_target(target_dir, filename)
    target.write_bytes(data)
    return filename

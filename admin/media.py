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


def save_validated_image(file_storage: FileStorage, target_dir: Path) -> str:
    """Validate, save under target_dir with a generated name, return that filename."""
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

    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{secrets.token_hex(8)}.{ext}"
    target = (target_dir / filename).resolve()
    if not target.is_relative_to(target_dir):
        raise UploadError("Ungültiger Zielpfad.")

    target.write_bytes(data)
    return filename

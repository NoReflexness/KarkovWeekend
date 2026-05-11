"""Image upload helpers. Stores under uploads/ and returns a public URL.

Two flavours:
- `save_profile_picture`: no Pillow processing, raw bytes written. Used for
  small avatars where users expect what they upload to be what shows up.
- `save_event_photo`: full Pillow validation, EXIF-based orientation
  normalization, max-dimension downscale, and EXIF DateTimeOriginal
  extraction for chronological gallery sorting. Photos can be large (phones
  shoot 12MP+); we cap at 2560px on the long edge to keep transfers sane
  while still looking good on a 4K screen.
"""

from __future__ import annotations

import io
import secrets
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import ExifTags, Image, UnidentifiedImageError

from app.core.config import get_settings

ALLOWED_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_BYTES = 5 * 1024 * 1024  # 5MB — profile pictures
MAX_PHOTO_BYTES = 25 * 1024 * 1024  # 25MB — modern phone photos
MAX_PHOTO_DIMENSION = 2560
JPEG_QUALITY = 88


def save_profile_picture(file: UploadFile, *, subdir: str) -> str:
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filnavn mangler")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Filtype ikke tilladt")

    contents = file.file.read()
    if len(contents) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Fil er for stor (>5MB)")

    dest_dir: Path = settings.uploads_dir / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}.{ext}"
    (dest_dir / name).write_bytes(contents)
    return f"/uploads/{subdir}/{name}"


class SavedPhoto:
    """Return value of `save_event_photo`."""

    __slots__ = ("url", "taken_at", "width", "height")

    def __init__(
        self,
        *,
        url: str,
        taken_at: datetime | None,
        width: int,
        height: int,
    ) -> None:
        self.url = url
        self.taken_at = taken_at
        self.width = width
        self.height = height


def _extract_taken_at(img: Image.Image) -> datetime | None:
    """Pull DateTimeOriginal from EXIF if present.

    EXIF date strings are local-time-ish without zone info. We treat them as
    UTC for sorting purposes — slightly fictional but consistent and avoids
    needing the photographer's timezone.
    """
    try:
        exif = img.getexif() if hasattr(img, "getexif") else None
    except Exception:
        return None
    if not exif:
        return None
    tag_id = None
    for tid, name in ExifTags.TAGS.items():
        if name == "DateTimeOriginal":
            tag_id = tid
            break
    if tag_id is None:
        return None
    raw = exif.get(tag_id)
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def save_event_photo(file: UploadFile, *, event_id: int) -> SavedPhoto:
    """Validate, normalize and persist a single event photo.

    Returns a `SavedPhoto` carrying the public URL, EXIF taken_at (UTC,
    best-effort), and final pixel dimensions. Raises HTTPException on
    invalid input.
    """
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filnavn mangler")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Filtype ikke tilladt")

    contents = file.file.read()
    if len(contents) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Fil er for stor (>25MB)")

    try:
        img = Image.open(io.BytesIO(contents))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(status_code=400, detail="Ugyldigt billede") from e

    taken_at = _extract_taken_at(img)

    # Honor EXIF orientation so portrait photos taken on phones don't show up
    # sideways. ImageOps.exif_transpose handles the rotate/flip math and strips
    # the orientation tag from the result.
    from PIL import ImageOps  # local import keeps cold-start cheap

    img = ImageOps.exif_transpose(img)

    if max(img.size) > MAX_PHOTO_DIMENSION:
        img.thumbnail((MAX_PHOTO_DIMENSION, MAX_PHOTO_DIMENSION), Image.LANCZOS)

    # Always emit JPEG for jpg/jpeg/heic-ish; preserve PNG/WEBP/GIF. JPEG saves
    # 5-10x vs PNG for photos. GIF is rarely used but we keep it as-is to
    # preserve animation. WEBP gives the best ratio when the client uploads it.
    save_kwargs: dict[str, object] = {}
    if ext in {"jpg", "jpeg"}:
        save_fmt = "JPEG"
        out_ext = "jpg"
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        save_kwargs = {"quality": JPEG_QUALITY, "optimize": True, "progressive": True}
    elif ext == "png":
        save_fmt = "PNG"
        out_ext = "png"
        save_kwargs = {"optimize": True}
    elif ext == "webp":
        save_fmt = "WEBP"
        out_ext = "webp"
        save_kwargs = {"quality": JPEG_QUALITY, "method": 4}
    elif ext == "gif":
        save_fmt = "GIF"
        out_ext = "gif"
    else:  # defensive — `ext` already validated above
        save_fmt = "JPEG"
        out_ext = "jpg"

    subdir = f"events/{event_id}/photos"
    dest_dir: Path = settings.uploads_dir / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}.{out_ext}"
    img.save(dest_dir / name, format=save_fmt, **save_kwargs)

    return SavedPhoto(
        url=f"/uploads/{subdir}/{name}",
        taken_at=taken_at,
        width=img.size[0],
        height=img.size[1],
    )

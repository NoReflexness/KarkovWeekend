"""Profile picture upload helper. Stores under uploads/ and returns a public URL."""

import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import get_settings

ALLOWED_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_BYTES = 5 * 1024 * 1024  # 5MB


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

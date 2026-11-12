from __future__ import annotations

import re
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ..config import DATA_DIR, settings

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".aac"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def user_dir(user_id: str, sub: str) -> Path:
    p = DATA_DIR / "users" / user_id / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:80] or "file"


async def save_upload(file: UploadFile, dest_dir: Path, allowed: set[str]) -> Path:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"نوع الملف غير مدعوم ({ext}). المسموح: {', '.join(sorted(allowed))}")
    dest = dest_dir / f"{secrets.token_hex(6)}_{safe_name(Path(file.filename).stem)}{ext}"
    size = 0
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    with open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"الملف أكبر من {settings.MAX_UPLOAD_MB}MB")
            out.write(chunk)
    return dest

"""All engine settings, read once from environment variables."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE_DIR = Path(os.getenv("ENGINE_CACHE", ROOT / ".cache"))
BIN_DIR = ROOT / ".bin"

SITE_URL = os.getenv("SITE_URL", "https://lioncoaching.github.io/cloning-voice/")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS", "https://lioncoaching.github.io").split(",") if o.strip()]
# Every request must carry this token: the tunnel URL is public, the token keeps strangers out.
TOKEN = os.getenv("ENGINE_TOKEN") or secrets.token_urlsafe(18)

MOCK = os.getenv("ENGINE_MOCK", "0") == "1"  # fake models, for testing the plumbing only
MAX_CHARS = int(os.getenv("MAX_CHARS", "2500"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "80"))

CACHE_DIR.mkdir(parents=True, exist_ok=True)

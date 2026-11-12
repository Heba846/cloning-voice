"""Central settings. Every value can be overridden with an environment variable."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # sawtak-studio/
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", BASE_DIR / "frontend"))


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # Branding
    APP_NAME: str = os.getenv("APP_NAME", "Sawtak Studio")
    APP_NAME_AR: str = os.getenv("APP_NAME_AR", "صوتك ستوديو")
    PUBLIC_URL: str = os.getenv("PUBLIC_URL", "http://localhost:8000")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ACCESS_TOKEN_HOURS: int = int(os.getenv("ACCESS_TOKEN_HOURS", "72"))
    ALLOW_SIGNUP: bool = _bool("ALLOW_SIGNUP", True)
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    WHATSAPP_NUMBER: str = os.getenv("WHATSAPP_NUMBER", "")  # e.g. 2010xxxxxxx (no +)

    # Storage
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'sawtak.db'}")
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "50"))

    # Engines
    TTS_ENGINE: str = os.getenv("TTS_ENGINE", "elevenlabs")  # elevenlabs | cairo | mock
    LIPSYNC_ENGINE: str = os.getenv("LIPSYNC_ENGINE", "mux")  # wav2lip | latentsync | mux
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    # Voice-similarity tuning: lower stability = more expressive, higher similarity = closer timbre
    ELEVENLABS_STABILITY: float = float(os.getenv("ELEVENLABS_STABILITY", "0.5"))
    ELEVENLABS_SIMILARITY: float = float(os.getenv("ELEVENLABS_SIMILARITY", "0.8"))
    ELEVENLABS_STYLE: float = float(os.getenv("ELEVENLABS_STYLE", "0.2"))
    CAIRO_DEVICE: str = os.getenv("CAIRO_DEVICE", "auto")
    WAV2LIP_DIR: str = os.getenv("WAV2LIP_DIR", "")
    WAV2LIP_CHECKPOINT: str = os.getenv("WAV2LIP_CHECKPOINT", "")
    LATENTSYNC_DIR: str = os.getenv("LATENTSYNC_DIR", "")
    FFMPEG_BIN: str = os.getenv("FFMPEG_BIN", "ffmpeg")

    # Credits / pricing. Rule of thumb: 100 credits ≈ 1,000 characters ≈ 1 minute of speech.
    # ElevenLabs costs the operator ≈ $0.20–0.30 per 1,000 chars, so 100 credits must sell for
    # more than ~12 EGP to break even on the hosted engine (local engines cost ~0 per generation).
    CREDITS_PER_1000_CHARS: int = int(os.getenv("CREDITS_PER_1000_CHARS", "100"))
    CREDITS_PER_VIDEO_SECOND: int = int(os.getenv("CREDITS_PER_VIDEO_SECOND", "2"))
    CREDITS_PER_VOICE_CLONE: int = int(os.getenv("CREDITS_PER_VOICE_CLONE", "100"))
    WORKER_THREADS: int = int(os.getenv("WORKER_THREADS", "1"))


settings = Settings()

_PLACEHOLDER_SECRETS = {"", "change-me", "change-me-in-production", "change-me-to-a-long-random-string", "secret"}


def _load_secret_key() -> str:
    """Never run with a guessable JWT key: use SECRET_KEY from the environment, or generate one
    once and keep it in DATA_DIR/secret.key so tokens survive restarts."""
    if settings.SECRET_KEY and settings.SECRET_KEY not in _PLACEHOLDER_SECRETS:
        return settings.SECRET_KEY
    if settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY is a placeholder. Set a random value: openssl rand -hex 32")
    key_file = DATA_DIR / "secret.key"
    if not key_file.exists():
        import secrets
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        key_file.write_text(secrets.token_hex(32))
        key_file.chmod(0o600)
    return key_file.read_text().strip()


settings.SECRET_KEY = _load_secret_key()

# Monthly allowances. Free = one clone + ~1.5 minutes of audio with a watermark (an acquisition
# cost of roughly $0.30 per free user on ElevenLabs). Paid tiers are priced at ~14 EGP per 100
# credits: thin margin on ElevenLabs, ~90% margin once TTS runs on your own GPU (TTS_ENGINE=cairo).
PLANS = {
    "free": {"name": "مجاني", "name_en": "Free", "monthly_credits": 250, "price_egp": 0,
             "max_voices": 1, "max_video_seconds": 15, "watermark": True},
    "creator": {"name": "صانع محتوى", "name_en": "Creator", "monthly_credits": 2500, "price_egp": 349,
                "max_voices": 2, "max_video_seconds": 60, "watermark": False},
    "pro": {"name": "برو", "name_en": "Pro", "monthly_credits": 8000, "price_egp": 999,
            "max_voices": 5, "max_video_seconds": 180, "watermark": False},
    "agency": {"name": "وكالة", "name_en": "Agency", "monthly_credits": 25000, "price_egp": 2999,
               "max_voices": 20, "max_video_seconds": 600, "watermark": False},
}

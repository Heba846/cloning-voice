"""Sawtak Studio API + static frontend. Run: uvicorn app.main:app --reload (from backend/)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import worker
from .config import FRONTEND_DIR, settings
from .db import init_db
from .routers import auth, billing, jobs, voices

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    worker.start()
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan,
              description="Clone your voice, speak any language, render lip-synced reels.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, voices.router, jobs.router, billing.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True, "app": settings.APP_NAME, "tts_engine": settings.TTS_ENGINE,
            "lipsync_engine": settings.LIPSYNC_ENGINE}


@app.get("/api/config")
def public_config():
    return {"app_name": settings.APP_NAME, "app_name_ar": settings.APP_NAME_AR,
            "allow_signup": settings.ALLOW_SIGNUP, "whatsapp": settings.WHATSAPP_NUMBER, "tts_engine": settings.TTS_ENGINE,
            "lipsync_engine": settings.LIPSYNC_ENGINE,
            "pricing": {"credits_per_1000_chars": settings.CREDITS_PER_1000_CHARS,
                        "credits_per_video_second": settings.CREDITS_PER_VIDEO_SECOND,
                        "credits_per_voice_clone": settings.CREDITS_PER_VOICE_CLONE}}


if FRONTEND_DIR.exists():
    @app.get("/app")
    def app_page():
        return FileResponse(FRONTEND_DIR / "app.html")

    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

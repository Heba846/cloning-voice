"""HTTP API the static site calls. Every route except /health needs the X-Engine-Token header."""
from __future__ import annotations

import logging
import secrets
import shutil
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from . import media
from .config import ALLOWED_ORIGINS, MAX_CHARS, MAX_UPLOAD_MB, MOCK, TOKEN
from .engines import lipsync, translate, tts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
app = FastAPI(title="Sawtak Engine", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["X-Engine-Token", "Content-Type"])


@app.middleware("http")
async def allow_private_network(request: Request, call_next):
    """Chrome asks before a public site talks to localhost; this header answers yes."""
    response = await call_next(request)
    if request.headers.get("access-control-request-private-network"):
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


def require_token(x_engine_token: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_engine_token, TOKEN):
        raise HTTPException(401, "رمز المحرك غلط. افتحي لينك التوصيل اللي طلع عند تشغيل المحرك.")


def _workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="sawtak_"))


async def _save(upload: UploadFile, dest: Path) -> Path:
    limit, size = MAX_UPLOAD_MB * 1024 * 1024, 0
    with open(dest, "wb") as f:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise HTTPException(413, f"الملف أكبر من {MAX_UPLOAD_MB}MB")
            f.write(chunk)
    return dest


def _send(path: Path, media_type: str, workdir: Path) -> FileResponse:
    return FileResponse(path, media_type=media_type, filename=path.name,
                        background=BackgroundTask(shutil.rmtree, workdir, ignore_errors=True))


def _fail(e: Exception) -> HTTPException:
    if isinstance(e, HTTPException):
        return e
    if isinstance(e, (LookupError, ValueError)):
        return HTTPException(400, str(e))
    logging.exception("engine error")
    return HTTPException(500, f"خطأ في المحرك: {e}")


@app.get("/health")
def health():
    import importlib.util
    gpu = False
    if importlib.util.find_spec("torch"):
        import torch
        gpu = torch.cuda.is_available()
    return {"ok": True, "mock": MOCK, "gpu": gpu, "tts": tts.status(), "languages": tts.languages(),
            "translate": translate.available(), "lipsync": lipsync.available()}


@app.get("/auth", dependencies=[Depends(require_token)])
def check_auth():
    return {"ok": True}


@app.post("/tts", dependencies=[Depends(require_token)])
async def speak(text: str = Form(...), lang: str = Form("ar-EG"), sample: UploadFile | None = File(None)):
    text = text.strip()
    if not text or len(text) > MAX_CHARS:
        raise HTTPException(400, f"النص لازم يكون بين 1 و {MAX_CHARS} حرف")
    work = _workdir()
    try:
        ref = None
        if sample and sample.filename:
            raw = await _save(sample, work / ("sample" + Path(sample.filename).suffix.lower()))
            ref = media.to_wav(raw, work / "ref.wav")
        out = tts.speak(text, lang, ref, work / "speech.wav")
        return _send(out, "audio/wav", work)
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(work, ignore_errors=True)
        raise _fail(e)


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)
    src: str = "ar-EG"
    tgt: str = "en"


@app.post("/translate", dependencies=[Depends(require_token)])
def do_translate(data: TranslateIn):
    try:
        return {"text": translate.translate(data.text, data.src, data.tgt)}
    except Exception as e:  # noqa: BLE001
        raise _fail(e)


@app.post("/lipsync", dependencies=[Depends(require_token)])
async def do_lipsync(face: UploadFile = File(...), audio: UploadFile = File(...)):
    work = _workdir()
    try:
        face_path = await _save(face, work / ("face" + Path(face.filename or "x.jpg").suffix.lower()))
        audio_raw = await _save(audio, work / ("audio" + Path(audio.filename or "a.wav").suffix.lower()))
        audio_wav = media.to_wav(audio_raw, work / "voice.wav", rate=16000)
        out = lipsync.render(face_path, audio_wav, work / "reel.mp4")
        return _send(out, "video/mp4", work)
    except Exception as e:  # noqa: BLE001
        shutil.rmtree(work, ignore_errors=True)
        raise _fail(e)

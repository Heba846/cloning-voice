from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import worker
from ..auth import current_user
from ..config import settings
from ..db import get_db
from ..engines import get_translator
from ..engines.lipsync import _ffmpeg
from ..models import Job, User, Voice
from ..schemas import JobOut, TranslateIn, TTSIn
from ..services import credits
from ..services.storage import AUDIO_EXT, IMAGE_EXT, VIDEO_EXT, save_upload, user_dir

router = APIRouter(prefix="/api", tags=["jobs"])


def job_out(j: Job) -> JobOut:
    p = json.loads(j.params_json)
    public = {k: v for k, v in p.items() if not k.endswith("_path")}
    return JobOut(id=j.id, kind=j.kind, status=j.status, progress=j.progress, message=j.message,
                  params=public, output_url=f"/api/jobs/{j.id}/download" if j.output_path else None,
                  credits_cost=j.credits_cost, created_at=j.created_at.isoformat())


def _own_voice(db: Session, user: User, voice_id: str) -> Voice:
    v = db.get(Voice, voice_id)
    if not v or v.user_id != user.id:
        raise HTTPException(404, "الصوت غير موجود")
    return v


def _submit(db: Session, user: User, kind: str, params: dict, cost: int) -> JobOut:
    job = Job(user_id=user.id, kind=kind, params_json=json.dumps(params, ensure_ascii=False),
              credits_cost=cost)
    credits.charge(db, user, cost, kind, job.id)  # raises 402 before anything is queued
    db.add(job)
    db.commit()
    worker.enqueue(job.id)
    return job_out(job)


@router.post("/translate")
def translate(data: TranslateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cost = credits.tts_cost(data.text) // 2 or 1
    credits.charge(db, user, cost, "translate")
    try:
        out = get_translator().translate(data.text, data.target, data.source)
    except Exception as e:  # noqa: BLE001
        credits.refund(db, user, cost, "", reason="refund_failed_translate")
        raise HTTPException(502, str(e))
    return {"text": out, "target": data.target, "credits_cost": cost}


@router.post("/tts", response_model=JobOut)
def tts(data: TTSIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _own_voice(db, user, data.voice_id)
    cost = credits.tts_cost(data.text) * (2 if data.translate_to else 1)
    return _submit(db, user, "tts", data.model_dump(), cost)


@router.post("/reels", response_model=JobOut)
async def reel(
    face: UploadFile = File(..., description="صورة أو فيديو لوجهك"),
    voice_id: str = Form(""),
    text: str = Form(""),
    translate_to: str = Form(""),
    source_lang: str = Form("auto"),
    lipsync_engine: str = Form(""),
    audio: UploadFile | None = File(None, description="بديل: ملف صوت جاهز"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    face_path = await save_upload(face, user_dir(user.id, "faces"), IMAGE_EXT | VIDEO_EXT)
    params: dict = {"face_path": str(face_path), "lipsync_engine": lipsync_engine or None,
                    "face_type": "image" if face_path.suffix.lower() in IMAGE_EXT else "video"}
    if audio and audio.filename:
        audio_path = await save_upload(audio, user_dir(user.id, "audio"), AUDIO_EXT)
        params["audio_path"] = str(audio_path)
        cost = credits.video_cost(_ffmpeg.duration(audio_path))
    else:
        if not voice_id or not text.strip():
            raise HTTPException(400, "اختاري صوت واكتبي النص، أو ارفعي ملف صوت جاهز")
        _own_voice(db, user, voice_id)
        params.update({"voice_id": voice_id, "text": text, "translate_to": translate_to or None,
                       "source_lang": source_lang})
        est_seconds = len(text) / 14
        cost = credits.tts_cost(text) * (2 if translate_to else 1) + credits.video_cost(est_seconds)
    return _submit(db, user, "reel", params, cost)


@router.post("/dub", response_model=JobOut)
async def dub(
    media: UploadFile = File(...),
    target_lang: str = Form(...),
    source_lang: str = Form("auto"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    path = await save_upload(media, user_dir(user.id, "dub_in"), AUDIO_EXT | VIDEO_EXT)
    cost = credits.video_cost(_ffmpeg.duration(path)) * 3
    return _submit(db, user, "dub", {"media_path": str(path), "target_lang": target_lang,
                                     "source_lang": source_lang}, cost)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(100)
    return [job_out(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j or j.user_id != user.id:
        raise HTTPException(404, "غير موجود")
    return job_out(j)


@router.get("/jobs/{job_id}/download")
def download(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j or j.user_id != user.id or not j.output_path or not Path(j.output_path).exists():
        raise HTTPException(404, "الملف غير جاهز")
    p = Path(j.output_path)
    return FileResponse(p, filename=f"{settings.APP_NAME.replace(' ', '_')}_{j.id}{p.suffix}")


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j or j.user_id != user.id:
        raise HTTPException(404, "غير موجود")
    if j.output_path:
        Path(j.output_path).unlink(missing_ok=True)
    db.delete(j)
    db.commit()
    return {"ok": True}

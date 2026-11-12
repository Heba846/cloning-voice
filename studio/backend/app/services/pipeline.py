"""The actual work behind each job kind. Runs inside the worker thread with its own DB session.
Every step reports progress so the UI can show a live bar."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import settings
from ..engines import get_lipsync, get_translator, get_tts
from ..engines.lipsync import _ffmpeg
from ..models import Job, Voice
from . import credits
from .storage import user_dir


def _progress(job: Job, db, base: float, span: float):
    def cb(frac: float):
        job.progress = round(base + span * max(0.0, min(1.0, frac)), 3)
        db.commit()
    return cb


def _resolve_text(job: Job, p: dict, db) -> str:
    """Optional translation step shared by tts and reel jobs."""
    text = p["text"]
    target = p.get("translate_to")
    if target and target != p.get("source_lang", "auto"):
        job.message = f"جاري ترجمة النص إلى {target}…"
        db.commit()
        text = get_translator().translate(text, target, p.get("source_lang", "auto"))
        p["translated_text"] = text
        job.params_json = json.dumps(p, ensure_ascii=False)
        db.commit()
    return text


def run_tts(job: Job, db) -> Path:
    p = json.loads(job.params_json)
    voice = db.get(Voice, p["voice_id"])
    if not voice:
        raise RuntimeError("الصوت غير موجود")
    text = _resolve_text(job, p, db)
    job.message = "جاري توليد الصوت بصوتك…"
    db.commit()
    out = user_dir(job.user_id, "audio") / f"{job.id}.mp3"
    lang = p.get("translate_to") or voice.language
    return get_tts(voice.engine).speak(text, voice.engine_ref, out, language=lang,
                                       progress=_progress(job, db, 0.3, 0.7))


def run_reel(job: Job, db) -> Path:
    p = json.loads(job.params_json)
    face = Path(p["face_path"])
    if p.get("audio_path"):
        audio = Path(p["audio_path"])
        job.progress = 0.3
    else:
        voice = db.get(Voice, p["voice_id"])
        if not voice:
            raise RuntimeError("الصوت غير موجود")
        text = _resolve_text(job, p, db)
        job.message = "1/2 توليد الصوت…"
        db.commit()
        audio = user_dir(job.user_id, "audio") / f"{job.id}.mp3"
        lang = p.get("translate_to") or voice.language
        audio = get_tts(voice.engine).speak(text, voice.engine_ref, audio, language=lang,
                                            progress=_progress(job, db, 0.1, 0.3))
    secs = _ffmpeg.duration(audio)
    plan = credits.plan_of(job.owner)
    if secs > plan["max_video_seconds"]:
        raise RuntimeError(f"مدة الفيديو {secs:.0f} ثانية أطول من حد باقتك ({plan['max_video_seconds']} ث)")
    job.message = "2/2 مزامنة الشفاه وتجميع الفيديو…"
    db.commit()
    out = user_dir(job.user_id, "video") / f"{job.id}.mp4"
    engine = get_lipsync(p.get("lipsync_engine") or settings.LIPSYNC_ENGINE)
    engine.render(face, audio, out, progress=_progress(job, db, 0.4, 0.55))
    if plan.get("watermark"):
        wm = out.with_name(out.stem + "_wm.mp4")
        _ffmpeg.add_watermark(out, wm, settings.APP_NAME)
        out = wm
    return out


def run_dub(job: Job, db) -> Path:
    p = json.loads(job.params_json)
    tts = get_tts("elevenlabs")
    job.message = "جاري دبلجة الفيديو بنفس صوتك…"
    db.commit()
    out = user_dir(job.user_id, "video") / f"{job.id}"
    return tts.dub(Path(p["media_path"]), p["target_lang"], p.get("source_lang", "auto"),
                   out_path=out, progress=_progress(job, db, 0.05, 0.95))


RUNNERS = {"tts": run_tts, "reel": run_reel, "dub": run_dub}

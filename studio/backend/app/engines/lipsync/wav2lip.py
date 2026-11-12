"""Open-source lip-sync (Wav2Lip). Needs a clone of github.com/Rudrabha/Wav2Lip at WAV2LIP_DIR
with its checkpoint (wav2lip_gan.pth) at WAV2LIP_CHECKPOINT. Works on CPU (slow) or GPU.
Accepts an image or a video as the face source."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ...config import settings
from . import _ffmpeg
from .base import LipsyncEngine


class Wav2LipEngine(LipsyncEngine):
    name = "wav2lip"

    def render(self, face_path: Path, audio_path: Path, out_path: Path, progress=None) -> Path:
        if not settings.WAV2LIP_DIR or not settings.WAV2LIP_CHECKPOINT:
            raise RuntimeError("Wav2Lip غير مُعد: حدد WAV2LIP_DIR و WAV2LIP_CHECKPOINT في .env")
        wav = audio_path.with_suffix(".16k.wav")
        _ffmpeg.run(["-i", str(audio_path), "-ac", "1", "-ar", "16000", str(wav)])
        cmd = [sys.executable, "inference.py", "--checkpoint_path", settings.WAV2LIP_CHECKPOINT,
               "--face", str(face_path), "--audio", str(wav), "--outfile", str(out_path),
               "--pads", "0", "10", "0", "0", "--resize_factor", "1"]
        if progress:
            progress(0.1)
        p = subprocess.run(cmd, cwd=settings.WAV2LIP_DIR, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Wav2Lip failed: {p.stderr[-500:]}")
        if progress:
            progress(1.0)
        return out_path

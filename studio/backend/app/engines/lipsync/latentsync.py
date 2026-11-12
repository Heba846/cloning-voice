"""Open-source lip-sync (ByteDance LatentSync, Apache-2.0). Higher quality than Wav2Lip,
needs an NVIDIA GPU (~8 GB VRAM) and a clone of github.com/bytedance/LatentSync at
LATENTSYNC_DIR with its checkpoints downloaded. Face source must be a video."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ...config import settings
from . import _ffmpeg
from .base import LipsyncEngine


class LatentSyncEngine(LipsyncEngine):
    name = "latentsync"

    def render(self, face_path: Path, audio_path: Path, out_path: Path, progress=None) -> Path:
        if not settings.LATENTSYNC_DIR:
            raise RuntimeError("LatentSync غير مُعد: حدد LATENTSYNC_DIR في .env")
        if face_path.suffix.lower() in _ffmpeg.IMAGE_EXT:
            face_video = face_path.with_suffix(".face.mp4")
            _ffmpeg.image_to_video(face_path, audio_path, face_video, size="720x1280")
            face_path = face_video
        cmd = [sys.executable, "-m", "scripts.inference",
               "--unet_config_path", "configs/unet/stage2.yaml",
               "--inference_ckpt_path", "checkpoints/latentsync_unet.pt",
               "--video_path", str(face_path), "--audio_path", str(audio_path),
               "--video_out_path", str(out_path), "--inference_steps", "20", "--guidance_scale", "1.5"]
        if progress:
            progress(0.1)
        p = subprocess.run(cmd, cwd=settings.LATENTSYNC_DIR, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"LatentSync failed: {p.stderr[-500:]}")
        if progress:
            progress(1.0)
        return out_path

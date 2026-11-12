"""Fallback engine with zero ML dependencies: puts the cloned-voice audio on a still image
(Ken Burns reel) or replaces the audio track of an existing video. No lip movement, but it
guarantees the product always delivers a video; upgrade to wav2lip/latentsync for real sync."""
from __future__ import annotations

from pathlib import Path

from . import _ffmpeg
from .base import LipsyncEngine


class MuxEngine(LipsyncEngine):
    name = "mux"

    def render(self, face_path: Path, audio_path: Path, out_path: Path, progress=None) -> Path:
        if face_path.suffix.lower() in _ffmpeg.IMAGE_EXT:
            _ffmpeg.image_to_video(face_path, audio_path, out_path)
        else:
            _ffmpeg.replace_audio(face_path, audio_path, out_path)
        if progress:
            progress(1.0)
        return out_path

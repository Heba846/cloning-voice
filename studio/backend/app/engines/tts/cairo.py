"""Local, free engine for Egyptian Arabic: Cairo-TTS (pip install cairo-tts).
Zero-shot cloning: the voice reference *is* the sample file, no training step."""
from __future__ import annotations

import shutil
from pathlib import Path

from ...config import DATA_DIR, settings
from .base import TTSEngine


class CairoTTS(TTSEngine):
    name = "cairo"

    def __init__(self) -> None:
        self._tts = None

    def _model(self):
        if self._tts is None:
            try:
                from cairo_tts import CairoTTS as _Cairo  # type: ignore
            except ImportError as e:
                raise RuntimeError("cairo-tts غير مثبت: pip install cairo-tts") from e
            kwargs = {} if settings.CAIRO_DEVICE == "auto" else {"device": settings.CAIRO_DEVICE}
            self._tts = _Cairo(**kwargs)
        return self._tts

    def clone(self, sample_path: Path, name: str, description: str = "") -> str:
        dest = DATA_DIR / "voice_refs" / f"{sample_path.stem}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if sample_path.suffix.lower() == ".wav":
            shutil.copy(sample_path, dest)
        else:
            import subprocess
            subprocess.run([settings.FFMPEG_BIN, "-y", "-i", str(sample_path), "-ac", "1",
                            "-ar", "24000", str(dest)], check=True, capture_output=True)
        return str(dest)

    def speak(self, text: str, voice_ref: str, out_path: Path, language: str = "ar",
              progress=None) -> Path:
        out_path = out_path.with_suffix(".wav")
        self._model().save(text, str(out_path), voice=voice_ref)
        if progress:
            progress(1.0)
        return out_path

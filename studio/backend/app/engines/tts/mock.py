"""Development engine: produces a silent-ish tone WAV with a realistic duration so the whole
pipeline (jobs, credits, lip-sync, UI) can be exercised without any API key or GPU."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from .base import TTSEngine


class MockTTS(TTSEngine):
    name = "mock"

    def clone(self, sample_path: Path, name: str, description: str = "") -> str:
        return f"mock:{sample_path.name}"

    def speak(self, text: str, voice_ref: str, out_path: Path, language: str = "ar",
              progress=None) -> Path:
        seconds = max(1.0, len(text) / 14)  # ~14 chars per second of speech
        rate = 22050
        out_path = out_path.with_suffix(".wav")
        with wave.open(str(out_path), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            frames = bytearray()
            for i in range(int(seconds * rate)):
                env = 0.5 + 0.5 * math.sin(i / rate * 6)  # syllable-like amplitude envelope
                v = int(6000 * env * math.sin(2 * math.pi * 180 * i / rate))
                frames += struct.pack("<h", v)
            w.writeframes(bytes(frames))
        if progress:
            progress(1.0)
        return out_path

"""Voice cloning TTS.

- Cairo-TTS: Egyptian Arabic (natural colloquial) and English. Priority languages, CPU friendly.
- Chatterbox Multilingual (optional extra): 23 languages, same cloned voice.
Both are zero-shot: the reference sample *is* the voice, no training step."""
from __future__ import annotations

import math
import struct
import threading
import wave
from pathlib import Path

from ..config import MOCK

CAIRO_LANGS = {"ar-EG", "en"}
CHATTERBOX_LANGS = {"ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja", "ko",
                    "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh"}

_lock = threading.Lock()
_models: dict[str, object] = {}


def _cairo():
    if "cairo" not in _models:
        from cairo_tts import CairoTTS
        _models["cairo"] = CairoTTS.from_pretrained()
    return _models["cairo"]


def _chatterbox():
    if "chatterbox" not in _models:
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _models["chatterbox"] = ChatterboxMultilingualTTS.from_pretrained(device=device)
    return _models["chatterbox"]


def _installed(module: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(module) is not None


def status() -> dict:
    return {"cairo": MOCK or _installed("cairo_tts"), "chatterbox": MOCK or _installed("chatterbox")}


def languages() -> list[str]:
    s = status()
    langs = set(CAIRO_LANGS if s["cairo"] else ())
    if s["chatterbox"]:
        langs |= CHATTERBOX_LANGS
    return sorted(langs)


def speak(text: str, lang: str, sample_wav: Path | None, out: Path) -> Path:
    if lang not in languages():
        raise LookupError(f"اللغة {lang} مش متاحة على المحرك ده. المتاح: {', '.join(languages())}")
    if MOCK:
        return _mock(text, out)
    with _lock:  # one generation at a time: the GPU/CPU is shared
        if lang in CAIRO_LANGS and status()["cairo"]:
            _cairo().save(text, str(out), voice=str(sample_wav) if sample_wav else None)
            return out
        if lang in CHATTERBOX_LANGS and status()["chatterbox"]:
            import torchaudio
            model = _chatterbox()
            wav = model.generate(text, language_id=lang.split("-")[0],
                                 audio_prompt_path=str(sample_wav) if sample_wav else None)
            torchaudio.save(str(out), wav, model.sr)
            return out
    raise LookupError(f"اللغة {lang} مش متاحة")


def _mock(text: str, out: Path) -> Path:
    rate, seconds = 22050, max(1.0, len(text) / 14)
    with wave.open(str(out), "w") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(b"".join(
            struct.pack("<h", int(5000 * (0.5 + 0.5 * math.sin(i / rate * 6)) * math.sin(2 * math.pi * 190 * i / rate)))
            for i in range(int(seconds * rate))))
    return out

"""Voice cloning TTS. Each language tries the installed engines in order; one that fails to load
(e.g. its weights are gone from the Hub) is skipped from then on.

- OmniVoice (VoiceTut-TTS weights): Egyptian Arabic with English code-switching, and English. Preferred.
- Cairo-TTS: Egyptian Arabic and English, CPU friendly. Hub weights were private as of 2026-11.
- Chatterbox Multilingual (optional extra): 23 languages; `ar-EG` falls back to its (MSA) `ar`.
All are zero-shot: the reference sample *is* the voice, no training step."""
from __future__ import annotations

import logging
import math
import os
import struct
import threading
import wave
from pathlib import Path

from .. import media
from ..config import MOCK

log = logging.getLogger("engine.tts")
CAIRO_LANGS = {"ar-EG", "en"}
OMNI_LANGS = {"ar-EG": "arz", "en": "en"}
CHATTERBOX_LANGS = {"ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja", "ko",
                    "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh"}
MODULES = {"omnivoice": "omnivoice", "cairo": "cairo_tts", "chatterbox": "chatterbox"}

_lock = threading.Lock()
_models: dict[str, object] = {}
_broken: dict[str, str] = {}  # engine -> load error, so a dead engine is not retried on every request
_ref_texts: dict[str, str] = {}  # sample hash -> transcript, so OmniVoice transcribes a voice sample only once
OMNI_REF_SECONDS = 10  # OmniVoice clones best from a 3-10 s reference; longer ones degrade quality


def _device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _omnivoice():
    import torch
    from omnivoice import OmniVoice
    device = _device()
    # Whisper transcribes the voice sample once; the small model keeps that bearable on CPU.
    asr = os.getenv("OMNIVOICE_ASR", "openai/whisper-large-v3-turbo" if device == "cuda" else "openai/whisper-small")
    return OmniVoice.from_pretrained(os.getenv("OMNIVOICE_MODEL", "mohammedaly22/VoiceTut-TTS"), device_map=device,
                                     dtype=torch.float16 if device == "cuda" else torch.float32, asr_model_name=asr)


def _omni_reference(model, ref: str) -> tuple[str, str]:
    """Trim the sample to the length OmniVoice likes and transcribe it once per distinct sample."""
    import hashlib
    trimmed = str(Path(ref).with_name("ref_short.wav"))
    media.run("-i", ref, "-t", str(OMNI_REF_SECONDS), "-ac", "1", trimmed)
    key = hashlib.sha256(Path(trimmed).read_bytes()).hexdigest()
    if key not in _ref_texts:
        if model._asr_pipe is None:
            model.load_asr_model()
        _ref_texts[key] = model.transcribe(trimmed)
    return trimmed, _ref_texts[key]


def _cairo():
    from cairo_tts import CairoTTS
    # The default repo (mohammedaly22/Cairo-TTS) was not public as of 2026-11: point this at a local
    # copy of the weights (folder with config.yaml + *.safetensors) or another Hub repo id.
    return CairoTTS.from_pretrained(os.getenv("CAIRO_TTS_MODEL", "mohammedaly22/Cairo-TTS"))


def _chatterbox():
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    return ChatterboxMultilingualTTS.from_pretrained(device=_device())


LOADERS = {"omnivoice": _omnivoice, "cairo": _cairo, "chatterbox": _chatterbox}


def _installed(module: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(module) is not None


def status() -> dict:
    return {name: MOCK or (_installed(mod) and name not in _broken) for name, mod in MODULES.items()}


def _chain(lang: str) -> list[str]:
    """Engines that can speak `lang`, best first."""
    order = []
    if lang in OMNI_LANGS:
        order.append("omnivoice")
    if lang in CAIRO_LANGS:
        order.append("cairo")
    if lang in CHATTERBOX_LANGS or lang == "ar-EG":
        order.append("chatterbox")
    s = status()
    return [e for e in order if s[e]]


def languages() -> list[str]:
    return sorted(lang for lang in set(OMNI_LANGS) | CAIRO_LANGS | CHATTERBOX_LANGS if _chain(lang))


def _load(engine: str):
    if engine not in _models:
        _models[engine] = LOADERS[engine]()
    return _models[engine]


def _generate(engine: str, model, text: str, lang: str, ref: str | None, out: Path) -> None:
    if engine == "omnivoice":
        import soundfile as sf
        ref_text = None
        if ref:
            ref, ref_text = _omni_reference(model, ref)
        audio = model.generate(text=text, language=OMNI_LANGS[lang], ref_audio=ref, ref_text=ref_text)
        sf.write(str(out), audio[0], model.sampling_rate)
    elif engine == "cairo":
        model.save(text, str(out), voice=ref)
    else:
        import torchaudio
        wav = model.generate(text, language_id="ar" if lang == "ar-EG" else lang.split("-")[0],
                             audio_prompt_path=ref)
        torchaudio.save(str(out), wav, model.sr)


def speak(text: str, lang: str, sample_wav: Path | None, out: Path) -> Path:
    if lang not in languages():
        raise LookupError(f"اللغة {lang} مش متاحة على المحرك ده. المتاح: {', '.join(languages())}")
    if MOCK:
        return _mock(text, out)
    ref = str(sample_wav) if sample_wav else None
    with _lock:  # one generation at a time: the GPU/CPU is shared
        for engine in _chain(lang):
            try:
                model = _load(engine)
            except Exception as e:  # noqa: BLE001  e.g. weights removed from the Hub: try the next engine
                log.warning("TTS engine %s unavailable: %s", engine, e)
                _broken[engine] = str(e)
                continue
            _generate(engine, model, text, lang, ref, out)
            log.info("tts %s via %s", lang, engine)
            return out
    raise LookupError(f"اللغة {lang} مش متاحة: {'; '.join(f'{k}: {v[:120]}' for k, v in _broken.items())}")


def _mock(text: str, out: Path) -> Path:
    rate, seconds = 22050, max(1.0, len(text) / 14)
    with wave.open(str(out), "w") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(b"".join(
            struct.pack("<h", int(5000 * (0.5 + 0.5 * math.sin(i / rate * 6)) * math.sin(2 * math.pi * 190 * i / rate)))
            for i in range(int(seconds * rate))))
    return out

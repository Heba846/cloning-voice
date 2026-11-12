"""Engine registry: every heavy capability (TTS, lip-sync, translation, dubbing) is a plugin
behind a small interface, so the product can swap hosted APIs for local open-source models
without touching the API or the frontend."""
from __future__ import annotations

from ..config import settings


def get_tts(name: str | None = None):
    name = (name or settings.TTS_ENGINE).lower()
    if name == "elevenlabs":
        from .tts.elevenlabs import ElevenLabsTTS
        return ElevenLabsTTS()
    if name == "cairo":
        from .tts.cairo import CairoTTS
        return CairoTTS()
    if name == "mock":
        from .tts.mock import MockTTS
        return MockTTS()
    raise ValueError(f"Unknown TTS engine: {name}")


def get_lipsync(name: str | None = None):
    name = (name or settings.LIPSYNC_ENGINE).lower()
    if name == "wav2lip":
        from .lipsync.wav2lip import Wav2LipEngine
        return Wav2LipEngine()
    if name == "latentsync":
        from .lipsync.latentsync import LatentSyncEngine
        return LatentSyncEngine()
    if name == "mux":
        from .lipsync.mux import MuxEngine
        return MuxEngine()
    raise ValueError(f"Unknown lipsync engine: {name}")


def get_translator():
    from .translate import ClaudeTranslator
    return ClaudeTranslator()


LANGUAGES = {
    "ar": "Arabic", "ar-EG": "Egyptian Arabic", "en": "English", "fr": "French", "de": "German",
    "es": "Spanish", "it": "Italian", "pt": "Portuguese", "tr": "Turkish", "ru": "Russian",
    "hi": "Hindi", "ur": "Urdu", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "id": "Indonesian",
    "nl": "Dutch", "pl": "Polish", "sv": "Swedish", "fil": "Filipino", "ms": "Malay", "ta": "Tamil",
}

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TTSEngine(ABC):
    name: str = "base"
    supports_clone: bool = True

    @abstractmethod
    def clone(self, sample_path: Path, name: str, description: str = "") -> str:
        """Register a voice from a short clean sample. Returns an engine-specific reference."""

    @abstractmethod
    def speak(self, text: str, voice_ref: str, out_path: Path, language: str = "ar",
              progress=None) -> Path:
        """Synthesize `text` with the cloned voice into out_path (wav/mp3)."""

    def delete_voice(self, voice_ref: str) -> None:  # optional
        return None

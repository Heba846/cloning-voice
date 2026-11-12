from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class LipsyncEngine(ABC):
    name: str = "base"

    @abstractmethod
    def render(self, face_path: Path, audio_path: Path, out_path: Path, progress=None) -> Path:
        """face_path is an image (jpg/png) or a video (mp4). Returns the final mp4 path."""

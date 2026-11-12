"""ffmpeg helpers. ffmpeg comes from the system PATH or from the imageio-ffmpeg wheel."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .config import BIN_DIR

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def ensure_ffmpeg() -> str:
    """Return an ffmpeg executable, exposing the bundled one as `ffmpeg` on PATH if needed
    (Wav2Lip shells out to plain `ffmpeg`)."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    target = BIN_DIR / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not target.exists():
        shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(), target)
        target.chmod(0o755)
    os.environ["PATH"] = f"{BIN_DIR}{os.pathsep}{os.environ['PATH']}"
    return str(target)


def run(*args: str) -> None:
    p = subprocess.run([ensure_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg: {p.stderr.strip()[-400:]}")


def to_wav(src: Path, dst: Path, rate: int = 24000) -> Path:
    """Any audio/video file (webm, m4a, mp3, mp4…) -> mono PCM wav."""
    run("-i", str(src), "-vn", "-ac", "1", "-ar", str(rate), str(dst))
    return dst


def to_png(src: Path, dst: Path) -> Path:
    run("-i", str(src), "-frames:v", "1", str(dst))
    return dst


def wav_seconds(path: Path) -> float:
    import wave

    with wave.open(str(path)) as w:
        return w.getnframes() / float(w.getframerate())


def still_video(image: Path, audio: Path, out: Path) -> Path:
    """Image + audio -> mp4 without lip movement (used by mock mode)."""
    run("-loop", "1", "-i", str(image), "-i", str(audio), "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-shortest", str(out))
    return out

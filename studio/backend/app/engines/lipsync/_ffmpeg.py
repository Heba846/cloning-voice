from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ...config import settings

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def run(args: list[str]) -> None:
    p = subprocess.run([settings.FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {p.stderr[-400:]}")


def duration(path: Path) -> float:
    p = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
                       capture_output=True, text=True)
    try:
        return float(json.loads(p.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def image_to_video(image: Path, audio: Path, out: Path, size: str = "1080x1920") -> Path:
    """Still image + audio -> vertical reel with a slow Ken Burns zoom (always works, no GPU)."""
    secs = max(1.0, duration(audio))
    w, h = size.split("x")
    vf = (f"scale={int(w)*2}:{int(h)*2}:force_original_aspect_ratio=increase,"
          f"crop={int(w)*2}:{int(h)*2},zoompan=z='min(zoom+0.0008,1.15)':d={int(secs*25)+25}"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps=25,format=yuv420p")
    run(["-loop", "1", "-i", str(image), "-i", str(audio), "-vf", vf, "-t", f"{secs:.2f}",
         "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k", "-shortest",
         str(out)])
    return out


def replace_audio(video: Path, audio: Path, out: Path) -> Path:
    run(["-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)])
    return out


def add_watermark(video: Path, out: Path, text: str) -> Path:
    run(["-i", str(video), "-vf",
         f"drawtext=text='{text}':fontcolor=white@0.6:fontsize=36:x=w-tw-30:y=h-th-40:"
         f"box=1:boxcolor=black@0.3:boxborderw=10", "-c:a", "copy", str(out)])
    return out

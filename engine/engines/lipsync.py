"""Lip-sync with the open-source Wav2Lip (GAN checkpoint).

First use clones the Wav2Lip repo, patches it for current numpy/librosa/torch, and downloads the
model checkpoint and face detector. Override the download sources with WAV2LIP_CKPT / S3FD_CKPT
(local path or URL) if a mirror disappears."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path

from .. import media
from ..config import MOCK, ROOT

log = logging.getLogger("engine.lipsync")
REPO = ROOT / "Wav2Lip"
REPO_ZIP = "https://github.com/Rudrabha/Wav2Lip/archive/refs/heads/master.zip"
CKPT = REPO / "checkpoints" / "wav2lip_gan.pth"
S3FD = REPO / "face_detection" / "detection" / "sfd" / "s3fd.pth"

# (huggingface repo, file) mirrors tried in order, then plain URLs.
CKPT_SOURCES = [("camenduru/Wav2Lip", "checkpoints/wav2lip_gan.pth"), ("Nekochu/Wav2Lip", "wav2lip_gan.pth"),
                ("numz/wav2lip_studio", "Wav2lip/wav2lip_gan.pth")]
S3FD_SOURCES = [("camenduru/Wav2Lip", "face_detection/detection/sfd/s3fd.pth"), ("Nekochu/Wav2Lip", "s3fd.pth"),
                "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"]

_lock = threading.Lock()


def available() -> bool:
    import importlib.util
    return MOCK or all(importlib.util.find_spec(m) for m in ("cv2", "librosa", "torch"))


def _fetch(dest: Path, env_var: str, sources: list) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    override = os.getenv(env_var)
    for src in ([override] if override else []) + sources:
        try:
            if isinstance(src, tuple):
                from huggingface_hub import hf_hub_download
                shutil.copy(hf_hub_download(*src), dest)
            elif Path(src).exists():
                shutil.copy(src, dest)
            else:
                urllib.request.urlretrieve(src, dest)
            log.info("downloaded %s from %s", dest.name, src)
            return
        except Exception as e:  # noqa: BLE001  try the next mirror
            log.warning("could not get %s from %s: %s", dest.name, src, e)
    raise RuntimeError(f"تعذر تحميل {dest.name}. حطي رابط/مسار في {env_var}")


def _patch_repo() -> None:
    """Make the 2020 Wav2Lip code run on current libraries."""
    audio = REPO / "audio.py"
    audio.write_text(audio.read_text().replace(
        "librosa.filters.mel(hp.sample_rate, hp.n_fft,", "librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft,"))
    inf = REPO / "inference.py"
    inf.write_text(re.sub(r"args\.face\.split\('\.'\)\[1\]", "args.face.rsplit('.', 1)[-1].lower()", inf.read_text()))
    (REPO / "temp").mkdir(exist_ok=True)


def setup() -> None:
    if not REPO.exists():  # zip download: works on Windows without git
        archive = ROOT / "wav2lip.zip"
        urllib.request.urlretrieve(REPO_ZIP, archive)
        with zipfile.ZipFile(archive) as z:
            z.extractall(ROOT)
        (ROOT / "Wav2Lip-master").rename(REPO)
        archive.unlink()
        _patch_repo()
    _fetch(CKPT, "WAV2LIP_CKPT", CKPT_SOURCES)
    _fetch(S3FD, "S3FD_CKPT", S3FD_SOURCES)


def render(face: Path, audio_wav: Path, out: Path) -> Path:
    if face.suffix.lower() in media.IMAGE_EXT and face.suffix.lower() != ".png":
        face = media.to_png(face, face.with_suffix(".png"))
    if MOCK:
        return media.still_video(face, audio_wav, out) if face.suffix == ".png" else _mux(face, audio_wav, out)
    with _lock:
        setup()
        media.ensure_ffmpeg()
        is_image = face.suffix.lower() == ".png"
        cmd = [sys.executable, "inference.py", "--checkpoint_path", str(CKPT), "--face", str(face),
               "--audio", str(audio_wav), "--outfile", str(out), "--pads", "0", "15", "0", "0",
               "--resize_factor", "1" if is_image else "2", "--nosmooth"]
        env = {**os.environ, "TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD": "1"}
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
        if p.returncode != 0 or not out.exists():
            tail = (p.stderr or p.stdout)[-700:]
            if "Face not detected" in tail:
                raise ValueError("مش لاقي وش في الصورة/الفيديو. استخدمي صورة واضحة ومواجهة للكاميرا.")
            raise RuntimeError(f"Wav2Lip: {tail}")
    return out


def _mux(video: Path, audio: Path, out: Path) -> Path:
    media.run("-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
              "-preset", "veryfast", "-c:a", "aac", "-shortest", str(out))
    return out

"""Hosted engine: ElevenLabs instant voice cloning + multilingual TTS (29+ languages).
Best quality today; needs ELEVENLABS_API_KEY and a plan that allows cloning."""
from __future__ import annotations

from pathlib import Path

import httpx

from ...config import settings
from .base import TTSEngine

API = "https://api.elevenlabs.io/v1"


class ElevenLabsTTS(TTSEngine):
    name = "elevenlabs"

    def __init__(self) -> None:
        self.headers = {"xi-api-key": settings.ELEVENLABS_API_KEY or "proxy-injected"}
        self.client = httpx.Client(timeout=120)

    def clone(self, sample_path: Path, name: str, description: str = "") -> str:
        with open(sample_path, "rb") as f:
            files = {"files": (sample_path.name, f, "audio/mpeg")}
            data = {"name": name, "description": description or "Created with Sawtak Studio",
                    "remove_background_noise": "true"}
            r = self.client.post(f"{API}/voices/add", headers=self.headers, data=data, files=files)
        if r.status_code >= 400:
            raise RuntimeError(f"ElevenLabs clone failed ({r.status_code}): {r.text[:300]}")
        return r.json()["voice_id"]

    def speak(self, text: str, voice_ref: str, out_path: Path, language: str = "ar",
              progress=None) -> Path:
        body = {
            "text": text,
            "model_id": settings.ELEVENLABS_MODEL,
            "voice_settings": {"stability": settings.ELEVENLABS_STABILITY,
                               "similarity_boost": settings.ELEVENLABS_SIMILARITY,
                               "style": settings.ELEVENLABS_STYLE,
                               "use_speaker_boost": "v3" not in settings.ELEVENLABS_MODEL},
        }
        # multilingual_v2 auto-detects the language; flash/turbo accept an explicit hint
        if "flash" in settings.ELEVENLABS_MODEL or "turbo" in settings.ELEVENLABS_MODEL:
            body["language_code"] = language.split("-")[0]
        r = self.client.post(f"{API}/text-to-speech/{voice_ref}?output_format=mp3_44100_128",
                             headers=self.headers, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"ElevenLabs TTS failed ({r.status_code}): {r.text[:300]}")
        out_path = out_path.with_suffix(".mp3")
        out_path.write_bytes(r.content)
        if progress:
            progress(1.0)
        return out_path

    def delete_voice(self, voice_ref: str) -> None:
        self.client.delete(f"{API}/voices/{voice_ref}", headers=self.headers)

    # --- Dubbing: audio/video in one language -> same voice in another language -------
    def dub(self, media_path: Path, target_lang: str, source_lang: str = "auto",
            out_path: Path | None = None, progress=None) -> Path:
        import time

        with open(media_path, "rb") as f:
            files = {"file": (media_path.name, f)}
            data = {"target_lang": target_lang.split("-")[0], "source_lang": source_lang,
                    "watermark": "false"}
            r = self.client.post(f"{API}/dubbing", headers=self.headers, data=data, files=files)
        if r.status_code >= 400:
            raise RuntimeError(f"ElevenLabs dubbing failed ({r.status_code}): {r.text[:300]}")
        dub_id = r.json()["dubbing_id"]
        for _ in range(360):  # up to 30 minutes
            time.sleep(5)
            s = self.client.get(f"{API}/dubbing/{dub_id}", headers=self.headers).json()
            if progress:
                progress(0.1 + 0.8 * min(1.0, _ / 60))
            if s.get("status") == "dubbed":
                break
            if s.get("status") == "failed":
                raise RuntimeError(f"Dubbing failed: {s.get('error', '')}")
        else:
            raise RuntimeError("Dubbing timed out")
        r = self.client.get(f"{API}/dubbing/{dub_id}/audio/{target_lang.split('-')[0]}",
                            headers=self.headers)
        out_path = (out_path or media_path.with_name(media_path.stem + f"_{target_lang}")).with_suffix(
            ".mp4" if media_path.suffix.lower() in {".mp4", ".mov", ".webm"} else ".mp3")
        out_path.write_bytes(r.content)
        return out_path

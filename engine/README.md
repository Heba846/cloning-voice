# Sawtak Engine

A small FastAPI server the static site calls. Runs on your PC or on Colab, reached through a free
Cloudflare quick tunnel (`*.trycloudflare.com`, no account). Every request needs the random token
printed at start-up; CORS only allows `https://heba846.github.io`.

| Endpoint | Body | Returns |
|---|---|---|
| `GET /health` | | engines installed, GPU, languages |
| `POST /tts` | form: `text`, `lang`, `sample` (voice reference, any audio/video) | `audio/wav` |
| `POST /translate` | json: `text`, `src`, `tgt` | `{text}` |
| `POST /lipsync` | form: `face` (image or video), `audio` | `video/mp4` |

Models (downloaded on first use, cached by Hugging Face):
TTS engines are tried in order per language; one whose weights fail to load is skipped (see `/health`):
- **OmniVoice + VoiceTut-TTS** (`pip install omnivoice`, weights `mohammedaly22/VoiceTut-TTS`, override with
  `OMNIVOICE_MODEL`) for `ar-EG` (Egyptian, English code-switching) and `en`. Clones from the first 10 s of the sample and transcribes it once with Whisper (`OMNIVOICE_ASR`).
- **Cairo-TTS** (not installed by default) for `ar-EG` and `en`. ⚠️ Its Hub repo `mohammedaly22/Cairo-TTS` was private/removed in Nov 2026;
  set `CAIRO_TTS_MODEL` to a copy of the weights.
- **Chatterbox Multilingual** for 22 more languages, and the last fallback for `ar-EG` (spoken as MSA-leaning `ar`). On Python 3.11/3.12 it needs its own venv
  (chatterbox-tts 0.1.7 pins numpy<2, torch 2.6, transformers 5.2; OmniVoice needs transformers>=5.3):
  `grep -v omnivoice engine/requirements.txt > req.txt && pip install -r req.txt -r engine/requirements-extra.txt`.
- **NLLB-200 600M** for translation, Egyptian Arabic included.
- **Wav2Lip GAN** for lip-sync. Checkpoint mirrors are tried in order; set `WAV2LIP_CKPT` / `S3FD_CKPT` to a path or URL if they move.

Environment variables: `OMNIVOICE_MODEL`, `OMNIVOICE_ASR`, `CAIRO_TTS_MODEL` (local folder or Hub repo of the weights), `ENGINE_TOKEN`, `ALLOWED_ORIGINS`, `SITE_URL`, `MAX_CHARS`, `MAX_UPLOAD_MB`,
`ENGINE_MOCK=1` (fake models, for testing the plumbing).

```bash
python -m engine.run              # server + tunnel + connect link
python -m engine.run --no-tunnel  # local only, Chrome on the same computer
```

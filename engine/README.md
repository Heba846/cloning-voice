# Sawtak Engine

A small FastAPI server the static site calls. Runs on your PC or on Colab, reached through a free
Cloudflare quick tunnel (`*.trycloudflare.com`, no account). Every request needs the random token
printed at start-up; CORS only allows `https://lioncoaching.github.io`.

| Endpoint | Body | Returns |
|---|---|---|
| `GET /health` | | engines installed, GPU, languages |
| `POST /tts` | form: `text`, `lang`, `sample` (voice reference, any audio/video) | `audio/wav` |
| `POST /translate` | json: `text`, `src`, `tgt` | `{text}` |
| `POST /lipsync` | form: `face` (image or video), `audio` | `video/mp4` |

Models (downloaded on first use, cached by Hugging Face):
- **Cairo-TTS** for `ar-EG` and `en`. Zero-shot cloning from the sample.
- **Chatterbox Multilingual** for 22 more languages (`pip install -r engine/requirements-extra.txt`).
- **NLLB-200 600M** for translation, Egyptian Arabic included.
- **Wav2Lip GAN** for lip-sync. Checkpoint mirrors are tried in order; set `WAV2LIP_CKPT` / `S3FD_CKPT` to a path or URL if they move.

Environment variables: `ENGINE_TOKEN`, `ALLOWED_ORIGINS`, `SITE_URL`, `MAX_CHARS`, `MAX_UPLOAD_MB`,
`ENGINE_MOCK=1` (fake models, for testing the plumbing).

```bash
python -m engine.run              # server + tunnel + connect link
python -m engine.run --no-tunnel  # local only, Chrome on the same computer
```

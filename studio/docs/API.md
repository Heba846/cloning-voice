# Sawtak Studio API

Base URL: `https://your-domain.com`. Interactive docs: `/docs`.
Auth: `Authorization: Bearer <jwt>` (from `/api/auth/login`) **or** `X-API-Key: <key>` (from the Billing page).

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/auth/signup` | `{email,password,name}` | returns `access_token` |
| POST | `/api/auth/login` | `{email,password}` | |
| GET | `/api/auth/me` | | plan, credits, api_key |
| GET | `/api/voices` | | your cloned voices |
| POST | `/api/voices` | multipart `name, language, sample(file)` | clone (costs credits) |
| GET | `/api/voices/remote` | | voices on the connected ElevenLabs account |
| POST | `/api/voices/import` | form `voice_id, name, language` | link an existing ElevenLabs voice (free) |
| DELETE | `/api/voices/{id}` | | |
| POST | `/api/translate` | `{text,target,source?}` | returns translated text |
| POST | `/api/tts` | `{voice_id,text,translate_to?,source_lang?}` | async job → audio |
| POST | `/api/reels` | multipart `face(file), voice_id, text, translate_to?, lipsync_engine?` or `audio(file)` | async job → mp4 1080×1920 |
| POST | `/api/dub` | multipart `media(file), target_lang, source_lang?` | async job → dubbed media |
| GET | `/api/jobs` / `/api/jobs/{id}` | | status, progress 0–1, message |
| GET | `/api/jobs/{id}/download` | | file (also accepts `?t=<jwt>`) |
| GET | `/api/billing/plans` | | |
| POST | `/api/billing/request-upgrade` | `{plan}` | WhatsApp-ready message |
| POST | `/api/billing/admin/activate?plan=pro` | `{user_email,delta,reason}` | admin only |

## Example: text → reel in your voice, in English, from a photo

```bash
curl -X POST https://your-domain.com/api/reels \
  -H "X-API-Key: sk_..." \
  -F face=@me.jpg -F voice_id=voc_xxx \
  -F text="أهلاً بيكم، النهاردة هنتكلم عن..." -F translate_to=en
# → {"id":"job_...","status":"queued",...}
curl https://your-domain.com/api/jobs/job_... -H "X-API-Key: sk_..."
curl -o reel.mp4 https://your-domain.com/api/jobs/job_.../download -H "X-API-Key: sk_..."
```

Job lifecycle: `queued → running (progress, message) → done | failed` (failed jobs refund their credits).

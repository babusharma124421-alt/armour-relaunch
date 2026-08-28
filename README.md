# the app — Armour

Armour is an AI-assisted, real-time voice-integrity and impersonation-detection platform for safer phone conversations. It combines audio authenticity signals, multilingual transcription, an offline scam-script scanner, optional Groq intent analysis, caller reputation, and rolling behavioral scoring.

> **Safety note:** Armour is decision support, not proof that a caller is genuine or fraudulent. Pause and verify through an independent official channel before sharing information or moving money.

## Prerequisites

- Python 3.11+
- Node 20+
- Android Studio (for APK)
- A Supabase project for durable session history and helpline data
- A Groq API key for Whisper and Llama intent analysis (the offline script scanner remains available without it)

## Quick Start

### 1. Clone & Configure

```bash
cp .env.example .env
# Fill in GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY, SMS_PROVIDER creds
```

For local development, leaving Supabase, Groq, and SMS credentials empty is supported. The backend uses an in-memory persistence fallback, the script scanner remains available, and outbound SMS is disabled until a provider is configured.

### 2. Supabase Setup

```bash
# Run backend/supabase/schema.sql in your Supabase SQL editor
# Then:
cd backend
python supabase/seed_helplines.py
cd ..
```

The schema never stores raw audio. Caller phone numbers used for reputation and community reports are stored only as unsalted SHA-256 hashes. Emergency contact numbers are stored for the explicit purpose of delivering a user-authorized alert.

### 3. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The first startup tries to load `backend/models/rawnet2.pt`, then the configured Hugging Face audio classifier. If neither is available, a conservative signal heuristic keeps local development and the rest of the pipeline usable. Set `VOICE_MODEL_LOCAL_ONLY=true` to avoid a model download during an offline demo.

### 4. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

The Vite development server proxies `/api` to `http://localhost:8000` so a browser-facing preview never needs to call a sandbox-localhost URL. Set `VITE_BACKEND_HTTP_URL` and `VITE_BACKEND_WS_URL` for a deployed frontend or APK.

### 5. SMS Provider

```bash
# For Twilio: set SMS_PROVIDER=twilio + Twilio creds in .env
# For Fast2SMS: set SMS_PROVIDER=fast2sms + FAST2SMS_API_KEY
# Both work without code changes — swapped via env var only
```

The alert service enforces a message length below 160 characters and the `/panic` route allows one trigger per session with a ten-minute cooldown.

## API Surface

- `POST /session/start` — create a monitored or practice session
- `GET /session/{session_id}/history` — retrieve score events and session metadata
- `GET /sessions/all?limit=20&offset=0` — paginated session history
- `WS /ws/call/{session_id}` — binary two-second audio chunk pipeline
- `POST /community-report` — hashed caller reputation report, limited to three per IP per hour
- `POST /panic` — alert saved emergency contacts, limited to one per session per ten minutes
- `POST /contacts`, `GET /contacts`, `DELETE /contacts/{id}` — emergency contact CRUD
- `GET /helplines?category=...` — editable Supabase helplines with JSON fallback
- `GET /health` — service and persistence readiness

## Demo Mode (Stage Backup)

```bash
cd backend
python demo_scripts/run_demo.py --script critical_en
```

Runs the critical impersonation script through the full pipeline and prints a formatted live risk table to the terminal. Available scripts are `benign_en`, `benign_hi`, `medium_en`, `medium_hi`, `critical_en`, and `critical_hi`. They are fictional test fixtures and must not be used as training data.

## Android APK

```bash
cd frontend
npm run build
npx cap sync android
npx cap open android
# In Android Studio: Build > Generate Signed APK
# Or for debug APK: ./gradlew assembleDebug
# APK location: android/app/build/outputs/apk/debug/
```

The generated Capacitor project includes `INTERNET`, `RECORD_AUDIO`, `READ_PHONE_STATE`, and `RECEIVE_BOOT_COMPLETED` permissions. Configure `VITE_BACKEND_HTTP_URL` for the device-accessible backend before producing a release build; `localhost` inside an APK refers to the device itself.

## Project Layout

```text
backend/
  main.py                  FastAPI lifespan, REST, and WebSocket orchestration
  schemas.py               Pydantic v2 contracts
  storage.py               Supabase adapter and local fallback
  services/                voice, intent, scanner, fusion, context, behavior, alerts
  supabase/                schema and helpline seed utility
  data/                   YAML patterns, bootstrap data, and JSON fallback helplines
  demo_scripts/            six fictional scripts and CLI replay
frontend/
  src/                    React pages, components, hook, i18n, and education content
  android/                Capacitor Android project
```

## Privacy and Operational Guarantees

- Raw audio exists only in the active request and is never written to disk or Supabase.
- Call-event transcript snippets are capped at 280 characters.
- Reputation phone numbers are SHA-256 hashes; raw caller numbers are not inserted into database rows.
- Community reports are rate limited to three per IP per hour.
- Panic alerts are rate limited to one trigger per session per ten minutes.
- Hindi, English, and Hinglish/code-switched language forms are included in the AI prompt and UI language flow.
- Supabase failures are logged as warnings and do not stop the live scoring pipeline.

## Troubleshooting

- **Groq API errors:** check `GROQ_API_KEY`; the app falls back to script scanner only.
- **RawNet2 checkpoint missing:** the service falls back to the Hugging Face model (auto-downloaded on first run) or a conservative heuristic if the model is unavailable.
- **Supabase offline:** call-event writes fail safely and local persistence keeps live development usable.
- **SMS not sending:** check `SMS_PROVIDER` matches the configured credentials and verify the destination number.
- **Microphone blocked:** grant browser or Android microphone permission and use HTTPS outside local development.
- **Preview cannot reach the backend:** use the Vite `/api` proxy in development or configure a publicly reachable `VITE_BACKEND_HTTP_URL` and `VITE_BACKEND_WS_URL`.

## Model Caveats

The included architecture documents the intended RawNet2/Hugging Face path, but model performance must be validated on real telephone audio. Telephone codecs, 8 kHz capture, background noise, and device variation can materially reduce accuracy. The behavioral model is bootstrapped on synthetic data and must be retrained on real labeled call logs before production accuracy claims.

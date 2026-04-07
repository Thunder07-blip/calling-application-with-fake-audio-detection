🚀 Your Final Stack (Validated)
Real-time layer
LiveKit Cloud
👉 handles audio routing, scaling, NAT, UDP, etc.
Backend
Railway
👉 runs your FastAPI + DB
Distribution
Direct APK sharing (WhatsApp/Drive)
👉 fastest for testing
🧠 Final Architecture (what you are actually building)
Mobile App (APK)
     │
     ▼
Railway Backend (FastAPI)
     │
     ├── PostgreSQL (users, calls, events)
     └── Token generation
     
     ▼
LiveKit Cloud (WebRTC)
     │
     ▼
ML Agent (can be Railway OR separate worker)
⚠️ Important change vs your current setup

Right now you are using:

ws://localhost:7880

You MUST switch to:

wss://your-project.livekit.cloud

Otherwise:

mobile app won’t connect
Railway backend won’t reach it
external users can’t join
🧩 Step-by-step execution plan
STEP 1 — Create LiveKit Cloud project

Go to LiveKit Cloud dashboard and:

You will get:

LIVEKIT_URL = wss://your-project.livekit.cloud
LIVEKIT_API_KEY = xxxx
LIVEKIT_API_SECRET = yyyy

⚠️ Important:

API Key ≠ API Secret
Secret is hidden → copy it once
STEP 2 — Update your backend

In your FastAPI (token_service.py):

import os

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

Token generation stays same — only URL changes on client side.

STEP 3 — Deploy backend on Railway
Push your repo to GitHub

Then connect to Railway:

Select repo
Railway auto-detects Dockerfile
Deploy
Add environment variables in Railway dashboard:
LIVEKIT_URL = wss://your-project.livekit.cloud
LIVEKIT_API_KEY = xxxx
LIVEKIT_API_SECRET = yyyy
DATABASE_URL = (Railway Postgres auto provides this)

Railway automatically gives:

https://your-app.up.railway.app
STEP 4 — Update Flutter client

Replace:

ws://localhost:7880

with:

wss://your-project.livekit.cloud

Replace backend URL:

http://127.0.0.1:8000/token

with:

https://your-app.up.railway.app/token
STEP 5 — Update ML agent

Your ML agent should connect to:

url = "wss://your-project.livekit.cloud"

NOT:

ws://livekit:7880
🔥 Big decision (VERY important)
Where will ML agent run?

You have 2 options:

Option A — Run ML agent on Railway (simple)

Pros:

easiest
no infra

Cons:

limited CPU
not ideal for heavy models
Option B — Run ML agent locally (for now)
python agent.py

Pros:

full control
easy debugging

Cons:

not scalable yet

👉 Recommended now: Option B

📦 APK distribution (your plan)

You chose:

WhatsApp / Drive APK
Steps:
flutter build apk --release

File:

build/app/outputs/flutter-apk/app-release.apk

Send via:

WhatsApp
Google Drive

User installs → allow "Unknown Sources"

⚠️ Real-world issues you WILL hit
1. CORS error (backend)

Fix in FastAPI:

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
2. HTTPS requirement

LiveKit Cloud requires:

wss:// (secure WebSocket)

So:

backend must be HTTPS (Railway handles this ✅)
mobile app works fine
3. Token mismatch errors

If you see:

unauthorized / invalid token

Check:

API key matches secret
room name matches
identity is unique
🧪 End-to-end test (VERY IMPORTANT)

Before ML, verify this flow:

1. Call backend
GET /token
2. Use token in app
3. Join room
4. Speak → hear audio

Only after this works:
👉 then test ML agent
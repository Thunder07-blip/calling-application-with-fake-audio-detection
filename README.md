<h1 align="center">
  🛡️ Safe Call Platform
</h1>

<p align="center">
  <strong>Real-time AI-powered deepfake audio detection for voice calls</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Flutter-3.x-02569B?style=for-the-badge&logo=flutter&logoColor=white" alt="Flutter"/>
  <img src="https://img.shields.io/badge/FastAPI-0.103+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/LiveKit-WebRTC-FF6B35?style=for-the-badge&logo=webrtc&logoColor=white" alt="LiveKit"/>
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/PyTorch-ML-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch"/>
</p>

<p align="center">
  A full-stack WebRTC voice calling platform with an AI agent that silently monitors live calls in real-time, analyzing audio streams frame-by-frame using a custom PyTorch neural network to detect AI-generated (deepfake) voices and alert users instantly.
</p>

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🎙️ **Real-time WebRTC Calls** | Full-duplex voice calling powered by LiveKit with sub-50ms latency |
| 🧠 **AI Deepfake Detection** | Custom-trained PyTorch model analyzing audio streams frame-by-frame |
| 🔐 **Speaker Verification** | Voiceprint enrollment & matching using wav2vec2 embeddings |
| 📱 **Cross-platform Client** | Beautiful dark-mode Flutter app (Android, Web, Windows) |
| 🐘 **Persistent Logging** | All calls, participants & ML detection events stored in PostgreSQL |
| 🐳 **One-command Deploy** | Entire 5-service backend orchestrated via Docker Compose |
| ⚡ **Live Alerts** | Real-time deepfake confidence scores pushed to the Flutter UI |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        Docker Compose                              │
│                                                                    │
│  ┌─────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────┐  │
│  │PostgreSQL│◄──│  FastAPI      │──►│  LiveKit      │◄──│ TURN   │  │
│  │  :5432   │   │  Backend API │   │  Media Server │   │ Server │  │
│  │          │   │  :8000       │   │  :7880        │   │ :5349  │  │
│  └─────────┘   └──────┬───────┘   └──────┬────────┘   └────────┘  │
│                       │                   │                        │
│                       │            ┌──────┴────────┐               │
│                       │            │  ML Deepfake  │               │
│                       └───────────►│  Agent (Bot)  │               │
│                                    │  (Background) │               │
│                                    └───────────────┘               │
└────────────────────────────────────────────────────────────────────┘
                              ▲
                    WebRTC    │    HTTP + WebSocket
                              │
              ┌───────────────┴───────────────┐
              │                               │
      ┌───────┴───────┐             ┌─────────┴─────────┐
      │  Flutter App  │             │  Web Test Client   │
      │  (Android/Web)│             │  (Browser HTML)    │
      └───────────────┘             └───────────────────┘
```

### Services Breakdown

| Service | Port | Role |
|---|---|---|
| **PostgreSQL** | `5432` | Stores companies, users, calls, participants & ML detection events |
| **LiveKit** | `7880` | WebRTC media server routing real-time UDP audio between clients |
| **TURN (Coturn)** | `5349` | NAT traversal relay for restrictive firewalls |
| **FastAPI Backend** | `8000` | Authentication, JWT token generation, database CRUD, REST API |
| **ML Agent** | Background | Invisible bot joining every call to run deepfake inference |

---

## 📂 Project Structure

```
safe-call-platform/
│
├── docker-compose.yml          # Orchestrates all 5 backend services
├── .env.example                # Environment variable template
│
├── backend_api/                # 🧠 FastAPI Backend
│   ├── main.py                 # App entrypoint, mounts routers
│   ├── database.py             # SQLAlchemy engine & session
│   ├── models.py               # DB models (User, Call, MLEvent)
│   ├── schemas.py              # Pydantic request/response validators
│   ├── routes/                 # API endpoints
│   │   ├── auth.py             # GET /token/demo — JWT token generation
│   │   ├── calls.py            # Call management endpoints
│   │   └── companies.py        # Company/user management
│   ├── services/               # Business logic layer
│   │   ├── token_service.py    # LiveKit JWT token minting
│   │   └── ml_event_service.py # Deepfake alert persistence
│   ├── Dockerfile
│   └── requirements.txt
│
├── ml_agent_python/            # 🤖 AI Deepfake Detection Agent
│   ├── agent.py                # LiveKit bot — joins rooms, intercepts audio
│   ├── model.py                # Custom PyTorch voice detector architecture
│   ├── speaker_verify.py       # wav2vec2 speaker verification
│   ├── audio_processor.py      # Audio preprocessing utilities
│   ├── enroll_speaker.py       # Voiceprint enrollment script
│   ├── calibrate_threshold.py  # Detection threshold calibration
│   ├── models/                 # Trained model weights (.pth)
│   ├── Dockerfile
│   └── requirements.txt
│
├── client_flutter/             # 📱 Flutter Client App
│   ├── lib/main.dart           # Full UI + WebRTC + mic streaming
│   ├── pubspec.yaml            # Flutter dependencies
│   └── android/                # Android platform config
│
├── test_client.html            # 🌐 Browser-based test client
├── test_backend_flow.py        # ✅ E2E backend verification script
├── simulate_client.py          # 🧪 Client simulation script
├── railway.toml                # Railway deployment config
├── ARCHITECTURE.md             # Detailed architecture documentation
└── SETUP.md                    # Quick-reference server guide
```

---

## 🚀 Getting Started

### Prerequisites

Make sure you have these installed:

- [**Docker Desktop**](https://www.docker.com/products/docker-desktop/) (v20+)
- [**Flutter SDK**](https://docs.flutter.dev/get-started/install) (v3.x)
- [**Python 3.11+**](https://www.python.org/downloads/) (for running test scripts)
- [**Git**](https://git-scm.com/downloads)

### 1. Clone the Repository

```bash
git clone https://github.com/Thunder07-blip/calling-application-with-fake-audio-detection.git
cd calling-application-with-fake-audio-detection
```

### 2. Configure Environment Variables

```bash
# Copy the template
cp .env.example .env

# Edit with your preferred editor
# For local development, the defaults work out of the box!
```

> **💡 Tip:** For local development with Docker, you don't need to change anything — the default `devkey`/`secret` values work automatically.

See [`.env.example`](.env.example) for a full annotated list of variables.

### 3. Start the Backend (Docker)

```bash
# Boot all 5 services (Postgres, LiveKit, TURN, FastAPI, ML Agent)
docker-compose up -d --build

# Verify everything is running
docker-compose ps

# (Optional) Watch the AI agent analyzing audio in real-time
docker-compose logs -f ml-agent
```

### 4. Verify the Backend

```bash
# Quick health check
curl http://localhost:8000/health

# Full E2E test (requires Python + httpx)
python test_backend_flow.py
```

### 5. Launch the Flutter Client

#### Option A: Web Browser (Quickest)

```bash
cd client_flutter
flutter pub get
flutter run -d chrome
```

#### Option B: Android Device

```bash
cd client_flutter
flutter pub get
flutter run -d <your-device-id>  # e.g., flutter run -d dd66499e
```

> **📱 For phone testing:** Update `LIVEKIT_NODE_IP` in your `.env` to your PC's local WiFi IP address (find it with `ipconfig` on Windows or `ifconfig` on macOS/Linux). Then restart Docker.

### 6. Test with a Second Caller

Open a separate terminal and serve the web test client:

```bash
python -m http.server 3000
```

Then open `http://localhost:3000/test_client.html` in Chrome and click **Connect**.

🎉 **Both callers are now in a live WebRTC call with real-time AI deepfake monitoring!**

---

## ☁️ Cloud Deployment

The platform supports deployment to cloud providers:

| Component | Recommended Provider |
|---|---|
| **Backend API** | [Render](https://render.com) / [Railway](https://railway.app) |
| **LiveKit** | [LiveKit Cloud](https://cloud.livekit.io) (free tier available) |
| **Database** | Railway PostgreSQL / Render PostgreSQL |
| **Flutter App** | Firebase Hosting (web) / Play Store (Android) |

For cloud deployment, update your `.env` with the cloud provider URLs and credentials. The `railway.toml` is pre-configured for Railway deployment.

---

## 🔧 Common Commands

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# Rebuild a specific service after code changes
docker-compose up -d --build --force-recreate ml-agent

# View ML agent logs (live deepfake scores)
docker-compose logs -f ml-agent

# View backend API logs
docker-compose logs -f backend-api

# Reset database (delete all data)
docker-compose down -v
docker-compose up -d
```

---

## 🧠 How the AI Detection Works

1. **Audio Interception** — The ML agent silently joins every LiveKit room as an invisible participant
2. **Frame Extraction** — Raw PCM audio is captured frame-by-frame from each participant's stream
3. **Feature Extraction** — Audio frames are processed through a wav2vec2 feature extractor
4. **Classification** — A custom-trained PyTorch neural network classifies each frame as real or AI-generated
5. **Speaker Verification** — Optionally verifies the speaker's identity against enrolled voiceprints
6. **Alert Dispatch** — If deepfake confidence exceeds the calibrated threshold, alerts are sent to the Flutter UI and logged to PostgreSQL

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Flutter (Dart), LiveKit Client SDK, Google Fonts |
| **Backend API** | FastAPI, SQLAlchemy, Pydantic, LiveKit Server SDK |
| **ML Engine** | PyTorch, torchaudio, transformers (wav2vec2), resemblyzer |
| **Media Server** | LiveKit (Go), Coturn TURN server |
| **Database** | PostgreSQL 15 |
| **Infrastructure** | Docker Compose, Railway, Render |

---

## 📄 License

This project is part of an academic research initiative. Please contact the maintainers for usage permissions.

---

<p align="center">
  Built with ❤️ using AI-assisted development
</p>

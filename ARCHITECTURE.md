# 🧠 Safe Call Platform: Architecture & Flow Guide

Welcome! Since we built this platform extremely quickly using an AI IDE, there are a lot of moving parts happening simultaneously. 

This document explains **exactly what is happening under the hood**, what servers are running, how the code is organized, and what happens when you press a button on your phone.

---

## 🏗️ 1. What Servers are Running & Where?

When the environment is fully active, there are exactly **5 backend servers** humming away simultaneously inside Docker, and **1 frontend app** running on your phone/browser. 

Here is exactly what is running on your PC natively right now.

### The Backend (Running inside `docker-compose up -d`)
1. **PostgreSQL Database (`db` service | Port `5432`)**
   - Stores all your Companies, Users, actively running Calls, Participants, and logs every Deepfake AI Detection event.
2. **LiveKit Media Server (`livekit` service | Port `7880`)**
   - The heart of the voice platform. Written in Go, this routes all massive raw audio WebRTC UDP packets between phones in real-time. 
3. **TURN Server (`coturn` service | Port `5349`)**
   - A relay server used to punch holes through strict enterprise Wi-Fi routers and NAT firewalls so audio can go anywhere.
4. **FastAPI Python Backend (`backend-api` service | Port `8000`)**
   - The central brain. This authenticates users, talks to the Postgres database, and generates secure JWT (JSON Web Tokens) that give the frontends permission to talk to LiveKit.
5. **Python ML Deepfake Agent (`ml-agent` service | Background Worker)**
   - An invisible bot that automatically joins every LiveKit room. It intercepts the raw voice traffic in real-time, passes it through your `.pth` AI model natively, and fires Alerts to Postgres if it detects a deepfake audio curve.

### The Frontend (Running locally outside of Docker)
* **Flutter Client (`client_flutter/` | Web, Android, Windows)**
   - The beautiful UI layer that holds the WebRTC engine. Runs locally on your phone or PC.
* *(Optional)* **Simple HTML Client (`test_client.html` | Port `3000`)**
   - A lightweight vanilla JS client we use purely to test the exact same LiveKit connection the phone uses, to ensure the backend is healthy.

---

## ⚡ 2. The "Start Call" Workflow: Exactly what happens?

When a user opens the Flutter app and taps **"Start Safe Call"**, a massive chain reaction happens across your PC in less than 50 milliseconds:

1. **The Request:** Flutter fires an HTTP `GET` request to your PC's IP address (`http://192.168.29.34:8000/token/demo`).
2. **The Database Prep (FastAPI):**
   - The Python backend intercepts this. It checks the PostgreSQL DB: *"Does the `Demo Corp` company exist? Does the user exist?"* 
   - If not, it automatically **creates a new Company instance, User instance, and Call instance** and permanently saves them to the Database with a Unique UUID.
3. **The Key Master (FastAPI + LiveKit):**
   - FastAPI secretly uses the `LIVEKIT_API_SECRET` to encrypt a JSON Web Token (JWT) that specifically says *"Tester 6983 is allowed to publish their microphone only to 'testroom'"*.
   - It sends this tiny encrypted Token string straight back to the Flutter app's memory.
4. **The Handshake (Flutter + LiveKit):**
   - Flutter completely bypasses Python now. It takes that encrypted Token and aims directly at the LiveKit Go server on Port `7880`. 
   - LiveKit validates the token, opens a permanent WebRTC WebSocket tunnel, and tells Flutter to start pumping raw microphone arrays to the server over UDP.
   - You hear audio instantly on all connected devices.

---

## 📂 3. The File Structure Explained

Here is why your code is shaped the way it is:

```text
safe-call-platform/
│
├── docker-compose.yml       <-- The map that wires the 5 servers together.
│
├── backend_api/             <-- The brain (FastAPI Layer)
│   ├── main.py              <-- The bootup script. Loads routers and databases.
│   ├── database.py          <-- Holds the PostgreSQL engine connection logic.
│   ├── models.py            <-- Defines exactly what DB tables look like (User, Call, MLEvent) 
│   ├── schemas.py           <-- Strict Pydantic validators that block bad front-end data
│   │
│   ├── routes/              <-- The URL listeners your Frontends talk to
│   │   ├── companies.py     <-- e.g. POST /users, POST /companies
│   │   ├── calls.py         <-- e.g. POST /calls/start
│   │   └── auth.py          <-- e.g. GET /token/demo (Where the Magic Token happens!)
│   │
│   └── services/            <-- Contains the heavy lifting backend logic to keep routes perfectly clean
│       ├── token_service.py <-- Actually generates the secure LiveKit JWT tokens
│       └── ml_event_service.py<- Code that saves DeepFake alerts to Postgres
│
├── client_flutter/          <-- The App (Dart Layer)
│   └── lib/main.dart        <-- The entire UI, mic streaming, and WebRTC logic.
│
├── ml_agent_python/         <-- The Voice ML Worker
│   └── agent.py             <-- The robot that joins the call to record incoming voice bytes!
│
└── test_backend_flow.py     <-- Our internal auto-testing bot to verify Postgres is alive.
```

---

## 🚀 4. "Absolute Baby Steps" to Start the Project Fresh

If your PC reboots, or you want to start everything up perfectly, follow this exact order:

**Step 1: Ignite the Database and Servers**
Open PowerShell at your project folder and run:
```bash
docker-compose up -d
```
*Docker will instantly spin up Postgres, LiveKit, Coturn, the API backend, and the ML bot.*

**Step 2: (Optional check) Verify the API hums**
```bash
uv run python test_backend_flow.py
```
*If this prints green checkmarks, your database and token generator are perfect.*

**Step 3: Boot the Android App**
Plug in your phone, swipe down the notifications to switch your USB connection to **"File Transfer"**, and run:
```bash
cd client_flutter
flutter run -d <your-device-id> 
# Example: flutter run -d dd66499e
```
*Your phone app will open.*

**Step 4: Boot a Web App to talk to your phone**
Open a new PowerShell terminal at your project folder and run:
```bash
uv run python -m http.server 3000
```
Then open Google Chrome and go to `http://127.0.0.1:3000/test_client.html`. Click connect. 

**Result:** Your Web Browser and your physical Android phone are now completely engaged in a live, real-time, UDP-powered bidirectional audio stream that is actively monitored by the Python Artificial Intelligence model!

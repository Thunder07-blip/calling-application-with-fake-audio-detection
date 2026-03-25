# 🛠️ Safe Call Platform: Quick Setup & Server Guide

This guide is your quick-reference sheet for starting, stopping, and understanding the server topology of the Safe Call Platform.

---

## 🖥️ Server Breakdown (What is running?)
Your entire backend is containerized inside Docker, meaning it actively houses 5 separate micro-services that talk to each other. Your Flutter mobile app does **not** rely on simple PC web servers; instead, it talks natively to these robust enterprise containers directly.

1. **`db` (Port `5432`)**: The resilient PostgreSQL database housing your Companies and Live Call data. 
2. **`livekit` (Port `7880`)**: The incredibly powerful WebRTC engine managing pure high-speed UDP audio traffic natively.
3. **`backend-api` (Port `8000`)**: The FastAPI Python brain that gives your Flutter App encrypted LiveKit Keys (JWTs).
4. **`ml-agent` (Background)**: The silent Artificial Intelligence Python worker constantly monitoring LiveKit arrays for Deepfake scores.
5. **`coturn` (Port `5349`)**: The Network Address Translator punching firewall holes for complex corporate networks.

---

## ⚡ The Phone-to-Backend Connection Magic
Even if the Python HTTP test server is dead, your phone knows **exactly** where to send the calls!

1. **The Handshake:** Flutter secretly targets the Dockerized Python API server (`http://192.168.29.34:8000/token/demo`) and asks for an encrypted WebRTC Key.
2. **The Audio Pipe:** Python hands the phone the Key along with the explicit location of the LiveKit server (`ws://192.168.29.34:7880`).
3. **The Voice Steam:** Flutter securely locks onto Port `7880` natively over WebSockets, bypassing Python completely and pushing high-speed native UDP voice. 

*(**Note:** The simple `http.server 3000` command purely exists to trick Chrome browser permissions if you ever decide to test raw HTML pages locally on your laptop without using the app. It has nothing to do with the heavy lifting!)*

---

## 🚀 The Essential Commands Cheat Sheet

### 1. 🟢 Start Everything Fresh
Turn on all 5 backend servers natively at once:
```bash
docker-compose up -d
```

### 2. 🤖 Watch the ML Agent Work Live
To watch the AI print out real-time Deepfake confidence scores (`user aece19f... fake confidence 0.99`) as people speak, use this command to stream its exact Python logs infinitely:
```bash
docker-compose logs -f ml-agent
```

### 3. 📱 Start the Flutter App
To launch the beautiful Voice Client (Web or Phone):
```bash
cd client_flutter
flutter run -d chrome    # For the Web App
flutter run -d dd66499e  # For the Physical OnePlus Android Phone
```

### 4. 🧰 Re-Compile the AI Bot
If you ever change `test_realtime.py` or `agent.py` and need the AI to reload instantly locally, use this (powered by lightning fast `uv` package manager builds!):
```bash
docker-compose up -d --build --force-recreate ml-agent
```

### 5. 🛑 Turn Everything Off Safely
When you are done for the day and want to elegantly shut down the databases and stop burning your laptop's CPU memory without corrupting anything:
```bash
docker-compose down
```

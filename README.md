# Safe Voice Calling Platform 🛡️📞

A complete WebRTC-based voice calling loop designed to securely stream and monitor raw voice data using an AI Python backend (via LiveKit).

This system includes:
- **LiveKit Server** (For WebRTC audio routing)
- **FastAPI Token Server** (For creating secure user tokens)
- **Python ML Safety Agent** (To listen to calls and analyze RMS audio levels)
- **Flutter Client App** (A premium dark-mode UI to place the calls)
- **Web Test Client** (To quickly test the audio on your PC browser)

---

## 🍼 "Baby Steps" Setup Guide

Follow these exact steps to turn on the entire project from scratch.

### 🔴 Step 1: Turn on the Brain (Docker)
You must have **Docker Desktop** installed and open on your computer before proceeding.

1. Open your terminal in this main project folder.
2. Run this command to boot up the WebRTC servers and Python ML Agent:
   ```bash
   docker-compose up -d --build --force-recreate
   ```
3. *(Optional)* If you want to literally watch the Python ML Agent analyzing your voice frame-by-frame, open a new terminal and run:
   ```bash
   docker-compose logs -f ml-agent
   ```

### 🔵 Step 2: Open the First Caller (PC Browser)
To test the call, you need a second person. We will use a quick web app as your first caller.

1. Open a new terminal tab.
2. Run this command to host the test web page:
   ```bash
   uv run python -m http.server 3000
   ```
3. Open Google Chrome on your PC and paste in this link:
   👉 `http://127.0.0.1:3000/test_client.html`
4. Click **Connect**. If Chrome asks for Microphone permissions, say **Allow**. (Ensure no other apps like Zoom are hogging your mic!)

### 🟡 Step 3: Open the Second Caller (Flutter App)
Now let's launch the beautiful native Flutter app. You have two options to run it:

#### Option A: Run it inside your PC Browser (Fastest, Easiest)
1. Open a new terminal tab and navigate into the Flutter folder:
   ```bash
   cd client_flutter
   ```
2. Run this command:
   ```bash
   flutter run -d chrome
   ```
3. It will automatically pop open a new Chrome window showing the Dark Mode App! Click **Start Safe Call**.

#### Option B: Run it on your Physical Android Phone (Advanced)
If you want to install it on your Android phone, you must adjust the Docker IP so your phone knows where your PC is on the Wi-Fi.

1. Find your PC's IP address by running `ipconfig` in CMD (Look for `IPv4 Address`, e.g., `192.168.1.7`).
2. Open `docker-compose.yml` and replace `--node-ip=192.168.1.7` with your computer's *current* IP address on line 6! (Also update it on line 34).
3. Open `client_flutter/lib/main.dart` and update line 59 from `192.168.1.7` to your current IP.
4. Run:
   ```bash
   docker-compose down
   docker-compose up -d --force-recreate
   ```
5. Plug your phone into your PC, navigate to the `client_flutter` folder in your terminal, and run:
   ```bash
   flutter run -d android
   ```

---

## 🎉 You're Done!
Once both callers are connected to the "testroom", you will see each other in the Participant List. Talk into your microphones and you will hear each other natively, while the Python ML agent silently calculates your audio levels in the background!

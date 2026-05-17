# 🧪 Safe Call Platform — Testing Guide

## 📌 Purpose

This document provides a **step-by-step testing strategy** for the Safe Calling Environment Platform. It ensures that each component (backend, database, LiveKit integration, and ML agent) works correctly before full system integration.

---

# 🧱 Testing Strategy Overview

We follow a **layered testing approach**:

```text
1. Infrastructure (Docker, Railway)
2. Backend API (FastAPI)
3. Database (PostgreSQL)
4. Token Generation (Auth)
5. LiveKit Connection
6. Client Integration (Flutter / Simulator)
7. ML Agent Integration
```

---

# ✅ 1. Infrastructure Testing

## Goal

Ensure deployment and container startup are working.

## Steps

### 1.1 Check Deployment

Open:

```
https://your-app.up.railway.app/health
```

### Expected Output

```json
{"status": "ok"}
```

---

### 1.2 Check Logs (Railway)

Look for:

```
Uvicorn running on http://0.0.0.0:<PORT>
```

### Failure Cases

| Issue             | Cause                   |
| ----------------- | ----------------------- |
| Healthcheck fails | `/health` route missing |
| App not starting  | Docker CMD issue        |
| Crash before logs | Import or DB error      |

---

# ✅ 2. Backend API Testing

## Goal

Ensure API endpoints respond correctly.

---

## 2.1 Health Endpoint

### Request

```
GET /health
```

### Expected

```json
{"status": "ok"}
```

---

## 2.2 Root Endpoint

### Request

```
GET /
```

### Expected

```json
{"message": "working"}
```

---

## 2.3 Swagger UI

Open:

```
/docs
```

### Expected

* Interactive API UI loads
* Endpoints visible

---

# ✅ 3. Database Testing

## Goal

Ensure DB connection and schema creation works.

---

## 3.1 Startup DB Init

Check logs:

```
Starting Safe Call API — initialising database tables...
```

---

## 3.2 Failure Handling

Ensure app does NOT crash if DB fails:

```python
try:
    init_db()
except Exception as e:
    print("DB ERROR:", e)
```

---

## 3.3 Manual DB Test

Test via endpoint (example):

```
POST /companies
```

### Expected

* Record created
* No 500 errors

---

# ✅ 4. Token Generation Testing

## Goal

Verify LiveKit token creation.

---

## 4.1 Request Token

```
GET /token?room=testroom&identity=user1
```

### Expected Response

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

## 4.2 Failure Cases

| Error            | Cause                |
| ---------------- | -------------------- |
| 401 Unauthorized | Wrong API key/secret |
| 500 Error        | Code issue           |
| Empty token      | Signing failed       |

---

# ✅ 5. LiveKit Connection Testing

## Goal

Ensure WebRTC connection works.

---

## 5.1 Configuration

```
LIVEKIT_URL = wss://your-project.livekit.cloud
```

---

## 5.2 Test Flow

```
1. Request token
2. Join room
3. Publish audio
4. Receive audio
```

---

## Expected Result

* No connection errors
* Participants visible
* Audio transmitted

---

# ✅ 6. Client Testing (Flutter / Simulator)

## Goal

Verify end-to-end user flow.

---

## 6.1 Token Fetch

Client calls:

```
/token
```

### Expected

* Valid token received

---

## 6.2 Join Room

Client connects using:

```
wss://your-project.livekit.cloud
```

---

## 6.3 Audio Test

* Speak into mic
* Other client hears audio

---

## Failure Cases

| Issue           | Cause           |
| --------------- | --------------- |
| No audio        | Mic permissions |
| Connection fail | Wrong URL       |
| Token rejected  | Backend issue   |

---

# ✅ 7. ML Agent Testing

## Goal

Ensure ML model receives and processes audio.

---

## 7.1 Start Agent

```
python agent.py
```

---

## 7.2 Expected Logs

```
Receiving audio frame...
RMS Energy: <value>
```

---

## 7.3 Test Audio Input

* Speak in client
* Agent logs activity

---

## Failure Cases

| Issue              | Cause                   |
| ------------------ | ----------------------- |
| No frames received | Not joined room         |
| Crash              | Import/dependency issue |
| No audio data      | Subscription issue      |

---

# ✅ 8. End-to-End System Test

## Goal

Validate full pipeline.

---

## Flow

```
User A → Backend → LiveKit → ML Agent → User B
```

---

## Steps

1. Start backend
2. Start ML agent
3. Open client (2 users)
4. Join same room
5. Speak

---

## Expected

* Audio flows
* ML agent logs data
* No crashes

---

# 🚨 9. Edge Case Testing

## 9.1 No Active Call

```
Join without call → expect 404
```

---

## 9.2 Multiple Users

* Join 3+ users
* Ensure no crash

---

## 9.3 Invalid Token

* Modify token
* Expect rejection

---

## 9.4 Network Drop

* Disconnect internet
* Reconnect
* Verify recovery

---

# 📊 10. Performance Testing (Basic)

## Test

* 5–10 users in same room
* Continuous audio for 5 minutes

## Observe

* Latency
* Packet loss
* CPU usage

---

# 🧠 Final Notes

* Always test **one layer at a time**
* Never debug everything at once
* Logs are your best friend

---

# 🚀 Status Checklist

| Component          | Status |
| ------------------ | ------ |
| Docker Build       | ⬜      |
| Railway Deploy     | ⬜      |
| Health API         | ⬜      |
| Token API          | ⬜      |
| LiveKit Connection | ⬜      |
| Client App         | ⬜      |
| ML Agent           | ⬜      |
| End-to-End Flow    | ⬜      |

---

# 🎯 Conclusion

Once all tests pass, your system becomes a fully functional:

```
Real-time, ML-powered, scalable VoIP platform
```

---

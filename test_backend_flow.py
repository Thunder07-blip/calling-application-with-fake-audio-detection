"""
test_backend_flow.py
────────────────────
A manual end-to-end sanity check script you can run anytime after deploying to
verify the full backend is wired correctly.

Usage:
    uv run python test_backend_flow.py
    # OR
    python test_backend_flow.py
"""
import requests
import sys

BASE = "https://calling-application-with-fake-audio-detection-production.up.railway.app"


def step(msg: str):
    print(f"\n{'─'*50}")
    print(f"  {msg}")
    print('─'*50)


def fail(msg: str, resp):
    print(f"❌ FAILED: {msg}")
    print(f"   Status: {resp.status_code}")
    print(f"   Body:   {resp.text}")
    sys.exit(1)


step("1. Creating Company...")
resp = requests.post(f"{BASE}/companies", json={"name": "Acme Corp"})
if resp.status_code != 200:
    fail("create company", resp)
company = resp.json()
print(f"✅ Company created: {company['name']} (id={company['id']})")

import uuid
random_suffix = uuid.uuid4().hex[:6]

step("2. Creating User...")
resp = requests.post(f"{BASE}/users", json={
    "company_id": company["id"],
    "email": f"bob_{random_suffix}@acme.com",
    "display_name": "Bob"
})
if resp.status_code != 200:
    fail("create user", resp)
user = resp.json()
print(f"✅ User created: {user['display_name']} (id={user['id']})")

step("3. Starting Call...")
resp = requests.post(f"{BASE}/calls/start", json={
    "company_id": company["id"],
    "created_by": user["id"]
})
if resp.status_code != 200:
    fail("start call", resp)
call = resp.json()
print(f"✅ Call started: room={call['room_name']} (id={call['id']})")

step("4. Requesting LiveKit Token...")
resp = requests.get(f"{BASE}/token", params={
    "user_id": user["id"],
    "call_id": call["id"]
})
if resp.status_code != 200:
    fail("get token", resp)
token_data = resp.json()
print(f"✅ Token received! Length={len(token_data['token'])} chars")
print(f"   LiveKit URL: {token_data['livekit_url']}")
print(f"   Room: {token_data['room_name']}")

step("5. Ending the Call...")
resp = requests.post(f"{BASE}/calls/{call['id']}/end")
if resp.status_code != 200:
    fail("end call", resp)
ended = resp.json()
print(f"✅ Call ended at: {ended['ended_at']}")

print(f"\n{'═'*50}")
print("  ✅ All backend checks PASSED!")
print(f"{'═'*50}\n")

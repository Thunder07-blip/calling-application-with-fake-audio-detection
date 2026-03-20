from fastapi.testclient import TestClient
from main import app
import os
import pytest

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_token():
    # Setup mock env vars before calling the token creation
    # Actually, token_service variables might be read already,
    # but let's test the endpoint logic anyway.
    os.environ["LIVEKIT_API_KEY"] = "devkey"
    os.environ["LIVEKIT_API_SECRET"] = "secret"
    
    response = client.get("/token?identity=testuser&room=testroom")
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "livekit_url" in data
    assert len(data["token"]) > 0
    
def test_get_token_missing_identity():
    response = client.get("/token")
    assert response.status_code == 422 # Unprocessable Entity due to missing required query parm

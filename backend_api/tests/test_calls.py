import requests
import pytest

BASE = "http://localhost:8000"


@pytest.fixture(scope="module")
def full_flow():
    """Creates a company, user, and call and returns them as test fixtures."""
    company = requests.post(f"{BASE}/companies", json={"name": "TestCo"}).json()
    assert "id" in company, f"Company creation failed: {company}"

    user = requests.post(f"{BASE}/users", json={
        "company_id": company["id"],
        "email": "alice@testco.com",
        "display_name": "Alice"
    }).json()
    assert "id" in user, f"User creation failed: {user}"

    call = requests.post(f"{BASE}/calls/start", json={
        "company_id": company["id"],
        "created_by": user["id"]
    }).json()
    assert "id" in call, f"Call start failed: {call}"

    return {"company": company, "user": user, "call": call}


def test_create_company():
    """Test company creation returns proper fields."""
    resp = requests.post(f"{BASE}/companies", json={"name": "Smoke Test Co"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["name"] == "Smoke Test Co"


def test_create_user(full_flow):
    """Test user creation inside a valid company."""
    company = full_flow["company"]
    resp = requests.post(f"{BASE}/users", json={
        "company_id": company["id"],
        "email": "bob@testco.com",
        "display_name": "Bob"
    })
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_start_call(full_flow):
    """Test that a call can be started and returns a unique room_name."""
    call = full_flow["call"]
    assert "room_name" in call
    assert call["room_name"].startswith("call_")


def test_get_token(full_flow):
    """Test the secure token endpoint with valid company-isolated user and call."""
    user = full_flow["user"]
    call = full_flow["call"]
    resp = requests.get(f"{BASE}/token", params={
        "user_id": user["id"],
        "call_id": call["id"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert len(data["token"]) > 50  # Valid JWT tokens are always long


def test_cross_company_token_denied():
    """Test that cross-company token requests are rejected with 403."""
    # Create a completely separate second company and user
    company2 = requests.post(f"{BASE}/companies", json={"name": "EvilCorp"}).json()
    user2 = requests.post(f"{BASE}/users", json={
        "company_id": company2["id"],
        "email": "hacker@evil.com",
        "display_name": "Hacker"
    }).json()

    # Create a call belonging to company2
    call2 = requests.post(f"{BASE}/calls/start", json={
        "company_id": company2["id"],
        "created_by": user2["id"]
    }).json()

    # Create an entirely different company and user
    company3 = requests.post(f"{BASE}/companies", json={"name": "OtherCo"}).json()
    user3 = requests.post(f"{BASE}/users", json={
        "company_id": company3["id"],
        "email": "legit@otherco.com",
        "display_name": "Legit User"
    }).json()

    # OtherCo user trying to get a token for EvilCorp's call — must be denied!
    resp = requests.get(f"{BASE}/token", params={
        "user_id": user3["id"],
        "call_id": call2["id"]
    })
    assert resp.status_code == 403


def test_end_call(full_flow):
    """Test ending a call sets the ended_at timestamp."""
    call = full_flow["call"]
    resp = requests.post(f"{BASE}/calls/{call['id']}/end")
    assert resp.status_code == 200
    assert resp.json()["ended_at"] is not None

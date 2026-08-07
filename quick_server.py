from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import uvicorn
from pydantic import BaseModel
from livekit.api import AccessToken, VideoGrants
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TokenResponse(BaseModel):
    token: str
    livekit_url: str
    room_name: str

API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "wss://safe-call-platform-evar91qb.livekit.cloud")

@app.get("/token/demo", response_model=TokenResponse)
def get_demo_token(room: str = "testroom", name: str = None):
    display_name = name.strip() if name else f"Tester {uuid.uuid4().hex[:4]}"
    
    # Generate LiveKit Token securely
    grants = VideoGrants(room_join=True, room=room)
    token = (
        AccessToken(API_KEY, API_SECRET)
        .with_identity(display_name)
        .with_name(display_name)
        .with_grants(grants)
    )
    
    return TokenResponse(
        token=token.to_jwt(),
        livekit_url=LIVEKIT_URL,
        room_name=room
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

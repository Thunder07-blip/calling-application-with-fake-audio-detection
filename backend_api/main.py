from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from models import TokenResponse
import token_service
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("api_backend")

app = FastAPI(title="Safe Calling Platform API")

# Add CORS to allow Flutter web client to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LIVEKIT_URL = os.getenv("LIVEKIT_PUBLIC_URL", "ws://localhost:7880")

@app.get("/token", response_model=TokenResponse)
async def get_token(
    identity: str = Query(..., description="The user's identity"),
    room: str = Query("testroom", description="The room to join")
):
    logger.info(f"Token requested for identity={identity}, room={room}")
    try:
        # Generate token and return along with correct public LiveKit URL
        token = token_service.create_token(identity, room)
        return {"token": token, "livekit_url": LIVEKIT_URL}
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate token")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

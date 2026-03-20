import os
from livekit.api import AccessToken, VideoGrants
import logging

logger = logging.getLogger("api_backend.token_service")

# Keys should be loaded from environment variables
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

def create_token(identity: str, room: str) -> str:
    grant = VideoGrants(room=room, room_join=True, can_publish=True, can_subscribe=True)
    access_token = AccessToken(API_KEY, API_SECRET)
    access_token.with_grants(grant).with_identity(identity).with_name(identity)
    
    jwt_token = access_token.to_jwt()
    logger.info(f"Generated token for identity: {identity} in room: {room}")
    return jwt_token

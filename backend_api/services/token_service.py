import os
from livekit.api import AccessToken, VideoGrants
import logging

logger = logging.getLogger("backend_api.services.token_service")

API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")


def generate_livekit_token(identity: str, room: str, name: str = "") -> str:
    """
    Generate a secure LiveKit JWT token for a specific identity and room.

    Args:
        identity: The unique user identifier (UUID string recommended)
        room:     The LiveKit room name to grant access to
        name:     The human-readable display name (optional)

    Returns:
        A signed JWT string to pass directly to the LiveKit client SDK.
    """
    try:
        grants = VideoGrants(room_join=True, room=room)
        token = (
            AccessToken(API_KEY, API_SECRET)
            .with_identity(identity)
            .with_name(name or identity)
            .with_grants(grants)
        )
        return token.to_jwt()
    except Exception as e:
        logger.error(f"Token generation failed for identity={identity}, room={room}: {e}")
        raise

import asyncio
import os
import logging
import datetime
from livekit import rtc
from livekit.api import AccessToken, VideoGrants
from audio_processor import process_audio_frame

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ml_agent")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = os.getenv("ROOM_NAME", "testroom")

async def main():
    logger.info(f"Connecting to LiveKit at {LIVEKIT_URL} in room {ROOM_NAME}")

    # Generate token for the agent securely using environment variables
    grant = VideoGrants(room=ROOM_NAME, room_join=True, can_publish=False, can_subscribe=True, hidden=True)
    access_token = AccessToken(API_KEY, API_SECRET)
    access_token.with_grants(grant).with_identity("ml_agent").with_name("ML Agent")
    token = access_token.to_jwt()

    room = rtc.Room()

    @room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        logger.info(f"Subscribed to track {track.sid} from {participant.identity}")
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            asyncio.create_task(handle_audio_stream(track, participant.identity))

    async def handle_audio_stream(track: rtc.Track, identity: str):
        logger.info(f"Starting audio stream processing for {identity}")
        audio_stream = rtc.AudioStream(track)
        async for frame_event in audio_stream:
            energy_level = process_audio_frame(frame_event.frame)
            if energy_level is not None:
                current_time = datetime.datetime.now().isoformat()
                print(f"[{current_time}] {identity} {energy_level:.4f}")

    try:
        await room.connect(LIVEKIT_URL, token)
        logger.info("Successfully connected to the room")
        
        # Keep the agent running
        while True:
            await asyncio.sleep(60)
            logger.info("Agent is still running...")
            
    except Exception as e:
        logger.error(f"Failed to connect or error occurred: {e}")
    finally:
        await room.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

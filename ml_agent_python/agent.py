import asyncio
import os
import sys
import logging
import datetime
import numpy as np

# LiveKit for capturing WebRTC UDP bits natively
from livekit import rtc
from livekit.api import AccessToken, VideoGrants

# Configure logging visually
logging.basicConfig(level=logging.INFO, format='%(asctime)s - ML_AGENT - %(levelname)s - %(message)s')
logger = logging.getLogger("ml_agent")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = os.getenv("ROOM_NAME", "testroom")

# ═══════════════════════════════════════════════
# DEEPFAKE ML CONFIGURATION & LOADING
# ═══════════════════════════════════════════════
# We wrap torch to gracefully alert user if they forgot model.py
try:
    import torch
    from model import VoiceDetector
except ImportError as e:
    logger.error("=" * 70)
    logger.error(f"❌ Failed to load Neural Network: {e}")
    logger.error("Did you forget to copy 'model.py' to the ml_agent_python folder?")
    logger.error("The PyTorch '.pth' weights absolutely require the original class!")
    logger.error("=" * 70)
    sys.exit(1)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_PATH = "./models/best_voice_detector.pth"
SR = 16000
CHUNK_SAMPLES = 48000           # 3-second rolling window per speaker
UPDATE_SAMPLES = int(SR * 1.0)  # Run inference every 1 second (per user request)
THRESHOLD = 0.5
SILENCE_THRESHOLD = 0.0005

global_model = None

def load_ai_model():
    global global_model
    if not os.path.exists(MODEL_PATH):
        logger.error(f"❌ Model weights not found at {MODEL_PATH}")
        logger.error("Please place 'best_voice_detector.pth' in the models/ folder.")
        sys.exit(1)
        
    global_model = VoiceDetector().to(DEVICE)
    global_model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    global_model.eval()
    logger.info(f"✅ AI VoiceDetector Pipeline instantly deployed on {DEVICE.upper()}.")

def run_ml_inference(chunk_data: np.ndarray) -> float:
    """Passes a 3s float32 audio chunk through the neural net returning DeepFake probability."""
    with torch.no_grad():
        tensor = torch.from_numpy(chunk_data).unsqueeze(0).to(DEVICE)
        logits = global_model(tensor).squeeze()
        if logits.dim() == 0:
            logits = logits.unsqueeze(0)
        prob = torch.sigmoid(logits).item()
        return prob


# ═══════════════════════════════════════════════
# ASYNC MEDIA PIPELINE
# ═══════════════════════════════════════════════
async def main():
    load_ai_model()
    logger.info(f"Connecting to LiveKit Room: '{ROOM_NAME}' at {LIVEKIT_URL}")

    # The ML Agent needs an admin token to secretly lurk over everyone's streams silently
    grant = VideoGrants(room=ROOM_NAME, room_join=True, can_publish=False, can_subscribe=True, hidden=True)
    access_token = AccessToken(API_KEY, API_SECRET)
    access_token.with_grants(grant).with_identity("ai_monitor").with_name("AI Safety Monitor")
    token = access_token.to_jwt()

    room = rtc.Room()

    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        count = len(room.remote_participants)
        print(f"\n👥 [ROOM UPDATE] {participant.identity} joined. Total users in room: {count}\n", flush=True)

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        count = len(room.remote_participants)
        print(f"\n👋 [ROOM UPDATE] {participant.identity} left. Total users in room: {count}\n", flush=True)

    @room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"🎤 Intercepted independent audio stream from {participant.identity}")
            # Launch a STRICTLY ISOLATED async task for this specific speaker
            asyncio.create_task(handle_audio_stream(track, participant.identity))


    async def handle_audio_stream(track: rtc.Track, identity: str):
        audio_stream = rtc.AudioStream(track)
        
        # 100% Isolated 3-Second rolling buffer for exactly this user
        buffer_3s = np.zeros(CHUNK_SAMPLES, dtype=np.float32)
        accumlated_frames = []
        
        # We loop infinitely over incoming WebRTC binary UDP frames
        async for frame_event in audio_stream:
            # frame_event.frame.data is 16-bit PCM integer bytes natively
            # Converts to Normalized Float32 (-1.0 to 1.0) identical to test_realtime.py
            audio_data = np.frombuffer(frame_event.frame.data, dtype=np.int16).astype(np.float32) / 32768.0
            accumlated_frames.extend(audio_data.tolist())
            
            # Every 1.0 SECONDS we analyze the buffer
            if len(accumlated_frames) >= UPDATE_SAMPLES:
                new_data = np.array(accumlated_frames[:UPDATE_SAMPLES], dtype=np.float32)
                accumlated_frames = accumlated_frames[UPDATE_SAMPLES:]  # Keep leftover microseconds
                
                # Slide the rolling window left by 1 second, append the new latest second
                buffer_3s = np.roll(buffer_3s, -len(new_data))
                buffer_3s[-len(new_data):] = new_data
                
                # Check for Silence (Is the speaker actively talking right now?)
                mx = np.max(np.abs(buffer_3s))
                if mx < SILENCE_THRESHOLD:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] user {identity} silence", flush=True)
                    continue
                
                # Normalize chunk identically to the original test_realtime pipeline
                chunk = buffer_3s / (mx + 1e-6)
                
                # Hand it off to the PyTorch Neural Thread without blocking WebRTC!
                prob = await asyncio.to_thread(run_ml_inference, chunk.copy())
                
                # Terminal output requirement:
                if prob > THRESHOLD:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] user {identity} fake confidence {prob:.2f}", flush=True)
                else:
                    real_conf = 1.0 - prob
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] user {identity} real confidence {real_conf:.2f}", flush=True)


    try:
        await room.connect(LIVEKIT_URL, token)
        logger.info("✅ ML Agent deployed and actively monitoring all independent streams!")
        
        # Infinitely keep the Python agent alive
        while True:
            await asyncio.sleep(60)
            
    except Exception as e:
        logger.error(f"CRITICAL FAULT: {e}")
    finally:
        await room.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

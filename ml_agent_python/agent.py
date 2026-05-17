import asyncio
import os
import sys
import logging
import datetime
import numpy as np
import wave
import json
import struct
import httpx

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
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

RECORDINGS_DIR = "./recordings"
SAMPLE_RATE = 16000

# ═══════════════════════════════════════════════
# DEEPFAKE ML CONFIGURATION & LOADING
# ═══════════════════════════════════════════════
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
CHUNK_SAMPLES = 48000           # 3-second rolling window per speaker
UPDATE_SAMPLES = int(SAMPLE_RATE * 1.0)  # Run inference every 1 second
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
# RECORDING STATE
# ═══════════════════════════════════════════════
class RecordingSession:
    """Manages per-participant WAV file writers for a recording session."""
    def __init__(self, room: str, recording_id: str):
        self.room = room
        self.recording_id = recording_id
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(RECORDINGS_DIR, room, timestamp)
        os.makedirs(self.session_dir, exist_ok=True)
        self.writers: dict[str, wave.Wave_write] = {}  # identity -> WAV writer
        self.file_paths: dict[str, str] = {}
        logger.info(f"🎙 Recording session started → {self.session_dir}")

    def get_writer(self, identity: str) -> wave.Wave_write:
        """Get or create a WAV writer for a specific participant."""
        if identity not in self.writers:
            path = os.path.join(self.session_dir, f"{identity}.wav")
            w = wave.open(path, "wb")
            w.setnchannels(1)
            w.setsampwidth(2)       # 16-bit PCM
            w.setframerate(SAMPLE_RATE)
            self.writers[identity] = w
            self.file_paths[identity] = path
            logger.info(f"📂 Recording track for '{identity}' → {path}")
        return self.writers[identity]

    def write_audio(self, identity: str, float32_data: np.ndarray):
        """Write normalized float32 audio as int16 PCM to participant's WAV file."""
        writer = self.get_writer(identity)
        pcm = (float32_data * 32767).astype(np.int16)
        writer.writeframes(pcm.tobytes())

    def stop(self) -> list[str]:
        """Close all WAV writers and return list of saved file paths."""
        paths = []
        for identity, writer in self.writers.items():
            writer.close()
            paths.append(self.file_paths[identity])
            logger.info(f"✅ Saved recording: {self.file_paths[identity]}")
        self.writers.clear()
        return paths


# Global recording session (one at a time per agent instance)
active_recording: RecordingSession | None = None


async def notify_backend_stop(room: str, file_paths: list[str]):
    """Tell the backend the recording stopped and pass file paths for DB storage."""
    try:
        async with httpx.AsyncClient() as client:
            paths_str = ",".join(file_paths)
            await client.post(
                f"{BACKEND_URL}/recording/stop",
                params={"room": room, "file_paths": paths_str},
                timeout=5.0,
            )
    except Exception as e:
        logger.warning(f"[RECORDING] Could not notify backend of stop: {e}")


# ═══════════════════════════════════════════════
# ASYNC MEDIA PIPELINE
# ═══════════════════════════════════════════════
async def main():
    global active_recording

    load_ai_model()
    logger.info(f"Connecting to LiveKit Room: '{ROOM_NAME}' at {LIVEKIT_URL}")

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

    @room.on("data_received")
    def on_data_received(data: bytes, participant: rtc.RemoteParticipant | None, *args):
        """Handle recording control messages sent by the Flutter client via backend."""
        global active_recording
        try:
            msg = json.loads(data.decode("utf-8"))
            msg_type = msg.get("type")

            if msg_type == "recording_start":
                recording_id = msg.get("recording_id", "unknown")
                triggered_by = msg.get("triggered_by", "unknown")
                if active_recording is None:
                    active_recording = RecordingSession(ROOM_NAME, recording_id)
                    print(f"\n🔴 [RECORDING] STARTED by '{triggered_by}' (id={recording_id})\n", flush=True)
                else:
                    print(f"[RECORDING] Already recording, ignoring start signal.", flush=True)

            elif msg_type == "recording_stop":
                if active_recording is not None:
                    paths = active_recording.stop()
                    print(f"\n⏹ [RECORDING] STOPPED. {len(paths)} track(s) saved.\n", flush=True)
                    asyncio.create_task(notify_backend_stop(ROOM_NAME, paths))
                    active_recording = None
                else:
                    print("[RECORDING] Stop signal received but nothing was recording.", flush=True)

        except Exception as e:
            logger.warning(f"[DATA] Failed to parse data message: {e}")

    @room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"🎤 Intercepted independent audio stream from {participant.identity}")
            asyncio.create_task(handle_audio_stream(track, participant.identity))


    async def handle_audio_stream(track: rtc.Track, identity: str):
        audio_stream = rtc.AudioStream(track)
        
        buffer_3s = np.zeros(CHUNK_SAMPLES, dtype=np.float32)
        accumlated_frames = []
        
        async for frame_event in audio_stream:
            audio_data = np.frombuffer(frame_event.frame.data, dtype=np.int16).astype(np.float32) / 32768.0
            accumlated_frames.extend(audio_data.tolist())

            # ── RECORDING: write every raw frame if a session is active ──
            if active_recording is not None:
                active_recording.write_audio(identity, audio_data)
            
            # Every 1.0 SECONDS we analyze the buffer
            if len(accumlated_frames) >= UPDATE_SAMPLES:
                new_data = np.array(accumlated_frames[:UPDATE_SAMPLES], dtype=np.float32)
                accumlated_frames = accumlated_frames[UPDATE_SAMPLES:]
                
                buffer_3s = np.roll(buffer_3s, -len(new_data))
                buffer_3s[-len(new_data):] = new_data
                
                mx = np.max(np.abs(buffer_3s))
                if mx < SILENCE_THRESHOLD:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] user {identity} silence", flush=True)
                    continue
                
                chunk = buffer_3s / (mx + 1e-6)
                prob = await asyncio.to_thread(run_ml_inference, chunk.copy())
                
                rec_marker = " 🔴REC" if active_recording is not None else ""
                if prob > THRESHOLD:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] user {identity} fake confidence {prob:.2f}{rec_marker}", flush=True)
                else:
                    real_conf = 1.0 - prob
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] user {identity} real confidence {real_conf:.2f}{rec_marker}", flush=True)


    try:
        await room.connect(LIVEKIT_URL, token)
        logger.info("✅ ML Agent deployed and actively monitoring all independent streams!")
        
        while True:
            await asyncio.sleep(60)
            
    except Exception as e:
        logger.error(f"CRITICAL FAULT: {e}")
    finally:
        # Clean up any open recording on crash/disconnect
        if active_recording is not None:
            paths = active_recording.stop()
            await notify_backend_stop(ROOM_NAME, paths)
        await room.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

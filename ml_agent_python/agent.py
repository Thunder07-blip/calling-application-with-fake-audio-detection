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
import threading
from collections import deque

# LiveKit for capturing WebRTC UDP bits natively
from livekit import rtc
from livekit.api import AccessToken, VideoGrants

# Configure logging visually
logging.basicConfig(level=logging.INFO, format='%(asctime)s - ML_AGENT - %(levelname)s - %(message)s')
logger = logging.getLogger("ml_agent")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

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

# ═══════════════════════════════════════════════
# ACCURACY ENHANCEMENT CONFIG
# ═══════════════════════════════════════════════
SMOOTHING_WINDOW = 5            # Rolling average over last N predictions
VD_ENSEMBLE_WEIGHT = 0.4        # ResNet (Custom)
LCNN_ENSEMBLE_WEIGHT = 0.6      # Wav2Vec2 (HuggingFace)
ENSEMBLE_FAKE_THRESHOLD = 0.41  # Calibrated boundary between real and fake
SMOOTHING_WINDOW = 5            # Rolling average window size
UNANIMOUS_REQUIRED = False      # If True, BOTH models must agree to flag FAKE

# ═══════════════════════════════════════════════
# SPEAKER ENROLLMENT CONFIG
# ═══════════════════════════════════════════════
SPEAKER_MATCH_THRESHOLD = 0.75     # Cosine similarity to consider a match
SPEAKER_ENROLLED_VD_WEIGHT = 0.2   # VD weight when speaker is enrolled
SPEAKER_ENROLLED_LCNN_WEIGHT = 0.3 # LCNN weight when speaker is enrolled
SPEAKER_ENROLLED_SIM_WEIGHT = 0.5  # Speaker sim weight (anchors toward REAL)

global_model = None
lcnn_classifier = None
silero_vad_model = None
silero_get_speech_ts = None
speaker_verifier = None

def load_ai_model():
    global global_model, lcnn_classifier, silero_vad_model, silero_get_speech_ts
    
    # 1. Load Custom VoiceDetector (PyTorch)
    if not os.path.exists(MODEL_PATH):
        logger.error(f"❌ Model weights not found at {MODEL_PATH}")
        logger.error("Please place 'best_voice_detector.pth' in the models/ folder.")
        sys.exit(1)
        
    global_model = VoiceDetector().to(DEVICE)
    global_model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    global_model.eval()
    logger.info(f"✅ [MODEL 1/3] VoiceDetector deployed on {DEVICE.upper()}.")

    # 2. Load LCNN Classifier (HuggingFace Wav2Vec2)
    logger.info("[MODEL 2/3] Loading HuggingFace Wav2Vec2 deepfake detector...")
    from transformers import pipeline
    lcnn_classifier = pipeline(
        "audio-classification",
        model="garystafford/wav2vec2-deepfake-voice-detector",
        device=0 if DEVICE == "cuda" else -1
    )
    logger.info("✅ [MODEL 2/3] HuggingFace LCNN Pipeline deployed.")

    # 3. Load Silero VAD (Voice Activity Detection)
    logger.info("[MODEL 3/3] Loading Silero VAD for speech detection...")
    silero_vad_model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        trust_repo=True,
        force_reload=False
    )
    silero_get_speech_ts = utils[0]  # get_speech_timestamps function
    logger.info("✅ [MODEL 3/3] Silero VAD deployed.")
    
    # 4. Load Speaker Enrollment Verifier
    global speaker_verifier
    from speaker_verify import SpeakerVerifier
    speaker_verifier = SpeakerVerifier("./models/enrolled_speakers.pkl")
    logger.info(f"✅ [MODEL 4/4] Speaker Verifier: {speaker_verifier.enrolled_count()} speakers enrolled.")
    
    logger.info("=" * 60)
    logger.info("  ALL 4 MODELS LOADED SUCCESSFULLY")
    logger.info(f"  Ensemble weights: VD={VD_ENSEMBLE_WEIGHT}, LCNN={LCNN_ENSEMBLE_WEIGHT}")
    logger.info(f"  Smoothing window: {SMOOTHING_WINDOW} predictions")
    logger.info(f"  Unanimous mode: {UNANIMOUS_REQUIRED}")
    logger.info("=" * 60)


# Thread lock for Silero VAD (its internal RNN state is NOT thread-safe)
_vad_lock = threading.Lock()

def check_silero_vad(chunk_data: np.ndarray) -> bool:
    """Returns True if Silero VAD detects human speech in the chunk."""
    with _vad_lock:
        # Reset internal RNN state before each call to prevent cross-thread corruption
        silero_vad_model.reset_states()
        tensor = torch.from_numpy(chunk_data)
        # Silero VAD expects 16kHz mono audio
        speech_timestamps = silero_get_speech_ts(
            tensor, silero_vad_model,
            sampling_rate=SAMPLE_RATE,
            threshold=0.3,           # Lower = more sensitive
            min_speech_duration_ms=250,
            min_silence_duration_ms=100,
        )
        return len(speech_timestamps) > 0


def run_all_models(chunk_data: np.ndarray) -> tuple[float, float, bool, str, float]:
    """
    Passes audio chunk through Silero VAD, both deepfake detectors, and speaker verifier.
    Returns (vd_fake_prob, lcnn_fake_prob, has_speech, matched_speaker, speaker_sim).
    """
    # Step 1: Silero VAD gate — is there actual human speech?
    has_speech = check_silero_vad(chunk_data)
    if not has_speech:
        return 0.0, 0.0, False, None, 0.0
    
    # Step 2: VoiceDetector Inference
    with torch.no_grad():
        tensor = torch.from_numpy(chunk_data).unsqueeze(0).to(DEVICE)
        logits = global_model(tensor).squeeze()
        if logits.dim() == 0:
            logits = logits.unsqueeze(0)
        vd_prob = torch.sigmoid(logits).item()
        
    # Step 3: LCNN Inference
    preds = lcnn_classifier({"array": chunk_data, "sampling_rate": SAMPLE_RATE})
    
    # Parse LCNN scores
    score_map = {}
    for p in preds:
        lbl = p["label"].lower()
        if lbl in ("real", "bonafide", "genuine"):
            score_map["real"] = p["score"]
        elif lbl in ("fake", "spoof", "synthetic"):
            score_map["fake"] = p["score"]
            
    if "fake" not in score_map:
        sorted_preds = sorted(preds, key=lambda x: x["score"], reverse=True)
        top_lbl = sorted_preds[0]["label"].lower()
        score_map["real"] = sorted_preds[0]["score"] if "real" in top_lbl or "bona" in top_lbl else sorted_preds[1]["score"]
        score_map["fake"] = 1.0 - score_map["real"]

    lcnn_prob = score_map.get("fake", 0.0)
    
    # Step 4: Speaker Verification
    matched_speaker, speaker_sim = speaker_verifier.verify(chunk_data)
    
    return vd_prob, lcnn_prob, True, matched_speaker, speaker_sim


# ═══════════════════════════════════════════════
# TEMPORAL SMOOTHING (per-user rolling history)
# ═══════════════════════════════════════════════
class SpeakerHistory:
    """Maintains a rolling window of predictions for temporal smoothing per speaker."""
    def __init__(self, window_size: int = SMOOTHING_WINDOW):
        self.vd_history: deque[float] = deque(maxlen=window_size)
        self.lcnn_history: deque[float] = deque(maxlen=window_size)
        self.sim_history: deque[float] = deque(maxlen=window_size)
        self.last_matched_speaker: str | None = None

    def add(self, vd_prob: float, lcnn_prob: float, sim: float, matched_speaker: str | None):
        self.vd_history.append(vd_prob)
        self.lcnn_history.append(lcnn_prob)
        self.sim_history.append(sim)
        if matched_speaker:
            self.last_matched_speaker = matched_speaker

    def smoothed_vd(self) -> float:
        return sum(self.vd_history) / len(self.vd_history) if self.vd_history else 0.0

    def smoothed_lcnn(self) -> float:
        return sum(self.lcnn_history) / len(self.lcnn_history) if self.lcnn_history else 0.0
        
    def smoothed_sim(self) -> float:
        return sum(self.sim_history) / len(self.sim_history) if self.sim_history else 0.0

    def ensemble_score(self) -> float:
        """Weighted ensemble of the smoothed probabilities."""
        avg_sim = self.smoothed_sim()
        if self.last_matched_speaker and avg_sim > SPEAKER_MATCH_THRESHOLD:
            return (self.smoothed_vd() * SPEAKER_ENROLLED_VD_WEIGHT +
                    self.smoothed_lcnn() * SPEAKER_ENROLLED_LCNN_WEIGHT +
                    (1.0 - avg_sim) * SPEAKER_ENROLLED_SIM_WEIGHT)
        else:
            return (self.smoothed_vd() * VD_ENSEMBLE_WEIGHT) + (self.smoothed_lcnn() * LCNN_ENSEMBLE_WEIGHT)

    def ensemble_verdict(self) -> tuple[str, float]:
        """Returns (verdict_string, confidence_percent)."""
        score = self.ensemble_score()
        if UNANIMOUS_REQUIRED:
            # Both models must independently agree it's fake
            both_fake = self.smoothed_vd() > THRESHOLD and self.smoothed_lcnn() > THRESHOLD
            if both_fake:
                return "FAKE", score * 100
            else:
                return "REAL", (1.0 - score) * 100
        else:
            if score > ENSEMBLE_FAKE_THRESHOLD:
                return "FAKE", score * 100
            else:
                return "REAL", (1.0 - score) * 100

# Per-speaker history storage
speaker_histories: dict[str, SpeakerHistory] = {}


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

    grant = VideoGrants(room=ROOM_NAME, room_join=True, can_publish=True, can_subscribe=True, hidden=True)
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
        # Clean up speaker history on disconnect
        speaker_histories.pop(participant.identity, None)

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
        was_silent = False  # Track silence state to avoid spamming

        # Initialize per-speaker smoothing history
        if identity not in speaker_histories:
            speaker_histories[identity] = SpeakerHistory()
        history = speaker_histories[identity]
        
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
                
                # Basic amplitude check (fast pre-filter before expensive VAD)
                mx = np.max(np.abs(buffer_3s))
                if mx < SILENCE_THRESHOLD:
                    if not was_silent:
                        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] user {identity} ─ 🔇 went silent", flush=True)
                        was_silent = True
                    continue
                
                chunk = buffer_3s / (mx + 1e-6)
                
                # ── Run Silero VAD + both deepfake models + Speaker Verifier ──
                vd_prob, lcnn_prob, has_speech, matched_speaker, speaker_sim = await asyncio.to_thread(run_all_models, chunk.copy())
                
                if not has_speech:
                    if not was_silent:
                        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] user {identity} ─ 🔇 no speech (VAD filtered)", flush=True)
                        was_silent = True
                    continue

                # Speech detected! Mark as active again
                if was_silent:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] user {identity} ─ 🎙 speaking again", flush=True)
                    was_silent = False

                # ── Temporal smoothing ──
                history.add(vd_prob, lcnn_prob, speaker_sim, matched_speaker)
                smoothed_vd = history.smoothed_vd()
                smoothed_lcnn = history.smoothed_lcnn()
                ensemble_verdict, ensemble_conf = history.ensemble_verdict()
                ensemble_score = history.ensemble_score()
                
                rec_marker = " 🔴REC" if active_recording is not None else ""
                time_str = datetime.datetime.now().strftime('%H:%M:%S')
                n_samples = len(history.vd_history)
                
                # ── Per-model raw + smoothed verdicts ──
                def fmt_verdict(raw: float, smoothed: float, name: str) -> str:
                    v = "FAKE" if smoothed > THRESHOLD else "REAL"
                    c = smoothed * 100 if v == "FAKE" else (1.0 - smoothed) * 100
                    return f"[{time_str}] user {identity} ─ {name:<14} ─ {v} ({c:5.1f}%) [raw={raw:.2f} avg={smoothed:.2f}]"

                print(fmt_verdict(vd_prob, smoothed_vd, "VoiceDetector"), flush=True)
                print(fmt_verdict(lcnn_prob, smoothed_lcnn, "LCNN(Wav2Vec2)"), flush=True)
                
                if matched_speaker and history.smoothed_sim() > SPEAKER_MATCH_THRESHOLD:
                    print(f"[{time_str}] user {identity} ─ SpeakerMatch   ─ 🔑 {matched_speaker.upper()} (sim={speaker_sim:.2f} avg={history.smoothed_sim():.2f})", flush=True)
                elif speaker_sim > 0.1:
                    print(f"[{time_str}] user {identity} ─ SpeakerMatch   ─ ❌ No match (sim={speaker_sim:.2f} avg={history.smoothed_sim():.2f})", flush=True)
                
                # ── Ensemble final verdict ──
                emoji = "🚨" if ensemble_verdict == "FAKE" else "✅"
                boost_str = " [enrolled_boost]" if history.last_matched_speaker and history.smoothed_sim() > SPEAKER_MATCH_THRESHOLD else ""
                
                print(
                    f"[{time_str}] user {identity} ─ {'ENSEMBLE':<14} ─ {emoji} {ensemble_verdict} "
                    f"({ensemble_conf:5.1f}%) [n={n_samples}]{boost_str}{rec_marker}",
                    flush=True
                )
                print("─" * 70, flush=True)
                
                # ── Broadcast to Flutter via WebRTC Data Channel ──
                try:
                    verdict_status = "REAL"
                    if ensemble_score >= 0.45:
                        verdict_status = "FAKE"
                    elif ensemble_score >= 0.35:
                        verdict_status = "SUSPICIOUS"

                    payload = json.dumps({
                        "type": "ml_verdict",
                        "identity": identity,
                        "verdict": verdict_status,
                        "confidence": ensemble_conf,
                        "speaker_match": history.last_matched_speaker if history.smoothed_sim() > SPEAKER_MATCH_THRESHOLD else None
                    }).encode("utf-8")
                    
                    if room and room.local_participant:
                        await room.local_participant.publish_data(payload, reliable=True)
                except Exception as e:
                    print(f"[{time_str}] ⚠️ Failed to broadcast ml_verdict: {e}", flush=True)


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

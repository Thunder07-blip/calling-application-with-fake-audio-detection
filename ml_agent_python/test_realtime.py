"""
test_realtime.py — Live PC Microphone Deepfake Detection
==========================================================
Continuously records from your microphone, buffers the last 3 seconds
of audio, and runs inference every 0.5 seconds.
"""

import sys
import os
import time
import queue
import numpy as np
import torch
import sounddevice as sd

sys.path.insert(0, os.path.dirname(__file__))
from model import VoiceDetector

# ═══════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════
DEVICE          = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_PATH      = "./models/best_voice_detector.pth"
SR              = 16000
CHUNK_SAMPLES   = 48000           # 3-second window
UPDATE_SAMPLES  = int(SR * 0.5)   # Run inference every 0.5 seconds
THRESHOLD       = 0.5

# Queues for passing audio chunks between threads
audio_q = queue.Queue()

# ═══════════════════════════════════════════════
# AUDIO CALLBACK
# ═══════════════════════════════════════════════
def audio_callback(indata, frames, time_info, status):
    """Called by sounddevice whenever a new chunk of mic data arrives."""
    if status:
        print(f"Audio Status: {status}")
    # Push the mono float32 data into the queue
    audio_q.put(indata.copy().squeeze())


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════
def main():
    if not os.path.exists(MODEL_PATH):
        print(f"[FAIL] Model not found at {MODEL_PATH}")
        sys.exit(1)

    print(f"\n{'='*65}")
    print(f"  Live Real-Time Voice Detector")
    print(f"  Model  : {MODEL_PATH}")
    print(f"  Device : {DEVICE}")
    print(f"{'='*65}\n")

    # 0. Print Available Audio Devices
    ACTIVE_MIC_ID = 2
    print("  🎙️  Available Microphones:")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:  # Only show input devices
            marker = "➡️" if i == ACTIVE_MIC_ID else "  "
            print(f"    {marker} [{i}] {dev['name']} (Channels: {dev['max_input_channels']})")
    print("\n")

    # 1. Load Model
    model = VoiceDetector().to(DEVICE)
    model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    model.eval()
    print(f"  [OK] Model loaded. Warming up GPU...")
    
    # Run a dummy batch to warm up CUDA
    with torch.no_grad():
        if DEVICE == "cuda":
            _ = model(torch.zeros(1, CHUNK_SAMPLES, device=DEVICE))
    
    print(f"  [OK] GPU ready.\n")
    print(f"🎤 Speak into the microphone! (Press Ctrl+C to stop)\n")

    # Rolling buffer holding the most recent 3 seconds of audio
    buffer_3s = np.zeros(CHUNK_SAMPLES, dtype=np.float32)

    # 2. Start Microphone Stream
    try:
        # We request updates in small blocks (e.g. 0.5s)
        print(f"  [INFO] Microphone active with Device ID: {ACTIVE_MIC_ID}")
        with sd.InputStream(device=ACTIVE_MIC_ID, samplerate=SR, channels=1, dtype='float32',
                            blocksize=UPDATE_SAMPLES, callback=audio_callback):
            while True:
                # Get the latest 0.5s block
                new_data = audio_q.get()
                
                # Shift buffer left by UPDATE_SAMPLES, and append the new_data to the end
                buffer_3s = np.roll(buffer_3s, -len(new_data))
                buffer_3s[-len(new_data):] = new_data

                # Check volume level
                mx = np.max(np.abs(buffer_3s))
                if mx < 0.0005:  # Extemely low threshold
                    print(f"\r  [SILENCE] Waiting for voice... (Vol: {mx:.5f})          ", end="", flush=True)
                    continue

                # Normalization (identical to training pipeline)
                chunk = buffer_3s / (mx + 1e-6)

                # Inference
                with torch.no_grad():
                    tensor = torch.from_numpy(chunk).unsqueeze(0).to(DEVICE) # [1, 48000]
                    logits = model(tensor).squeeze()
                    if logits.dim() == 0:
                        logits = logits.unsqueeze(0)
                    prob = torch.sigmoid(logits).item()

                # Visualizing the output
                bar_len  = int(prob * 10)
                prob_bar = "#" * bar_len + "-" * (10 - bar_len)
                
                if prob > THRESHOLD:
                    verdict = "🤖 FAKE"
                else:
                    verdict = "👤 REAL"

                print(f"\r  {verdict:<8s} | Prob: [{prob_bar}] {prob:0.3f} | Vol: {mx:.3f}   ", end="", flush=True)

    except KeyboardInterrupt:
        print("\n\n  🛑 Live stream stopped.")


if __name__ == "__main__":
    main()

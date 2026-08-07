import os
import subprocess
import glob
import numpy as np
import librosa
import torch
from tqdm import tqdm
import imageio_ffmpeg
import math

# Get local ffmpeg executable
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

def load_audio(filepath, sr=16000):
    """Loads audio, converting to temporary wav if needed."""
    if filepath.endswith('.wav'):
        y, _ = librosa.load(filepath, sr=sr)
        return y
    
    # Use ffmpeg to convert to a temporary wav file
    temp_wav = "temp_load.wav"
    try:
        subprocess.run([
            FFMPEG_EXE, "-y", "-i", filepath, 
            "-ar", str(sr), "-ac", "1", temp_wav
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        y, _ = librosa.load(temp_wav, sr=sr)
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
    return y



def main():
    SR = 16000
    TARGET_SECONDS = 1800 # 30 minutes
    CHUNK_SAMPLES = SR * 3 # 3-second windows
    
    print("Preparing Data for Fine-Tuning...")
    
    # ── 1. REAL DATA COLLECTION ──
    print("\nGathering 30 mins of REAL data...")
    real_audio = []
    real_duration = 0.0
    
    # Priority files
    priority_real = [
        "real_recordinsg/sajal-intro.aac",
        "real_recordinsg/raj-intro.mp3"
    ]
    
    for f in priority_real:
        if not os.path.exists(f):
            print(f"Warning: {f} not found.")
            continue
        y = load_audio(f, sr=SR)
        real_audio.append(y)
        real_duration += len(y) / SR
        print(f"  + Added {f} ({len(y)/SR:.1f}s)")
        
    print(f"  Current Real Duration: {real_duration:.1f}s")
    
    # Add partial long recording to fill the gap
    if real_duration < TARGET_SECONDS:
        fill_needed = TARGET_SECONDS - real_duration
        fill_file = "real_recordinsg/Call recording Sajal Patil_260416_181003.m4a"
        print(f"  Need {fill_needed:.1f}s more. Extracting from {fill_file}...")
        y = load_audio(fill_file, sr=SR)
        samples_needed = int(fill_needed * SR)
        y = y[:samples_needed]
        real_audio.append(y)
        real_duration += len(y) / SR
        print(f"  + Sliced {len(y)/SR:.1f}s")
        
    # Combine and chunk
    real_combined = np.concatenate(real_audio)
    real_chunks = []
    print("  Chunking real audio into 3-second windows...")
    for i in range(0, len(real_combined) - CHUNK_SAMPLES, CHUNK_SAMPLES):
        real_chunks.append(real_combined[i:i+CHUNK_SAMPLES])
    
    # ── 2. FAKE DATA COLLECTION ──
    print("\nGathering 30 mins of FAKE data...")
    fake_audio = []
    fake_files = glob.glob("fake_call_recordins/*.*")
    
    for f in fake_files:
        if not f.endswith(('.mp3', '.m4a', '.mp4', '.aac', '.mpeg')):
            continue
        y = load_audio(f, sr=SR)
        fake_audio.append(y)
        
    fake_combined = np.concatenate(fake_audio)
    fake_duration = len(fake_combined) / SR
    print(f"  Found {fake_duration:.1f}s of fake data.")
    
    # Loop and augment if we need more to reach 30 mins
    if fake_duration < TARGET_SECONDS:
        print(f"  Looping data to reach {TARGET_SECONDS}s...")
        repeats = math.ceil(TARGET_SECONDS / fake_duration)
        fake_combined = np.tile(fake_combined, repeats)
        
    # Exactly slice to 30 mins
    fake_combined = fake_combined[: int(TARGET_SECONDS * SR)]
    fake_duration = len(fake_combined) / SR
    print(f"  Final Fake Duration: {fake_duration:.1f}s")
    
    fake_chunks = []
    print("  Chunking fake audio into 3-second windows...")
    for i in range(0, len(fake_combined) - CHUNK_SAMPLES, CHUNK_SAMPLES):
        fake_chunks.append(fake_combined[i:i+CHUNK_SAMPLES])
        
    # ── 3. FEATURE EXTRACTION ──
    print(f"\nPackaging Raw Audio Chunks ({len(real_chunks)} real, {len(fake_chunks)} fake)...")
    
    features = []
    labels = []
    
    for chunk in tqdm(real_chunks, desc="Real chunks"):
        features.append(chunk) # Save raw audio!
        labels.append(0.0) # REAL = 0.0
        
    for chunk in tqdm(fake_chunks, desc="Fake chunks"):
        features.append(chunk) # Save raw audio!
        labels.append(1.0) # FAKE = 1.0
        
    # ── 4. SAVE DATASET ──
    X = torch.tensor(np.array(features), dtype=torch.float32)
    y = torch.tensor(np.array(labels), dtype=torch.float32)
    
    print(f"\nSaving dataset: X shape {X.shape}, y shape {y.shape}")
    torch.save({"X": X, "y": y}, "training_data.pt")
    print("Done! Dataset saved as training_data.pt")

if __name__ == "__main__":
    main()

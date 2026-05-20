"""
calibrate_threshold.py — Find the optimal threshold for the VoiceDetector ensemble
==================================================================================
Runs inference on all real and fake recordings, plots the score distributions,
and determines the optimal threshold for separating real from fake.
"""

import os
import glob
import numpy as np
import torch
import logging
from transformers import pipeline
import warnings
warnings.filterwarnings("ignore")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("calibrate")

from model import VoiceDetector
from speaker_verify import load_audio_universal

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 48000  # 3 seconds

def load_models():
    """Load VD and LCNN models"""
    print("Loading models...")
    # 1. VoiceDetector
    vd = VoiceDetector().to(DEVICE)
    model_path = "./models/best_voice_detector.pth"
    if not os.path.exists(model_path):
        model_path = "./models/baseline_backup/best_voice_detector.pth"
    
    vd.load_state_dict(torch.load(model_path, map_location=DEVICE))
    vd.eval()
    
    # 2. LCNN
    lcnn = pipeline(
        "audio-classification",
        model="garystafford/wav2vec2-deepfake-voice-detector",
        device=0 if DEVICE == "cuda" else -1
    )
    
    return vd, lcnn

def process_chunk(chunk, vd_model, lcnn_model):
    """Run inference on a single 3s chunk"""
    # Normalize chunk like in agent.py
    mx = np.max(np.abs(chunk))
    if mx < 0.0005:  # silence
        return None, None
        
    norm_chunk = chunk / (mx + 1e-6)
    
    # VD Prediction
    with torch.no_grad():
        tensor = torch.from_numpy(norm_chunk).unsqueeze(0).to(DEVICE)
        logits = vd_model(tensor).squeeze()
        if logits.dim() == 0: logits = logits.unsqueeze(0)
        vd_prob = torch.sigmoid(logits).item()
        
    # LCNN Prediction
    preds = lcnn_model({"array": norm_chunk, "sampling_rate": SAMPLE_RATE})
    
    score_map = {}
    for p in preds:
        lbl = p["label"].lower()
        if lbl in ("real", "bonafide", "genuine"): score_map["real"] = p["score"]
        elif lbl in ("fake", "spoof", "synthetic"): score_map["fake"] = p["score"]
            
    if "fake" not in score_map:
        sorted_preds = sorted(preds, key=lambda x: x["score"], reverse=True)
        top_lbl = sorted_preds[0]["label"].lower()
        score_map["real"] = sorted_preds[0]["score"] if "real" in top_lbl or "bona" in top_lbl else sorted_preds[1]["score"]
        score_map["fake"] = 1.0 - score_map["real"]

    lcnn_prob = score_map.get("fake", 0.0)
    return vd_prob, lcnn_prob

def analyze_file(filepath, vd_model, lcnn_model):
    """Analyze all chunks in a file and return average score"""
    try:
        audio = load_audio_universal(filepath)
    except Exception as e:
        print(f"  Error loading {filepath}: {e}")
        return None
        
    chunks = []
    hop = int(SAMPLE_RATE * 1.5)  # 1.5s hop for dense sampling
    for start in range(0, len(audio) - CHUNK_SAMPLES, hop):
        chunk = audio[start:start + CHUNK_SAMPLES]
        vd, lcnn = process_chunk(chunk, vd_model, lcnn_model)
        if vd is not None:
            chunks.append((vd, lcnn))
            
    if not chunks:
        # Try processing whatever we have if it's shorter than 3s
        if len(audio) > 1600:
            padded = np.zeros(CHUNK_SAMPLES, dtype=np.float32)
            padded[:len(audio)] = audio
            vd, lcnn = process_chunk(padded, vd_model, lcnn_model)
            if vd is not None:
                chunks.append((vd, lcnn))
                
    if not chunks:
        return None
        
    avg_vd = sum(c[0] for c in chunks) / len(chunks)
    avg_lcnn = sum(c[1] for c in chunks) / len(chunks)
    
    # Standard ensemble score
    ensemble = (avg_vd * 0.4) + (avg_lcnn * 0.6)
    
    return {
        'vd': avg_vd,
        'lcnn': avg_lcnn,
        'ensemble': ensemble,
        'chunks': len(chunks)
    }

def find_best_threshold(real_scores, fake_scores):
    """Find threshold that maximizes accuracy"""
    best_thresh = 0.5
    best_acc = 0
    
    # Test thresholds from 0.05 to 0.95
    for t in np.arange(0.05, 0.96, 0.01):
        real_correct = sum(1 for s in real_scores if s <= t)
        fake_correct = sum(1 for s in fake_scores if s > t)
        
        acc = (real_correct + fake_correct) / (len(real_scores) + len(fake_scores))
        
        if acc > best_acc:
            best_acc = acc
            best_thresh = t
            
    return best_thresh, best_acc

def main():
    print("=" * 60)
    print("VoiceDetector Ensemble Threshold Calibration")
    print("=" * 60)
    
    vd_model, lcnn_model = load_models()
    
    real_dir = "../real_recordinsg"
    fake_dir = "../fake_call_recordins"
    
    real_files = []
    for ext in ["*.mp3", "*.aac", "*.m4a", "*.mp4", "*.mpeg", "*.wav"]:
        real_files.extend(glob.glob(os.path.join(real_dir, ext)))
        
    fake_files = []
    for ext in ["*.mp3", "*.aac", "*.m4a", "*.mp4", "*.mpeg", "*.wav"]:
        fake_files.extend(glob.glob(os.path.join(fake_dir, ext)))
        
    print(f"\nFound {len(real_files)} real recordings and {len(fake_files)} fake recordings.")
    
    real_scores = []
    fake_scores = []
    
    print("\n--- Processing REAL recordings ---")
    for f in real_files:
        name = os.path.basename(f)
        print(f"Analyzing {name}...", end=" ", flush=True)
        res = analyze_file(f, vd_model, lcnn_model)
        if res:
            real_scores.append(res['ensemble'])
            print(f"Score: {res['ensemble']:.3f} (VD:{res['vd']:.2f}, LCNN:{res['lcnn']:.2f})")
        else:
            print("Failed.")
            
    print("\n--- Processing FAKE recordings ---")
    for f in fake_files:
        name = os.path.basename(f)
        print(f"Analyzing {name}...", end=" ", flush=True)
        res = analyze_file(f, vd_model, lcnn_model)
        if res:
            fake_scores.append(res['ensemble'])
            print(f"Score: {res['ensemble']:.3f} (VD:{res['vd']:.2f}, LCNN:{res['lcnn']:.2f})")
        else:
            print("Failed.")
            
    if not real_scores or not fake_scores:
        print("\n❌ Missing scores, cannot calibrate.")
        return
        
    # Analyze
    opt_t, max_acc = find_best_threshold(real_scores, fake_scores)
    
    print("\n" + "=" * 60)
    print("CALIBRATION RESULTS")
    print("=" * 60)
    print(f"REAL scores -> Min: {min(real_scores):.3f} | Max: {max(real_scores):.3f} | Avg: {np.mean(real_scores):.3f}")
    print(f"FAKE scores -> Min: {min(fake_scores):.3f} | Max: {max(fake_scores):.3f} | Avg: {np.mean(fake_scores):.3f}")
    
    print(f"\n⭐ Optimal Threshold: {opt_t:.2f}")
    print(f"⭐ Max Accuracy:    {max_acc*100:.1f}%")
    
    if max(real_scores) < min(fake_scores):
        print("\n✅ Perfect separation! Your models easily distinguish the two classes.")
        suggested = (max(real_scores) + min(fake_scores)) / 2
        print(f"Suggested threshold: {suggested:.2f} (midpoint between max real and min fake)")
    else:
        print("\n⚠️ Overlap detected! Some fakes look real or reals look fake.")
        print("Consider adjusting ENSEMBLE_FAKE_THRESHOLD in agent.py or relying heavily on Speaker Enrollment.")
        
if __name__ == "__main__":
    main()

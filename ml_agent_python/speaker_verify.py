"""
speaker_verify.py — Speaker Verification via Resemblyzer
=========================================================
Uses a pretrained d-vector speaker encoder to verify whether incoming
audio matches any enrolled (known) speaker.

The encoder produces a 256-dimensional embedding per utterance.
Cosine similarity between embeddings determines if voices match.

Usage (standalone test):
    python speaker_verify.py --test --audio ../real_recordinsg/sajal-intro.aac
"""

import os
import pickle
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger("ml_agent.speaker_verify")

# Lazy-loaded globals to avoid import overhead at module level
_encoder = None
_encoder_lock = None


def _get_encoder():
    """Lazy-load Resemblyzer encoder on first use."""
    global _encoder, _encoder_lock
    if _encoder_lock is None:
        import threading
        _encoder_lock = threading.Lock()

    with _encoder_lock:
        if _encoder is None:
            from resemblyzer import VoiceEncoder
            _encoder = VoiceEncoder(device="cpu")
            logger.info("✅ Resemblyzer VoiceEncoder loaded (CPU)")
        return _encoder


def load_audio_universal(filepath: str, target_sr: int = 16000) -> np.ndarray:
    """
    Load any audio format (mp3, aac, m4a, mp4, mpeg, wav) and return
    a mono float32 numpy array resampled to target_sr.

    Uses imageio_ffmpeg to ensure ffmpeg binaries are available across platforms.
    """
    import subprocess
    import imageio_ffmpeg
    
    filepath = str(filepath)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # We want 16kHz mono float32 PCM output directly from ffmpeg to stdout
    cmd = [
        ffmpeg_exe,
        "-i", filepath,
        "-f", "f32le",     # 32-bit float little endian
        "-ac", "1",        # Mono
        "-ar", str(target_sr), # Sample rate
        "-"                # Output to stdout
    ]
    
    try:
        # Run ffmpeg, capture stdout
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        # Convert raw bytes back into float32 array
        samples = np.frombuffer(process.stdout, dtype=np.float32).copy()
        
        # Prevent completely silent samples from returning pure 0.0
        # (adds tiny epsilon so models don't crash on division by zero)
        if len(samples) > 0 and np.max(np.abs(samples)) == 0.0:
            samples += 1e-9
            
        return samples
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode('utf-8', errors='ignore')
        raise RuntimeError(f"Failed to load {filepath} with FFmpeg.\nError: {err_msg}")


def extract_embedding(audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """
    Extract a 256-dim speaker embedding from audio waveform.

    For long audio (>10s), splits into overlapping windows and averages
    the embeddings for a more robust fingerprint.
    """
    encoder = _get_encoder()
    from resemblyzer import preprocess_wav

    # Resemblyzer's preprocess_wav expects (samples,) float array
    # It handles its own normalization and trimming
    processed = preprocess_wav(audio, source_sr=sample_rate)

    if len(processed) < 1600:  # Less than 0.1s — too short
        raise ValueError("Audio too short for embedding extraction (< 0.1s)")

    # For short clips, use single embedding
    if len(processed) < sample_rate * 10:  # < 10 seconds
        embed = encoder.embed_utterance(processed)
    else:
        # For longer clips, use sliding window for more robust embedding
        # embed_utterance with multiple partial utterances
        chunk_len = sample_rate * 3  # 3-second windows
        hop = sample_rate * 1        # 1-second hop (2s overlap)
        chunks = []
        for start in range(0, len(processed) - chunk_len, hop):
            chunks.append(processed[start:start + chunk_len])

        if not chunks:
            chunks = [processed]

        # Get embedding for each chunk and average
        embeds = [encoder.embed_utterance(c) for c in chunks]
        embed = np.mean(embeds, axis=0)

    # L2 normalize
    embed = embed / (np.linalg.norm(embed) + 1e-8)
    return embed


class SpeakerVerifier:
    """
    Manages enrolled speaker embeddings and performs real-time verification.

    Enrollment data is stored as a pickle file containing:
        {speaker_name: np.ndarray(256,)}
    """

    def __init__(self, enrollment_path: str = "./models/enrolled_speakers.pkl"):
        self.enrollment_path = enrollment_path
        self.enrolled: dict[str, np.ndarray] = {}
        self._load_enrollments()

    def _load_enrollments(self):
        """Load enrolled speakers from disk."""
        if os.path.exists(self.enrollment_path):
            with open(self.enrollment_path, "rb") as f:
                self.enrolled = pickle.load(f)
            logger.info(f"Loaded {len(self.enrolled)} enrolled speaker(s): {list(self.enrolled.keys())}")
        else:
            logger.info("No enrolled speakers found. Run enroll_speaker.py to enroll.")
            self.enrolled = {}

    def _save_enrollments(self):
        """Save enrolled speakers to disk."""
        os.makedirs(os.path.dirname(self.enrollment_path), exist_ok=True)
        with open(self.enrollment_path, "wb") as f:
            pickle.dump(self.enrolled, f)

    def enroll(self, name: str, audio: np.ndarray, sample_rate: int = 16000):
        """Enroll a speaker by extracting and storing their embedding."""
        embed = extract_embedding(audio, sample_rate)
        self.enrolled[name.lower()] = embed
        self._save_enrollments()
        logger.info(f"✅ Enrolled speaker '{name}' (embedding shape: {embed.shape})")

    def enroll_from_file(self, name: str, filepath: str):
        """Enroll a speaker from an audio file (any format)."""
        audio = load_audio_universal(filepath)
        self.enroll(name, audio)

    def remove(self, name: str):
        """Remove an enrolled speaker."""
        name = name.lower()
        if name in self.enrolled:
            del self.enrolled[name]
            self._save_enrollments()
            logger.info(f"Removed speaker '{name}'")
        else:
            logger.warning(f"Speaker '{name}' not found in enrollments")

    def enrolled_count(self) -> int:
        return len(self.enrolled)

    def list_enrolled(self) -> list[str]:
        return list(self.enrolled.keys())

    def verify(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> tuple:
        """
        Compare an audio chunk against all enrolled speakers.

        Returns:
            (matched_name: str | None, similarity: float)
            - ("sajal", 0.87) if match found
            - (None, 0.31) if no match exceeds threshold
        """
        if not self.enrolled:
            return None, 0.0

        try:
            chunk_embed = extract_embedding(audio_chunk, sample_rate)
        except ValueError:
            return None, 0.0

        best_name = None
        best_sim = -1.0

        for name, enrolled_embed in self.enrolled.items():
            # Cosine similarity (both are L2-normalized, so dot product = cosine sim)
            sim = float(np.dot(chunk_embed, enrolled_embed))
            if sim > best_sim:
                best_sim = sim
                best_name = name

        return best_name, best_sim

    def is_enrolled_speaker(self, audio_chunk: np.ndarray,
                            threshold: float = 0.75,
                            sample_rate: int = 16000) -> tuple:
        """
        Quick check: is this a known speaker above the match threshold?

        Returns:
            (is_known: bool, speaker_name: str, confidence: float)
        """
        name, sim = self.verify(audio_chunk, sample_rate)
        if name and sim >= threshold:
            return True, name, sim
        return False, "", sim


# ═══════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="Test speaker verification")
    parser.add_argument("--test", action="store_true", help="Run verification test")
    parser.add_argument("--audio", type=str, required=True, help="Path to audio file to test")
    parser.add_argument("--enrollment", type=str, default="./models/enrolled_speakers.pkl",
                        help="Path to enrollment file")
    args = parser.parse_args()

    if args.test:
        verifier = SpeakerVerifier(args.enrollment)
        if verifier.enrolled_count() == 0:
            print("❌ No speakers enrolled. Run enroll_speaker.py first.")
        else:
            print(f"Enrolled speakers: {verifier.list_enrolled()}")
            audio = load_audio_universal(args.audio)

            # Test on first 3 seconds
            chunk = audio[:48000] if len(audio) >= 48000 else audio
            name, sim = verifier.verify(chunk)

            print(f"\n{'='*50}")
            print(f"Audio: {args.audio}")
            print(f"Best match: {name} (similarity: {sim:.4f})")
            if sim >= 0.75:
                print(f"✅ MATCH — recognized as '{name}'")
            else:
                print(f"❌ NO MATCH — unknown speaker")
            print(f"{'='*50}")

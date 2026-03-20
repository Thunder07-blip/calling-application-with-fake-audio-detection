import numpy as np
from livekit import rtc
import logging

logger = logging.getLogger("ml_agent.audio_processor")

def process_audio_frame(frame: rtc.AudioFrame) -> float:
    try:
        # Convert audio frame data to numpy array
        # LiveKit returns audio data as 16-bit PCM
        audio_data = np.frombuffer(frame.data, dtype=np.int16)
        
        if len(audio_data) == 0:
            return 0.0
            
        # Ensure we use float64 for math to prevent overflow
        audio_data_float = audio_data.astype(np.float64)
        
        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_data_float**2))
        return rms
    except Exception as e:
        logger.error(f"Error processing audio frame: {e}")
        return 0.0

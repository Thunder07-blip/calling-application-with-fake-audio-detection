import asyncio
import os
import aiohttp
import numpy as np
import time
import livekit.rtc as rtc

# Ensure you have 'aiohttp', 'numpy', and 'livekit' installed via pip.
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/token")

async def get_token(identity: str, room: str):
    async with aiohttp.ClientSession() as session:
        url = f"{BACKEND_URL}?identity={identity}&room={room}"
        async with session.get(url) as resp:
            data = await resp.json()
            return data["token"], data["livekit_url"]

async def main():
    identity = f"test_publisher_{int(time.time())}"
    print(f"Requesting token for {identity}...")
    token, livekit_url = await get_token(identity, "testroom")
    print(f"Token received. Connecting to {livekit_url}...")

    room = rtc.Room()
    
    # We explicitly wait for the connection to form
    await room.connect(livekit_url, token)
    print("Connected to room!")

    # Attempt to publish a sine wave
    source = rtc.AudioSource(16000, 1) # 16kHz, 1 channel
    track = rtc.LocalAudioTrack.create_audio_track("sine_wave", source)
    
    options = rtc.TrackPublishOptions()
    options.source = rtc.TrackSource.SOURCE_MICROPHONE
    
    publication = await room.local_participant.publish_track(track, options)
    print("Successfully published audio track!")

    # Generate Audio Frames
    sample_rate = 16000
    frequency = 440.0 # 440Hz sine wave
    duration_ms = 20 # 20ms frame
    samples_per_frame = int(sample_rate * duration_ms / 1000)
    
    t = 0.0
    dt = 1.0 / sample_rate
    
    print("Streaming audio... Press Ctrl+C to stop in terminal.")
    try:
        while True:
            # Generate 20ms of audio frame
            frame_data = np.zeros(samples_per_frame, dtype=np.int16)
            for i in range(samples_per_frame):
                frame_data[i] = int(32767.0 * 0.5 * np.sin(2.0 * np.pi * frequency * t))
                t += dt

            try:
                # Constructing an AudioFrame for capture source
                frame = rtc.AudioFrame(frame_data.tobytes(), sample_rate, 1, samples_per_frame)
                await source.capture_frame(frame)
            except Exception as e:
                pass
                
            await asyncio.sleep(duration_ms / 1000.0)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        print("Stopping stream...")
    finally:
        await room.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

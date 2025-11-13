"""
Example: Using AI providers without UI components
"""

from providers import ElevenLabsProvider, WaveSpeedProvider, ReplicateProvider

# Example 1: ElevenLabs Text-to-Speech
el = ElevenLabsProvider(api_key="your_elevenlabs_key")
audio_file = el.generate(
    text="Hello, this is a test of text-to-speech.",
    voice_id="21m00Tcm4TlvDq8ikWAM",  # Optional: use character voice ID
    model_id="eleven_multilingual_v2"
)
print(f"Generated audio: {audio_file}")

# Example 2: ElevenLabs Speech-to-Speech (voice conversion)
converted_audio = el.speech_to_speech(
    audio_path="recorded_voice.wav",
    voice_id="character_voice_id_here",
    model_id="eleven_multilingual_sts_v2"
)
print(f"Converted audio: {converted_audio}")

# Example 3: WaveSpeed InfiniteTalk
ws = WaveSpeedProvider(api_key="your_wavespeed_key")
video_file = ws.generate(
    prompt="happy and energetic",
    image_path="character_photo.jpg",
    audio_path="dialogue.mp3",
    resolution="720p",
    seed=-1
)
print(f"Generated video: {video_file}")

# Example 4: Replicate Veo 3.1
rep = ReplicateProvider(api_key="your_replicate_key")
video_file = rep.generate(
    prompt="a person walking through a forest",
    model="google/veo-3.1",
    first_frame_image="start_frame.jpg",
    reference_images=["ref1.jpg", "ref2.jpg"],  # Optional: 1-3 images
    duration=8,
    resolution="1080p",
    aspect_ratio="16:9"
)
print(f"Generated video: {video_file}")


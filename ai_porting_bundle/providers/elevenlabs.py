"""
ElevenLabs Text-to-Speech and Voice Conversion
API docs: https://api.elevenlabs.io/docs
"""

import os
import mimetypes
from .base import AIProvider, AIProviderError


class ElevenLabsProvider(AIProvider):
    """
    ElevenLabs TTS / voice conversion client.
    Defaults to the stock 'Rachel' voice if no voice_id is provided.
    """

    BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"
    SPEECH_TO_SPEECH_URL = "https://api.elevenlabs.io/v1/speech-to-speech"
    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel

    def generate(self, text: str, voice_id: str = None, output_format: str = "mp3", model_id: str = None, **kwargs) -> str:
        if not self.api_key:
            raise AIProviderError("ElevenLabs API key not set")
        if not text or not text.strip():
            raise AIProviderError("No text provided for TTS")

        voice = voice_id or self.DEFAULT_VOICE_ID
        url = f"{self.BASE_URL}/{voice}"

        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg" if output_format == "mp3" else "audio/wav",
            "Content-Type": "application/json",
        }
        body = {
            "text": text,
        }
        if model_id:
            body["model_id"] = model_id

        resp = self._make_request("POST", url, headers=headers, json=body, timeout=120)
        ctype = (resp.headers.get("Content-Type") or "").lower()
        ext = ".mp3" if "mpeg" in ctype or output_format == "mp3" else ".wav"
        out_path = os.path.join("/tmp", f"elevenlabs_tts{ext}")
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path

    def speech_to_speech(self, audio_path: str, voice_id: str = None, model_id: str = "eleven_multilingual_sts_v2", output_format: str = "mp3") -> str:
        if not self.api_key:
            raise AIProviderError("ElevenLabs API key not set")
        if not audio_path or not os.path.exists(audio_path):
            raise AIProviderError("Audio file not found for voice conversion")

        voice = voice_id or self.DEFAULT_VOICE_ID
        url = f"{self.SPEECH_TO_SPEECH_URL}/{voice}"
        headers = {
            "xi-api-key": self.api_key,
        }

        mime = mimetypes.guess_type(audio_path)[0] or "audio/wav"
        data = {
            "model_id": model_id,
            "output_format": output_format,
        }

        with open(audio_path, "rb") as fh:
            files = {
                "audio": (os.path.basename(audio_path), fh, mime),
            }
            resp = self._make_request("POST", url, headers=headers, data=data, files=files, timeout=300)

        ctype = (resp.headers.get("Content-Type") or "").lower()
        ext = ".mp3" if "mpeg" in ctype or output_format == "mp3" else ".wav"
        out_path = os.path.join("/tmp", f"elevenlabs_voice_convert{ext}")
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path



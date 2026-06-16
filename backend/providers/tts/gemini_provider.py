from __future__ import annotations

import io
import os
import time
import wave
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

from providers.base import BaseTTSProvider, BenchmarkMetadata, TTSResult

load_dotenv("config.env", override=False)
load_dotenv()


class GeminiTTSProvider(BaseTTSProvider):
    provider_name = "gemini"

    def __init__(
        self,
        model_name: Optional[str] = None,
        voice_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model_name = model_name or os.getenv("GEMINI_TTS_MODEL") or "gemini-3.1-flash-tts-preview"
        self.voice_name = voice_name or os.getenv("GEMINI_TTS_VOICE") or "Kore"
        resolved_api_key = api_key or os.getenv("LLM_API_KEY")
        if not resolved_api_key:
            raise ValueError("Falta LLM_API_KEY para Gemini TTS.")
        self.client = genai.Client(api_key=resolved_api_key, vertexai=False)

    def synthesize(self, text: str, output_path: str) -> TTSResult:
        start = time.perf_counter()
        wav_bytes = self.generate_audio(text)
        end = time.perf_counter()

        with open(output_path, "wb") as handle:
            handle.write(wav_bytes)

        return TTSResult(
            audio_path=output_path,
            latency_ms=(end - start) * 1000,
            sample_rate_hz=24000,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
                raw={"voice_name": self.voice_name},
            ),
        )

    def generate_audio(self, text: str) -> bytes:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self.voice_name
                        )
                    )
                ),
            ),
        )
        pcm_bytes = response.candidates[0].content.parts[0].inline_data.data
        return self._build_wav_bytes(pcm_bytes)

    def _build_wav_bytes(self, pcm_bytes: bytes) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(pcm_bytes)
        return buffer.getvalue()

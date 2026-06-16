from __future__ import annotations

import os
import time
from typing import Optional

from dotenv import load_dotenv

from providers.base import BaseTTSProvider, BenchmarkMetadata, TTSResult
from tts_module import TTSModule

load_dotenv("config.env", override=False)
load_dotenv()


class ElevenLabsTTSProvider(BaseTTSProvider):
    provider_name = "elevenlabs"

    def __init__(self, model_name: Optional[str] = None, voice_id: Optional[str] = None):
        self.model_name = model_name or os.getenv("TTS_MODEL") or "eleven_multilingual_v2"
        self.voice_id = voice_id or os.getenv("TTS_VOICE_ID") or "JBFqnCBsd6RMkjVDRZzb"
        self.module = TTSModule(model_id=self.model_name, voice_id=self.voice_id)

    def synthesize(self, text: str, output_path: str) -> TTSResult:
        start = time.perf_counter()
        audio_bytes = self.module.generate_audio(text)
        end = time.perf_counter()

        with open(output_path, "wb") as handle:
            handle.write(audio_bytes)

        return TTSResult(
            audio_path=output_path,
            latency_ms=(end - start) * 1000,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
                raw={"voice_id": self.voice_id},
            ),
        )

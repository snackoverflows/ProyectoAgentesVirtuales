from __future__ import annotations

import os
import time
from typing import Optional

from env_config import load_project_env
from providers.base import BaseSTTProvider, BenchmarkMetadata, STTResult
from stt_module import STTModule

load_project_env()


class ElevenLabsSTTProvider(BaseSTTProvider):
    provider_name = "elevenlabs"

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("STT_MODEL") or "scribe_v2"
        self.module = STTModule(model_id=self.model_name)

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        del language
        with open(audio_path, "rb") as handle:
            audio_bytes = handle.read()

        start = time.perf_counter()
        text = self.module.transcribe(audio_bytes, mime_type="audio/wav")
        end = time.perf_counter()

        return STTResult(
            text=text,
            latency_ms=(end - start) * 1000,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
            ),
        )

from __future__ import annotations

import os
import tempfile
import time
from typing import Optional

from env_config import load_project_env
from providers.base import BaseSTTProvider, BenchmarkMetadata, STTResult

load_project_env()


class MoonshineSTTProvider(BaseSTTProvider):
    provider_name = "moonshine"

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("MOONSHINE_MODEL") or "es"
        self._transcriber = None

    def _get_transcriber(self):
        if self._transcriber is not None:
            return self._transcriber

        try:
            from moonshine_voice.download import get_model_for_language
            from moonshine_voice.transcriber import Transcriber
        except ImportError as exc:
            raise ImportError(
                "Falta instalar 'moonshine-voice' para usar Moonshine STT."
            ) from exc

        model_path, model_arch = get_model_for_language(self.model_name)
        self._transcriber = Transcriber(model_path=model_path, model_arch=model_arch)
        return self._transcriber

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        del language
        try:
            from moonshine_voice.transcriber import load_wav_file
        except ImportError as exc:
            raise ImportError("Falta instalar 'moonshine-voice' para usar Moonshine STT.") from exc

        transcriber = self._get_transcriber()
        audio_data, sample_rate = load_wav_file(audio_path)
        start = time.perf_counter()
        result = transcriber.transcribe_without_streaming(audio_data, sample_rate=sample_rate)
        end = time.perf_counter()

        transcript_lines = [
            line.text.strip()
            for line in getattr(result, "lines", [])
            if getattr(line, "text", "").strip()
        ]
        transcript_text = " ".join(transcript_lines).strip()

        return STTResult(
            text=transcript_text,
            latency_ms=(end - start) * 1000,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
            ),
        )

    def transcribe_bytes(self, audio_bytes: bytes, mime_type: str = "audio/wav", language: Optional[str] = None) -> str:
        del language
        if "wav" not in mime_type:
            raise ValueError("Moonshine STT solo soporta audio WAV en esta integracion.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
            handle.write(audio_bytes)
            temp_path = handle.name

        try:
            return self.transcribe(temp_path).text
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

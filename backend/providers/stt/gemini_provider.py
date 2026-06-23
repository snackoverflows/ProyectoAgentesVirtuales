from __future__ import annotations

import mimetypes
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from env_config import load_project_env
from google import genai

from providers.base import BaseSTTProvider, BenchmarkMetadata, STTResult

load_project_env()


class GeminiSTTProvider(BaseSTTProvider):
    provider_name = "gemini"

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        self.model_name = model_name or os.getenv("GEMINI_STT_MODEL") or "gemini-3.5-flash"
        resolved_api_key = api_key or os.getenv("LLM_API_KEY")
        if not resolved_api_key:
            raise ValueError("Falta LLM_API_KEY para Gemini STT.")
        self.client = genai.Client(api_key=resolved_api_key, vertexai=False)

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"No se encontro el archivo de audio: {audio_path}")

        mime_type = mimetypes.guess_type(path.name)[0] or "audio/wav"
        prompt = self._build_prompt(language=language)

        uploaded = self.client.files.upload(file=str(path))
        start = time.perf_counter()
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, uploaded],
            )
        finally:
            try:
                self.client.files.delete(name=uploaded.name)
            except Exception:
                pass
        end = time.perf_counter()

        return STTResult(
            text=(response.text or "").strip(),
            latency_ms=(end - start) * 1000,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
                raw={"mime_type": mime_type},
            ),
        )

    def transcribe_bytes(self, audio_bytes: bytes, mime_type: str = "audio/wav", language: Optional[str] = None) -> str:
        suffix = mimetypes.guess_extension(mime_type) or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(audio_bytes)
            temp_path = handle.name

        try:
            return self.transcribe(temp_path, language=language).text
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def _build_prompt(self, language: Optional[str]) -> str:
        if language:
            return (
                f"Transcribe este audio al texto plano en idioma {language}. "
                "Devuelve solo la transcripcion, sin resumen, sin timestamps y sin formato adicional."
            )
        return "Transcribe este audio a texto plano. Devuelve solo la transcripcion, sin resumen ni timestamps."

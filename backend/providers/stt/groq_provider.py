from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx
from env_config import load_project_env
from providers.base import BaseSTTProvider, BenchmarkMetadata, STTResult

load_project_env()


class GroqSTTProvider(BaseSTTProvider):
    provider_name = "groq"

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model_name = model_name or os.getenv("GROQ_STT_MODEL") or "whisper-large-v3-turbo"
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.base_url = (base_url or os.getenv("GROQ_BASE_URL") or "https://api.groq.com").rstrip("/")
        if not self.api_key:
            raise ValueError("Falta GROQ_API_KEY para Groq STT.")

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"No se encontro el archivo de audio: {audio_path}")

        data = {
            "model": self.model_name,
            "response_format": "verbose_json",
        }
        if language:
            data["language"] = language

        with path.open("rb") as handle:
            files = {"file": (path.name, handle, "audio/wav")}
            start = time.perf_counter()
            response = httpx.post(
                f"{self.base_url}/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=data,
                files=files,
                timeout=120.0,
            )
            end = time.perf_counter()

        response.raise_for_status()
        payload = response.json()
        return STTResult(
            text=(payload.get("text") or "").strip(),
            latency_ms=(end - start) * 1000,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
                raw={"request_id": response.headers.get("x-request-id")},
            ),
        )

    def transcribe_bytes(self, audio_bytes: bytes, mime_type: str = "audio/wav", language: Optional[str] = None) -> str:
        suffix = ".wav"
        if "mpeg" in mime_type or "mp3" in mime_type:
            suffix = ".mp3"
        elif "ogg" in mime_type:
            suffix = ".ogg"
        elif "webm" in mime_type:
            suffix = ".webm"

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

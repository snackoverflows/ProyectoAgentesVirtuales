from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from env_config import load_project_env
from providers.base import BaseTTSProvider, BenchmarkMetadata, TTSResult

load_project_env()


class KokoroTTSProvider(BaseTTSProvider):
    provider_name = "kokoro"

    def __init__(
        self,
        model_name: Optional[str] = None,
        voices_path: Optional[str] = None,
        voice: Optional[str] = None,
        device: Optional[str] = None,
        language: Optional[str] = None,
    ):
        self.model_name = model_name or os.getenv("KOKORO_MODEL_PATH") or ""
        self.voices_path = voices_path or os.getenv("KOKORO_VOICES_PATH") or ""
        self.voice = voice or os.getenv("KOKORO_VOICE") or "default"
        self.device = device or os.getenv("KOKORO_DEVICE") or "cpu"
        self.language = language or os.getenv("KOKORO_LANGUAGE") or "es"
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        try:
            from kokoro import KPipeline
        except ImportError:
            return self._get_onnx_pipeline()

        kwargs = {"lang_code": self.language}
        if self.model_name:
            kwargs["repo_id"] = self.model_name
        self._pipeline = ("native", KPipeline(**kwargs))
        return self._pipeline

    def _get_onnx_pipeline(self):
        try:
            import espeakng_loader
            from kokoro_onnx import Kokoro
            from kokoro_onnx.config import EspeakConfig
        except ImportError as exc:
            raise ImportError(
                "Falta instalar 'kokoro' o 'kokoro-onnx' para usar Kokoro TTS."
            ) from exc

        if not self.model_name or not self.voices_path:
            raise ValueError(
                "Kokoro ONNX requiere KOKORO_MODEL_PATH y KOKORO_VOICES_PATH."
            )

        espeakng_loader.make_library_available()
        espeak_config = EspeakConfig(
            lib_path=espeakng_loader.get_library_path(),
            data_path=espeakng_loader.get_data_path(),
        )
        self._pipeline = (
            "onnx",
            Kokoro(
                model_path=self.model_name,
                voices_path=self.voices_path,
                espeak_config=espeak_config,
            ),
        )
        return self._pipeline

    def _write_audio(self, output_path: str, audio) -> None:
        try:
            import soundfile as sf
        except ImportError as exc:
            raise ImportError("Falta instalar 'soundfile' para escribir audio de Kokoro.") from exc

        sf.write(output_path, audio, 24000)

    def synthesize(self, text: str, output_path: str) -> TTSResult:
        pipeline_type, pipeline = self._get_pipeline()
        start = time.perf_counter()
        audio = None
        sample_rate = 24000
        if pipeline_type == "native":
            result = pipeline(text, voice=self.voice)
            for chunk in result:
                if isinstance(chunk, tuple) and len(chunk) >= 3:
                    audio = chunk[-1]
                    break
                if isinstance(chunk, dict) and "audio" in chunk:
                    audio = chunk["audio"]
                    break
        else:
            audio, sample_rate = pipeline.create(text=text, voice=self.voice, lang=self.language)
        end = time.perf_counter()

        if audio is None:
            raise RuntimeError("Kokoro no devolvio audio sintetizado.")

        self._write_audio(output_path, audio)
        return TTSResult(
            audio_path=output_path,
            latency_ms=(end - start) * 1000,
            sample_rate_hz=sample_rate,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name or "default",
                raw={
                    "voice": self.voice,
                    "device": self.device,
                    "language": self.language,
                    "pipeline": pipeline_type,
                },
            ),
        )

    def generate_audio(self, text: str) -> bytes:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
            output_path = handle.name

        try:
            self.synthesize(text, output_path)
            return Path(output_path).read_bytes()
        finally:
            try:
                os.remove(output_path)
            except OSError:
                pass

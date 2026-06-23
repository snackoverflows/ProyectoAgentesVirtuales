from __future__ import annotations

import os
import shutil
import tempfile
import time
from subprocess import CalledProcessError, run
from typing import Optional

from env_config import load_project_env
from providers.base import BaseSTTProvider, BenchmarkMetadata, STTResult

load_project_env()


class WhisperSTTProvider(BaseSTTProvider):
    provider_name = "whisper"

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        self.model_name = model_name or os.getenv("WHISPER_MODEL") or "base"
        self.device = device or os.getenv("WHISPER_DEVICE") or "cpu"
        self.ffmpeg_binary = os.getenv("FFMPEG_BINARY") or ""
        self._model = None

    def _ensure_ffmpeg(self) -> None:
        if shutil.which("ffmpeg"):
            return
        if not self.ffmpeg_binary:
            raise FileNotFoundError(
                "Whisper requiere ffmpeg. Configura FFMPEG_BINARY con la ruta a ffmpeg.exe o agrega ffmpeg al PATH."
            )
        ffmpeg_dir = os.path.dirname(self.ffmpeg_binary)
        if not ffmpeg_dir:
            raise FileNotFoundError(
                "FFMPEG_BINARY no es valido. Debe apuntar a ffmpeg.exe o deja ffmpeg disponible en PATH."
            )
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    def _patch_whisper_audio_loader(self, whisper_module) -> None:
        ffmpeg_executable = self.ffmpeg_binary or shutil.which("ffmpeg") or "ffmpeg"
        audio_module = whisper_module.audio

        def load_audio(file: str, sr: int = audio_module.SAMPLE_RATE):
            cmd = [
                ffmpeg_executable,
                "-nostdin",
                "-threads",
                "0",
                "-i",
                file,
                "-f",
                "s16le",
                "-ac",
                "1",
                "-acodec",
                "pcm_s16le",
                "-ar",
                str(sr),
                "-",
            ]
            try:
                out = run(cmd, capture_output=True, check=True).stdout
            except CalledProcessError as exc:
                raise RuntimeError(f"Failed to load audio: {exc.stderr.decode()}") from exc
            return audio_module.np.frombuffer(out, audio_module.np.int16).flatten().astype(audio_module.np.float32) / 32768.0

        audio_module.load_audio = load_audio

    def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            import whisper
        except ImportError as exc:
            raise ImportError("Falta instalar 'openai-whisper' para usar STT local con Whisper.") from exc

        self._ensure_ffmpeg()
        self._patch_whisper_audio_loader(whisper)
        self._model = whisper.load_model(self.model_name, device=self.device)
        return self._model

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        model = self._get_model()
        start = time.perf_counter()
        result = model.transcribe(
            audio_path,
            language=language,
            fp16=self.device.lower() != "cpu",
        )
        end = time.perf_counter()
        return STTResult(
            text=(result.get("text") or "").strip(),
            latency_ms=(end - start) * 1000,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
                raw={"device": self.device},
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

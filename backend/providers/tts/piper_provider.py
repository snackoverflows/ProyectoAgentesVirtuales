from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from providers.base import BaseTTSProvider, BenchmarkMetadata, TTSResult

load_dotenv("config.env", override=False)
load_dotenv()


class PiperTTSProvider(BaseTTSProvider):
    provider_name = "piper"

    def __init__(
        self,
        binary_path: Optional[str] = None,
        model_path: Optional[str] = None,
        config_path: Optional[str] = None,
        speaker_id: Optional[str] = None,
    ):
        self.binary_path = binary_path or os.getenv("PIPER_BINARY") or "piper"
        self.model_name = model_path or os.getenv("PIPER_MODEL_PATH") or ""
        self.config_path = config_path or os.getenv("PIPER_CONFIG_PATH") or ""
        self.speaker_id = speaker_id or os.getenv("PIPER_SPEAKER_ID") or "0"
        self._voice = None

    def _resolve_binary(self) -> str:
        resolved = shutil.which(self.binary_path) or self.binary_path
        if not Path(resolved).exists() and shutil.which(self.binary_path) is None:
            raise FileNotFoundError(
                "No se encontro el binario de Piper. Configura PIPER_BINARY con la ruta correcta."
            )
        return resolved

    def _get_voice(self):
        if self._voice is not None:
            return self._voice
        if not self.model_name:
            raise ValueError("Falta PIPER_MODEL_PATH para usar Piper TTS.")

        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise ImportError("Falta instalar 'piper-tts' para usar Piper TTS.") from exc

        self._voice = PiperVoice.load(
            model_path=self.model_name,
            config_path=self.config_path or None,
        )
        return self._voice

    def _build_command(self, output_path: str) -> list[str]:
        if not self.model_name:
            raise ValueError("Falta PIPER_MODEL_PATH para usar Piper TTS.")

        command = [
            self._resolve_binary(),
            "--model",
            self.model_name,
            "--output_file",
            output_path,
            "--speaker",
            str(self.speaker_id),
        ]
        if self.config_path:
            command.extend(["--config", self.config_path])
        return command

    def synthesize(self, text: str, output_path: str) -> TTSResult:
        start = time.perf_counter()
        process = None
        try:
            command = self._build_command(output_path)
            process = subprocess.run(
                command,
                input=text,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            voice = self._get_voice()
            with wave.open(output_path, "wb") as wav_file:
                voice.synthesize_wav(text, wav_file)
        else:
            if process.returncode != 0:
                raise RuntimeError(
                    f"Piper TTS fallo con codigo {process.returncode}: {(process.stderr or process.stdout).strip()}"
                )
        end = time.perf_counter()

        return TTSResult(
            audio_path=output_path,
            latency_ms=(end - start) * 1000,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
                raw={"speaker_id": self.speaker_id},
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

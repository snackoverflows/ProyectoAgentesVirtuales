# stt_module.py
from elevenlabs.client import ElevenLabs
import os
import typing
import json

from env_config import load_project_env

load_project_env()


class STTModule:
    """
    Módulo para Speech-to-Text usando ElevenLabs (wrapper).
    """

    def __init__(self, model_id: str = None, client: typing.Any = None):
        self.model_id = self._resolve_model_id(model_id or os.getenv("STT_MODEL"))
        self.client = client

    def _resolve_model_id(self, model_id: typing.Optional[str]) -> str:
        allowed_models = {"scribe_v1", "scribe_v1_experimental", "scribe_v2"}
        normalized = (model_id or "").strip()
        if normalized in allowed_models:
            return normalized

        return "scribe_v2"

    def _get_client(self):
        if self.client is not None:
            return self.client

        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("Falta ELEVENLABS_API_KEY para STT")

        self.client = ElevenLabs(api_key=api_key)
        return self.client

    def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        """
        Transcribe audio bytes y devuelve texto.
        Usa el cliente speech_to_text.convert de ElevenLabs.
        """
        eleven = self._get_client()

        audio_file = ("voice.wav", audio_bytes, mime_type)

        print(f"[STTModule] Using model_id={self.model_id}, mime_type={mime_type}, bytes={len(audio_bytes)}")
        resp = eleven.speech_to_text.convert(
            model_id=self.model_id,
            file=audio_file,
            file_format="other" if mime_type != "audio/wav" else "other",
        )

        for attr_name in ("text", "transcript", "transcription"):
            attr_value = getattr(resp, attr_name, None)
            if isinstance(attr_value, str) and attr_value.strip():
                return attr_value.strip()

        if isinstance(resp, str):
            return resp.strip()
        if isinstance(resp, bytes):
            return resp.decode("utf-8", errors="ignore").strip()
        if isinstance(resp, dict):
            for key in ("text", "transcript", "transcription", "result"):
                value = resp.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return json.dumps(resp, ensure_ascii=False)

        return str(resp).strip()

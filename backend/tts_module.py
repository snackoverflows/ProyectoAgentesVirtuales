# tts_module.py
from elevenlabs.client import ElevenLabs
import os
from typing import Iterator, List, Tuple
from dotenv import load_dotenv

load_dotenv()


class TTSModule:
    """
    Módulo para Text-to-Speech usando ElevenLabs
    """

    def __init__(
        self,
        voice_id: str = None,
        model_id: str = None,
        client=None,
    ):
        """
        voice_id: ID de la voz que se desea usar
        model_id: Modelo ElevenLabs
        """
        self.voice_id = voice_id or os.getenv("TTS_VOICE_ID") or "JBFqnCBsd6RMkjVDRZzb"
        self.model_id = model_id or os.getenv("TTS_MODEL_ID") or "eleven_multilingual_v2"
        self.client = client
        self.output_format = os.getenv("TTS_OUTPUT_FORMAT", "mp3_44100_128")
        self.streaming_model = os.getenv("TTS_STREAM_MODEL", "eleven_flash_v2_5")

    def _get_client(self):
        if self.client is not None:
            return self.client

        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("Falta ELEVENLABS_API_KEY")

        self.client = ElevenLabs(api_key=api_key)
        return self.client

    def generate_audio(self, text: str) -> bytes:
        """
        Convierte texto a audio en formato MP3.
        Devuelve los bytes del audio listos para enviar a frontend o Unity.
        """
        eleven = self._get_client()
        response = eleven.text_to_speech.convert(
            voice_id=self.voice_id,
            model_id=self.model_id,
            text=text,
            output_format=self.output_format,
        )

        # Si la librería devuelve un iterable, concatenamos bytes
        if isinstance(response, bytes):
            return response
        return b"".join(response)

    def generate_audio_stream(self, text: str) -> Iterator[bytes]:
        """
        Genera audio en chunks para reproducción en tiempo real.
        """
        eleven = self._get_client()
        response = eleven.text_to_speech.stream(
            voice_id=self.voice_id,
            model_id=self.streaming_model,
            text=text,
            output_format=self.output_format,
        )

        if isinstance(response, bytes):
            yield response
            return

        for chunk in response:
            if chunk:
                yield chunk

    def synthesize(self, text: str, mode: str = "auto") -> Tuple[bytes, List[str]]:
        """
        Genera audio completo con fallback automático.
        mode: auto | stream | batch
        """
        warnings: List[str] = []
        requested_mode = (mode or "auto").lower()

        if requested_mode in {"auto", "stream"}:
            try:
                return b"".join(self.generate_audio_stream(text)), warnings
            except Exception:
                warnings.append("TTS streaming no disponible; se usa modo batch.")

        return self.generate_audio(text), warnings

    def stream_with_fallback(self, text: str, mode: str = "auto") -> Tuple[Iterator[bytes], List[str]]:
        """
        Devuelve un iterador de chunks. Si streaming falla, devuelve un único chunk batch.
        """
        warnings: List[str] = []
        requested_mode = (mode or "auto").lower()

        if requested_mode in {"auto", "stream"}:
            try:
                return self.generate_audio_stream(text), warnings
            except Exception:
                warnings.append("TTS streaming no disponible; se usa modo batch.")

        audio = self.generate_audio(text)

        def _single_chunk() -> Iterator[bytes]:
            if audio:
                yield audio

        return _single_chunk(), warnings
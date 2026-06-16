from __future__ import annotations

import os

from providers.base import BaseLLMProvider, BaseSTTProvider, BaseTTSProvider
from providers.llm import GeminiLLMProvider, GroqLLMProvider, OllamaLLMProvider
from providers.stt import (
    ElevenLabsSTTProvider,
    GeminiSTTProvider,
    GroqSTTProvider,
    MoonshineSTTProvider,
    WhisperSTTProvider,
)
from providers.tts import (
    ElevenLabsTTSProvider,
    GeminiTTSProvider,
    KokoroTTSProvider,
    PiperTTSProvider,
)


def build_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    resolved = (provider_name or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    if resolved == "gemini":
        return GeminiLLMProvider()
    if resolved == "groq":
        return GroqLLMProvider()
    if resolved == "ollama":
        return OllamaLLMProvider()
    raise ValueError(f"Proveedor LLM no soportado: {resolved}")


def build_stt_provider(provider_name: str | None = None) -> BaseSTTProvider:
    resolved = (provider_name or os.getenv("STT_PROVIDER") or "elevenlabs").strip().lower()
    if resolved == "elevenlabs":
        return ElevenLabsSTTProvider()
    if resolved == "gemini":
        return GeminiSTTProvider()
    if resolved == "groq":
        return GroqSTTProvider()
    if resolved == "whisper":
        return WhisperSTTProvider()
    if resolved == "moonshine":
        return MoonshineSTTProvider()
    raise ValueError(f"Proveedor STT no soportado: {resolved}")


def build_tts_provider(provider_name: str | None = None) -> BaseTTSProvider:
    resolved = (provider_name or os.getenv("TTS_PROVIDER") or "elevenlabs").strip().lower()
    if resolved == "elevenlabs":
        return ElevenLabsTTSProvider()
    if resolved == "gemini":
        return GeminiTTSProvider()
    if resolved == "piper":
        return PiperTTSProvider()
    if resolved == "kokoro":
        return KokoroTTSProvider()
    raise ValueError(f"Proveedor TTS no soportado: {resolved}")

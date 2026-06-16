from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class BenchmarkMetadata:
    provider: str
    model: str
    raw: Optional[Dict[str, Any]] = field(default=None)


@dataclass
class LLMResult:
    text: str
    total_latency_ms: float
    ttft_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    metadata: Optional[BenchmarkMetadata] = None


@dataclass
class STTResult:
    text: str
    latency_ms: float
    audio_duration_ms: Optional[float] = None
    metadata: Optional[BenchmarkMetadata] = None


@dataclass
class TTSResult:
    audio_path: str
    latency_ms: float
    audio_duration_ms: Optional[float] = None
    sample_rate_hz: Optional[int] = None
    metadata: Optional[BenchmarkMetadata] = None


class BaseLLMProvider(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResult:
        raise NotImplementedError


class BaseSTTProvider(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> STTResult:
        raise NotImplementedError


class BaseTTSProvider(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def synthesize(self, text: str, output_path: str) -> TTSResult:
        raise NotImplementedError

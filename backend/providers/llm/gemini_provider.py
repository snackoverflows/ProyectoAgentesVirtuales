from __future__ import annotations

import os
import time
from typing import Optional

from dotenv import load_dotenv
from google import genai

from providers.base import BaseLLMProvider, BenchmarkMetadata, LLMResult

load_dotenv("config.env", override=False)
load_dotenv()


class GeminiLLMProvider(BaseLLMProvider):
    provider_name = "gemini"

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        self.model_name = model_name or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        resolved_api_key = api_key or os.getenv("LLM_API_KEY")
        if not resolved_api_key:
            raise ValueError("Falta LLM_API_KEY para Gemini")
        self.client = genai.Client(api_key=resolved_api_key, vertexai=False)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResult:
        start = time.perf_counter()
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        response = self.client.models.generate_content(model=self.model_name, contents=contents)
        end = time.perf_counter()

        return LLMResult(
            text=(response.text or "").strip(),
            total_latency_ms=(end - start) * 1000,
            ttft_ms=None,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
                raw={"sdk": "google-genai"},
            ),
        )

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Optional

from env_config import load_project_env
from providers.base import BaseLLMProvider, BenchmarkMetadata, LLMResult

load_project_env()


class OllamaLLMProvider(BaseLLMProvider):
    provider_name = "ollama"

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL") or "gemma3"
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResult:
        start = time.perf_counter()
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        request = urllib.request.Request(
            url=f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
        end = time.perf_counter()

        return LLMResult(
            text=(body.get("response") or "").strip(),
            total_latency_ms=(end - start) * 1000,
            ttft_ms=None,
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
                raw={"done": body.get("done", True)},
            ),
        )

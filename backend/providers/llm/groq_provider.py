from __future__ import annotations

import os
import time
from typing import Optional

from dotenv import load_dotenv
from groq import Groq

from providers.base import BaseLLMProvider, BenchmarkMetadata, LLMResult

load_dotenv("config.env", override=False)
load_dotenv()


class GroqLLMProvider(BaseLLMProvider):
    provider_name = "groq"

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        response_format: Optional[str] = None,
    ):
        self.model_name = model_name or os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant"
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.base_url = (base_url or os.getenv("GROQ_BASE_URL") or "https://api.groq.com").rstrip("/")
        configured_response_format = (response_format or os.getenv("GROQ_RESPONSE_FORMAT") or "").strip().lower()
        if configured_response_format:
            self.response_format = configured_response_format
        elif self.model_name == "qwen/qwen3-32b":
            self.response_format = "json"
        else:
            self.response_format = ""
        if not self.api_key:
            raise ValueError("Falta GROQ_API_KEY para Groq")
        self.client = Groq(api_key=self.api_key, base_url=self.base_url)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResult:
        messages = []
        resolved_system_prompt = system_prompt
        resolved_prompt = prompt
        if self.response_format == "json":
            json_instruction = "Responde en JSON valido con una sola clave llamada text."
            if resolved_system_prompt:
                resolved_system_prompt = f"{resolved_system_prompt}\n{json_instruction}"
            else:
                resolved_system_prompt = json_instruction
            resolved_prompt = f"{prompt}\nDevuelve solo json."

        if resolved_system_prompt:
            messages.append({"role": "system", "content": resolved_system_prompt})
        messages.append({"role": "user", "content": resolved_prompt})

        request_kwargs = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 1,
            "max_completion_tokens": 1024,
            "top_p": 1,
            "stream": False,
            "stop": None,
        }
        if self.response_format == "json":
            request_kwargs["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        completion = self.client.chat.completions.create(**request_kwargs)
        end = time.perf_counter()

        choice = (completion.choices or [None])[0]
        message = choice.message if choice else None
        usage = completion.usage
        return LLMResult(
            text=((message.content if message else "") or "").strip(),
            total_latency_ms=(end - start) * 1000,
            ttft_ms=None,
            input_tokens=(usage.prompt_tokens if usage else None),
            output_tokens=(usage.completion_tokens if usage else None),
            metadata=BenchmarkMetadata(
                provider=self.provider_name,
                model=self.model_name,
                raw={"id": completion.id, "object": completion.object},
            ),
        )

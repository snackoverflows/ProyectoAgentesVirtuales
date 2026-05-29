import json
import re
from typing import Any, Dict, List, Optional, Tuple


class ChatService:
    def __init__(self, memory_module, llm_module, error_handler, available_emotion_profiles, default_emotion_profile: str):
        self.memory_module = memory_module
        self.llm_module = llm_module
        self.error_handler = error_handler
        self.available_emotion_profiles = available_emotion_profiles
        self.default_emotion_profile = default_emotion_profile

    def parse_agent_response_payload(self, raw_text: str) -> Dict[str, Any]:
        stripped = raw_text.strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
        if fenced_match:
            parsed = json.loads(fenced_match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed

        return {"text": stripped, "emotion_profile": self.default_emotion_profile}

    def run_chat_workflow(
        self,
        user_text: str,
        user_id: str,
        session_id: str,
        normalize_emotion_profile,
        log_debug,
    ) -> Tuple[str, List[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]], str]:
        warnings: List[str] = []
        conversation_history = self.memory_module.get_last_messages(n=10, user_id=user_id, session_id=session_id)
        agent_prompt = self.llm_module.build_agent_response_prompt(self.available_emotion_profiles)
        raw_llm_response = self.error_handler.run_with_retry(
            self.llm_module.generate_response,
            user_text,
            history=conversation_history,
            system_prompt=agent_prompt,
            fallback=json.dumps(
                {"text": "Lo siento, no pude generar una respuesta en este momento.", "emotion_profile": self.default_emotion_profile},
                ensure_ascii=False,
            ),
        )

        log_debug("llm.chat.raw", raw_llm_response)
        parsed_response = self.parse_agent_response_payload(raw_llm_response)
        log_debug("llm.chat.parsed", parsed_response)

        llm_response = parsed_response.get("text") or raw_llm_response
        emotion_profile = normalize_emotion_profile(parsed_response.get("emotion_profile", self.default_emotion_profile))
        self.memory_module.add_message(
            "assistant",
            llm_response,
            user_id,
            session_id,
            metadata={"emotion_profile": emotion_profile},
        )
        return llm_response, warnings, None, None, emotion_profile

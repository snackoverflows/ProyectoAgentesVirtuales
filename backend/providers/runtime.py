from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from env_config import load_project_env
from providers.base import BaseLLMProvider, BaseSTTProvider, BaseTTSProvider
from providers.factories import build_llm_provider, build_stt_provider, build_tts_provider

load_project_env()


class ProviderBackedLLMModule:
    """
    Adaptador runtime para conservar la API usada por ChatService y ScheduleService.
    """

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self.provider = provider or build_llm_provider()
        self.model = self.provider.model_name
        self.system_prompt = os.getenv("LLM_SYSTEM_PROMPT") or (
            "Eres un asistente virtual que responde de manera clara, breve y amigable. "
            "Responde solo con JSON valido y solo usa informacion real del usuario."
        )
        self.available_emotion_profiles = self._load_emotion_profiles_from_env()

    def _load_emotion_profiles_from_env(self) -> List[str]:
        raw_profiles = os.getenv(
            "LLM_EMOTION_PROFILES",
            "neutral,friendly,thinking,sad,surprise,happy,point_lu,point_ru",
        )
        configured = [profile.strip().lower() for profile in raw_profiles.split(",") if profile.strip()]
        required = ["neutral", "friendly", "thinking", "sad", "surprise", "happy", "point_lu", "point_ru"]

        profiles: List[str] = []
        for profile in configured + required:
            if profile and profile not in profiles:
                profiles.append(profile)
        return profiles

    def build_agent_response_prompt(self, available_profiles: Optional[List[str]] = None) -> str:
        profiles = available_profiles or self.available_emotion_profiles
        profiles_text = ", ".join(profiles)
        default_profile = profiles[0] if profiles else "neutral"

        return (
            "Tu nombre es Chippy. Eres un asistente conversacional para un avatar en Unity. "
            "Debes responder siempre con JSON valido y nada mas. "
            "Manten tus respuestas cortas. "
            "Cuando menciones horas al usuario, nunca uses formato HH:MM ni 24h. "
            "Expresa siempre la hora en formato de 12 horas, escrita de forma natural en palabras, por ejemplo "
            "'siete y cincuenta de la mañana' o 'tres de la tarde'. "
            "No respondas a nada que no este relacionado con horarios; si el usuario pregunta otra cosa, redirige brevemente al tema de horarios. "
            "Tu salida debe usar exactamente estas keys: text y emotion_profile. "
            "emotion_profile debe ser siempre uno de los perfiles permitidos. "
            "No pidas doble confirmacion para crear el horario: detecta el intento del usuario y genera el horario cuando lo pida explicitamente, "
            "o bien ofrecelo luego de haber agregado cursos si todavia falta confirmacion. "
            "Antes de generar el horario, no repitas todos los cursos agregados; en su lugar, indicale que puede ver los cursos considerados "
            "y las restricciones usando los botones de la esquina superior izquierda de la pantalla. "
            "Cuando el horario quede listo, NO enumeres cursos, grupos, profesores ni restricciones: solo dile que ya esta listo y que puede ver "
            "el horario en la esquina superior derecha de la pantalla. "
            "Usa emotion_profile='point_lu' cuando indiques que mire botones o paneles en la esquina superior izquierda (cursos/restricciones). "
            "Usa emotion_profile='point_ru' cuando indiques que mire el horario en la esquina superior derecha. "
            "Nunca inventes perfiles fuera de la lista. "
            "Siempre debes especificar un emotion_profile.\n\n"
            f"Perfiles permitidos: {profiles_text}\n\n"
            "Formato esperado de salida:\n"
            "{\n"
            '  "text": "respuesta breve para el usuario",\n'
            f'  "emotion_profile": "{default_profile}"\n'
            "}\n\n"
            "Reglas: responde solo con JSON valido y usa un solo emotion_profile por respuesta."
        )

    def generate_response(
        self,
        user_text: str,
        history: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        prompt = self._compose_prompt(user_text, history=history, system_prompt=system_prompt)
        return self.provider.generate(prompt, system_prompt=system_prompt).text

    def _compose_prompt(
        self,
        user_text: str,
        history: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        history_lines: List[str] = []
        for msg in history or []:
            role = "assistant" if msg.get("role") == "assistant" else "user"
            history_lines.append(f"{role}: {msg.get('content', '')}")
        history_block = "\n".join(history_lines)

        parts = []
        if system_prompt:
            parts.append(system_prompt)
        if history_block:
            parts.append(f"Historial reciente:\n{history_block}")
        parts.append(f"Mensaje del usuario:\n{user_text}")
        return "\n\n".join(parts)

    def build_schedule_chat_prompt(
        self,
        user_text: str,
        current_draft: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        draft_json = json.dumps(
            current_draft
            or {
                "courses": [],
                "constraints": {
                    "hard": [],
                    "soft": [],
                    "optimization": {"objectives": []},
                    "scoring": {"mode": "fixed", "per": 30},
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        history_json = json.dumps(history or [], ensure_ascii=False, indent=2)

        return (
            "Tu nombre es Chippy. Eres un asistente para construir paso a paso el borrador de horarios. "
            "Responde solo con JSON valido. Sin markdown. Sin texto extra. "
            "No llames a ActionModule ni inventes horarios finales.\n\n"
            "FORMATO DE SALIDA OBLIGATORIO (sin keys extra):\n"
            "{\n"
            '  "assistant_message": "texto breve",\n'
            '  "draft": {"courses": [], "constraints": {"hard": [], "soft": [], "optimization": {"objectives": []}, "scoring": {"mode": "fixed", "per": 30}}},\n'
            '  "status": "collecting" | "awaiting_confirmation",\n'
            '  "missing_items": [],\n'
            '  "emotion_profile": "neutral",\n'
            '  "should_generate": false\n'
            "}\n\n"
            "CONTRATO CANONICO OBLIGATORIO (constraints.py):\n"
            "- constraints solo puede tener: hard, soft, optimization, scoring.\n"
            "- optimization solo puede tener: objectives.\n"
            "- Operadores permitidos: include, exclude, prefer, avoid, <=, >=, ==, between, outside.\n"
            "- Types permitidos: day, time_window, professor, group, course, metric, tag, campus, custom.\n"
            "- day usa days con: Lunes, Martes, Miercoles, Jueves, Viernes, Sabado, Domingo.\n"
            "- time_window usa range.start y range.end en HH:MM.\n"
            "- professor/group/course/campus usan values, no target.\n"
            "- metric requiere target. Si operator es <=, >= o ==, requiere value numerico.\n"
            "- optimization.objectives usa operator, target, priority.\n"
            "- En optimization.objectives, operator SOLO puede ser maximize o minimize.\n"
            "- No inventes keys nuevas en ningun nivel.\n\n"
            "REGLAS DE DRAFT:\n"
            "- Mantener y actualizar draft; no resetear salvo que el usuario lo pida.\n"
            "- Cada item en courses es seccion o grupo alternativo.\n"
            "- Cada curso usa: course, group, professor, meetings.\n"
            "- group y professor pueden faltar individualmente mientras construyes el borrador, pero no ambos a la vez al momento de generar.\n"
            "- Para generar un horario, cada curso necesita nombre de curso, al menos uno entre group o professor, y meetings con day/start/end.\n"
            "- Cada meeting usa: day, start, end.\n"
            "- Formato obligatorio de group: Grupo N.\n"
            "- Horas estructuradas en HH:MM.\n"
            "- En assistant_message, nunca uses HH:MM ni formato 24h.\n"
            "- Si el usuario pregunta algo fuera del tema de horarios, responde breve y amable, y redirige la conversacion hacia planificacion de horarios.\n"
            "- Si el usuario habla de horarios pero aun no hay cursos cargados, responde de forma natural; no uses por defecto frases genericas como 'Tome en cuenta esa preferencia'.\n"
            "- Si falta group pero hay professor y meetings, puedes seguir construyendo el borrador.\n"
            "- Si falta professor pero hay group y meetings, puedes seguir construyendo el borrador.\n"
            "- Si faltan group y professor juntos, pide al menos uno antes de generar.\n"
            "- Si faltan meetings, pide los horarios antes de generar.\n"
            "- Si falta informacion clave, preguntar solo por lo faltante.\n"
            "- Restricciones soportadas por el backend:\n"
            "  * 'quiero ir pocos dias a la U' -> optimization.objectives += {operator: minimize, target: days_on_campus, priority: 2}.\n"
            "  * 'quiero solo clases en la manana' -> hard += {type: time_window, scope: meeting, operator: outside, range: {start: 12:00, end: 23:59}}.\n"
            "- Cuando una frase coincida con una restriccion soportada, usa esa traduccion canonica exacta.\n"
            "- should_generate=true cuando el usuario pida generar y ya tengas los datos necesarios de cada curso.\n"
            "- Si el usuario dice 'genera' o equivalente y el borrador ya esta completo, no pidas confirmaciones adicionales.\n\n"
            "EMOCION:\n"
            "- emotion_profile obligatorio y debe ser uno de: " + ", ".join(self.available_emotion_profiles) + ".\n\n"
            f"Historial reciente:\n{history_json}\n\n"
            f"Borrador actual:\n{draft_json}\n\n"
            f"Mensaje del usuario:\n{user_text}"
        )

    def generate_schedule_chat_turn(
        self,
        user_text: str,
        current_draft: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        prompt = self.build_schedule_chat_prompt(user_text, current_draft=current_draft, history=history)
        return self.provider.generate(prompt, system_prompt=self.system_prompt).text


class ProviderBackedSTTModule:
    def __init__(self, provider: Optional[BaseSTTProvider] = None):
        self.provider = provider or build_stt_provider()

    def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        provider_module = getattr(self.provider, "module", None)
        if provider_module is not None and hasattr(provider_module, "transcribe"):
            return provider_module.transcribe(audio_bytes, mime_type)
        if hasattr(self.provider, "transcribe_bytes"):
            return self.provider.transcribe_bytes(audio_bytes, mime_type)
        raise NotImplementedError("El provider STT activo no soporta transcripcion directa desde bytes.")


class ProviderBackedTTSModule:
    def __init__(self, provider: Optional[BaseTTSProvider] = None):
        self.provider = provider or build_tts_provider()

    def generate_audio(self, text: str) -> bytes:
        provider_module = getattr(self.provider, "module", None)
        if provider_module is not None and hasattr(provider_module, "generate_audio"):
            return provider_module.generate_audio(text)
        if hasattr(self.provider, "generate_audio"):
            return self.provider.generate_audio(text)
        raise NotImplementedError("El provider TTS activo no soporta generate_audio en runtime.")

    def generate_audio_stream(self, text: str):
        provider_module = getattr(self.provider, "module", None)
        if provider_module is not None and hasattr(provider_module, "generate_audio_stream"):
            return provider_module.generate_audio_stream(text)

        def _single_chunk():
            audio = self.generate_audio(text)
            if audio:
                yield audio

        return _single_chunk()

    def synthesize(self, text: str, mode: str = "auto"):
        provider_module = getattr(self.provider, "module", None)
        if provider_module is not None and hasattr(provider_module, "synthesize"):
            return provider_module.synthesize(text, mode=mode)
        return self.generate_audio(text), []

    def stream_with_fallback(self, text: str, mode: str = "auto"):
        provider_module = getattr(self.provider, "module", None)
        if provider_module is not None and hasattr(provider_module, "stream_with_fallback"):
            return provider_module.stream_with_fallback(text, mode=mode)
        return self.generate_audio_stream(text), []


def build_runtime_llm_module() -> ProviderBackedLLMModule:
    return ProviderBackedLLMModule()


def build_runtime_stt_module() -> ProviderBackedSTTModule:
    return ProviderBackedSTTModule()


def build_runtime_tts_module() -> ProviderBackedTTSModule:
    return ProviderBackedTTSModule()

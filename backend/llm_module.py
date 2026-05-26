# llm_module.py
import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from google import genai

load_dotenv("config.env", override=False)
load_dotenv()

class LLMModule:
    """
    Conversational Core para un agente virtual.
    Configurable vía variables de entorno para poder cambiar de modelo sin tocar el código.
    """

    def __init__(self):
        # API key genérica para LLM
        self.api_key = os.getenv("LLM_API_KEY")
        if not self.api_key:
            raise ValueError("Falta LLM_API_KEY en el entorno")

        # Modelo configurable genérico
        self.model = os.getenv("LLM_MODEL") or "gemini-2.5-flash"

        # Prompt de sistema genérico
        self.system_prompt = os.getenv(
            "LLM_SYSTEM_PROMPT"
        ) or (
            "Eres un asistente virtual que responde de manera clara, breve y amigable. "
            "Si necesitas pedir una herramienta para horarios, inicia la respuesta con TOOL:schedule."
        )

        self.available_emotion_profiles = self._load_emotion_profiles_from_env()

        # Inicializa el cliente LLM
        self.client = genai.Client(api_key=self.api_key, vertexai=False)

        # Historial de conversación
        self.history = []

    def _friendly_fallback_response(self) -> str:
        return "No entendí bien, puedes repetirlo?"

    def _load_emotion_profiles_from_env(self) -> List[str]:
        raw_profiles = os.getenv("LLM_EMOTION_PROFILES", "neutral,friendly,thinking,sad,surprise,happy")
        profiles = [profile.strip() for profile in raw_profiles.split(",") if profile.strip()]
        return profiles or ["neutral"]

    def build_agent_response_prompt(self, available_profiles: Optional[List[str]] = None) -> str:
        profiles = available_profiles or self.available_emotion_profiles
        profiles_text = ", ".join(profiles)
        default_profile = profiles[0] if profiles else "neutral"

        return (
            "Eres un asistente conversacional para un avatar en Unity. "
            "Debes responder siempre con JSON valido y nada mas. "
            "Tu salida debe usar exactamente estas keys: text, emotion_profile y tool_call. "
            "emotion_profile debe ser siempre uno de los perfiles permitidos. "
            "tool_call debe ser null salvo que realmente necesites activar una herramienta. "
            "Si necesitas pedir el flujo de horarios, usa tool_call con el valor schedule. "
            "Nunca inventes perfiles fuera de la lista. "
            "Siempre debes especificar un emotion_profile.\n\n"
            f"Perfiles permitidos: {profiles_text}\n\n"
            "Formato esperado de salida:\n"
            "{\n"
            '  "text": "respuesta breve para el usuario",\n'
            f'  "emotion_profile": "{default_profile}",\n'
            '  "tool_call": null\n'
            "}\n\n"
            "Reglas: responde solo con JSON valido, usa un solo emotion_profile por respuesta, "
            "y si no necesitas herramienta deja tool_call en null."
        )

    def _build_contents(
        self,
        user_text: str,
        history: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> List[Dict]:
        contents = [
            {"role": "user", "parts": [{"text": system_prompt or self.system_prompt}]}
        ]

        for msg in history or []:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        contents.append({"role": "user", "parts": [{"text": user_text}]})
        return contents

    def _generate_text(
        self,
        prompt_text: str,
        history: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        store_user_text: Optional[str] = None,
    ) -> str:
        contents = self._build_contents(prompt_text, history or self.history, system_prompt=system_prompt)

        last_error = None
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents
                )
                response_text = response.text.strip()
                if store_user_text is not None:
                    self.add_to_history("user", store_user_text)
                    self.add_to_history("assistant", response_text)
                return response_text
            except Exception as e:
                last_error = e

        return f"Error LLM: {last_error}"

    def add_to_history(self, role: str, content: str):
        """Agrega un mensaje al historial de la conversación"""
        self.history.append({"role": role, "content": content})

    def generate_response(
        self,
        user_text: str,
        history: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Genera una respuesta usando el LLM configurado.
        """
        response_text = self._generate_text(
            user_text,
            history=history or self.history,
            system_prompt=system_prompt,
            store_user_text=user_text,
        )

        if response_text.startswith("Error LLM:"):
            return self._friendly_fallback_response()

        return response_text

    def build_schedule_input_prompt(
        self,
        user_text: str,
        template_payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        template_json = json.dumps(
            template_payload or {
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

        return (
            "Eres un analizador de requisitos para horarios. "
            "Tienes disponible ActionModule más adelante, pero en esta etapa NO lo ejecutes. "
            "Tu tarea es devolver solo el input JSON estructurado que se le entregaría a ActionModule. "
            "No incluyas explicaciones, markdown ni texto adicional. "
            "No inventes campos nuevos ni cambies los nombres de las keys. "
            "Si falta información, pregunta o devuelve el borrador más simple posible usando el template.\n\n"
            "ESQUEMA ESTRICTO PERMITIDO. Usa exactamente estas keys y ninguna otra en la raíz:\n"
            "{\n"
            '  "courses": [\n'
            '    {\n'
            '      "course": "Nombre del curso",\n'
            '      "group": "Seccion o grupo",\n'
            '      "professor": "Profesor o TBD",\n'
            '      "meetings": [\n'
            '        {"day": "Lunes", "start": "08:00", "end": "10:00"}\n'
            "      ]\n"
            "    }\n"
            "  ],\n"
            '  "constraints": {\n'
            '    "hard": [ /* reglas canonicas */ ],\n'
            '    "soft": [ /* reglas canonicas */ ],\n'
            '    "optimization": {"objectives": [ /* objetivos canonicos */ ]},\n'
            '    "scoring": {"mode": "fixed", "per": 30}\n'
            "  }\n"
            "}\n\n"
            "Reglas importantes:\n"
            "- Cada objeto en courses es una sección o grupo alternativo.\n"
            "- meetings contiene los bloques obligatorios de esa sección.\n"
            "- Nunca omitas el campo professor en ningún curso. Si el profesor no está claro, pregunta una aclaración breve; si aun así no se sabe, usa exactamente 'Desconocido'.\n"
            "- Si el usuario agrega otro curso con el mismo nombre y el mismo profesor, primero verifica si quiere corregir el registro existente; solo crea otra entrada si explícitamente es otro grupo.\n"
            "- Si falta el número de grupo o cualquier otro campo del template inicial, pregunta siempre antes de inventarlo.\n"
            "- Si un mismo course aparece varias veces, son alternativas o correcciones del mismo curso según el profesor y el grupo indicado.\n"
            "- constraints.hard y constraints.soft deben usar el DSL canónico de constraints.py.\n"
            "- optimization.objectives debe describir objetivos soportados por constraints.py.\n"
            "- max_per_day y top_n son opcionales; inclúyelos solo si el usuario los pide explícitamente.\n"
            "- Usa únicamente estas keys: courses, constraints, course, group, professor, meetings, day, start, end, hard, soft, optimization, scoring, objectives, mode, per.\n"
            "- Devuelve un JSON válido y nada más.\n\n"
            f"Catálogo/base de referencia:\n{template_json}\n\n"
            f"Instrucción del usuario:\n{user_text}"
        )

    def generate_schedule_input(
        self,
        user_text: str,
        template_payload: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        prompt = self.build_schedule_input_prompt(user_text, template_payload=template_payload)
        return self._generate_text(
            prompt,
            history=history or self.history,
            store_user_text=user_text,
        )

    def build_schedule_chat_prompt(
        self,
        user_text: str,
        current_draft: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        draft_json = json.dumps(
            current_draft or {
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
            "Eres un asistente conversacional para construir paso a paso la estructura de un horario. "
            "Tu objetivo es ayudar a completar y confirmar un borrador JSON antes de llamar al generador. "
            "NO llames a ActionModule ni inventes horarios finales. "
            "Solo actualiza el borrador con la informacion nueva y decide si falta algo o si ya se puede pedir confirmacion para generar.\n\n"
            "Debes seguir exactamente el siguiente formato de salida y no agregar ninguna otra key:\n"
            "{\n"
            '  "assistant_message": "texto breve para el usuario",\n'
            '  "draft": {\n'
            '    "courses": [ ... ],\n'
            '    "constraints": {\n'
            '      "hard": [ ... ],\n'
            '      "soft": [ ... ],\n'
            '      "optimization": {"objectives": [ ... ]},\n'
            '      "scoring": {"mode": "fixed", "per": 30}\n'
            "    }\n"
            "  },\n"
            '  "status": "collecting" | "awaiting_confirmation",\n'
            '  "missing_items": ["..."],\n'
            '  "emotion_profile": "neutral",\n'
            '  "should_generate": false\n'
            "}\n\n"
            "Debes responder solo con JSON valido y exactamente con esta forma.\n"
            "Reglas:\n"
            "- Mantén la estructura del draft con keys courses y constraints.\n"
            "- Cada objeto en courses representa una seccion/grupo alternativo.\n"
            "- meetings contiene bloques obligatorios de la seccion.\n"
            "- Usa exactamente las keys course, group, professor y meetings en cada curso.\n"
            "- Nunca omitas el campo professor en ningún curso. Si el profesor no está claro, pregunta una aclaración breve; si aun así no se sabe, usa exactamente 'Desconocido'.\n"
            "- Si el usuario agrega otro curso con el mismo nombre y el mismo profesor, primero verifica si quiere corregir el registro existente; solo crea otra entrada si explícitamente es otro grupo.\n"
            "- Si falta el número de grupo o cualquier otro campo del template inicial, pregunta siempre antes de inventarlo.\n"
            "- Si un mismo course aparece varias veces, trátalo como alternativa o corrección según el profesor y el grupo indicado.\n"
            "- Cada meeting debe usar solo day, start y end.\n"
            "- Usa constraints.hard, constraints.soft, constraints.optimization y constraints.scoring.\n"
            "- Si el usuario no especifica max_per_day o top_n, no los inventes ni los agregues.\n"
            "- Si faltan cursos, preferencias o restricciones relevantes, pregunta solo por lo faltante.\n"
            "- Si una preferencia es ambigua, pregunta una aclaración breve en lugar de inventarla.\n"
            "- Si ya hay suficiente informacion para generar horarios, cambia status a awaiting_confirmation y pregunta si desea generar los horarios.\n"
            "- should_generate solo debe ser true cuando el usuario ya confirmó explícitamente que quiere generar.\n"
            "- Si el usuario pide agregar o corregir algo, actualiza el draft en lugar de resetearlo.\n\n"
            "- Incluye siempre emotion_profile con uno de estos valores: " + ", ".join(self.available_emotion_profiles) + ".\n"
            "- No uses keys fuera del template canónico.\n\n"
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
        return self._generate_text(
            prompt,
            history=history or self.history,
            store_user_text=user_text,
        )